"""
Jurisdiction-Aware Legal Reasoning Engine.

Maps detected jurisdictions to their legal standards, mandatory requirements,
and default rules so that risk severity and gap analysis can be calibrated
to the governing law of the agreement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class JurisdictionProfile:
    """Legal standards and defaults for a specific jurisdiction."""
    name: str
    aliases: tuple[str, ...]

    # Implied warranty rules
    implied_warranty_survives_disclaimer: bool
    implied_warranty_note: str

    # Liability cap norms
    typical_liability_cap_multiple: float        # e.g. 1.0 = purchase price, 2.0 = 2x
    liability_cap_note: str

    # Mandatory notice periods (days)
    min_cure_period_days: int
    min_termination_notice_days: int

    # Consequential damages
    consequential_damages_waivable: bool
    consequential_damages_note: str

    # IP indemnity standards
    ip_indemnity_standard: str                   # "strict" | "reasonable" | "limited"

    # Mandatory provisions (if absent, flag as gap)
    mandatory_provisions: tuple[str, ...]

    # Jurisdiction-specific risk additions
    additional_risks: tuple[dict, ...]


_PROFILES: list[JurisdictionProfile] = [
    JurisdictionProfile(
        name="New York",
        aliases=("new york", "ny", "n.y.", "state of new york"),
        implied_warranty_survives_disclaimer=False,
        implied_warranty_note=(
            "Under New York UCC § 2-316, implied warranties can be disclaimed "
            "with conspicuous AS-IS language. However, express warranties cannot "
            "be disclaimed and survive."
        ),
        typical_liability_cap_multiple=1.0,
        liability_cap_note=(
            "New York courts generally enforce liability caps at Purchase Price "
            "unless unconscionable. Carve-outs for fraud and willful misconduct "
            "are standard practice."
        ),
        min_cure_period_days=30,
        min_termination_notice_days=30,
        consequential_damages_waivable=True,
        consequential_damages_note=(
            "New York enforces consequential damages waivers between sophisticated "
            "commercial parties. Waivers may not apply to personal injury or fraud."
        ),
        ip_indemnity_standard="strict",
        mandatory_provisions=(
            "governing law",
            "dispute resolution",
            "notice",
        ),
        additional_risks=(
            {
                "category": "NY UCC Risk",
                "severity": "medium",
                "description": (
                    "Under NY UCC Article 2, risk of loss passes to Buyer upon "
                    "delivery by carrier unless agreement specifies otherwise. "
                    "Buyer should confirm risk transfer point aligns with UCC defaults."
                ),
                "clause_reference": "Title/Risk of Loss section",
                "affected_party": "buyer",
            },
        ),
    ),
    JurisdictionProfile(
        name="Delaware",
        aliases=("delaware", "de", "state of delaware"),
        implied_warranty_survives_disclaimer=False,
        implied_warranty_note=(
            "Delaware follows UCC Article 2. AS-IS disclaimers are enforceable "
            "if conspicuous. Delaware courts are highly commercial-friendly."
        ),
        typical_liability_cap_multiple=1.0,
        liability_cap_note=(
            "Delaware courts strongly enforce negotiated liability caps. "
            "Carve-outs for fraud, gross negligence, and willful misconduct "
            "are standard and recommended."
        ),
        min_cure_period_days=30,
        min_termination_notice_days=30,
        consequential_damages_waivable=True,
        consequential_damages_note=(
            "Delaware enforces consequential damages waivers between commercial "
            "parties. Delaware courts are highly deferential to contract terms."
        ),
        ip_indemnity_standard="strict",
        mandatory_provisions=(
            "governing law",
            "dispute resolution",
        ),
        additional_risks=(),
    ),
    JurisdictionProfile(
        name="California",
        aliases=("california", "ca", "cal.", "state of california"),
        implied_warranty_survives_disclaimer=True,
        implied_warranty_note=(
            "California Civil Code § 1791.1 provides implied warranty of "
            "merchantability for consumer goods that CANNOT be disclaimed. "
            "For commercial goods, UCC applies but courts scrutinize disclaimers."
        ),
        typical_liability_cap_multiple=2.0,
        liability_cap_note=(
            "California courts may find liability caps unconscionable if they "
            "effectively eliminate all remedies. Caps below 2x purchase price "
            "are frequently challenged. Carve-outs for gross negligence required."
        ),
        min_cure_period_days=30,
        min_termination_notice_days=30,
        consequential_damages_waivable=False,
        consequential_damages_note=(
            "California courts are more likely to strike consequential damages "
            "waivers as unconscionable, especially in consumer or adhesion contracts. "
            "Even B2B waivers may not survive if the cap fails its essential purpose."
        ),
        ip_indemnity_standard="strict",
        mandatory_provisions=(
            "governing law",
            "dispute resolution",
            "privacy",
            "data protection",
        ),
        additional_risks=(
            {
                "category": "California Unconscionability Risk",
                "severity": "high",
                "description": (
                    "California courts may void liability cap and consequential damages "
                    "waiver as unconscionable if they deprive Buyer of all meaningful "
                    "remedy. Seller should ensure cap is not below actual foreseeable loss."
                ),
                "clause_reference": "Section 8 (Limitation of Liability)",
                "affected_party": "seller",
            },
            {
                "category": "CCPA/Privacy Obligation",
                "severity": "medium",
                "description": (
                    "California Consumer Privacy Act (CCPA) may apply if personal data "
                    "is processed. Agreement lacks explicit data processing and privacy "
                    "obligations required under California law."
                ),
                "clause_reference": "Confidentiality section",
                "affected_party": "both",
            },
        ),
    ),
    JurisdictionProfile(
        name="England & Wales",
        aliases=("england", "wales", "england and wales", "english law", "uk", "united kingdom"),
        implied_warranty_survives_disclaimer=True,
        implied_warranty_note=(
            "Under UK Sale of Goods Act 1979 and Consumer Rights Act 2015, "
            "implied terms of satisfactory quality and fitness for purpose CANNOT "
            "be excluded in B2C contracts. In B2B, exclusion must satisfy UCTA 1977 "
            "reasonableness test."
        ),
        typical_liability_cap_multiple=2.0,
        liability_cap_note=(
            "Under UCTA 1977, liability caps must satisfy the reasonableness test. "
            "Caps set at Purchase Price may be challenged if inadequate to cover "
            "foreseeable loss. Death/personal injury liability cannot be capped."
        ),
        min_cure_period_days=14,
        min_termination_notice_days=14,
        consequential_damages_waivable=True,
        consequential_damages_note=(
            "Consequential damages waivers are enforceable in English B2B contracts "
            "subject to UCTA reasonableness. Must be reasonable given the parties' "
            "bargaining positions and available insurance."
        ),
        ip_indemnity_standard="reasonable",
        mandatory_provisions=(
            "governing law",
            "dispute resolution",
            "notice",
            "data protection",
        ),
        additional_risks=(
            {
                "category": "UCTA Reasonableness Risk",
                "severity": "high",
                "description": (
                    "Under UK Unfair Contract Terms Act 1977, limitation clauses "
                    "must pass the reasonableness test. Liability cap at Purchase Price "
                    "may be challenged as unreasonable if foreseeable loss significantly "
                    "exceeds the contract value."
                ),
                "clause_reference": "Section 8 (Limitation of Liability)",
                "affected_party": "seller",
            },
            {
                "category": "UK GDPR Obligation",
                "severity": "high",
                "description": (
                    "UK GDPR applies if personal data is processed. Agreement lacks "
                    "data processing agreement (DPA), data subject rights, and breach "
                    "notification obligations required under UK GDPR Article 28."
                ),
                "clause_reference": "Confidentiality section",
                "affected_party": "both",
            },
        ),
    ),
    JurisdictionProfile(
        name="India",
        aliases=("india", "indian law", "laws of india"),
        implied_warranty_survives_disclaimer=True,
        implied_warranty_note=(
            "Under Indian Sale of Goods Act 1930, implied conditions of merchantability "
            "and fitness for purpose apply. Exclusion requires clear and unambiguous "
            "language and may be subject to Consumer Protection Act 2019."
        ),
        typical_liability_cap_multiple=1.0,
        liability_cap_note=(
            "Indian courts generally enforce negotiated liability caps between "
            "commercial parties. However, caps that are unconscionable or against "
            "public policy may be struck down under Indian Contract Act 1872."
        ),
        min_cure_period_days=30,
        min_termination_notice_days=30,
        consequential_damages_waivable=True,
        consequential_damages_note=(
            "Indian courts enforce consequential damages waivers in commercial "
            "contracts. However, Section 73 of Indian Contract Act provides for "
            "natural and probable consequences of breach."
        ),
        ip_indemnity_standard="limited",
        mandatory_provisions=(
            "governing law",
            "dispute resolution",
            "stamp duty compliance",
        ),
        additional_risks=(
            {
                "category": "Stamp Duty Risk",
                "severity": "medium",
                "description": (
                    "Indian Stamp Act requires commercial agreements to be stamped "
                    "adequately. Unstamped or under-stamped agreements are inadmissible "
                    "as evidence in Indian courts. Verify stamp duty compliance."
                ),
                "clause_reference": "Execution/Signature section",
                "affected_party": "both",
            },
        ),
    ),
]

_PROFILE_MAP: dict[str, JurisdictionProfile] = {}
for _p in _PROFILES:
    _PROFILE_MAP[_p.name.lower()] = _p
    for _alias in _p.aliases:
        _PROFILE_MAP[_alias.lower()] = _p

_DEFAULT_PROFILE = JurisdictionProfile(
    name="General Commercial",
    aliases=(),
    implied_warranty_survives_disclaimer=False,
    implied_warranty_note="Jurisdiction not detected. Applying general commercial law standards.",
    typical_liability_cap_multiple=1.0,
    liability_cap_note="Standard commercial practice: cap at Purchase Price with fraud/willful misconduct carve-outs.",
    min_cure_period_days=30,
    min_termination_notice_days=30,
    consequential_damages_waivable=True,
    consequential_damages_note="Consequential damages waivers are generally enforceable between commercial parties.",
    ip_indemnity_standard="reasonable",
    mandatory_provisions=("governing law", "dispute resolution"),
    additional_risks=(),
)


@dataclass
class JurisdictionAnalysis:
    """Output of jurisdiction-aware analysis."""
    detected_jurisdiction: str
    profile_name: str
    jurisdiction_risks: list[dict]
    severity_adjustments: list[dict]
    missing_mandatory_provisions: list[str]
    jurisdiction_notes: list[str]
    cure_period_gap: bool
    termination_notice_gap: bool


class JurisdictionEngine:
    """
    Detects the governing jurisdiction from document text and applies
    jurisdiction-specific legal standards to adjust risk analysis.
    """

    def detect_jurisdiction(self, text: str, metadata_jurisdiction: str = "") -> JurisdictionProfile:
        """
        Detect jurisdiction dynamically from the document, in priority order:
        1. Metadata jurisdiction field (most reliable)
        2. Explicit governing law clause ("governed by the laws of X")
        3. Choice of law / forum selection clauses
        4. Party addresses and incorporation state
        5. Document title signals
        6. First 5000 chars general scan
        """
        lower_text = text.lower()

        # 1. Metadata — highest priority
        if metadata_jurisdiction:
            meta_lower = metadata_jurisdiction.lower()
            for alias, profile in _PROFILE_MAP.items():
                if alias in meta_lower:
                    return profile

        # 2. Explicit governing law clause — most reliable in-document signal
        gov_patterns = [
            r"governed by (?:the )?laws? of ([A-Za-z ,&]+?)(?:\.|,|\band\b|$)",
            r"governing law[:\s]+([A-Za-z ,&]+?)(?:\.|,|\n)",
            r"laws? of the state of ([A-Za-z ]+?)(?:\.|,|\band\b|$)",
            r"subject to (?:the )?laws? of ([A-Za-z ,&]+?)(?:\.|,|\n)",
        ]
        import re as _re
        for pat in gov_patterns:
            m = _re.search(pat, lower_text[:8000])
            if m:
                candidate = m.group(1).strip()
                for alias, profile in _PROFILE_MAP.items():
                    if alias in candidate:
                        return profile

        # 3. Forum selection / arbitration seat
        forum_patterns = [
            r"courts? of ([A-Za-z ,]+?) shall have",
            r"arbitration (?:seat|venue)[:\s]+([A-Za-z ,]+?)(?:\.|,|\n)",
            r"venue[:\s]+(?:the )?(?:courts? of )?([A-Za-z ,]+?)(?:\.|,|\n)",
        ]
        for pat in forum_patterns:
            m = _re.search(pat, lower_text[:8000])
            if m:
                candidate = m.group(1).strip()
                for alias, profile in _PROFILE_MAP.items():
                    if alias in candidate:
                        return profile

        # 4. Party address / incorporation signals
        address_patterns = [
            r"incorporated (?:in|under) (?:the )?(?:state of )?([A-Za-z ]+?)(?:\.|,|\band\b)",
            r"(?:principal )?(?:place of )?business[:\s]+[^,\n]*,\s*([A-Za-z ]+?)(?:\d{5}|\.|,|\n)",
        ]
        for pat in address_patterns:
            m = _re.search(pat, lower_text[:5000])
            if m:
                candidate = m.group(1).strip()
                for alias, profile in _PROFILE_MAP.items():
                    if alias in candidate:
                        return profile

        # 5. General scan of first 8000 chars — weighted by specificity
        scan_text = lower_text[:8000]
        best_profile: JurisdictionProfile | None = None
        best_score = 0
        for alias, profile in _PROFILE_MAP.items():
            if alias in scan_text:
                score = len(alias)  # longer alias = more specific match
                if score > best_score:
                    best_score = score
                    best_profile = profile

        if best_profile is not None:
            return best_profile

        return _DEFAULT_PROFILE

    def analyze(
        self,
        text: str,
        metadata_jurisdiction: str = "",
    ) -> JurisdictionAnalysis:
        profile = self.detect_jurisdiction(text, metadata_jurisdiction)
        lower = text.lower()

        jurisdiction_risks = list(profile.additional_risks)

        severity_adjustments: list[dict] = []

        if not profile.implied_warranty_survives_disclaimer:
            severity_adjustments.append({
                "category": "AS-IS Disclaimer",
                "original_severity": "high",
                "adjusted_severity": "medium",
                "reason": f"{profile.name}: AS-IS disclaimers are enforceable — {profile.implied_warranty_note[:120]}",
            })
        else:
            severity_adjustments.append({
                "category": "AS-IS Disclaimer",
                "original_severity": "high",
                "adjusted_severity": "critical",
                "reason": f"{profile.name}: Implied warranties may survive disclaimer — {profile.implied_warranty_note[:120]}",
            })

        if not profile.consequential_damages_waivable:
            severity_adjustments.append({
                "category": "Consequential Damages Exclusion",
                "original_severity": "high",
                "adjusted_severity": "critical",
                "reason": f"{profile.name}: Consequential damages waivers may be unenforceable — {profile.consequential_damages_note[:120]}",
            })

        if profile.typical_liability_cap_multiple > 1.0:
            severity_adjustments.append({
                "category": "Liability Cap",
                "original_severity": "critical",
                "adjusted_severity": "critical",
                "reason": (
                    f"{profile.name}: Liability cap at Purchase Price is below the typical "
                    f"{profile.typical_liability_cap_multiple:.0f}x multiple expected in this jurisdiction. "
                    f"{profile.liability_cap_note[:100]}"
                ),
            })

        missing_mandatory: list[str] = []
        for provision in profile.mandatory_provisions:
            if provision not in lower:
                missing_mandatory.append(provision)

        cure_gap = False
        if "terminat" in lower and "cure" not in lower:
            cure_gap = True

        notice_gap = False
        if "terminat" in lower and "notice" not in lower:
            notice_gap = True

        notes = [
            f"Governing jurisdiction: **{profile.name}**",
            f"Implied warranty: {profile.implied_warranty_note[:200]}",
            f"Liability cap standard: {profile.liability_cap_note[:200]}",
            f"Consequential damages: {profile.consequential_damages_note[:200]}",
            f"IP indemnity standard: {profile.ip_indemnity_standard.upper()}",
            f"Minimum cure period: {profile.min_cure_period_days} days",
            f"Minimum termination notice: {profile.min_termination_notice_days} days",
        ]

        return JurisdictionAnalysis(
            detected_jurisdiction=profile.name,
            profile_name=profile.name,
            jurisdiction_risks=jurisdiction_risks,
            severity_adjustments=severity_adjustments,
            missing_mandatory_provisions=missing_mandatory,
            jurisdiction_notes=notes,
            cure_period_gap=cure_gap,
            termination_notice_gap=notice_gap,
        )
