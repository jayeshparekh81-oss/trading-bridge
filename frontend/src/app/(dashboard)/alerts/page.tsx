import { ComingSoon } from "@/components/coming-soon";

export default function AlertsPage() {
  return (
    <ComingSoon
      pageName="Alerts"
      description="Configure Telegram and email alert preferences per event type (ENTRY / PARTIAL / EXIT / SL_HIT / errors / kill switch). Telegram is already firing reliably end-to-end — UI to toggle individual events lands once the per-user preferences endpoint ships."
    />
  );
}
