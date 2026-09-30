"use client";

/**
 * SignupOrLogin — every "Start Free / Account banao" link on the site (1 Oct 2026).
 *
 * While public signup is CLOSED (or the backend has not said, live, that it is open) the link
 * becomes a plain "Login karo" link: the site never invites a stranger to a form the server will
 * refuse (lib/signup-status.ts — the server is the gate, this is courtesy).
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { useSignupOpen } from "@/hooks/useSignupOpen";
import { SIGNUP_CLOSED_LINE } from "@/lib/signup-status";

export function SignupOrLogin({
  href = "/register",
  loginHref = "/login",
  className,
  children,
  closedText = "Login karo",
  testid,
  onClick,
}: {
  href?: string;
  loginHref?: string;
  className?: string;
  children: ReactNode;
  closedText?: ReactNode;
  testid?: string;
  onClick?: () => void;
}) {
  const state = useSignupOpen();
  if (state === "open") {
    return (
      <Link href={href} className={className} data-testid={testid} onClick={onClick}>
        {children}
      </Link>
    );
  }
  return (
    <Link
      href={loginHref}
      className={className}
      data-testid={testid ? `${testid}-closed` : "signup-closed-login"}
      title={SIGNUP_CLOSED_LINE}
      onClick={onClick}
    >
      {closedText}
    </Link>
  );
}
