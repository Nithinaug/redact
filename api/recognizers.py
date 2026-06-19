from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.predefined_recognizers import SgFinRecognizer, SgUenRecognizer


def build_custom_recognizers():
    recognizers = []
    recognizers.append(SgFinRecognizer())
    recognizers.append(SgUenRecognizer())
    recognizers.append(PatternRecognizer(
        supported_entity="PASSPORT",
        patterns=[
            Pattern(name="passport_alpha_numeric", regex=r"\b[A-Z]{1,2}[0-9]{6,9}\b", score=0.4),
            Pattern(name="passport_numeric", regex=r"\b[0-9]{9}\b", score=0.3),
        ],
        context=["passport", "travel document", "nationality", "issued by", "expiry", "date of issue"],
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="BANK_ACCOUNT",
        patterns=[Pattern(name="bank_account_generic", regex=r"\b\d{8,12}\b", score=0.3)],
        context=["account number", "bank account", "account no", "acct", "savings", "current account"],
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="DRIVER_LICENSE",
        patterns=[Pattern(name="driver_license_generic", regex=r"\b(?=[A-Z0-9]*[0-9])[A-Z0-9]{6,12}\b", score=0.3)],
        context=["driver", "driving", "license", "licence", "DL", "driving license", "driving licence"],
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="DATE_OF_BIRTH",
        patterns=[
            Pattern(name="dob_dd_mm_yyyy", regex=r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-](19|20)\d\d\b", score=0.5),
        ],
        context=["date of birth", "DOB", "born", "birthday", "birth date", "d.o.b"],
    ))
    return recognizers
