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
    results.sort(key=lambda r: (r.start, -r.score))
    deduped = [results[0]]
    for r in results[1:]:
        prev = deduped[-1]
        if r.start < prev.end:
            if r.score > prev.score:
                deduped[-1] = r
        else:
            deduped.append(r)
    return deduped


import re

_DATE_PATTERN = re.compile(
    r"(?:"
    r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b"          # 01/02/2024, 1-2-24
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s*\d{2,4}\b"  # Jan 1, 2024
    r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4}\b"    # 1 January 2024
    r"|\b(?:19|20)\d{2}\b"                               # 2024, 2023
    r")",
    re.IGNORECASE,
)


def _is_valid_date(text: str, start: int, end: int) -> bool:
    return bool(_DATE_PATTERN.search(text[start:end]))


def analyze_text(text: str, language: str = "en") -> List[RecognizerResult]:
    results = get_analyzer().analyze(text=text, language=language, return_decision_process=True)
    filtered = []
    for r in results:
        if r.score < MIN_SCORE:
            continue
        if r.entity_type == "DATE_TIME" and not _is_valid_date(text, r.start, r.end):
            continue
        if r.entity_type == "PHONE_NUMBER" and not re.search(r"[\d\s\-\+\(\)]{7,}", text[r.start:r.end]):
            continue
        filtered.append(r)
    return _dedupe_results(filtered)


def anonymize_text(text: str, analyzer_results):
    return get_anonymizer().anonymize(text=text, analyzer_results=analyzer_results)


def supported_entities(language: str = "en"):
    return sorted(get_analyzer().get_supported_entities(language))
