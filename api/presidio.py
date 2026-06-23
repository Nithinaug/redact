from functools import lru_cache
from typing import List

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import TransformersNlpEngine
from presidio_anonymizer import AnonymizerEngine

from .recognizers import build_custom_recognizers

MIN_SCORE = 0.5


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    nlp_engine = TransformersNlpEngine(
        models=[{"lang_code": "en", "model_name": {
            "spacy": "en_core_web_sm",
            "transformers": "StanfordAIMI/stanford-deidentifier-base",
        }}],
    )
    nlp_engine.load()
    engine = AnalyzerEngine(nlp_engine=nlp_engine)
    engine.registry.remove_recognizer("UrlRecognizer")
    engine.registry.remove_recognizer("DateRecognizer")
    engine.registry.remove_recognizer("PhoneRecognizer")
    engine.registry.add_recognizer(PatternRecognizer(
        supported_entity="URL",
        patterns=[Pattern("url_strict", r"\bhttps?://[^\s]+", 0.6)],
    ))
    for r in build_custom_recognizers():
        engine.registry.add_recognizer(r)
    return engine


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


def _dedupe_results(results: List[RecognizerResult]) -> List[RecognizerResult]:
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


import re

_DATE_PATTERN = re.compile(
    r"(?:"
    r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s*\d{2,4}\b"
    r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4}\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b"
    r"|\b(?:19|20)\d{2}\b"
    r")",
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


def _is_valid_date(text: str, start: int, end: int) -> bool:
    return bool(_DATE_PATTERN.search(text[start:end]))


def _looks_like_address(matched_text: str) -> bool:
    return bool(_ADDRESS_WORDS.search(matched_text))


def _is_location_fragment(matched_text: str) -> bool:
    return bool(_LOCATION_FRAGMENT.match(matched_text))


def analyze_text(text: str, language: str = "en") -> List[RecognizerResult]:
    results = get_analyzer().analyze(text=text, language=language, return_decision_process=True)
    filtered = []
    for r in results:
        if r.score < MIN_SCORE:
            continue
        matched = text[r.start:r.end]
        if r.entity_type == "DATE_TIME" and not _is_valid_date(text, r.start, r.end):
            continue
        if r.entity_type == "PHONE_NUMBER" and not re.search(r"[\d\s\-\+\(\)]{7,}", matched):
            continue
        if r.entity_type == "PHONE_NUMBER":
            context_window = text[max(0, r.start - 100):r.start]
            if _BANK_CONTEXT.search(context_window):
                r = RecognizerResult("ID", r.start, r.end, r.score)
        if r.entity_type == "PERSON" and (_looks_like_address(matched) or _is_location_fragment(matched)):
            r = RecognizerResult("LOCATION", r.start, r.end, r.score)
        if r.entity_type == "ORGANIZATION" and (_is_location_fragment(matched) or _looks_like_address(matched)):
            r = RecognizerResult("LOCATION", r.start, r.end, r.score)
        filtered.append(r)
    return _dedupe_results(filtered)


def anonymize_text(text: str, analyzer_results):
    return get_anonymizer().anonymize(text=text, analyzer_results=analyzer_results)


def supported_entities(language: str = "en"):
    return sorted(get_analyzer().get_supported_entities(language))
