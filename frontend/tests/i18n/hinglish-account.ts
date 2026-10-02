/**
 * Side-effect import for tests that pin HINGLISH words: before every test the device carries an
 * explicit Hinglish choice (as a tap on the switch would leave it). Default since 2 Oct 2026 = English.
 * Files that clear localStorage in their own beforeEach call forceLang("hinglish") again after it.
 */
import { beforeEach } from "vitest";
import { forceLang } from "./force-lang";

beforeEach(() => forceLang("hinglish"));
