/**
 * strategy — what a strategy IS, in the customer's language.
 *
 * Today this is the explainer corpus: one plain-Hinglish explanation per
 * strategy slug, read by the template detail page and by the templates
 * explainer link. Types-and-content only; nothing here fetches.
 *
 * NOTE: the strategy COMPONENTS (builders, pine importer, go-live, the truth
 * and deviation panels) are deliberately still in the legacy tree — see
 * docs/adr/0001 §"Deliberately not migrated". They cannot move until the
 * kill-switch, system-mode, mode and indicators slices exist, because they
 * import all four.
 */
export * from "./lib/explainers";
