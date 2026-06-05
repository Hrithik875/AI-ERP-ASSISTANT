"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Mic,
  FileText,
  BarChart3,
  Settings,
  Database,
} from "lucide-react";
import { cn } from "@/lib/utils";

const links = [
  { href: "/dashboard", label: "Home", icon: LayoutDashboard },
  { href: "/database", label: "Database", icon: Database },
  { href: "/voice", label: "Voice", icon: Mic, primary: true },
  { href: "/documents", label: "Docs", icon: FileText },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

export default function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 lg:hidden glass border-t border-border">
      <div className="flex items-center justify-around px-2 py-1.5">
        {links.map((link) => {
          const isActive = pathname === link.href || pathname.startsWith(link.href + "/");
          const Icon = link.icon;

          if (link.primary) {
            return (
              <Link key={link.href} href={link.href} className="relative -mt-5">
                <motion.div
                  whileTap={{ scale: 0.9 }}
                  className={cn(
                    "flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-colors",
                    isActive
                      ? "bg-foreground text-background"
                      : "bg-card border border-border text-foreground"
                  )}
                >
                  <Icon className="h-6 w-6" />
                </motion.div>
              </Link>
            );
          }

          return (
            <Link
              key={link.href}
              href={link.href}
              className="flex flex-col items-center gap-0.5 py-1.5 px-3"
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
        })}
      </div>
      {/* Safe area for notched phones */}
      <div className="h-[env(safe-area-inset-bottom)]" />
    </nav>
  );
}
