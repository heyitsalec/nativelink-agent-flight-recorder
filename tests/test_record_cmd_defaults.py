"""Regression: the default run group must be collision-free (fleet identity).

A date-only default (`record-YYYY-MM-DD`) collides across hosts, repos, and
same-day runs; fleet consumers key evidence by run group, so the default must
carry entropy. Found by the validation-layer control plane (N1.4).
"""

from __future__ import annotations

import re

from nlfr.commands.record_cmd import _default_run_group


def test_default_run_group_is_dated_and_unique() -> None:
    a, b = _default_run_group(), _default_run_group()
    assert re.fullmatch(r"record-\d{4}-\d{2}-\d{2}-[0-9a-f]{8}", a), a
    assert a != b, "two same-day defaults must not collide"
