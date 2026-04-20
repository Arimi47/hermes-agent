# -*- coding: utf-8 -*-
"""
Pydantic Data Models for M-Files MCP Server

Includes:
- Input models for tool parameter validation (FastMCP)
- Output models for structured responses
"""

from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =============================================================================
# ENUMS
# =============================================================================

class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# =============================================================================
# INPUT MODELS (for FastMCP tool validation)
# =============================================================================

class ListPortfoliosInput(BaseModel):
    """Input for mfiles_list_portfolios - no parameters required."""
    model_config = ConfigDict(str_strip_whitespace=True)

    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetPortfolioPropertiesInput(BaseModel):
    """Input for mfiles_get_portfolio_properties."""
    model_config = ConfigDict(str_strip_whitespace=True)

    portfolio_name: str = Field(
        ...,
        description="Name des Portfolios (z.B. 'Portfolio Suede', 'Portfolio Ralf')",
        min_length=1,
        max_length=200
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class PropertyIdentifierInput(BaseModel):
    """Base input for tools that identify a property by ID or name."""
    model_config = ConfigDict(str_strip_whitespace=True)

    property_id: Optional[int] = Field(
        default=None,
        description="M-Files ID der Liegenschaft",
        ge=1
    )
    property_name: Optional[str] = Field(
        default=None,
        description="Name der Liegenschaft (Alternative zu property_id)",
        min_length=1,
        max_length=300
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('property_name')
    @classmethod
    def validate_at_least_one_identifier(cls, v, info):
        """Ensure at least property_id or property_name is provided."""
        # This runs after property_id is already validated
        # We check in the tool itself since validators run per-field
        return v


class GetUnitsInput(PropertyIdentifierInput):
    """Input for mfiles_get_units."""
    pass


class GetMortgagesInput(PropertyIdentifierInput):
    """Input for mfiles_get_mortgages."""
    pass


class GetMetricsInput(PropertyIdentifierInput):
    """Input for mfiles_get_metrics."""
    verkehrswert: Optional[float] = Field(
        default=None,
        description="Verkehrswert in EUR (fuer LTV und Cap Rate Berechnung)",
        ge=0
    )


class SimulateScenarioInput(PropertyIdentifierInput):
    """Input for mfiles_simulate_scenario."""
    new_loan_amount: Optional[float] = Field(
        default=None,
        description="Neues Darlehen in EUR",
        ge=0
    )
    new_interest_rate: Optional[float] = Field(
        default=None,
        description="Zinssatz fuer neues Darlehen in % (z.B. 4.5)",
        ge=0,
        le=100
    )
    rent_change_pct: Optional[float] = Field(
        default=None,
        description="Mieterhoehung/-senkung in % (z.B. 5.0 fuer +5%)",
        ge=-100,
        le=1000
    )
    vacancy_change_pct: Optional[float] = Field(
        default=None,
        description="Leerstandsaenderung in Prozentpunkten",
        ge=-100,
        le=100
    )
    new_verkehrswert: Optional[float] = Field(
        default=None,
        description="Neuer Verkehrswert in EUR",
        ge=0
    )


class SearchInput(BaseModel):
    """Input for mfiles_search."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        description="Suchbegriff (Name oder Teil des Namens)",
        min_length=1,
        max_length=200
    )
    portfolio: Optional[str] = Field(
        default=None,
        description="Optional: Suche auf bestimmtes Portfolio einschraenken"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetTenantsInput(PropertyIdentifierInput):
    """Input for mfiles_get_tenants."""
    pass


class GetVacancyInput(PropertyIdentifierInput):
    """Input for mfiles_get_vacancy."""
    pass


class ComparePropertiesInput(BaseModel):
    """Input for mfiles_compare."""
    model_config = ConfigDict(str_strip_whitespace=True)

    property_ids: Optional[List[int]] = Field(
        default=None,
        description="Liste von M-Files IDs der zu vergleichenden Liegenschaften"
    )
    property_names: Optional[List[str]] = Field(
        default=None,
        description="Liste von Namen der zu vergleichenden Liegenschaften"
    )
    verkehrswerte: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional: Verkehrswerte als Dict {property_id: wert}"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('property_names')
    @classmethod
    def validate_at_least_one_list(cls, v, info):
        """Ensure at least one property list is provided."""
        return v


class RefinancingScenariosInput(PropertyIdentifierInput):
    """Input for mfiles_refinancing_scenarios."""
    rate_scenarios: Optional[List[float]] = Field(
        default=None,
        description="Zinssaetze zu simulieren in % (Standard: [3.0, 4.0, 5.0, 6.0])"
    )


class PortfolioSummaryInput(BaseModel):
    """Input for mfiles_portfolio_summary."""
    model_config = ConfigDict(str_strip_whitespace=True)

    portfolio_name: str = Field(
        ...,
        description="Name des Portfolios",
        min_length=1,
        max_length=200
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class ExpiringLeasesInput(BaseModel):
    """Input for mfiles_expiring_leases."""
    model_config = ConfigDict(str_strip_whitespace=True)

    property_id: Optional[int] = Field(
        default=None,
        description="M-Files ID der Liegenschaft (optional)",
        ge=1
    )
    property_name: Optional[str] = Field(
        default=None,
        description="Name der Liegenschaft (optional)"
    )
    portfolio_name: Optional[str] = Field(
        default=None,
        description="Name des Portfolios (optional, fuer portfolioweite Suche)"
    )
    months_ahead: int = Field(
        default=12,
        description="Monate vorausschauen (Standard: 12)",
        ge=1,
        le=120
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class UpcomingRefinancingInput(BaseModel):
    """Input for mfiles_upcoming_refinancing."""
    model_config = ConfigDict(str_strip_whitespace=True)

    property_id: Optional[int] = Field(
        default=None,
        description="M-Files ID der Liegenschaft (optional)",
        ge=1
    )
    property_name: Optional[str] = Field(
        default=None,
        description="Name der Liegenschaft (optional)"
    )
    portfolio_name: Optional[str] = Field(
        default=None,
        description="Name des Portfolios (optional, fuer portfolioweite Suche)"
    )
    months_ahead: int = Field(
        default=24,
        description="Monate vorausschauen (Standard: 24)",
        ge=1,
        le=120
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetInvoicesInput(PropertyIdentifierInput):
    """Input for mfiles_get_invoices."""
    pass


class GetUnitDocsInput(BaseModel):
    """Input for mfiles_get_unit_docs."""
    model_config = ConfigDict(str_strip_whitespace=True)

    unit_id: Optional[int] = Field(
        default=None,
        description="M-Files ID der Einheit",
        ge=1
    )
    unit_name: Optional[str] = Field(
        default=None,
        description="Name/Nummer der Einheit (Alternative zu unit_id, erfordert property_id/name)"
    )
    property_id: Optional[int] = Field(
        default=None,
        description="M-Files ID der Liegenschaft (wenn unit_name verwendet wird)",
        ge=1
    )
    property_name: Optional[str] = Field(
        default=None,
        description="Name der Liegenschaft (wenn unit_name verwendet wird)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetPropertyDocsInput(PropertyIdentifierInput):
    """Input for mfiles_get_property_docs."""
    include_unit_docs: bool = Field(
        default=True,
        description="Auch Dokumente aller Einheiten abrufen (Standard: true)"
    )


class DownloadDocInput(BaseModel):
    """Input for mfiles_download_doc."""
    model_config = ConfigDict(str_strip_whitespace=True)

    object_type: int = Field(
        ...,
        description="M-Files Objekttyp (130=Liegenschaft, 132=Einheit, 0=Dokument)"
    )
    object_id: int = Field(
        ...,
        description="M-Files ID des Objekts",
        ge=1
    )
    file_id: int = Field(
        ...,
        description="ID der Datei (aus mfiles_get_unit_docs/mfiles_get_property_docs)",
        ge=1
    )
    extract_text: bool = Field(
        default=True,
        description="Bei PDFs Text extrahieren (Standard: true)"
    )


# =============================================================================
# OUTPUT MODELS
# =============================================================================

class PortfolioInfo(BaseModel):
    """Portfolio with property count"""
    name: str
    property_count: int = 0


class PortfolioList(BaseModel):
    """List of all portfolios"""
    portfolios: List[PortfolioInfo]
    total_portfolios: int
    total_properties: int


class PropertySummary(BaseModel):
    """Property summary with key metrics"""
    id: int
    name: str
    monthly_rent: float = 0.0
    monthly_rent_projected: float = 0.0
    vacancy_rate: float = 0.0
    dscr: Optional[float] = None
    ltv: Optional[float] = None
    unit_count: int = 0
    vacant_unit_count: int = 0


class PortfolioProperties(BaseModel):
    """Properties belonging to a portfolio"""
    portfolio_name: str
    properties: List[PropertySummary]
    total_monthly_rent: float
    total_monthly_rent_projected: float
    average_vacancy_rate: float
    average_dscr: Optional[float] = None
    average_ltv: Optional[float] = None


class UnitInfo(BaseModel):
    """Unit (Einheit) details - erweitert für Rent Roll Kompatibilität"""
    id: int
    unit_number: str = ""
    unit_name: str = ""  # z.B. "VH 2. OG links" (aus M-Files Name Property)
    unit_type: str = ""
    unit_category: str = "main"  # main, cellar, parking, bike, excluded
    status: str = ""
    net_rent: float = 0.0
    net_rent_projected: float = 0.0
    area_sqm: float = 0.0
    tenant: str = ""
    is_vacant: bool = False
    is_parking: bool = False
    is_cellar: bool = False
    is_bike: bool = False


class CategorySummary(BaseModel):
    """Summary metrics for a unit category"""
    total: int = 0
    occupied: int = 0
    vacant: int = 0
    vacancy_rate: float = 0.0
    rent_actual: float = 0.0
    rent_projected: float = 0.0
    area_sqm: float = 0.0


class PropertyUnits(BaseModel):
    """All units for a property - strukturiert wie Rent Roll Generator"""
    property_id: int
    property_name: str

    # Einheiten nach Kategorie (wie Generator: main, cellar, parking, bike)
    main_units: List[UnitInfo] = Field(default_factory=list)     # Wohnen + Gewerbe
    cellar_units: List[UnitInfo] = Field(default_factory=list)   # Keller
    parking_units: List[UnitInfo] = Field(default_factory=list)  # Stellplätze
    bike_units: List[UnitInfo] = Field(default_factory=list)     # Fahrradstellplätze

    # Legacy: Alle Einheiten flach (für Rückwärtskompatibilität)
    units: List[UnitInfo] = Field(default_factory=list)

    # Zusammenfassung pro Kategorie
    summary: Dict[str, CategorySummary] = Field(default_factory=dict)

    # Hauptkennzahlen (NUR main_units für Leerstandsquote!)
    total_units: int = 0        # Nur Haupteinheiten (Wohnen + Gewerbe)
    total_parking: int = 0
    total_cellar: int = 0
    total_bike: int = 0
    total_rent: float = 0.0               # main + parking
    total_rent_projected: float = 0.0     # main + parking
    total_area_sqm: float = 0.0           # Nur main_units
    vacancy_rate: float = 0.0             # NUR main_units Quote!

    # Separate Parking-Miete für Fußnote (wie Generator)
    parking_rent: float = 0.0
    parking_rent_note: str = ""  # z.B. "enthält 426,31€ für 5 vermietete Stellplätze"


class MortgageInfo(BaseModel):
    """Mortgage/Loan details - erweitert analog Darlehensübersicht Generator"""
    id: int
    bank: str = ""
    contract_number: str = ""  # Vertragsnummer
    loan_type: str = ""  # Darlehenstyp

    # Beträge
    loan_amount: float = 0.0  # Ursprüngliche Darlehenssumme
    outstanding_balance: float = 0.0  # Aktueller Darlehensstand
    balance_date: Optional[str] = None  # Datum des Darlehensstands

    # Konditionen
    interest_rate: float = 0.0  # Zinssatz %
    amortization_rate: float = 0.0  # Tilgungssatz %
    monthly_payment: float = 0.0  # Monatliche Rate
    payment_interval: str = ""  # Zahlungsintervall
    debit_date: str = ""  # Abbuchungstag

    # Laufzeiten
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    fixed_rate_until: Optional[str] = None  # Zinsbindungsende

    # Verknüpfungen
    linked_properties: List[str] = Field(default_factory=list)


class PropertyMortgages(BaseModel):
    """All mortgages for a property"""
    property_id: int
    property_name: str
    mortgages: List[MortgageInfo]
    total_outstanding: float
    total_monthly_interest: float
    total_monthly_payment: float


class PropertyMetrics(BaseModel):
    """Comprehensive property metrics - erweitert für Ergebnisrechnung-Kompatibilität"""
    property_id: int
    property_name: str

    # Rent metrics
    monthly_rent_actual: float = 0.0
    monthly_rent_projected: float = 0.0
    annual_rent_actual: float = 0.0
    annual_rent_projected: float = 0.0

    # Unit metrics
    total_units: int = 0
    occupied_units: int = 0
    vacant_units: int = 0
    vacancy_rate: float = 0.0
    total_area_sqm: float = 0.0

    # Debt metrics
    total_outstanding_debt: float = 0.0
    monthly_interest: float = 0.0
    monthly_principal: float = 0.0  # Tilgung = Annuität - Zinsen
    monthly_debt_service: float = 0.0
    annual_interest: float = 0.0
    annual_principal: float = 0.0
    annual_debt_service: float = 0.0

    # Key ratios
    dscr: Optional[float] = None  # Debt Service Coverage Ratio
    ltv: Optional[float] = None   # Loan-to-Value
    cap_rate: Optional[float] = None  # Capitalization Rate

    # NEU: Zusätzliche Kennzahlen (Ergebnisrechnung-konform)
    interest_coverage_ratio: Optional[float] = None  # Deckungsgrad = Miete / Zinsen
    cashflow_ratio: Optional[float] = None  # Cashflow-Quote = (Cashflow / Miete) * 100
    debt_ratio: Optional[float] = None  # Verschuldungsgrad = Schulden / Jahresmiete

    # NOI & Cashflow (simplified)
    noi_monthly: float = 0.0  # Net Operating Income
    noi_annual: float = 0.0

    # NEU: Überschuss vor Tilgung (wie Ergebnisrechnung)
    surplus_before_principal_monthly: float = 0.0  # Miete - Zinsen
    surplus_before_principal_annual: float = 0.0

    # Restüberschuss / Cashflow (nach Tilgung)
    cashflow_monthly: float = 0.0  # After debt service
    cashflow_annual: float = 0.0
    final_surplus_annual: float = 0.0  # Alias für Klarheit

    # NEU: Verschuldung pro m² (für Deckblatt)
    debt_per_sqm: Optional[float] = None

    # NEU: Miet-Breakdown (Wohnen/Gewerbe/Parking)
    wohn_monthly: float = 0.0
    wohn_annual: float = 0.0
    wohn_area: float = 0.0
    wohn_per_sqm: float = 0.0
    gewerbe_monthly: float = 0.0
    gewerbe_annual: float = 0.0
    gewerbe_area: float = 0.0
    gewerbe_per_sqm: float = 0.0
    parking_monthly: float = 0.0
    parking_annual: float = 0.0
    parking_count: int = 0

    # === E-Bike-Sonderfelder (Task 32) ===
    ebike_total: int = 0  # Gesamtanzahl E-Bike-Garagen
    ebike_empty_count: int = 0  # Anzahl leere E-Bike-Garagen
    ebike_occupied_count: int = 0  # Anzahl vermietete E-Bike-Garagen
    ebike_projected_rent: float = 0.0  # Potenzialmiete leere E-Bikes
    ebike_occupied_rent: float = 0.0  # Aktuelle Miete vermietete E-Bikes

    # === PROJEKTIERTE KENNZAHLEN (Task 33) ===
    # Separates Kennzahlen-Set mit Projektion für leere Einheiten
    total_rent_with_projection_monthly: float = 0.0  # Ist-Miete + Potenzial leerer Einheiten
    total_rent_with_projection_annual: float = 0.0
    potential_rent_vacant_monthly: float = 0.0  # Nur Potenzialmiete aus Leerstand
    potential_rent_vacant_annual: float = 0.0
    noi_projected_monthly: float = 0.0  # NOI mit Projektion
    noi_projected_annual: float = 0.0
    surplus_before_principal_projected_monthly: float = 0.0  # Überschuss vor Tilgung (mit Projektion)
    surplus_before_principal_projected_annual: float = 0.0
    cashflow_projected_monthly: float = 0.0  # Cashflow mit Projektion
    cashflow_projected_annual: float = 0.0
    dscr_projected: Optional[float] = None  # DSCR mit Projektion
    interest_coverage_ratio_projected: Optional[float] = None  # Deckungsgrad mit Projektion
    cashflow_ratio_projected: Optional[float] = None  # Cashflow-Quote mit Projektion

    # Input parameters
    verkehrswert: Optional[float] = None
    verkehrswert_source: str = "not provided"


class ScenarioInput(BaseModel):
    """Input for scenario simulation"""
    property_id: Optional[int] = None
    property_name: Optional[str] = None

    # Simulation parameters
    new_loan_amount: Optional[float] = None
    new_interest_rate: Optional[float] = None
    rent_change_pct: Optional[float] = None  # e.g., 5.0 for +5%
    vacancy_change_pct: Optional[float] = None  # e.g., -2.0 for -2%

    # Optional: New property value for LTV
    new_verkehrswert: Optional[float] = None


class ScenarioDelta(BaseModel):
    """Change values for before/after comparison"""
    before: float
    after: float
    delta: float
    delta_pct: Optional[float] = None


# Status-Maps (for write operations)

MIETERMELDUNG_STATUS_MAP = {
    "eingegangen": 184,
    "in-pruefung": 185,
    "berechtigt": 186,
    "in-behebung": 187,
    "unberechtigt": 188,
    "erledigt": 189,
    "in-abrechnung": 204,
    "nachfrage": 212,
    "aufgeschoben": 339,
}

ANGEBOT_STATUS_MAP = {
    "angenommen": 208,
    "abgelehnt": 207,
    "nachverhandeln": 206,
}

SANIERUNG_STATUS_MAP = {
    "durchfuehrung": 193,
    "abrechnung": 204,
    "nachfrage": 212,
    "ausschreibung-schwarzbaum": 224,
    "vergabe": 225,
    "ausschreibung": 226,
    "abnahme": 230,
    "abgeschlossen": 231,
}


class ScenarioResult(BaseModel):
    """Result of a what-if scenario simulation"""
    property_id: int
    property_name: str
    scenario_description: str
    monthly_rent: ScenarioDelta
    monthly_debt_service: ScenarioDelta
    monthly_cashflow: ScenarioDelta
    dscr: ScenarioDelta
    ltv: Optional[ScenarioDelta] = None

    # Warnings
    warnings: List[str] = Field(default_factory=list)
    is_viable: bool = True


class SearchResult(BaseModel):
    """Property search result"""
    id: int
    name: str
    portfolio: str = ""
    relevance_score: float = 1.0


class SearchResults(BaseModel):
    """Search results with metadata"""
    query: str
    results: List[SearchResult]
    total_found: int


# =============================================================================
# NEW MODELS FOR ADDITIONAL TOOLS
# =============================================================================

class TenantInfo(BaseModel):
    """Tenant/Mieter details - erweitert für Rent Roll Kompatibilität"""
    name: str
    unit_id: int
    unit_number: str = ""
    unit_name: str = ""  # z.B. "VH 2. OG links"
    unit_type: str = ""
    unit_category: str = "main"  # main, cellar, parking, bike

    # Miete
    monthly_rent: float = 0.0  # Netto
    betriebskosten: float = 0.0
    heizkosten: float = 0.0
    bruttomiete: float = 0.0  # Warmmiete
    rent_per_sqm: float = 0.0

    # Fläche
    area_sqm: float = 0.0

    # Vertrag
    status: str = ""
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None  # "unbegr." für unbefristet
    has_option: bool = False
    option_details: str = ""


class PropertyTenants(BaseModel):
    """All tenants for a property - strukturiert wie Rent Roll Generator"""
    property_id: int
    property_name: str

    # Mieter nach Kategorie
    main_tenants: List[TenantInfo] = Field(default_factory=list)    # Wohnen + Gewerbe
    cellar_tenants: List[TenantInfo] = Field(default_factory=list)  # Keller
    parking_tenants: List[TenantInfo] = Field(default_factory=list) # Stellplätze
    bike_tenants: List[TenantInfo] = Field(default_factory=list)    # Fahrradstellplätze

    # Legacy: Alle Mieter flach
    tenants: List[TenantInfo] = Field(default_factory=list)

    # Statistiken (nur main_units)
    total_tenants: int = 0
    total_monthly_rent: float = 0.0
    occupancy_rate: float = 0.0

    # Zusätzliche Statistiken
    residential_area: float = 0.0
    commercial_area: float = 0.0
    total_area: float = 0.0


class VacantUnitInfo(BaseModel):
    """Details of a vacant unit - erweitert für Kategorisierung"""
    id: int
    unit_number: str = ""
    unit_name: str = ""  # z.B. "VH 2. OG links"
    unit_type: str = ""
    unit_category: str = "main"  # main, cellar, parking, bike
    status: str = ""  # leer, gekuendigt
    projected_rent: float = 0.0
    area_sqm: float = 0.0
    rent_per_sqm: float = 0.0


class VacancyCategorySummary(BaseModel):
    """Vacancy summary for a unit category"""
    vacant_count: int = 0
    total: int = 0
    vacancy_rate: float = 0.0
    potential_monthly_rent: float = 0.0
    potential_annual_rent: float = 0.0
    units: List[VacantUnitInfo] = Field(default_factory=list)


class UnitTypeSummary(BaseModel):
    """Vacancy summary for unit type (wohnen/gewerbe)"""
    vacant_count: int = 0
    total: int = 0
    vacancy_rate: float = 0.0
    potential_monthly_rent: float = 0.0
    potential_annual_rent: float = 0.0
    area: float = 0.0


class VacancyAnalysis(BaseModel):
    """Detailed vacancy analysis - strukturiert wie Rent Roll Generator"""
    property_id: int
    property_name: str

    # Leere Einheiten flach (alle)
    vacant_units: List[VacantUnitInfo] = Field(default_factory=list)

    # Hauptkennzahlen (NUR main_units!)
    total_units: int = 0      # Nur Haupteinheiten
    vacant_count: int = 0     # Nur Haupteinheiten
    vacancy_rate: float = 0.0 # Nur Haupteinheiten
    potential_monthly_rent: float = 0.0  # Nur main_units
    potential_annual_rent: float = 0.0
    rent_loss_monthly: float = 0.0
    rent_loss_annual: float = 0.0

    # Aufschlüsselung nach Status
    by_status: Dict[str, int] = Field(default_factory=dict)

    # NEU: Aufschlüsselung nach WorkflowStatus (für Sanierung, Makler etc.)
    by_workflow_status: Dict[str, int] = Field(default_factory=dict)

    # Aufschlüsselung nach Kategorie
    by_category: Dict[str, VacancyCategorySummary] = Field(default_factory=dict)

    # NEU: Aufschlüsselung nach Einheitentyp (Wohnen/Gewerbe)
    by_unit_type: Dict[str, UnitTypeSummary] = Field(default_factory=dict)

    # Gesamtpotenzial aller Kategorien
    total_potential_monthly: float = 0.0
    total_potential_annual: float = 0.0


class PropertyComparison(BaseModel):
    """Comparison of multiple properties"""
    properties: List[PropertyMetrics]
    best_dscr: Optional[str] = None
    best_vacancy: Optional[str] = None
    best_cashflow: Optional[str] = None
    total_portfolio_rent: float = 0.0
    total_portfolio_debt: float = 0.0
    average_vacancy_rate: float = 0.0


class RefinancingScenario(BaseModel):
    """Single refinancing scenario"""
    new_interest_rate: float
    new_monthly_interest: float
    new_monthly_payment: float
    monthly_change: float
    annual_change: float
    new_dscr: Optional[float] = None
    is_viable: bool = True


class MortgageRefinancing(BaseModel):
    """Refinancing analysis for a mortgage"""
    mortgage_id: int
    bank: str
    outstanding_balance: float
    current_interest_rate: float
    current_monthly_payment: float
    fixed_rate_until: Optional[str] = None
    months_until_refinancing: int = 0
    scenarios: List[RefinancingScenario]


class PropertyRefinancingAnalysis(BaseModel):
    """Refinancing analysis for a property"""
    property_id: int
    property_name: str
    mortgages: List[MortgageRefinancing]
    current_total_payment: float
    current_dscr: Optional[float] = None
    warning: Optional[str] = None


class PortfolioSummary(BaseModel):
    """Aggregated portfolio metrics - erweitert für Ergebnisrechnung-Kompatibilität"""
    portfolio_name: str
    property_count: int
    total_units: int
    occupied_units: int
    vacant_units: int
    vacancy_rate: float

    # Rent
    total_monthly_rent_actual: float
    total_monthly_rent_projected: float
    total_annual_rent_actual: float
    total_annual_rent_projected: float

    # Debt
    total_outstanding_debt: float
    total_monthly_interest: float = 0.0
    total_monthly_principal: float = 0.0
    total_monthly_debt_service: float
    total_annual_interest: float = 0.0
    total_annual_principal: float = 0.0
    total_annual_debt_service: float

    # NEU: Überschuss vor Tilgung (wie Ergebnisrechnung)
    surplus_before_principal_monthly: float = 0.0
    surplus_before_principal_annual: float = 0.0

    # Cashflow
    total_monthly_cashflow: float
    total_annual_cashflow: float

    # Averages
    average_dscr: Optional[float] = None
    weighted_average_interest_rate: Optional[float] = None

    # NEU: Zusätzliche Kennzahlen
    total_mortgages: int = 0
    interest_coverage_ratio: Optional[float] = None  # Deckungsgrad = Miete / Zinsen
    cashflow_ratio: Optional[float] = None  # Cashflow-Quote = (Cashflow / Miete) * 100
    debt_ratio: Optional[float] = None  # Verschuldungsgrad = Schulden / Jahresmiete

    # Breakdown by property
    property_breakdown: List[PropertySummary] = Field(default_factory=list)


class ExpiringItem(BaseModel):
    """Item that expires within a timeframe"""
    id: int
    name: str
    property_id: int
    property_name: str
    expiry_date: str
    days_until_expiry: int
    monthly_amount: float = 0.0


class ExpiringLeases(BaseModel):
    """Leases expiring within timeframe"""
    property_id: Optional[int] = None
    property_name: Optional[str] = None
    portfolio_name: Optional[str] = None
    months_ahead: int
    expiring_leases: List[ExpiringItem]
    total_count: int
    total_monthly_rent_at_risk: float


class UpcomingRefinancing(BaseModel):
    """Mortgages needing refinancing soon"""
    property_id: Optional[int] = None
    property_name: Optional[str] = None
    portfolio_name: Optional[str] = None
    months_ahead: int
    mortgages: List[ExpiringItem]
    total_count: int
    total_outstanding_balance: float
    total_monthly_payment_at_risk: float


# =============================================================================
# DOCUMENT MODELS (for accessing contracts, invoices, etc.)
# =============================================================================

class DocumentInfo(BaseModel):
    """Information about a document/file in M-Files"""
    file_id: int
    name: str
    extension: str
    size_bytes: int = 0
    object_type: int
    object_id: int
    version: int = 0
    created_date: Optional[str] = None
    modified_date: Optional[str] = None
    # Contract context (for Mietverträge via Property 1431 - Vermietungsordner)
    contract_id: Optional[int] = None
    contract_name: Optional[str] = None


class ObjectDocuments(BaseModel):
    """Documents attached to an M-Files object"""
    object_type: int
    object_id: int
    object_name: str = ""
    documents: List[DocumentInfo] = Field(default_factory=list)
    total_count: int = 0


class UnitDocuments(BaseModel):
    """Documents for a unit (Einheit) - includes Mietvertraege"""
    unit_id: int
    unit_name: str = ""
    unit_number: str = ""
    tenant: str = ""
    documents: List[DocumentInfo] = Field(default_factory=list)
    total_count: int = 0


class PropertyDocuments(BaseModel):
    """All documents for a property and its units"""
    property_id: int
    property_name: str
    property_documents: List[DocumentInfo] = Field(default_factory=list)
    unit_documents: List[UnitDocuments] = Field(default_factory=list)
    total_property_docs: int = 0
    total_unit_docs: int = 0


class DocumentContent(BaseModel):
    """Content of a downloaded document"""
    file_id: int
    file_name: str
    file_extension: str
    file_size: int = 0
    content_type: str = ""
    # For text/PDF: extracted text content
    text_content: Optional[str] = None
    # For binary: path where file was saved
    saved_path: Optional[str] = None
    # Status
    success: bool = True
    error_message: Optional[str] = None


# =============================================================================
# VERSION HISTORY MODELS
# =============================================================================

# =============================================================================
# VORGÄNGE / OBJECT TYPE DISCOVERY MODELS
# =============================================================================

class DiscoverObjectTypesInput(BaseModel):
    """Input for mfiles_discover_object_types - no parameters required."""
    model_config = ConfigDict(str_strip_whitespace=True)

    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class ObjectTypeInfo(BaseModel):
    """Information about an M-Files object type."""
    id: int
    name: str
    name_plural: str = ""
    real_object_type: bool = True


class ObjectTypeList(BaseModel):
    """List of all object types in the vault."""
    object_types: List[ObjectTypeInfo]
    total_count: int


class ListVorgaengeInput(BaseModel):
    """Input for mfiles_list_vorgaenge."""
    model_config = ConfigDict(str_strip_whitespace=True)

    property_filter: Optional[str] = Field(
        default=None,
        description="Optional: Name der Liegenschaft zum Filtern der Vorgaenge"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetVorgangDetailsInput(BaseModel):
    """Input for mfiles_get_vorgang_details."""
    model_config = ConfigDict(str_strip_whitespace=True)

    vorgang_id: int = Field(
        ...,
        description="M-Files ID des Vorgangs",
        ge=1
    )
    include_documents: bool = Field(
        default=False,
        description="Auch Dokumente des Vorgangs abrufen (Standard: false)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetVorgangDocumentsInput(BaseModel):
    """Input for mfiles_get_vorgang_documents."""
    model_config = ConfigDict(str_strip_whitespace=True)

    vorgang_id: int = Field(
        ...,
        description="M-Files ID des Vorgangs",
        ge=1
    )
    extract_text: bool = Field(
        default=True,
        description="Bei PDFs Text extrahieren (Standard: true)"
    )


class VorgangSummary(BaseModel):
    """Summary of a Vorgang for list view."""
    id: int
    name: str
    class_name: str = ""  # e.g. Mietermeldung, Sanierung, Rechtsstreitigkeiten
    status: str = ""
    workflow_status: str = ""
    linked_properties: List[str] = Field(default_factory=list)
    linked_units: List[str] = Field(default_factory=list)
    linked_companies: List[str] = Field(default_factory=list)
    created_date: Optional[str] = None
    modified_date: Optional[str] = None


class VorgaengeList(BaseModel):
    """List of all Vorgänge."""
    vorgaenge: List[VorgangSummary]
    total_count: int
    property_filter: Optional[str] = None


class LinkedObjectInfo(BaseModel):
    """A linked object reference from a Vorgang."""
    object_type: int
    id: Optional[int] = None
    name: str = ""
    property_name: str = ""  # The M-Files property that links to this


class VorgangDetails(BaseModel):
    """Full details of a Vorgang including all properties."""
    id: int
    object_type: int
    name: str
    class_name: str = ""
    status: str = ""
    workflow_status: str = ""
    all_properties: Dict[str, str] = Field(default_factory=dict)
    linked_properties: List[str] = Field(default_factory=list)
    linked_units: List[str] = Field(default_factory=list)
    linked_companies: List[str] = Field(default_factory=list)
    linked_objects: List[LinkedObjectInfo] = Field(default_factory=list)
    created_date: Optional[str] = None
    modified_date: Optional[str] = None
    created_by: str = ""
    modified_by: str = ""
    documents: List[DocumentInfo] = Field(default_factory=list)
    document_count: int = 0


class VorgangDocumentWithContent(BaseModel):
    """A document from a Vorgang with optional extracted text."""
    file_id: int
    name: str
    extension: str
    size_bytes: int = 0
    object_type: int
    object_id: int
    source: str = ""  # direct, relationship, collectionmember
    text_content: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class VorgangDocuments(BaseModel):
    """All documents from a Vorgang with extracted text."""
    vorgang_id: int
    vorgang_name: str = ""
    documents: List[VorgangDocumentWithContent] = Field(default_factory=list)
    total_count: int = 0


class GetUnitHistoryInput(BaseModel):
    """Input for mfiles_get_unit_history - Versionshistorie einer Einheit."""
    model_config = ConfigDict(str_strip_whitespace=True)

    unit_id: Optional[int] = Field(
        default=None,
        description="M-Files ID der Einheit",
        ge=1
    )
    unit_name: Optional[str] = Field(
        default=None,
        description="Name/Nummer der Einheit (Alternative zu unit_id, erfordert property_id/name)"
    )
    property_id: Optional[int] = Field(
        default=None,
        description="M-Files ID der Liegenschaft (wenn unit_name verwendet wird)",
        ge=1
    )
    property_name: Optional[str] = Field(
        default=None,
        description="Name der Liegenschaft (wenn unit_name verwendet wird)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class UnitVersionEntry(BaseModel):
    """A single version entry in a unit's history."""
    version: int
    modified_date: Optional[str] = None
    modified_by: str = ""
    tenant: str = ""
    status: str = ""  # Einheitenstatus (vermietet/gekündigt/leer)
    workflow_status: str = ""
    net_rent: float = 0.0
    net_rent_projected: float = 0.0
    changes: List[str] = Field(default_factory=list)  # What changed vs previous version


class UnitVersionHistory(BaseModel):
    """Complete version history for a unit."""
    unit_id: int
    unit_name: str = ""
    unit_number: str = ""
    current_status: str = ""
    current_tenant: str = ""
    total_versions: int = 0
    versions: List[UnitVersionEntry] = Field(default_factory=list)
    status_timeline: List[Dict[str, str]] = Field(default_factory=list)


# Status-Maps (for write operations)

MIETERMELDUNG_STATUS_MAP = {
    "eingegangen": 184,
    "in-pruefung": 185,
    "berechtigt": 186,
    "in-behebung": 187,
    "unberechtigt": 188,
    "erledigt": 189,
    "in-abrechnung": 204,
    "nachfrage": 212,
    "aufgeschoben": 339,
}

ANGEBOT_STATUS_MAP = {
    "angenommen": 208,
    "abgelehnt": 207,
    "nachverhandeln": 206,
}

SANIERUNG_STATUS_MAP = {
    "durchfuehrung": 193,
    "abrechnung": 204,
    "nachfrage": 212,
    "ausschreibung-schwarzbaum": 224,
    "vergabe": 225,
    "ausschreibung": 226,
    "abnahme": 230,
    "abgeschlossen": 231,
}


class SetVorgangStatusInput(BaseModel):
    """Input for setting Mietermeldungs-Vorgang status."""
    vorgang_id: int = Field(description="ID des Mietermeldungs-Vorgangs in M-Files")
    status: str = Field(description="Ziel-Status: berechtigt, unberechtigt, in-pruefung, in-behebung, erledigt, in-abrechnung, nachfrage, aufgeschoben")
    kommentar: Optional[str] = Field(default=None, description="Optionaler Kommentar zum Status-Wechsel")


class SetAngebotStatusInput(BaseModel):
    """Input for setting Angebot status."""
    angebot_id: int = Field(description="ID des Angebots in M-Files")
    status: str = Field(description="Ziel-Status: angenommen, abgelehnt, nachverhandeln")
    kommentar: Optional[str] = Field(default=None, description="Optionaler Kommentar")


class SetSanierungStatusInput(BaseModel):
    """Input for setting Sanierungsvorgang status."""
    vorgang_id: int = Field(description="ID des Sanierungsvorgangs in M-Files")
    status: str = Field(description="Ziel-Status: vergabe, durchfuehrung, abnahme, abrechnung, nachfrage, abgeschlossen, ausschreibung, ausschreibung-schwarzbaum")
    kommentar: Optional[str] = Field(default=None, description="Optionaler Kommentar zum Status-Wechsel")


class AddVorgangCommentInput(BaseModel):
    """Input for adding a comment to any Vorgang."""
    vorgang_id: int = Field(description="ID des Vorgangs in M-Files")
    kommentar: str = Field(description="Kommentar-Text")
    object_type: int = Field(default=139, description="M-Files Objekt-Typ (139=Vorgaenge, 0=Dokument). Standard: 139")


class GetViewItemsInput(BaseModel):
    """Input for fetching items from an M-Files view."""
    view_id: int = Field(description="M-Files View ID (z.B. 117 fuer 'Mietermeldungen unerledigt nach Status')")
    limit: int = Field(default=1000, description="Maximale Anzahl Ergebnisse pro Seite", ge=1, le=2000)
    include_properties: bool = Field(default=True, description="Ob Properties fuer jedes Objekt geladen werden sollen")
    format: str = Field(default="json", description="Ausgabeformat: 'json' oder 'markdown'")
