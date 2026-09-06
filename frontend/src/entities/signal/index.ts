/**
 * signal — the subscriber signal feed's shape, as the backend serialises it.
 *
 * Types only, no runtime: an entity owns the vocabulary, not the fetching.
 * Reach for this barrel, never for the file inside — slice internals are
 * private (ADR 0001 §1).
 */
export * from "./model/types";
