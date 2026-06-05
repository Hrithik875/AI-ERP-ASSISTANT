"use client";

import { useState, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import VoiceRecorder from "@/components/VoiceRecorder";
import ChatUI, { ChatUIHandle } from "@/components/ChatUI";
import { sendVoiceInput } from "@/lib/api";

export default function VoicePage() {
  const [status, setStatus] = useState<"idle" | "listening" | "processing" | "responding">("idle");
  const chatRef = useRef<ChatUIHandle>(null);

  const handleRecordingComplete = useCallback(async (blob: Blob) => {
    setStatus("processing");
    try {
      const result = await sendVoiceInput(blob);
      setStatus("responding");

      // Add the transcript to chat
      chatRef.current?.addTranscript(result.text, result.response);

      setTimeout(() => setStatus("idle"), 1500);
    } catch {
      setStatus("idle");
    }
  }, []);

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100dvh-9rem)] lg:h-[calc(100vh-4rem)] overflow-hidden relative">
      {/* Mobile-only Header */}
      <div className="lg:hidden shrink-0 border-b border-border p-4 bg-card/30 flex items-center justify-between z-10">
        <div>
          <h1 className="text-xl font-bold font-[family-name:var(--font-space)]">Voice Assistant</h1>
          <p className="text-xs text-muted-foreground">Speak naturally to query your ERP</p>
        </div>
      </div>

      {/* Desktop Voice Recorder Panel (Hidden on mobile) */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
        className="hidden lg:flex flex-col items-center justify-center p-12 lg:w-[420px] border-r border-border bg-card/30 shrink-0"
      >
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight mb-2 font-[family-name:var(--font-space)]">
            Voice Assistant
          </h1>
          <p className="text-sm text-muted-foreground">
            Speak naturally to query your ERP system
          </p>
        </div>

        <VoiceRecorder
          onRecordingComplete={handleRecordingComplete}
          onStatusChange={(s) => setStatus(s)}
          status={status}
        />

        {/* Quick Tips */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-10 w-full max-w-xs"
        >
          <p className="text-xs font-medium text-muted-foreground mb-3 uppercase tracking-wider">
            Try asking
          </p>
          <div className="space-y-2">
            {[
              "What's the attendance for CS601?",
              "List all students in section A",
              "Show me grades for Machine Learning",
            ].map((tip, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + i * 0.1 }}
                className="rounded-lg bg-accent/50 border border-border px-3 py-2 text-xs text-muted-foreground"
              >
                &ldquo;{tip}&rdquo;
              </motion.div>
            ))}
          </div>
        </motion.div>
      </motion.div>

      {/* Chat Panel */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="flex-1 flex flex-col h-full min-h-0 relative z-0"
      >
        <ChatUI 
          ref={chatRef} 
          initialMessages={[]} 
          bottomSlot={
            <div className="lg:hidden flex flex-col items-center justify-center pt-2 border-b border-border/10 pb-0">
               <VoiceRecorder
                 onRecordingComplete={handleRecordingComplete}
                 onStatusChange={(s) => setStatus(s)}
                 status={status}
               />
            </div>
          }
        />
      </motion.div>
    </div>
  );
}
