import { ComingSoon } from "@/components/coming-soon";

export default function AdminSystemHealthPage() {
  return (
    <ComingSoon
      pageName="System Health"
      description="Backend status, database / Redis health, broker latency metrics, recent errors. Backend endpoint /api/admin/system-health exists — UI wire-up in next sprint."
    />
  );
}
