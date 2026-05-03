import { ComingSoon } from "@/components/coming-soon";

export default function AdminAnnouncementsPage() {
  return (
    <ComingSoon
      pageName="Announce (admin)"
      description="Compose and broadcast platform-wide announcement banners. Backend POST /api/admin/announcements exists — UI in a later sprint."
    />
  );
}
