"use client";

/**
 * /admin/users — admin-only user list.
 *
 * Wire: GET /api/admin/users (existing). Supports search + paginated
 * lists. Read-only here; activation/role mutations are documented as
 * a future sprint (existing endpoints exist but we don't expose
 * destructive ops in this build).
 */

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Users, Search, Crown, ShieldOff } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useApi } from "@/lib/use-api";
import { relativeTime, cn } from "@/lib/utils";

interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string | null;
}

interface AdminUserList {
  total: number;
  skip: number;
  limit: number;
  users: AdminUser[];
}

const PAGE_SIZE = 50;
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function AdminUsersPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const url = useMemo(() => {
    const qs = new URLSearchParams();
    qs.set("skip", String(page * PAGE_SIZE));
    qs.set("limit", String(PAGE_SIZE));
    if (search.trim()) qs.set("search", search.trim());
    return `/admin/users?${qs.toString()}`;
  }, [page, search]);

  const { data, isLoading } = useApi<AdminUserList>(url);
  const users = data?.users ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Users className="h-6 w-6 text-accent-blue" /> Users (admin)
        </h1>
        <p className="text-muted-foreground text-sm">
          Read-only platform user list. Activation / role / kill-switch reset are admin-only
          mutations — wired in a future sprint.
        </p>
      </header>

      <GlassmorphismCard className="p-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search email or name…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="pl-9"
          />
        </div>
      </GlassmorphismCard>

      <GlassmorphismCard className="overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-muted-foreground">Loading users…</div>
        ) : users.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">No users match.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground uppercase tracking-wider">
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3">User</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Role</th>
                <th className="text-left px-4 py-3">Joined</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-border/40 hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <div className="font-medium">{u.full_name ?? "(no name)"}</div>
                    <div className="text-xs text-muted-foreground">{u.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant={u.is_active ? "default" : "secondary"}
                      className={cn(
                        u.is_active
                          ? "bg-profit/15 text-profit border-profit/30"
                          : "bg-loss/10 text-loss border-loss/30",
                      )}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {u.is_admin ? (
                      <Badge className="bg-amber-500/15 text-amber-300 border-amber-500/30 flex items-center gap-1 w-fit">
                        <Crown className="h-3 w-3" /> Admin
                      </Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <ShieldOff className="h-3 w-3" /> User
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {u.created_at ? relativeTime(u.created_at) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassmorphismCard>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {total.toLocaleString()} users · page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || isLoading}
              className="px-3 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || isLoading}
              className="px-3 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </motion.div>
  );
}
