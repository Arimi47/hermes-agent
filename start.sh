#!/bin/bash
set -e

# Fork-bomb guard. Incident 2026-05-24: hermes-agent ist komplett ausgefallen
# weil der Railway-Cgroup PIDs geleakt hat (Gateway-Crash-Loop, MCP-Subprozesse
# wurden nicht gereapt). Diese 3 Zeilen sind die Verteidigung dagegen:
#   - ulimit -u 2048: hartes Limit pro user-process tree, damit kein einzelner
#     Spawn-Burst die Cgroup-pids.max sprengt.
#   - set -m + EXIT trap: stellt sicher dass Background-Loops (vault sync,
#     graph ingester, lint report) bei Container-Stop sauber gekillt werden,
#     statt als Zombies hinter Cgroup-Wechseln zurueckzubleiben.
#   - Early-exit Probe: wenn beim Boot schon > 1500 PIDs in /proc liegen,
#     ist die Cgroup bereits geleakt; weiterstarten wuerde nur den Crash-Loop
#     verlaengern. Lieber sauber failen und manuell triagieren.
ulimit -u 2048 || true
set -m
trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

PID_USAGE=$(ls /proc 2>/dev/null | grep -c '^[0-9]' || echo 0)
if [ "$PID_USAGE" -gt 1500 ]; then
    echo "[start] ABORT: $PID_USAGE PIDs already in use - cgroup likely leaked. Manual triage needed (railway redeploy reicht nicht, evtl. fresh rebuild + Support-Ticket)." >&2
    exit 1
fi

mkdir -p /data/.hermes/sessions /data/.hermes/skills /data/.hermes/workspace /data/.hermes/pairing
mkdir -p /data/wedding-invoices

# Register our custom skills under the running Hermes's skill tree. Hermes's
# skill discovery (os.walk in agent/skill_utils.py, rglob in tools/skills_tool.py)
# does NOT follow symlinks - so symlinking /opt/hermes-skills in doesn't
# surface the skill via skills_list / skill_view. We copy the skill as a real
# directory instead. Idempotent: only copy if the SKILL.md is missing or
# older than the one shipped in /opt/hermes-skills (source of truth on every
# container build).
if [ -d /opt/hermes-skills ]; then
    mkdir -p /data/.hermes/skills/productivity
    for skill in /opt/hermes-skills/*/; do
        [ -d "$skill" ] || continue
        name=$(basename "$skill")
        src_skill_md="$skill/SKILL.md"
        dst_dir="/data/.hermes/skills/productivity/$name"
        dst_skill_md="$dst_dir/SKILL.md"
        # If symlink left over from older builds, remove it.
        if [ -L "$dst_dir" ]; then
            rm "$dst_dir"
        fi
        # Copy when destination is missing or older than the source SKILL.md.
        if [ ! -f "$dst_skill_md" ] || [ "$src_skill_md" -nt "$dst_skill_md" ]; then
            rm -rf "$dst_dir"
            cp -r "$skill" "$dst_dir"
            echo "[skills] seeded /data/.hermes/skills/productivity/$name from /opt/hermes-skills/"
        fi
    done
fi

# Merge the git-tracked seed config into the persisted config.yaml. The seed
# wins for everything except model.default and model.provider, which are
# owned at runtime by the admin dashboard and `hermes model` / `codex_login`
# respectively. envsubst fills any ${VAR} placeholders before the merge.
if [ -f /opt/hermes-config/config.seed.yaml ]; then
    envsubst < /opt/hermes-config/config.seed.yaml > /tmp/config.seed.rendered.yaml
    python /app/merge_config.py /tmp/config.seed.rendered.yaml /data/.hermes/config.yaml
fi

# PA bootstrap: SOUL.md vs USER.md/MEMORY.md have different update policies.
#
# SOUL.md is the persona spec - dev-edited via git, never written at runtime.
# Always sync from /opt seed when the seed is newer (mtime check, same
# pattern as the skills block above). Without this, edits to SOUL.md never
# propagated past the very first boot, because the cp-only-if-missing
# guard left /data/.hermes/SOUL.md stuck on whatever was seeded originally.
# Runtime tweaks via `railway ssh` still survive within a build cycle:
# the volume mtime wins until a new build advances /opt's SOUL.md mtime.
if [ -f /opt/hermes-config/SOUL.md ]; then
    if [ ! -f /data/.hermes/SOUL.md ]; then
        cp /opt/hermes-config/SOUL.md /data/.hermes/SOUL.md
        echo "[bootstrap] seeded /data/.hermes/SOUL.md (initial)"
    elif [ /opt/hermes-config/SOUL.md -nt /data/.hermes/SOUL.md ]; then
        cp /opt/hermes-config/SOUL.md /data/.hermes/SOUL.md
        echo "[bootstrap] updated /data/.hermes/SOUL.md from seed (build newer)"
    fi
fi

# USER.md and MEMORY.md are runtime-mutable: the memory tool writes to
# MEMORY.md, and USER.md may be tuned via `railway ssh`. First-write-wins
# so accumulated runtime state is never silently overwritten by a redeploy.
for f in USER.md MEMORY.md; do
    if [ ! -f "/data/.hermes/$f" ] && [ -f "/opt/hermes-config/$f" ]; then
        cp "/opt/hermes-config/$f" "/data/.hermes/$f"
    fi
done

# Obsidian vault mount (2-way). When OBSIDIAN_VAULT_REPO_URL +
# OBSIDIAN_VAULT_GITHUB_TOKEN are set, clone the vault to /data/vault on
# first boot and keep it in sync with GitHub via a background loop:
#   - auto-commit any uncommitted local changes (safety net if the agent
#     forgot the commit ritual from SOUL.md). These fallback commits have
#     timestamp names, not semantic ones; agent-crafted commits remain the
#     primary path.
#   - pull --rebase --autostash keeps local work safe when Ari's Obsidian
#     Git plugin pushes new content.
#   - push origin HEAD ensures Hermes' commits land on GitHub.
# OBSIDIAN_VAULT_PATH is exported so the bundled note-taking/obsidian
# Hermes skill finds the vault.
if [ -n "${OBSIDIAN_VAULT_REPO_URL:-}" ] && [ -n "${OBSIDIAN_VAULT_GITHUB_TOKEN:-}" ]; then
    AUTHED_URL="${OBSIDIAN_VAULT_REPO_URL/https:\/\//https:\/\/x-access-token:${OBSIDIAN_VAULT_GITHUB_TOKEN}@}"
    if [ -d /data/vault/.git ]; then
        # Token-Rotation: bei jedem Boot remote URL refreshen, sonst bleibt
        # der initial-clone-Token in .git/config gepinnt und alle Pushs
        # scheitern still nachdem der Token rotated wurde (Incident 2026-05-24).
        git -C /data/vault remote set-url origin "$AUTHED_URL"
        git -C /data/vault pull --rebase --autostash 2>&1 | sed 's/^/[vault-pull] /' \
            || git -C /data/vault rebase --abort 2>&1 | sed 's/^/[vault-pull] /' \
            || true
    else
        rm -rf /data/vault 2>/dev/null || true
        git clone --depth 50 "$AUTHED_URL" /data/vault 2>&1 | sed 's/^/[vault-clone] /' || true
    fi

    # Configure Hermes' git identity so his own commits are distinguishable
    # from Ari's in the vault's GitHub history.
    if [ -d /data/vault/.git ]; then
        git -C /data/vault config user.name  "Hermes PA"
        git -C /data/vault config user.email "hermes@ari-birnbaum"

        # Background sync loop - 60-second interval. Short interval is
        # chosen because the agent's SOUL Exit-Bedingung (commit before
        # answering Ari) is not reliably honoured by the model; the loop
        # is effectively the real commit mechanism. 60s keeps the
        # observable data-loss window tiny while still leaving semantic
        # room for agent-crafted commits in the cases where it does
        # commit. Errors swallowed so a transient network blip or rebase
        # conflict never crashes the gateway.
        (
            # Heartbeat: vault-sync-status.json wird jede Runde geschrieben.
            # Ohne ihn bricht der Sync nach einem unloesbaren Rebase-Konflikt
            # still fuer immer (jeder Push failt non-fast-forward, Commits
            # stauen sich lokal, niemand merkt es). Admin /api/status liefert
            # die Datei samt Alter aus.
            VAULT_STATUS=/data/.hermes/vault-sync-status.json
            while true; do
                sleep 60
                if [ -n "$(git -C /data/vault status --porcelain 2>/dev/null)" ]; then
                    git -C /data/vault add -A 2>/dev/null || true
                    git -C /data/vault commit -m "Hermes: auto-commit pending changes $(date -u +%Y-%m-%dT%H:%M:%SZ)" >/dev/null 2>&1 || true
                fi
                git -C /data/vault pull --rebase --autostash >/dev/null 2>&1 \
                    || git -C /data/vault rebase --abort >/dev/null 2>&1 || true
                if push_err=$(git -C /data/vault push origin HEAD 2>&1); then
                    printf '{"at":"%s","ok":true,"error":null}\n' \
                        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$VAULT_STATUS.tmp" \
                        && mv "$VAULT_STATUS.tmp" "$VAULT_STATUS"
                else
                    msg=$(printf '%s' "$push_err" | tail -1 | tr -d '"\\' | cut -c1-160)
                    printf '{"at":"%s","ok":false,"error":"push: %s"}\n' \
                        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$msg" > "$VAULT_STATUS.tmp" \
                        && mv "$VAULT_STATUS.tmp" "$VAULT_STATUS"
                    echo "[vault-sync] push failed: $msg" >&2
                fi
            done
        ) &
        echo "[vault] background sync loop started (PID $!)"
    fi
fi
export OBSIDIAN_VAULT_PATH="${OBSIDIAN_VAULT_PATH:-/data/vault}"

# Graph ingester loop - 120-second interval. Walks the vault, upserts
# nodes + edges into Neo4j via MERGE (idempotent). Only runs when the
# Neo4j service connection is configured. 120s keeps Neo4j write load
# low while staying close to real-time from Ari's perspective. Errors
# swallowed so a transient Neo4j blip never crashes the gateway.
if [ -n "${NEO4J_URI:-}" ] && [ -n "${NEO4J_PASSWORD:-}" ]; then
    (
        # Initial delay so the vault has time to clone on first boot.
        # timeout: the loop runs sequentially, so without a watchdog one
        # hung Neo4j query would silently stall ALL future ingest passes
        # (the graph goes stale with no crash and no restart). ingest.py
        # has its own driver/tx deadlines; this is the outer belt.
        sleep 30
        while true; do
            timeout -k 30 600 python /app/graph-ingester/ingest.py 2>&1 | sed 's/^/[graph-ingest] /' || true
            sleep 120
        done
    ) &
    echo "[graph] background ingester loop started (PID $!)"

    # Weekly lint report loop - hourly tick, idempotent. lint_report.py
    # exits 0 (no-op) if the current ISO week's report file already
    # exists in Dashboards/, so this loop effectively writes one
    # snapshot per ISO week (the first tick after the rollover wins).
    # Initial delay > graph-ingester's so the IngestRun singleton and
    # at least one full pass exist before the first lint report runs.
    (
        sleep 240
        while true; do
            timeout -k 30 900 python /app/graph-ingester/lint_report.py 2>&1 | sed 's/^/[lint-report] /' || true
            sleep 3600
        done
    ) &
    echo "[lint] background weekly lint report loop started (PID $!)"
fi

# MS365 Token-Freshness-Probe - stuendlich. Refresh-Tokens sterben nach
# ~90 Tagen Idle; ohne Probe faellt das erst beim naechsten Mail-Tool-Call
# auf. Die Probe refresht still pro Mailbox (haelt Tokens aktiv) und
# schreibt ms365-probe-status.json; Fehlschlaege landen im Gateway-Log.
if [ -n "${MS365_MCP_CLIENT_ID:-}" ]; then
    (
        sleep 420
        while true; do
            timeout -k 30 300 python /app/ms365-mcp/probe.py 2>&1 | sed 's/^/[ms365-probe] /' || true
            sleep 3600
        done
    ) &
    echo "[ms365] hourly token-freshness probe started (PID $!)"
fi

# /data Backup-Loop - stuendlich, verschluesselt, off-volume.
# Blast-Radius ohne Backup: .env (alle API-Keys), Codex auth.json,
# ms365-Tokens (3 Mailboxen mit Device-Code neu einloggen), google-Tokens,
# MEMORY.md (das Gedaechtnis des Agenten), config.yaml, Pairing, SA-Key.
# ALLOWLIST statt Excludes: der erste Versuch mit Excludes hat 322 MB
# erzeugt (node/, node_modules/, bin/ sind reproduzierbare Runtime-
# Installationen) und GitHubs 100-MB-Limit gerissen. Nur Unersetzliches
# wird gesichert - wenige MB.
# Ziel ist der orphan Branch "hermes-backup" im Vault-Sync-Repo (gleicher
# Token, kein zusaetzliches Secret) - force-push, es zaehlt nur der letzte
# Stand.
#
# Restore (im frischen Container, BACKUP_PASSPHRASE gesetzt):
#   git clone --depth 1 --branch hermes-backup <vault-repo-url> /tmp/bk
#   openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE \
#     -in /tmp/bk/hermes-home.tar.gz.enc | tar -xzf - -C /data
if [ -n "${BACKUP_PASSPHRASE:-}" ] && [ -n "${OBSIDIAN_VAULT_REPO_URL:-}" ] && [ -n "${OBSIDIAN_VAULT_GITHUB_TOKEN:-}" ]; then
    (
        sleep 300
        BK_URL="${OBSIDIAN_VAULT_REPO_URL/https:\/\//https:\/\/x-access-token:${OBSIDIAN_VAULT_GITHUB_TOKEN}@}"
        while true; do
            if (
                set -e
                BK=$(mktemp -d)
                trap 'rm -rf "$BK"' EXIT
                # Pfade relativ zu /data, damit ein Restore beide Homes
                # (.hermes + .hermes-estatemate) in einem Zug zurueckspielt.
                ITEMS=""
                for item in \
                    .hermes/.env .hermes/auth.json .hermes/config.yaml \
                    .hermes/MEMORY.md .hermes/USER.md .hermes/SOUL.md \
                    .hermes/google_client_secret.json \
                    .hermes/google_token.json .hermes/google_tokens.json \
                    .hermes/pairing .hermes/memories .hermes/kanban \
                    .hermes/state .hermes/workspace \
                    .hermes-estatemate; do
                    [ -e "/data/$item" ] && ITEMS="$ITEMS $item"
                done
                for f in /data/.hermes/ms365_tokens*.json /data/.hermes/*-status.json; do
                    [ -e "$f" ] && ITEMS="$ITEMS ${f#/data/}"
                done
                # tar exit 1 = "file changed as we read it" (live agent
                # schreibt waehrenddessen) - fuer ein Backup akzeptabel.
                tar -czf "$BK/hermes-home.tar.gz" -C /data \
                    --exclude='.hermes-estatemate/__pycache__' \
                    --exclude='.hermes-estatemate/logs' \
                    $ITEMS || [ $? -eq 1 ]
                openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_PASSPHRASE \
                    -in "$BK/hermes-home.tar.gz" -out "$BK/hermes-home.tar.gz.enc"
                rm "$BK/hermes-home.tar.gz"
                cd "$BK"
                git init -q -b hermes-backup
                git config user.name "Hermes PA"
                git config user.email "hermes@ari-birnbaum"
                git add hermes-home.tar.gz.enc
                git commit -qm "encrypted hermes-home snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ)"
                git push -q --force "$BK_URL" hermes-backup:hermes-backup
            ) > /tmp/backup-last.log 2>&1; then
                echo "[backup] pushed encrypted hermes-home snapshot to hermes-backup branch"
            else
                echo "[backup] FAILED: $(tail -1 /tmp/backup-last.log)" >&2
            fi
            sleep 3600
        done
    ) &
    echo "[backup] hourly encrypted backup loop started (PID $!)"
else
    echo "[backup] disabled (BACKUP_PASSPHRASE and/or vault repo env not set)"
fi

exec python /app/server.py
