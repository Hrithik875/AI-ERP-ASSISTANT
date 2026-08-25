"""
AI ERP Assistant — Database Management Console Routes
=======================================================
Provides endpoints for the frontend database management UI:
- List tables, view/edit/delete rows
- Execute raw SQL queries
- Export/Import data (CSV, JSON)

Security: every route in this file is protected by the ADMIN_API_KEY
shared-secret check (X-Admin-Key request header).  The regular assistant
routes (/chat, /voice-query, etc.) are intentionally NOT covered here.
"""

import csv
import io
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db.connection import get_cursor, execute_query, execute_write
from config import AURORA_DATABASE, ADMIN_API_KEY

logger = logging.getLogger("erp-assistant")


# ── Admin authentication dependency ─────────────────────────────────────────

def verify_admin_key(x_admin_key: Optional[str] = Header(default=None)):
    """
    FastAPI dependency that enforces the ADMIN_API_KEY shared-secret gate.

    Every route in this router requires a valid X-Admin-Key header.  This
    protects the raw-SQL admin console (/db/*) from unauthenticated access
    without affecting the assistant's normal /chat or /voice-query routes.

    Returns 401 if the header is absent or the value does not match.
    """
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail=(
                "Unauthorized: X-Admin-Key header is missing or incorrect. "
                "This endpoint is restricted to database administrators."
            ),
        )


router = APIRouter(
    prefix="/db",
    tags=["database-console"],
    dependencies=[Depends(verify_admin_key)],
)


# ── Pydantic Models ─────────────────────────────────────────────────────────

class SQLQueryRequest(BaseModel):
    sql: str
    params: list = []

class RowInsertRequest(BaseModel):
    data: dict

class RowUpdateRequest(BaseModel):
    data: dict


# ── JSON serializer for MySQL types ─────────────────────────────────────────

def _serialize_value(val):
    """Convert MySQL-specific types to JSON-safe primitives."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, timedelta):
        total = int(val.total_seconds())
        h, remainder = divmod(total, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    return val



def _serialize_rows(rows):
    """Serialize a list of dict rows so all values are JSON-safe."""
    return [
        {k: _serialize_value(v) for k, v in row.items()}
        for row in rows
    ]


# ══════════════════════════════════════════════════════════════════════════
# List all tables
# ══════════════════════════════════════════════════════════════════════════

@router.get("/tables")
def list_tables():
    """Return a list of all tables with row counts and column info."""
    logger.info("Database console: listing tables")
    try:
        tables_sql = """
            SELECT TABLE_NAME, TABLE_ROWS, TABLE_COMMENT
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """
        tables = execute_query(tables_sql, (AURORA_DATABASE,))

        result = []
        for t in tables:
            table_name = t["TABLE_NAME"]
            # Get column details
            cols_sql = """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY,
                       COLUMN_DEFAULT, EXTRA
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """
            columns = execute_query(cols_sql, (AURORA_DATABASE, table_name))

            # Get actual row count (TABLE_ROWS is approximate)
            count_rows = execute_query(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
            actual_count = count_rows[0]["cnt"] if count_rows else 0

            result.append({
                "name": table_name,
                "rowCount": actual_count,
                "columns": _serialize_rows(columns),
            })

        return result

    except Exception as e:
        logger.error(f"Failed to list tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Get table data with pagination & filtering
# ══════════════════════════════════════════════════════════════════════════

@router.get("/tables/{table_name}")
def get_table_data(
    table_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: Optional[str] = None,
    sort_order: str = Query(default="ASC", regex="^(ASC|DESC)$"),
    search: Optional[str] = None,
):
    """Get paginated table data with optional sorting and search."""
    logger.info(f"Database console: fetching {table_name} page={page}")

    # Validate table name to prevent SQL injection
    valid_tables = execute_query(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s",
        (AURORA_DATABASE,)
    )
    valid_names = {t["TABLE_NAME"] for t in valid_tables}
    if table_name not in valid_names:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    try:
        # Get column names for search
        cols = execute_query(
            """SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
               WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
               ORDER BY ORDINAL_POSITION""",
            (AURORA_DATABASE, table_name)
        )
        col_names = [c["COLUMN_NAME"] for c in cols]

        # Build query
        where_clause = ""
        params = []

        if search:
            # Search across all VARCHAR/TEXT columns
            searchable = [c["COLUMN_NAME"] for c in cols
                         if c["DATA_TYPE"] in ("varchar", "text", "char", "longtext", "mediumtext")]
            if searchable:
                conditions = [f"`{col}` LIKE %s" for col in searchable]
                where_clause = "WHERE " + " OR ".join(conditions)
                params = [f"%{search}%" for _ in searchable]

        # Count total
        count_sql = f"SELECT COUNT(*) AS total FROM `{table_name}` {where_clause}"
        total_result = execute_query(count_sql, tuple(params))
        total = total_result[0]["total"] if total_result else 0

        # Sort
        order_clause = ""
        if sort_by and sort_by in col_names:
            order_clause = f"ORDER BY `{sort_by}` {sort_order}"
        else:
            order_clause = "ORDER BY 1 ASC"  # Default: sort by first column

        # Paginate
        offset = (page - 1) * page_size
        data_sql = f"SELECT * FROM `{table_name}` {where_clause} {order_clause} LIMIT %s OFFSET %s"
        params.extend([page_size, offset])

        rows = execute_query(data_sql, tuple(params))

        return {
            "table": table_name,
            "columns": col_names,
            "columnDetails": _serialize_rows(cols),
            "rows": _serialize_rows(rows),
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": (total + page_size - 1) // page_size,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get table data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Insert a row
# ══════════════════════════════════════════════════════════════════════════

@router.post("/tables/{table_name}")
def insert_row(table_name: str, body: RowInsertRequest):
    """Insert a new row into the specified table."""
    logger.info(f"Database console: INSERT into {table_name}")

    # Validate table
    valid_tables = execute_query(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s",
        (AURORA_DATABASE,)
    )
    if table_name not in {t["TABLE_NAME"] for t in valid_tables}:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    try:
        data = body.data
        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        columns = ", ".join(f"`{k}`" for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = tuple(data.values())

        sql = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
        with get_cursor() as cur:
            cur.execute(sql, values)
            new_id = cur.lastrowid

        return {"success": True, "id": new_id, "message": f"Row inserted into {table_name}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Insert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Update a row
# ══════════════════════════════════════════════════════════════════════════

@router.put("/tables/{table_name}/{row_id}")
def update_row(table_name: str, row_id: int, body: RowUpdateRequest):
    """Update a row by its primary key (id)."""
    logger.info(f"Database console: UPDATE {table_name} id={row_id}")

    valid_tables = execute_query(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s",
        (AURORA_DATABASE,)
    )
    if table_name not in {t["TABLE_NAME"] for t in valid_tables}:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    try:
        data = body.data
        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        set_clause = ", ".join(f"`{k}` = %s" for k in data.keys())
        values = tuple(data.values()) + (row_id,)

        sql = f"UPDATE `{table_name}` SET {set_clause} WHERE id = %s"
        affected = execute_write(sql, values)

        if affected == 0:
            raise HTTPException(status_code=404, detail=f"Row {row_id} not found in {table_name}")

        return {"success": True, "message": f"Row {row_id} updated in {table_name}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Delete a row
# ══════════════════════════════════════════════════════════════════════════

@router.delete("/tables/{table_name}/{row_id}")
def delete_row(table_name: str, row_id: int):
    """Delete a row by its primary key (id)."""
    logger.info(f"Database console: DELETE {table_name} id={row_id}")

    valid_tables = execute_query(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s",
        (AURORA_DATABASE,)
    )
    if table_name not in {t["TABLE_NAME"] for t in valid_tables}:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    try:
        affected = execute_write(f"DELETE FROM `{table_name}` WHERE id = %s", (row_id,))
        if affected == 0:
            raise HTTPException(status_code=404, detail=f"Row {row_id} not found")

        return {"success": True, "message": f"Row {row_id} deleted from {table_name}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Execute raw SQL
# ══════════════════════════════════════════════════════════════════════════

@router.post("/query")
def execute_sql(body: SQLQueryRequest):
    """Execute a raw SQL query. Returns results for SELECT, affected rows for writes."""
    logger.info(f"Database console: raw SQL query")

    sql = body.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Empty SQL query")

    try:
        is_select = sql.upper().startswith(("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"))

        if is_select:
            rows = execute_query(sql, tuple(body.params) if body.params else ())
            return {
                "type": "select",
                "rows": _serialize_rows(rows),
                "rowCount": len(rows),
                "columns": list(rows[0].keys()) if rows else [],
            }
        else:
            affected = execute_write(sql, tuple(body.params) if body.params else ())
            return {
                "type": "write",
                "affectedRows": affected,
                "message": f"{affected} row(s) affected",
            }

    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Export table data
# ══════════════════════════════════════════════════════════════════════════

@router.get("/export/{table_name}")
def export_table(
    table_name: str,
    format: str = Query(default="csv", regex="^(csv|json)$"),
):
    """Export all rows from a table as CSV or JSON."""
    logger.info(f"Database console: export {table_name} as {format}")

    valid_tables = execute_query(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s",
        (AURORA_DATABASE,)
    )
    if table_name not in {t["TABLE_NAME"] for t in valid_tables}:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    try:
        rows = execute_query(f"SELECT * FROM `{table_name}`")
        serialized = _serialize_rows(rows)

        if format == "json":
            content = json.dumps(serialized, indent=2, default=str)
            return StreamingResponse(
                io.BytesIO(content.encode("utf-8")),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={table_name}.json"},
            )
        else:
            output = io.StringIO()
            if serialized:
                writer = csv.DictWriter(output, fieldnames=serialized[0].keys())
                writer.writeheader()
                writer.writerows(serialized)
            csv_bytes = output.getvalue().encode("utf-8")
            return StreamingResponse(
                io.BytesIO(csv_bytes),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={table_name}.csv"},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Import data into a table
# ══════════════════════════════════════════════════════════════════════════

@router.post("/import/{table_name}")
async def import_table(table_name: str, file: UploadFile = File(...)):
    """Import data from a CSV or JSON file into a table."""
    logger.info(f"Database console: import into {table_name} from {file.filename}")

    valid_tables = execute_query(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s",
        (AURORA_DATABASE,)
    )
    if table_name not in {t["TABLE_NAME"] for t in valid_tables}:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    try:
        content = await file.read()
        content_str = content.decode("utf-8")

        rows = []
        if file.filename and file.filename.endswith(".json"):
            rows = json.loads(content_str)
            if not isinstance(rows, list):
                raise HTTPException(status_code=400, detail="JSON must be an array of objects")
        else:
            # CSV
            reader = csv.DictReader(io.StringIO(content_str))
            rows = list(reader)

        if not rows:
            return {"success": True, "imported": 0, "message": "No rows to import"}

        imported = 0
        with get_cursor() as cur:
            for row in rows:
                # Filter out empty values and 'id' column
                filtered = {k: v for k, v in row.items() if k != "id" and v not in (None, "")}
                if not filtered:
                    continue

                columns = ", ".join(f"`{k}`" for k in filtered.keys())
                placeholders = ", ".join(["%s"] * len(filtered))
                values = tuple(filtered.values())

                sql = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
                cur.execute(sql, values)
                imported += 1

        return {"success": True, "imported": imported, "message": f"{imported} rows imported into {table_name}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
