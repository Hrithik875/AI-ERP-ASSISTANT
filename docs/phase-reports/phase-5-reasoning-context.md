# Phase 5 — Conversation Context, ERP Reasoning Layer & Tool Transparency Report

**Project:** AI-ERP Assistant  
**Phase:** 5 — Conversation Context, Reasoning Calculations, Explainable Answers & Tool Transparency  
**Date:** 2026-08-25  
**Status:** ✅ Complete  

---

## Executive Summary

Phase 5 addresses three core architectural limitations of the AI-ERP Assistant:
1. **Stateless Conversational Disconnect:** Prior to this phase, `/chat` requests were strictly stateless. The frontend UI did not send prior turns to the backend, causing referential follow-up queries (such as *"which one has the lowest attendance in that course?"*) to fail completely.
2. **LLM Arithmetic Hallucinations:** Questions requiring quantitative attendance calculations (such as *"how many more classes does this student need to attend to reach 75%?"* or *"how many classes can they safely miss?"*) were previously left to the LLM's non-deterministic text generation, which is prone to arithmetic errors.
3. **Opaque Tool Execution:** API responses lacked visibility into which underlying ERP tool or reasoning engine produced the result.

### Deliverables Completed
- **Bounded Conversation Context:** `ChatUI.tsx` and `api.ts` send the last $N=4$ turns as bounded history. `agent.py` and `chat.py` ingest history to resolve referential entities (student names, USNs, course codes) during intent classification and tool parameter extraction.
- **Deterministic ERP Reasoning Layer:** Implemented pure Python mathematical calculation engines (`compute_classes_needed_to_reach_target` and `compute_classes_can_miss`) within `AttendanceTool`. The LLM only formats the verified numerical results.
- **Explainable "At-Risk" Responses:** Flagged at-risk students now explicitly detail current attendance %, attended/total class counts, comparison thresholds, percentage-point shortage gaps, and consecutive classes required to regain eligibility.
- **Tool Transparency:** Added `tool_used` to `/chat` and `/text-query` response payloads (e.g. `"Reasoning (AttendanceTool)"`, `"AttendanceTool"`, `"DocumentTool"`, `"TimetableTool"`).

---

## 1. Multi-Turn Conversation Context

### Implementation Architecture
- **Frontend (`frontend/src/components/ChatUI.tsx` & `frontend/src/lib/api.ts`):** When submitting a new message, the frontend extracts the last 4 turns (`{role: "user" | "assistant", content: string}`) from the local state and sends it in the JSON request body: `{ message: "...", history: [...] }`.
- **Backend Classification (`backend/ai/agent.py`):** `classify_query` formats prior turns as conversation context. When a user asks *"which one has the lowest?"*, the classifier recognizes from prior turn context that the query refers to ERP attendance records rather than general chat.
- **Entity Resolution (`backend/ai/agent.py`):** `execute_tool_query` provides the prior turns in the tool extraction prompt, allowing the LLM router to extract entities like `course_code: "CS601"` from the previous turn's context.

### Verified Two-Turn Conversation Flow

```
[Turn 1: User] "Show me attendance for CS601"
  ↳ Classification: 'erp'
  ↳ Router Extraction: AttendanceTool {'action': 'course_summary', 'course_code': 'CS601'}
  ↳ Tool Used: 'AttendanceTool'
  ↳ Assistant Response:
      ### Attendance Summary for Course CS601
      | Course Code | Average Attendance (%) |
      |-------------|-----------------------|
      | CS601       | 87.58                 |
      The average attendance for students enrolled in CS601 is 87.58%...

[Turn 2: User] "Which one has the lowest attendance in that course?" (Sent with history=[Turn 1])
  ↳ Context Resolution: Resolves 'in that course' -> Course CS601
  ↳ Classification: 'erp'
  ↳ Router Extraction: AttendanceTool {'action': 'risk_list', 'course_code': 'CS601'}
  ↳ Tool Used: 'AttendanceTool'
  ↳ Assistant Response:
      ### Attendance Summary for Course CS601
      | Course Code | Average Attendance (%) |
      |-------------|-----------------------|
      | CS601       | 87.58                 |
      The average attendance for students enrolled in CS601 is 87.58%. Since no students are 
      currently at attendance risk, there is no specific student with low attendance to highlight.
```

---

## 2. Deterministic ERP Reasoning Layer

### Why Python Arithmetic, Not LLM Generation?
LLMs are probabilistic token predictors and routinely produce arithmetic errors when calculating rational functions involving fractional percentages. To guarantee 100% mathematical precision for institutional attendance policies, all threshold calculations are executed in Python using closed-form algebra:

### Mathematical Formulas

#### 1. Additional Classes Needed to Reach Target Threshold ($x$)
Let $A$ = classes attended, $T$ = total classes held so far, and $\tau$ = target attendance percentage (e.g. $75.0$ or $85.0$).  
To find the minimum number of future consecutive classes $x$ the student must attend:

$$\frac{A + x}{T + x} \ge \frac{\tau}{100}$$

$$100(A + x) \ge \tau(T + x)$$

$$x(100 - \tau) \ge \tau T - 100A$$

$$x = \left\lceil \frac{\tau T - 100A}{100 - \tau} \right\rceil \quad (\text{for } \tau < 100, \text{ and } x = 0 \text{ if } \frac{A}{T} \ge \frac{\tau}{100})$$

#### 2. Safe Miss / Bunk Margin ($y$)
To find the maximum number of future classes $y$ a student can miss without dropping below threshold $\tau$:

$$\frac{A}{T + y} \ge \frac{\tau}{100} \implies 100A \ge \tau(T + y) \implies \tau y \le 100A - \tau T$$

$$y = \left\lfloor \frac{100A - \tau T}{\tau} \right\rfloor \quad (\text{for } 100A \ge \tau T, \text{ and } y = 0 \text{ if } \frac{A}{T} < \frac{\tau}{100})$$

---

### Worked Verification Examples from Seeded ERP Data

#### Worked Example 1: Classes Needed to Reach 75%
- **Query:** *"How many more classes does Anjali Sharma (IS2023006) need to attend to reach 75% attendance in IS301?"*
- **Database Record:** `Anjali Sharma (IS2023006)` in `IS301`: Attended $A = 20$, Total $T = 33$, Current % = $60.61\%$.
- **Calculation:**
  $$x = \left\lceil \frac{75 \cdot 33 - 100 \cdot 20}{100 - 75} \right\rceil = \left\lceil \frac{2475 - 2000}{25} \right\rceil = \left\lceil \frac{475}{25} \right\rceil = 19$$
- **Verification:**
  $$\text{Projected Total} = 33 + 19 = 52, \quad \text{Projected Attended} = 20 + 19 = 39$$
  $$\text{Projected Attendance} = \frac{39}{52} = 75.00\%$$
- **API Response:**
  ```markdown
  To reach 75% attendance in the course Digital Logic Design (IS301), Anjali Sharma (IS2023006) needs to attend an additional 19 classes.

  | Metric                | Value          |
  |-----------------------|----------------|
  | Current Attended      | 20 classes     |
  | Current Total         | 33 classes     |
  | Current Attendance %  | 60.61%         |
  | Target Threshold %    | 75.0%          |
  | Classes Needed        | 19 classes     |
  | Projected Attended    | 39 classes     |
  | Projected Total       | 52 classes     |
  | Projected Attendance %| 75.0%          |
  | Gap in Percentage Points | 14.39%        |
  ```

#### Worked Example 2: Safe Absence Margin
- **Query:** *"How many classes can Uday Sinha (CS2022081) miss in CS601 and stay above 75% attendance?"*
- **Database Record:** `Uday Sinha (CS2022081)` in `CS601`: Attended $A = 30$, Total $T = 33$, Current % = $90.91\%$.
- **Calculation:**
  $$y = \left\lfloor \frac{100 \cdot 30 - 75 \cdot 33}{75} \right\rfloor = \left\lfloor \frac{3000 - 2475}{75} \right\rfloor = \left\lfloor \frac{525}{75} \right\rfloor = 7$$
- **Verification:**
  $$\text{If 7 missed:} \quad \frac{30}{33 + 7} = \frac{30}{40} = 75.00\% \ge 75\% \quad \text{(Safe)}$$
  $$\text{If 8 missed:} \quad \frac{30}{33 + 8} = \frac{30}{41} = 73.17\% < 75\% \quad \text{(Violates Threshold)}$$
- **API Response:**
  ```markdown
  ### Attendance Calculation for Uday Sinha (CS2022081) in Course CS601 (Machine Learning)

  | USN       | Student Name | Current Attended | Current Total | Current % | Target % | Classes Can Miss Safely | Projected Total | Projected % | Buffer % |
  |-----------|--------------|------------------|---------------|-----------|----------|-------------------------|-----------------|-------------|----------|
  | CS2022081 | Uday Sinha   | 30               | 33            | 90.91     | 75.0     | 7                       | 40              | 75.0        | 15.91    |

  Summary: Uday Sinha can miss up to 7 classes in CS601 and still maintain an attendance percentage above 75%.
  ```

---

## 3. Explainable "At-Risk" Responses

When querying for students at academic or attendance risk, the system no longer outputs binary "Risk: Yes" flags. Instead, every record is enriched with full explainable breakdowns:

- **Query:** *"Show me the at-risk students in CS501"*
- **Result:**
  ```markdown
  ### At-Risk Students in CS501

  | USN       | Student Name | Current % | Attended / Total | Threshold | Shortage Gap | Risk Level | Classes Needed (75%) | Classes Needed (85%) |
  |-----------|--------------|-----------|------------------|-----------|--------------|------------|----------------------|----------------------|
  | CS2022062 | Sarath Menon | 69.7%     | 23 / 33 classes  | 75.0%     | 5.3% points  | Warning    | 7 classes            | 34 classes           |

  Explanation: Current attendance is 69.7% (23/33 classes). Short by 5.3% points below the 75.0% minimum threshold. Needs to attend 7 consecutive classes to reach 75%.
  ```

---

## 4. Tool Transparency

Every response from `/chat` and `/text-query` now contains the `tool_used` metadata field indicating the subsystem that handled the request:

| Scenario / Query Type | `tool_used` Value | `query_type` Value |
|---|---|---|
| Deterministic Attendance Calculation | `"Reasoning (AttendanceTool)"` | `"erp"` |
| Standard Attendance Lookup / Risk List | `"AttendanceTool"` | `"erp"` |
| Grades / GPA Lookup | `"GradesTool"` | `"erp"` |
| Timetable / Schedule Lookup | `"TimetableTool"` | `"erp"` |
| RAG Document Search | `"DocumentTool"` | `"document"` |
| General Conversation | `"Direct LLM"` | `"general"` |

---

## 5. End-to-End Verification Test Results

All test scenarios were executed and validated against the live backend server:

| Test ID | Test Description | Input Payload / History | HTTP Status | Response `tool_used` | Result Summary |
|---|---|---|---|---|---|
| **P5-T1A** | Multi-Turn Context: Turn 1 | `{"message": "Show me attendance for CS601"}` | `200 OK` | `AttendanceTool` | Correctly returned CS601 course statistics. |
| **P5-T1B** | Multi-Turn Context: Turn 2 (Referential Follow-Up) | `{"message": "Which one has the lowest attendance in that course?", "history": [Turn 1]}` | `200 OK` | `AttendanceTool` | Successfully resolved "in that course" to CS601 from prior turn history. |
| **P5-T2** | Reasoning Calculation: Classes Needed | `{"message": "How many more classes does Anjali Sharma (IS2023006) need to attend to reach 75% attendance in IS301?"}` | `200 OK` | `Reasoning (AttendanceTool)` | Calculated $x=19$ classes needed ($20/33 \to 39/52 = 75.00\%$). |
| **P5-T3** | Reasoning Calculation: Safe Absence Margin | `{"message": "How many classes can Uday Sinha (CS2022081) miss in CS601 and stay above 75% attendance?"}` | `200 OK` | `Reasoning (AttendanceTool)` | Calculated $y=7$ classes allowed to miss ($30/33 \to 30/40 = 75.00\%$). |
| **P5-T4** | Explainable At-Risk Response | `{"message": "Show me the at-risk students in CS501"}` | `200 OK` | `AttendanceTool` | Returned Sarath Menon ($69.7\%$, $5.3\%$ shortage, $7$ classes needed for $75\%$). |
| **P5-T5A** | Unregressed Tool: Timetable | `{"message": "What classes are scheduled on Monday?"}` | `200 OK` | `TimetableTool` | Returned Monday timetable matrix. |
| **P5-T5B** | Unregressed Tool: RAG Citations | `{"message": "According to the uploaded academic policies document, what is the condonation fee?"}` | `200 OK` | `DocumentTool` | Returned INR 1000 fee with page 1 citation source. |

---

## 6. Git Commit History for Phase 5

The implementation was committed across atomic, dedicated commits adhering strictly to the phase discipline:

1. `a61561e` — `feat: send bounded conversation history from frontend to support follow-up queries`
2. `04b7fca` — `feat: resolve conversational references using prior turn context in agent classification`
3. `2dee42f` — `feat: add attendance-threshold reasoning calculations computed in Python, not LLM`
4. `12ad20d` — `feat: add explainable at-risk responses showing percentage, threshold, and gap`
5. `dd1e729` — `feat: return tool_used field in chat response for tool transparency`
6. `6bcf843` — `perf: optimize query classification with fast heuristic pre-check and robust dotenv loading`
7. `docs: add phase 5 reasoning and context report with worked examples` (This report)
