# EstateMate CRM Datenmodell

Vollstaendige Feld-Referenz fuer alle 6 Objekte. Kanonisch im Repo `Arimi47/estatemate-sales-ops` unter `docs/data-model-reference.md`. Diese Datei wird synchron gehalten.

## Pricing-Grundlage

EstateMate rechnet pro Einheit ab, mit Unterscheidung Wohnen/Gewerbe. Aktuelle Preise: 2 EUR/Wohneinheit/Monat, 3 EUR/Gewerbeeinheit/Monat. Jahresrechnung = (Wohn × 24) + (Gewerbe × 36).

## Objekte

### 1. company
- Standard-Felder: `name`, `domainName`, `address`, `employees`, `annualRecurringRevenue`, `linkedinLink`
- Custom-Felder: `companyType`, `wohneinheiten`, `gewerbeeinheiten`, `icpScore`, `hqStadt`
- Inverse-Relations: `people[]`, `opportunities[]`, `leads[]`, `activities[]`

### 2. person
- Standard: `name` (firstName/lastName object), `emails`, `phones`, `companyId`, `jobTitle`, `city`, `avatarUrl`, `linkedinLink`
- Custom: `titel`, `buyingRole`, `isReferrer`, `sprache`
- Inverse: `referredDeals[]`, `referredLeads[]`, `leads[]`

### 3. opportunity (Deal)
- Standard: `name`, `amount` (Currency), `stage`, `closeDate`, `pointOfContactId`, `companyId`
- Custom: `dealSource`, `referrerId` (only contacts with isReferrer=true), `unitsDealWohnen`, `unitsDealGewerbe`, `preisProEinheit` (Currency, p.a. per Wohneinheit), `probability`, `stageSeit`, `pilotStart`, `pilotEnde`, `nextAction`, `nextActionBis`, `lostReason`
- Inverse: `activities[]`, `pilotScopes[]`

### 4. lead
- Custom (alle): `name`, `companyText` (freitext bis Konversion), `personId` (optional), `leadSource`, `referrerId`, `stage`, `icpQuickFit`, `nextAction`, `nextActionBis`, `convertedDealId`, `notes` (Rich Text)
- Inverse: `activities[]`

### 5. activity
- Custom (alle): `name`, `aktivitaetDatum` (DateTime), `leadId` **oder** `dealId`, `typ`, `richtung`, `summary` (Rich Text), `sentiment` (optional)
- Constraint: genau einer von leadId/dealId gesetzt

### 6. pilotScope
- Custom (alle): `dealId` (one-to-many zu deal), `unitsPilotWohnen`, `unitsPilotGewerbe`, `erfolgskriterien` (Rich Text), `dauerWochen`, `pilotStart`, `pilotEnde`, `deliverablesEstatemate` (Rich Text), `deliverablesKunde` (Rich Text), `preis` (Currency), `zahlungsplan` (Rich Text), `status`
- Attachments: Word/PDF der Vereinbarung

## Konvertierungs-Flow

1. Lead wird angelegt (`stage=STAGE_NEU`) - alles vor Qualifizierung
2. Lead wandert durch Stages: NEU → KONTAKTIERT → GEANTWORTET → NURTURING → QUALIFIZIERT
3. Bei Qualifizierung: Opportunity erzeugen, `convertedDealId` auf Lead setzen
4. Opportunity durchlaeuft: GESPRAECH → DEMO → PILOT → ANGEBOT → WON/LOST
5. In PILOT: PilotScope-Record anlegen mit Scope-Details + Word-Anhang
6. Nach WON: Deal abgeschlossen, Daten bleiben fuer ARR-Analyse

## Kontextuelles Wissen

- **Prime-Referrer**: Rackham Schroeder (Engel & Voelkers) - aktiver Kunde UND Referrer, bringt laut Erwartung viele Leads
- **Multiplikatoren**: Dr. Sebastian Franck (Franck Satzl Notare, 40 MA), Herr Rist (Allianz)
- **Warm-Sales-Modell**: Kein Cold Outbound. Alle Leads kommen via Netzwerk oder Referral. Source ist fast immer SRC_NETWORK oder SRC_REFERRAL.
