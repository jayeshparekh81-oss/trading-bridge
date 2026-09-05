import { notFound } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Dev-only design previews (fixtures, no auth). Served ONLY when the dev server
 * is started with NEXT_PUBLIC_DEV_PREVIEW=1; production builds never set it,
 * so every /dev-preview/* URL is a 404 on tradetri.com.
 */
export default function DevPreviewLayout({ children }: { children: ReactNode }) {
  if (process.env.NEXT_PUBLIC_DEV_PREVIEW !== "1") notFound();
  return <>{children}</>;
}
