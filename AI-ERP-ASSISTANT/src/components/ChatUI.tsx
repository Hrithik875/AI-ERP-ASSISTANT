"use client";

import { useState, useRef, useEffect, useImperativeHandle, forwardRef, FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Bot, User, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatMessage, sendChatMessage } from "@/lib/api";

export interface ChatUIHandle {
  addTranscript: (text: string, response: string) => void;
}

interface ChatUIProps {
  initialMessages?: ChatMessage[];
}

const ChatUI = forwardRef<ChatUIHandle, ChatUIProps>(function ChatUI(
  { initialMessages = [] },
  ref
) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  // Load persistently stored session history to prevent navigation destruction
  useEffect(() => {
    const savedSession = localStorage.getItem("erp_chat_history");
    if (savedSession) {
      try {
        const parsed = JSON.parse(savedSession);
        parsed.forEach((m: any) => m.timestamp = new Date(m.timestamp));
        setMessages(parsed);
      } catch (e) {}
    }
  }, []);

  // Save history on changes
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem("erp_chat_history", JSON.stringify(messages));
    }
  }, [messages]);

  useImperativeHandle(ref, () => ({
    addTranscript(text: string, response: string) {
      const userMsg: ChatMessage = {
        id: Date.now().toString(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };
      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg, aiMsg]);
    },
  }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await sendChatMessage(userMsg.content);
      setMessages((prev) => [...prev, response]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="relative flex flex-col h-full w-full overflow-hidden">
      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-scroll px-4 py-6 space-y-4"
        style={{ overscrollBehavior: "contain" }}
      >
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center h-full text-center py-20"
          >
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent mb-4">
              <Bot className="h-7 w-7 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-1">Start a conversation</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              Ask me anything about your ERP data — attendance, grades, schedules, and more.
            </p>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg, i) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.3, delay: i === messages.length - 1 ? 0.1 : 0 }}
              className={cn(
                "flex gap-3",
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {msg.role === "assistant" && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent mt-0.5">
                  <Bot className="h-4 w-4" />
                </div>
              )}
              <div
                className={cn(
                  "max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-foreground text-background rounded-br-md"
                    : "bg-card border border-border rounded-bl-md"
                )}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                <p
                  suppressHydrationWarning
                  className={cn(
                    "mt-1.5 text-[10px]",
                    msg.role === "user"
                      ? "text-background/50"
                      : "text-muted-foreground"
                  )}
                >
                  {msg.timestamp.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
              {msg.role === "user" && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-foreground text-background mt-0.5">
                  <User className="h-4 w-4" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Typing Indicator */}
        <AnimatePresence>
          {isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="flex gap-3"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-1 rounded-2xl bg-card border border-border px-4 py-3 rounded-bl-md">
                <motion.div
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 1.2, repeat: Infinity, delay: 0 }}
                  className="h-2 w-2 rounded-full bg-muted-foreground"
                />
                <motion.div
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 1.2, repeat: Infinity, delay: 0.2 }}
                  className="h-2 w-2 rounded-full bg-muted-foreground"
                />
                <motion.div
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 1.2, repeat: Infinity, delay: 0.4 }}
                  className="h-2 w-2 rounded-full bg-muted-foreground"
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Input */}
      <div className="border-t border-border p-4">
        <form onSubmit={handleSubmit} className="flex items-center gap-3" suppressHydrationWarning>
          <input
            suppressHydrationWarning
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your query…"
            disabled={isLoading}
            className="flex-1 bg-accent rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground outline-none border border-transparent focus:border-border transition-colors duration-200 disabled:opacity-50"
          />
          <motion.button
            suppressHydrationWarning
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            type="submit"
            disabled={!input.trim() || isLoading}
            className="flex h-11 w-11 items-center justify-center rounded-xl bg-foreground text-background transition-opacity disabled:opacity-30"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </motion.button>
        </form>
      </div>
    </div>
  );
});

export default ChatUI;
