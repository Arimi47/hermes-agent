import os
import re
from pathlib import Path

SECRET_KEYS = ("TOKEN", "PASSWORD", "PASS", "SECRET", "COOKIE", "SESSION", "AUTH", "CONNECTION")

_SECRET_PATTERNS = [
    re.compile(r"(?i)(token|password|passwd|secret|cookie|session(id)?|authorization|connection[_ -]?string)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)(https?://)([^\s/@:]+):([^\s/@]+)@"),
    re.compile(r"(?i)X-Authentication\s*[:=]\s*([^\s,;]+)"),
]


def redact(value: object) -> str:
    text = str(value)
    for pat in _SECRET_PATTERNS:
        if pat.pattern.startswith("(?i)(https?://)"):
            text = pat.sub(r"\1[REDACTED]@", text)
        elif "X-Authentication" in pat.pattern:
            text = pat.sub("X-Authentication=[REDACTED]", text)
        else:
            text = pat.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    for key, val in os.environ.items():
        if any(marker in key.upper() for marker in SECRET_KEYS) and val and len(val) >= 8:
            text = text.replace(val, "[REDACTED]")
    return text


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def mfiles_mcp_path() -> Path:
    env = os.environ.get("MFILES_MCP_PATH")
    if env:
        return Path(env)
    return repo_root().parent / "mfiles-mcp"
