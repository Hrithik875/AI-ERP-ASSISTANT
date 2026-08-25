# Phase 3 — Security Report: Admin Console Authentication & CORS Hardening

**Project:** AI-ERP Assistant  
**Phase:** 3 — Security Hardening & SQL Safety  
**Date:** 2026-08-25  
**Status:** ✅ Complete  

---

## Executive Summary

Phase 3 addresses two major attack surfaces in the AI-ERP Assistant backend:
1. **Unauthenticated Raw-SQL Admin Endpoints:** Gated all `/db/*` management routes behind a mandatory `X-Admin-Key` shared-secret header check (`ADMIN_API_KEY`), eliminating unauthenticated arbitrary SQL execution.
2. **Permissive Wildcard CORS Configuration:** Replaced `allow_origins=["*"]` with an environment-driven, explicit whitelist (`ALLOWED_ORIGINS`, defaulting to `http://localhost:3000`), blocking cross-origin browser requests from unauthorized domains.

---

## The Dual-SQL Architecture & Risk Profile

The AI-ERP Assistant architecture deliberately contains **two distinct SQL execution pathways**, each designed for different personas with fundamentally different security characteristics:

```
                                  ┌──────────────────────────────┐
                                  │   Incoming HTTP Request      │
                                  └──────────────┬───────────────┘
                                                 │
                        ┌────────────────────────┴────────────────────────┐
                        ▼                                                 ▼
        ┌──────────────────────────────┐                  ┌──────────────────────────────┐
        │  Assistant Tool Execution    │                  │ Database Management Console  │
        │  (/chat, /voice-query)       │                  │ (/db/*)                      │
        ├──────────────────────────────┤                  ├──────────────────────────────┤
        │ • Invoker: Student / Faculty │                  │ • Invoker: Database Admin    │
        │ • Predefined Parameterized   │                  │ • Arbitrary Raw SQL Execution│
        │   SQL Templates              │                  │ • Direct Table Editing / DDL │
        │ • LLM cannot alter SQL query │                  │ • Requires X-Admin-Key Auth  │
        │   structure                  │                  │                              │
        │ • Safe against SQL Injection │                  │ • Gated behind Shared Secret │
        └──────────────┬───────────────┘                  └──────────────┬───────────────┘
                       │                                                 │
                       ▼                                                 ▼
        ┌────────────────────────────────────────────────────────────────────────────────┐
        │                     Aurora MySQL / Local MySQL Database                        │
        └────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Pathway A: AI Assistant Tool-Based Queries (Safe by Design)
* **Components:** `backend/ai/tools/attendance_tool.py`, `grades_tool.py`, `student_tool.py`, `faculty_tool.py`, `timetable_tool.py`, `course_tool.py`.
* **Execution Model:** The LLM does **not** construct arbitrary SQL strings. Instead, the AI agent parses user intents and dispatches to predefined Python tool methods.
* **Security Mechanics:** All queries utilize strict parameterized query templates with `%s` placeholders (e.g. `SELECT * FROM students WHERE usn = %s`). Extracted entity arguments (e.g., student USN or course codes) are passed as separated data tuples to the MySQL driver (`pymysql` / DB-API cursor).
* **Risk Profile:** Minimal risk of SQL injection. The LLM cannot alter the database schema or execute unauthorized statements (`DROP`, `DELETE`, `UPDATE`) through the assistant interface.

### 2. Pathway B: Database Management Console (Administrative Surface)
* **Components:** `backend/routes/database.py` (`POST /db/query`, `GET /db/tables`, `POST /db/tables/{table}`, `DELETE /db/tables/{table}/{id}`, `POST /db/import/{table}`).
* **Execution Model:** Exists specifically for institutional administrators to inspect tables, debug schema changes, import student datasets, and run ad-hoc maintenance queries.
* **Security Mechanics (Post-Phase 3):** All endpoints under `/db` are enforced by FastAPI's `dependencies=[Depends(verify_admin_key)]`. Any request lacking a valid `X-Admin-Key` header matching `ADMIN_API_KEY` is terminated immediately with `401 Unauthorized`.
* **Risk Profile:** High capability, now appropriately restricted to authorized administrators via shared-secret gating.

---

## Vulnerability Analysis: Before vs. After

| Area | Pre-Phase 3 State (Vulnerable) | Root Cause | Post-Phase 3 State (Remediated) | Verification Result |
|---|---|---|---|---|
| **Database Console (`/db/*`)** | Any client could send arbitrary SQL (including `DROP TABLE`, `DELETE FROM`, or data exfiltration) to `POST /db/query` without any authentication. | `database.py` router had no dependency checks or authentication middleware attached. | Added `verify_admin_key` dependency verifying `X-Admin-Key` header against `ADMIN_API_KEY`. Returns `401 Unauthorized` on missing/invalid keys. | ✅ `curl` without header returned `HTTP 401`.<br>✅ `curl` with invalid key returned `HTTP 401`.<br>✅ `curl` with valid key returned `HTTP 200` with query results. |
| **CORS Policy** | `main.py` configured with `allow_origins=["*"]`, allowing any external website in a browser to make cross-origin requests to the API. | Wildcard origin setting left in `CORSMiddleware`. | `main.py` now reads `ALLOWED_ORIGINS` from environment (defaults to `http://localhost:3000`). Wildcard removed. | ✅ Origin `http://localhost:3000` receives `Access-Control-Allow-Origin: http://localhost:3000`.<br>✅ Arbitrary origin `http://malicious.com` receives `Access-Control-Allow-Origin: None`. |
| **Assistant Normal Operation** | Unauthenticated assistant endpoints (`/chat`, `/voice-query`, `/documents`). | By design for rapid demo access. | Gating is scoped strictly to `/db/*`. Regular `/chat` and `/voice-query` endpoints remain functional for demo users without requiring admin keys. | ✅ `POST /chat` succeeds without `X-Admin-Key` (unaffected). |

---

## Verification Logs & Evidence

### 1. Database Admin Console Authentication Check
```python
# Test 1: POST /db/query without header
Request: POST http://localhost:8000/db/query {"sql": "SELECT 1"}
Response: HTTP 401 Unauthorized
Body: {"detail": "Unauthorized: X-Admin-Key header is missing or incorrect. This endpoint is restricted to database administrators."}

# Test 2: POST /db/query with invalid header
Request: POST http://localhost:8000/db/query (Header: X-Admin-Key: wrong-key)
Response: HTTP 401 Unauthorized

# Test 3: POST /db/query with valid header
Request: POST http://localhost:8000/db/query (Header: X-Admin-Key: local-dev-admin-key)
Response: HTTP 200 OK
Body: {"type": "select", "rowCount": 1, "columns": ["n"], "rows": [{"n": 1}]}
```

### 2. CORS Allowed vs. Rejected Origin Test
```
Request with Origin 'http://localhost:3000':
  Access-Control-Allow-Origin: http://localhost:3000 (ALLOWED)

Request with Origin 'http://malicious.com':
  Access-Control-Allow-Origin: None (REJECTED)
```

---

## Explicit Future Work & Scope Boundaries

The following security features are intentionally deferred to future iterations per the project architecture roadmap:
1. **Role-Based Access Control (RBAC):** Implementing fine-grained user authentication (JWT/OAuth2) distinguishing student, faculty, HOD, and Dean personas for tailored query permissions.
2. **Audit Logging for Admin Actions:** Writing structured audit logs to CloudWatch/filesystem capturing the actor, timestamp, and executed SQL query for all `/db/*` actions.
3. **Admin Key Rotation Mechanism:** Integration with AWS Secrets Manager or KMS for automated rotation of `ADMIN_API_KEY` in production environments.
