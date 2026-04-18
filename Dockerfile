FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates git gettext-base && \
    rm -rf /var/lib/apt/lists/*

# Install hermes-agent as a package (gives us the `hermes` CLI entry point)
RUN git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /tmp/hermes-agent && \
    cd /tmp/hermes-agent && \
    uv pip install --system --no-cache -e ".[all]" && \
    rm -rf /tmp/hermes-agent/.git

COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache -r /app/requirements.txt

# M-Files MCP server (stdio subprocess spawned by hermes gateway)
RUN git clone --depth 1 https://github.com/Arimi47/mfiles-mcp-server.git /opt/mfiles-mcp-server && \
    uv pip install --system --no-cache -r /opt/mfiles-mcp-server/requirements.txt && \
    rm -rf /opt/mfiles-mcp-server/.git

# M-Files knowledge library (baked; start.sh seeds it into $HERMES_HOME/skills on boot)
RUN git clone --depth 1 https://github.com/Arimi47/mfiles-agent-library.git /opt/mfiles-agent-library && \
    rm -rf /opt/mfiles-agent-library/.git

# SKILL.md that describes the m-files skill to the hermes skill loader
COPY mfiles-skill/SKILL.md /opt/mfiles-agent-library/SKILL.md

RUN mkdir -p /data/.hermes

# Git-tracked config seed + merge script (see hermes-config/config.seed.yaml
# and merge_config.py for the merge semantics).
COPY hermes-config/config.seed.yaml /opt/hermes-config/config.seed.yaml
COPY merge_config.py /app/merge_config.py

COPY server.py /app/server.py
COPY templates/ /app/templates/
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV HOME=/data
ENV HERMES_HOME=/data/.hermes

CMD ["/app/start.sh"]
