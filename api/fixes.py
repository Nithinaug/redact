import re
from typing import List

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.predefined_recognizers import SgFinRecognizer, SgUenRecognizer

from .id_validators import (
    cin_valid,
    driver_license_valid,
    fiscal_year_valid,
    gstin_valid,
    ifsc_valid,
    nric_fin_valid,
    pan_valid,
    passport_plausible,
    phone_plausible,
    verhoeff_valid,
)


class PanRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return pan_valid(pattern_text)


class AadhaarRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return verhoeff_valid(pattern_text.replace(" ", ""))


class GstinRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return gstin_valid(pattern_text)


class IfscRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return ifsc_valid(pattern_text)


class CinRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return cin_valid(pattern_text)


class DriverLicenseRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return None if driver_license_valid(pattern_text) else False


class SgFinChecksumRecognizer(SgFinRecognizer):
    def validate_result(self, pattern_text):
        return nric_fin_valid(pattern_text)


class PlausiblePhoneRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return None if phone_plausible(pattern_text) else False


class PlausiblePassportRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return None if passport_plausible(pattern_text) else False


class FiscalYearRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return fiscal_year_valid(pattern_text)


_DATE_PATTERN = re.compile(
    r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s*\d{2,4}\b"
    r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4}\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b"
    r"|\b(?:19|20)\d{2}\b",
    re.IGNORECASE,
)

_ADDRESS_WORDS = re.compile(
    r"\b(?:St|Rd|Ave|Blvd|Dr|Ln|Ct|Pl|Way|Hwy|Pkwy|Cir|Ter|Loop|Trail|"
    r"Street|Road|Avenue|Boulevard|Drive|Lane|Court|Place|Highway|Parkway|Circle|"
    r"D\.?C\.?|VA|MD|CA|NY|TX|FL|NJ|PA|IL|OH|GA|NC|MI|WA|AZ|MA|TN|IN|MO|WI|MN|CO|AL|SC|"
    r"Arlington|Washington|Manhattan|Brooklyn|Boston|Chicago|Houston|Phoenix|Philadelphia|"
    r"San\s+(?:Francisco|Diego|Antonio|Jose)|Los\s+Angeles|New\s+York|"
    r"\d{5}(?:-\d{4})?)\b",
    re.IGNORECASE,
)

_LOCATION_FRAGMENT = re.compile(r"^[\s,]*(?:[A-Z]{2}|D\.?C\.?|(?:,?\s*[A-Z][a-z]+)+,?\s*[A-Z]{2})[\s,.]*$")

_BANK_CONTEXT = re.compile(
    r"\b(?:account|acct|bank|IBAN|SWIFT|sort\s*code|routing|DBS|OCBC|UOB|POSB|Citibank|HSBC|Standard\s*Chartered)\b",
    re.IGNORECASE,
)

_PHONE_CONTEXT = re.compile(r"\b(?:phone|mobile|contact|call|tel|hp|fax)\b", re.IGNORECASE)

_ORG_WORDS = re.compile(
    r"\b(?:Bank|Chase|Morgan|Goldman|Sachs|Merrill|Lynch|Barclays|Citibank|HSBC|"
    r"UBS|Credit\s+Suisse|Deutsche|JPMorgan|Standard\s+Chartered|"
    r"Corp|Inc|Ltd|LLC|LLP|GmbH|PLC|Pte|Group|Holdings|Capital|Securities|"
    r"University|College|Institute|Academy|Hospital|Clinic)\b",
    re.IGNORECASE,
)

_COUNTRY_NAMES = re.compile(
    r"^(?:Singapore|Malaysia|Indonesia|Thailand|Philippines|Vietnam|Myanmar|Cambodia|"
    r"Japan|China|India|Australia|Switzerland|Germany|France|UK|USA|Brazil|Canada|"
    r"Hong Kong|New Zealand|South Korea|Taiwan|Netherlands|Ireland|Luxembourg|"
    r"United Kingdom|United States)$",
    re.IGNORECASE,
)


def build_custom_recognizers():
    return [
        SgFinChecksumRecognizer(),
        SgUenRecognizer(),
        PlausiblePhoneRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=[Pattern("sg_phone", r"\b[89]\d{3}[\-\s]?\d{4}\b", 0.5)],
            context=["phone", "mobile", "contact", "call", "tel", "hp"],
        ),
        PlausiblePassportRecognizer(
            supported_entity="PASSPORT",
            patterns=[
                Pattern("passport_an", r"\b[A-Z][0-9]{7,8}\b", 0.4),
                Pattern("passport_n", r"\b[0-9]{9}\b", 0.3),
            ],
            context=["passport", "travel document", "nationality", "issued by", "expiry", "date of issue"],
        ),
        PatternRecognizer(
            supported_entity="BANK_ACCOUNT",
            patterns=[
                Pattern("bank_account_sep", r"\b\d{3}[\-\s]?\d{5,9}\b", 0.3),
                Pattern("bank_account_plain", r"\b\d{7,12}\b", 0.2),
            ],
            context=["account number", "bank account", "account no", "account", "acct", "savings",
                     "DBS", "OCBC", "UOB", "POSB", "Citibank", "HSBC", "Standard Chartered"],
        ),
        DriverLicenseRecognizer(
            supported_entity="DRIVER_LICENSE",
            patterns=[Pattern("driver_license", r"\b(?=[A-Z0-9]*[0-9])[A-Z0-9]{6,17}\b", 0.3)],
            context=["driver", "driving", "license", "licence", "DL"],
        ),
        PatternRecognizer(
            supported_entity="CVV",
            patterns=[Pattern("cvv", r"\b\d{3,4}\b", 0.3)],
            context=["CVV", "CVC", "CVV2", "CVC2", "security code", "card verification"],
        ),
        PatternRecognizer(
            supported_entity="ORGANIZATION",
            patterns=[Pattern(
                "company_suffix",
                r"(?-i)(?:[A-Z][a-z]+\s){1,6}(?:Pte\.?\s*Ltd\.?|Pvt\.?\s*Ltd\.?|Sdn\.?\s*Bhd\.?|Ltd\.?|Limited|Inc\.?|Corp\.?|Corporation|LLC|LLP|GmbH|Berhad|PLC|&\s*Co\.?|and\s+Associates|Chartered\s+Accountants)\b",
                0.85,
            )],
        ),
        PanRecognizer(
            supported_entity="PAN",
            patterns=[Pattern("pan_in", r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", 0.7)],
            context=["PAN", "permanent account number", "income tax", "IT return", "assessee"],
        ),
        AadhaarRecognizer(
            supported_entity="AADHAAR",
            patterns=[Pattern("aadhaar_in", r"\b\d{4}\s?\d{4}\s?\d{4}\b", 0.4)],
            context=["aadhaar", "aadhar", "UID", "unique identification"],
        ),
        GstinRecognizer(
            supported_entity="GSTIN",
            patterns=[Pattern("gstin_in", r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Zz][A-Z\d]\b", 0.8)],
            context=["GSTIN", "GST", "goods and services tax", "GST number", "GST registration"],
        ),
        IfscRecognizer(
            supported_entity="IFSC_CODE",
            patterns=[Pattern("ifsc_in", r"\b[A-Z]{4}0[A-Z0-9]{6}\b", 0.75)],
            context=["IFSC", "branch code", "bank branch"],
        ),
        CinRecognizer(
            supported_entity="CIN",
            patterns=[Pattern("cin_in", r"\b[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\b", 0.8)],
            context=["CIN", "corporate identification number", "company registration"],
        ),
        PlausiblePhoneRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=[Pattern("in_phone", r"\b(?:\+?91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}\b", 0.5)],
            context=["phone", "mobile", "contact", "call", "tel"],
        ),
        FiscalYearRecognizer(
            supported_entity="DATE_TIME",
            patterns=[Pattern(
                "fiscal_year",
                r"\b(?:F\.?\s?Y\.?|A\.?\s?Y\.?|Financial\s+Year|Assessment\s+Year)\s?[:\-]?\s?\d{2,4}\s?[-–/]\s?\d{2,4}\b",
                0.6,
            )],
            context=["fiscal", "financial year", "assessment year", "FY", "AY"],
        ),
        PatternRecognizer(
            supported_entity="ID",
            patterns=[
                Pattern("id_separated", r"\b[A-Z]{1,5}[\/\-]\d{2,4}[\/\-]\d{2,6}\b", 0.4),
                Pattern("id_digits", r"\b\d{5,15}\b", 0.3),
            ],
            context=["reference", "ref", "id", "number", "no", "membership", "registration", "code"],
        ),
    ]


def reclassify(r, text):
    matched = text[r.start:r.end]
    ctx_before = text[max(0, r.start - 100):r.start]

    if r.entity_type == "DATE_TIME" and not _DATE_PATTERN.search(matched):
        return None
    if r.entity_type == "PHONE_NUMBER" and not re.search(r"[\d\s\-\+\(\)]{7,}", matched):
        return None
    if r.entity_type == "PHONE_NUMBER":
        ctx_lower = ctx_before.lower()
        if _BANK_CONTEXT.search(ctx_before) or "account" in ctx_lower or "acct" in ctx_lower:
            return RecognizerResult("ID", r.start, r.end, r.score)
    if r.entity_type == "ID" and re.search(r"^\+?\d[\d\s\-\(\)]{6,}$", matched.strip()):
        short_ctx = text[max(0, r.start - 30):r.start].lower()
        if _PHONE_CONTEXT.search(short_ctx) and not _BANK_CONTEXT.search(ctx_before):
            return RecognizerResult("PHONE_NUMBER", r.start, r.end, r.score)
    if r.entity_type == "PERSON" and _ORG_WORDS.search(matched):
        return RecognizerResult("ORGANIZATION", r.start, r.end, r.score)
    if r.entity_type == "PERSON" and (_ADDRESS_WORDS.search(matched) or _LOCATION_FRAGMENT.match(matched)):
        return RecognizerResult("LOCATION", r.start, r.end, r.score)
    if r.entity_type == "ORGANIZATION" and (_LOCATION_FRAGMENT.match(matched) or _ADDRESS_WORDS.search(matched) or _COUNTRY_NAMES.match(matched.strip())):
        return RecognizerResult("LOCATION", r.start, r.end, r.score)
    return r


def dedupe_results(results: List[RecognizerResult]) -> List[RecognizerResult]:
    if not results:
        return results
    results.sort(key=lambda r: (r.start, -(r.end - r.start), -r.score))
    deduped = [results[0]]
    for r in results[1:]:
        prev = deduped[-1]
        if r.start >= prev.start and r.end <= prev.end:
            continue
        if r.start < prev.end:
            if (r.end - r.start) > (prev.end - prev.start):
                deduped[-1] = r
            elif (r.end - r.start) == (prev.end - prev.start) and r.score > prev.score:
                deduped[-1] = r
        else:
            deduped.append(r)
    return deduped


def merge_adjacent(results: List[RecognizerResult], text: str) -> List[RecognizerResult]:
    if not results:
        return results
    results.sort(key=lambda r: r.start)
    merged = [results[0]]
    for r in results[1:]:
        prev = merged[-1]
        if r.entity_type == prev.entity_type and r.entity_type in ("PERSON", "ORGANIZATION", "LOCATION"):
            gap = text[prev.end:r.start]
            if len(gap) <= 2 and gap.strip() == "":
                merged[-1] = RecognizerResult(prev.entity_type, prev.start, r.end, max(prev.score, r.score))
                continue
        merged.append(r)
    return merged
