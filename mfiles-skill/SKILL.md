---
name: m-files
description: M-Files Immobilien vault operations for Birnbaum Group real-estate portfolio. Use this skill whenever the user asks about properties (Liegenschaft), tenants (Mieter), units (Einheit), vacancies, mortgages, invoices, Vorgaenge (tickets), Angebote (offers), Sanierungen (renovations), portfolio summaries, or refinancing scenarios. Calls mcp_mfiles_* tools and references the 541 property IDs, 31 object types, and 20 workflows documented in the companion .md files in this directory.
license: proprietary
---

# M-Files agent

This skill gives you read and write access to the Birnbaum Group M-Files vault via the `mfiles` MCP server.

## Reference files in this directory

- `MFILES_REST_API_REFERENCE.md` - endpoints and example requests for the Birnbaum vault
- `MFILES_PROPERTY_DEFINITIONS.md` - all 541 property IDs with data types and value lists
- `MFILES_REST_API_OFFICIAL_ENDPOINTS.md` - official M-Files REST API endpoints
- `README.md` - vault overview (object types, workflows, value lists)

Always consult these before constructing a call. Never invent property IDs.

## Tools

All M-Files tools are registered under the `mcp_mfiles_*` prefix. Common ones:

- `mcp_mfiles_list_portfolios`, `mcp_mfiles_get_portfolio_properties`, `mcp_mfiles_portfolio_summary`
- `mcp_mfiles_get_units`, `mcp_mfiles_get_tenants`, `mcp_mfiles_get_vacancy`
- `mcp_mfiles_list_vorgaenge`, `mcp_mfiles_get_vorgang_details`, `mcp_mfiles_get_vorgang_documents`
- `mcp_mfiles_get_mortgages`, `mcp_mfiles_get_metrics`, `mcp_mfiles_get_invoices`
- `mcp_mfiles_simulate_scenario`, `mcp_mfiles_refinancing_scenarios`, `mcp_mfiles_upcoming_refinancing`, `mcp_mfiles_expiring_leases`
- `mcp_mfiles_get_unit_docs`, `mcp_mfiles_get_property_docs`, `mcp_mfiles_download_doc`, `mcp_mfiles_get_unit_history`
- Write ops: `mcp_mfiles_set_vorgang_status`, `mcp_mfiles_set_angebot_status`, `mcp_mfiles_set_sanierung_status`, `mcp_mfiles_add_vorgang_comment`
- Metadata: `mcp_mfiles_discover_object_types`, `mcp_mfiles_search`, `mcp_mfiles_get_view_items`, `mcp_mfiles_compare`

## Rules

- Never invent property IDs. Always resolve them via `MFILES_PROPERTY_DEFINITIONS.md` or a prior `mcp_mfiles_search` call.
- For write operations (`set_*_status`, `add_vorgang_comment`), confirm the target Vorgang ID and the intended new state with the user before calling the tool.
- Default language for comments and user-facing output: German.
- If a tool returns an auth error, surface it verbatim. Do not guess credentials.
