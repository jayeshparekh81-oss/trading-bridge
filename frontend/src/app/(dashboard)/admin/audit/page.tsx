import { ComingSoon } from "@/components/coming-soon";

export default function AdminAuditPage() {
  return (
    <ComingSoon
      pageName="Audit logs"
      description="Full audit log viewer — login events, kill-switch trips, config changes, broker reconnects. Backend /api/admin/audit-logs exists — UI in a later sprint."
    />
  );
}
