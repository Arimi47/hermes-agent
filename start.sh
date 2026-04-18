#!/bin/bash
set -e

mkdir -p /data/.hermes/sessions /data/.hermes/skills /data/.hermes/workspace /data/.hermes/pairing

# Merge the git-tracked seed config into the persisted config.yaml. The seed
# wins for everything except model.default and model.provider, which are
# owned at runtime by the admin dashboard and `hermes model` / `codex_login`
# respectively. envsubst fills any ${VAR} placeholders before the merge.
if [ -f /opt/hermes-config/config.seed.yaml ]; then
    envsubst < /opt/hermes-config/config.seed.yaml > /tmp/config.seed.rendered.yaml
    python /app/merge_config.py /tmp/config.seed.rendered.yaml /data/.hermes/config.yaml
fi

# PA bootstrap: seed SOUL.md / USER.md / MEMORY.md only if the target file
# is missing. Runtime edits (via the memory tool or `railway ssh`) always
# win over the seed, matching the config.seed.yaml philosophy.
for f in SOUL.md USER.md MEMORY.md; do
    if [ ! -f "/data/.hermes/$f" ] && [ -f "/opt/hermes-config/$f" ]; then
        cp "/opt/hermes-config/$f" "/data/.hermes/$f"
    fi
done

exec python /app/server.py
