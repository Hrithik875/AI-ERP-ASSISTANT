"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileText,
  MoreVertical,
  Trash2,
  Download,
  CheckCircle2,
  Loader2,
  XCircle,
  File,
} from "lucide-react";
import { Card } from "@/components/Cards";
import { Document, uploadDocument, fetchDocuments } from "@/lib/api";
import { cn } from "@/lib/utils";

const stagger = {
  animate: { transition: { staggerChildren: 0.05 } },
};

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
};

const statusConfig = {
  processed: {
    icon: CheckCircle2,
    label: "Processed",
    className: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10",
  },
  processing: {
    icon: Loader2,
    label: "Processing",
    className: "text-amber-600 dark:text-amber-400 bg-amber-500/10",
  },
  failed: {
    icon: XCircle,
    label: "Failed",
    className: "text-red-600 dark:text-red-400 bg-red-500/10",
  },
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);

  // Fetch documents from backend on mount
  useEffect(() => {
    fetchDocuments()
      .then((docs) => setDocuments(docs))
      .catch((err) => console.error("Failed to fetch documents:", err))
      .finally(() => setLoading(false));
  }, []);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const doc = await uploadDocument(files[0]);
      setDocuments((prev) => [doc, ...prev]);
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  };

  return (
    <div className="p-6 lg:p-8 max-w-6xl">
      {/* Header */}
      <motion.div
        initial="initial"
        animate="animate"
        variants={stagger}
        className="mb-10"
      >
        <motion.p
          variants={fadeUp}
          transition={{ duration: 0.4 }}
          className="text-sm text-muted-foreground mb-1"
        >
          Files
        </motion.p>
        <motion.h1
          variants={fadeUp}
          transition={{ duration: 0.4 }}
          className="text-3xl sm:text-4xl font-bold tracking-tight font-[family-name:var(--font-space)]"
        >
          Documents
        </motion.h1>
      </motion.div>

      {/* Upload Zone */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="mb-8"
      >
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            handleUpload(e.dataTransfer.files);
          }}
          className={cn(
            "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 cursor-pointer transition-all duration-300",
            dragging
              ? "border-foreground/30 bg-accent/50"
              : "border-border hover:border-foreground/15 hover:bg-accent/30"
          )}
        >
          <input
            type="file"
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
            accept=".pdf,.doc,.docx,.xlsx,.csv,.txt"
          />
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent mb-4">
            {uploading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Upload className="h-5 w-5 text-muted-foreground" />
            )}
          </div>
          <p className="text-sm font-medium mb-1">
            {uploading ? "Uploading…" : "Drop files here or click to upload"}
          </p>
          <p className="text-xs text-muted-foreground">
            PDF, DOCX, XLSX, CSV — Max 10MB
          </p>
        </label>
      </motion.div>

      {/* Loading State */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : documents.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-20 text-center"
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent mb-4">
            <File className="h-7 w-7 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold mb-1">No documents yet</h3>
          <p className="text-sm text-muted-foreground">
            Upload files to get started with document intelligence.
          </p>
        </motion.div>
      ) : (
        <motion.div
          initial="initial"
          animate="animate"
          variants={stagger}
        >
          <Card hover={false}>
            {/* Header Row */}
            <div className="hidden sm:grid grid-cols-[1fr_80px_80px_100px_100px_40px] gap-4 px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <span>Name</span>
              <span>Type</span>
              <span>Size</span>
              <span>Uploaded</span>
              <span>Status</span>
              <span></span>
            </div>

            <div className="divide-y divide-border">
              <AnimatePresence>
                {documents.map((doc) => {
                  const statusInfo = statusConfig[doc.status];
                  const StatusIcon = statusInfo.icon;

                  return (
                    <motion.div
                      key={doc.id}
                      variants={fadeUp}
                      exit={{ opacity: 0, height: 0, marginTop: 0, marginBottom: 0 }}
                      transition={{ duration: 0.3 }}
                      className="grid grid-cols-1 sm:grid-cols-[1fr_80px_80px_100px_100px_40px] gap-2 sm:gap-4 items-center px-4 py-3.5 group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent shrink-0">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <span className="text-sm font-medium truncate">
                          {doc.name}
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {doc.type}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {doc.size}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {doc.uploadedAt}
                      </span>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium w-fit",
                          statusInfo.className
                        )}
                      >
                        <StatusIcon
                          className={cn(
                            "h-3 w-3",
                            doc.status === "processing" && "animate-spin"
                          )}
                        />
                        {statusInfo.label}
                      </span>
                      <div className="flex justify-end">
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="flex h-7 w-7 items-center justify-center rounded-md opacity-0 group-hover:opacity-100 transition-opacity hover:bg-accent"
                        >
                          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                        </button>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
