"use client";

import { useRef } from "react";
import Link from "next/link";
import { motion, useScroll, useTransform } from "framer-motion";
import {
  Mic,
  BarChart3,
  FileText,
  Zap,
  ArrowRight,
  Sparkles,
  Shield,
  Clock,
} from "lucide-react";
import Navbar from "@/components/Navbar";

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  animate: { opacity: 1, y: 0 },
};

const stagger = {
  animate: {
    transition: { staggerChildren: 0.1 },
  },
};

const features = [
  {
    icon: Mic,
    title: "Voice Queries",
    description: "Ask questions naturally using voice. Our AI understands context and intent.",
  },
  {
    icon: Zap,
    title: "Instant Insights",
    description: "Get real-time answers from your ERP data — attendance, grades, schedules.",
  },
  {
    icon: BarChart3,
    title: "Smart Analytics",
    description: "Visualize usage patterns and trends with beautiful, interactive charts.",
  },
  {
    icon: Shield,
    title: "Secure Access",
    description: "Enterprise-grade security. Your data stays protected at every layer.",
  },
  {
    icon: FileText,
    title: "Document Intelligence",
    description: "Upload and query documents. AI extracts meaning from your files instantly.",
  },
  {
    icon: Clock,
    title: "24/7 Available",
    description: "Always-on assistant. Get the information you need, whenever you need it.",
  },
];

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });

  const heroOpacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const heroScale = useTransform(scrollYProgress, [0, 0.5], [1, 0.95]);
  const heroY = useTransform(scrollYProgress, [0, 0.5], [0, 60]);

  return (
    <div className="min-h-screen">
      <Navbar />

      {/* ── Hero Section ─────────────────────────────────────────── */}
      <section ref={heroRef} className="relative min-h-screen flex items-center justify-center overflow-hidden">
        {/* Background Gradient */}
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-gradient-to-b from-background via-background to-accent/30" />
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-gradient-radial from-foreground/[0.03] to-transparent blur-3xl" />
        </div>

        {/* Floating Grid Lines */}
        <div className="absolute inset-0 overflow-hidden opacity-[0.03]">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "linear-gradient(var(--foreground) 1px, transparent 1px), linear-gradient(90deg, var(--foreground) 1px, transparent 1px)",
              backgroundSize: "60px 60px",
            }}
          />
        </div>

        <motion.div
          style={{ opacity: heroOpacity, scale: heroScale, y: heroY }}
          className="relative z-10 max-w-5xl mx-auto px-6 text-center pt-24"
        >
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-1.5 text-xs font-medium text-muted-foreground mb-8"
          >
            <Sparkles className="h-3.5 w-3.5" />
            AI-Powered Enterprise Intelligence
          </motion.div>

          {/* Heading */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-bold tracking-tight leading-[0.95] font-[family-name:var(--font-space)]"
          >
            Your AI-Powered
            <br />
            <span className="text-muted-foreground">ERP Assistant</span>
          </motion.h1>

          {/* Subheading */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mt-6 text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed"
          >
            Ask anything. Get instant insights from your ERP using voice.
            <br className="hidden sm:block" />
            Attendance, grades, schedules — all at your fingertips.
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link href="/dashboard">
              <motion.button
                whileHover={{ scale: 1.03, y: -1 }}
                whileTap={{ scale: 0.97 }}
                className="group flex items-center gap-2 rounded-xl bg-foreground text-background px-8 py-3.5 text-sm font-semibold transition-shadow hover:shadow-xl hover:shadow-foreground/10"
              >
                Get Started
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </motion.button>
            </Link>
            <Link href="/voice">
              <motion.button
                whileHover={{ scale: 1.03, y: -1 }}
                whileTap={{ scale: 0.97 }}
                className="flex items-center gap-2 rounded-xl border border-border bg-card px-8 py-3.5 text-sm font-semibold transition-all hover:bg-accent hover:border-foreground/10"
              >
                <Mic className="h-4 w-4" />
                Try Voice Demo
              </motion.button>
            </Link>
          </motion.div>

          {/* Animated Mic Visual */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.8 }}
            className="mt-20 relative flex items-center justify-center"
          >
            <div className="relative">
              {/* Outer rings */}
              {[1, 2, 3].map((ring) => (
                <motion.div
                  key={ring}
                  animate={{
                    scale: [1, 1.5 + ring * 0.3, 1],
                    opacity: [0.15, 0, 0.15],
                  }}
                  transition={{
                    duration: 3,
                    repeat: Infinity,
                    delay: ring * 0.4,
                    ease: "easeInOut",
                  }}
                  className="absolute inset-0 rounded-full border border-foreground/10"
                  style={{
                    margin: `-${ring * 20}px`,
                  }}
                />
              ))}
              <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-card border border-border shadow-lg">
                <Mic className="h-8 w-8 text-foreground" />
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Scroll Indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="w-5 h-8 rounded-full border-2 border-border flex items-start justify-center p-1"
          >
            <motion.div className="w-1 h-2 rounded-full bg-muted-foreground" />
          </motion.div>
        </motion.div>
      </section>

      {/* ── Features Section ─────────────────────────────────────── */}
      <section className="relative py-32 px-6">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial="initial"
            whileInView="animate"
            viewport={{ once: true, margin: "-100px" }}
            variants={stagger}
            className="text-center mb-20"
          >
            <motion.p
              variants={fadeUp}
              transition={{ duration: 0.5 }}
              className="text-sm font-medium text-muted-foreground tracking-wider uppercase mb-4"
            >
              Capabilities
            </motion.p>
            <motion.h2
              variants={fadeUp}
              transition={{ duration: 0.5 }}
              className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight font-[family-name:var(--font-space)]"
            >
              Everything you need,
              <br />
              <span className="text-muted-foreground">nothing you don&apos;t.</span>
            </motion.h2>
          </motion.div>

          <motion.div
            initial="initial"
            whileInView="animate"
            viewport={{ once: true, margin: "-50px" }}
            variants={stagger}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {features.map((feature, i) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={i}
                  variants={fadeUp}
                  transition={{ duration: 0.5 }}
                  whileHover={{ y: -4 }}
                  className="group rounded-2xl border border-border bg-card p-8 transition-all duration-300 hover:shadow-lg hover:shadow-black/[0.03] dark:hover:shadow-white/[0.02] hover:border-foreground/10"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent mb-5 transition-transform duration-300 group-hover:scale-105">
                    <Icon className="h-5 w-5 text-foreground" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {feature.description}
                  </p>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </section>

      {/* ── CTA Section ──────────────────────────────────────────── */}
      <section className="py-32 px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="max-w-4xl mx-auto text-center"
        >
          <div className="rounded-3xl border border-border bg-card p-12 sm:p-16 relative overflow-hidden">
            {/* Subtle glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[500px] h-[200px] bg-gradient-radial from-foreground/[0.03] to-transparent blur-3xl" />

            <div className="relative z-10">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-4 font-[family-name:var(--font-space)]">
                Ready to get started?
              </h2>
              <p className="text-muted-foreground mb-8 max-w-lg mx-auto">
                Transform how you interact with your ERP system. Start using AI-powered voice queries today.
              </p>
              <Link href="/dashboard">
                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className="group inline-flex items-center gap-2 rounded-xl bg-foreground text-background px-8 py-3.5 text-sm font-semibold transition-shadow hover:shadow-xl hover:shadow-foreground/10"
                >
                  Launch Dashboard
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </motion.button>
              </Link>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────── */}
      <footer className="border-t border-border py-8 px-6">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-foreground">
              <Sparkles className="h-3 w-3 text-background" />
            </div>
            <span className="text-sm font-medium">AI ERP</span>
          </div>
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} AI ERP Assistant. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
