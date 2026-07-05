import importlib.util
import sys
from typing import Any

from .config import mfiles_mcp_path

_CLIENT_CLASS = None


def _load_mfiles_client() -> Any:
    global _CLIENT_CLASS
    if _CLIENT_CLASS is not None:
        return _CLIENT_CLASS
    mcp_dir = mfiles_mcp_path()
    client_file = mcp_dir / "mfiles_client.py"
    if not client_file.exists():
        raise RuntimeError(f"mfiles_client.py not found at {client_file}. Set MFILES_MCP_PATH.")
    if str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))
    spec = importlib.util.spec_from_file_location("mfiles_mcp_client", client_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {client_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CLIENT_CLASS = module.MFilesClient
    return _CLIENT_CLASS


def create_client():
    return _load_mfiles_client()()
