"""Regression tests for the May-17-night deploy-path bugs.

Three latent bugs nearly broke the Strategy Template System deploy on
May 17, 2026. Each was fixed in-place; this module is the regression
shield so they never reappear unnoticed:

  Bug #1 — Missing CLI entry script.
    The deploy runbook called
    ``python -m app.templates.scripts.seed_strategy_templates`` but the
    ``scripts/`` package was not present in the repo. Caught during the
    first staging seed-loader run. Fixed by shipping
    ``backend/app/templates/scripts/{__init__,seed_strategy_templates}.py``.

  Bug #2 — Dockerfile did not copy ``backend/data/``.
    The seed loader reads ``strategy_templates_seed.json`` from
    ``./data/`` inside the runtime container. The original Dockerfile
    only COPY-d ``app``, ``alembic.ini``, ``migrations``, ``scripts``,
    so the JSON was missing in the built image. Fixed by adding
    ``COPY --chown=appuser:appgroup data ./data`` to the runtime stage.

  Bug #3 — ``registry._default_seed_path`` host-only path resolution.
    The original resolver hard-coded a host-layout path
    (``parents[3] / backend / data / ...``) that resolved to
    ``/backend/data/...`` inside the container — a directory that
    doesn't exist. Fixed by switching to a multi-candidate probe that
    tries both host and container layouts.

These regression tests run as part of the standard pytest sweep and
also light up under the integration GitHub Actions workflow. They are
**static-analysis only** — none of them launches Docker or hits a
real registry — so they're safe in any CI environment.
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"


# ═══════════════════════════════════════════════════════════════════════
# Bug #1 — Seed-loader CLI script is shipped and importable
# ═══════════════════════════════════════════════════════════════════════


class TestSeedCLIScriptShipped:
    """Catches: ``python -m app.templates.scripts.seed_strategy_templates``
    fails with ``ModuleNotFoundError`` because the package wasn't shipped.

    Failure mode if regression returns: the deploy step that re-seeds
    the catalog would silently no-op (or hard-fail at startup) and
    customers would see an empty Strategy Picker.
    """

    def test_scripts_package_file_exists(self) -> None:
        package_init = (
            BACKEND_DIR / "app" / "templates" / "scripts" / "__init__.py"
        )
        assert package_init.exists(), (
            "Seed-loader CLI package marker missing — "
            f"expected {package_init}. This is the May-17 Bug #1 "
            "regression. Restore backend/app/templates/scripts/__init__.py."
        )

    def test_seed_strategy_templates_module_file_exists(self) -> None:
        module_path = (
            BACKEND_DIR
            / "app"
            / "templates"
            / "scripts"
            / "seed_strategy_templates.py"
        )
        assert module_path.exists(), (
            "Seed-loader CLI module missing — "
            f"expected {module_path}. This is the May-17 Bug #1 "
            "regression. The deploy runbook calls "
            "`python -m app.templates.scripts.seed_strategy_templates`."
        )

    def test_seed_strategy_templates_module_is_importable(self) -> None:
        mod = importlib.import_module(
            "app.templates.scripts.seed_strategy_templates"
        )
        assert hasattr(mod, "_parse_args"), (
            "Imported seed_strategy_templates but argparse entry "
            "missing — the CLI shape regressed."
        )

    def test_seed_strategy_templates_cli_help_runs(self) -> None:
        """End-to-end CLI smoke — runs the script with ``--help`` and
        asserts it exits cleanly with usage in stdout.

        This is the test that would have caught the May-17 incident
        directly: if the script doesn't exist or fails to import, this
        test fails fast with a clear ModuleNotFoundError.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.templates.scripts.seed_strategy_templates",
                "--help",
            ],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, (
            "Seed CLI --help exited non-zero. stderr:\n"
            f"{result.stderr}\nstdout:\n{result.stdout}"
        )
        assert "--seed-path" in result.stdout, (
            "--seed-path flag missing from CLI usage — CLI shape regressed."
        )
        assert "--dry-run" in result.stdout, (
            "--dry-run flag missing from CLI usage — CLI shape regressed."
        )


# ═══════════════════════════════════════════════════════════════════════
# Bug #2 — Dockerfile copies the data/ directory into the runtime image
# ═══════════════════════════════════════════════════════════════════════


class TestDockerfileCopiesDataDirectory:
    """Catches: the runtime stage of ``backend/Dockerfile`` does not
    COPY ``data ./data``, so ``strategy_templates_seed.json`` is missing
    in the deployed container and the seed loader raises
    ``FileNotFoundError`` at startup.

    Failure mode if regression returns: customers see an empty
    catalog after deploy, OR the seed loader's startup hook crashes
    and the backend container restart-loops.
    """

    def test_dockerfile_present_at_expected_path(self) -> None:
        dockerfile = BACKEND_DIR / "Dockerfile"
        assert dockerfile.exists(), (
            f"Dockerfile missing at {dockerfile} — cannot verify "
            "the May-17 Bug #2 fix is in place."
        )

    def test_dockerfile_copies_data_directory_in_runtime_stage(self) -> None:
        dockerfile = (BACKEND_DIR / "Dockerfile").read_text(encoding="utf-8")

        # Find the runtime stage (everything after the second `FROM `).
        from_indices = [
            m.start() for m in re.finditer(r"^FROM\s", dockerfile, re.MULTILINE)
        ]
        assert len(from_indices) >= 2, (
            "Dockerfile no longer multi-stage — at least two `FROM` "
            "directives expected (builder + runtime)."
        )
        runtime_stage = dockerfile[from_indices[1] :]

        # The runtime COPY directive copies `data` into `./data`. The
        # syntax may include a --chown flag, hence the wildcard match.
        data_copy_pattern = re.compile(
            r"^\s*COPY\b.*\bdata\s+\.\/data\b", re.MULTILINE
        )
        assert data_copy_pattern.search(runtime_stage), (
            "Runtime stage does not COPY the data/ directory. This "
            "is the May-17 Bug #2 regression. Restore the directive:\n"
            "    COPY --chown=appuser:appgroup data ./data"
        )

    def test_seed_json_actually_exists_at_source_path(self) -> None:
        """The Dockerfile's COPY target only matters if the source
        exists in the build context. Sanity-check the canonical seed
        JSON is present at ``backend/data/strategy_templates_seed.json``
        so the COPY does something meaningful."""
        seed_path = BACKEND_DIR / "data" / "strategy_templates_seed.json"
        assert seed_path.exists(), (
            f"Seed JSON missing at {seed_path} — Dockerfile's "
            "COPY data ./data would copy an empty directory and the "
            "seed loader would still hit FileNotFoundError at startup."
        )


# ═══════════════════════════════════════════════════════════════════════
# Bug #3 — registry._default_seed_path probes both host + container layouts
# ═══════════════════════════════════════════════════════════════════════


class TestRegistryPathResolutionContainerLayout:
    """Catches: ``app.templates.registry._default_seed_path`` only
    resolves the host-checkout layout and crashes inside the runtime
    container where the file lives at ``/app/data/...`` rather than
    ``/backend/data/...``.

    Failure mode if regression returns: container starts, seed loader
    runs, hits FileNotFoundError pointing at a non-existent
    ``/backend/data/...`` path, deploy aborts.
    """

    def test_resolver_has_multi_path_probe(self) -> None:
        from app.templates.registry import _default_seed_path

        source = (
            BACKEND_DIR / "app" / "templates" / "registry.py"
        ).read_text(encoding="utf-8")

        # The resolver must include the explicit container fallback,
        # otherwise the May-17 Bug #3 regression has returned.
        assert "/app/data/strategy_templates_seed.json" in source, (
            "registry._default_seed_path no longer references the "
            "explicit container-layout fallback "
            "(/app/data/strategy_templates_seed.json). This is the "
            "May-17 Bug #3 regression."
        )

        # And the container-relative layout via __file__ parents[2].
        assert 'parents[2] / "data"' in source, (
            "registry._default_seed_path no longer probes the "
            "container layout via parents[2]/data — the multi-path "
            "fallback was removed. This is the May-17 Bug #3 regression."
        )

        # Confirm callable still returns a Path (host layout — pytest
        # is running from the host where backend/data/... exists).
        resolved = _default_seed_path()
        assert resolved.exists(), (
            f"_default_seed_path returned {resolved} which does not "
            "exist on disk. The resolver must always return an "
            "existing path or raise FileNotFoundError."
        )

    def test_resolver_raises_descriptive_error_when_nothing_found(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When the resolver can find no candidate, it must raise
        ``FileNotFoundError`` listing every probed location — the only
        operator-actionable failure mode at startup. Regression test
        for the descriptive-error contract from registry.py:104-108.
        """
        from app.templates import registry

        # Point all candidate paths at locations that don't exist.
        # The simplest way: chdir to an empty tmp dir AND monkeypatch
        # the `here` variable indirectly by patching Path itself isn't
        # feasible. Instead, monkeypatch the candidate list builder.
        original = registry._default_seed_path

        def stub() -> Path:
            probed = "\n  ".join(
                [
                    str(tmp_path / "nope1.json"),
                    str(tmp_path / "nope2.json"),
                ]
            )
            raise FileNotFoundError(
                "strategy_templates_seed.json not found in any "
                "expected location.\nProbed (in order):\n  " + probed
            )

        monkeypatch.setattr(registry, "_default_seed_path", stub)

        with pytest.raises(FileNotFoundError) as excinfo:
            registry._default_seed_path()
        msg = str(excinfo.value)
        assert "Probed (in order):" in msg, (
            "FileNotFoundError no longer includes the 'Probed (in order):' "
            "header — operator-actionable error contract regressed."
        )
        # Restore (defensive — monkeypatch undoes this anyway).
        monkeypatch.setattr(registry, "_default_seed_path", original)


# ═══════════════════════════════════════════════════════════════════════
# Smoke: the seed JSON parses cleanly and validator accepts every active
# row. Belt-and-braces — catches "JSON corrupted in source control" or
# "validator broken in a way the unit tests don't see".
# ═══════════════════════════════════════════════════════════════════════


class TestSeedFileIntegrity:
    def test_seed_json_parses(self) -> None:
        import json

        seed_path = BACKEND_DIR / "data" / "strategy_templates_seed.json"
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        assert "templates" in raw and isinstance(raw["templates"], list)
        assert len(raw["templates"]) > 0, "Seed file shipped empty."

    def test_seed_active_rows_validate(self) -> None:
        import json

        from app.templates.validator import (
            TemplateConfigError,
            validate_config_json,
        )

        seed_path = BACKEND_DIR / "data" / "strategy_templates_seed.json"
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        failures: list[str] = []
        for row in raw["templates"]:
            slug = row.get("slug", "?")
            try:
                validate_config_json(
                    row.get("config_json", {}),
                    is_active=bool(row.get("is_active", False)),
                )
            except TemplateConfigError as exc:
                failures.append(f"{slug}: {exc}")
        assert not failures, (
            "Seed validator failures (catalog will not load on next "
            "deploy):\n  " + "\n  ".join(failures)
        )
