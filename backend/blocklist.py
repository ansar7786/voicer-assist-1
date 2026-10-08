"""
Blocklist filter for SIH26097.

Drops text containing:
- Caste / community / religion terms (Telugu, Hindi, English).
- Address-like strings (street, ward, door-number patterns).
- Aadhaar-style 12-digit strings and phone-like 10-digit strings.

Rules:
- Returns (True, reason_label) if text should be blocked.
- Returns (False, "") if text is clean.
- NEVER log or return the original text.
"""
import re
import logging

logger = logging.getLogger("voicer_live")


# ---------------------------------------------------------------------------
# Word lists  (kept short; extend from real vocabulary without changing API)
# ---------------------------------------------------------------------------

# Caste terms – English, romanized, Telugu script, Hindi Devanagari
_CASTE_TERMS: list[str] = [
    # English / romanized
    "brahmin", "brahman", "kshatriya", "vaishya", "shudra", "dalit",
    "sc", "st", "obc", "bc", "forward caste", "scheduled caste",
    "scheduled tribe", "reddy", "naidu", "kamma", "kapu", "mala", "madiga",
    "goud", "yadav", "kuruma", "lambada", "banjara", "komati", "balija",
    "caste", "jati", "jaat", "gotra",
    # Telugu script
    "కులం", "కుల", "జాతి", "బ్రాహ్మణ", "క్షత్రియ", "వైశ్య", "శూద్ర",
    "దళిత", "రెడ్డి", "నాయుడు", "కమ్మ", "కాపు", "మాల", "మాదిగ",
    "గౌడ్", "యాదవ్", "కురుమ", "లంబాడ", "గోత్రం",
    # Hindi Devanagari
    "जाति", "ब्राह्मण", "क्षत्रिय", "वैश्य", "शूद्र", "दलित",
    "यादव", "जाट", "गुर्जर", "ठाकुर", "राजपूत", "गोत्र", "कुर्मी",
]

# Religion terms
_RELIGION_TERMS: list[str] = [
    # English / romanized
    "hindu", "muslim", "christian", "sikh", "jain", "buddhist", "parsi",
    "islam", "christianity", "sikhism", "religion", "panth", "dharma",
    "mosque", "temple", "church", "mandir", "masjid",
    # Telugu script
    "హిందూ", "ముస్లిం", "క్రైస్తవ", "సిక్కు", "జైన", "బౌద్ధ",
    "మతం", "దేవాలయం", "మసీదు", "చర్చి", "మందిర్",
    # Hindi Devanagari
    "हिंदू", "मुस्लिम", "इस्लाम", "ईसाई", "सिख", "जैन", "बौद्ध",
    "धर्म", "मंदिर", "मस्जिद", "गिरजाघर",
]

# Address patterns (common tokens; door numbers handled by regex below)
_ADDRESS_TERMS: list[str] = [
    # English
    "door no", "d.no", "h.no", "house no", "flat no", "street",
    "road", "ward", "nagar", "colony", "district", "mandal",
    "pincode", "pin code", "zip",
    # Telugu
    "వీధి", "కాలనీ", "నగర్", "మండల్", "పిన్‌కోడ్",
    # Hindi
    "गली", "मोहल्ला", "नगर", "पिन कोड", "पता",
]

# Separate ASCII and non-ASCII terms for different matching strategies
def _is_ascii(s: str) -> bool:
    return all(ord(c) < 128 for c in s)


def _build_word_re(terms: list[str]) -> re.Pattern:
    """
    ASCII terms: use word-boundary \\b for precision.
    Non-ASCII terms (Telugu/Hindi script): use lookahead/lookbehind with
    Unicode whitespace since \\b doesn't work across script boundaries.
    Build two alternations and combine.
    """
    ascii_terms = sorted([t for t in terms if _is_ascii(t)], key=len, reverse=True)
    nonascii_terms = sorted([t for t in terms if not _is_ascii(t)], key=len, reverse=True)

    parts = []
    if ascii_terms:
        alts = "|".join(re.escape(t) for t in ascii_terms)
        parts.append(rf"(?i)(?<![\w])(?:{alts})(?![\w])")
    if nonascii_terms:
        alts = "|".join(re.escape(t) for t in nonascii_terms)
        # Use (?:^|\s|[,;।।.!?]) style delimiters for script text
        parts.append(rf"(?:{alts})")

    combined = "|".join(parts)
    return re.compile(combined)


_CASTE_RE = _build_word_re(_CASTE_TERMS)
_RELIGION_RE = _build_word_re(_RELIGION_TERMS)
_ADDRESS_RE = _build_word_re(_ADDRESS_TERMS)

# Numeric patterns — ASCII-only so \b works fine here
_AADHAAR_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")   # 12-digit Aadhaar
_PHONE_RE = re.compile(r"\b[6-9]\d{9}\b")                          # 10-digit mobile


def check_blocked(field_name: str, text: str) -> tuple[bool, str]:
    """
    Returns (True, label) if the text should be blocked, (False, "") otherwise.
    Never logs or returns the original text.

    Parameters
    ----------
    field_name : human-readable field label for logging (e.g. "interests")
    text       : the string to check
    """
    if not text or not text.strip():
        return False, ""

    if _CASTE_RE.search(text):
        logger.info("EVENT: blocked_field | field: %s | reason: caste_community", field_name)
        return True, "caste_community"

    if _RELIGION_RE.search(text):
        logger.info("EVENT: blocked_field | field: %s | reason: religion", field_name)
        return True, "religion"

    if _ADDRESS_RE.search(text):
        logger.info("EVENT: blocked_field | field: %s | reason: address", field_name)
        return True, "address"

    if _AADHAAR_RE.search(text):
        logger.info("EVENT: blocked_field | field: %s | reason: id_number_12digit", field_name)
        return True, "id_number"

    if _PHONE_RE.search(text):
        logger.info("EVENT: blocked_field | field: %s | reason: phone_number", field_name)
        return True, "id_number"

    return False, ""
