"""ASGI / Starlette middleware.

Kept in one package so :func:`app.main.create_app` can register them in a
predictable order. Order matters: request-id → size-limit → trusted-proxy →
timing → sensitive-filter → security-headers (outermost).
"""
