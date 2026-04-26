# Hermes Mission Control

Next.js 15 cockpit over the Hermes knowledge graph (Neo4j) and the
Obsidian vault. Separate Railway service, shares the private network
with `hermes-agent` and `hermes-graph`.

## Env

- `NEO4J_URI` (e.g. `bolt://hermes-graph.railway.internal:7687`)
- `NEO4J_USER` (default `neo4j`)
- `NEO4J_PASSWORD`

## Local dev

```bash
cd mission-control
npm install
NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=... npm run dev
```

## Phased buildout

- Slice A: stats panel (node/edge counts, label breakdown) - this PR.
- Slice B: force-directed graph (`reagraph`, 2D + 3D layouts) of whole vault.
- Slice C: click node → detail panel (props + neighbours).
- Slice D: activity feed tailing obsidian-vault-sync git log.
- Slice E: task board reading Tasks/ folder + YAML frontmatter.
