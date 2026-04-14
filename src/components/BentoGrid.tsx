"use client";

import { useState, useRef, ReactNode } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { Mic, ArrowRight, Activity, FileText, Sparkles, Database, AudioLines, Volume2, Shield } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

// --- Subcomponents ---

function CursorGlow({ mouseX, mouseY }: { mouseX: any; mouseY: any }) {
  return (
    <motion.div
      className="pointer-events-none absolute -inset-px rounded-[2rem] opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-30 overflow-hidden"
    >
      <motion.div
        className="absolute inset-0 bg-gradient-to-r from-foreground/0 via-foreground/20 to-foreground/0"
        style={{
          background: useTransform(
            [mouseX, mouseY],
            ([x, y]) => `radial-gradient(600px circle at ${x}px ${y}px, var(--foreground), transparent 40%)`
          ),
          opacity: 0.05,
        }}
      />
    </motion.div>
  );
}

function BentoCard({
  children,
  className,
  delay = 0,
  index,
  hoveredIndex,
  onHover,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  index: number;
  hoveredIndex: number | null;
  onHover: (i: number | null) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    mouseX.set(e.clientX - rect.left);
    mouseY.set(e.clientY - rect.top);
  };

  const isDimmed = hoveredIndex !== null && hoveredIndex !== index;

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => onHover(index)}
      onMouseLeave={() => onHover(null)}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10%" }}
      transition={{ duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "group relative flex flex-col justify-between overflow-hidden rounded-[2rem] bg-card border border-border/40 p-8 cursor-default z-10",
        "transition-all duration-500 ease-out",
        "hover:scale-[1.02] hover:-translate-y-1.5 hover:shadow-2xl hover:border-foreground/30",
        isDimmed && "opacity-50 blur-[1px] scale-[0.98]",
        className
      )}
    >
      {/* Background Depth layer */}
      <div className="absolute inset-0 bg-noise opacity-[0.02]" />
      
      {/* Spotlight */}
      <CursorGlow mouseX={mouseX} mouseY={mouseY} />
      
      {children}
    </motion.div>
  );
}

// --- The Grid ---

export default function BentoGrid() {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  return (
    <section className="relative py-32 px-4 sm:px-6 max-w-[1300px] mx-auto z-10 bg-background text-foreground">
      <div className="mb-20 max-w-2xl text-center mx-auto">
        <motion.h2 
           initial={{ opacity: 0, y: 20 }}
           whileInView={{ opacity: 1, y: 0 }}
           transition={{ duration: 0.8 }}
           className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight font-[family-name:var(--font-space)] mb-6"
        >
          Intelligent by design.
        </motion.h2>
        <motion.p 
           initial={{ opacity: 0, y: 20 }}
           whileInView={{ opacity: 1, y: 0 }}
           transition={{ duration: 0.8, delay: 0.1 }}
           className="text-xl text-muted-foreground leading-relaxed font-light"
        >
          A meticulously crafted experience. Instant intelligence wrapped in an interface that gets out of your way.
        </motion.p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6 lg:auto-rows-[340px]">
        
        {/* 1. Voice Interaction (Top Left) */}
        <BentoCard index={0} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.05} className="lg:col-span-1 lg:row-span-1">
          <div className="relative z-10 flex-1 flex flex-col justify-between h-full">
            <div className="w-12 h-12 rounded-[1rem] border border-border flex items-center justify-center bg-background shadow-sm mb-6 group-hover:scale-110 group-hover:rotate-3 transition-transform duration-500 relative">
              <Mic className="w-5 h-5 group-hover:animate-pulse" />
              {/* Fake waveform popping out on hover */}
              <div className="absolute -bottom-2 flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                {[1, 2, 3, 2, 1].map((h, i) => (
                  <motion.div key={i} animate={{ height: [4, 12, 4] }} transition={{ duration: 1, repeat: Infinity, delay: i * 0.1 }} className="w-0.5 bg-foreground rounded-full" />
                ))}
              </div>
            </div>
            <div>
              <h3 className="text-xl font-semibold tracking-tight mb-2">Voice-First Experience</h3>
              <motion.p className="text-sm text-muted-foreground leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">
                Talk to your ERP naturally using voice commands.
              </motion.p>
            </div>
          </div>
        </BentoCard>

        {/* 2. HERO CARD (Center Massive) */}
        <BentoCard index={1} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.1} className="lg:col-span-2 lg:row-span-2 text-center items-center">
          <div className="relative z-20 flex flex-col items-center flex-1 justify-center">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-background shadow-sm mb-6 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              <Sparkles className="w-3 h-3" /> System Active
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-4 font-[family-name:var(--font-space)] relative">
              Your AI-Powered <br/>ERP Assistant
            </h2>
            <p className="text-muted-foreground text-lg sm:text-xl max-w-sm mx-auto leading-relaxed mb-10 opacity-90 group-hover:opacity-100 transition-opacity">
              Speak. Query. Get instant insights from your ERP.
            </p>
            <Link href="/voice" className="relative z-30 group/btn">
              <button className="flex items-center gap-2 rounded-full bg-foreground text-background px-8 py-4 text-sm font-semibold transition-all hover:scale-105 active:scale-95 overflow-hidden relative shadow-[0_0_20px_rgba(0,0,0,0.1)] dark:shadow-[0_0_20px_rgba(255,255,255,0.1)]">
                <span className="relative z-10">Try Voice Assistant</span>
                <ArrowRight className="w-4 h-4 relative z-10 transition-transform group-hover/btn:translate-x-1" />
                <motion.div className="absolute inset-0 bg-background/20 opacity-0 group-hover/btn:opacity-100 transition-opacity" />
              </button>
            </Link>
          </div>

          {/* Animated AI Orb */}
          <div className="absolute -bottom-48 left-1/2 -translate-x-1/2 w-[400px] h-[400px] pointer-events-none">
            <div className="absolute inset-0 rounded-full border-[1px] border-foreground/10 animate-[spin_40s_linear_infinite]" />
            <div className="absolute inset-8 rounded-full border-[1px] border-foreground/5 animate-[spin_60s_linear_infinite_reverse]" />
            <div className="absolute inset-20 flex items-center justify-center">
               <motion.div 
                 animate={{ scale: [1, 1.05, 1], opacity: [0.3, 0.4, 0.3] }}
                 transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                 className="w-64 h-64 rounded-full bg-foreground/10 blur-3xl"
               />
               <motion.div 
                 animate={{ scale: [0.95, 1.05, 0.95] }}
                 transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                 className="absolute w-40 h-40 rounded-full bg-foreground/20 blur-2xl"
               />
            </div>
          </div>
        </BentoCard>

        {/* 3. AI Query Engine (Top Right) */}
        <BentoCard index={2} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.15} className="lg:col-span-1 lg:row-span-1">
           <div className="relative z-10 flex-1 flex flex-col justify-between h-full">
            <div className="w-12 h-12 rounded-[1rem] border border-border flex items-center justify-center bg-background shadow-sm mb-6 group-hover:scale-110 group-hover:-rotate-3 transition-transform duration-500">
              <Sparkles className="w-5 h-5 group-hover:fill-foreground/20" />
            </div>
            <div>
              <h3 className="text-xl font-semibold tracking-tight mb-2">AI Query Engine</h3>
              <p className="text-sm text-muted-foreground leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">Understand complex queries and retrieve accurate ERP data.</p>
            </div>
          </div>
          {/* Animated Neural Network */}
          <div className="absolute top-0 right-0 w-40 h-40 pointer-events-none opacity-20 group-hover:opacity-40 transition-opacity duration-700">
             <motion.svg viewBox="0 0 100 100" className="w-full h-full stroke-foreground fill-none stroke-[0.5]">
               <motion.path 
                 initial={{ pathLength: 0 }} 
                 animate={{ pathLength: 1 }} 
                 transition={{ duration: 2, repeat: Infinity, repeatType: "reverse" }}
                 d="M20,20 L50,40 L80,20 M50,40 L40,70 L80,80 L50,40" 
               />
               <circle cx="20" cy="20" r="2" className="fill-foreground" />
               <motion.circle cx="50" cy="40" r="3" animate={{ r: [2, 4, 2] }} transition={{ duration: 1.5, repeat: Infinity }} className="fill-foreground shadow-[0_0_10px_var(--foreground)]" />
               <circle cx="80" cy="20" r="2" className="fill-foreground" />
               <circle cx="40" cy="70" r="2" className="fill-foreground" />
               <circle cx="80" cy="80" r="2" className="fill-foreground" />
             </motion.svg>
          </div>
        </BentoCard>

        {/* 4. Analytics (Middle Left) */}
        <BentoCard index={3} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.2} className="lg:col-span-1 lg:row-span-1">
          <div className="relative z-10 flex-1 flex flex-col justify-between h-full">
            <div className="w-12 h-12 rounded-[1rem] border border-border flex items-center justify-center bg-background shadow-sm mb-6 group-hover:scale-110 transition-transform duration-500 relative overflow-hidden">
              <Activity className="w-5 h-5 relative z-10" />
            </div>
            <div>
              <h3 className="text-xl font-semibold tracking-tight mb-2">Real-Time Insights</h3>
              <p className="text-sm text-muted-foreground leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">Get instant analytics on attendance, grades, and performance.</p>
            </div>
          </div>
          {/* Wave Line Chart */}
          <div className="absolute right-0 bottom-24 w-32 h-20 pointer-events-none opacity-20 group-hover:opacity-50 transition-opacity duration-500">
             <svg viewBox="0 0 100 50" className="w-full h-full stroke-foreground fill-none stroke-[2] stroke-linecap-round stroke-linejoin-round">
                <motion.path 
                  initial={{ pathLength: 0 }} 
                  whileInView={{ pathLength: 1 }} 
                  transition={{ duration: 2, ease: "easeInOut", repeat: Infinity, repeatDelay: 1 }}
                  d="M0,40 Q10,10 20,30 T40,20 T60,40 T80,10 T100,50" 
                />
             </svg>
          </div>
        </BentoCard>

        {/* 5. Documents (Middle Right) */}
        <BentoCard index={4} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.25} className="lg:col-span-1 lg:row-span-1">
           <div className="relative z-10 flex-1 flex flex-col justify-between h-full">
            <div className="w-12 h-12 rounded-[1rem] border border-border flex items-center justify-center bg-background shadow-sm mb-6 group-hover:scale-110 transition-transform duration-500">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-xl font-semibold tracking-tight mb-2">Smart Document Retrieval</h3>
              <p className="text-sm text-muted-foreground leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">Search across ERP documents using AI-powered retrieval.</p>
            </div>
          </div>
          {/* File Stack Scanning */}
          <div className="absolute right-4 top-1/2 -translate-y-1/2 w-16 h-16 pointer-events-none opacity-20 group-hover:opacity-80 transition-all duration-500">
             <div className="absolute inset-0 bg-foreground/10 border border-border rounded-lg transform rotate-[10deg] group-hover:rotate-[15deg] transition-transform duration-700" />
             <div className="absolute inset-0 bg-background border border-foreground/30 rounded-lg shadow-lg overflow-hidden flex flex-col gap-1.5 p-2 transform -rotate-2 group-hover:rotate-0 transition-transform duration-700">
                <div className="h-1 w-full bg-foreground/20 rounded-full" />
                <div className="h-1 w-2/3 bg-foreground/20 rounded-full" />
                <div className="h-1 w-full bg-foreground/20 rounded-full" />
                {/* OCR Scanner */}
                <motion.div 
                  animate={{ top: ["0%", "100%", "0%"] }} 
                  transition={{ duration: 2, ease: "linear", repeat: Infinity }}
                  className="absolute left-0 w-full h-[1px] bg-foreground shadow-[0_0_8px_var(--foreground)]" 
                />
             </div>
          </div>
        </BentoCard>

        {/* ROW 3 */}
        
        {/* 6. Database Integration */}
        <BentoCard index={5} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.3} className="lg:col-span-1">
           <div className="w-10 h-10 mb-4 text-foreground/70 group-hover:text-foreground transition-colors group-hover:scale-110 duration-500">
             <Database className="w-full h-full" />
           </div>
           <div>
              <h3 className="text-lg font-semibold tracking-tight mb-1">Seamless ERP Integration</h3>
              <p className="text-sm text-muted-foreground leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">Connected directly with your institutional databases.</p>
           </div>
           {/* Flowing Lines */}
           <div className="absolute top-0 right-10 w-[1px] h-32 bg-gradient-to-b from-foreground/0 via-foreground/20 to-foreground/0">
              <motion.div animate={{ y: [0, 100] }} transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }} className="w-full h-4 bg-foreground blur-[2px]" />
           </div>
           <div className="absolute top-0 right-16 w-[1px] h-32 bg-gradient-to-b from-foreground/0 via-foreground/20 to-foreground/0">
              <motion.div animate={{ y: [100, 0] }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }} className="w-full h-8 bg-foreground blur-[2px]" />
           </div>
        </BentoCard>

        {/* 7. Speech to Text */}
        <BentoCard index={6} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.35} className="lg:col-span-1">
           <div className="w-10 h-10 mb-4 text-foreground/70 group-hover:text-foreground transition-colors group-hover:scale-110 duration-500">
             <AudioLines className="w-full h-full" />
           </div>
           <div>
              <h3 className="text-lg font-semibold tracking-tight mb-1">Speech → Intelligence</h3>
              <p className="text-sm text-muted-foreground leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">Convert voice into actionable queries instantly.</p>
           </div>
           {/* Live Waveform loop */}
           <div className="absolute right-6 bottom-6 flex items-center gap-1 opacity-10 group-hover:opacity-40 transition-opacity">
              {[1, 3, 2, 4, 2, 3, 1].map((h, i) => (
                <motion.div key={i} animate={{ height: [8, 8 + h * 6, 8] }} transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.1 }} className="w-1 bg-foreground rounded-full" />
              ))}
           </div>
        </BentoCard>

        {/* 8. Text to Speech */}
        <BentoCard index={7} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.4} className="lg:col-span-1">
           <div className="w-10 h-10 mb-4 text-foreground/70 group-hover:text-foreground transition-colors group-hover:scale-110 duration-500 relative">
             <Volume2 className="w-full h-full relative z-10 bg-card rounded-full" />
             {/* Sound waves expanding outward */}
             <motion.div animate={{ scale: [1, 2], opacity: [0.5, 0] }} transition={{ duration: 1.5, repeat: Infinity }} className="absolute inset-0 border border-foreground rounded-full pointer-events-none" />
             <motion.div animate={{ scale: [1, 2], opacity: [0.5, 0] }} transition={{ duration: 1.5, repeat: Infinity, delay: 0.5 }} className="absolute inset-0 border border-foreground rounded-full pointer-events-none" />
           </div>
           <div>
              <h3 className="text-lg font-semibold tracking-tight mb-1">AI Voice Responses</h3>
              <p className="text-sm text-muted-foreground leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">Get responses as natural speech using AI.</p>
           </div>
        </BentoCard>

        {/* 9. Security */}
        <BentoCard index={8} hoveredIndex={hoveredIdx} onHover={setHoveredIdx} delay={0.45} className="lg:col-span-1">
           <div className="w-10 h-10 mb-4 text-foreground/70 group-hover:text-foreground transition-colors group-hover:scale-110 duration-500 relative">
             <Shield className="w-full h-full relative z-10" />
             <motion.div animate={{ rotate: 360 }} transition={{ duration: 10, repeat: Infinity, ease: "linear" }} className="absolute -inset-2 border-[1px] border-dashed border-foreground/30 rounded-full group-hover:border-foreground/60 transition-colors" />
           </div>
           <div>
              <h3 className="text-lg font-semibold tracking-tight mb-1">Secure & Scalable</h3>
              <p className="text-sm text-muted-foreground leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">Built on cloud infrastructure with enterprise-grade security.</p>
           </div>
        </BentoCard>

      </div>
    </section>
  );
}
