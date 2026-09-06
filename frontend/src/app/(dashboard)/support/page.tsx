/**
 * Moved. Filing a ticket and reading the FAQ are the same errand, so they are
 * one page now: /help. This route had its own nav entry ("Contact Support")
 * beside "Help & Support", which was two ways to the same thing.
 */
import { redirect } from "next/navigation";

export default function MovedSupport() {
  redirect("/help");
}
