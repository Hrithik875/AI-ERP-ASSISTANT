"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { BarChart3, TrendingUp, Activity } from "lucide-react";
import { Card, SkeletonCard } from "@/components/Cards";
import { fetchAnalytics, AnalyticsData } from "@/lib/api";

const CHART_COLORS = [
  "#525252",
  "#737373",
  "#a3a3a3",
  "#d4d4d4",
  "#e5e5e5",
];

const stagger = {
  animate: { transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
};

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

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
          Insights
        </motion.p>
        <motion.h1
          variants={fadeUp}
          transition={{ duration: 0.4 }}
          className="text-3xl sm:text-4xl font-bold tracking-tight font-[family-name:var(--font-space)]"
        >
          Analytics
        </motion.h1>
      </motion.div>

      {loading || !data ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SkeletonCard className="h-[350px]" />
          <SkeletonCard className="h-[350px]" />
          <SkeletonCard className="h-[350px]" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Queries Per Day */}
          <Card delay={0} hover={false} className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent">
                <BarChart3 className="h-4 w-4" />
              </div>
              <div>
                <h3 className="font-semibold">Queries Per Day</h3>
                <p className="text-xs text-muted-foreground">
                  Last 7 days activity
                </p>
              </div>
            </div>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.queriesPerDay} barSize={32}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "12px",
                      fontSize: "12px",
                      boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                    }}
                    cursor={{ fill: "var(--accent)", opacity: 0.5 }}
                  />
                  <Bar
                    dataKey="count"
                    fill="var(--foreground)"
                    radius={[6, 6, 0, 0]}
                    opacity={0.85}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Response Times */}
          <Card delay={0.08} hover={false}>
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent">
                <TrendingUp className="h-4 w-4" />
              </div>
              <div>
                <h3 className="font-semibold">Response Times</h3>
                <p className="text-xs text-muted-foreground">Average in ms</p>
              </div>
            </div>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.responseTimes}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "12px",
                      fontSize: "12px",
                      boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="avgMs"
                    stroke="var(--foreground)"
                    strokeWidth={2}
                    dot={{ fill: "var(--foreground)", r: 4, strokeWidth: 0 }}
                    activeDot={{ r: 6, strokeWidth: 0 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Usage by Category */}
          <Card delay={0.16} hover={false}>
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent">
                <Activity className="h-4 w-4" />
              </div>
              <div>
                <h3 className="font-semibold">Usage by Category</h3>
                <p className="text-xs text-muted-foreground">Query distribution</p>
              </div>
            </div>
            <div className="h-[240px] flex items-center">
              <div className="w-1/2 h-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data.usageStats}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                      stroke="none"
                    >
                      {data.usageStats.map((_, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={CHART_COLORS[index % CHART_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "var(--card)",
                        border: "1px solid var(--border)",
                        borderRadius: "12px",
                        fontSize: "12px",
                        boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="w-1/2 space-y-2.5 pl-2">
                {data.usageStats.map((stat, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{
                        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                      }}
                    />
                    <span className="text-xs text-muted-foreground flex-1">
                      {stat.name}
                    </span>
                    <span className="text-xs font-medium tabular-nums">
                      {stat.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
