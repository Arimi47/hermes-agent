# SELECT-Werte Referenz

Alle Select-Felder und ihre gueltigen Werte. Beim Write MUESSEN exakt diese Strings verwendet werden.

## company.companyType
- `TYPE_FAMILY_OFFICE` - Family Office
- `TYPE_ASSET_MANAGER` - Asset Manager
- `TYPE_FONDS` - Fonds
- `TYPE_BESTANDSHALTER` - Bestandshalter
- `TYPE_MAKLER` - Makler
- `TYPE_SONSTIGES` - Sonstiges

## company.icpScore / lead.icpQuickFit
- `SCORE_1` bis `SCORE_5`

## person.buyingRole
- `ROLE_ECONOMIC_BUYER` - Economic Buyer
- `ROLE_CHAMPION` - Champion
- `ROLE_USER` - User
- `ROLE_NO_ROLE` - Kontakt-ohne-Rolle

## person.sprache
- `LANG_DE` - DE
- `LANG_EN` - EN

## opportunity.stage (Deal Stages)
- `STAGE_GESPRAECH` - Gespraech (default)
- `STAGE_DEMO` - Demo
- `STAGE_PILOT` - Pilot
- `STAGE_ANGEBOT` - Angebot
- `STAGE_WON` - Won
- `STAGE_LOST` - Lost

## opportunity.dealSource / lead.leadSource
- `SRC_NETWORK` - Eigenes Netzwerk
- `SRC_REFERRAL` - Referral
- `SRC_INBOUND` - Inbound
- `SRC_EVENT` - Event
- `SRC_SONSTIGES` - Sonstiges

## opportunity.probability
- `PROB_10`, `PROB_25`, `PROB_50`, `PROB_75`, `PROB_90`

## lead.stage
- `STAGE_NEU` - Neu (default)
- `STAGE_KONTAKTIERT` - Kontaktiert
- `STAGE_GEANTWORTET` - Geantwortet
- `STAGE_NURTURING` - Nurturing
- `STAGE_QUALIFIZIERT` - Qualifiziert
- `STAGE_DISQUALIFIZIERT` - Disqualifiziert

## activity.typ
- `TYPE_CALL`, `TYPE_MEETING`, `TYPE_DEMO`, `TYPE_EMAIL`, `TYPE_VOICE`, `TYPE_SONSTIGES`

## activity.richtung
- `DIR_OUTBOUND`, `DIR_INBOUND`

## activity.sentiment (optional)
- `SENT_POSITIV`, `SENT_NEUTRAL`, `SENT_NEGATIV`

## pilotScope.status
- `STATUS_DRAFT`, `STATUS_ABGESTIMMT`, `STATUS_UNTERSCHRIEBEN`

## tasks.status (Twenty native)
- `TODO`, `IN_PROGRESS`, `DONE`

## Rich-Text-Felder (notes, summary, body)
Object-Format: `{"markdown": "<text>"}`, NICHT String.

## Currency-Felder (amount, preisProEinheit, preis)
Object-Format:
```json
{"amountMicros": 132000000000, "currencyCode": "EUR"}
```
(amountMicros = Betrag × 1_000_000)
