"""Reproducible capture script. Spec 0011 § 3 + spec 0012.

Renders the same outputs the CLI produces against anonymised fixture trees,
then exports plain text (no ANSI) suitable for fenced README blocks. Captures:
- examples/capture-classify-tree.txt
- examples/capture-classify-here.txt
- examples/capture-plan-recreate-here.txt          (default Panel render, spec 0012)
- examples/capture-plan-recreate-here-table.txt    (--table render, spec 0012)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from clain import classify as cls  # noqa: E402
from clain import plan as planmod  # noqa: E402
from clain.ui.tables import (  # noqa: E402
    classify_here_view,
    classify_tree_view,
    plan_table_flat,
    plan_view,
)

WIDTH = 78


def capture(renderable) -> str:
    buf = Console(record=True, width=WIDTH, force_terminal=False)
    buf.print(renderable)
    return buf.export_text(clear=False)


def anon_payload(payload):
    """Rewrite paths inside the JSON before rendering so wrapping can't break it."""
    s = json.dumps(payload)
    s = s.replace("/tmp/clain-captures/single/example-workspace", "~/dev/example-workspace")
    s = s.replace("/tmp/clain-captures/dev", "~/dev")
    s = s.replace("/private", "")
    return json.loads(s)


# Multi-workspace classify (spec 0013: tree view, legend off by default)
multi = cls.run_classify(Path("/tmp/clain-captures/dev"), None)
multi = anon_payload(multi)
multi_text = capture(classify_tree_view(multi, legend=False))

# Single-workspace classify (spec 0013: here view, legend on by default)
single = cls.run_classify(Path("/tmp/clain-captures/single/example-workspace"), None, single=True)
single = anon_payload(single)
ws = single["workspaces"][0]
single_text = capture(classify_here_view(ws, single, legend=True))

# Plan recreate (single) — default panel render with spec 0013 wrapping (legend on)
plan = planmod.build_recreate_plan(single)
plan = anon_payload(plan)
plan_panel_text = capture(
    plan_view(
        plan,
        saved_path="$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json",
        legend=True,
    )
)

# Plan recreate (single) — --table render (spec 0012/0013, legend off)
plan_table_text = capture(
    plan_view(
        plan,
        saved_path="$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json",
        legend=False,
        flat_table=True,
    )
)

Path("/tmp/clain-captures/multi.txt").write_text(multi_text, encoding="utf-8")
Path("/tmp/clain-captures/single.txt").write_text(single_text, encoding="utf-8")
Path("/tmp/clain-captures/plan.txt").write_text(plan_panel_text, encoding="utf-8")
Path("/tmp/clain-captures/plan-table.txt").write_text(plan_table_text, encoding="utf-8")
# `plan_table_flat` directly — kept for reference even though plan_view wraps it.
_ = plan_table_flat  # used to keep the import; spec-0012 snapshot test exercises it.
print("ok")
