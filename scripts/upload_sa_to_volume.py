"""One-shot: upload the estatemate SA JSON to the Railway volume via railway ssh.

Encodes the SA file as base64 locally, then runs `railway ssh` with a
remote python -c that decodes and writes the file. Avoids manual paste,
so no character mangling.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

LOCAL_JSON = Path(r"C:\Users\aribi\OneDrive\Desktop\estatemate-claude-code-c9e10528c6f5.json")
REMOTE_PATH = "/data/.hermes-estatemate/google_service_account.json"


def main() -> int:
    if not LOCAL_JSON.exists():
        print(f"Local SA JSON not found: {LOCAL_JSON}", file=sys.stderr)
        return 1
    data_b64 = base64.b64encode(LOCAL_JSON.read_bytes()).decode()

    remote_py = (
        "import base64,sys,os,hashlib,json;"
        "raw=base64.b64decode(sys.argv[1]);"
        f"open({REMOTE_PATH!r},'wb').write(raw);"
        "d=json.loads(raw);"
        f"print('wrote',{REMOTE_PATH!r},'sha256',hashlib.sha256(raw).hexdigest()[:16],"
        "'client_email',d['client_email'])"
    )

    cmd = [
        "railway", "ssh", "--service", "hermes-agent",
        f"python -c \"{remote_py}\" {data_b64}",
    ]
    env = os.environ.copy()
    env["MSYS_NO_PATHCONV"] = "1"
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    local_sha = __import__("hashlib").sha256(LOCAL_JSON.read_bytes()).hexdigest()[:16]
    print(f"local  sha256 {local_sha}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
