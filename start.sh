#!/bin/bash
set -e

mkdir -p /data/.hermes/sessions /data/.hermes/skills /data/.hermes/workspace /data/.hermes/pairing

# Seed the m-files skill into HERMES_HOME/skills on every boot so updates to
# the baked mfiles-agent-library (pulled into /opt at image build) propagate
# on redeploy. /data is a persisted volume, so we overwrite rather than only
# copying on first boot.
if [ -d /opt/mfiles-agent-library ]; then
    mkdir -p /data/.hermes/skills/m-files
    cp -f /opt/mfiles-agent-library/*.md /data/.hermes/skills/m-files/
fi

# Merge the git-tracked seed config into the persisted config.yaml. The seed
# wins for everything except model.default and model.provider, which are
# owned at runtime by the admin dashboard and `hermes model` respectively.
# envsubst fills ${MFILES_*} placeholders from Railway env vars before merge.
if [ -f /opt/hermes-config/config.seed.yaml ]; then
    envsubst < /opt/hermes-config/config.seed.yaml > /tmp/config.seed.rendered.yaml
    python /app/merge_config.py /tmp/config.seed.rendered.yaml /data/.hermes/config.yaml
fi

exec python /app/server.py
