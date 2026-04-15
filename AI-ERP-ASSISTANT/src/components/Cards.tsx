"use client";

import { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface CardProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  hover?: boolean;
}

export function Card({ children, className, delay = 0, hover = true }: CardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={
        hover
          ? {
              y: -4,
              transition: { duration: 0.25 },
            }
          : undefined
      }
      className={cn(
        "group relative rounded-2xl border border-border bg-card p-6 transition-shadow duration-300",
        hover && "hover:shadow-lg hover:shadow-black/[0.03] dark:hover:shadow-white/[0.02] hover:border-border/80",
        className
      )}
    >
      {/* Subtle border glow on hover */}
      <div className="absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100 pointer-events-none bg-gradient-to-br from-white/[0.02] to-transparent" />
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}

interface StatCardProps {
  icon: ReactNode;
  label: string;
  value: string;
  trend?: string;
  trendUp?: boolean;
  delay?: number;
}

export function StatCard({ icon, label, value, trend, trendUp, delay = 0 }: StatCardProps) {
  return (
    <Card delay={delay}>
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-foreground">
          {icon}
        </div>
        {trend && (
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
              trendUp
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : "bg-red-500/10 text-red-600 dark:text-red-400"
            )}
          >
            {trend}
          </span>
        )}
      </div>
      <div className="mt-4">
        <p className="text-2xl font-bold tracking-tight font-[family-name:var(--font-space)]">{value}</p>
        <p className="mt-1 text-sm text-muted-foreground">{label}</p>
      </div>
    </Card>
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-2xl border border-border bg-card p-6", className)}>
      <div className="skeleton h-10 w-10 rounded-xl" />
      <div className="mt-4 space-y-2">
        <div className="skeleton h-7 w-24 rounded-md" />
        <div className="skeleton h-4 w-32 rounded-md" />
      </div>
    </div>
  );
}
