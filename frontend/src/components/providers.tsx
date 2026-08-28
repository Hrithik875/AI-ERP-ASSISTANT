"use client";

import { ThemeProvider } from "next-themes";
import { ReactNode } from "react";
import { ReactLenis } from "lenis/react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange={false}
    >
      <ReactLenis root>
        {children}
      </ReactLenis>
    </ThemeProvider>
  );
}
