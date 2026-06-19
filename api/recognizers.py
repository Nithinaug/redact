from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.predefined_recognizers import SgFinRecognizer, SgUenRecognizer

_MONTHS = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
)


def build_custom_recognizers():
    recognizers = []
    recognizers.append(SgFinRecognizer())
    recognizers.append(SgUenRecognizer())
    recognizers.append(PatternRecognizer(
        supported_entity="SG_PHONE_NUMBER",
        patterns=[Pattern(name="sg_phone", regex=r"\b[89]\d{7}\b", score=0.5)],
        context=["phone", "mobile", "contact", "call", "tel", "hp"],
    ))
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
        context=["account number", "bank account", "account no", "acct", "savings", "current account",
                 "DBS", "OCBC", "UOB", "POSB", "Citibank", "HSBC", "Standard Chartered"],
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="DRIVER_LICENSE",
        patterns=[Pattern(name="driver_license_generic", regex=r"\b(?=[A-Z0-9]*[0-9])[A-Z0-9]{6,12}\b", score=0.3)],
        context=["driver", "driving", "license", "licence", "DL", "driving license", "driving licence"],
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="ORGANIZATION",
        patterns=[Pattern(
            name="company_suffix",
            regex=(
                r"(?-i)(?:[A-Z][a-z]+\s){1,6}"
                r"(?:Pte\.?\s*Ltd\.?|Pvt\.?\s*Ltd\.?|Sdn\.?\s*Bhd\.?|"
                r"Ltd\.?|Limited|Inc\.?|Incorporated|Corp\.?|Corporation|"
                r"LLC|LLP|GmbH|Berhad|S\.A\.|PLC)\b"
            ),
            score=0.7,
        )],
    ))
    recognizers.append(PatternRecognizer(
        supported_entity="DATE_OF_BIRTH",
        patterns=[
            # 14/03/1985 or 14-03-1985
            Pattern(name="dob_numeric", regex=r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-](19|20)\d\d\b", score=0.5),
            # 26-April-2026 or 26 April 2026
            Pattern(name="dob_text_month_dmy", regex=rf"\b(0?[1-9]|[12][0-9]|3[01])[\s\-]({_MONTHS})[\s\-,]*(19|20)\d\d\b", score=0.5),
            # April 26, 2026 or April 26 2026
            Pattern(name="dob_text_month_mdy", regex=rf"\b({_MONTHS})[\s](0?[1-9]|[12][0-9]|3[01]),?\s*(19|20)\d\d\b", score=0.5),
        ],
        context=["date of birth", "DOB", "born", "birthday", "birth date", "d.o.b", "dob"],
    ))
    return recognizers
