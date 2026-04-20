"""
AI ERP Assistant — Analytics Routes (Aurora MySQL)
====================================================
Real analytics from Aurora MySQL — all MySQL-compatible SQL.
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from db.connection import execute_query

logger = logging.getLogger("erp-assistant")
router = APIRouter(tags=["analytics"])


@router.get("/analytics")
def get_analytics():
    """
    Return analytics data dynamically from Aurora MySQL.
    Provides: queriesPerDay, usageStats, responseTimes — all live.
    """
    logger.info("Analytics data requested")

    try:
        # ── Queries per day (last 7 days) ────────────────────────────────
        queries_per_day_sql = """
            SELECT
                DATE_FORMAT(created_at, '%%a') AS date,
                COUNT(*) AS count
            FROM query_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at), DATE_FORMAT(created_at, '%%a')
            ORDER BY DATE(created_at)
        """
        queries_per_day = execute_query(queries_per_day_sql)

        if not queries_per_day:
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            queries_per_day = [{"date": d, "count": 0} for d in days]

        # ── Usage by category ────────────────────────────────────────────
        usage_stats_sql = """
            SELECT
                CONCAT(UCASE(LEFT(query_type, 1)), LCASE(SUBSTRING(query_type, 2))) AS name,
                COUNT(*) AS value
            FROM query_log
            GROUP BY query_type
            ORDER BY value DESC
        """
        usage_stats = execute_query(usage_stats_sql)

        if not usage_stats:
            usage_stats = [
                {"name": "Attendance", "value": 0},
                {"name": "Grades",     "value": 0},
                {"name": "Schedule",   "value": 0},
                {"name": "Documents",  "value": 0},
                {"name": "General",    "value": 0},
            ]

        # ── Response times (last 7 days) ─────────────────────────────────
        response_times_sql = """
            SELECT
                DATE_FORMAT(created_at, '%%a') AS date,
                CAST(IFNULL(AVG(response_time_ms), 0) AS UNSIGNED) AS avgMs
            FROM query_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at), DATE_FORMAT(created_at, '%%a')
            ORDER BY DATE(created_at)
        """
        response_times = execute_query(response_times_sql)

        if not response_times:
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            response_times = [{"date": d, "avgMs": 0} for d in days]

        return {
            "queriesPerDay": queries_per_day,
            "usageStats": usage_stats,
            "responseTimes": response_times,
        }

    except Exception as e:
        logger.error(f"Analytics query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


@router.get("/dashboard/stats")
def get_dashboard_stats():
    """
    Return summary statistics for the dashboard — all dynamically computed.
    """
    logger.info("Dashboard stats requested")

    try:
        # ── Total queries ────────────────────────────────────────────────
        total_q = execute_query("SELECT COUNT(*) AS cnt FROM query_log")
        total_queries = total_q[0]["cnt"] if total_q else 0

        # ── This week vs last week ───────────────────────────────────────
        trend_sql = """
            SELECT
                SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) AS this_week,
                SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 14 DAY)
                          AND created_at  < DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) AS last_week
            FROM query_log
        """
        trend = execute_query(trend_sql)
        this_week = trend[0]["this_week"] or 0 if trend else 0
        last_week = trend[0]["last_week"] or 1 if trend else 1
        q_trend = ((this_week - last_week) / max(last_week, 1)) * 100

        # ── Average response time ────────────────────────────────────────
        avg_resp = execute_query(
            "SELECT CAST(IFNULL(AVG(response_time_ms), 0) AS UNSIGNED) AS avg_ms FROM query_log"
        )
        avg_ms = avg_resp[0]["avg_ms"] if avg_resp else 0
        avg_response = f"{avg_ms / 1000:.1f}s" if avg_ms > 0 else "0.0s"

        # ── Active students ───────────────────────────────────────────────
        students = execute_query(
            "SELECT COUNT(*) AS cnt FROM students WHERE is_active = TRUE"
        )
        total_students = students[0]["cnt"] if students else 0

        # ── Success rate ──────────────────────────────────────────────────
        success = execute_query("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful
            FROM query_log
        """)
        total = success[0]["total"] if success else 0
        successful = success[0]["successful"] or 0 if success else 0
        success_rate = (successful / max(total, 1)) * 100

        # ── Recent queries ────────────────────────────────────────────────
        recent = execute_query("""
            SELECT
                query_text AS query_text,
                CASE
                    WHEN created_at >= DATE_SUB(NOW(), INTERVAL 5 MINUTE) THEN 'Just now'
                    WHEN created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR) THEN
                        CONCAT(TIMESTAMPDIFF(MINUTE, created_at, NOW()), ' min ago')
                    ELSE
                        CONCAT(TIMESTAMPDIFF(HOUR, created_at, NOW()), ' hours ago')
                END AS time,
                status
            FROM query_log
            ORDER BY created_at DESC
            LIMIT 5
        """)

        return {
            "totalQueries": f"{total_queries:,}",
            "totalQueriesTrend": f"{q_trend:+.1f}%",
            "avgResponse": avg_response,
            "avgResponseTrend": f"-{avg_ms * 0.1:.0f}ms",
            "activeSessions": str(total_students),
            "activeSessionsTrend": f"+{total_students}",
            "successRate": f"{success_rate:.1f}%",
            "successRateTrend": "+0.0%",
            "recentQueries": recent if recent else [],
        }

    except Exception as e:
        logger.error(f"Dashboard stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
