"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Mic,
  FileText,
  BarChart3,
  Database,
} from "lucide-react";
import { cn } from "@/lib/utils";

const leftLinks = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/database", label: "Database", icon: Database },
];

const rightLinks = [
  { href: "/documents", label: "Docs", icon: FileText },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

const voiceLink = { href: "/voice", label: "Voice", icon: Mic };

export default function MobileNav() {
  const pathname = usePathname();

  const renderLink = (link: { href: string; label: string; icon: React.ComponentType<{ className?: string }> }) => {
    const isActive = pathname === link.href || pathname.startsWith(link.href + "/");
    const Icon = link.icon;

    return (
      <Link
        key={link.href}
        href={link.href}
        className="flex-1 flex flex-col items-center gap-0.5 py-1.5"
      >
        <div className="relative">
          {isActive && (
            <motion.div
              layoutId="mobile-nav-active"
              className="absolute -inset-1.5 rounded-lg bg-accent"
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
            />
          )}
          <Icon
            className={cn(
              "relative h-5 w-5 transition-colors",
              isActive ? "text-foreground" : "text-muted-foreground"
            )}
          />
        </div>
        <span
          className={cn(
            "text-[10px] font-medium transition-colors",
            isActive ? "text-foreground" : "text-muted-foreground"
          )}
        >
          {link.label}
        </span>
      </Link>
    );
  };

  const isVoiceActive = pathname === voiceLink.href || pathname.startsWith(voiceLink.href + "/");
  const VoiceIcon = voiceLink.icon;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 lg:hidden bg-background border-t border-border">
      <div className="flex items-center justify-between px-2 py-1.5">
        {/* Left two links */}
        {leftLinks.map(renderLink)}

        {/* Center voice button */}
        <div className="flex-1 flex items-center justify-center">
          <Link href={voiceLink.href} className="relative -mt-5">
            <motion.div
              whileTap={{ scale: 0.9 }}
              className={cn(
                "flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-colors",
                isVoiceActive
                  ? "bg-foreground text-background"
                  : "bg-card border border-border text-foreground"
              )}
            >
              <VoiceIcon className="h-6 w-6" />
            </motion.div>
          </Link>
        </div>

        {/* Right two links */}
        {rightLinks.map(renderLink)}
      </div>
      {/* Safe area for notched phones */}
      <div className="h-[env(safe-area-inset-bottom)]" />
    </nav>
  );
}
