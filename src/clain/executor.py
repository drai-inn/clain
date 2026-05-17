"""Phase-gated execute path.

Per spec 0005 § Phase-gate invariant: while `EXECUTE_ENABLED` is False, this
module must not import or use any process-spawning, network, clipboard, or
filesystem-mutating-against-ROOT facility. A static import-graph test asserts
this. A runtime test asserts that calling `try_execute` raises with a clear
message that names the future spec 00NN as the only way to lift the gate.

To lift the gate, a future spec named "00NN — Lift the dry-run gate" must:
- explicitly authorise the change,
- add the additional safety mechanisms (signed-commit checks, clean-tree
  checks, rollback path, audit-log requirements, etc.),
- and only then flip `EXECUTE_ENABLED` to True in a reviewed PR.

Editing this constant outside of that workflow is a process violation.
"""

from __future__ import annotations

EXECUTE_ENABLED: bool = False

GATE_ERROR_MESSAGE = (
    "Execution is currently disabled by the development-phase gate "
    "(see src/clain/executor.py:EXECUTE_ENABLED). Lifting the gate requires "
    "spec 00NN — Lift the dry-run gate — which must specify rollback, "
    "audit requirements, and additional safety mechanisms. Re-run without "
    "--execute to see the dry-run plan."
)


class ExecuteGateClosed(RuntimeError):
    """Raised when --execute is requested but EXECUTE_ENABLED is False."""


def try_execute(_plan: dict[str, object]) -> None:
    """Entry point for executing a plan. Always raises while the gate is closed."""
    if not EXECUTE_ENABLED:
        raise ExecuteGateClosed(GATE_ERROR_MESSAGE)
    # The True branch is intentionally unimplemented in this spec. Spec 00NN
    # adds it under additional safety mechanisms.
    raise NotImplementedError(
        "EXECUTE_ENABLED is True but no executor body exists. Spec 00NN must "
        "supply the implementation under its named safety regime."
    )
