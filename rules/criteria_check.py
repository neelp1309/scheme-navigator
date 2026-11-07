"""Deterministic eligibility checks.

Numbers (age, income, land) are checked here in plain Python instead of by the
LLM. The LLM-based Eligibility Judge only handles `fuzzy_conditions`.

Semantics
---------
* A failed rule      -> verdict "not_eligible"
* An unknown value   -> verdict "needs_info" (unless another rule already failed)
* Exclusion flags (income-tax payer, govt employee, EPFO/ESIC/NPS) and the bank
  account requirement are *assumed* to pass when unknown, and recorded as
  assumptions, because almost no one mentions them unprompted.
"""
from __future__ import annotations

from schemas import CitizenProfile, RuleCheckResult, Scheme, SchemeCriteria


def _fmt_inr(n: int) -> str:
    return f"₹{n:,}"


def _check(c: SchemeCriteria, p: CitizenProfile) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (matched, failed, missing, assumptions) for one criteria block."""
    matched: list[str] = []
    failed: list[str] = []
    missing: list[str] = []
    assumptions: list[str] = []

    def need(field: str, value) -> bool:
        if value is None:
            missing.append(field)
            return False
        return True

    # --- age ---------------------------------------------------------------
    if c.min_age is not None or c.max_age is not None:
        if need("age", p.age):
            lo = c.min_age if c.min_age is not None else 0
            hi = c.max_age if c.max_age is not None else 200
            label = f"age {lo}-{hi}" if c.max_age is not None else f"age {lo}+"
            (matched if lo <= p.age <= hi else failed).append(f"{label} (is {p.age})")

    if c.genders and need("gender", p.gender):
        (matched if p.gender in c.genders else failed).append(f"gender in {c.genders}")

    if c.states and need("state", p.state):
        ok = p.state.strip().lower() in [s.lower() for s in c.states]
        (matched if ok else failed).append(f"resident of {', '.join(c.states)}")

    if c.area and need("area (rural/urban)", p.area):
        (matched if p.area == c.area else failed).append(f"{c.area} area")

    # --- income ------------------------------------------------------------
    if c.max_family_income is not None and need("annual_family_income", p.annual_family_income):
        ok = p.annual_family_income <= c.max_family_income
        (matched if ok else failed).append(f"family income ≤ {_fmt_inr(c.max_family_income)}")

    if c.max_family_income_rural is not None or c.max_family_income_urban is not None:
        if need("area (rural/urban)", p.area) and need("annual_family_income", p.annual_family_income):
            limit = c.max_family_income_rural if p.area == "rural" else c.max_family_income_urban
            if limit is not None:
                ok = p.annual_family_income <= limit
                (matched if ok else failed).append(f"{p.area} family income ≤ {_fmt_inr(limit)}")

    if c.max_monthly_income is not None:
        monthly = p.monthly_income
        if monthly is None and p.annual_family_income is not None:
            # Fall back to family income / 12 as an upper bound for the individual.
            monthly = p.annual_family_income // 12
            assumptions.append("monthly income estimated as family income / 12")
        if need("monthly_income", monthly):
            ok = monthly <= c.max_monthly_income
            (matched if ok else failed).append(f"monthly income ≤ {_fmt_inr(c.max_monthly_income)}")

    # --- occupation --------------------------------------------------------
    if c.occupations and need("occupation", p.occupation):
        (matched if p.occupation in c.occupations else failed).append(f"occupation in {c.occupations}")

    if c.artisan_trades and need("artisan_trade", p.artisan_trade):
        (matched if p.artisan_trade in c.artisan_trades else failed).append("one of the notified trades")

    if c.social_categories and need("social_category", p.social_category):
        ok = p.social_category in c.social_categories
        (matched if ok else failed).append(f"category in {[s.upper() for s in c.social_categories]}")

    if c.requires_bpl and need("is_bpl", p.is_bpl):
        (matched if p.is_bpl else failed).append("BPL household")

    if c.min_disability_percent is not None and need("disability_percent", p.disability_percent):
        ok = p.disability_percent >= c.min_disability_percent
        (matched if ok else failed).append(f"disability ≥ {c.min_disability_percent}%")

    # --- land --------------------------------------------------------------
    if c.requires_land_owner and need("owns_agricultural_land", p.owns_agricultural_land):
        (matched if p.owns_agricultural_land else failed).append("owns cultivable land")

    if c.max_land_hectares is not None and need("land_hectares", p.land_hectares):
        ok = p.land_hectares <= c.max_land_hectares
        (matched if ok else failed).append(f"land ≤ {c.max_land_hectares} ha (has {p.land_hectares:.2f})")

    # --- family / life stage -----------------------------------------------
    if c.marital_status and need("marital_status", p.marital_status):
        (matched if p.marital_status in c.marital_status else failed).append(f"marital status {c.marital_status}")

    if c.requires_pregnant_or_lactating and need("is_pregnant_or_lactating", p.is_pregnant_or_lactating):
        (matched if p.is_pregnant_or_lactating else failed).append("pregnant or lactating")

    if c.child is not None:
        if not p.children:
            missing.append("children (age, gender)")
        else:
            def child_ok(ch) -> bool:
                if c.child.gender and ch.gender != c.child.gender:
                    return False
                if c.child.max_age is not None and ch.age > c.child.max_age:
                    return False
                return True
            ok = any(child_ok(ch) for ch in p.children)
            desc = f"has a {c.child.gender or ''} child aged ≤ {c.child.max_age}".replace("  ", " ")
            (matched if ok else failed).append(desc)

    # --- education ---------------------------------------------------------
    if c.education_levels and need("education_level", p.education_level):
        (matched if p.education_level in c.education_levels else failed).append(f"studying in {c.education_levels}")

    if c.streams and need("stream", p.stream):
        (matched if p.stream in c.streams else failed).append(f"stream in {c.streams}")

    if c.min_exam_percent is not None:
        # A percentile is not a percentage, but if only the percentile is known
        # we cannot conclude anything, so ask.
        if need("last_exam_percent", p.last_exam_percent):
            ok = p.last_exam_percent >= c.min_exam_percent
            (matched if ok else failed).append(f"≥ {c.min_exam_percent}% in last exam")

    if c.min_exam_percentile is not None and need("last_exam_percentile", p.last_exam_percentile):
        ok = p.last_exam_percentile >= c.min_exam_percentile
        (matched if ok else failed).append(f"≥ {c.min_exam_percentile} percentile")

    # --- assets / status ---------------------------------------------------
    if c.requires_no_pucca_house and need("owns_pucca_house", p.owns_pucca_house):
        (matched if not p.owns_pucca_house else failed).append("no pucca house")

    if c.requires_no_lpg_connection and need("has_lpg_connection", p.has_lpg_connection):
        (matched if not p.has_lpg_connection else failed).append("no LPG connection in household")

    if c.health_conditions:
        have = {h.lower() for h in p.health_conditions}
        ok = any(h.lower() in have for h in c.health_conditions)
        (matched if ok else failed).append(f"diagnosed with {c.health_conditions}")

    if c.required_intents:
        ok = any(i in p.intents for i in c.required_intents)
        (matched if ok else failed).append(f"wants: {c.required_intents}")

    if c.requires_list_lookup:
        missing.append(f"check {c.requires_list_lookup}")

    # --- exclusions / soft requirements (assumed OK when unknown) ----------
    def soft(flag_value, bad_when: bool, label: str):
        if flag_value is None:
            assumptions.append(f"assumed {label}")
        elif flag_value == bad_when:
            failed.append(label)
        else:
            matched.append(label)

    if c.requires_bank_account:
        soft(p.has_bank_account, False, "has a savings bank account")
    if c.excludes_income_tax_payer:
        soft(p.is_income_tax_payer, True, "not an income-tax payer")
    if c.excludes_govt_employee:
        soft(p.is_govt_employee if p.occupation != "govt_employee" else True, True, "not a government employee")
    if c.excludes_epfo_esic_nps:
        soft(p.has_epfo_esic_nps, True, "not an EPFO/ESIC/NPS member")

    # --- OR groups ---------------------------------------------------------
    if c.any_of:
        branch_results = [_check(sub, p) for sub in c.any_of]
        passing = [r for r in branch_results if not r[1] and not r[2]]
        if passing:
            matched.append("meets one of: " + " | ".join(r[0][0] if r[0] else "?" for r in passing[:1]))
        elif any(not r[1] for r in branch_results):
            # No branch failed outright but some lack data
            missing.extend(sorted({m for r in branch_results for m in r[2]}))
        else:
            failed.append("does not meet any of the alternative groups: "
                          + " | ".join(r[1][0] for r in branch_results if r[1]))

    return matched, failed, missing, assumptions


def check_scheme(scheme: Scheme, profile: CitizenProfile) -> RuleCheckResult:
    matched, failed, missing, assumptions = _check(scheme.criteria, profile)
    if failed:
        verdict = "not_eligible"
    elif missing:
        verdict = "needs_info"
    else:
        verdict = "eligible"
    return RuleCheckResult(
        scheme_id=scheme.scheme_id,
        verdict=verdict,
        matched_criteria=matched,
        failed_criteria=failed,
        missing_info=sorted(set(missing)),
        assumptions=assumptions,
    )


def check_all(schemes: list[Scheme], profile: CitizenProfile) -> list[RuleCheckResult]:
    return [check_scheme(s, profile) for s in schemes]
