/**
 * THE ONE LIST of customer-copy dictionaries. The one-language-per-screen guard
 * (tests/i18n/one-language-per-screen.test.tsx) walks exactly this list: every dictionary must
 * carry `en` and `hinglish` with ONE key set, no Hinglish word in the English block, no English
 * sentence frame in the Hinglish block, and the honest lines (NOT MEASURED, the practice line, the
 * risk lines) present in both. A new screen's dictionary joins this list the day it is written.
 */

import type { Copy } from "@/lib/i18n/core";

import { siteCopy } from "./site";
import { authCopy } from "./auth";
import { publicCopy } from "./public";
import { guidedCopy } from "./guided";
import { appCopy } from "./app";

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- a heterogeneous registry of dictionaries
export const ALL_COPIES: ReadonlyArray<Copy<any>> = [siteCopy, authCopy, publicCopy, guidedCopy, appCopy];
