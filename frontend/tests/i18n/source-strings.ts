/**
 * Customer-readable strings in a source file (the same extractor the ten-point rule test uses —
 * tests/copy/customer-screen-rules.test.ts; copied here so a test never imports another test's
 * describe blocks).
 */

/** Drop comments, keep strings (a `//` inside a URL string is not a comment). */
export function stripComments(src: string): string {
  let out = src.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
  out = out.replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, "");
  out = out.replace(/(^|[^:"'`\w])\/\/[^\n]*/g, "$1");
  return out;
}

/** A string that is code, not words a customer reads. */
function looksLikeCode(s: string): boolean {
  const t = s.trim();
  if (!t) return true;
  if (!/\s/.test(t)) return true; // single token: a key, a path, an id, a class
  if (/^(\/|https?:|@\/|\.\/|\.\.\/)/.test(t)) return true;
  if (/(^|\s)(flex|grid|inline-flex|text-|bg-|px-|py-|p-\d|m[tbxy]?-\d|rounded|border|items-|justify-|gap-|w-|h-\d|min-h|max-w|font-|hover:|space-y|sr-only|shrink|truncate|tracking-|leading-|ring-|opacity-|transition|overflow|absolute|relative|sticky|z-\d)/.test(t)) return true;
  if (/^[\w.$]+\(/.test(t) || /=>|===|!==|&&|\|\|/.test(t)) return true;
  return false;
}

/** Every piece of text a customer could read, with its line number. */
export function customerStrings(src: string): { line: number; text: string }[] {
  const clean = stripComments(src);
  const out: { line: number; text: string }[] = [];
  const lineOf = (i: number) => clean.slice(0, i).split("\n").length;
  const lit = /"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)'|`((?:[^`\\]|\\.)*)`/g;
  let m: RegExpExecArray | null;
  while ((m = lit.exec(clean))) {
    let s = m[1] ?? m[2] ?? m[3] ?? "";
    s = s.replace(/\$\{[^}]*\}/g, " ");
    if (!looksLikeCode(s)) out.push({ line: lineOf(m.index), text: s });
  }
  const jsx = />([^<>{}]*[A-Za-z][^<>{}]*)</g;
  while ((m = jsx.exec(clean))) {
    const s = m[1].replace(/\s+/g, " ").trim();
    if (s && !/[;=]/.test(s)) out.push({ line: lineOf(m.index), text: s });
  }
  return out;
}
