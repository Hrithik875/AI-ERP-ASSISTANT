"use client";

import { useRef } from "react";
import Link from "next/link";
import { motion, useScroll, useTransform, useSpring } from "framer-motion";
import { Mic, ArrowRight, Sparkles } from "lucide-react";
import Navbar from "@/components/Navbar";
import BentoGrid from "@/components/BentoGrid";

import { SplineScene } from "@/components/ui/splite";
import { Card } from "@/components/ui/card";
import { Spotlight } from "@/components/ui/spotlight";

/* ── Animation Utilities ─────────────────────────────────────────────────── */

const SplitText = ({ text, className }: { text: string; className?: string }) => {
  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-10%" }}
      transition={{ staggerChildren: 0.15 }}
      className={className}
    >
      {text.split("\n").map((line, i) => (
        <div key={i} className="overflow-hidden pb-2 -mb-2">
          <motion.div
            variants={{
              hidden: { opacity: 0, y: "100%" },
              visible: { 
                opacity: 1, 
                y: 0,
                transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } 
              }
            }}
          >
            {line}
          </motion.div>
        </div>
      ))}
    </motion.div>
  );
};

export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Smooth scroll progress
  const { scrollYProgress } = useScroll({ target: containerRef });
  const smoothProgress = useSpring(scrollYProgress, { damping: 20, stiffness: 100, mass: 0.5 });
  
  // Hero Paralax
  const heroOpacity = useTransform(smoothProgress, [0, 0.15], [1, 0]);
  const heroScale = useTransform(smoothProgress, [0, 0.15], [1, 0.95]);

  return (
    <div ref={containerRef} className="min-h-screen bg-background text-foreground overflow-hidden">
      <Navbar />

      {/* ── Scene 1: Hero ─────────────────────────────────────────── */}
      <section className="relative min-h-[100svh] flex flex-col items-center justify-center p-4 sm:p-6 overflow-hidden">
        <motion.div style={{ opacity: heroOpacity, scale: heroScale }} className="w-full max-w-7xl mx-auto min-h-[800px] md:h-[700px] relative z-10 pt-16">
          <Card className="w-full h-full bg-black/[0.96] border-neutral-800 relative overflow-hidden rounded-[2.5rem]">
            <Spotlight
              className="-top-40 left-0 md:left-60 md:-top-20"
              fill="white"
            />
            
            <div className="flex flex-col md:flex-row h-full">
              {/* Left content */}
              <div className="flex-1 p-8 sm:p-14 relative z-10 flex flex-col justify-center">
                <motion.div
                  initial={{ opacity: 0, scale: 0.9, filter: "blur(4px)" }}
                  animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-neutral-700 bg-neutral-900/50 backdrop-blur-md mb-8 text-sm font-medium text-neutral-300 w-fit"
                >
                  <Sparkles className="w-4 h-4 text-white" />
                  <span>Meet your new AI colleague</span>
                </motion.div>

                <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold bg-clip-text text-transparent bg-gradient-to-b from-neutral-50 to-neutral-500 tracking-tight font-[family-name:var(--font-space)] leading-[1.05]">
                  Talk to your <br/> ERP properly.
                </h1>
                
                <p className="mt-8 text-lg sm:text-xl text-neutral-400 max-w-lg font-light leading-relaxed">
                  Stop digging through endless menus to find attendance, grades, or schedules. Just ask exactly what you need, and get the answer instantly.
                </p>

                <div className="mt-10 flex flex-col sm:flex-row items-center gap-4">
                  <Link href="/voice" className="w-full sm:w-auto">
                    <button className="w-full group relative flex h-12 items-center justify-center gap-2 rounded-full bg-white text-black px-8 text-sm font-semibold transition-all hover:scale-105 active:scale-95 shadow-[0_0_20px_rgba(255,255,255,0.1)]">
                      <span>Try the demo</span>
                      <Mic className="w-4 h-4 transition-transform group-hover:scale-110" />
                    </button>
                  </Link>
                  <Link href="/dashboard" className="w-full sm:w-auto">
                    <button className="w-full group flex h-12 items-center justify-center gap-2 rounded-full border border-neutral-700 bg-transparent px-8 text-sm font-semibold text-white transition-colors hover:bg-neutral-800">
                      <span>Open Dashboard</span>
                      <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                    </button>
                  </Link>
                </div>
              </div>

              {/* Right content */}
              <div className="flex-1 relative min-h-[400px] md:min-h-full">
                <div className="absolute inset-0 bg-gradient-to-l from-transparent to-black/[0.96] z-10 pointer-events-none md:block hidden" />
                <div className="absolute inset-y-0 left-0 w-full bg-gradient-to-t from-black/[0.96] via-transparent to-transparent z-10 pointer-events-none md:hidden block bottom-0" />
                <SplineScene 
                  scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
                  className="w-full h-full max-md:scale-[2] max-md:origin-[50%_25%]"
                />
              </div>
            </div>
          </Card>
        </motion.div>
      </section>

      {/* ── Scene 2: Interactive Bento Grid ────────────────────────── */}
      <BentoGrid />

      {/* ── Scene 3: Clean CTA ─────────────────────────────────────── */}
      <section className="relative py-32 px-4 sm:px-6">
        <div className="max-w-4xl mx-auto rounded-[3rem] border border-border bg-foreground text-background p-12 sm:p-20 text-center overflow-hidden flex flex-col items-center relative">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-2xl h-[300px] bg-background/10 blur-[100px] rounded-full pointer-events-none" />
          
          <div className="relative z-10 w-full flex flex-col items-center">
            <h2 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight font-[family-name:var(--font-space)] mb-6">
              Experience the future of work.
            </h2>
            <p className="text-lg md:text-xl opacity-80 mb-10 max-w-2xl mx-auto font-light leading-relaxed">
              No setup required. Jump into the dashboard and see how voice AI can transform your daily administration.
            </p>
            <Link href="/dashboard">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="inline-flex h-14 items-center justify-center rounded-full bg-background text-foreground px-10 text-lg font-medium transition-transform"
              >
                Launch Dashboard
              </motion.button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer className="border-t border-border py-12 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground transition-transform group-hover:rotate-180 duration-500">
              <Sparkles className="h-4 w-4 text-background" />
            </div>
            <span className="text-base font-semibold font-[family-name:var(--font-space)]">AI ERP Assistant</span>
          </div>
          
          <div className="flex items-center gap-6 text-sm text-muted-foreground">
             <Link href="/dashboard" className="hover:text-foreground transition-colors">Dashboard</Link>
             <Link href="/voice" className="hover:text-foreground transition-colors">Voice</Link>
             <Link href="/analytics" className="hover:text-foreground transition-colors">Analytics</Link>
          </div>

          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} AI ERP. Designed with precision.
          </p>
        </div>
      </footer>
    </div>
  );
}
