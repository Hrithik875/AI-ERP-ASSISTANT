"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Database,
  Table2,
  Play,
  Download,
  Upload,
  Plus,
  Trash2,
  Edit3,
  Search,
  ChevronLeft,
  ChevronRight,
  X,
  Check,
  Loader2,
  Terminal,
  FileDown,
  FileUp,
  RefreshCw,
  ArrowUpDown,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { Card } from "@/components/Cards";
import { cn } from "@/lib/utils";
import {
  fetchTables,
  fetchTableData,
  insertTableRow,
  updateTableRow,
  deleteTableRow,
  executeSql,
  getExportUrl,
  importTableData,
  TableInfo,
  TableData,
  SqlResult,
} from "@/lib/api";

const stagger = {
  animate: { transition: { staggerChildren: 0.05 } },
};

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
};

type TabId = "tables" | "query";

// ══════════════════════════════════════════════════════════════════════════════
// Main Database Page
// ══════════════════════════════════════════════════════════════════════════════

export default function DatabasePage() {
  const [activeTab, setActiveTab] = useState<TabId>("tables");
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableData, setTableData] = useState<TableData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<"ASC" | "DESC">("ASC");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // SQL Console state
  const [sqlQuery, setSqlQuery] = useState("SELECT * FROM faculty LIMIT 10;");
  const [sqlResult, setSqlResult] = useState<SqlResult | null>(null);
  const [sqlRunning, setSqlRunning] = useState(false);
  const [sqlError, setSqlError] = useState<string | null>(null);

  // Edit/Add modal state
  const [editingRow, setEditingRow] = useState<Record<string, unknown> | null>(null);
  const [addingRow, setAddingRow] = useState(false);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  // Import state
  const [importing, setImporting] = useState(false);

  const showToast = useCallback((message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  // Load tables
  useEffect(() => {
    fetchTables()
      .then(setTables)
      .catch((e) => showToast(`Failed to load tables: ${e.message}`, "error"))
      .finally(() => setLoading(false));
  }, [showToast]);

  // Load table data when table/page/search/sort changes
  const loadTableData = useCallback(async () => {
    if (!selectedTable) return;
    setTableLoading(true);
    try {
      const data = await fetchTableData(selectedTable, {
        page,
        pageSize: 25,
        sortBy: sortBy || undefined,
        sortOrder,
        search: search || undefined,
      });
      setTableData(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      showToast(`Failed to load data: ${msg}`, "error");
    } finally {
      setTableLoading(false);
    }
  }, [selectedTable, page, search, sortBy, sortOrder, showToast]);

  useEffect(() => {
    loadTableData();
  }, [loadTableData]);

  // Select table
  const handleSelectTable = (name: string) => {
    setSelectedTable(name);
    setPage(1);
    setSearch("");
    setSortBy(null);
    setSortOrder("ASC");
  };

  // Sort column
  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortOrder((prev) => (prev === "ASC" ? "DESC" : "ASC"));
    } else {
      setSortBy(col);
      setSortOrder("ASC");
    }
    setPage(1);
  };

  // Delete row
  const handleDelete = async (rowId: number) => {
    if (!selectedTable) return;
    try {
      await deleteTableRow(selectedTable, rowId);
      showToast("Row deleted successfully", "success");
      loadTableData();
      // Refresh table list for row counts
      fetchTables().then(setTables);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      showToast(`Delete failed: ${msg}`, "error");
    }
  };

  // Start editing
  const handleEdit = (row: Record<string, unknown>) => {
    setEditingRow(row);
    const data: Record<string, string> = {};
    for (const [k, v] of Object.entries(row)) {
      if (k === "id") continue;
      data[k] = v === null ? "" : String(v);
    }
    setFormData(data);
  };

  // Start adding
  const handleAdd = () => {
    setAddingRow(true);
    setEditingRow(null);
    const data: Record<string, string> = {};
    if (tableData) {
      for (const col of tableData.columns) {
        if (col === "id") continue;
        data[col] = "";
      }
    }
    setFormData(data);
  };

  // Save row (add or edit)
  const handleSave = async () => {
    if (!selectedTable) return;
    setSaving(true);
    try {
      // Filter out empty strings for optional fields
      const cleaned: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(formData)) {
        if (v !== "") cleaned[k] = v;
      }

      if (editingRow) {
        await updateTableRow(selectedTable, editingRow.id as number, cleaned);
        showToast("Row updated successfully", "success");
      } else {
        await insertTableRow(selectedTable, cleaned);
        showToast("Row inserted successfully", "success");
      }
      setEditingRow(null);
      setAddingRow(false);
      setFormData({});
      loadTableData();
      fetchTables().then(setTables);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      showToast(`Save failed: ${msg}`, "error");
    } finally {
      setSaving(false);
    }
  };

  // Run SQL
  const handleRunSql = async () => {
    if (!sqlQuery.trim()) return;
    setSqlRunning(true);
    setSqlError(null);
    setSqlResult(null);
    try {
      const result = await executeSql(sqlQuery);
      setSqlResult(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setSqlError(msg);
    } finally {
      setSqlRunning(false);
    }
  };

  // Import file
  const handleImport = async (file: File) => {
    if (!selectedTable) return;
    setImporting(true);
    try {
      const result = await importTableData(selectedTable, file);
      showToast(result.message, "success");
      loadTableData();
      fetchTables().then(setTables);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      showToast(`Import failed: ${msg}`, "error");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className={cn(
              "fixed top-20 right-6 z-50 flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium shadow-lg border",
              toast.type === "success"
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                : "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
            )}
          >
            {toast.type === "success" ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <motion.div
        initial="initial"
        animate="animate"
        variants={stagger}
        className="mb-8"
      >
        <motion.p
          variants={fadeUp}
          transition={{ duration: 0.4 }}
          className="text-sm text-muted-foreground mb-1"
        >
          Management
        </motion.p>
        <motion.h1
          variants={fadeUp}
          transition={{ duration: 0.4 }}
          className="text-3xl sm:text-4xl font-bold tracking-tight font-[family-name:var(--font-space)]"
        >
          Database Console
        </motion.h1>
      </motion.div>

      {/* Tabs */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex gap-1 mb-6 p-1 bg-accent/50 rounded-xl w-fit border border-border"
      >
        {[
          { id: "tables" as TabId, label: "Table Editor", icon: Table2 },
          { id: "query" as TabId, label: "SQL Console", icon: Terminal },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200",
              activeTab === tab.id
                ? "bg-card text-foreground shadow-sm border border-border"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </motion.div>

      {activeTab === "tables" ? (
        <div className="flex gap-6">
          {/* Table List Sidebar */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 }}
            className="w-64 shrink-0 hidden lg:block"
          >
            <Card hover={false} delay={0.15}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Tables
                </h3>
                <button
                  onClick={() => {
                    setLoading(true);
                    fetchTables()
                      .then(setTables)
                      .finally(() => setLoading(false));
                  }}
                  className="p-1.5 rounded-md hover:bg-accent transition-colors"
                >
                  <RefreshCw className={cn("h-3.5 w-3.5 text-muted-foreground", loading && "animate-spin")} />
                </button>
              </div>
              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <div className="space-y-1">
                  {tables.map((t) => (
                    <button
                      key={t.name}
                      onClick={() => handleSelectTable(t.name)}
                      className={cn(
                        "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all duration-200",
                        selectedTable === t.name
                          ? "bg-foreground text-background font-medium"
                          : "text-foreground hover:bg-accent"
                      )}
                    >
                      <span className="flex items-center gap-2 truncate">
                        <Database className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{t.name}</span>
                      </span>
                      <span
                        className={cn(
                          "text-[10px] font-mono px-1.5 py-0.5 rounded-md",
                          selectedTable === t.name
                            ? "bg-background/20 text-background"
                            : "bg-accent text-muted-foreground"
                        )}
                      >
                        {t.rowCount}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </Card>
          </motion.div>

          {/* Table Data Area */}
          <div className="flex-1 min-w-0">
            {/* Mobile table selector */}
            <div className="lg:hidden mb-4">
              <select
                value={selectedTable || ""}
                onChange={(e) => handleSelectTable(e.target.value)}
                className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-foreground/20"
              >
                <option value="">Select a table...</option>
                {tables.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.name} ({t.rowCount} rows)
                  </option>
                ))}
              </select>
            </div>

            {!selectedTable ? (
              <Card hover={false} delay={0.2}>
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent mb-4">
                    <Database className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-semibold mb-1">Select a Table</h3>
                  <p className="text-sm text-muted-foreground">
                    Choose a table from the sidebar to view and manage its data.
                  </p>
                </div>
              </Card>
            ) : (
              <motion.div
                key={selectedTable}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                {/* Toolbar */}
                <div className="flex flex-wrap items-center gap-3 mb-4">
                  <div className="relative flex-1 min-w-[200px]">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Search records..."
                      value={search}
                      onChange={(e) => {
                        setSearch(e.target.value);
                        setPage(1);
                      }}
                      className="w-full rounded-xl border border-border bg-card pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-foreground/20 transition-all"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleAdd}
                      className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-foreground text-background text-sm font-medium hover:opacity-90 transition-opacity"
                    >
                      <Plus className="h-4 w-4" />
                      Add Row
                    </motion.button>
                    <a
                      href={getExportUrl(selectedTable, "csv")}
                      className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-border bg-card text-sm font-medium hover:bg-accent transition-colors"
                    >
                      <FileDown className="h-4 w-4" />
                      <span className="hidden sm:inline">CSV</span>
                    </a>
                    <a
                      href={getExportUrl(selectedTable, "json")}
                      className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-border bg-card text-sm font-medium hover:bg-accent transition-colors"
                    >
                      <FileDown className="h-4 w-4" />
                      <span className="hidden sm:inline">JSON</span>
                    </a>
                    <label className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-border bg-card text-sm font-medium hover:bg-accent transition-colors cursor-pointer">
                      <FileUp className="h-4 w-4" />
                      <span className="hidden sm:inline">
                        {importing ? "Importing..." : "Import"}
                      </span>
                      <input
                        type="file"
                        className="hidden"
                        accept=".csv,.json"
                        onChange={(e) => {
                          if (e.target.files?.[0]) handleImport(e.target.files[0]);
                          e.target.value = "";
                        }}
                      />
                    </label>
                  </div>
                </div>

                {/* Data Table */}
                <Card hover={false} delay={0}>
                  <div className="overflow-x-auto -mx-6 -my-6">
                    {tableLoading ? (
                      <div className="flex items-center justify-center py-16">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                      </div>
                    ) : !tableData || tableData.rows.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-16 text-center">
                        <p className="text-sm text-muted-foreground">No records found</p>
                      </div>
                    ) : (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border bg-accent/30">
                            {tableData.columns.map((col) => (
                              <th
                                key={col}
                                onClick={() => handleSort(col)}
                                className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-foreground transition-colors whitespace-nowrap select-none"
                              >
                                <span className="flex items-center gap-1">
                                  {col}
                                  {sortBy === col && (
                                    <ArrowUpDown className="h-3 w-3" />
                                  )}
                                </span>
                              </th>
                            ))}
                            <th className="w-20 px-4 py-3"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {tableData.rows.map((row, i) => (
                            <tr
                              key={i}
                              className="border-b border-border/50 hover:bg-accent/20 transition-colors group"
                            >
                              {tableData.columns.map((col) => (
                                <td
                                  key={col}
                                  className="px-4 py-3 whitespace-nowrap max-w-[200px] truncate"
                                  title={String(row[col] ?? "")}
                                >
                                  {row[col] === null ? (
                                    <span className="text-muted-foreground/40 italic">null</span>
                                  ) : (
                                    String(row[col])
                                  )}
                                </td>
                              ))}
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <button
                                    onClick={() => handleEdit(row)}
                                    className="p-1.5 rounded-md hover:bg-accent transition-colors"
                                    title="Edit"
                                  >
                                    <Edit3 className="h-3.5 w-3.5 text-muted-foreground" />
                                  </button>
                                  <button
                                    onClick={() => handleDelete(row.id as number)}
                                    className="p-1.5 rounded-md hover:bg-red-500/10 transition-colors"
                                    title="Delete"
                                  >
                                    <Trash2 className="h-3.5 w-3.5 text-red-500" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>

                  {/* Pagination */}
                  {tableData && tableData.totalPages > 1 && (
                    <div className="flex items-center justify-between pt-4 mt-4 border-t border-border">
                      <p className="text-xs text-muted-foreground">
                        Showing {(page - 1) * 25 + 1}–{Math.min(page * 25, tableData.total)} of{" "}
                        {tableData.total} records
                      </p>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setPage((p) => Math.max(1, p - 1))}
                          disabled={page === 1}
                          className="p-2 rounded-lg hover:bg-accent transition-colors disabled:opacity-30"
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </button>
                        <span className="px-3 py-1.5 text-xs font-medium bg-accent rounded-lg">
                          {page} / {tableData.totalPages}
                        </span>
                        <button
                          onClick={() => setPage((p) => Math.min(tableData.totalPages, p + 1))}
                          disabled={page === tableData.totalPages}
                          className="p-2 rounded-lg hover:bg-accent transition-colors disabled:opacity-30"
                        >
                          <ChevronRight className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </Card>
              </motion.div>
            )}
          </div>
        </div>
      ) : (
        /* SQL Console Tab */
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="space-y-4"
        >
          <Card hover={false} delay={0.15}>
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent">
                <Terminal className="h-4 w-4" />
              </div>
              <div>
                <h3 className="font-semibold">SQL Query Console</h3>
                <p className="text-xs text-muted-foreground">
                  Execute raw SQL queries against the database
                </p>
              </div>
            </div>
            <div className="relative">
              <textarea
                value={sqlQuery}
                onChange={(e) => setSqlQuery(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                    handleRunSql();
                  }
                }}
                rows={6}
                placeholder="Enter SQL query..."
                className="w-full rounded-xl border border-border bg-accent/30 px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-foreground/20 resize-y transition-all"
                spellCheck={false}
              />
              <div className="flex items-center justify-between mt-3">
                <p className="text-[10px] text-muted-foreground">
                  Press Ctrl+Enter to run
                </p>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleRunSql}
                  disabled={sqlRunning || !sqlQuery.trim()}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-foreground text-background text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
                >
                  {sqlRunning ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Run Query
                </motion.button>
              </div>
            </div>
          </Card>

          {/* SQL Error */}
          {sqlError && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl border border-red-500/20 bg-red-500/5 p-4"
            >
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-red-600 dark:text-red-400">Query Error</p>
                  <p className="text-xs text-red-600/70 dark:text-red-400/70 mt-1 font-mono">
                    {sqlError}
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* SQL Results */}
          {sqlResult && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <Card hover={false} delay={0}>
                {sqlResult.type === "select" ? (
                  <>
                    <div className="flex items-center justify-between mb-4">
                      <p className="text-sm font-medium">
                        Results{" "}
                        <span className="text-muted-foreground">
                          ({sqlResult.rowCount} row{sqlResult.rowCount !== 1 ? "s" : ""})
                        </span>
                      </p>
                    </div>
                    <div className="overflow-x-auto -mx-6 -mb-6">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border bg-accent/30">
                            {sqlResult.columns?.map((col) => (
                              <th
                                key={col}
                                className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap"
                              >
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {sqlResult.rows?.map((row, i) => (
                            <tr
                              key={i}
                              className="border-b border-border/50 hover:bg-accent/20 transition-colors"
                            >
                              {sqlResult.columns?.map((col) => (
                                <td
                                  key={col}
                                  className="px-4 py-3 whitespace-nowrap max-w-[250px] truncate"
                                  title={String(row[col] ?? "")}
                                >
                                  {row[col] === null ? (
                                    <span className="text-muted-foreground/40 italic">null</span>
                                  ) : (
                                    String(row[col])
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    <div>
                      <p className="text-sm font-medium">Query executed successfully</p>
                      <p className="text-xs text-muted-foreground">{sqlResult.message}</p>
                    </div>
                  </div>
                )}
              </Card>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Edit/Add Modal */}
      <AnimatePresence>
        {(editingRow || addingRow) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            onClick={() => {
              setEditingRow(null);
              setAddingRow(false);
            }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto"
            >
              <div className="sticky top-0 bg-card border-b border-border px-6 py-4 flex items-center justify-between rounded-t-2xl">
                <h3 className="text-lg font-semibold">
                  {editingRow ? "Edit Row" : "Add New Row"}
                </h3>
                <button
                  onClick={() => {
                    setEditingRow(null);
                    setAddingRow(false);
                  }}
                  className="p-2 rounded-lg hover:bg-accent transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="p-6 space-y-4">
                {Object.entries(formData).map(([key, value]) => (
                  <div key={key}>
                    <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                      {key}
                    </label>
                    <input
                      type="text"
                      value={value}
                      onChange={(e) =>
                        setFormData((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                      className="w-full rounded-xl border border-border bg-accent/30 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-foreground/20 transition-all"
                      placeholder={`Enter ${key}...`}
                    />
                  </div>
                ))}
              </div>
              <div className="sticky bottom-0 bg-card border-t border-border px-6 py-4 flex justify-end gap-3 rounded-b-2xl">
                <button
                  onClick={() => {
                    setEditingRow(null);
                    setAddingRow(false);
                  }}
                  className="px-4 py-2.5 rounded-xl border border-border text-sm font-medium hover:bg-accent transition-colors"
                >
                  Cancel
                </button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-foreground text-background text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4" />
                  )}
                  {editingRow ? "Update" : "Insert"}
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
