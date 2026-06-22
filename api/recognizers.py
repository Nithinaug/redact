from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.predefined_recognizers import SgFinRecognizer, SgUenRecognizer


def build_custom_recognizers():
    return [
        SgFinRecognizer(),
        SgUenRecognizer(),
        PatternRecognizer(
            supported_entity="SG_PHONE_NUMBER",
            patterns=[Pattern("sg_phone", r"\b[89]\d{7}\b", 0.5)],
            context=["phone", "mobile", "contact", "call", "tel", "hp"],
        ),
        PatternRecognizer(
            supported_entity="PASSPORT",
            patterns=[
                Pattern("passport_an", r"\b[A-Z][0-9]{7,8}\b", 0.4),
                Pattern("passport_n", r"\b[0-9]{9}\b", 0.3),
            ],
            context=["passport", "travel document", "nationality", "issued by", "expiry", "date of issue"],
        ),
        PatternRecognizer(
            supported_entity="BANK_ACCOUNT",
            patterns=[Pattern("bank_account", r"\b\d{3}[\-\s]?\d{5,9}\b", 0.3)],
            context=["account number", "bank account", "account no", "acct", "savings",
                     "DBS", "OCBC", "UOB", "POSB", "Citibank", "HSBC", "Standard Chartered"],
        ),
        PatternRecognizer(
            supported_entity="DRIVER_LICENSE",
            patterns=[Pattern("driver_license", r"\b(?=[A-Z0-9]*[0-9])[A-Z0-9]{6,12}\b", 0.3)],
            context=["driver", "driving", "license", "licence", "DL"],
        ),
        PatternRecognizer(
            supported_entity="ORGANIZATION",
            patterns=[Pattern(
                "company_suffix",
                r"(?-i)(?:[A-Z][a-z]+\s){1,6}(?:Pte\.?\s*Ltd\.?|Pvt\.?\s*Ltd\.?|Sdn\.?\s*Bhd\.?|Ltd\.?|Limited|Inc\.?|Corp\.?|Corporation|LLC|LLP|GmbH|Berhad|PLC)\b",
                0.85,
            )],
        ),
    ]
