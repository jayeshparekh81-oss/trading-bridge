/**
 * Retired. /alerts rendered the shared ComingSoon placeholder and carried a
 * "Soon" pill in the sidebar — a nav entry for a page that does nothing. The
 * summary emails it described are configured in Settings, so this forwards
 * there and keeps any bookmark working.
 */
import { redirect } from "next/navigation";

export default function MovedAlerts() {
  redirect("/settings");
}
