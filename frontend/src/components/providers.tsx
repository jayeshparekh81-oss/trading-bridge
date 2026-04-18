"use client";

import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { AuthProvider } from "@/lib/auth";
import { CustomThemeProvider } from "@/lib/theme-context";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange={false}
    >
      <CustomThemeProvider>
        <AuthProvider>
          {children}
          <Toaster
            theme="dark"
            position="top-right"
            richColors
            closeButton
            toastOptions={{
              style: {
                background: "var(--card)",
                border: "1px solid var(--border)",
                backdropFilter: "blur(12px)",
                color: "var(--foreground)",
              },
            }}
          />
        </AuthProvider>
      </CustomThemeProvider>
    </ThemeProvider>
  );
}
