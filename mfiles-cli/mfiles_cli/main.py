import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from .client import create_client
from .config import redact
from .extract import extract_text, grep_context, render_hits
from .formatters import money, print_json, table
from .rent_check import rent_check
from .xlsx import write_rent_roll


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mfiles", description="Token-efficient M-Files CLI")
    p.add_argument("--json", action="store_true", help="Emit JSON where supported")
    p.add_argument("--debug", action="store_true", help="Show redacted debug errors")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("search", help="Search properties/units by text")
    s.add_argument("query")
    s = sub.add_parser("units", help="List units for a property")
    s.add_argument("--property-id", type=int, required=True)
    s = sub.add_parser("docs", help="List contract documents for a unit")
    s.add_argument("--unit-id", type=int, required=True)
    s = sub.add_parser("contract", help="Extract contract text for a unit")
    s.add_argument("--unit-id", type=int, required=True)
    s.add_argument("--latest", action="store_true", default=True)
    s.add_argument("--grep")
    s.add_argument("--context", type=int, default=3)
    s.add_argument("--full", action="store_true")
    s.add_argument("--out")
    s = sub.add_parser("rent-check", help="Check M-Files rent against contract/evidence")
    s.add_argument("--unit-id", type=int, required=True)
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("rent-roll", help="Create rent-roll XLSX for a property")
    s.add_argument("--property-id", type=int, required=True)
    s.add_argument("--xlsx", required=True)
    return p


async def _unit_details(client, unit_id: int) -> dict[str, Any]:
    meth = getattr(client, "_get_unit_details", None)
    if meth is None:
        return {"id": unit_id}
    data = await meth(unit_id)
    return data or {"id": unit_id}


async def cmd_search(args):
    client = create_client()
    try:
        props = await client.get_all_properties()
        q = args.query.lower()
        rows = []
        for prop in props:
            if q in str(prop.get("name", "")).lower() or q in str(prop.get("id", "")):
                rows.append({"id": prop.get("id"), "type": "Property", "name": prop.get("name", ""), "extra": ""})
        if args.json:
            print_json(rows)
        else:
            print(table([[r["id"], r["type"], r["name"], r["extra"]] for r in rows[:50]], ["ID", "Typ", "Name", "Zusatz"]))
    finally:
        await client.close()


async def cmd_units(args):
    client = create_client()
    try:
        units = await client.get_property_units(args.property_id)
        if args.json:
            print_json(units)
        else:
            rows = []
            for u in units:
                rows.append([
                    u.get("id", ""),
                    u.get("unit_name") or u.get("unit_number") or u.get("bezeichnung") or "",
                    u.get("tenant", ""),
                    money(u.get("net_rent")),
                    u.get("workflow_status_label") or u.get("status", ""),
                ])
            print(table(rows, ["Unit ID", "Einheit", "Mieter", "M-Files NKM", "Vermietung/Status"]))
    finally:
        await client.close()


async def cmd_docs(args):
    client = create_client()
    try:
        docs = await client.get_unit_contract_documents(args.unit_id)
        if args.json:
            print_json(docs)
        else:
            rows = [[d.get("object_id", ""), d.get("file_id", ""), d.get("extension", ""), d.get("name", ""), d.get("contract_name", ""), d.get("size_bytes", "")] for d in docs]
            print(table(rows, ["object_id", "file_id", "extension", "name", "contract_name", "size"]))
    finally:
        await client.close()


async def _contract_text(client, unit_id: int) -> tuple[str, list[dict]]:
    docs = await client.get_unit_contract_documents(unit_id)
    texts = []
    used = []
    for d in docs:
        ext = (d.get("extension") or "").lower()
        if ext not in {"pdf", "txt", "html", "htm", "msg"}:
            continue
        content, _info = await client.download_file(int(d.get("object_type", 0)), int(d.get("object_id", 0)), int(d.get("file_id", 0)))
        if content is None:
            continue
        text = extract_text(content, ext, d.get("name", "document"))
        used.append(d)
        texts.append(f"\n\n===== {d.get('contract_name') or ''} / {d.get('name')} ({ext}) =====\n{text}")
    return "".join(texts).strip(), used


async def cmd_contract(args):
    client = create_client()
    try:
        text, _docs = await _contract_text(client, args.unit_id)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        elif args.full:
            print(text)
        elif text:
            tmp = Path(f"/tmp/mfiles_contract_{args.unit_id}.txt")
            tmp.write_text(text, encoding="utf-8")
            print(f"Volltext geschrieben: {tmp}")
        else:
            print("Kein Vertragstext extrahiert.")
        if args.grep and text:
            print(render_hits(grep_context(text, args.grep, args.context)))
        if args.out:
            print(f"Volltext geschrieben: {args.out}")
    finally:
        await client.close()


async def cmd_rent_check(args):
    client = create_client()
    try:
        unit = await _unit_details(client, args.unit_id)
        text, docs = await _contract_text(client, args.unit_id)
        source = "; ".join(filter(None, [d.get("contract_name") or d.get("name") for d in docs[:3]]))
        result = rent_check(unit, text, source)
        if getattr(args, "json", False):
            print_json(result)
        else:
            print(f"Unit {result.get('unit_id')} | {result.get('tenant') or '-'} | {result.get('unit') or '-'}")
            print()
            print(f"M-Files NKM aktuell: {money(result.get('mfiles_net_rent'))}")
            print(f"Miete laut Vertrag/letztem Beleg: {money(result.get('contract_or_evidence_rent'))}")
            print(f"Delta: {money(result.get('delta'))}")
            print(f"Stimmt M-Files mit Vertrag/Beleg? {result.get('status')}")
            print(f"Letzte Erhöhung / Basisdatum: {result.get('basis_date') or '-'}")
            print(f"Was ist das Datum? {result.get('date_kind') or '-'}")
            print(f"Quelle: {result.get('source') or '-'}")
            print()
            print("Klartext:")
            print(result.get("klartext") or "")
    finally:
        await client.close()


async def cmd_rent_roll(args):
    client = create_client()
    try:
        props = await client.get_all_properties()
        prop_name = next((p.get("name", "") for p in props if int(p.get("id", 0)) == args.property_id), str(args.property_id))
        units = await client.get_property_units(args.property_id)
        rows = []
        for u in units:
            typ = (u.get("unit_type", "") + " " + u.get("bezeichnung", "")).lower()
            category = "Gewerbe" if any(x in typ for x in ["gewerbe", "laden", "büro", "buero"]) else "BGB"
            rows.append({
                "Objekt": prop_name,
                "Einheit": u.get("unit_name") or u.get("unit_number") or u.get("bezeichnung") or "",
                "Mieter": u.get("tenant", ""),
                "Unit ID": u.get("id", ""),
                "Kategorie": category,
                "M-Files NKM aktuell": money(u.get("net_rent")),
                "Miete laut Vertrag/letztem Beleg": "",
                "Delta": "",
                "Stimmt M-Files mit Vertrag/Beleg?": "OFFEN",
                "Letzte Erhoehung / Basisdatum": "",
                "Was ist das Datum?": "",
                "Quelle": "M-Files Einheitenliste; Vertragsabgleich separat mit rent-check",
                "Klartext fuer Dritte": "Rent-roll-Zeile aus M-Files; Vertragsbeleg noch nicht geprueft.",
            })
        out = write_rent_roll(args.xlsx, rows)
        print(f"XLSX geschrieben und validiert: {out}")
    finally:
        await client.close()


async def amain(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return await {
            "search": cmd_search,
            "units": cmd_units,
            "docs": cmd_docs,
            "contract": cmd_contract,
            "rent-check": cmd_rent_check,
            "rent-roll": cmd_rent_roll,
        }[args.command](args) or 0
    except Exception as e:
        msg = redact(str(e))
        print(f"mfiles: error: {msg}", file=sys.stderr)
        if getattr(args, "debug", False):
            import traceback
            print(redact(traceback.format_exc()), file=sys.stderr)
        return 1


def main(argv=None):
    raise SystemExit(asyncio.run(amain(argv)))


if __name__ == "__main__":
    main()
