import json
import logging
import os
from logging.config import fileConfig
from pathlib import Path
from typing import Tuple

from flask import Flask, Response, jsonify, request
from presidio_analyzer import (
    AnalyzerEngine,
    AnalyzerEngineProvider,
    AnalyzerRequest,
    BatchAnalyzerEngine,
    Pattern,
    PatternRecognizer,
)
from presidio_analyzer.predefined_recognizers import SgFinRecognizer, SgUenRecognizer
from werkzeug.exceptions import HTTPException

DEFAULT_PORT = "3000"
DEFAULT_BATCH_SIZE = "500"
DEFAULT_N_PROCESS = "1"
LOGGING_CONF_FILE = "logging_analyzer.ini"


def build_custom_recognizers():
    recognizers = []
    recognizers.append(SgFinRecognizer())
    recognizers.append(SgUenRecognizer())
    recognizers.append(PatternRecognizer(
        supported_entity="SG_PHONE_NUMBER",
        patterns=[Pattern(name="sg_phone", regex=r"\b[89]\d{7}\b", score=0.5)],
        context=["phone", "mobile", "contact", "call", "tel", "hp"]
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="PASSPORT",
        patterns=[
            Pattern(name="passport_alpha_numeric", regex=r"\b[A-Z]{1,2}[0-9]{6,9}\b", score=0.4),
            Pattern(name="passport_numeric", regex=r"\b[0-9]{9}\b", score=0.3),
        ],
        context=["passport", "travel document", "nationality", "issued by", "expiry", "date of issue"]
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="BANK_ACCOUNT",
        patterns=[Pattern(name="bank_account_generic", regex=r"\b\d{8,12}\b", score=0.3)],
        context=["account number", "bank account", "account no", "acct", "savings", "current account",
                  "DBS", "OCBC", "UOB", "POSB", "Citibank", "HSBC", "Standard Chartered"]
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="DRIVER_LICENSE",
        patterns=[Pattern(name="driver_license_generic", regex=r"\b(?=[A-Z0-9]*[0-9])[A-Z0-9]{6,12}\b", score=0.3)],
        context=["driver", "driving", "license", "licence", "DL", "driving license", "driving licence"]
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="DATE_OF_BIRTH",
        patterns=[
            Pattern(name="dob_dd_mm_yyyy", regex=r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-](19|20)\d\d\b", score=0.5),
        ],
        context=["date of birth", "DOB", "born", "birthday", "birth date", "d.o.b"]
    ))

    return recognizers


class Server:
    def __init__(self):
        fileConfig(Path(Path(__file__).parent, LOGGING_CONF_FILE))
        self.logger = logging.getLogger("presidio-analyzer")
        self.logger.setLevel(os.environ.get("LOG_LEVEL", self.logger.level))
        self.app = Flask(__name__)
        analyzer_conf_file = os.environ.get("ANALYZER_CONF_FILE") or None
        nlp_engine_conf_file = os.environ.get("NLP_CONF_FILE") or None
        recognizer_registry_conf_file = (
                os.environ.get("RECOGNIZER_REGISTRY_CONF_FILE") or None
        )

        self.logger.info("Starting analyzer engine")
        self.engine: AnalyzerEngine = AnalyzerEngineProvider(
            analyzer_engine_conf_file=analyzer_conf_file,
            nlp_engine_conf_file=nlp_engine_conf_file,
            recognizer_registry_conf_file=recognizer_registry_conf_file,
        ).create_engine()

        for recognizer in build_custom_recognizers():
            self.engine.registry.add_recognizer(recognizer)
            self.logger.info(f"Registered recognizer: {recognizer.supported_entities}")

        self.batch_engine = BatchAnalyzerEngine(self.engine)
        self.logger.info("Presidio Analyzer service is up")

        @self.app.route("/health")
        def health() -> str:
            return "Presidio Analyzer service is up"

        @self.app.route("/analyze", methods=["POST"])
        def analyze() -> Tuple[str, int]:
            try:
                req_data = AnalyzerRequest(request.get_json())
                if not req_data.text:
                    raise Exception("No text provided")

                batch_request = isinstance(req_data.text, list)
                batch = req_data.text if batch_request else [req_data.text]

                if not req_data.language:
                    raise Exception("No language provided")
                else:
                    self.engine.get_supported_entities(req_data.language)

                iterator = self.batch_engine.analyze_iterator(
                    texts=batch,
                    batch_size=min(len(batch), int(os.environ.get("BATCH_SIZE", DEFAULT_BATCH_SIZE))),
                    language=req_data.language,
                    correlation_id=req_data.correlation_id,
                    score_threshold=req_data.score_threshold,
                    entities=req_data.entities,
                    return_decision_process=req_data.return_decision_process,
                    ad_hoc_recognizers=req_data.ad_hoc_recognizers,
                    context=req_data.context,
                    allow_list=req_data.allow_list,
                    allow_list_match=req_data.allow_list_match,
                    regex_flags=req_data.regex_flags,
                    n_process=min(len(batch), int(os.environ.get("N_PROCESS", DEFAULT_N_PROCESS)))
                )

                results = []
                for recognizer_result_list in iterator:
                    _exclude_attributes_from_dto(recognizer_result_list)
                    results.append(recognizer_result_list)

                return Response(
                    json.dumps(
                        results if batch_request else results[0],
                        default=lambda o: o.to_dict(),
                        sort_keys=True,
                    ),
                    content_type="application/json",
                )
            except TypeError as te:
                error_msg = f"Failed to parse /analyze request for AnalyzerEngine.analyze(). {te.args[0]}"
                self.logger.error(error_msg)
                return jsonify(error=error_msg), 400

            except Exception as e:
                self.logger.error(f"A fatal error occurred during execution of AnalyzerEngine.analyze(). {e}")
                return jsonify(error=e.args[0]), 500

        @self.app.route("/recognizers", methods=["GET"])
        def recognizers() -> Tuple[str, int]:
            language = request.args.get("language")
            try:
                recognizers_list = self.engine.get_recognizers(language)
                names = [o.name for o in recognizers_list]
                return jsonify(names), 200
            except Exception as e:
                self.logger.error(f"A fatal error occurred during execution of AnalyzerEngine.get_recognizers(). {e}")
                return jsonify(error=e.args[0]), 500

        @self.app.route("/supportedentities", methods=["GET"])
        def supported_entities() -> Tuple[str, int]:
            language = request.args.get("language")
            try:
                entities_list = self.engine.get_supported_entities(language)
                return jsonify(entities_list), 200
            except Exception as e:
                self.logger.error(f"A fatal error occurred during execution of AnalyzerEngine.supported_entities(). {e}")
                return jsonify(error=e.args[0]), 500

        @self.app.errorhandler(HTTPException)
        def http_exception(e):
            return jsonify(error=e.description), e.code


def _exclude_attributes_from_dto(recognizer_result_list):
    excluded_attributes = ["recognition_metadata"]
    for result in recognizer_result_list:
        for attr in excluded_attributes:
            if hasattr(result, attr):
                delattr(result, attr)


def create_app():
    server = Server()
    return server.app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    app.run(host="0.0.0.0", port=port)