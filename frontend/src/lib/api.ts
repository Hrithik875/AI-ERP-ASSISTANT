// ══════════════════════════════════════════════════════════════════════════════
// API Integration Layer — Connected to AWS Backend (Production)
// ══════════════════════════════════════════════════════════════════════════════
// ALL data is dynamically fetched from the backend. No mock data.
// No localStorage hacks. No hardcoded fallbacks.
// ══════════════════════════════════════════════════════════════════════════════

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ADMIN_API_KEY = process.env.NEXT_PUBLIC_ADMIN_API_KEY || "";

/** Headers required for every /db/* admin-console request. */
const adminHeaders = (): HeadersInit => ({ "X-Admin-Key": ADMIN_API_KEY });

// ── Types ──────────────────────────────────────────────────────────────────

export interface SystemServiceStatus {
  status: "ok" | "error" | "degraded";
  latency_ms?: number;
  provider?: string;
  model?: string;
  fast_model?: string;
  fast_model_downloaded?: boolean;
  error?: string;
}

export interface SystemStatus {
  mode: string;
  services: {
    mysql?: SystemServiceStatus;
    qdrant?: SystemServiceStatus;
    llm?: SystemServiceStatus;
    stt?: SystemServiceStatus;
    tts?: SystemServiceStatus;
  };
  overall: "ok" | "degraded" | "error";
  timestamp: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  query_type?: string;
  source?: string;
  tool_used?: string;
  sources?: { filename: string; page?: number; score: number }[];
  audio_url?: string;
}

export interface AnalyticsData {
  queriesPerDay: { date: string; count: number }[];
  usageStats: { name: string; value: number }[];
  responseTimes: { date: string; avgMs: number }[];
  deptStats: { name: string; value: number }[];
}

export interface Document {
  id: string;
  name: string;
  size: string;
  type: string;
  uploadedAt: string;
  status: "processed" | "processing" | "failed";
}

export interface DashboardStats {
  totalQueries: string;
  totalQueriesTrend: string;
  avgResponse: string;
  avgResponseTrend: string;
  activeSessions: string;
  activeSessionsTrend: string;
  successRate: string;
  successRateTrend: string;
  totalFaculty: string;
  totalCourses: string;
  recentQueries: {
    query: string;
    time: string;
    status: string;
  }[];
}

interface VoiceInputResponse {
  job_name: string;
  file_id: string;
  s3_key: string;
  message: string;
  status: string;
}

interface TranscriptResponse {
  status: "IN_PROGRESS" | "COMPLETED" | "FAILED";
  transcript?: string;
  reason?: string;
  message?: string;
}

// ══════════════════════════════════════════════════════════════════════════════
// Helper: Poll Transcription Status
// ══════════════════════════════════════════════════════════════════════════════

async function pollTranscript(
  jobName: string,
  intervalMs: number = 2000,
  timeoutMs: number = 180000
): Promise<string> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    try {
      const res = await fetch(`${API_BASE}/get-transcript/${jobName}`);
      if (!res.ok) {
        throw new Error(`Transcript fetch failed: ${res.status} ${res.statusText}`);
      }

      const data: TranscriptResponse = await res.json();

      if (data.status === "COMPLETED" && data.transcript) {
        return data.transcript;
      }

      if (data.status === "FAILED") {
        throw new Error(`Transcription failed: ${data.reason || "Unknown error"}`);
      }

      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    } catch (error) {
      console.error("Poll error:", error);
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
  }

  throw new Error("Transcription timed out after 60 seconds");
}

// ══════════════════════════════════════════════════════════════════════════════
// API Functions — All dynamically fetched, no mock data
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Send voice audio to the backend for transcription + AI processing.
 */
export async function sendVoiceInput(
  audioBlob: Blob
): Promise<{ text: string; response: string; audio_url?: string }> {
  try {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");

    const uploadRes = await fetch(`${API_BASE}/voice-input`, {
      method: "POST",
      body: formData,
    });

    if (!uploadRes.ok) {
      const error = await uploadRes.json().catch(() => ({}));
      throw new Error(error.detail || `Upload failed: ${uploadRes.status}`);
    }

    const uploadData: VoiceInputResponse = await uploadRes.json();
    console.log("Voice upload successful:", uploadData);

    // Poll for transcript
    const transcriptText = await pollTranscript(uploadData.job_name);
    console.log("Transcript received:", transcriptText);

    // Send through AI chat pipeline
    const aiResponse = await sendChatMessage(transcriptText);

    return {
      text: transcriptText,
      response: aiResponse.content,
      audio_url: aiResponse.audio_url,
    };
  } catch (error) {
    console.error("Voice input error:", error);
    return {
      text: "(Failed to transcribe audio)",
      response:
        "Sorry, I was unable to process your voice input. Please check your connection and try again.",
    };
  }
}

/**
 * Send a text chat message with bounded conversation history to the backend AI agent.
 */
export async function sendChatMessage(
  message: string,
  history: ChatTurn[] = []
): Promise<ChatMessage> {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || `Chat request failed: ${res.status}`);
    }

    const data = await res.json();

    return {
      id: data.id || Date.now().toString(),
      role: "assistant",
      content: data.content,
      timestamp: new Date(),
      query_type: data.query_type,
      source: data.source,
      tool_used: data.tool_used,
      sources: data.sources,
      audio_url: data.audio_url,
    };
  } catch (error) {
    console.error("Chat error:", error);
    return {
      id: Date.now().toString(),
      role: "assistant",
      content:
        "Sorry, I'm unable to connect to the backend. Please ensure the server is running and try again.",
      timestamp: new Date(),
    };
  }
}

/**
 * Stream a chat response via SSE (/chat/stream).
 *
 * Calls `onToken` for each token string as it arrives.
 * Calls `onDone` with the completed ChatMessage when the [DONE] event fires.
 * Calls `onError` if a network or server error occurs.
 *
 * Returns an AbortController so the caller can cancel the stream.
 */
export function streamChatMessage(
  message: string,
  history: ChatTurn[],
  onToken: (token: string) => void,
  onDone: (msg: ChatMessage) => void,
  onError: (err: string) => void
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        onError(err.detail || `Stream request failed: ${res.status}`);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        onError("ReadableStream not supported");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last (possibly incomplete) line in the buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6); // strip "data: "

          if (payload.startsWith("[DONE]")) {
            try {
              const meta = JSON.parse(payload.slice(7)); // strip "[DONE] "
              onDone({
                id: meta.id || Date.now().toString(),
                role: "assistant",
                content: "", // content was built progressively via onToken
                timestamp: new Date(),
                query_type: meta.query_type,
                source: meta.source,
                tool_used: meta.tool_used,
                sources: meta.sources,
              });
            } catch {
              onDone({
                id: Date.now().toString(),
                role: "assistant",
                content: "",
                timestamp: new Date(),
              });
            }
            return;
          }

          if (payload.startsWith("[ERROR]")) {
            const errJson = payload.slice(8);
            try {
              const e = JSON.parse(errJson);
              onError(e.error || "Unknown streaming error");
            } catch {
              onError(errJson);
            }
            return;
          }

          // Regular token — unescape \n back to newlines
          const token = payload.replace(/\\n/g, "\n");
          onToken(token);
        }
      }
    } catch (err: any) {
      if (err?.name === "AbortError") return; // cancelled
      console.error("Stream error:", err);
      onError(err?.message || "Streaming failed");
    }
  })();

  return controller;
}

/**
 * Fetch the deep system-status health check.
 */
export async function fetchSystemStatus(): Promise<SystemStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/system-status`, { cache: "no-store" });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("system-status unavailable:", err);
    return null;
  }
}

/**
 * Fetch analytics data from the backend database.
 */
export async function fetchAnalytics(): Promise<AnalyticsData> {
  try {
    const res = await fetch(`${API_BASE}/analytics`);
    if (!res.ok) {
      throw new Error(`Analytics fetch failed: ${res.status}`);
    }
    const data = await res.json();
    return data;
  } catch (error) {
    console.error("Analytics fetch error:", error);
    // Return empty data structure (not fake data)
    return {
      queriesPerDay: [],
      usageStats: [],
      responseTimes: [],
    };
  }
}

/**
 * Fetch dashboard statistics from the backend database.
 */
export async function fetchDashboardStats(): Promise<DashboardStats | null> {
  try {
    const res = await fetch(`${API_BASE}/dashboard/stats`);
    if (!res.ok) {
      throw new Error(`Dashboard stats fetch failed: ${res.status}`);
    }
    return await res.json();
  } catch (error) {
    console.error("Dashboard stats fetch error:", error);
    return null;
  }
}

/**
 * Fetch list of documents from the backend database.
 */
export async function fetchDocuments(): Promise<Document[]> {
  try {
    const res = await fetch(`${API_BASE}/documents`);
    if (!res.ok) {
      throw new Error(`Documents fetch failed: ${res.status}`);
    }
    return await res.json();
  } catch (error) {
    console.error("Documents fetch error:", error);
    return [];
  }
}

/**
 * Upload a document to the backend (stored in S3 + processed by RAG).
 */
export async function uploadDocument(file: File): Promise<Document> {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/documents`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || `Upload failed: ${res.status}`);
    }

    const data = await res.json();

    return {
      id: data.id,
      name: data.name || file.name,
      size: data.size || `${(file.size / 1024 / 1024).toFixed(1)} MB`,
      type: data.type || file.name.split(".").pop()?.toUpperCase() || "FILE",
      uploadedAt: data.uploadedAt || new Date().toISOString().split("T")[0],
      status: data.status || "processing",
    };
  } catch (error) {
    console.error("Document upload error:", error);
    throw error; // Don't silently return mock data
  }
}

/**
 * Check backend health status.
 */
export async function checkHealth(): Promise<{
  status: string;
  message: string;
  region: string;
  bucket: string;
  llm_provider: string;
  llm_model: string;
} | null> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error("Health check error:", error);
    return null;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// Database Console API
// ══════════════════════════════════════════════════════════════════════════════

export interface TableInfo {
  name: string;
  rowCount: number;
  columns: {
    COLUMN_NAME: string;
    DATA_TYPE: string;
    IS_NULLABLE: string;
    COLUMN_KEY: string;
    COLUMN_DEFAULT: string | null;
    EXTRA: string;
  }[];
}

export interface TableData {
  table: string;
  columns: string[];
  columnDetails: {
    COLUMN_NAME: string;
    DATA_TYPE: string;
    IS_NULLABLE: string;
    COLUMN_KEY: string;
  }[];
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface SqlResult {
  type: "select" | "write";
  rows?: Record<string, unknown>[];
  rowCount?: number;
  columns?: string[];
  affectedRows?: number;
  message?: string;
}

/**
 * Fetch all tables with their column info and row counts.
 */
export async function fetchTables(): Promise<TableInfo[]> {
  const res = await fetch(`${API_BASE}/db/tables`, { headers: adminHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch tables: ${res.status}`);
  return res.json();
}

/**
 * Fetch paginated data from a specific table.
 */
export async function fetchTableData(
  tableName: string,
  options: {
    page?: number;
    pageSize?: number;
    sortBy?: string;
    sortOrder?: "ASC" | "DESC";
    search?: string;
  } = {}
): Promise<TableData> {
  const params = new URLSearchParams();
  if (options.page) params.set("page", String(options.page));
  if (options.pageSize) params.set("page_size", String(options.pageSize));
  if (options.sortBy) params.set("sort_by", options.sortBy);
  if (options.sortOrder) params.set("sort_order", options.sortOrder);
  if (options.search) params.set("search", options.search);

  const res = await fetch(`${API_BASE}/db/tables/${tableName}?${params}`, { headers: adminHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch table data: ${res.status}`);
  return res.json();
}

/**
 * Insert a row into a table.
 */
export async function insertTableRow(
  tableName: string,
  data: Record<string, unknown>
): Promise<{ success: boolean; id: number; message: string }> {
  const res = await fetch(`${API_BASE}/db/tables/${tableName}`, {
    method: "POST",
    headers: { ...adminHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Insert failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Update a row in a table.
 */
export async function updateTableRow(
  tableName: string,
  rowId: number,
  data: Record<string, unknown>
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/db/tables/${tableName}/${rowId}`, {
    method: "PUT",
    headers: { ...adminHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Update failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Delete a row from a table.
 */
export async function deleteTableRow(
  tableName: string,
  rowId: number
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/db/tables/${tableName}/${rowId}`, {
    method: "DELETE",
    headers: adminHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Delete failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Execute raw SQL query.
 */
export async function executeSql(sql: string): Promise<SqlResult> {
  const res = await fetch(`${API_BASE}/db/query`, {
    method: "POST",
    headers: { ...adminHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ sql }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `SQL execution failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Export table data as CSV or JSON.
 */
export function getExportUrl(tableName: string, format: "csv" | "json"): string {
  return `${API_BASE}/db/export/${tableName}?format=${format}`;
}

/**
 * Import data into a table from a file.
 */
export async function importTableData(
  tableName: string,
  file: File
): Promise<{ success: boolean; imported: number; message: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/db/import/${tableName}`, {
    method: "POST",
    headers: adminHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Import failed: ${res.status}`);
  }
  return res.json();
}
