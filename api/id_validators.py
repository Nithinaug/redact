import datetime
import re

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_valid(digits: str) -> bool:
    if not digits.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


_PAN_HOLDER_CODES = set("ABCFGHJLPT")


def pan_valid(pan: str) -> bool:
    pan = pan.strip().upper()
    if len(pan) != 10:
        return False
    return pan[3] in _PAN_HOLDER_CODES


_GSTIN_CODEPOINTS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

_GST_STATE_CODES = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
    "31", "32", "33", "34", "35", "36", "37", "38",
}


def gstin_valid(gstin: str) -> bool:
    gstin = gstin.strip().upper()
    if len(gstin) != 15:
        return False
    if gstin[:2] not in _GST_STATE_CODES:
        return False
    if not pan_valid(gstin[2:12]):
        return False
    if any(ch not in _GSTIN_CODEPOINTS for ch in gstin):
        return False

    factor = 1
    total = 0
    for ch in gstin[:14]:
        code_point = _GSTIN_CODEPOINTS.index(ch) * factor
        total += (code_point // 36) + (code_point % 36)
        factor = 1 if factor == 2 else 2
    check_code_point = (36 - (total % 36)) % 36
    return _GSTIN_CODEPOINTS[check_code_point] == gstin[14]


_INDIA_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "DD", "DL", "DN",
    "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "MP",
    "MH", "ML", "MN", "MZ", "NL", "OR", "PY", "PB", "RJ", "SK",
    "TN", "TG", "TR", "UK", "UP", "UA", "WB",
}


def cin_valid(cin: str) -> bool:
    cin = cin.strip().upper()
    if len(cin) != 21:
        return False
    if cin[0] not in ("L", "U"):
        return False
    if not cin[1:6].isdigit():
        return False
    if cin[6:8] not in _INDIA_STATE_CODES:
        return False
    year_str = cin[8:12]
    if not year_str.isdigit():
        return False
    year = int(year_str)
    current_year = datetime.date.today().year
    if year < 1850 or year > current_year:
        return False
    if not cin[12:15].isalpha():
        return False
    if not cin[15:21].isdigit():
        return False
    return True


def ifsc_valid(ifsc: str) -> bool:
    ifsc = ifsc.strip().upper()
    if len(ifsc) != 11:
        return False
    if not ifsc[:4].isalpha():
        return False
    if ifsc[4] != "0":
        return False
    return ifsc[5:].isalnum()


def driver_license_valid(dl: str) -> bool:
    dl = dl.strip().upper()
    if len(dl) < 8:
        return False
    if dl[:2] not in _INDIA_STATE_CODES:
        return False
    return dl[2:].isalnum()


_NRIC_ST_TABLE = "JZIHGFEDCBA"
_NRIC_FG_TABLE = "XWUTRQPNMLK"
_NRIC_WEIGHTS = [2, 7, 6, 5, 4, 3, 2]


def nric_fin_valid(nric: str) -> bool:
    nric = nric.strip().upper()
    if len(nric) != 9:
        return False
    prefix, digits, check = nric[0], nric[1:8], nric[8]
    if prefix not in "STFG" or not digits.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(digits, _NRIC_WEIGHTS))
    if prefix in "TG":
        total += 4
    index = total % 11
    table = _NRIC_ST_TABLE if prefix in "ST" else _NRIC_FG_TABLE
    return table[index] == check


def _no_dead_giveaway_pattern(digits: str) -> bool:
    if len(set(digits)) == 1:
        return False
    ascending = "".join(str(i % 10) for i in range(len(digits)))
    descending = "".join(str((9 - i) % 10) for i in range(len(digits)))
    return digits not in (ascending, descending)


_FISCAL_YEAR_PARTS = re.compile(r"(\d{2,4})\s?[-–/]\s?(\d{2,4})")


def fiscal_year_valid(text: str) -> bool:
    match = _FISCAL_YEAR_PARTS.search(text)
    if not match:
        return False
    first, second = match.groups()
    year1 = int(first) if len(first) == 4 else 2000 + int(first)
    if len(second) == 4:
        year2 = int(second)
    else:
        year2 = (year1 // 100) * 100 + int(second)
        if year2 < year1:
            year2 += 100
    current_year = datetime.date.today().year
    if year1 < 1950 or year1 > current_year + 1:
        return False
    return year2 == year1 + 1


def phone_plausible(phone: str) -> bool:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return _no_dead_giveaway_pattern(digits)


def passport_plausible(passport: str) -> bool:
    digits = "".join(ch for ch in passport if ch.isdigit())
    if len(digits) < 6:
        return True
    return _no_dead_giveaway_pattern(digits)
