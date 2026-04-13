// API Integration Layer — Placeholder endpoints with mock data

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
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

// ── Mock Data ──────────────────────────────────────────────────────────────

export const mockMessages: ChatMessage[] = [
  {
    id: "1",
    role: "user",
    content: "What is my attendance for this semester?",
    timestamp: new Date(Date.now() - 120000),
  },
  {
    id: "2",
    role: "assistant",
    content:
      "Your attendance for this semester is 87.5%. You have attended 42 out of 48 classes. You need to maintain at least 75% attendance to be eligible for exams.",
    timestamp: new Date(Date.now() - 110000),
  },
  {
    id: "3",
    role: "user",
    content: "Show me my grades for last semester",
    timestamp: new Date(Date.now() - 60000),
  },
  {
    id: "4",
    role: "assistant",
    content:
      "Here are your grades for last semester:\n\n• Data Structures: A (9.0)\n• Operating Systems: A+ (10.0)\n• Database Management: B+ (8.0)\n• Computer Networks: A (9.0)\n• Mathematics III: B (7.0)\n\nSemester GPA: 8.6",
    timestamp: new Date(Date.now() - 50000),
  },
];

export const mockAnalytics: AnalyticsData = {
  queriesPerDay: [
    { date: "Mon", count: 24 },
    { date: "Tue", count: 18 },
    { date: "Wed", count: 32 },
    { date: "Thu", count: 28 },
    { date: "Fri", count: 42 },
    { date: "Sat", count: 15 },
    { date: "Sun", count: 8 },
  ],
  usageStats: [
    { name: "Attendance", value: 340 },
    { name: "Grades", value: 280 },
    { name: "Schedule", value: 190 },
    { name: "Documents", value: 120 },
    { name: "General", value: 90 },
  ],
  responseTimes: [
    { date: "Mon", avgMs: 320 },
    { date: "Tue", avgMs: 280 },
    { date: "Wed", avgMs: 350 },
    { date: "Thu", avgMs: 290 },
    { date: "Fri", avgMs: 310 },
    { date: "Sat", avgMs: 250 },
    { date: "Sun", avgMs: 220 },
  ],
};

export const mockDocuments: Document[] = [
  {
    id: "1",
    name: "Semester_Report_2025.pdf",
    size: "2.4 MB",
    type: "PDF",
    uploadedAt: "2025-12-15",
    status: "processed",
  },
  {
    id: "2",
    name: "Attendance_Sheet_Nov.xlsx",
    size: "1.1 MB",
    type: "XLSX",
    uploadedAt: "2025-11-30",
    status: "processed",
  },
  {
    id: "3",
    name: "Grade_Card_Final.pdf",
    size: "890 KB",
    type: "PDF",
    uploadedAt: "2025-12-20",
    status: "processed",
  },
  {
    id: "4",
    name: "Timetable_Spring_2026.pdf",
    size: "456 KB",
    type: "PDF",
    uploadedAt: "2026-01-05",
    status: "processing",
  },
  {
    id: "5",
    name: "Lab_Manual_DBMS.docx",
    size: "3.2 MB",
    type: "DOCX",
    uploadedAt: "2025-10-12",
    status: "processed",
  },
];

// ── API Functions ──────────────────────────────────────────────────────────

export async function sendVoiceInput(audioBlob: Blob): Promise<{ text: string; response: string }> {
  // Placeholder: POST /voice-input
  // const formData = new FormData();
  // formData.append("audio", audioBlob);
  // const res = await fetch(`${API_BASE}/voice-input`, { method: "POST", body: formData });
  // return res.json();

  await new Promise((resolve) => setTimeout(resolve, 2000));
  return {
    text: "What is my attendance percentage?",
    response:
      "Your current attendance is 87.5%. You have attended 42 out of 48 classes this semester.",
  };
}

export async function sendChatMessage(message: string): Promise<ChatMessage> {
  // Placeholder: POST /chat
  // const res = await fetch(`${API_BASE}/chat`, {
  //   method: "POST",
  //   headers: { "Content-Type": "application/json" },
  //   body: JSON.stringify({ message }),
  // });
  // return res.json();

  await new Promise((resolve) => setTimeout(resolve, 1500));
  return {
    id: Date.now().toString(),
    role: "assistant",
    content: `Based on your ERP data, here's what I found regarding "${message}": The information has been retrieved successfully from the system. Please let me know if you need any additional details.`,
    timestamp: new Date(),
  };
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  // Placeholder: GET /analytics
  await new Promise((resolve) => setTimeout(resolve, 800));
  return mockAnalytics;
}

export async function uploadDocument(file: File): Promise<Document> {
  // Placeholder: POST /documents
  await new Promise((resolve) => setTimeout(resolve, 1500));
  return {
    id: Date.now().toString(),
    name: file.name,
    size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
    type: file.name.split(".").pop()?.toUpperCase() || "FILE",
    uploadedAt: new Date().toISOString().split("T")[0],
    status: "processing",
  };
}
