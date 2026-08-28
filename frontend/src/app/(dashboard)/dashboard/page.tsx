"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import {
  Mic,
  BarChart3,
  FileText,
  BookOpen,
  ArrowRight,
  TrendingUp,
  Users,
  Clock,
} from "lucide-react";
import { Card, StatCard } from "@/components/Cards";
import { fetchDashboardStats, DashboardStats } from "@/lib/api";

const stagger = {
  animate: { transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
};

const quickActions = [
  {
    icon: Mic,
    title: "Voice Assistant",
    description: "Ask questions using natural voice",
    href: "/voice",
    accent: true,
  },
  {
    icon: BarChart3,
    title: "Analytics",
    description: "View usage statistics and trends",
    href: "/analytics",
    accent: false,
  },
  {
    icon: FileText,
    title: "Documents",
    description: "Upload and manage documents",
    href: "/documents",
    accent: false,
  },
  {
    icon: BookOpen,
    title: "ERP Queries",
    description: "Browse recent queries and responses",
    href: "/voice",
    accent: false,
  },
];

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch live stats from backend on mount and poll
  useEffect(() => {
    let mounted = true;
    const fetchStats = () => {
      fetchDashboardStats()
        .then((data) => {
          if (mounted) setStats(data);
        })
        .finally(() => {
          if (mounted) setLoading(false);
        });
    };
    
    fetchStats();
    const intervalId = setInterval(fetchStats, 10000);
    
    return () => {
      mounted = false;
      clearInterval(intervalId);
    };
  }, []);

  if (loading) {
    return (
      <div className="p-6 lg:p-8 max-w-6xl flex items-center justify-center min-h-[50vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="p-6 lg:p-8 max-w-6xl">
        <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
          <h2 className="text-lg font-semibold mb-2">Unable to load dashboard</h2>
          <p className="text-sm text-muted-foreground">Please ensure the backend is running and try again.</p>
        </div>
      </div>
    );
  }

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
          Welcome back
        </motion.p>
        <motion.h1
          variants={fadeUp}
          transition={{ duration: 0.4 }}
          className="text-3xl sm:text-4xl font-bold tracking-tight font-[family-name:var(--font-space)]"
        >
          Dashboard
        </motion.h1>
      </motion.div>

      {/* Stat Cards — now driven by backend data */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<BookOpen className="h-5 w-5" />}
          label="Total Queries"
          value={stats.totalQueries}
          trend={stats.totalQueriesTrend}
          trendUp={true}
          delay={0}
        />
        <StatCard
          icon={<Clock className="h-5 w-5" />}
          label="Avg Response"
          value={stats.avgResponse}
          trend={stats.avgResponseTrend}
          trendUp={true}
          delay={0.08}
        />
        <StatCard
          icon={<Users className="h-5 w-5" />}
          label="Total Students"
          value={stats.activeSessions}
          trend={stats.activeSessionsTrend}
          trendUp={true}
          delay={0.16}
        />
        <StatCard
          icon={<TrendingUp className="h-5 w-5" />}
          label="Total Faculty"
          value={stats.totalFaculty}
          trend={stats.successRateTrend}
          trendUp={true}
          delay={0.24}
        />
      </div>

      {/* Quick Actions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="mb-8"
      >
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {quickActions.map((action, i) => {
            const Icon = action.icon;
            return (
              <Link key={i} href={action.href}>
                <Card delay={0.3 + i * 0.08} className="h-full cursor-pointer">
                  <div className="flex items-start justify-between mb-4">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-110 ${
                        action.accent
                          ? "bg-foreground text-background"
                          : "bg-accent text-foreground"
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-hover:translate-x-1" />
                  </div>
                  <h3 className="font-semibold mb-1">{action.title}</h3>
                  <p className="text-xs text-muted-foreground">
                    {action.description}
                  </p>
                </Card>
              </Link>
            );
          })}
        </div>
      </motion.div>

      {/* Recent Activity — now driven by backend data */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
      >
        <h2 className="text-lg font-semibold mb-4">Recent Activity</h2>
        <Card hover={false}>
          <div className="divide-y divide-border">
            {stats.recentQueries.map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + i * 0.05 }}
                className="flex items-center justify-between py-3.5 first:pt-0 last:pb-0"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                    <BookOpen className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate max-w-[200px] sm:max-w-[300px] lg:max-w-[400px]">{item.query}</p>
                    <p className="text-xs text-muted-foreground">{item.time}</p>
                  </div>
                </div>
                <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 capitalize">
                  {item.status}
                </span>
              </motion.div>
            ))}
          </div>
        </Card>
      </motion.div>
    </div>
  );
}
