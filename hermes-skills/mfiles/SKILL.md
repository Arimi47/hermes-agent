---
name: mfiles
description: "M-Files Birnbaum-Vault Skill fuer Mietermeldungen, Angebote, Sanierungen und Mietvertraege. Nutzt mfiles_* MCP-Tools fuer Read (recap_bundle, list_vorgaenge, get_vorgang_details, read_unit_contract mit PDF-Extraktion, get_units, get_unit_docs, get_tenants) und Write (set_vorgang_status, set_angebot_status, set_sanierung_status, add_vorgang_comment, vorgaenge_decide_batch). Kann Maengel freigeben (berechtigt/unberechtigt), an VMM weiterreichen (Schwarzbaum/andere Portfolios), Angebote annehmen/ablehnen, Sanierungen weiterschalten, Kommentare anhaengen, und Mietvertraege als PDF lesen (nicht nur Metadaten - extrahiert vollstaendigen Vertragstext fuer Fragen zu Mietbeginn, Kaution, Sondervereinbarungen, Schoenheitsreparaturen, Kuendigungsfristen). Triggers: Mietermeldung, Mangel, Maengel, Vorgang, freigeben, berechtigt, unberechtigt, aufgeschoben, in Behebung, in Abrechnung, Nachfrage, an Schwarzbaum, VMM Schwarzbaum, andere Portfolios, weiterreichen, Angebot, annehmen, ablehnen, nachverhandeln, Sanierung, Vergabe, Durchfuehrung, Abnahme, abgeschlossen, Kommentar, recap, was liegt an, offene Vorgaenge, was muss ich pruefen, lies die Mails, Mietvertrag, Vermietung, Mietzins, Kaltmiete, Warmmiete, Kaution, Mietbeginn, eingezogen, Vertragsende, Befristung, Sondervereinbarung, Schoenheitsreparaturen, Buerge, Mieterhoehung, Mieter, Vormieter. Nur fuer Ari (User-ID 7652652109). NICHT fuer Vika."
---

# M-Files Skill (Hermes port)

## Overview

Verwaltet Birnbaum-Group Vorgaenge in M-Files (`birnbaumgruppe.cloudvault.m-files.com`) durch das `mfiles-mcp` Tool-Set. Drei Workflow-Klassen werden unterstuetzt:

- **Mietermeldungen** (Workflow 109, Class 62) - Mieter-Beschwerden / Maengelmeldungen
- **Angebote** (Workflow 113, Class 17) - Handwerker- und Dienstleister-Quotes
- **Sanierungen** (Workflow 110, Class 63) - Modernisierungs- und Sanierungs-Vorgaenge

Ari triagiert Vorgaenge per Telegram-Nachricht. Hermes recapt, zeigt Preview, pusht nach OK in M-Files. Schreib-Aenderungen sind echte Workflow-State-Transitions im Vault, sichtbar fuer Hausverwaltung Hennig (HVK) und VMM.

**Nur fuer Ari.** Vika darf diese Tools nicht aufrufen ("Das ist Aris Immobilien-Arbeit").

## Was der Skill NICHT macht

- Loeschen von Vorgaengen oder Dokumenten
- Neue Vorgaenge / Angebote / Mieter anlegen (POST /objects)
- Properties ausser Status und Kommentar setzen (z.B. Maengelart, Faelligkeitsdatum, zugewiesene Person)
- Andere Workflows pushen (Eingangsrechnung, Mahnungen, Vermietungen, Vertragsverwaltung) - 17 weitere Workflows existieren im Vault, sind aber bewusst nicht freigegeben
- Finanzen-Tools (Mortgages, Metrics, DSCR, Refinancing) - im Server vorhanden, aber nicht in `tools.include`

## Datenmodell-Kurzreferenz

**Vorgang (ObjectType 139):** Container fuer Mietermeldung oder Sanierung. Klasse 62 = Mietermeldung, Klasse 63 = Sanierung. Wichtige Properties:
- `0` = Name/Titel
- `38/39` = Workflow / State
- `100` = Klasse
- `1266` = Liegenschaft (Lookup)
- `1272` = Einheit (Lookup) - der Anker fuer Mietvertrag-Lookups
- `1269` = Mieter (Lookup)
- `1308` = Maengelart (VL 137: Gebaeude=9, Wohnung=11)

**Kommentare** gehen nicht an PropertyDef 33 (alte Implementierung), sondern via `PUT /objects/.../comments` an den Comments-Tab des Objekts. Sichtbar in M-Files als eigener Tab, das ist was HVK liest.

**Angebot (ObjectType 0 = Dokument, Klasse 17):** Handwerker-Quote. Workflow 113.

**Einheit (ObjectType 132, Klasse 52):** Wohn-/Gewerbeeinheit. Property `1431` = Vermietung-Lookup, das Bindeglied zur aktiven Vermietung.

**Vermietung (Klasse 57, Workflow 128):** Container pro Mietperiode. Haelt den Mietvertrag-PDF (Klasse 39), Uebergabeprotokoll (Klasse 61), evtl. Vertragsanpassungen. Eine Einheit kann ueber die Jahre mehrere Vermietungen durchlaufen haben - aktuelle = `Laufzeit_Ende` leer oder in Zukunft.

Vollstaendige Property-Liste: `Documents/2026-04-10_MFILES_PROPERTY_DEFINITIONS.md` (541 Properties). REST-API-Details: `Documents/2026-04-10_MFILES_REST_API_REFERENCE.md`.

## Workflow A - Recap offene Vorgaenge (read-only)

**Trigger:** "was liegt an", "offene Mietermeldungen", "Recap Maengel", "was muss ich pruefen", "lies die Mails"

**Tool:** `mfiles_vorgaenge_recap_bundle(status_id=185, fetch_docs=True)` - **immer mit `status_id`-Filter**, sonst timeout.

Status-IDs fuer den Recap-Filter:
- `185` = Mietermeldungen "in Pruefung" (offene Maengel die Ari bewerten muss)
- `205` = Angebote "in Pruefung"
- `184` = neu eingegangene Mietermeldungen (selten gebraucht)

Optional: `limit=5` fuer "nur die wichtigsten 5", `fetch_docs=False` fuer Triage-Ueberblick ohne MSG-Inhalte.

**Output-Format pro Vorgang:**
- ID + Titel
- Liegenschaft / Einheit
- Mieter-Meldung aus MSG-Body (oder PDF-Text)
- Kontext (vorherige Vorgaenge, Foto-Beilagen)
- Einschaetzung Vermieter-vs-Mieter-Verschulden (Tuerscharnier=Mieter, Wasserschaden Fenster=Vermieter, etc.)
- Empfehlung (berechtigt / unberechtigt / nachfrage / aufgeschoben)

Empfehlungen sind konservativ - finale Entscheidung trifft Ari.

## Workflow B - Mangel freigeben (Status setzen)

**Der Push-Pfad.** Nach Recap sagt Ari typisch eine oder mehrere Entscheidungen.

### Trigger-Patterns (Mietermeldung) - Aris Decision-Set

Ari macht im Mietermeldungs-Workflow exakt die Triage-Entscheidung: **ist der Mangel berechtigt oder nicht.** Mehr nicht. Alles andere (Handwerker beauftragen → `in-behebung`, abnehmen → `erledigt`, abrechnen → `in-abrechnung`) macht das Operations-Team / die Hausverwaltung nach Aris Entscheidung. Schlage daher von Dir aus IMMER nur diese vier Status (+ optional Kommentar) vor.

| Eingabe | Status-Name | State-ID |
|---------|-------------|----------|
| "5036 berechtigt" / "5036 ok" / "5036 Mangel anerkannt" | `berechtigt` | 186 |
| "5036 unberechtigt" / "5036 abgelehnt" / "5036 Mieterverschulden" | `unberechtigt` | 188 |
| "5036 aufgeschoben" / "5036 spaeter" / "5036 zurueckstellen" | `aufgeschoben` | 339 |
| "5036 Nachfrage" / "5036 frag mal nach" / "5036 Rueckfrage" | `nachfrage` | 212 |

**Kommentar:** kann mit jedem Status mitkommen, z.B. "5036 unberechtigt Kommentar Tuer beim Einzug uebernommen" oder "5036 nachfrage Kommentar Art und Ort des Befalls klaeren". Der Kommentar wird vor dem Status-Wechsel an PropertyDef 33 gehaengt.

### Selten - nur wenn Ari es explizit sagt

| Eingabe | Status-Name | State-ID | Wer macht das normalerweise? |
|---------|-------------|----------|------------------------------|
| "5036 an Schwarzbaum" / "VMM Schwarzbaum" | `portfolio-schwarzbaum` | 190 | Ari, wenn Vorgang ans VMM-Routing soll |
| "5036 an andere" / "VMM andere" | `portfolio-andere` | 191 | Ari, fuer andere Portfolios |
| "5036 in Behebung" / "Handwerker beauftragt" | `in-behebung` | 187 | Operations-Team nach `berechtigt` |
| "5036 erledigt" / "5036 fertig" | `erledigt` | 189 | Operations-Team nach Handwerker-Abnahme |
| "5036 in Abrechnung" / "5036 abrechnen" | `in-abrechnung` | 204 | Operations-Team / Buchhaltung |
| "5036 Nachfrage erledigt" / "Antwort kam" | `nachfrage-erledigt` | 213 | Operations-Team |
| "5036 VMM hat freigegeben Schwarzbaum" | `vmm-berechtigt-schwarzbaum` | 234 | VMM, nicht Ari |
| "5036 VMM hat freigegeben andere" | `vmm-berechtigt-andere` | 233 | VMM, nicht Ari |

Diese Status NIE proaktiv vorschlagen. Nur ausfuehren wenn Ari den State-Namen explizit nennt - er weiss dann warum er aus dem normalen Pfad ausbricht.

### Trigger-Patterns (Angebot)

| Eingabe | Status-Name | State-ID |
|---------|-------------|----------|
| "Angebot 8722 annehmen" / "8722 ok" / "8722 angenommen" | `angenommen` | 208 |
| "8722 ablehnen" / "8722 abgelehnt" / "8722 zu teuer" | `abgelehnt` | 207 |
| "8722 nachverhandeln" / "8722 Preis verhandeln" | `nachverhandeln` | 206 |

Bei mehrdeutigen IDs (selber Tag fuer Mietermeldung und Angebot): Namespace `angebot.angenommen` nutzen.

### Trigger-Patterns (Sanierung)

| Eingabe | Status-Name | State-ID |
|---------|-------------|----------|
| "Sanierung 7211 in Durchfuehrung" / "7211 laeuft" | `durchfuehrung` | 193 |
| "7211 Vergabe" / "Auftrag vergeben" | `vergabe` | 225 |
| "7211 Ausschreibung" | `ausschreibung` | 226 |
| "7211 Ausschreibung Schwarzbaum" | `ausschreibung-schwarzbaum` | 224 |
| "7211 Abnahme" / "abgenommen" | `abnahme` | 230 |
| "7211 Abrechnung" | `abrechnung` | 204 |
| "7211 Nachfrage" | `nachfrage` | 212 |
| "7211 abgeschlossen" / "fertig" | `abgeschlossen` | 231 |

Bei Mehrdeutigkeit: Namespace `sanierung.durchfuehrung`.

### Tool-Wahl

**Einzelne Aenderung** (nur 1 Vorgang, kein Batch):
```
mfiles_set_vorgang_status(vorgang_id=5036, status="berechtigt", kommentar=None)
mfiles_set_angebot_status(angebot_id=8722, status="angenommen")
mfiles_set_sanierung_status(vorgang_id=7211, status="durchfuehrung")
```

**Mehrere Aenderungen in einem Schwung** (batch, mit dry_run-Preview):
```
mfiles_vorgaenge_decide_batch(
    decisions=[
        {"vorgang_id": 5036, "status": "berechtigt"},
        {"vorgang_id": 5040, "status": "unberechtigt", "comment": "Tuer beim Einzug uebernommen"},
        {"vorgang_id": 5044, "status": "aufgeschoben", "comment": "kommt nach Pfingsten"},
    ],
    dry_run=True
)
```

**Default-Strategie:** Bei 2+ Vorgaengen IMMER `decide_batch` benutzen, nicht 2+ Einzel-Calls. Das ist 1 Call statt N.

## Workflow C - Kommentar ohne Status-Aenderung

**Trigger:** "Kommentar an 5036: Mieter ruft naechste Woche zurueck", "Notiz an Vorgang 5036: Foto fehlt"

**Tool:** `mfiles_add_vorgang_comment(vorgang_id=5036, kommentar="Mieter ruft naechste Woche zurueck")`

Kommentare werden an PropertyDef 33 gehaengt, mit M-Files-Timestamp. Kein Workflow-Wechsel.

Bei Angebot-Kommentaren: object_type=0 (Dokument), nicht 139. Beispiel:
```
mfiles_add_vorgang_comment(vorgang_id=8722, kommentar="Preis ok, aber Termin verschieben", object_type=0)
```

## Pflicht-Regel: Preview-Then-Confirm

**Jede Schreib-Aktion** (Status, Kommentar, Batch) durchlaeuft Preview-Confirm. Niemals silent schreiben.

### Pattern fuer Einzel-Aenderung

```
Status-Change:
- Vorgang: [Titel] (ID 5036)
- Liegenschaft: Schillerstr. 12 / WE 03
- Aktueller Status: in Pruefung
- Neuer Status: berechtigt (186)
- Kommentar: -

Soll ich das setzen?
```

Erst nach explizitem `ja` / `setzen` / `passt` / `mach` ausfuehren. Unklares "ok" = nachfragen.

### Pattern fuer Batch (decide_batch)

1. Ari liefert Entscheidungen als Prosa.
2. Hermes parst in Liste.
3. Hermes ruft `decide_batch(dry_run=True)` - validiert die Status-Namen, schreibt nichts.
4. Hermes zeigt Preview:
   ```
   Geplant (3 Aenderungen, dry-run validiert):
   - 5036 → berechtigt (186)
   - 5040 → unberechtigt (188), Kommentar: "Tuer beim Einzug uebernommen"
   - 5044 → aufgeschoben (339), Kommentar: "kommt nach Pfingsten"

   Soll ich alles so setzen?
   ```
5. Nach OK: gleiche `decisions`-Liste, aber `dry_run=False`. Tool fuehrt parallel aus.
6. Hermes meldet Ergebnis: "3 von 3 erfolgreich gesetzt in M-Files. Vorgang 5044 hat zusaetzlich den Kommentar bekommen."

Falls 1 von 3 failt: Ari die Failure-Details zeigen, Frage ob nochmal versuchen oder skippen.

## Workflow D - Suche nach Vorgang

**Trigger:** "Vorgang zu Schillerstr 12", "Maengel fuer Mueller", "wo ist der Graffiti-Vorgang"

**Tool:** `mfiles_search(query="Graffiti", object_type=139)` - liefert Treffer-Liste mit IDs und Titeln.

Bei Ambiguitaet: Liste an Ari zeigen, nach Klarstellung fragen. Niemals raten.

## Workflow E - Mietvertrag lesen (PDF-Inhalt, nicht nur Metadaten)

**Trigger:** Ari fragt etwas was im Vertrag steht, z.B.:
- "wann ist [Mieter] eingezogen?" / "Mietbeginn von Plieth?"
- "was zahlt der Mieter?" / "Mietzins" / "Kaltmiete" / "Warmmiete"
- "wie hoch ist die Kaution?" / "Kautionskonto"
- "wann laeuft der Vertrag aus?" / "Befristung" / "Kuendigungsfrist"
- "Sondervereinbarungen?" / "Schoenheitsreparaturen" / "Nebenkosten-Vorauszahlung"
- "was steht im Mietvertrag von Mueggelstr 4 WE03?"
- "lies mir den Vertrag von [Adresse]"
- "Buerge?" / "Mieterhoehung moeglich?"

Wichtig: das sind Fragen ueber den **PDF-Inhalt**, nicht ueber M-Files-Properties. M-Files hat zwar Vertragsabschluss-Datum als Property, aber Sondervereinbarungen, exakte Klauseln, handgeschriebene Anmerkungen stehen NUR in der PDF.

**Tool:** `mfiles_read_unit_contract(...)` - liest die aktive Vermietung **inkl. extrahiertem PDF-Text** in einem Call.

### Standard-Pfad: aus einer Mietermeldung heraus

Wenn Ari gerade in einem Vorgang-Recap ist und eine Vertragsfrage stellt: einfach die `vorgang_id` durchreichen, das Tool ermittelt automatisch die verlinkte Einheit.

```
mfiles_read_unit_contract(vorgang_id=5262)
```

Returns: Einheit-Info + neueste aktive Vermietung mit Properties (Vertragsabschluss, Laufzeit_Beginn, Laufzeit_Ende) + alle Dokumente der Vermietung (Mietvertrag, Uebergabeprotokoll, etc.) mit **vollstaendig extrahiertem PDF-Text**. Hermes kann dann jede Vertragsfrage aus dem Text beantworten.

### Standalone-Pfad: ohne Mietermeldungs-Kontext

Wenn Ari direkt fragt "lies den Mietvertrag von Mueggelstr 4 WE03": entweder Adresse + Einheit, oder direkte unit_id wenn schon bekannt.

```
mfiles_read_unit_contract(unit_name="WE03", property_name="Mueggelstr 4")
mfiles_read_unit_contract(unit_id=12345)
```

### Historische Vertraege (Vorvermieter)

Default ist `latest_only=True` - nur die aktive Vermietung. Wenn Ari nach Vorvermietern fragt ("wie war die Miete beim Schmidt vor 2020?"): `latest_only=False` setzen, dann kommen alle historischen Vermietungen zurueck. Hermes filtert auf den passenden Mieter.

```
mfiles_read_unit_contract(vorgang_id=5262, latest_only=False)
```

### Antwort-Format

Beantworte Aris Frage **in Klartext mit Zitat aus dem Vertragstext**, nicht nur ein Snippet. Beispiel:

> Plieth ist am 1. April 2018 eingezogen. Steht in §2 des Vertrags: "Das Mietverhaeltnis beginnt am 01.04.2018 und laeuft auf unbestimmte Zeit." Vorher gab es eine Schluesseluebergabe am 28. Maerz - in §11 als Sonderregelung erwaehnt.

So sieht Ari sofort woher die Info kommt und kann die PDF in M-Files nachschlagen wenn er zweifelt.

## Status-Namen Quick-Reference

### Mietermeldung (Workflow 109, 14 mappings)
`eingegangen` (184), `in-pruefung` (185), `berechtigt` (186), `in-behebung` (187), `unberechtigt` (188), `erledigt` (189), `portfolio-schwarzbaum` (190), `portfolio-andere` (191), `in-abrechnung` (204), `nachfrage` (212), `nachfrage-erledigt` (213), `vmm-berechtigt-andere` (233), `vmm-berechtigt-schwarzbaum` (234), `aufgeschoben` (339).

### Angebot (Workflow 113, 3 mappings)
`angenommen` (208), `abgelehnt` (207), `nachverhandeln` (206).

### Sanierung (Workflow 110, 8 mappings)
`durchfuehrung` (193), `abrechnung` (204), `nachfrage` (212), `ausschreibung-schwarzbaum` (224), `vergabe` (225), `ausschreibung` (226), `abnahme` (230), `abgeschlossen` (231).

Bei Mehrdeutigkeit (z.B. `nachfrage` existiert in Mietermeldung UND Sanierung mit gleicher ID 212): Namespace-Prefix nutzen (`mietermeldung.nachfrage`, `sanierung.nachfrage`).

## Typische Ablaeufe

### "Recap offene Mietermeldungen"
1. `mfiles_vorgaenge_recap_bundle(status_id=185)` → 1 Tool-Call mit allen Doks
2. Antworte mit semantischem Recap pro Vorgang inkl. Vermieter-vs-Mieter-Einschaetzung
3. Warte auf Aris Entscheidungen

### "5036 berechtigt, 5040 unberechtigt Tuer beim Einzug, 5044 aufgeschoben"
1. Parse zu Liste: `[{5036, berechtigt}, {5040, unberechtigt, "Tuer beim Einzug"}, {5044, aufgeschoben}]`
2. `mfiles_vorgaenge_decide_batch(decisions=[...], dry_run=True)` → validiere
3. Zeig Preview-Block, frag "Soll ich alles so setzen?"
4. Auf "ja": `mfiles_vorgaenge_decide_batch(decisions=[...], dry_run=False)`
5. Bestaetige: "3 von 3 in M-Files gesetzt"

### "5037 an Schwarzbaum weiter"
1. `mfiles_set_vorgang_status(vorgang_id=5037, status="portfolio-schwarzbaum")` - Preview-Confirm
2. Auf OK: ausfuehren
3. Bestaetige: "Vorgang 5037 ist jetzt im Portfolio Schwarzbaum (State 190). VMM uebernimmt ab hier."

### "Angebot 8722 annehmen, ist ein guter Preis"
1. `mfiles_set_angebot_status(angebot_id=8722, status="angenommen", kommentar="guter Preis")` - Preview-Confirm
2. Auf OK: ausfuehren

### "Kommentar an 5036: Foto fehlt noch, frag den Mieter"
1. `mfiles_add_vorgang_comment(vorgang_id=5036, kommentar="Foto fehlt noch, frag den Mieter")` - Preview-Confirm
2. Auf OK: ausfuehren

## Troubleshooting

- **"MSG nicht extrahierbar / extract-msg nicht installiert"**: Deploy-Issue. Ari Bescheid geben (`pip install extract-msg` + Redeploy noetig). Outlook-Mails kommen dann als Plaintext.
- **"401 / Token-Refresh failed"**: M-Files-Token abgelaufen. Server-Restart oder Login-Refresh. Nicht von Hermes auf Railway fixbar.
- **"Status invalid / erlaubt: [...]"**: Status-Name passt nicht zur Map. Liste der erlaubten Namen in der Fehlermeldung pruefen, neuen Versuch mit korrektem Namen oder direkter State-ID.
- **"Object not found / 404"**: Vorgang-ID falsch oder geloescht. Vor Push mit `mfiles_get_vorgang_details` verifizieren.
- **"Workflow transition not allowed"**: M-Files validiert serverseitig welche Transitions erlaubt sind. Nicht jede State-Kombination geht direkt (z.B. "in Pruefung" → "erledigt" geht nicht ohne "berechtigt"+"in Behebung" zwischendurch). Zwischen-Status setzen oder Ari nach gewuenschtem Pfad fragen.
- **MCP-Server timeout** (>45s): nur bei `recap_bundle` ohne `status_id` moeglich. IMMER `status_id` setzen.

## Repo

Skill ist Teil von `Arimi47/hermes-agent`. MCP-Server-Code in `mfiles-mcp/server.py` (31 Tools). Vollstaendige API-Dokumentation in `Documents/2026-04-10_MFILES_REST_API_REFERENCE.md` (Birnbaum-Vault state-of-art per 10.04.2026).
