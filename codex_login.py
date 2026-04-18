"""Trigger OpenAI Codex OAuth device-code flow without going through the
interactive `hermes model` curses picker.

Invoke from inside the Hermes container:

    python /app/codex_login.py

The flow uses stdin prompts and prints a device-code URL, so it works cleanly
over Railway SSH on Windows where curses navigation is broken.
"""

import argparse

from hermes_cli.auth import _login_openai_codex, PROVIDER_REGISTRY


if __name__ == "__main__":
    _login_openai_codex(argparse.Namespace(), PROVIDER_REGISTRY["openai-codex"])
