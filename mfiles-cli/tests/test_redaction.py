from mfiles_cli.config import redact


def test_redacts_key_value_secrets():
    out = redact("token=abc123456789 password:secretvalue")
    assert "abc123456789" not in out
    assert "secretvalue" not in out
    assert "[REDACTED]" in out


def test_redacts_url_credentials():
    out = redact("https://user:pass@example.com/path")
    assert "user:pass" not in out
    assert "[REDACTED]" in out
