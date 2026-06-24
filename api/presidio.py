from functools import lru_cache
from typing import List

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import TransformersNlpEngine
from presidio_anonymizer import AnonymizerEngine

from .fixes import build_custom_recognizers, reclassify, dedupe_results, merge_adjacent

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


def supported_entities(language: str = "en"):
    return sorted(get_analyzer().get_supported_entities(language))
