---
name: estatemate-crm
description: "Pflegt das EstateMate Sales-CRM in Twenty (self-hosted auf Railway). Nutze diesen Skill IMMER fuer EstateMate-Vertriebsthemen: Pipeline-Status, Deals, Leads, Opportunities, Stages (Gespraech/Demo/Pilot/Angebot/Won/Lost), Referrer-Tracking, Kunden-Kontakte und Activities. Scripts machen Twenty-REST-API-Calls (search, log_activity, update_stage, create_lead, create_contact, add_note_task, pipeline_status). Triggers: EstateMate, Pipeline, Deal, Lead, Referrer, Opportunity, Won, Lost, Stage, Sales, CRM, Twenty, Demo gezeigt, Call gehabt, Meeting mit Kunde, pipeline status, wie sieht die pipeline aus, aktive deals, neue leads, wer hat wen gebracht, onboarding, stage wechseln, log activity, log call, log meeting, BIDDEX, Caleus, Sandra Habermann, Jachimowicz, Flo Muenster, Rackham Schroeder, Dr. Franck, Franck Satzl, Herr Rist, Patrick Reich, Lukas Jackl, Engel & Voelkers."
---

# EstateMate CRM Skill

## Overview

Pflegt das EstateMate Sales-CRM (Twenty, self-hosted auf Railway). Erstellt Activities, legt Leads/Contacts an, aktualisiert Deal- und Lead-Stages, erfasst Notes und Tasks, und beantwortet Pipeline-Fragen. Alle Schreibvorgänge passieren gegen die Twenty REST API.

Das CRM ist für ein Dreier-Team gebaut (Ari, Roman, Christof) und folgt einem warm-sales / referrer-zentrierten Modell: Referrer sind first-class, jede Opportunity lässt sich auf eine Person zurückführen, und die Pilot-Phase wird strukturiert über das `pilotScope`-Objekt dokumentiert.

## Environment

Braucht zwei Variablen (im Hermes `.env` oder Admin-Dashboard gesetzt):

```
TWENTY_API_KEY=<long-lived service key named 'estatemate-ops'>
TWENTY_BASE_URL=https://twenty-production-f45b.up.railway.app
```

Der API-Key hat volle Schreib-/Leserechte auf den Workspace. In 1Password abgelegt. Rotation nach 11 Monaten.

## Objekt-Modell (Kurzreferenz)

Siehe `references/data-model.md` für alle Felder. Kurz:

- **company** - Firma/Kunde/Referrer-Firma. Key-Felder: `name`, `companyType`, `wohneinheiten`, `gewerbeeinheiten`, `icpScore`, `hqStadt`, `employees`
- **person** - Kontakt. Key-Felder: `name` (Object: firstName/lastName), `companyId`, `titel`, `buyingRole`, `isReferrer`, `sprache`
- **opportunity** - Deal. Key-Felder: `name`, `companyId`, `pointOfContactId`, `stage`, `stageSeit`, `dealSource`, `referrerId`, `unitsDealWohnen`, `unitsDealGewerbe`, `preisProEinheit`, `probability`, `nextAction`, `nextActionBis`, `pilotStart`, `pilotEnde`, `closeDate`
- **lead** - Vor-Qualifizierung. Key-Felder: `name`, `companyText`, `personId`, `leadSource`, `referrerId`, `stage`, `icpQuickFit`, `nextAction`, `nextActionBis`, `convertedDealId`, `notes`
- **activity** - Kontakt-Log. Key-Felder: `name`, `aktivitaetDatum`, `leadId` **oder** `dealId` (genau eines), `typ`, `richtung`, `summary`, `sentiment`
- **pilotScope** - Leistungsvereinbarung. Key-Felder: `dealId`, `unitsPilotWohnen`, `unitsPilotGewerbe`, `erfolgskriterien`, `pilotStart`, `pilotEnde`, `preis`, `status`

Enum-Werte siehe `references/enums.md`.

## Regeln (wichtig)

1. **Activity-Parent**: Jede Activity hat genau einen Parent - entweder `leadId` oder `dealId`, nie beides, nie keins. Script validiert das.
2. **Stage-Wechsel bei Deals**: Wenn `stage` geändert wird, IMMER `stageSeit` auf heute setzen. `update_stage.py` macht das automatisch.
3. **Referrer-Beziehungen**: Nur Contacts mit `isReferrer=true` dürfen als `referrerId` auf Deals/Leads stehen. `create_lead.py` und `create_contact.py` prüfen das.
4. **Human-in-the-Loop**: Vor Writes die geplante Operation zusammenfassen und auf Bestätigung warten. Nie silent schreiben.
5. **Pricing**: Wohn- und Gewerbe-Units getrennt erfassen. Deal-Amount (`amount`) = Total-Units × Preis-pro-Einheit. Preis-Feld ist jährlich.

## Workflow

### Schritt 1 - Entity finden

Vor jedem Write: erst den relevanten Record finden (by name / substring). Nie raten.

```bash
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/search.py --type person --query "Rackham"
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/search.py --type company --query "Caleus"
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/search.py --type deal --query "Onboarding"
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/search.py --type lead --query "BIDDEX"
```

Gibt JSON mit `id`, Name, wichtigste Felder und Relations zurück. Ambiguität (mehrere Matches): User nachfragen, nie raten.

### Schritt 2 - Operation ausführen

**Activity loggen (Deal oder Lead):**
```bash
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/log_activity.py \
  --parent-type deal --parent-id <uuid> \
  --typ TYPE_CALL --richtung DIR_OUTBOUND \
  --datum 2026-04-22T14:30:00Z \
  --summary "Demo gezeigt, Patrick will intern abstimmen, Entscheidung bis Ende April"
```

`--typ`: TYPE_CALL, TYPE_MEETING, TYPE_DEMO, TYPE_EMAIL, TYPE_VOICE, TYPE_SONSTIGES
`--richtung`: DIR_OUTBOUND, DIR_INBOUND
`--sentiment` (optional): SENT_POSITIV, SENT_NEUTRAL, SENT_NEGATIV

**Stage ändern (Deal oder Lead), setzt stageSeit automatisch:**
```bash
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/update_stage.py \
  --type deal --id <uuid> --stage STAGE_ANGEBOT
```

Deal-Stages: STAGE_GESPRAECH, STAGE_DEMO, STAGE_PILOT, STAGE_ANGEBOT, STAGE_WON, STAGE_LOST
Lead-Stages: STAGE_NEU, STAGE_KONTAKTIERT, STAGE_GEANTWORTET, STAGE_NURTURING, STAGE_QUALIFIZIERT, STAGE_DISQUALIFIZIERT

**Neuen Lead anlegen (mit Referrer):**
```bash
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/create_lead.py \
  --name "KGAL Portfolio" --company-text "KGAL" \
  --source SRC_REFERRAL --referrer-id <person-id-of-referrer> \
  --icp-quick-fit SCORE_4 \
  --next-action "Erstgespräch diese Woche"
```

**Neuen Contact anlegen:**
```bash
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/create_contact.py \
  --first "Klara" --last "Nowak" \
  --company-id <uuid> \
  --titel "Head of Real Estate" --buying-role ROLE_CHAMPION \
  --is-referrer false --sprache LANG_DE
```

**Note oder Task hinzufügen:**
```bash
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/add_note_task.py \
  --kind note --attach-to-type person --attach-to-id <uuid> \
  --title "Referral über LinkedIn kam durch Dr. Franck" \
  --body "Dr. Franck hat uns heute Abend per LinkedIn vorgestellt..."
```

Oder Task mit Fälligkeit:
```bash
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/add_note_task.py \
  --kind task --attach-to-type deal --attach-to-id <uuid> \
  --title "Scope-Entwurf an Patrick senden" --due 2026-05-01
```

### Schritt 3 - Pipeline-Overview

Für "was liegt an?", "wer ist dran?", "wie steht's":

```bash
python3 ~/.hermes/skills/productivity/estatemate-crm/scripts/pipeline_status.py
```

Gibt Summary: aktive Deals (Stage + Age), offene Leads, Next Actions bis heute, stille Referrer (>60 Tage).

## Typische Abläufe

### "Log Call mit Patrick Reich heute, haben Demo besprochen"
1. `search.py --type person --query "Patrick Reich"` → bekomme contact-id
2. search linked lead: `search.py --type lead --query "Caleus"` → bekomme lead-id
3. `log_activity.py --parent-type lead --parent-id <lead-id> --typ TYPE_CALL --richtung DIR_OUTBOUND --summary "Demo besprochen, Patrick will intern abstimmen"`
4. Optional: wenn Stage auf "Geantwortet" noch nicht, bleibt so; wenn jetzt "Nurturing" wird: `update_stage.py --type lead --id <lead-id> --stage STAGE_NURTURING`

### "Neuer Lead: Hans Müller von Müller FO, kommt über Dr. Franck"
1. `search.py --type person --query "Franck"` → Dr. Franck's id (must be isReferrer=true)
2. `search.py --type person --query "Müller"` → gibt's schon?
3. Falls nicht: `create_contact.py --first "Hans" --last "Müller" --is-referrer false`
4. `create_lead.py --name "Müller FO - Hans Müller" --company-text "Müller FO" --source SRC_REFERRAL --referrer-id <franck-id> --person-id <hans-id>`

### "Rackham-Deal auf Won setzen, Onboarding erfolgreich abgeschlossen"
1. `search.py --type deal --query "Rackham"` → deal-id
2. `log_activity.py --parent-type deal --parent-id <deal-id> --typ TYPE_MEETING --richtung DIR_OUTBOUND --summary "Onboarding final abgeschlossen, Produktivbetrieb gestartet" --sentiment SENT_POSITIV`
3. `update_stage.py --type deal --id <deal-id> --stage STAGE_WON`

## Was der Skill NICHT macht

- Batch-Imports oder Migrations (separate Scripts im `estatemate-sales-ops`-Repo)
- Schema-Änderungen (Custom Objects/Felder anlegen - das ist Bootstrap-Territory)
- View-Konfiguration (UI-Klick oder Views-Script im anderen Repo)
- User-Einladungen (UI-only in Twenty v2)
- Demo-Daten-Cleanup (einmalig im anderen Repo gemacht)

## Troubleshooting

- **401 Unauthorized**: API-Key abgelaufen oder revoked. Neuen `estatemate-ops`-Key im Twenty UI erstellen.
- **400 Bad Request mit "Invalid object value"**: RICH_TEXT-Felder erwarten `{"markdown": "..."}` als Object, kein String.
- **RELATION 400**: `relationCreationPayload` hat falsche targetObjectMetadataId oder type. Script sollte das nicht selbst bauen - Create-Scripts sind darauf vorkonfiguriert.
- **Idempotency**: Bei wiederholtem Aufruf zuerst mit `search.py` prüfen ob Record schon existiert. Nicht blind duplizieren.

## Repo

Dieser Skill ist Teil von `Arimi47/hermes-agent`. Das zugrundeliegende CRM-Setup (Bootstrap-Scripts, Datenmodell-Doku, Runbook) lebt in `Arimi47/estatemate-sales-ops`.
