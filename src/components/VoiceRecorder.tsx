"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Square } from "lucide-react";
import { cn } from "@/lib/utils";

interface VoiceRecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  onStatusChange?: (status: "idle" | "listening" | "processing") => void;
  status?: "idle" | "listening" | "processing" | "responding";
}

export default function VoiceRecorder({
  onRecordingComplete,
  onStatusChange,
  status = "idle",
}: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animationRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const barWidth = 3;
      const gap = 2;
      const bars = Math.floor(canvas.width / (barWidth + gap));
      const startIndex = Math.floor((bufferLength - bars) / 2);

      for (let i = 0; i < bars; i++) {
        const value = dataArray[startIndex + i] || 0;
        const height = (value / 255) * canvas.height * 0.8;
        const x = i * (barWidth + gap);
        const y = (canvas.height - height) / 2;

        const computedStyle = getComputedStyle(document.documentElement);
        const fg = computedStyle.getPropertyValue("--foreground").trim();

        ctx.fillStyle = fg.startsWith("#") ? fg + "60" : "rgba(255,255,255,0.35)";
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, height, 1.5);
        ctx.fill();
      }
    };

    draw();
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        onRecordingComplete(blob);
        stream.getTracks().forEach((track) => track.stop());
        cancelAnimationFrame(animationRef.current);
      };

      mediaRecorder.start();
      setIsRecording(true);
      onStatusChange?.("listening");
      drawWaveform();
    } catch (err) {
      console.error("Microphone access denied:", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      onStatusChange?.("processing");
    }
  };

  useEffect(() => {
    return () => {
      cancelAnimationFrame(animationRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const statusLabels: Record<string, string> = {
    idle: "Tap to speak",
    listening: "Listening…",
    processing: "Processing…",
    responding: "Responding…",
  };

  return (
    <div className="flex flex-col items-center gap-8">
      {/* Waveform Canvas */}
      <div className="relative w-full max-w-md h-16 flex items-center justify-center">
        <AnimatePresence>
          {isRecording && (
            <motion.canvas
              ref={canvasRef}
              width={400}
              height={64}
              initial={{ opacity: 0, scaleY: 0 }}
              animate={{ opacity: 1, scaleY: 1 }}
              exit={{ opacity: 0, scaleY: 0 }}
              transition={{ duration: 0.3 }}
              className="w-full h-full"
            />
          )}
        </AnimatePresence>
        {!isRecording && status === "idle" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-[3px]"
          >
            {Array.from({ length: 32 }).map((_, i) => (
              <div
                key={i}
                className="w-[3px] rounded-full bg-border"
                style={{ height: `${8 + Math.sin(i * 0.5) * 6}px` }}
              />
            ))}
          </motion.div>
        )}
      </div>

      {/* Mic Button */}
      <div className="relative">
        {/* Pulse Rings */}
        <AnimatePresence>
          {isRecording && (
            <>
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 2, opacity: 0 }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="absolute inset-0 rounded-full border-2 border-foreground/10"
              />
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 2, opacity: 0 }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 0.5 }}
                className="absolute inset-0 rounded-full border-2 border-foreground/10"
              />
            </>
          )}
        </AnimatePresence>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={isRecording ? stopRecording : startRecording}
          disabled={status === "processing" || status === "responding"}
          className={cn(
            "relative z-10 flex h-20 w-20 items-center justify-center rounded-full transition-all duration-300",
            isRecording
              ? "bg-foreground text-background shadow-xl"
              : "bg-card border-2 border-border text-foreground hover:border-foreground/20 hover:shadow-lg",
            (status === "processing" || status === "responding") &&
              "opacity-50 cursor-not-allowed"
          )}
        >
          {isRecording ? (
            <Square className="h-6 w-6" fill="currentColor" />
          ) : (
            <Mic className="h-7 w-7" />
          )}
        </motion.button>
      </div>

      {/* Status Label */}
      <AnimatePresence mode="wait">
        <motion.p
          key={status}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.2 }}
          className={cn(
            "text-sm font-medium",
            status === "listening"
              ? "text-foreground"
              : "text-muted-foreground"
          )}
        >
          {statusLabels[status]}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}
