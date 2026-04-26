#!/bin/bash
set -e

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
            while true; do
                sleep 60
                if [ -n "$(git -C /data/vault status --porcelain 2>/dev/null)" ]; then
                    git -C /data/vault add -A 2>/dev/null || true
                    git -C /data/vault commit -m "Hermes: auto-commit pending changes $(date -u +%Y-%m-%dT%H:%M:%SZ)" >/dev/null 2>&1 || true
                fi
                git -C /data/vault pull --rebase --autostash >/dev/null 2>&1 \
                    || git -C /data/vault rebase --abort >/dev/null 2>&1 || true
                git -C /data/vault push origin HEAD >/dev/null 2>&1 || true
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
        sleep 30
        while true; do
            python /app/graph-ingester/ingest.py 2>&1 | sed 's/^/[graph-ingest] /' || true
            sleep 120
        done
    ) &
    echo "[graph] background ingester loop started (PID $!)"
fi

exec python /app/server.py
