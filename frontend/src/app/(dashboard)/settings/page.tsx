"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import { motion } from "framer-motion";
import {
  Moon,
  Sun,
  Volume2,
  Mic,
  User,
  Mail,
  Building,
  Globe,
} from "lucide-react";
import { Card } from "@/components/Cards";

const stagger = {
  animate: { transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
};

function Toggle({
  enabled,
  onChange,
}: {
  enabled: boolean;
  onChange: (val: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
        enabled ? "bg-foreground" : "bg-border"
      }`}
    >
      <motion.span
        animate={{ x: enabled ? 20 : 2 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
        className={`inline-block h-4 w-4 rounded-full transition-colors ${
          enabled ? "bg-background" : "bg-muted-foreground"
        }`}
      />
    </button>
  );
}

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [autoPlay, setAutoPlay] = useState(true);
  const [notifications, setNotifications] = useState(false);

  return (
    <div className="p-6 lg:p-8 max-w-3xl">
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
          Preferences
        </motion.p>
        <motion.h1
          variants={fadeUp}
          transition={{ duration: 0.4 }}
          className="text-3xl sm:text-4xl font-bold tracking-tight font-[family-name:var(--font-space)]"
        >
          Settings
        </motion.h1>
      </motion.div>

      <div className="space-y-6">
        {/* Profile Section */}
        <Card delay={0} hover={false}>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-5">
            Profile
          </h2>
          <div className="flex items-start gap-5 mb-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-foreground text-background text-xl font-bold shrink-0">
              R
            </div>
            <div>
              <h3 className="text-lg font-semibold">Dr. Raghav Sharma</h3>
              <p className="text-sm text-muted-foreground">Professor • CSE</p>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="mt-3 text-xs font-medium text-muted-foreground rounded-lg border border-border px-3 py-1.5 hover:bg-accent transition-colors"
              >
                Edit Profile
              </motion.button>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { icon: Mail, label: "Email", value: "raghav.sharma@university.edu" },
              { icon: Building, label: "Department", value: "Computer Science" },
              { icon: User, label: "Employee ID", value: "FAC001" },
              { icon: Globe, label: "Language", value: "English" },
            ].map((item, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-xl bg-accent/50 px-4 py-3"
              >
                <item.icon className="h-4 w-4 text-muted-foreground shrink-0" />
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {item.label}
                  </p>
                  <p className="text-sm font-medium">{item.value}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Appearance */}
        <Card delay={0.08} hover={false}>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-5">
            Appearance
          </h2>
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              {theme === "dark" ? (
                <Moon className="h-4 w-4 text-muted-foreground" />
              ) : (
                <Sun className="h-4 w-4 text-muted-foreground" />
              )}
              <div>
                <p className="text-sm font-medium">Dark Mode</p>
                <p className="text-xs text-muted-foreground">
                  Toggle dark and light theme
                </p>
              </div>
            </div>
            <Toggle
              enabled={theme === "dark"}
              onChange={(v) => setTheme(v ? "dark" : "light")}
            />
          </div>
        </Card>

        {/* Voice Settings */}
        <Card delay={0.16} hover={false}>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-5">
            Voice Settings
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-3">
                <Mic className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Voice Input</p>
                  <p className="text-xs text-muted-foreground">
                    Enable microphone for voice queries
                  </p>
                </div>
              </div>
              <Toggle enabled={voiceEnabled} onChange={setVoiceEnabled} />
            </div>
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-3">
                <Volume2 className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Auto-play Responses</p>
                  <p className="text-xs text-muted-foreground">
                    Automatically play AI voice responses
                  </p>
                </div>
              </div>
              <Toggle enabled={autoPlay} onChange={setAutoPlay} />
            </div>
          </div>
        </Card>

        {/* Notifications */}
        <Card delay={0.24} hover={false}>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-5">
            Notifications
          </h2>
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm font-medium">Push Notifications</p>
              <p className="text-xs text-muted-foreground">
                Get notified about important updates
              </p>
            </div>
            <Toggle enabled={notifications} onChange={setNotifications} />
          </div>
        </Card>
      </div>
    </div>
  );
}
