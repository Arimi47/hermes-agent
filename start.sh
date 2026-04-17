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

exec python /app/server.py
