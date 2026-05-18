# API Reference

Auto-generated from the FastAPI OpenAPI schema by
`scripts/generate_api_docs.py`. The script supports two modes:

1. **Import-app mode** — imports `app.main.create_app()` directly,
   builds the schema in-process. Fastest; requires full backend dep
   tree installed (`pip install -e backend/`).
2. **Live-server mode** — hits `GET /openapi.json` against a running
   backend.

## How to regenerate

### From a checkout with full deps
```sh
cd backend && pip install -e .
cd ..
python3 scripts/generate_api_docs.py --import
```

### From a running server
```sh
python3 scripts/generate_api_docs.py --url http://localhost:8000
```

### CI / scheduled regen
A GitHub Actions job can call the script post-deploy to keep docs
in sync. Workflow not currently in `.github/workflows/` — schedule
when the existing `MANUAL_INSTALL_CI_WORKFLOW.md` workflow YAML lands.

## What gets generated

- `INDEX.md` — one-line summary per endpoint, grouped by tag
- `<TAG>.md` — one file per router tag with full request/response
  reference per endpoint

Tag → filename mapping uppercases + replaces hyphens with underscores
(e.g. `strategy-engine` → `STRATEGY_ENGINE.md`).

## Hard rules (re-stated from script docstring)

- NO live API tokens or secrets written to output
- Endpoint examples use placeholder values
- Per-route descriptions pulled from docstrings (so docstrings ARE the
  spec — keep them current)

## What's pre-curated vs auto-generated

The files in this directory shipped with the `docs/api-reference-v1`
branch are pre-curated stubs reflecting the router structure as of
2026-05-18. They're 1:1 mappings of `app.include_router(...)` calls
in `app/main.py:_register_routers()`.

The first real regeneration (post-merge, with deps installed) will
overwrite these stubs with the full auto-generated reference.
