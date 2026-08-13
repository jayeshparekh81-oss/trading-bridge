"""DiskGuard tests: pre-session gate + runtime pause/resume hysteresis.

Free space is a mutable holder so each test drives the exact GB reading.
"""

from __future__ import annotations

from recorder.diskguard import DiskGuard, StartMode


class _Free:
    def __init__(self, gb):
        self.gb = float(gb)

    def __call__(self):
        return self.gb


def _guard(free, *, start=8, core=4, runtime=2, resume=3):
    return DiskGuard(min_free_gb_start=start, min_free_gb_core_only=core,
                     min_free_gb_runtime=runtime, disk_resume_gb=resume,
                     free_gb_fn=free)


def test_plan_start_full_above_start():
    assert _guard(_Free(20)).plan_start() is StartMode.FULL
    assert _guard(_Free(8)).plan_start() is StartMode.FULL  # inclusive


def test_plan_start_core_only_band():
    assert _guard(_Free(6)).plan_start() is StartMode.CORE_ONLY
    assert _guard(_Free(4)).plan_start() is StartMode.CORE_ONLY  # inclusive


def test_plan_start_skip_below_core_only():
    assert _guard(_Free(3.9)).plan_start() is StartMode.SKIP
    assert _guard(_Free(0.5)).plan_start() is StartMode.SKIP


def test_runtime_pause_and_resume_with_hysteresis():
    free = _Free(10)
    g = _guard(free, runtime=2, resume=3)
    assert g.runtime_check() is None and not g.paused
    # drop below runtime floor -> pause
    free.gb = 1.5
    assert g.runtime_check() == "pause"
    assert g.paused
    # recover a little but still below resume -> stay paused (hysteresis)
    free.gb = 2.5
    assert g.runtime_check() is None
    assert g.paused
    # recover above resume -> resume
    free.gb = 3.1
    assert g.runtime_check() == "resume"
    assert not g.paused


def test_runtime_check_idempotent_while_state_unchanged():
    free = _Free(1.0)
    g = _guard(free, runtime=2, resume=3)
    assert g.runtime_check() == "pause"
    assert g.runtime_check() is None   # already paused, no repeat transition
    assert g.runtime_check() is None


def test_resume_threshold_raised_when_not_above_runtime():
    # misconfigured resume <= runtime is auto-corrected to avoid flapping
    g = _guard(_Free(10), runtime=2, resume=2)
    assert g.resume_gb > g.runtime_gb
