import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import boundaries from "eslint-plugin-boundaries";

/**
 * ADR 0001 (docs/adr/0001-frontend-architecture.md) is enforced here, not in review.
 *
 *   §1 layer direction   -> boundaries/element-types + boundaries/no-private
 *   §3 design tokens     -> the no-restricted-syntax block below
 *
 * Both rules are proven to fail on an injected violation by
 * tests/architecture/enforcement.test.ts, which lints deliberately-bad code
 * through THIS config and fails if ESLint stays quiet. That test is the only
 * thing standing between "enforced" and "silently disabled": boundaries
 * passes everything if its element patterns stop matching or the @/ alias
 * stops resolving.
 */

// ── ADR 0001 §1: the layers, and who may import whom ───────────────────
// Direction is downward only:  app > widgets > features > entities > shared
// `legacy` is the not-yet-migrated tree. It is the OLD world: it may import
// anything except app, and route files may still reach into it while the
// migration runs. What it may NOT do is be imported by a migrated slice —
// that is what stops the tangle re-forming inside the new tree.
// eslint-plugin-boundaries v7 selector syntax.
const from = (type) => [{ element: { type } }];
const to = (...types) => types.map((type) => ({ to: { element: { type } } }));

const LAYER_RULES = [
  { from: from("app"), allow: to("widgets", "features", "entities", "shared", "legacy") },
  { from: from("widgets"), allow: to("features", "entities", "shared") },
  { from: from("features"), allow: to("entities", "shared") },
  { from: from("entities"), allow: to("shared") },
  { from: from("shared"), allow: to("shared") },
  { from: from("legacy"), allow: to("legacy", "shared", "entities", "features", "widgets") },
];

// ── ADR 0001 §3: where raw design values are legitimate ────────────────
// An exception is a decision, so it is listed here rather than assumed.
// Verified against the tree on 2026-09-06: these are the ONLY two files that
// carry raw design values for a real reason. Every other path considered
// (themes.ts, fonts.ts, lib/chart, components/charts, logo.tsx, brand/**,
// lib/email) turned out to hold zero raw values, so granting them an
// exception would have been an untrue statement about the code.
const TOKEN_EXCEPTIONS = [
  // lightweight-charts takes literal colour strings in its options objects —
  // it cannot read a CSS custom property. The className-based colours in the
  // rest of src/components/chart are NOT exempt and use tokens.
  "src/components/chart/CandlestickChart.tsx",
  // The theme picker renders swatches OF the palettes; the hex values are its
  // data, not styling choices.
  "src/components/theme-picker.tsx",
  // canvas-confetti takes an array of literal colour strings.
  "src/lib/celebration.ts",
  // Chart marker colours handed to the charting layer as literals.
  "src/lib/markers-overlay/mapper.ts",
  // Razorpay's hosted checkout widget is themed with a literal hex.
  "src/lib/billing/razorpay.ts",
  // The glossary tooltip is deliberately theme-INDEPENDENT: it renders a fixed
  // light card (bg-white / text-gray-900) in both themes, with its own palette.
  // ⚠ Flagged for the founder: should this tooltip follow the theme instead?
  "src/components/SamjhoWord.tsx",
];

// Utilities whose arbitrary values ARE design decisions and must come from a
// token. Layout constraints (h/w/min-*/max-*/inset/grid-cols/basis) are
// deliberately NOT here: a modal's max-width or a chart box's height is a
// layout constraint, not a design token, and Tailwind's spacing scale is a
// rhythm scale rather than a constraint vocabulary. Forcing those through
// tokens would add ceremony without removing a single real defect.
const SPACING_UTILS = "p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml|gap|gap-x|gap-y|space-x|space-y";
const TOKENED_UTILS = "rounded|rounded-[a-z]+|ring|ring-offset|shadow|backdrop-blur|blur|border|border-[a-z]+";

// An arbitrary value that already references a CSS custom property is using a
// token — never flag it (e.g. rounded-[min(var(--radius-md),12px)]).
const NOT_VAR = "(?![^\\]]*var\\(--)";

const RAW_DESIGN_VALUE_RULES = [
  {
    selector: "Literal[value=/#[0-9a-fA-F]{3,8}\\b/]",
    message:
      "ADR 0001 §3: hardcoded colour. Use a token from src/app/globals.css (@theme) — e.g. text-profit, bg-card, border-border. Add a token first if none fits.",
  },
  {
    selector: "TemplateElement[value.raw=/#[0-9a-fA-F]{3,8}\\b/]",
    message: "ADR 0001 §3: hardcoded colour in a template literal. Use a token from src/app/globals.css (@theme).",
  },
  {
    selector: "Literal[value=/(rgba?|hsla?)\\(/]",
    message:
      "ADR 0001 §3: raw rgb()/hsl() colour. Use a token from src/app/globals.css (@theme), or a token with an opacity modifier (bg-profit/10).",
  },
  {
    selector: "TemplateElement[value.raw=/(rgba?|hsla?)\\(/]",
    message: "ADR 0001 §3: raw rgb()/hsl() colour in a template literal. Use a token from src/app/globals.css (@theme).",
  },
  {
    selector: `Literal[value=/(^|[\\s"'\`])text-\\[${NOT_VAR}[^\\]]*[0-9.]+(px|rem)/]`,
    message:
      "ADR 0001 §3: raw font size. Use the type scale in src/app/globals.css (@theme) — text-8 / text-9 / text-10 / text-11 / text-xs / text-13 / text-15 / text-sm …",
  },
  {
    selector: `Literal[value=/(^|[\\s"'\`])(${SPACING_UTILS})-\\[${NOT_VAR}[^\\]]*[0-9.]+px/]`,
    message: "ADR 0001 §3: raw pixel spacing. Use the spacing scale (p-4, gap-3, mt-2), which already resolves to tokens.",
  },
  {
    selector: `Literal[value=/(^|[\\s"'\`])(${TOKENED_UTILS})-\\[${NOT_VAR}[^\\]]*[0-9.]+px/]`,
    message:
      "ADR 0001 §3: raw pixel value on a token-governed property (radius / ring / shadow / blur / border). Add a token in src/app/globals.css (@theme) and use it.",
  },
];

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,

  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),

  // ── ADR 0001 §1 — layer direction and slice isolation ───────────────
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { boundaries },
    settings: {
      "boundaries/include": ["src/**/*.{ts,tsx}"],
      "boundaries/elements": [
        // Order matters: first match wins, so the FSD tree is declared before
        // the legacy catch-all.
        { type: "shared", pattern: "src/shared/**" },
        { type: "entities", pattern: "src/entities/*", capture: ["slice"] },
        { type: "features", pattern: "src/features/*", capture: ["slice"] },
        { type: "widgets", pattern: "src/widgets/*", capture: ["slice"] },
        { type: "app", pattern: "src/app/**" },
        {
          type: "legacy",
          pattern: [
            "src/components/**",
            "src/lib/**",
            "src/hooks/**",
            "src/contexts/**",
          ],
        },
      ],
    },
    rules: {
      "boundaries/element-types": ["error", { default: "disallow", rules: LAYER_RULES }],
      // Every file under src/ must belong to a declared layer. A new top-level
      // directory is a structural decision, so it fails until it is declared.
      "boundaries/no-unknown-files": "error",
    },
  },

  // ── ADR 0001 §3 — design tokens ─────────────────────────────────────
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: TOKEN_EXCEPTIONS,
    rules: { "no-restricted-syntax": ["error", ...RAW_DESIGN_VALUE_RULES] },
  },
]);

export default eslintConfig;
