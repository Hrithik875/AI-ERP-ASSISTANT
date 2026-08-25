"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Activity, CheckCircle2, AlertTriangle, XCircle, ChevronDown, ChevronUp, Cpu, Database, Disc, Mic, Volume2 } from "lucide-react";
import { fetchSystemStatus, SystemStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function StatusPanel() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadStatus = async () => {
    try {
      const data = await fetchSystemStatus();
      if (data) {
        setStatus(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 20000); // 20s polling
    return () => clearInterval(interval);
  }, []);

  if (!status && loading) return null;

  const isOk = status?.overall === "ok";
  const isDegraded = status?.overall === "degraded";

  return (
    <div className="relative z-30 font-sans">
      {/* Mini Toggle Pill */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all shadow-sm backdrop-blur-md",
          isOk
            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
            : isDegraded
            ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/20"
            : "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30 hover:bg-red-500/20"
        )}
      >
        <span className="relative flex h-2 w-2">
          <span
            className={cn(
              "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
              isOk ? "bg-emerald-400" : isDegraded ? "bg-amber-400" : "bg-red-400"
            )}
          />
          <span
            className={cn(
              "relative inline-flex rounded-full h-2 w-2",
              isOk ? "bg-emerald-500" : isDegraded ? "bg-amber-500" : "bg-red-500"
            )}
          />
        </span>
        <span className="uppercase tracking-wider font-semibold text-[10px]">
          {status?.mode || "SYSTEM"}
        </span>
        <span className="text-[11px] opacity-90 font-medium">
          {isOk ? "All Systems Normal" : isDegraded ? "Degraded" : "Offline"}
        </span>
        {isOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {/* Expanded Details Modal / Popover */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            transition={{ duration: 0.2 }}
            className="absolute right-0 mt-2 w-72 p-3.5 rounded-2xl bg-card/95 border border-border/80 shadow-2xl backdrop-blur-xl space-y-3"
          >
            <div className="flex items-center justify-between border-b border-border/50 pb-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                <Activity className="h-3.5 w-3.5 text-primary" />
                <span>Observability & Health</span>
              </div>
              <span className="text-[10px] text-muted-foreground font-mono">
                {status?.timestamp ? new Date(status.timestamp).toLocaleTimeString() : ""}
              </span>
            </div>

            <div className="space-y-2 text-xs">
              {/* MySQL */}
              <div className="flex items-center justify-between p-2 rounded-xl bg-accent/40 border border-border/40">
                <div className="flex items-center gap-2">
                  <Database className="h-3.5 w-3.5 text-blue-500" />
                  <span className="font-medium text-foreground">MySQL / Aurora</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {status?.services.mysql?.status === "ok" ? (
                    <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
                      {status.services.mysql.latency_ms}ms
                    </span>
                  ) : (
                    <span className="text-[11px] text-red-500">Error</span>
                  )}
                  {status?.services.mysql?.status === "ok" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-red-500" />
                  )}
                </div>
              </div>

              {/* Qdrant */}
              <div className="flex items-center justify-between p-2 rounded-xl bg-accent/40 border border-border/40">
                <div className="flex items-center gap-2">
                  <Disc className="h-3.5 w-3.5 text-purple-500" />
                  <span className="font-medium text-foreground">Qdrant Vector DB</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {status?.services.qdrant?.status === "ok" ? (
                    <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
                      {status.services.qdrant.latency_ms}ms
                    </span>
                  ) : (
                    <span className="text-[11px] text-red-500">Error</span>
                  )}
                  {status?.services.qdrant?.status === "ok" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-red-500" />
                  )}
                </div>
              </div>

              {/* LLM */}
              <div className="flex items-center justify-between p-2 rounded-xl bg-accent/40 border border-border/40">
                <div className="flex items-center gap-2">
                  <Cpu className="h-3.5 w-3.5 text-amber-500" />
                  <div className="flex flex-col">
                    <span className="font-medium text-foreground">AI / LLM</span>
                    <span className="text-[9px] text-muted-foreground truncate max-w-[110px]">
                      {status?.services.llm?.model || status?.services.llm?.provider}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {status?.services.llm?.status === "ok" ? (
                    <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
                      {status.services.llm.latency_ms}ms
                    </span>
                  ) : (
                    <span className="text-[11px] text-red-500">Error</span>
                  )}
                  {status?.services.llm?.status === "ok" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-red-500" />
                  )}
                </div>
              </div>

              {/* STT & TTS */}
              <div className="grid grid-cols-2 gap-2">
                <div className="flex items-center justify-between p-2 rounded-xl bg-accent/40 border border-border/40">
                  <div className="flex items-center gap-1.5">
                    <Mic className="h-3.5 w-3.5 text-pink-500" />
                    <span className="font-medium text-foreground">STT</span>
                  </div>
                  {status?.services.stt?.status === "ok" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-red-500" />
                  )}
                </div>
                <div className="flex items-center justify-between p-2 rounded-xl bg-accent/40 border border-border/40">
                  <div className="flex items-center gap-1.5">
                    <Volume2 className="h-3.5 w-3.5 text-cyan-500" />
                    <span className="font-medium text-foreground">TTS</span>
                  </div>
                  {status?.services.tts?.status === "ok" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-red-500" />
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
