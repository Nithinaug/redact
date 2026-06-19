from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from .recognizers import build_custom_recognizers


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    engine = AnalyzerEngine()
    for recognizer in build_custom_recognizers():
        engine.registry.add_recognizer(recognizer)
    return engine


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


def analyze_text(text: str, language: str = "en"):
    return get_analyzer().analyze(text=text, language=language)


def anonymize_text(text: str, analyzer_results):
    return get_anonymizer().anonymize(text=text, analyzer_results=analyzer_results)


def supported_entities(language: str = "en"):
    return sorted(get_analyzer().get_supported_entities(language))
