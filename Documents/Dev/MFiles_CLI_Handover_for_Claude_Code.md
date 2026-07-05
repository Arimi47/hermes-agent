---
type: dev-handover
created: 2026-07-04
project: M-Files CLI
status: ready-for-claude-code
---

# M-Files CLI Handover for Claude Code

## Kurzstatus

Die CLI ist **noch nicht implementiert**. Dieses Dokument ist der konkrete Handover an Claude Code, um die CLI zu bauen.

Hermes hat aktuell Zugriff auf M-Files über MCP-Tools, aber der eigentliche MCP-Server-Code liegt in dieser Runtime nicht als bearbeitbares Repo vor. Daher soll Claude Code die CLI in dem echten M-Files-/Hermes-Repo bauen, in dem der bestehende M-Files-REST-Client oder MCP-Servercode vorhanden ist.

## Ziel

Baue eine tokenarme Python-CLI namens `mfiles`, die Claude Code und Menschen nutzen können, ohne große MCP-Tool-Schemas oder riesige JSON-Dumps in den Kontext zu laden.

Die CLI soll Standardausgaben kurz und geschäftlich lesbar halten. Volltext oder große Dokumentmengen werden nur auf expliziten Wunsch ausgegeben oder in Dateien geschrieben.

## Warum CLI statt nur MCP

- Claude Code arbeitet ohnehin gut über Terminal/Bash.
- CLI-Ausgaben können gezielt kurz sein.
- Große M-Files-Objekte, Vertrags-PDFs und Dokumentlisten sollen nicht ungefiltert in den Modellkontext laufen.
- CLI ist leichter zu testen und zu debuggen: Exit-Code, stdout, stderr.
- MCP kann später als Komfortschicht auf denselben Core aufsetzen.

Zielarchitektur:

```text
mfiles-core
  ↓
mfiles-cli      # tokenfreundlich für Claude Code / Menschen
  ↓
mfiles-mcp      # optional weiter für Hermes/Chat-Agenten
```

## Sicherheitsregeln

- Niemals Secrets, Tokens, Cookies, Session IDs, Vault-URLs mit Credentials oder Connection Strings ausgeben.
- Alle sensiblen Werte in Logs als `[REDACTED]` maskieren.
- Auth nur über Environment-Variablen oder lokale Config außerhalb des Repos.
- Keine echten Credentials committen.
- Debug-Ausgaben nur mit `--debug`, ebenfalls redacted.

## Empfohlene Paketstruktur

```text
mfiles_cli/
├── pyproject.toml
├── README.md
├── mfiles_cli/
│   ├── __init__.py
│   ├── main.py              # Typer/Click entrypoint
│   ├── config.py            # env vars / config loading / redaction
│   ├── client.py            # M-Files REST client wrapper
│   ├── constants.py         # bekannte Property IDs zentral
│   ├── formatters.py        # brief/json/markdown/xlsx
│   ├── extract.py           # PDF/DOCX text extraction, grep, context windows
│   └── commands/
│       ├── search.py
│       ├── units.py
│       ├── docs.py
│       ├── contract.py
│       ├── rent_check.py
│       └── rent_roll.py
└── tests/
    ├── test_amount_parsing.py
    ├── test_grep_context.py
    ├── test_redaction.py
    ├── test_rent_check.py
    └── test_xlsx_output.py
```

Typer ist bevorzugt, Click ist auch ok. Wichtig ist stabile, scriptbare Ausgabe.

## Commands v1

### `mfiles search QUERY`

Zweck: Objekte/Liegenschaften/Einheiten/Dokumente suchen, soweit vorhandene REST-Logik das unterstützt.

Default-Ausgabe kurz:

```text
ID     Typ          Name                                 Zusatz
103    Property     Zweibrückenstr. 15                   München
5814   Unit         EG rechts                            Indian Mango
```

Optionen:

```bash
mfiles search "Indian Mango"
mfiles search "Zweibrücken" --json
```

### `mfiles units --property-id ID`

Zweck: Einheiten einer Liegenschaft mit aktueller Miete und Mieter kompakt anzeigen.

```bash
mfiles units --property-id 103
mfiles units --property-id 103 --json
```

Pflichtfelder default:

```text
Unit ID | Einheit | Mieter | M-Files NKM | Vermietung/Status
```

### `mfiles docs --unit-id ID`

Zweck: Dokumente einer Einheit kompakt listen.

```bash
mfiles docs --unit-id 5814
```

Pflichtfelder:

```text
object_id | file_id | extension | name | contract_name | size
```

### `mfiles contract --unit-id ID [--latest] [--grep REGEX] [--context N] [--full] [--out PATH]`

Zweck: Vertragstext gezielt extrahieren.

Default: keine Volltexte dumpen.

Beispiele:

```bash
mfiles contract --unit-id 5814 --grep "Index|Verbraucherpreis|Nettokaltmiete" --context 8
mfiles contract --unit-id 5814 --full --out /tmp/5814_contract.txt
```

Bei `--grep`:

```text
Unit 5814 | Indian Mango | EG rechts | Zweibrückenstr. 15
Dokument: Immo_GMV_2001_06_IndianMango.pdf
Fundstelle: 3. Nachtrag, Seite 2

[Zeilen/Snippet]
Ab dem 01.01.2026 wird die Miete ... jährlich zum 01.01. automatisch angepasst.
Bemessungsgrundlage für die erste Mietanpassung ist der Indexstand zum 01.01.2025.
```

Wenn extrahierter Text groß ist und kein `--full`: vollständigen Text in `/tmp/mfiles_contract_<unit_id>.txt` schreiben und nur Pfad + Treffer ausgeben.

### `mfiles rent-check --unit-id ID`

Zweck: aktuelle M-Files-NKM gegen Vertrag/letzten Beleg prüfen.

Output muss fachlich lesbar sein:

```text
Unit 5814 | Indian Mango | EG rechts | Zweibrückenstr. 15

M-Files NKM aktuell: 7.000,00 €
Miete laut Vertrag/letztem Beleg: 7.147,00 € rechnerisch ab 01.01.2026
Delta: -147,00 €
Stimmt M-Files mit Vertrag/Beleg? NEIN
Letzte Erhöhung / Basisdatum: 01.01.2026
Was ist das Datum? automatische VPI-Anpassung; Basis Indexstand 01.01.2025
Quelle: Immo_GMV_2001_06_IndianMango, 3. Nachtrag, Seite 2

Klartext:
M-Files zeigt noch 7.000,00 €. Der 3. Nachtrag sieht ab 01.01.2026 eine automatische jährliche VPI-Anpassung vor. Wenn Januar 2026 gegenüber Januar 2025 +2,1 % angesetzt wird, ergibt sich 7.147,00 €.
```

Statuswerte zwingend:

- `JA` - M-Files entspricht Vertrag/letztem Beleg.
- `NEIN` - M-Files weicht ab.
- `OFFEN` - kein belastbarer Beleg gefunden.

### `mfiles rent-roll --property-id ID --xlsx OUT`

Zweck: einfache, drittverständliche XLSX erzeugen.

```bash
mfiles rent-roll --property-id 103 --xlsx /tmp/zb15.xlsx
```

Pflicht: maximal zwei Blätter:

- `Uebersicht`
- `Legende`

Keine Excel-Tabellenobjekte, keine Makros, keine Umlaute in Blattnamen. Nur einfache Zellen, Freeze Pane, Autofilter.

Spalten:

```text
Objekt
Einheit
Mieter
Unit ID
Kategorie
M-Files NKM aktuell
Miete laut Vertrag/letztem Beleg
Delta
Stimmt M-Files mit Vertrag/Beleg?
Letzte Erhoehung / Basisdatum
Was ist das Datum?
Quelle
Klartext fuer Dritte
```

Nach Erstellung immer validieren:

```python
import zipfile, openpyxl
assert zipfile.ZipFile(path).testzip() is None
wb = openpyxl.load_workbook(path, data_only=True)
assert wb.sheetnames == ["Uebersicht", "Legende"]
```

## Business-Regeln für Mieterhöhungen

- M-Files-Feld `letzte Mieterhöhung` nie blind übernehmen.
- NK-/Betriebskostenanpassungen nicht als echte Mieterhöhung werten.
- Parteientausch/Haftentlassung als Sonderfall behandeln.
- Index/VPI-Fälle müssen direkt sagen:
  - aktuelles M-Files-NKM,
  - Miete laut Vertrag/letztem Beleg,
  - Delta,
  - `Stimmt M-Files mit Vertrag/Beleg?`,
  - VPI-Basisdatum / letzte Indexanpassung.
- Große Audit-Tabs vermeiden. Finaldatei für Ari: maximal zwei Blätter.

## Testfälle aus der echten Arbeit

### Indian Mango - Unit 5814

Quelle: `Immo_GMV_2001_06_IndianMango`, 3. Nachtrag, Seite 2.

Klausel:

- 01.01.2024: NKM 6.500,00 €
- 01.01.2025: NKM 7.000,00 €
- ab 01.01.2026: jährliche automatische VPI-Anpassung zum 01.01.
- Bemessungsgrundlage erste Mietanpassung: Indexstand 01.01.2025.

Erwartung `rent-check`:

- M-Files aktuell: 7.000,00 €
- wenn Januar 2026 vs Januar 2025 +2,1 % verwendet wird: rechnerisch 7.147,00 €
- Status: `NEIN`, wenn M-Files noch 7.000,00 € zeigt.

### Mama Pizza - Unit 5778

Quelle: `Immo_GMV_2020_10_Mama Pizza`, Staffelmiete.

- ab 15.01.2024: 1.674,75 €
- ab 15.01.2027: 1.758,49 €
- M-Files in letzter Prüfung: 1.693,73 €
- Erwartung: `NEIN`, Delta 18,98 €, sofern kein späterer Beleg gefunden wird.

### Artis - Unit 5777

Quelle: `Immo_GMV_2023_12_Ambulante Pflege Artis GmbH`, §2 Mietzins.

- Kaltmiete: 1.650,00 €
- M-Files: 1.650,00 €
- Erwartung: `JA`.

### SecondHand Umhau - Unit 5816

M-Files meldete: keine Vermietung an Einheit / keine Dokumente am Unit-Lookup.

- M-Files NKM vorhanden, aber kein Beleg.
- Erwartung: `OFFEN`.

## Parsing-Hinweise

Deutschbeträge robust parsen:

- `7.000,00 €` -> `7000.00`
- `1.674,75` -> `1674.75`
- `3212,50€` -> `3212.50`
- `DM 1.650,--` nicht blind als Euro werten, historische DM markieren.

Regex-Suche muss Unicode/Deutsch können:

```text
Index|Verbraucherpreis|Nettokaltmiete|Kaltmiete|Mietzins|Staffelmiete|erhöht sich|Nachtrag|Mieterhöhung
```

## Claude-Code-Auftrag

Nutze diesen Prompt in Claude Code im echten Repo:

```text
Build the M-Files CLI described in Documents/Dev/MFiles_CLI_Handover_for_Claude_Code.md.

Requirements:
- Implement Python package `mfiles_cli` with CLI command `mfiles`.
- Reuse existing M-Files REST/MCP client logic from this repository.
- Do not print secrets. Add redaction tests.
- Default outputs must be brief and token-efficient.
- Implement commands: search, units, docs, contract, rent-check, rent-roll.
- For contract text, support --grep and --context; do not dump full contracts unless --full or --out is provided.
- For rent-roll xlsx, produce exactly two sheets: Uebersicht and Legende.
- Validate xlsx with zipfile and openpyxl.
- Add tests for amount parsing, grep context extraction, redaction, xlsx validation.
- Run tests and show exact command outputs.
```

## Acceptance commands

```bash
mfiles --help
mfiles units --property-id 103
mfiles docs --unit-id 5814
mfiles contract --unit-id 5814 --grep "Index|Verbraucherpreis|Nettokaltmiete" --context 8
mfiles rent-check --unit-id 5814
mfiles rent-roll --property-id 103 --xlsx /tmp/zb15.xlsx
python -m pytest tests/ -q
```

## Aktueller Handover-Status

- Konzept und Spezifikation: erledigt.
- CLI-Code: noch durch Claude Code im echten Repo umzusetzen.
- Grund: In dieser Runtime liegt der M-Files-MCP-Servercode nicht als bearbeitbares Repo vor; Hermes sieht nur die angebundenen MCP-Tools.
