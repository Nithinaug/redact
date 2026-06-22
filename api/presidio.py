from functools import lru_cache
from typing import List

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import SpacyRecognizer
from presidio_anonymizer import AnonymizerEngine

from .recognizers import build_custom_recognizers

MIN_SCORE = 0.5


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    nlp_config = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_trf"}]}
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
    engine = AnalyzerEngine(nlp_engine=nlp_engine)
    engine.registry.add_recognizer(SpacyRecognizer(
        supported_entities=["ORGANIZATION"],
        check_label_groups=[({"ORGANIZATION"}, {"ORG"})],
    ))
    engine.registry.remove_recognizer("UrlRecognizer")
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


def analyze_text(text: str, language: str = "en", allow_list: List[str] = None) -> List[RecognizerResult]:
    results = get_analyzer().analyze(text=text, language=language, allow_list=allow_list or [], return_decision_process=True)
    filtered = [r for r in results if r.score >= MIN_SCORE]
    return _dedupe_results(filtered)


def find_custom_terms(text: str, terms: List[str]) -> List[RecognizerResult]:
    results = []
    lower = text.lower()
    for term in terms:
        term = term.strip()
        if not term:
            continue
        lt, start = term.lower(), 0
        while (idx := lower.find(lt, start)) != -1:
            results.append(RecognizerResult("CUSTOM_TERM", idx, idx + len(term), 1.0))
            start = idx + len(term)
    return results


def anonymize_text(text: str, analyzer_results):
    return get_anonymizer().anonymize(text=text, analyzer_results=analyzer_results)


def supported_entities(language: str = "en"):
    return sorted(get_analyzer().get_supported_entities(language))
