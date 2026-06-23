import re
from functools import lru_cache
from typing import List

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import TransformersNlpEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_image_redactor import ImageRedactorEngine, ImageAnalyzerEngine

from .fixes import build_custom_recognizers, reclassify, dedupe_results, merge_adjacent

MIN_SCORE = 0.5

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


def analyze_text(text: str, language: str = "en") -> List[RecognizerResult]:
    results = get_analyzer().analyze(text=text, language=language, return_decision_process=True)
    filtered = []
    for r in results:
        if r.score < MIN_SCORE:
            continue
        r = reclassify(r, text)
        if r:
            filtered.append(r)
    deduped = dedupe_results(filtered)
    return merge_adjacent(deduped, text)


def anonymize_text(text: str, analyzer_results):
    return get_anonymizer().anonymize(text=text, analyzer_results=analyzer_results)


@lru_cache(maxsize=1)
def get_image_redactor() -> ImageRedactorEngine:
    image_analyzer = ImageAnalyzerEngine(analyzer_engine=get_analyzer())
    return ImageRedactorEngine(image_analyzer_engine=image_analyzer)


def supported_entities(language: str = "en"):
    return sorted(get_analyzer().get_supported_entities(language))
