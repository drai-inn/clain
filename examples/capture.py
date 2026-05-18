"""Reproducible capture script. Spec 0011 § 3."""
from __future__ import annotations
import json, sys
from pathlib import Path
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from clain import classify as cls
from clain import plan as planmod
from clain.ui.tables import (
    classify_table, classify_footer,
    single_workspace_tree, single_workspace_footer,
    plan_table, plan_footer,
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
single_text = capture(single_workspace_tree(ws, single)) + "\n" + capture(single_workspace_footer(ws, single))

# Plan recreate (single)
plan = planmod.build_recreate_plan(single)
plan = anon_payload(plan)
plan_text = capture(plan_table(plan)) + "\n" + capture(plan_footer(plan, "$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json"))

Path("/tmp/clain-captures/multi.txt").write_text(multi_text, encoding="utf-8")
Path("/tmp/clain-captures/single.txt").write_text(single_text, encoding="utf-8")
Path("/tmp/clain-captures/plan.txt").write_text(plan_text, encoding="utf-8")
print("ok")
