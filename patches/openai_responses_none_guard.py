"""
None-guard patch for openai SDK's parse_response.

Background: When the ChatGPT/Codex backend (chatgpt.com/backend-api/codex)
streams a Responses-API SSE event where `response.output` is null,
openai/lib/_parsing/_responses.py::parse_response crashes with
`TypeError: 'NoneType' object is not iterable` on the bare
`for output in response.output:` line.

Hermes classifies any TypeError raised inside the API-call try-block as
is_local_validation_error -> is_client_error -> "Primary model failed"
-> switch to fallback gpt-5.4 (which also breaks our graph MCP tooling
because the encrypted-reasoning Codex path is gone). Net effect for the
user: every Codex stream that hits this code path forces a fallback.

This patch turns the bare iteration into `for output in (response.output
or []):` so a null output is treated as an empty event instead of a
crash. The accumulator's subsequent state-machine handles empty events
correctly; only the parser was missing the guard.

Idempotent. Fails loudly if the upstream source layout changes so a
silent rename does not leave us unprotected. Run order: must execute
AFTER `uv pip install` so the site-packages tree exists.
"""
import sys
from pathlib import Path

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "/usr/local/lib/python3.12/site-packages/openai/lib/_parsing/_responses.py"
)

if not TARGET.exists():
    print(f"[openai-patch] target not found: {TARGET}", file=sys.stderr)
    sys.exit(1)

# Normalize line endings in case the patch script itself was CRLF.
src = TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")

NEEDLE = "    for output in response.output:\n"
REPL = "    for output in (response.output or []):  # patched: codex backend can send null output\n"

if REPL in src:
    print("[openai-patch] already applied")
    sys.exit(0)

if NEEDLE not in src:
    # Diagnostic: list lines containing "response.output" so a future
    # SDK rename is debuggable without re-reading the whole file.
    hits = [
        f"  L{i+1}: {line.rstrip()}"
        for i, line in enumerate(src.splitlines())
        if "response.output" in line
    ]
    print(
        "[openai-patch] needle not found in " + str(TARGET)
        + "\n  expected: " + repr(NEEDLE.strip())
        + "\n  candidates:\n" + ("\n".join(hits) if hits else "  (none)"),
        file=sys.stderr,
    )
    sys.exit(2)

TARGET.write_text(src.replace(NEEDLE, REPL), encoding="utf-8")
print(f"[openai-patch] wrote {TARGET}")
