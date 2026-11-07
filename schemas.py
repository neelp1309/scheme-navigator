"""Pydantic models shared by every agent.

Every agent reads and writes these types, so the contract between agents is
explicit and testable. Field vocabularies (occupations, education levels, ...)
are listed as Literals so the Profile Extractor can't invent new values.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Controlled vocabularies
# --------------------------------------------------------------------------
Occupation = Literal[
    "farmer",               # cultivates land (owner, tenant or sharecropper)
    "farm_labourer",
    "animal_husbandry",     # dairy, poultry, goat rearing
    "fisher",
    "construction_worker",
    "street_vendor",
    "domestic_worker",
    "artisan",              # see ArtisanTrade
    "driver",
    "gig_worker",
    "self_employed",        # small shop / own business
    "salaried_private",
    "govt_employee",
    "student",
    "homemaker",
    "unemployed",
    "retired",
    "other",
]

# Occupations treated as "unorganised sector" by e-Shram / PM-SYM
UNORGANISED_OCCUPATIONS = [
    "farmer", "farm_labourer", "animal_husbandry", "fisher", "construction_worker",
    "street_vendor", "domestic_worker", "artisan", "driver", "gig_worker", "self_employed",
]

# The 18 family-based trades covered by PM Vishwakarma
ArtisanTrade = Literal[
    "carpenter", "boat_maker", "armourer", "blacksmith", "hammer_toolkit_maker",
    "locksmith", "goldsmith", "potter", "sculptor_stone_breaker", "cobbler", "mason",
    "basket_mat_broom_coir_weaver", "doll_toy_maker", "barber", "garland_maker",
    "washerman", "tailor", "fishing_net_maker",
]

EducationLevel = Literal[
    "class_1_7", "class_8", "class_9_10", "class_11_12", "diploma", "ug", "pg", "not_studying",
]

Intent = Literal["start_business", "expand_business", "education_loan"]

SocialCategory = Literal["general", "ews", "obc", "sc", "st"]


# --------------------------------------------------------------------------
# Agent 1 output: the citizen profile
# --------------------------------------------------------------------------
class Child(BaseModel):
    age: int
    gender: Literal["male", "female", "other"]


class CitizenProfile(BaseModel):
    """Everything the system knows about the person. None = not mentioned."""

    age: Optional[int] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    state: Optional[str] = Field(None, description="Indian state, title case, e.g. 'Gujarat'")
    area: Optional[Literal["rural", "urban"]] = None
    occupation: Optional[Occupation] = None
    artisan_trade: Optional[ArtisanTrade] = None

    annual_family_income: Optional[int] = Field(None, description="Rupees per year, whole family")
    monthly_income: Optional[int] = Field(None, description="Rupees per month, the person themselves")
    social_category: Optional[SocialCategory] = None
    is_bpl: Optional[bool] = Field(None, description="Holds a BPL card / is on the BPL list")
    disability_percent: Optional[int] = None

    owns_agricultural_land: Optional[bool] = None
    land_hectares: Optional[float] = Field(None, description="1 acre = 0.4047 ha; 1 bigha varies by region")

    marital_status: Optional[Literal["single", "married", "widowed", "divorced"]] = None
    is_pregnant_or_lactating: Optional[bool] = None
    children: list[Child] = Field(default_factory=list)

    education_level: Optional[EducationLevel] = None
    stream: Optional[Literal["science", "commerce", "arts", "other"]] = None
    last_exam_percent: Optional[float] = None
    last_exam_percentile: Optional[float] = None

    has_bank_account: Optional[bool] = None
    is_income_tax_payer: Optional[bool] = None
    is_govt_employee: Optional[bool] = None
    has_epfo_esic_nps: Optional[bool] = None
    owns_pucca_house: Optional[bool] = None
    has_lpg_connection: Optional[bool] = None
    health_conditions: list[str] = Field(default_factory=list, description="e.g. ['tuberculosis']")
    intents: list[Intent] = Field(default_factory=list)

    missing_fields: list[str] = Field(default_factory=list, description="Critical fields the user should be asked about")


# --------------------------------------------------------------------------
# Knowledge base: one scheme
# --------------------------------------------------------------------------
class ChildCriteria(BaseModel):
    gender: Optional[Literal["male", "female"]] = None
    max_age: Optional[int] = None


class SchemeCriteria(BaseModel):
    """Machine-checkable eligibility rules. All set fields must pass (AND).

    `any_of` lets a scheme say "at least one of these groups" (OR), e.g.
    JSY in high-performing states: BPL OR SC OR ST.
    Anything that can't be expressed here goes in Scheme.fuzzy_conditions
    and is judged by the LLM.
    """

    min_age: Optional[int] = None
    max_age: Optional[int] = None
    genders: Optional[list[str]] = None
    states: Optional[list[str]] = None            # None = all of India
    area: Optional[Literal["rural", "urban"]] = None
    max_family_income: Optional[int] = None
    max_family_income_rural: Optional[int] = None
    max_family_income_urban: Optional[int] = None
    max_monthly_income: Optional[int] = None
    occupations: Optional[list[str]] = None
    artisan_trades: Optional[list[str]] = None
    social_categories: Optional[list[str]] = None
    requires_bpl: Optional[bool] = None
    min_disability_percent: Optional[int] = None
    requires_land_owner: Optional[bool] = None
    max_land_hectares: Optional[float] = None
    marital_status: Optional[list[str]] = None
    requires_pregnant_or_lactating: Optional[bool] = None
    education_levels: Optional[list[str]] = None
    streams: Optional[list[str]] = None
    min_exam_percent: Optional[float] = None
    min_exam_percentile: Optional[float] = None
    requires_bank_account: Optional[bool] = None
    excludes_income_tax_payer: Optional[bool] = None
    excludes_govt_employee: Optional[bool] = None
    excludes_epfo_esic_nps: Optional[bool] = None
    requires_no_pucca_house: Optional[bool] = None
    requires_no_lpg_connection: Optional[bool] = None
    health_conditions: Optional[list[str]] = None
    required_intents: Optional[list[str]] = None   # at least one must be present
    child: Optional[ChildCriteria] = None          # at least one child must match
    requires_list_lookup: Optional[str] = None     # e.g. "SECC 2011 beneficiary list": always needs_info
    any_of: Optional[list["SchemeCriteria"]] = None


class Scheme(BaseModel):
    scheme_id: str
    name: str
    level: Literal["central", "state"]
    state: Optional[str] = None
    category: Literal[
        "agriculture", "pension_social_security", "education", "women_child",
        "health", "livelihood", "housing",
    ]
    ministry_or_department: str
    description: str
    benefits: str
    eligibility_text: str
    exclusions_text: str = ""
    criteria: SchemeCriteria
    fuzzy_conditions: list[str] = Field(default_factory=list)
    documents_required: list[str]
    application_steps: list[str]
    application_mode: Literal["online", "offline", "online_or_offline"]
    source_urls: list[str]
    last_verified: str
    notes: str = ""


# --------------------------------------------------------------------------
# Agent 2 / 3 / 6 outputs
# --------------------------------------------------------------------------
class SchemeDoc(BaseModel):
    scheme_id: str
    name: str
    level: Literal["central", "state"]
    category: str
    text: str
    score: float


class RuleCheckResult(BaseModel):
    """Output of the deterministic checker (rules/criteria_check.py)."""

    scheme_id: str
    verdict: Literal["eligible", "not_eligible", "needs_info"]
    matched_criteria: list[str] = Field(default_factory=list)
    failed_criteria: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class EligibilityResult(BaseModel):
    scheme_id: str
    verdict: Literal["eligible", "not_eligible", "needs_info"]
    matched_criteria: list[str] = Field(default_factory=list)
    failed_criteria: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    evidence: str = Field("", description="Quote from the scheme text supporting the verdict")
    confidence: float = Field(1.0, ge=0, le=1)


class VerificationReport(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)


SchemeCriteria.model_rebuild()
