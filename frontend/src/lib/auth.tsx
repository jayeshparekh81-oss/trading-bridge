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
import { apiClient } from "./api";

interface User {
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
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    phone?: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "tb_access_token";
const REFRESH_KEY = "tb_refresh_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const saveTokens = useCallback((tokens: AuthTokens) => {
    localStorage.setItem(TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    setToken(tokens.access_token);
  }, []);

  const clearAuth = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const fetchUser = useCallback(
    async (accessToken: string) => {
      try {
        const userData = await apiClient.get<User>(
          "/api/auth/me",
          accessToken
        );
        setUser(userData);
      } catch {
        clearAuth();
      }
    },
    [clearAuth]
  );

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) {
      setToken(stored);
      fetchUser(stored).finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [fetchUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await apiClient.post<AuthTokens>("/api/auth/login", {
        email,
        password,
      });
      saveTokens(tokens);
      await fetchUser(tokens.access_token);
    },
    [saveTokens, fetchUser]
  );

  const register = useCallback(
    async (data: {
      email: string;
      password: string;
      full_name: string;
      phone?: string;
    }) => {
      await apiClient.post("/api/auth/register", data);
    },
    []
  );

  const logout = useCallback(() => {
    if (token) {
      apiClient
        .post("/api/auth/logout", {}, token)
        .catch(() => {});
    }
    clearAuth();
  }, [token, clearAuth]);

  const value = useMemo(
    () => ({ user, token, isLoading, login, register, logout }),
    [user, token, isLoading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export type { User, AuthTokens };
