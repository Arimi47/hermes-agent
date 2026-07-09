import io
import re
from dataclasses import dataclass

try:
    import PyPDF2
except Exception:  # pragma: no cover
    PyPDF2 = None


@dataclass
class GrepHit:
    line_no: int
    text: str
    before: list[str]
    after: list[str]


def extract_text(content: bytes, extension: str, filename: str = "document") -> str:
    ext = (extension or "").lower().lstrip(".")
    if ext == "pdf":
        if PyPDF2 is None:
            return "[PDF - PyPDF2 not installed]"
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return "\n\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            return f"[PDF extraction failed: {e}]"
    if ext in {"txt", "csv", "xml", "json", "html", "htm"}:
        for enc in ("utf-8", "latin-1"):
            try:
                return content.decode(enc)
            except UnicodeDecodeError:
                pass
        return "[Text decode failed]"
    if ext == "msg":
        try:
            import extract_msg
            msg = extract_msg.openMsg(io.BytesIO(content))
            parts = []
            for label, val in (("Von", msg.sender), ("An", msg.to), ("Cc", msg.cc), ("Datum", msg.date), ("Betreff", msg.subject)):
                if val:
                    parts.append(f"{label}: {val}")
            parts.append("")
            parts.append((msg.body or "").strip())
            return "\n".join(parts)
        except ImportError:
            return "[MSG - extract-msg nicht installiert]"
        except Exception as e:
            return f"[MSG extraction failed: {e}]"
    return f"[Binary file: {filename}.{ext}, {len(content)} bytes]"


def grep_context(text: str, pattern: str, context: int = 3) -> list[GrepHit]:
    rx = re.compile(pattern, re.IGNORECASE | re.UNICODE)
    lines = text.splitlines()
    hits: list[GrepHit] = []
    for idx, line in enumerate(lines):
        if rx.search(line):
            before = lines[max(0, idx-context):idx]
            after = lines[idx+1:idx+1+context]
            hits.append(GrepHit(idx + 1, line, before, after))
    return hits


def render_hits(hits: list[GrepHit], max_hits: int = 20) -> str:
    if not hits:
        return "Keine Treffer."
    out = []
    for hit in hits[:max_hits]:
        out.append(f"Treffer Zeile {hit.line_no}:")
        start = hit.line_no - len(hit.before)
        for off, line in enumerate(hit.before, start):
            out.append(f"  {off}: {line}")
        out.append(f"> {hit.line_no}: {hit.text}")
        for off, line in enumerate(hit.after, hit.line_no + 1):
            out.append(f"  {off}: {line}")
        out.append("")
    if len(hits) > max_hits:
        out.append(f"... {len(hits) - max_hits} weitere Treffer nicht angezeigt")
    return "\n".join(out).rstrip()
