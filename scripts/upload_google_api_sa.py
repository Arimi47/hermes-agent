"""Upload the SA-backed google_api wrapper to /data/.hermes-estatemate/."""
from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

LOCAL = Path(__file__).with_name("google_api_sa.py")
REMOTE = "/data/.hermes-estatemate/google_api.py"
SUBJECT_REMOTE = "/data/.hermes-estatemate/google_subject"
SUBJECT_VALUE = "ari@estatemate.io"


def main() -> int:
    data_b64 = base64.b64encode(LOCAL.read_bytes()).decode()
    subj_b64 = base64.b64encode(SUBJECT_VALUE.encode() + b"\n").decode()
    remote_py = (
        "import base64,sys,hashlib;"
        f"raw=base64.b64decode(sys.argv[1]);open({REMOTE!r},'wb').write(raw);"
        f"open({SUBJECT_REMOTE!r},'wb').write(base64.b64decode(sys.argv[2]));"
        f"print('wrote',{REMOTE!r},'sha256',hashlib.sha256(raw).hexdigest()[:16]);"
        f"print('wrote',{SUBJECT_REMOTE!r},'value',{SUBJECT_VALUE!r})"
    )
    cmd = [
        "railway", "ssh", "--service", "hermes-agent",
        f"python -c \"{remote_py}\" {data_b64} {subj_b64}",
    ]
    env = os.environ.copy()
    env["MSYS_NO_PATHCONV"] = "1"
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr)
    local_sha = __import__("hashlib").sha256(LOCAL.read_bytes()).hexdigest()[:16]
    print(f"local  sha256 {local_sha}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
