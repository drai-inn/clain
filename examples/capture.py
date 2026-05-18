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
    classify_footer,
    classify_table,
    plan_footer,
    plan_header,
    plan_panels,
    plan_table_flat,
    single_workspace_footer,
    single_workspace_tree,
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


# Multi-workspace classify
multi = cls.run_classify(Path("/tmp/clain-captures/dev"), None)
multi = anon_payload(multi)
multi_text = capture(classify_table(multi)) + "\n" + capture(classify_footer(multi))

# Single-workspace classify
single = cls.run_classify(Path("/tmp/clain-captures/single/example-workspace"), None, single=True)
single = anon_payload(single)
ws = single["workspaces"][0]
single_text = capture(single_workspace_tree(ws, single)) + "\n" + capture(
    single_workspace_footer(ws, single)
)

# Plan recreate (single) — default Panel render (spec 0012)
plan = planmod.build_recreate_plan(single)
plan = anon_payload(plan)
plan_panel_text = capture(plan_header(plan)) + "\n"
for panel in plan_panels(plan):
    plan_panel_text += capture(panel)
plan_panel_text += "\n" + capture(
    plan_footer(plan, "$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json")
)

# Plan recreate (single) — --table render (spec 0012, backwards-compat)
plan_table_text = capture(plan_table_flat(plan)) + "\n" + capture(
    plan_footer(plan, "$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json")
)

Path("/tmp/clain-captures/multi.txt").write_text(multi_text, encoding="utf-8")
Path("/tmp/clain-captures/single.txt").write_text(single_text, encoding="utf-8")
Path("/tmp/clain-captures/plan.txt").write_text(plan_panel_text, encoding="utf-8")
Path("/tmp/clain-captures/plan-table.txt").write_text(plan_table_text, encoding="utf-8")
print("ok")
