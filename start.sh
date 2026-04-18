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

exec python /app/server.py
