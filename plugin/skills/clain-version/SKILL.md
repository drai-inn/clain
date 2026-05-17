---
name: clain-version
description: Use ONLY when the user explicitly asks for the installed version of the `clain` CLI on this machine — e.g. "what version of clain do I have", "clain --version", "is clain installed". Do not use for any other version question, any other CLI, or any other clain subcommand.
---

Report the installed version of the `clain` CLI by invoking it directly.

Run this Bash command exactly as written, with no added flags or pipes:

```bash
clain --version
```

If the command succeeds, report its output to the user verbatim.

If the command fails (for example `clain: command not found`, or a non-zero exit), report the failure verbatim and tell the user to install `clain` per the project README. Do not attempt to install it, locate an alternative binary, infer the version from any other source, or substitute a value.
