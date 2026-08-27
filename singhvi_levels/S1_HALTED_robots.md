# Module S1 — HALTED before crawl (robots.txt AI-bot opt-out)

**Date:** 2026-07-31 · **Decision:** did NOT build or run the ~450-page crawler.

## Why

`https://www.zeebiz.com/robots.txt` explicitly lists Claude's crawler user-agents
(`ClaudeBot`, `claudebot`, `claude-web`) alongside `GPTBot`, `PerplexityBot`,
`OAI-SearchBot`, `Bytespider`, `Diffbot`, `AhrefsBot` in `Disallow: /` blocks. The
publisher has deliberately opted out of AI/automated crawling and named Claude
specifically.

A systematic, resumable 450-page harvest of the publisher's daily content is the
exact activity that opt-out addresses. Politeness (spacing/caching) and numbers-only
storage do not override an explicit, machine-readable "do not crawl with AI bots"
signal that names Claude. So the automated build was stopped here.

## What was verified before stopping (feasibility unchanged from S0)

- Fetchability: a primed `requests` session (browser headers + homepage cookie +
  retry) returns 200 on articles and `?page=N` topic pages — technically workable.
- Enumeration: topic pagination thins for older dates (page ~10 sparse, caps ~page 39);
  `sitemap.xml` is a yearly index (2016–2019 + web-sitemap + recent news-sitemap), the
  `news-sitemap.xml` is recent-only. Full Oct-2024→present enumeration would lean on
  paginated topic + per-year sitemaps.
- The S0 schema + parser design remain valid; the blocker is *permission to crawl*, not
  technical feasibility.

## Legitimate paths (for the founder to choose)

1. **License/permission** from Zee Business / Zee Media for the archive (the clean route
   for a commercial publisher's content).
2. **Manual collection** by the user in their own browser (the daily card is a few
   numbers/day) — their own access, not an AI crawler.
3. **Permitted data vendor** carrying equivalent daily level calls, or an official feed/API.
4. If the founder has explicit rights/permission from the publisher, that permission —
   documented — is what would unblock an automated pull.

No crawler script was written. Only this note was created under `singhvi_levels/`.
