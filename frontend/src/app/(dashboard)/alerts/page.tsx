import { ComingSoon } from "@/components/coming-soon";

export default function AlertsPage() {
  return (
    <ComingSoon
      pageName="Alerts"
      description="Per-event alert preferences (entry, partial, exit, stop-loss, errors, kill switch) by email and Telegram. Per-customer trade alerts are not live yet; today you get the daily and weekly summary email from Settings."
    />
  );
}
