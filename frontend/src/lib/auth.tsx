"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { api, ApiError, setTokens, clearTokens } from "./api";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  is_active: boolean;
  is_admin: boolean;
  telegram_chat_id: string | null;
  notification_prefs: Record<string, boolean>;
  created_at: string;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; full_name: string; phone?: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const fetchUser = useCallback(async () => {
    try {
      const u = await api.get<User>("/auth/me");
      setUser(u);
    } catch {
      clearTokens();
      setUser(null);
    }
  }, []);

  // Check auth on mount
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("tb_access_token") : null;
    if (token) {
      fetchUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [fetchUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      try {
        const tokens = await api.post<AuthTokens>("/auth/login", { email, password }, true);
        setTokens(tokens.access_token, tokens.refresh_token);
        await fetchUser();
        toast.success("Login successful!");
        router.push("/");
      } catch (err) {
        const msg = err instanceof ApiError ? err.detail : "Login failed";
        toast.error(msg);
        throw err;
      }
    },
    [fetchUser, router],
  );

  const register = useCallback(
    async (data: { email: string; password: string; full_name: string; phone?: string }) => {
      try {
        await api.post("/auth/register", data, true);
        toast.success("Account created! Logging in...");
        // Auto-login after register
        const tokens = await api.post<AuthTokens>("/auth/login", { email: data.email, password: data.password }, true);
        setTokens(tokens.access_token, tokens.refresh_token);
        await fetchUser();
        router.push("/");
      } catch (err) {
        const msg = err instanceof ApiError ? err.detail : "Registration failed";
        toast.error(msg);
        throw err;
      }
    },
    [fetchUser, router],
  );

  const logout = useCallback(() => {
    api.post("/auth/logout", {}).catch(() => {});
    clearTokens();
    setUser(null);
    toast.success("Logged out");
    router.push("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, isLoading, isAuthenticated: !!user, login, register, logout }),
    [user, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
