"use client";

/**
 * useSignupOpen — "open" only when the backend said, live, that public signup is open.
 * "checking" and "closed" both hide every signup link (fail closed). See lib/signup-status.ts.
 */

import { useEffect, useState } from "react";

import { signupOpen } from "@/lib/signup-status";

export type SignupState = "checking" | "open" | "closed";

export function useSignupOpen(): SignupState {
  const [state, setState] = useState<SignupState>("checking");
  useEffect(() => {
    let alive = true;
    signupOpen().then(
      (ok) => { if (alive) setState(ok ? "open" : "closed"); },
      () => { if (alive) setState("closed"); },
    );
    return () => { alive = false; };
  }, []);
  return state;
}
