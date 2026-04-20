"""
AI ERP Assistant — Database Connection (Aurora MySQL)
======================================================
MySQL connection pool with context-manager access.
Uses PyMySQL for Lambda compatibility (pure Python, no C extensions).
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import pymysql
import pymysql.cursors

from config import (
    AURORA_HOST, AURORA_PORT, AURORA_USER,
    AURORA_PASSWORD, AURORA_DATABASE,
)

logger = logging.getLogger("erp-assistant")

# ── Connection Pool (simple reuse for Lambda) ──────────────────────────────
# Lambda reuses the global connection across warm invocations.
_connection: Optional[pymysql.connections.Connection] = None
_last_connection_failure: float = 0

def get_connection() -> pymysql.connections.Connection:
    """Return a reusable MySQL connection (creates one if needed)."""
    global _connection, _last_connection_failure
    import time
    
    # Fast-fail if we recently failed (avoid multiple 10s timeouts in one request)
    if time.time() - _last_connection_failure < 30:
        raise Exception("Database connection recently failed (fast-fail).")

    if _connection is None or not _connection.open:
        try:
            _connection = pymysql.connect(
                host=AURORA_HOST,
                port=AURORA_PORT,
                user=AURORA_USER,
                password=AURORA_PASSWORD,
                database=AURORA_DATABASE,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
            )
            logger.info(f"MySQL connection established: {AURORA_HOST}:{AURORA_PORT}/{AURORA_DATABASE}")
            _last_connection_failure = 0 # Reset on success
        except pymysql.err.OperationalError as e:
            if e.args[0] == 1049: # Unknown database
                logger.warning(f"Database {AURORA_DATABASE} not found, creating it now...")
                # Connect without database context
                temp_conn = pymysql.connect(
                    host=AURORA_HOST, port=AURORA_PORT, user=AURORA_USER, password=AURORA_PASSWORD, autocommit=True
                )
                with temp_conn.cursor() as cur:
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{AURORA_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                temp_conn.close()
                logger.info(f"Database {AURORA_DATABASE} created successfully. Reconnecting to create tables and seed...")
                
                # Reconnect now that the DB exists
                _last_connection_failure = 0
                conn = get_connection()
                
                # Create schema and seed data
                try:
                    from db.models import create_tables
                    from db.seed import seed_database
                    create_tables()
                    seed_database()
                    logger.info("Auto-initialization of schema and seeds complete.")
                except Exception as seed_err:
                    logger.error(f"Auto-init failed: {seed_err}")
                
                return conn
            else:
                _last_connection_failure = time.time()
                logger.error(f"Failed to connect to Aurora MySQL: {e}")
                raise
        except Exception as e:
            _last_connection_failure = time.time()
            logger.error(f"Failed to connect to Aurora MySQL: {e}")
            raise
    return _connection


@contextmanager
def get_cursor(dict_cursor: bool = True):
    """Context manager that yields a MySQL cursor."""
    conn = get_connection()
    cursor_class = pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor
    cur = conn.cursor(cursor_class)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


# ── Query Helpers ───────────────────────────────────────────────────────────

def execute_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a SELECT query and return list of dicts."""
    try:
        with get_cursor() as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Query failed: {e}\nSQL: {sql}\nParams: {params}")
        raise


def execute_write(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE and return affected row count."""
    try:
        with get_cursor(dict_cursor=False) as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return cur.rowcount
    except Exception as e:
        logger.error(f"Write failed: {e}\nSQL: {sql}\nParams: {params}")
        raise


def execute_insert_returning(sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    """
    Execute INSERT and return the inserted row.
    MySQL doesn't support RETURNING, so we use LAST_INSERT_ID().
    The caller should NOT include RETURNING clause; this method handles it.
    """
    try:
        with get_cursor() as cur:
            cur.execute(sql, params)
            last_id = cur.lastrowid
            if last_id:
                return {"id": last_id}
            return None
    except Exception as e:
        logger.error(f"Insert failed: {e}\nSQL: {sql}")
        raise


def close_pool():
    """Gracefully close the database connection."""
    global _connection
    if _connection and _connection.open:
        _connection.close()
        _connection = None
        logger.info("Database connection closed")
