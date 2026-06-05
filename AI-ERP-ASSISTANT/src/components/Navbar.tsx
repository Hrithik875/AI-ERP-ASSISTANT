"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { motion, AnimatePresence, useScroll, useMotionValueEvent } from "framer-motion";
import {
  Sun,
  Moon,
  LayoutDashboard,
  Mic,
  BarChart3,
  Settings,
  Sparkles,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navLinks = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/database", label: "Database", icon: LayoutDashboard },
  { href: "/voice", label: "Assistant", icon: Mic },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

export default function Navbar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  const { scrollY } = useScroll();
  const [navState, setNavState] = useState<"top" | "pill" | "hidden">("top");

  useMotionValueEvent(scrollY, "change", (latest) => {
    const previous = scrollY.getPrevious() || 0;
    if (latest <= 60) {
      setNavState("top");
    } else if (latest > previous && latest > 150) {
      setNavState("hidden"); // scrolling down
      setMobileMenuOpen(false); // Close menu on scroll down
    } else {
      setNavState("pill"); // scrolling up
    }
  });

  useEffect(() => setMounted(true), []);

  const isTop = navState === "top";
  const isHidden = navState === "hidden";

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className="fixed top-0 left-0 right-0 z-50 flex flex-col items-center pointer-events-none pt-4 sm:pt-6 px-4"
    >
      <motion.nav
        variants={{
          top: {
            width: "100%",
            maxWidth: "1200px",
            height: "56px",
            borderRadius: "16px",
            y: 0,
            backgroundColor: "rgba(255, 255, 255, 0)",
            border: "1px solid rgba(255, 255, 255, 0)",
          },
          pill: {
            width: "100%",
            maxWidth: "560px",
            height: "56px",
            borderRadius: "999px",
            y: 10,
            backgroundColor: "var(--glass-bg)",
            border: "1px solid var(--border)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.06)",
          },
          hidden: {
            width: "100%",
            maxWidth: "560px",
            height: "56px",
            borderRadius: "999px",
            y: -50,
            opacity: 0,
            backgroundColor: "var(--glass-bg)",
            border: "1px solid var(--border)",
            boxShadow: "0 8px 32px rgba(0,0,0,0)",
            pointerEvents: "none",
          },
        }}
        initial="top"
        animate={navState}
        transition={{ type: "spring", stiffness: 200, damping: 25, mass: 1 }}
        className="pointer-events-auto relative flex items-center px-4 overflow-hidden backdrop-blur-2xl"
      >
        <div className="flex w-full items-center justify-between transition-opacity duration-300" style={{ opacity: isHidden ? 0 : 1 }}>
          
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group shrink-0" aria-label="Home">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground transition-transform duration-300 group-hover:scale-105">
              <Sparkles className="h-4 w-4 text-background" />
            </div>
            <AnimatePresence>
              {isTop && (
                <motion.span
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: "auto" }}
                  exit={{ opacity: 0, width: 0 }}
                  className="font-semibold tracking-tight font-[family-name:var(--font-space)] overflow-hidden whitespace-nowrap ml-1"
                >
                  AI ERP
                </motion.span>
              )}
            </AnimatePresence>
          </Link>

          {/* Desktop Center Links */}
          <div className="hidden sm:flex items-center gap-1 absolute left-1/2 -translate-x-1/2">
            {navLinks.map((link) => {
              const isActive = pathname === link.href || pathname.startsWith(link.href + "/");
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "relative px-4 py-2 text-sm font-medium rounded-full transition-colors duration-200",
                    isActive
                      ? "text-background"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {isActive && (
                    <motion.span
                      layoutId="pill-active"
                      className="absolute inset-0 rounded-full bg-foreground"
                      transition={{ type: "spring", stiffness: 150, damping: 22 }}
                    />
                  )}
                  <span className="relative z-10">{link.label}</span>
                </Link>
              );
            })}
          </div>

          {/* Right Side Settings & Hamburger */}
          <div className="flex items-center gap-2 shrink-0">
            {mounted && (
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                className="hidden sm:flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-muted text-foreground"
                aria-label="Toggle theme"
              >
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </motion.button>
            )}

            <Link href="/settings" className="hidden sm:block">
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-border text-foreground text-sm font-medium hover:bg-foreground hover:text-background transition-colors"
                title="Settings"
              >
                <Settings className="w-4 h-4" />
              </motion.div>
            </Link>

            {/* Mobile Hamburger Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="sm:hidden flex h-8 w-8 items-center justify-center rounded-full bg-transparent hover:bg-muted text-foreground transition-colors"
              aria-label="Toggle Menu"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </motion.nav>

      {/* Mobile Dropdown Menu (Full Screen) */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-background/98 backdrop-blur-3xl sm:hidden pointer-events-auto"
          >
            {/* Overlay Close Button */}
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="absolute top-6 right-6 p-2 rounded-full bg-accent/20 text-foreground hover:bg-muted transition-colors z-50"
              aria-label="Close Menu"
            >
              <X className="h-6 w-6" />
            </button>

            <motion.div
              variants={{
                hidden: { opacity: 0 },
                show: {
                  opacity: 1,
                  transition: { staggerChildren: 0.1, delayChildren: 0.1 },
                },
                exit: {
                  opacity: 0,
                  transition: { staggerChildren: 0.05, staggerDirection: -1 },
                },
              }}
              initial="hidden"
              animate="show"
              exit="exit"
              className="flex flex-col w-full px-8 gap-4"
            >
              {navLinks.map((link) => {
                const isActive = pathname === link.href || pathname.startsWith(link.href + "/");
                return (
                  <motion.div key={link.href} variants={{
                    hidden: { opacity: 0, y: 30 },
                    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } },
                    exit: { opacity: 0, y: -20, transition: { duration: 0.2 } }
                  }}>
                    <Link
                      href={link.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        "flex items-center gap-6 px-6 py-5 rounded-2xl transition-colors text-xl font-medium",
                        isActive ? "bg-foreground text-background" : "hover:bg-muted text-foreground bg-accent/20"
                      )}
                    >
                      <link.icon className="h-6 w-6" />
                      <span>{link.label}</span>
                    </Link>
                  </motion.div>
                );
              })}
              
              <motion.div variants={{
                hidden: { opacity: 0, y: 30 },
                show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } },
                exit: { opacity: 0, y: -20 }
              }} className="h-[1px] w-full bg-border my-4" />
              
              {mounted && (
                <motion.div variants={{
                  hidden: { opacity: 0, y: 30 },
                  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } },
                  exit: { opacity: 0, y: -20 }
                }}>
                  <button
                    onClick={() => {
                      setTheme(theme === "dark" ? "light" : "dark");
                    }}
                    className="flex w-full items-center gap-6 px-6 py-5 rounded-2xl hover:bg-muted text-foreground transition-colors text-xl font-medium text-left bg-accent/20"
                  >
                    {theme === "dark" ? <Sun className="h-6 w-6" /> : <Moon className="h-6 w-6" />}
                    <span>Toggle Theme</span>
                  </button>
                </motion.div>
              )}
              
              <motion.div variants={{
                hidden: { opacity: 0, y: 30 },
                show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } },
                exit: { opacity: 0, y: -20 }
              }}>
                <Link
                  href="/settings"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-6 px-6 py-5 rounded-2xl hover:bg-muted text-foreground transition-colors text-xl font-medium bg-accent/20"
                >
                  <Settings className="h-6 w-6" />
                  <span>Settings</span>
                </Link>
              </motion.div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
