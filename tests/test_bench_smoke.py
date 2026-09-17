"""Smoke tests for the bench/ demo scripts - not checking exact numbers,
just that they still run without raising, so a refactor elsewhere can't
silently break a script nobody runs except manually before an interview.
"""

import io
import runpy
from contextlib import redirect_stdout


def test_cascade_cost_demo_runs_without_raising() -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        runpy.run_path("bench/cascade_cost_demo.py", run_name="__main__")

    assert "Cascade saves vs always-expensive" in output.getvalue()