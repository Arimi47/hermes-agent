"""
In-place patch for upstream hermes-agent run_agent.py.

Adds `exc_info=True` to two logger calls so non-retryable client errors
surface their full Python traceback in the gateway log deque (visible
via /api/logs). Without this, errors like `'NoneType' object is not
iterable` give no indication of which line in run_agent.py (~4500 lines
of try-block) actually raised, leaving ops with no way to file a
targeted upstream bug.

Idempotent: safe to re-run on an already-patched file. Validates that
the expected source markers exist and aborts loudly otherwise so a
silent upstream rename does not make this a no-op.
"""
import sys
from pathlib import Path

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/hermes-agent/run_agent.py")

if not TARGET.exists():
    print(f"[patch] target not found: {TARGET}", file=sys.stderr)
    sys.exit(1)

# Normalize line endings so a CRLF-checked-out patch file still matches
# the LF-source from upstream's GitHub tarball.
src = TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")
orig = src

# Patch 1: the single-line `logging.error` for non-retryable client errors.
NEEDLE_1 = 'logging.error(f"{self.log_prefix}Non-retryable client error: {api_error}")'
REPL_1 = 'logging.error(f"{self.log_prefix}Non-retryable client error: {api_error}", exc_info=True)'

# Patch 2: the multiline `logger.warning("API call failed (attempt ...)` block.
# We insert exc_info=True before the closing paren on the line that has
# `_error_summary,`. Built via "\n".join to avoid CRLF-vs-LF mismatches if
# this patch file is checked out on Windows but applied in a Linux build.
NEEDLE_2 = "\n".join([
    'logger.warning(',
    '                        "API call failed (attempt %s/%s) error_type=%s %s summary=%s",',
    '                        retry_count,',
    '                        max_retries,',
    '                        error_type,',
    '                        self._client_log_context(),',
    '                        _error_summary,',
    '                    )',
])
REPL_2 = "\n".join([
    'logger.warning(',
    '                        "API call failed (attempt %s/%s) error_type=%s %s summary=%s",',
    '                        retry_count,',
    '                        max_retries,',
    '                        error_type,',
    '                        self._client_log_context(),',
    '                        _error_summary,',
    '                        exc_info=True,',
    '                    )',
])

def patch(needle: str, repl: str, label: str, source: str) -> str:
    if repl in source:
        print(f"[patch] {label}: already applied")
        return source
    if needle not in source:
        print(f"[patch] {label}: needle not found in {TARGET}", file=sys.stderr)
        sys.exit(2)
    print(f"[patch] {label}: applying")
    return source.replace(needle, repl)

src = patch(NEEDLE_1, REPL_1, "non-retryable-error", src)
src = patch(NEEDLE_2, REPL_2, "api-call-failed-warning", src)

if src == orig:
    print("[patch] no changes (all patches already applied)")
else:
    TARGET.write_text(src, encoding="utf-8")
    print(f"[patch] wrote {TARGET}")
