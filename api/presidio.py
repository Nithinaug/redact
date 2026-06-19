from functools import lru_cache
from typing import List

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.predefined_recognizers import SpacyRecognizer
from presidio_anonymizer import AnonymizerEngine

from .recognizers import build_custom_recognizers


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    engine = AnalyzerEngine()

    engine.registry.add_recognizer(SpacyRecognizer(
        supported_entities=["ORGANIZATION"],
        check_label_groups=[({"ORGANIZATION"}, {"ORG"})],
    ))

    engine.registry.remove_recognizer("UrlRecognizer")
    engine.registry.add_recognizer(PatternRecognizer(
        supported_entity="URL",
        patterns=[Pattern(name="url_strict", regex=r"\bhttps?://[^\s]+", score=0.6)],
    ))

    for recognizer in build_custom_recognizers():
        engine.registry.add_recognizer(recognizer)

    return engine


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


MIN_SCORE = 0.4


def analyze_text(
    text: str,
    language: str = "en",
    allow_list: List[str] = None,
) -> List[RecognizerResult]:
    results = get_analyzer().analyze(
        text=text,
        language=language,
        allow_list=allow_list or [],
        return_decision_process=True,
    )
    return [r for r in results if r.score >= MIN_SCORE]


def find_custom_terms(text: str, terms: List[str]) -> List[RecognizerResult]:
    results = []
    for term in terms:
        term = term.strip()
        if not term:
            continue
        lower_text = text.lower()
        lower_term = term.lower()
        start = 0
        while True:
            idx = lower_text.find(lower_term, start)
            if idx == -1:
                break
            results.append(RecognizerResult(
                entity_type="CUSTOM_TERM",
                start=idx,
                end=idx + len(term),
                score=1.0,
            ))
            start = idx + len(term)
    return results


def anonymize_text(text: str, analyzer_results):
    return get_anonymizer().anonymize(text=text, analyzer_results=analyzer_results)


def supported_entities(language: str = "en"):
    return sorted(get_analyzer().get_supported_entities(language))
