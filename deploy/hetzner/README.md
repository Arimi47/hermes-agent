# Hermes auf Hetzner — Betrieb & Deploy

Server: `ssh hetzner` (46.224.223.248). Stack liegt unter `/opt/hermes/`:

```
/opt/hermes/
├── docker-compose.yml   (Kopie von deploy/hetzner/docker-compose.yml)
├── .env                 (Secrets, chmod 600 — NICHT in git)
├── src/                 (dieses Repo)
└── data/
    ├── hermes/          (= /data im Agent: HERMES_HOME, Vault-Clone, Sessions)
    └── neo4j/           (Neo4j-Daten — bei Verlust egal, Ingester baut neu)
```

## Deploy eines Updates (KEIN Push-to-Deploy mehr!)

Railway deployte automatisch bei git push — hier ist Deploy ein bewusster Schritt:

```bash
# vom Mac aus (Repo-Root):
rsync -az --delete --exclude .git --exclude node_modules --exclude mission-control/node_modules \
  ./ hetzner:/opt/hermes/src/
ssh hetzner 'cd /opt/hermes && docker compose build && docker compose up -d'
```

## Status & Logs

```bash
ssh hetzner 'cd /opt/hermes && docker compose ps'
ssh hetzner 'cd /opt/hermes && docker compose logs -f hermes-agent'
ssh hetzner 'cat /opt/hermes/data/hermes/.hermes/graph-ingest-status.json'
```

## Restore aus dem GitHub-Backup

Der stuendliche Backup-Loop (start.sh) pusht ein verschluesseltes Archiv
auf den Branch `hermes-backup` des Vault-Sync-Repos. Restore:

```bash
git clone --depth 1 --branch hermes-backup <vault-repo-url-mit-token> /tmp/bk
openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE \
  -in /tmp/bk/hermes-home.tar.gz.enc | tar -xzf - -C /opt/hermes/data/hermes
```

BACKUP_PASSPHRASE steht in `/opt/hermes/.env` (und in Aris Passwort-Manager).

## Phase-A-Zustand (bis zum Cutover)

Solange Railway noch produktiv ist:
- `data/hermes/.hermes/auth.json.staged` — bewusst NICHT `auth.json`, damit
  der Gateway hier nicht startet (zwei Gateways = Telegram-409-Krieg).
- `BACKUP_PASSPHRASE` fehlt bewusst in `.env` (kein Branch-Force-Push-Duell).
- `hermes-agent`-Container gestoppt; nur `neo4j` + `mission-control` laufen.

## Cutover (Railway -> Hetzner scharf schalten)

1. Frisches Backup + Sessions-Delta von Railway nachziehen.
2. Railway-Gateway stoppen (Admin-Dashboard), `railway down --service hermes-agent`.
3. Hier: `mv data/hermes/.hermes/auth.json.staged data/hermes/.hermes/auth.json`,
   `BACKUP_PASSPHRASE=...` in `.env` ergaenzen, `docker compose up -d`.
4. Telegram-Test, Loops im Log pruefen, Backup-Push verifizieren.

## Rollback

`docker compose stop hermes-agent` hier, auf Railway das letzte
Agent-Deployment redeployen (Projekt + Volumes bleiben 1 Woche stehen).

## Caddy (Host, nicht Docker)

`/etc/caddy/Caddyfile`:

```
hermes.birnbaum-group.com  { reverse_proxy 127.0.0.1:8200 }
mission.birnbaum-group.com { reverse_proxy 127.0.0.1:8201 }
```

Nach Aenderung: `systemctl reload caddy`. DNS laeuft ueber die bestehende
Cloudflare-Wildcard `*.birnbaum-group.com` (DNS-only) — nichts zu tun.
