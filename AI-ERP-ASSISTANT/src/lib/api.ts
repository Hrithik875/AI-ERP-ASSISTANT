// ══════════════════════════════════════════════════════════════════════════════
// API Integration Layer — Connected to AWS Backend (Production)
// ══════════════════════════════════════════════════════════════════════════════
// ALL data is dynamically fetched from the backend. No mock data.
// No localStorage hacks. No hardcoded fallbacks.
// ══════════════════════════════════════════════════════════════════════════════

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  query_type?: string;
  audio_url?: string;
}

export interface AnalyticsData {
  queriesPerDay: { date: string; count: number }[];
  usageStats: { name: string; value: number }[];
  responseTimes: { date: string; avgMs: number }[];
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
  timeoutMs: number = 60000
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
 * Send a text chat message to the backend AI agent.
 */
export async function sendChatMessage(message: string): Promise<ChatMessage> {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
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
