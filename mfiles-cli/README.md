# M-Files CLI

Tokenarme CLI fuer Claude Code und Menschen. Die CLI liegt bewusst getrennt vom MCP-Frontend, nutzt aber den bestehenden `mfiles-mcp/mfiles_client.py` REST-Client wieder.

## Installation aus dem Repo

```bash
cd mfiles-cli
python -m pip install -e .
```

## Beispiele

```bash
mfiles --help
mfiles search "Indian Mango"
mfiles units --property-id 103
mfiles docs --unit-id 5814
mfiles contract --unit-id 5814 --grep "Index|Verbraucherpreis|Nettokaltmiete" --context 8
mfiles contract --unit-id 5814 --full --out /tmp/5814_contract.txt
mfiles rent-check --unit-id 5814
mfiles rent-roll --property-id 103 --xlsx /tmp/zb15.xlsx
```

## Auth

Die CLI nutzt dieselbe Konfiguration wie der M-Files-MCP-Server:

- `MFILES_SERVER_URL`
- `MFILES_VAULT_GUID`
- `MFILES_USERNAME`
- `MFILES_PASSWORD`

Alternativ greift der bestehende Client auf `MFILES_CONFIG_PATH` bzw. den Legacy-Config-Pfad zurueck. Secrets werden in CLI-Ausgaben redacted.
