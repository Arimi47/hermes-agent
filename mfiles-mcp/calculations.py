# -*- coding: utf-8 -*-
"""
Financial Calculations for Real Estate Metrics
Implements DSCR, LTV, Cap Rate, and scenario simulations.
"""

from typing import List, Dict, Any, Optional, Tuple

# WorkflowStatus-Mapping für Leerstandsanalyse (aus Rent Roll Generator)
WORKFLOW_STATUS_MAPPING = {
    "1": "Beim Makler zur Vermietung ausgeschrieben",
    "2": "In Sanierung",
    "3": "Rückbau",
    "4": "Modernisierung",
    "": "Nicht kategorisiert"
}


def calculate_monthly_interest(outstanding_balance: float, annual_rate: float) -> float:
    """
    Calculate monthly interest payment.

    Args:
        outstanding_balance: Remaining loan balance
        annual_rate: Annual interest rate as percentage (e.g., 3.5 for 3.5%)

    Returns:
        Monthly interest amount
    """
    if outstanding_balance <= 0 or annual_rate <= 0:
        return 0.0
    return outstanding_balance * (annual_rate / 100) / 12


def calculate_monthly_principal(outstanding_balance: float, amortization_rate: float) -> float:
    """
    Calculate monthly principal (Tilgung) payment.

    Args:
        outstanding_balance: Remaining loan balance
        amortization_rate: Annual amortization rate as percentage

    Returns:
        Monthly principal amount
    """
    if outstanding_balance <= 0 or amortization_rate <= 0:
        return 0.0
    return outstanding_balance * (amortization_rate / 100) / 12


def calculate_debt_service(
    mortgages: List[Dict[str, Any]],
    monthly: bool = True
) -> Tuple[float, float, float]:
    """
    Calculate total debt service from mortgages.

    WICHTIG: Tilgung wird aus Annuität - Zinsen berechnet (wie Ergebnisrechnung-Generator),
    NICHT aus dem Tilgungssatz. Der Tilgungssatz ist nur ein Fallback.

    Args:
        mortgages: List of mortgage dicts with interest_rate, monthly_payment, outstanding_balance
        monthly: If True, return monthly values; else annual

    Returns:
        Tuple of (total_interest, total_principal, total_debt_service)
    """
    total_interest = 0.0
    total_principal = 0.0

    for mortgage in mortgages:
        balance = mortgage.get('outstanding_balance', 0)
        interest_rate = mortgage.get('interest_rate', 0)
        monthly_payment = mortgage.get('monthly_payment', 0)
        amort_rate = mortgage.get('amortization_rate', 0)

        # Zinsen berechnen
        monthly_interest = calculate_monthly_interest(balance, interest_rate)

        # Tilgung = Annuität - Zinsen (wie Generator!)
        # Nur Fallback auf Tilgungssatz wenn keine monatliche Rate verfügbar
        if monthly_payment > 0:
            monthly_principal = monthly_payment - monthly_interest
            # Sicherstellen dass Tilgung nicht negativ wird
            monthly_principal = max(0, monthly_principal)
        else:
            # Fallback: Aus Tilgungssatz berechnen
            monthly_principal = calculate_monthly_principal(balance, amort_rate)

        total_interest += monthly_interest
        total_principal += monthly_principal

    total_debt_service = total_interest + total_principal

    if not monthly:
        return total_interest * 12, total_principal * 12, total_debt_service * 12

    return total_interest, total_principal, total_debt_service


def calculate_dscr(
    net_operating_income: float,
    debt_service: float
) -> Optional[float]:
    """
    Calculate Debt Service Coverage Ratio.

    DSCR = NOI / Debt Service

    Args:
        net_operating_income: Net Operating Income (same period as debt_service)
        debt_service: Total debt service (interest + principal)

    Returns:
        DSCR value or None if debt_service is 0
    """
    if debt_service <= 0:
        return None  # No debt = infinite coverage, represented as None
    return net_operating_income / debt_service


def calculate_ltv(
    outstanding_debt: float,
    property_value: float
) -> Optional[float]:
    """
    Calculate Loan-to-Value ratio.

    LTV = Outstanding Debt / Property Value * 100

    Args:
        outstanding_debt: Total outstanding loan balance
        property_value: Current property value (Verkehrswert)

    Returns:
        LTV as percentage (e.g., 65.5 for 65.5%) or None if value is 0
    """
    if property_value <= 0:
        return None
    return (outstanding_debt / property_value) * 100


def calculate_cap_rate(
    net_operating_income: float,
    property_value: float
) -> Optional[float]:
    """
    Calculate Capitalization Rate.

    Cap Rate = Annual NOI / Property Value * 100

    Args:
        net_operating_income: Annual Net Operating Income
        property_value: Current property value (Verkehrswert)

    Returns:
        Cap rate as percentage or None if value is 0
    """
    if property_value <= 0:
        return None
    return (net_operating_income / property_value) * 100


def calculate_vacancy_rate(
    total_units: int,
    vacant_units: int
) -> float:
    """
    Calculate vacancy rate.

    Args:
        total_units: Total number of rentable units
        vacant_units: Number of vacant units

    Returns:
        Vacancy rate as percentage
    """
    if total_units <= 0:
        return 0.0
    return (vacant_units / total_units) * 100


def get_effective_rent(unit: Dict[str, Any]) -> float:
    """
    Get effective rent for a unit, using projected rent for vacant/terminated units
    or units with Projektierte_Nutzen flag.

    Konsistent mit Generator portfolio_ergebnisrechnung.py:278-286:
    - Projektierte Werte wenn status == 'leer'
    - Projektierte Werte wenn status == 'gekündigt'
    - Projektierte Werte wenn Projektierte_Nutzen == True

    Args:
        unit: Unit dict with status, net_rent, net_rent_projected, projektierte_nutzen

    Returns:
        Effective monthly rent
    """
    status = unit.get('status', '').lower()

    # KRITISCH: Auch Projektierte_Nutzen Flag prüfen (Property 1546)
    # Dies ist der Hauptgrund für die Diskrepanz zwischen Generator und MCP-Tool
    projektierte_nutzen = unit.get('projektierte_nutzen', False)

    # Verwende projektierte Werte wenn:
    # 1. Einheit ist leer oder gekündigt (is_vacant Flag oder Status)
    # 2. Projektierte_Nutzen Flag ist True
    is_vacant = unit.get('is_vacant', False) or status in ['leer', 'gekündigt']
    use_projected = is_vacant or projektierte_nutzen

    if use_projected:
        # Use projected rent for vacant/terminated units or units with projektierte_nutzen flag
        projected = unit.get('net_rent_projected', 0) or 0
        if projected > 0:
            return projected
        # Fallback to actual rent if no projection
        return unit.get('net_rent', 0) or 0

    return unit.get('net_rent', 0) or 0


def classify_unit_for_metrics(unit: Dict[str, Any]) -> str:
    """
    Klassifiziert Einheit für Metriken - konsistent mit Rent Roll Generator.

    Returns:
        'main' - Wohnen, Gewerbe (für Hauptleerstandsquote)
        'cellar' - Keller (eigene Quote)
        'parking' - Stellplatz, Garage (eigene Quote)
        'bike' - Fahrradstellplatz (eigene Quote)
        'excluded' - Geldautomat, Technikraum etc. (nicht zählen)
    """
    unit_type = (unit.get('unit_type', '') or '').lower()
    unit_class = unit.get('unit_class', '')  # Falls von mfiles_client gesetzt

    # Liste nicht-vermietbarer Einheiten (aus Generator NON_RENTABLE_UNITS)
    non_rentable = [
        "geldautomat", "atm", "bankautomat", "ec-automat",
        "technikraum", "technik", "hausanschluss", "hausanschlüsse",
        "müllraum", "abstellraum gemeinschaft", "waschküche",
        "treppenhaus", "flur", "eingang", "foyer"
    ]

    # Prüfe auf nicht-vermietbare Einheiten
    for excluded in non_rentable:
        if excluded in unit_type:
            return 'excluded'

    # Nutze unit_class falls vorhanden (von mfiles_client)
    if unit_class:
        if unit_class == 'keller':
            return 'cellar'
        elif unit_class == 'ebike':
            return 'bike'
        elif unit_class == 'parking':
            return 'parking'
        elif unit_class == 'main':
            return 'main'

    # Fallback auf Typ-basierte Klassifikation
    if "keller" in unit_type or "lager" in unit_type:
        return 'cellar'
    elif "stellplatz" in unit_type or "garage" in unit_type:
        if "fahrrad" in unit_type or "rad" in unit_type:
            return 'bike'
        return 'parking'
    else:
        return 'main'


def is_ebike_garage(unit: Dict[str, Any]) -> bool:
    """
    Prüft ob eine Einheit eine E-Bike-Garage ist.

    Generator prüft: unit_name, bezeichnung (Property 1279), unit_number
    für Keywords wie "e-bike", "fahrradgarage", "ebike"

    Args:
        unit: Unit dict

    Returns:
        True wenn E-Bike-Garage
    """
    # Sammle alle relevanten Textfelder
    check_fields = [
        unit.get('unit_type', ''),
        unit.get('unit_name', ''),
        unit.get('bezeichnung', ''),
        unit.get('unit_number', ''),
        unit.get('unit_class', '')
    ]

    ebike_keywords = ['e-bike', 'ebike', 'e bike', 'fahrradgarage']

    for field in check_fields:
        if field:
            field_lower = field.lower()
            for keyword in ebike_keywords:
                if keyword in field_lower:
                    return True

    # Auch unit_class prüfen (von mfiles_client gesetzt)
    if unit.get('unit_class') == 'ebike':
        return True

    return False


def aggregate_unit_metrics(units: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate metrics from a list of units.

    WICHTIG: Leerstandsquote nur für Haupteinheiten (Wohnen + Gewerbe),
    NICHT für Keller, Stellplätze etc. - konsistent mit Rent Roll Generator.

    Erweitert um E-Bike-Sonderlogik (Task 32):
    - E-Bike projektierte Miete NUR für LEERE E-Bike-Garagen

    =========================================================================
    BIRNBAUM GROUP GESCHÄFTSREGEL - MIETBERECHNUNG (Stand: Januar 2026)
    =========================================================================

    Bei der Aggregation von Mieteinnahmen gilt folgende Regel:

    | Einheitentyp         | Abrechnung                    | Aggregation           |
    |----------------------|-------------------------------|-----------------------|
    | Keller               | In Hauptmietvertrag enthalten | NICHT separat addieren|
    | Fahrradstellplätze   | In Hauptmietvertrag enthalten | NICHT separat addieren|
    | Autostellplätze      | Separat vermietet             | MUSS addiert werden   |

    KORREKT:   Gesamtmiete = main_units['rent_actual'] + parking_units['rent_actual']
    FALSCH:    Gesamtmiete = main + cellar + bike (führt zu Doppelzählung!)

    Hintergrund:
    - Keller- und Fahrradmieten werden in M-Files separat erfasst (Transparenz)
    - Diese Beträge sind jedoch bereits in den Hauptmietverträgen enthalten
    - Nur PKW-Stellplätze werden tatsächlich separat vermietet

    Beispiel Schönhauser Allee 111:
    - Mieterliste (korrekt): 30.128,32 € (nur main + parking)
    - Mit Doppelzählung:     30.803,32 € (main + parking + cellar + bike = FALSCH)
    =========================================================================

    Args:
        units: List of unit dicts

    Returns:
        Dict with aggregated metrics (main, cellar, parking, bike separat)
    """
    # Klassifiziere alle Einheiten
    main_units = []
    cellar_units = []
    parking_units = []
    bike_units = []

    for unit in units:
        category = classify_unit_for_metrics(unit)
        if category == 'main':
            main_units.append(unit)
        elif category == 'cellar':
            cellar_units.append(unit)
        elif category == 'parking':
            parking_units.append(unit)
        elif category == 'bike':
            bike_units.append(unit)
        # 'excluded' units werden ignoriert

    def calc_category_metrics(unit_list: List[Dict[str, Any]], is_bike: bool = False) -> Dict[str, Any]:
        """Berechne Metriken für eine Einheiten-Kategorie

        WICHTIG: Berücksichtigt jetzt auch das Projektierte_Nutzen Flag (Property 1546)
        konsistent mit Generator portfolio_ergebnisrechnung.py:278-286
        """
        total_rent_actual = 0.0
        total_rent_projected = 0.0
        total_area = 0.0
        vacant_count = 0

        # E-Bike-Sonderlogik (nur für bike-Kategorie)
        ebike_projected_rent = 0.0
        ebike_empty_count = 0
        ebike_occupied_rent = 0.0
        ebike_total = 0

        for unit in unit_list:
            status = unit.get('status', '').lower()
            # KRITISCH: Auch Projektierte_Nutzen Flag prüfen (Property 1546)
            projektierte_nutzen = unit.get('projektierte_nutzen', False)
            is_vacant = unit.get('is_vacant', False) or status in ['leer', 'gekündigt']

            # Verwende projektierte Werte wenn leer/gekündigt ODER projektierte_nutzen Flag
            use_projected = is_vacant or projektierte_nutzen

            # E-Bike-Erkennung
            is_ebike = is_bike and is_ebike_garage(unit)
            if is_ebike:
                ebike_total += 1

            if use_projected:
                # Zähle als "leer" für Leerstandsquote nur wenn wirklich leer/gekündigt
                if is_vacant:
                    vacant_count += 1

                effective_rent = get_effective_rent(unit)
                total_rent_projected += effective_rent

                # Für actual_rent: Wenn nur projektierte_nutzen aber nicht vacant,
                # dann haben wir eine vermietete Einheit mit projiziertem Wert
                if not is_vacant and projektierte_nutzen:
                    # Einheit ist vermietet aber mit projiziertem Wert
                    # actual_rent bleibt die tatsächliche Miete
                    actual_rent = unit.get('net_rent', 0) or 0
                    total_rent_actual += actual_rent

                # E-Bike-Sonderlogik: Projektierte Miete NUR für leere E-Bikes
                if is_ebike and is_vacant:
                    ebike_empty_count += 1
                    projected = unit.get('net_rent_projected', 0) or 0
                    ebike_projected_rent += projected
                elif is_ebike and not is_vacant:
                    ebike_occupied_rent += unit.get('net_rent', 0) or 0
            else:
                actual_rent = unit.get('net_rent', 0) or 0
                total_rent_actual += actual_rent
                total_rent_projected += actual_rent

                # E-Bike-Sonderlogik: Aktuelle Miete vermieteter E-Bikes
                if is_ebike:
                    ebike_occupied_rent += actual_rent

            total_area += unit.get('area_sqm', 0) or 0

        total = len(unit_list)
        occupied = total - vacant_count
        vacancy_rate = calculate_vacancy_rate(total, vacant_count)

        result = {
            'total': total,
            'occupied': occupied,
            'vacant': vacant_count,
            'vacancy_rate': vacancy_rate,
            'rent_actual': total_rent_actual,
            'rent_projected': total_rent_projected,
            'area_sqm': total_area
        }

        # E-Bike-Felder nur bei bike-Kategorie hinzufügen
        if is_bike:
            result['ebike_total'] = ebike_total
            result['ebike_empty_count'] = ebike_empty_count
            result['ebike_occupied_count'] = ebike_total - ebike_empty_count
            result['ebike_projected_rent'] = ebike_projected_rent
            result['ebike_occupied_rent'] = ebike_occupied_rent

        return result

    main_metrics = calc_category_metrics(main_units)
    cellar_metrics = calc_category_metrics(cellar_units)
    parking_metrics = calc_category_metrics(parking_units)
    bike_metrics = calc_category_metrics(bike_units, is_bike=True)  # E-Bike-Logik aktivieren

    # =========================================================================
    # BIRNBAUM GROUP GESCHÄFTSREGEL - Miet-Aggregation
    # =========================================================================
    # Gesamtmiete = main_units + parking_units (PKW-Stellplätze)
    #
    # NICHT addiert werden:
    # - cellar_metrics (Keller) -> bereits in Hauptmietvertrag enthalten
    # - bike_metrics (Fahrrad) -> bereits in Hauptmietvertrag enthalten
    #
    # Diese werden nur zur Transparenz separat ausgewiesen, NICHT zur
    # Hauptmiete addiert, da dies zu Doppelzählung führen würde.
    #
    # AUSNAHME für projected rent (Stand Januar 2026):
    # - E-Bike projektierte Miete für LEERE E-Bike-Garagen wird zu
    #   total_rent_projected addiert, um das Vermietungspotenzial abzubilden
    # - Dies entspricht dem Generator portfolio_ergebnisrechnung.py:992:
    #   total_net_rent_with_extras = total_net_rent + parking_total_rent + ebike_total_rent
    # =========================================================================
    total_rent_actual = main_metrics['rent_actual'] + parking_metrics['rent_actual']

    # E-Bike projected rent für leere E-Bike-Garagen (konsistent mit Generator)
    ebike_projected_rent = bike_metrics.get('ebike_projected_rent', 0)
    total_rent_projected = main_metrics['rent_projected'] + parking_metrics['rent_projected'] + ebike_projected_rent

    return {
        # Hauptkennzahlen (konsistent mit Portfolio-Generator: main + parking)
        'total_units': main_metrics['total'] + parking_metrics['total'],
        'total_parking': parking_metrics['total'],
        'vacant_units': main_metrics['vacant'],
        'occupied_units': main_metrics['occupied'],
        'vacancy_rate': main_metrics['vacancy_rate'],  # NUR main_units!
        'monthly_rent_actual': total_rent_actual,
        'monthly_rent_projected': total_rent_projected,
        'total_area_sqm': main_metrics['area_sqm'],

        # Detaillierte Aufschlüsselung pro Kategorie
        'by_category': {
            'main': main_metrics,
            'cellar': cellar_metrics,
            'parking': parking_metrics,
            'bike': bike_metrics
        },

        # Separate Parking-Miete für Fußnote (wie Generator)
        'parking_rent_actual': parking_metrics['rent_actual'],
        'parking_rent_projected': parking_metrics['rent_projected'],
        'parking_occupied': parking_metrics['occupied'],
        'parking_vacant': parking_metrics['vacant'],

        # E-Bike-Sonderfelder (Task 32)
        'ebike_total': bike_metrics.get('ebike_total', 0),
        'ebike_empty_count': bike_metrics.get('ebike_empty_count', 0),
        'ebike_occupied_count': bike_metrics.get('ebike_occupied_count', 0),
        'ebike_projected_rent': bike_metrics.get('ebike_projected_rent', 0),
        'ebike_occupied_rent': bike_metrics.get('ebike_occupied_rent', 0),

        # =========================================================================
        # BIRNBAUM GROUP - Dokumentation der Aggregationsregel
        # =========================================================================
        # Diese Felder dokumentieren explizit die angewandte Geschäftsregel
        'rent_includes_cellar_and_bike': True,  # Keller/Fahrrad bereits in main enthalten
        'rent_includes_parking_separately': True,  # Parking wird separat addiert
        'ebike_rent_included_in_projected': True,  # E-Bike projected rent in total_rent_projected
        'aggregation_note': (
            'BIRNBAUM GROUP GESCHÄFTSREGEL: '
            'Keller- und Fahrradmieten sind in den Hauptmietverträgen enthalten '
            'und dürfen NICHT separat addiert werden. '
            'Nur Autostellplätze (parking) werden separat vermietet und addiert. '
            'E-Bike projektierte Miete (für leere E-Bike-Garagen) wird zu projected rent addiert. '
            'Gesamtmiete actual = main_units + parking_units. '
            'Gesamtmiete projected = main_units + parking_units + ebike_projected_rent.'
        )
    }


def calculate_interest_coverage_ratio(
    monthly_rent: float,
    monthly_interest: float
) -> Optional[float]:
    """
    Calculate Interest Coverage Ratio (Deckungsgrad Miete/Zinsen).

    Unterschied zu DSCR: Hier nur Zinsen, nicht gesamter Schuldendienst.

    Args:
        monthly_rent: Monthly rent income
        monthly_interest: Monthly interest payment

    Returns:
        ICR value or None if no interest
    """
    if monthly_interest <= 0:
        return None
    return monthly_rent / monthly_interest


def calculate_cashflow_ratio(
    annual_cashflow: float,
    annual_rent: float
) -> Optional[float]:
    """
    Calculate Cashflow Ratio (Cashflow-Quote).

    cashflow_ratio = (Restüberschuss / Jahresmiete) * 100

    Args:
        annual_cashflow: Annual cashflow after debt service
        annual_rent: Annual rent income

    Returns:
        Cashflow ratio as percentage or None if no rent
    """
    if annual_rent <= 0:
        return None
    return (annual_cashflow / annual_rent) * 100


def calculate_debt_ratio(
    total_debt: float,
    annual_rent: float
) -> Optional[float]:
    """
    Calculate Debt Ratio (Verschuldungsgrad).

    debt_ratio = Gesamtschulden / Jahresmiete

    Args:
        total_debt: Total outstanding debt
        annual_rent: Annual rent income

    Returns:
        Debt ratio (factor) or None if no rent
    """
    if annual_rent <= 0:
        return None
    return total_debt / annual_rent


def calculate_rent_breakdown(units: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate rent breakdown by type (Wohnen/Gewerbe/Parking).

    Args:
        units: List of unit dicts

    Returns:
        Dict with rent breakdown
    """
    wohn_rent = 0.0
    wohn_area = 0.0
    gewerbe_rent = 0.0
    gewerbe_area = 0.0
    parking_rent = 0.0
    parking_count = 0

    for unit in units:
        category = classify_unit_for_metrics(unit)
        if category == 'excluded':
            continue

        is_vacant = unit.get('is_vacant', False)
        rent = unit.get('net_rent', 0) or 0
        area = unit.get('area_sqm', 0) or 0

        if category == 'main':
            unit_type_cat = get_unit_type_category(unit.get('unit_type', ''))
            if not is_vacant:
                if unit_type_cat == 'gewerbe':
                    gewerbe_rent += rent
                    gewerbe_area += area
                else:
                    wohn_rent += rent
                    wohn_area += area
        elif category == 'parking':
            if not is_vacant:
                parking_rent += rent
                parking_count += 1

    # Calculate per sqm
    wohn_per_sqm = wohn_rent / wohn_area if wohn_area > 0 else 0
    gewerbe_per_sqm = gewerbe_rent / gewerbe_area if gewerbe_area > 0 else 0

    return {
        'wohn_monthly': wohn_rent,
        'wohn_annual': wohn_rent * 12,
        'wohn_area': wohn_area,
        'wohn_per_sqm': round(wohn_per_sqm, 2),
        'gewerbe_monthly': gewerbe_rent,
        'gewerbe_annual': gewerbe_rent * 12,
        'gewerbe_area': gewerbe_area,
        'gewerbe_per_sqm': round(gewerbe_per_sqm, 2),
        'parking_monthly': parking_rent,
        'parking_annual': parking_rent * 12,
        'parking_count': parking_count
    }


def calculate_property_metrics(
    units: List[Dict[str, Any]],
    mortgages: List[Dict[str, Any]],
    verkehrswert: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive property metrics.

    Erweitert um Ergebnisrechnung-konforme Kennzahlen:
    - Überschuss vor Tilgung (Miete - Zinsen)
    - Deckungsgrad (Miete / Zinsen)
    - Cashflow-Quote
    - Verschuldungsgrad
    - Verschuldung pro m²
    - Miet-Breakdown (Wohnen/Gewerbe/Parking)

    Args:
        units: List of unit dicts
        mortgages: List of mortgage dicts
        verkehrswert: Optional property value for LTV/Cap Rate

    Returns:
        Dict with all calculated metrics
    """
    # Aggregate unit data
    unit_metrics = aggregate_unit_metrics(units)

    # NEU: Miet-Breakdown
    rent_breakdown = calculate_rent_breakdown(units)

    # Calculate debt service (mit korrigierter Tilgungsberechnung)
    monthly_interest, monthly_principal, monthly_debt_service = calculate_debt_service(mortgages, monthly=True)

    # Total outstanding debt
    total_debt = sum(m.get('outstanding_balance', 0) for m in mortgages)

    # Use projected rent as NOI proxy (simplified - actual NOI would subtract OpEx)
    monthly_noi = unit_metrics['monthly_rent_projected']
    annual_noi = monthly_noi * 12
    annual_rent = unit_metrics['monthly_rent_actual'] * 12

    # === NEUE KENNZAHLEN (Ergebnisrechnung-konform) ===

    # Überschuss vor Tilgung = Miete - Zinsen
    surplus_before_principal_monthly = monthly_noi - monthly_interest
    surplus_before_principal_annual = surplus_before_principal_monthly * 12

    # Restüberschuss (nach Tilgung) = Miete - Zinsen - Tilgung = Miete - Schuldendienst
    monthly_cashflow = monthly_noi - monthly_debt_service
    annual_cashflow = monthly_cashflow * 12

    # Key ratios
    dscr = calculate_dscr(monthly_noi, monthly_debt_service)
    ltv = calculate_ltv(total_debt, verkehrswert) if verkehrswert else None
    cap_rate = calculate_cap_rate(annual_noi, verkehrswert) if verkehrswert else None

    # Neue Kennzahlen
    interest_coverage_ratio = calculate_interest_coverage_ratio(monthly_noi, monthly_interest)
    cashflow_ratio = calculate_cashflow_ratio(annual_cashflow, annual_noi)
    debt_ratio = calculate_debt_ratio(total_debt, annual_noi)

    # NEU: Verschuldung pro m²
    total_area = unit_metrics.get('total_area_sqm', 0)
    debt_per_sqm = total_debt / total_area if total_area > 0 else None

    # === PROJEKTIERTE KENNZAHLEN (Task 33) ===
    # total_rent_with_projection = Ist-Miete + Potenzial leerer Einheiten
    # Dies ist bereits in monthly_rent_projected enthalten
    total_rent_with_projection_monthly = unit_metrics['monthly_rent_projected']
    total_rent_with_projection_annual = total_rent_with_projection_monthly * 12

    # Potenzialmiete nur aus leeren Einheiten
    potential_rent_vacant_monthly = total_rent_with_projection_monthly - unit_metrics['monthly_rent_actual']
    potential_rent_vacant_annual = potential_rent_vacant_monthly * 12

    # NOI projected (bereits monthly_noi, aber explizit)
    noi_projected_monthly = total_rent_with_projection_monthly
    noi_projected_annual = total_rent_with_projection_annual

    # Surplus before principal mit Projektion
    surplus_before_principal_projected_monthly = noi_projected_monthly - monthly_interest
    surplus_before_principal_projected_annual = surplus_before_principal_projected_monthly * 12

    # Cashflow mit Projektion (nach Schuldendienst)
    cashflow_projected_monthly = noi_projected_monthly - monthly_debt_service
    cashflow_projected_annual = cashflow_projected_monthly * 12

    # DSCR mit Projektion
    dscr_projected = calculate_dscr(noi_projected_monthly, monthly_debt_service)

    # Interest Coverage Ratio mit Projektion
    interest_coverage_ratio_projected = calculate_interest_coverage_ratio(
        noi_projected_monthly, monthly_interest
    )

    # Cashflow-Quote mit Projektion
    cashflow_ratio_projected = calculate_cashflow_ratio(
        cashflow_projected_annual, noi_projected_annual
    )

    return {
        **unit_metrics,
        'annual_rent_actual': unit_metrics['monthly_rent_actual'] * 12,
        'annual_rent_projected': annual_noi,
        'total_outstanding_debt': total_debt,
        'monthly_interest': monthly_interest,
        'monthly_principal': monthly_principal,
        'monthly_debt_service': monthly_debt_service,
        'annual_interest': monthly_interest * 12,
        'annual_principal': monthly_principal * 12,
        'annual_debt_service': monthly_debt_service * 12,
        'noi_monthly': monthly_noi,
        'noi_annual': annual_noi,

        # Überschuss vor Tilgung (NEU - wie Ergebnisrechnung)
        'surplus_before_principal_monthly': surplus_before_principal_monthly,
        'surplus_before_principal_annual': surplus_before_principal_annual,

        # Restüberschuss / Cashflow
        'cashflow_monthly': monthly_cashflow,
        'cashflow_annual': annual_cashflow,
        'final_surplus_annual': annual_cashflow,  # Alias für Klarheit

        # Kennzahlen
        'dscr': dscr,
        'ltv': ltv,
        'cap_rate': cap_rate,
        'interest_coverage_ratio': interest_coverage_ratio,  # NEU: Miete/Zinsen
        'cashflow_ratio': cashflow_ratio,  # NEU: Cashflow/Miete %
        'debt_ratio': debt_ratio,  # NEU: Schulden/Jahresmiete
        'debt_per_sqm': debt_per_sqm,  # NEU: Verschuldung pro m²

        # NEU: Miet-Breakdown (Wohnen/Gewerbe/Parking)
        **rent_breakdown,

        # === PROJEKTIERTE KENNZAHLEN (Task 33) ===
        # Separates Kennzahlen-Set mit Projektion für leere Einheiten
        'total_rent_with_projection_monthly': total_rent_with_projection_monthly,
        'total_rent_with_projection_annual': total_rent_with_projection_annual,
        'potential_rent_vacant_monthly': potential_rent_vacant_monthly,
        'potential_rent_vacant_annual': potential_rent_vacant_annual,
        'noi_projected_monthly': noi_projected_monthly,
        'noi_projected_annual': noi_projected_annual,
        'surplus_before_principal_projected_monthly': surplus_before_principal_projected_monthly,
        'surplus_before_principal_projected_annual': surplus_before_principal_projected_annual,
        'cashflow_projected_monthly': cashflow_projected_monthly,
        'cashflow_projected_annual': cashflow_projected_annual,
        'dscr_projected': dscr_projected,
        'interest_coverage_ratio_projected': interest_coverage_ratio_projected,
        'cashflow_ratio_projected': cashflow_ratio_projected,

        'verkehrswert': verkehrswert
    }


def simulate_scenario(
    current_metrics: Dict[str, Any],
    new_loan_amount: Optional[float] = None,
    new_interest_rate: Optional[float] = None,
    rent_change_pct: Optional[float] = None,
    vacancy_change_pct: Optional[float] = None,
    new_verkehrswert: Optional[float] = None
) -> Dict[str, Any]:
    """
    Simulate what-if scenario.

    Args:
        current_metrics: Current property metrics
        new_loan_amount: Additional loan amount
        new_interest_rate: Interest rate for new loan (or override existing)
        rent_change_pct: Rent change percentage (e.g., 5.0 for +5%)
        vacancy_change_pct: Vacancy change in percentage points
        new_verkehrswert: New property value

    Returns:
        Dict with before/after comparison
    """
    # Current values
    current_rent = current_metrics.get('monthly_rent_projected', 0)
    current_debt_service = current_metrics.get('monthly_debt_service', 0)
    current_debt = current_metrics.get('total_outstanding_debt', 0)
    current_dscr = current_metrics.get('dscr')
    current_ltv = current_metrics.get('ltv')
    current_verkehrswert = current_metrics.get('verkehrswert')

    # Calculate new values
    new_rent = current_rent
    new_debt_service = current_debt_service
    new_debt = current_debt
    scenario_parts = []

    # Apply rent change
    if rent_change_pct is not None:
        new_rent = current_rent * (1 + rent_change_pct / 100)
        scenario_parts.append(f"Miete {rent_change_pct:+.1f}%")

    # Apply new loan
    if new_loan_amount is not None and new_loan_amount > 0:
        rate = new_interest_rate if new_interest_rate is not None else 4.0  # Default 4%
        additional_interest = calculate_monthly_interest(new_loan_amount, rate)
        additional_principal = calculate_monthly_principal(new_loan_amount, 2.0)  # Assume 2% amortization
        new_debt_service += additional_interest + additional_principal
        new_debt += new_loan_amount
        scenario_parts.append(f"Neues Darlehen {new_loan_amount:,.0f} EUR @ {rate:.2f}%")

    # Use new property value if provided
    final_verkehrswert = new_verkehrswert if new_verkehrswert else current_verkehrswert

    # Calculate new metrics
    new_noi = new_rent  # Simplified
    new_cashflow = new_noi - new_debt_service
    new_dscr = calculate_dscr(new_noi, new_debt_service)
    new_ltv = calculate_ltv(new_debt, final_verkehrswert) if final_verkehrswert else None

    # Build result
    def make_delta(before: float, after: float) -> Dict[str, Any]:
        delta = after - before
        delta_pct = (delta / before * 100) if before != 0 else None
        return {
            'before': before,
            'after': after,
            'delta': delta,
            'delta_pct': delta_pct
        }

    warnings = []
    if new_dscr is not None and new_dscr < 1.0:
        warnings.append("DSCR unter 1.0 - Cashflow negativ")
    if new_ltv is not None and new_ltv > 80:
        warnings.append("LTV ueber 80% - hohes Beleihungsrisiko")
    if new_cashflow < 0:
        warnings.append("Negativer monatlicher Cashflow")

    return {
        'scenario_description': "; ".join(scenario_parts) if scenario_parts else "Keine Aenderungen",
        'monthly_rent': make_delta(current_rent, new_rent),
        'monthly_debt_service': make_delta(current_debt_service, new_debt_service),
        'monthly_cashflow': make_delta(current_rent - current_debt_service, new_cashflow),
        'dscr': make_delta(current_dscr or 0, new_dscr or 0),
        'ltv': make_delta(current_ltv or 0, new_ltv or 0) if new_ltv or current_ltv else None,
        'warnings': warnings,
        'is_viable': new_cashflow >= 0 and (new_dscr is None or new_dscr >= 1.0)
    }


def fuzzy_search(query: str, items: List[Dict[str, Any]], key: str = 'name') -> List[Dict[str, Any]]:
    """
    Simple fuzzy search on items.

    Args:
        query: Search query
        items: List of dicts to search
        key: Key to search in

    Returns:
        Sorted list of matches with relevance scores
    """
    query_lower = query.lower()
    results = []

    for item in items:
        name = item.get(key, '').lower()
        if not name:
            continue

        score = 0.0

        # Exact match
        if name == query_lower:
            score = 1.0
        # Starts with query
        elif name.startswith(query_lower):
            score = 0.9
        # Contains query
        elif query_lower in name:
            score = 0.7
        # Individual words match
        else:
            query_words = query_lower.split()
            matches = sum(1 for w in query_words if w in name)
            if matches > 0:
                score = 0.5 * (matches / len(query_words))

        if score > 0:
            results.append({**item, 'relevance_score': score})

    return sorted(results, key=lambda x: x['relevance_score'], reverse=True)


# =============================================================================
# NEW CALCULATION FUNCTIONS FOR ADDITIONAL TOOLS
# =============================================================================

def get_unit_type_category(unit_type: str) -> str:
    """Klassifiziert Einheit als 'wohnen' oder 'gewerbe' für Leerstandsanalyse."""
    ut = unit_type.lower() if unit_type else ""
    gewerbe_keywords = ['gewerbe', 'laden', 'büro', 'buero', 'praxis', 'gastro', 'restaurant']
    for kw in gewerbe_keywords:
        if kw in ut:
            return 'gewerbe'
    return 'wohnen'


def analyze_vacancy(units: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detailed vacancy analysis - aufgeteilt nach Kategorien wie Rent Roll Generator.

    Erweitert um:
    - WorkflowStatus-Kategorisierung
    - Wohnen/Gewerbe-Split

    Args:
        units: List of unit dicts

    Returns:
        Dict with vacancy details by category (main, cellar, parking, bike)
    """
    # Klassifiziere und sammle leere Einheiten pro Kategorie
    vacant_by_category = {
        'main': [],
        'cellar': [],
        'parking': [],
        'bike': []
    }
    total_by_category = {
        'main': 0,
        'cellar': 0,
        'parking': 0,
        'bike': 0
    }
    by_status = {}
    by_workflow_status = {}

    # NEU: Wohnen/Gewerbe-Split
    by_unit_type = {
        'wohnen': {'vacant_count': 0, 'total': 0, 'potential_rent': 0, 'area': 0},
        'gewerbe': {'vacant_count': 0, 'total': 0, 'potential_rent': 0, 'area': 0}
    }

    for unit in units:
        category = classify_unit_for_metrics(unit)
        if category == 'excluded':
            continue

        total_by_category[category] += 1

        # Wohnen/Gewerbe nur für main_units
        if category == 'main':
            unit_type_cat = get_unit_type_category(unit.get('unit_type', ''))
            by_unit_type[unit_type_cat]['total'] += 1

        if unit.get('is_vacant', False):
            status = unit.get('status', 'leer').lower()
            by_status[status] = by_status.get(status, 0) + 1

            # WorkflowStatus (falls verfügbar)
            workflow_status = unit.get('workflow_status', '')
            ws_label = WORKFLOW_STATUS_MAPPING.get(str(workflow_status), 'Nicht kategorisiert')
            by_workflow_status[ws_label] = by_workflow_status.get(ws_label, 0) + 1

            projected_rent = unit.get('net_rent_projected', 0) or unit.get('net_rent', 0) or 0
            area = unit.get('area_sqm', 0) or 0
            rent_per_sqm = projected_rent / area if area > 0 else 0

            vacant_info = {
                'id': unit.get('id', 0),
                'unit_number': unit.get('unit_number', ''),
                'unit_name': unit.get('unit_name', ''),  # Falls verfügbar
                'unit_type': unit.get('unit_type', ''),
                'status': unit.get('status', ''),
                'workflow_status': ws_label,
                'projected_rent': projected_rent,
                'area_sqm': area,
                'rent_per_sqm': round(rent_per_sqm, 2),
                'category': category
            }
            vacant_by_category[category].append(vacant_info)

            # Wohnen/Gewerbe für main_units
            if category == 'main':
                unit_type_cat = get_unit_type_category(unit.get('unit_type', ''))
                by_unit_type[unit_type_cat]['vacant_count'] += 1
                by_unit_type[unit_type_cat]['potential_rent'] += projected_rent
                by_unit_type[unit_type_cat]['area'] += area

    # Berechne Metriken pro Kategorie
    def calc_vacancy_metrics(vacant_list, total):
        vacant_count = len(vacant_list)
        vacancy_rate = (vacant_count / total * 100) if total > 0 else 0
        potential_rent = sum(v['projected_rent'] for v in vacant_list)
        return {
            'vacant_count': vacant_count,
            'total': total,
            'vacancy_rate': round(vacancy_rate, 2),
            'potential_monthly_rent': potential_rent,
            'potential_annual_rent': potential_rent * 12,
            'units': vacant_list
        }

    main_vacancy = calc_vacancy_metrics(vacant_by_category['main'], total_by_category['main'])
    cellar_vacancy = calc_vacancy_metrics(vacant_by_category['cellar'], total_by_category['cellar'])
    parking_vacancy = calc_vacancy_metrics(vacant_by_category['parking'], total_by_category['parking'])
    bike_vacancy = calc_vacancy_metrics(vacant_by_category['bike'], total_by_category['bike'])

    # Alle leeren Einheiten flach (für Rückwärtskompatibilität)
    all_vacant = (vacant_by_category['main'] + vacant_by_category['cellar'] +
                  vacant_by_category['parking'] + vacant_by_category['bike'])

    # Hauptkennzahlen NUR aus main_units (wie Generator)
    total_main = total_by_category['main']
    vacant_main = len(vacant_by_category['main'])

    potential_monthly_main = sum(v['projected_rent'] for v in vacant_by_category['main'])
    potential_monthly_all = sum(v['projected_rent'] for v in all_vacant)

    # Finalisiere by_unit_type mit Vacancy-Rates
    for cat in ['wohnen', 'gewerbe']:
        total = by_unit_type[cat]['total']
        vacant = by_unit_type[cat]['vacant_count']
        by_unit_type[cat]['vacancy_rate'] = round((vacant / total * 100) if total > 0 else 0, 2)
        by_unit_type[cat]['potential_monthly_rent'] = by_unit_type[cat]['potential_rent']
        by_unit_type[cat]['potential_annual_rent'] = by_unit_type[cat]['potential_rent'] * 12

    return {
        # Hauptkennzahlen (nur main_units für Quote)
        'vacant_units': all_vacant,  # Alle für Detailansicht
        'total_units': total_main,   # Nur Haupteinheiten
        'vacant_count': vacant_main, # Nur Haupteinheiten
        'vacancy_rate': round((vacant_main / total_main * 100) if total_main > 0 else 0, 2),
        'potential_monthly_rent': potential_monthly_main,  # Nur main
        'potential_annual_rent': potential_monthly_main * 12,
        'rent_loss_monthly': potential_monthly_main,
        'rent_loss_annual': potential_monthly_main * 12,
        'by_status': by_status,
        'by_workflow_status': by_workflow_status,  # NEU

        # Detaillierte Aufschlüsselung pro Kategorie
        'by_category': {
            'main': main_vacancy,
            'cellar': cellar_vacancy,
            'parking': parking_vacancy,
            'bike': bike_vacancy
        },

        # NEU: Wohnen/Gewerbe-Split
        'by_unit_type': by_unit_type,

        # Gesamtpotenzial aller Kategorien
        'total_potential_monthly': potential_monthly_all,
        'total_potential_annual': potential_monthly_all * 12
    }


def calculate_refinancing_scenarios(
    mortgage: Dict[str, Any],
    monthly_noi: float,
    rate_scenarios: List[float] = None
) -> List[Dict[str, Any]]:
    """
    Calculate refinancing scenarios for a mortgage.

    Args:
        mortgage: Mortgage dict
        monthly_noi: Monthly NOI for DSCR calculation
        rate_scenarios: List of interest rates to simulate (default: 3%, 4%, 5%, 6%)

    Returns:
        List of scenario dicts
    """
    if rate_scenarios is None:
        rate_scenarios = [3.0, 4.0, 5.0, 6.0]

    balance = mortgage.get('outstanding_balance', 0)
    current_rate = mortgage.get('interest_rate', 0)
    amort_rate = mortgage.get('amortization_rate', 2.0)  # Default 2% if not set

    current_monthly_interest = calculate_monthly_interest(balance, current_rate)
    current_monthly_principal = calculate_monthly_principal(balance, amort_rate)
    current_monthly_payment = current_monthly_interest + current_monthly_principal

    scenarios = []
    for new_rate in rate_scenarios:
        new_monthly_interest = calculate_monthly_interest(balance, new_rate)
        new_monthly_principal = calculate_monthly_principal(balance, amort_rate)
        new_monthly_payment = new_monthly_interest + new_monthly_principal

        monthly_change = new_monthly_payment - current_monthly_payment
        annual_change = monthly_change * 12

        new_dscr = None
        if new_monthly_payment > 0 and monthly_noi > 0:
            new_dscr = monthly_noi / new_monthly_payment

        is_viable = new_dscr is None or new_dscr >= 1.0

        scenarios.append({
            'new_interest_rate': new_rate,
            'new_monthly_interest': round(new_monthly_interest, 2),
            'new_monthly_payment': round(new_monthly_payment, 2),
            'monthly_change': round(monthly_change, 2),
            'annual_change': round(annual_change, 2),
            'new_dscr': round(new_dscr, 2) if new_dscr else None,
            'is_viable': is_viable
        })

    return scenarios


def calculate_days_until(date_str: Optional[str]) -> int:
    """
    Calculate days until a date.

    Args:
        date_str: Date string in DD.MM.YYYY format

    Returns:
        Days until date (negative if past)
    """
    if not date_str:
        return 9999  # Far future if no date

    from datetime import datetime

    try:
        for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%m/%d/%Y']:
            try:
                target = datetime.strptime(date_str.split(' ')[0], fmt)
                delta = target - datetime.now()
                return delta.days
            except (ValueError, TypeError):
                continue
        return 9999
    except Exception:
        return 9999


def aggregate_portfolio_metrics(
    properties_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Aggregate metrics across multiple properties.

    Erweitert um Ergebnisrechnung-konforme Kennzahlen:
    - total_mortgages (Anzahl Darlehen)
    - debt_ratio (Verschuldungsgrad)
    - interest_coverage_ratio (Deckungsgrad Miete/Zinsen)
    - surplus_before_principal (Überschuss vor Tilgung)
    - cashflow_ratio

    Args:
        properties_data: List of property data dicts (each with units, mortgages, metrics)

    Returns:
        Dict with aggregated portfolio metrics
    """
    total_units = 0
    occupied_units = 0
    vacant_units = 0

    total_rent_actual = 0.0
    total_rent_projected = 0.0
    total_debt = 0.0
    total_debt_service = 0.0
    total_interest = 0.0
    total_principal = 0.0
    total_cashflow = 0.0
    total_mortgages = 0

    dscr_values = []
    weighted_rates = []  # (balance, rate) pairs

    for prop in properties_data:
        metrics = prop.get('metrics', {})

        total_units += metrics.get('total_units', 0)
        occupied_units += metrics.get('occupied_units', 0)
        vacant_units += metrics.get('vacant_units', 0)

        total_rent_actual += metrics.get('monthly_rent_actual', 0)
        total_rent_projected += metrics.get('monthly_rent_projected', 0)
        total_debt += metrics.get('total_outstanding_debt', 0)
        total_debt_service += metrics.get('monthly_debt_service', 0)
        total_interest += metrics.get('monthly_interest', 0)
        total_principal += metrics.get('monthly_principal', 0)
        total_cashflow += metrics.get('cashflow_monthly', 0)

        if metrics.get('dscr'):
            dscr_values.append(metrics['dscr'])

        # Collect for weighted average interest rate and count mortgages
        for m in prop.get('mortgages', []):
            total_mortgages += 1
            balance = m.get('outstanding_balance', 0)
            rate = m.get('interest_rate', 0)
            if balance > 0 and rate > 0:
                weighted_rates.append((balance, rate))

    vacancy_rate = (vacant_units / total_units * 100) if total_units > 0 else 0
    avg_dscr = sum(dscr_values) / len(dscr_values) if dscr_values else None

    # Weighted average interest rate
    weighted_avg_rate = None
    if weighted_rates:
        total_weight = sum(b for b, r in weighted_rates)
        if total_weight > 0:
            weighted_avg_rate = sum(b * r for b, r in weighted_rates) / total_weight

    # === NEUE KENNZAHLEN (Ergebnisrechnung-konform) ===
    annual_rent_projected = total_rent_projected * 12

    # Überschuss vor Tilgung = Miete - Zinsen
    surplus_before_principal_monthly = total_rent_projected - total_interest
    surplus_before_principal_annual = surplus_before_principal_monthly * 12

    # Deckungsgrad = Miete / Zinsen (nur Zinsen, nicht Schuldendienst!)
    interest_coverage_ratio = None
    if total_interest > 0:
        interest_coverage_ratio = total_rent_projected / total_interest

    # Cashflow-Quote = (Cashflow / Miete) * 100
    cashflow_ratio = None
    if annual_rent_projected > 0:
        cashflow_ratio = (total_cashflow * 12 / annual_rent_projected) * 100

    # Verschuldungsgrad = Schulden / Jahresmiete
    debt_ratio = None
    if annual_rent_projected > 0:
        debt_ratio = total_debt / annual_rent_projected

    return {
        'total_units': total_units,
        'occupied_units': occupied_units,
        'vacant_units': vacant_units,
        'vacancy_rate': round(vacancy_rate, 2),
        'total_monthly_rent_actual': total_rent_actual,
        'total_monthly_rent_projected': total_rent_projected,
        'total_annual_rent_actual': total_rent_actual * 12,
        'total_annual_rent_projected': annual_rent_projected,
        'total_outstanding_debt': total_debt,
        'total_monthly_interest': total_interest,
        'total_monthly_principal': total_principal,
        'total_monthly_debt_service': total_debt_service,
        'total_annual_interest': total_interest * 12,
        'total_annual_principal': total_principal * 12,
        'total_annual_debt_service': total_debt_service * 12,

        # Überschuss vor Tilgung (NEU)
        'surplus_before_principal_monthly': round(surplus_before_principal_monthly, 2),
        'surplus_before_principal_annual': round(surplus_before_principal_annual, 2),

        # Cashflow
        'total_monthly_cashflow': total_cashflow,
        'total_annual_cashflow': total_cashflow * 12,

        # Kennzahlen
        'average_dscr': round(avg_dscr, 2) if avg_dscr else None,
        'weighted_average_interest_rate': round(weighted_avg_rate, 2) if weighted_avg_rate else None,
        'total_mortgages': total_mortgages,
        'interest_coverage_ratio': round(interest_coverage_ratio, 2) if interest_coverage_ratio else None,
        'cashflow_ratio': round(cashflow_ratio, 2) if cashflow_ratio else None,
        'debt_ratio': round(debt_ratio, 2) if debt_ratio else None
    }
