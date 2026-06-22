from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.predefined_recognizers import SgFinRecognizer, SgUenRecognizer

_MONTHS = r"January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec"

_DAY = r"(0?[1-9]|[12][0-9]|3[01])"
_YEAR = r"(19|20)\d\d"


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
                0.7,
            )],
        ),
        PatternRecognizer(
            supported_entity="DATE_OF_BIRTH",
            patterns=[
                Pattern("dob_numeric", rf"\b{_DAY}[\/\-](0?[1-9]|1[012])[\/\-]{_YEAR}\b", 0.5),
                Pattern("dob_dmy", rf"\b{_DAY}[\s\-]({_MONTHS})[\s\-,]*{_YEAR}\b", 0.5),
                Pattern("dob_mdy", rf"\b({_MONTHS})[\s]{_DAY},?\s*{_YEAR}\b", 0.5),
            ],
            context=["date of birth", "DOB", "born", "birthday", "birth date", "d.o.b"],
        ),
    ]
