"""
Vocabulary normalizer for SIH26097 Live Voice Livelihood Pathway Engine.
Maps Telugu script, Hindi Devanagari, romanized text, and English synonyms to canonical tags.
Uses whole-token and exact boundary matching to prevent substring collision errors.
"""
import re
from typing import Optional, List

# Canonical trade mappings
TRADE_SYNONYMS = {
    "tailoring": [
        # English / Romanized
        "tailoring", "tailor", "silai", "silayi", "kuttu", "kuttupani", "stitching",
        "stitch", "sewing", "sew", "embroider", "embroidery", "kadhai", "darzi",
        "dressmaking", "garment", "garments", "apparel", "sewing machine operator",
        # Telugu script
        "కుట్టు", "కుట్టుపని", "కుట్టు పని", "టైలరింగ్", "బట్టలు కుట్టడం", "మిషన్ కుట్టడం",
        "సూది దారం", "ఎంబ్రాయిడరీ", "కుట్లు", "దర్జీ", "కుట్టుమిషన్",
        # Hindi Devanagari
        "सिलाई", "सिलाई कढ़ाई", "सिलाई का काम", "दर्जी", "टेलरिंग", "कढ़ाई",
        "कपडे सिलना", "कसीदाकारी", "सिलाई मशीन"
    ],
    "catering": [
        # English / Romanized
        "catering", "cooking", "cook", "chef", "vanta", "vantapani", "food preparation",
        "bakery", "baking", "halwai", "bawarchi", "hotel work", "kitchen", "kitchen helper",
        "food service", "culinary", "restaurant", "hospitality", "street food",
        # Telugu script
        "వంట", "వంటపని", "క్యాటరింగ్", "హోటల్ పని", "భోజనం", "చెఫ్", "పాకశాస్త్రం", "ఆహార తయారీ",
        # Hindi Devanagari
        "खाना बनाना", "बावर्ची", "कुक", "कैटरिंग", "हलवाई", "होटल का काम", "रसोई", "भोजन"
    ],
    "electrician": [
        # English / Romanized
        "electrician", "electrical", "wiring", "bijli", "bijlee", "current", "current pani",
        "current work", "wireman", "home appliances", "electrical repair",
        # Telugu script
        "ఎలక్ట్రీషియన్", "విద్యుత్ పని", "వైరింగ్", "కరెంట్ పని", "బోర్డు ఫిట్టింగ్",
        # Hindi Devanagari
        "इलेक्ट्रीशियन", "बिजली का काम", "वायरिंग", "बिजली मिस्त्री", "करंट"
    ],
    "solar_technician": [
        # English / Romanized
        "solar", "solar technician", "solar pv", "solar panel", "suryamitra",
        "solar installer", "green jobs", "renewable",
        # Telugu script
        "సోలార్", "సౌర విద్యుత్", "సోలార్ ప్యానెల్", "సూర్యమిత్ర",
        # Hindi Devanagari
        "सोलर", "सौर ऊर्जा", "सोलर पैनल", "सूर्यमित्र", "सोलर इंस्टॉलेशन"
    ],
    "dairy_farming": [
        # English / Romanized
        "dairy", "dairy farming", "cattle", "cows", "buffaloes", "milk business",
        "pashupalan", "paadi", "dairy farmer", "livestock", "animal husbandry",
        # Telugu script
        "పాడి పరిశ్రమ", "పాడి", "గేదెలు", "ఆవులు", "పాల వ్యాపారం", "పశుపోషణ", "పశువుల పెంపకం",
        # Hindi Devanagari
        "डेयरी", "पशुपालन", "गाय भैंस", "दूध का काम", "डेयरी फार्मिंग", "पशु पालन"
    ],
    "beauty_wellness": [
        # English / Romanized
        "beauty", "beauty parlour", "parlour", "beautician", "makeup", "grooming",
        "salon", "bridal makeup", "hair styling", "wellness",
        # Telugu script
        "బ్యూటీ పార్లర్", "మేకప్", "బ్యూటీషియన్", "ముస్తాబు", "అందం", "పార్లర్",
        # Hindi Devanagari
        "ब्यूटी पार्लर", "ब्यूटीशियन", "मेकअप", "पार्लर", "सौंदर्य", "सैलून"
    ],
    "retail_sales": [
        # English / Romanized
        "retail", "sales", "shopkeeper", "counter sales", "dukaan", "store helper",
        "sales executive", "cashier", "supermarket",
        # Telugu script
        "సేల్స్", "దుకాణం పని", "రిటైల్", "కౌంటర్ సేల్స్", "అమ్మకాలు", "షాప్",
        # Hindi Devanagari
        "सेल्स", "दुकान का काम", "रिटेल", "बिक्री", "सेल्समैन", "दुकान"
    ]
}

# Skill synonyms
SKILL_SYNONYMS = {
    "sewing": [
        "sewing", "stitching", "machine stitching", "silai", "kuttu",
        "కుట్టు", "కుట్టుపని", "सिलाई", "कपडे सिलना"
    ],
    "embroidery": [
        "embroidery", "hand embroiderer", "kadhai", "aari work", "needle work",
        "ఎంబ్రాయిడరీ", "కసీదా", "कढ़ाई", "कसीदाकारी"
    ],
    "garment_cutting": [
        "cutting", "garment cutting", "pattern cutting",
        "కటింగ్", "कटिंग"
    ],
    "cooking": [
        "cooking", "cook", "culinary", "vanta", "food preparation",
        "వంట", "వంటపని", "खाना बनाना", "रसोई"
    ],
    "food_service": [
        "food service", "serving", "steward", "catering service", "table service",
        "సర్వింగ్", "भोजन सेवा"
    ],
    "wiring": [
        "wiring", "house wiring", "electrical wiring",
        "వైరింగ్", "वायरिंग"
    ],
    "appliance_repair": [
        "appliance repair", "field technician", "maintenance", "repair",
        "రిపేర్", "रिपेयर"
    ],
    "solar_installation": [
        "solar installation", "pv installation", "solar mounting",
        "సోలార్ ఫిట్టింగ్", "सोलर फिटिंग"
    ],
    "milking": [
        "milking", "milk extraction",
        "పాలు పితకడం", "दूध निकालना"
    ],
    "cattle_care": [
        "cattle rearing", "cattle care", "animal care",
        "పశు సంరక్షణ", "पशु देखभाल"
    ],
    "facial": [
        "facial", "skin care",
        "ఫేషియల్", "फेशियल"
    ],
    "bridal_makeup": [
        "bridal makeup", "makeup", "bridal grooming",
        "పెళ్లి మేకప్", "మేకప్", "ब्राइडल मेकअप"
    ],
    "cashier": [
        "cashier", "billing", "counter billing",
        "క్యాషియర్", "कैशियर", "बिलिंग"
    ],
    "customer_service": [
        "customer service", "sales counter", "customer interaction",
        "కస్టమర్ సర్వీస్", "ग्राहक सेवा"
    ]
}

# Education mappings
EDUCATION_SYNONYMS = {
    "none": [
        "none", "illiterate", "uneducated", "no schooling", "zero",
        "చదువుకోలేదు", "చదువు లేదు", "అనక్షరాస్యత", "अनपढ़", "बिना पढ़े", "निरक्षर"
    ],
    "primary": [
        "primary", "5th", "5th pass", "5th class", "4th", "3rd", "2nd", "1st",
        "ప్రాథమిక", "ఐదో తరగతి", "5వ తరగతి", "पांचवीं", "5वीं", "प्राथमिक"
    ],
    "8th": [
        "8th", "8th pass", "8th class", "middle school", "7th", "6th",
        "ఎనిమిదో తరగతి", "8వ తరగతి", "ఆరవ తరగతి",
        "आठवीं", "8वीं", "मिडिल"
    ],
    "10th": [
        "10th", "10th pass", "ssc", "matric", "metric", "high school", "tenth", "10",
        "పదో తరగతి", "10వ తరగతి", "టెన్త్", "ఎస్ఎస్సి",
        "दसवीं", "10वीं", "मैट्रिक", "हाई स्कूल"
    ],
    "12th": [
        "12th", "12th pass", "inter", "intermediate", "puc", "plus two", "+2", "12",
        "ఇంటర్మీడియట్", "ఇంటర్", "12వ తరగతి", "పన్నెండో తరగతి",
        "बारहवीं", "12वीं", "इंटर", "इंटरमीडिएट"
    ],
    "ITI": [
        "iti", "iti pass", "polytechnic", "diploma", "vocational",
        "ఐటీఐ", "డిప్లొమా", "आईटीआई", "पॉलिटेक्निक"
    ],
    "graduate": [
        "graduate", "degree", "graduation", "ba", "bsc", "bcom", "btech", "post graduate", "pg",
        "డిగ్రీ", "గ్రాడ్యుయేట్", "పట్టభద్రుడు",
        "ग्रेजुएशन", "स्नातक", "डिग्री", "बीए", "बीएससी", "बीकॉम"
    ]
}

# Work preference mappings
WORK_PREF_SYNONYMS = {
    "self": [
        "self", "own work", "self employment", "business", "own business", "freelance",
        "స్వంత పని", "స్వయం ఉపాధి", "సొంత పని", "సొంత వ్యాపారం", "వ్యాపారం",
        "खुद का काम", "स्वरोजगार", "अपना काम", "व्यापार", "बिजनेस", "स्वयं का काम"
    ],
    "wage": [
        "wage", "job", "salary", "wage employment", "employee", "company", "service",
        "ఉద్యోగం", "జీతం పని", "కొలువు", "కంపెనీ పని",
        "नौकरी", "जॉब", "मजदूरी", "रोजगार", "वेतन", "नौकर"
    ],
    "either": [
        "either", "both", "any", "either is fine", "any work", "flexible",
        "ఏదైనా", "ఏదైనా పర్లేదు", "ఏదైనా సరే", "రెండూ",
        "कोई भी", "दोनों", "कुछ भी चलेगा", "दोनों चलेगा"
    ]
}

# Mobility mappings
MOBILITY_SYNONYMS = {
    "home_only": [
        "home_only", "home only", "work from home", "cannot travel", "no travel", "at home", "stay at home",
        "ఇంటి వద్దే", "ఇంటి నుంచే", "ఇంట్లోనే", "ప్రయాణం చేయలేను", "బయటకు వెళ్లలేను",
        "घर से ही", "घर पर", "घर पर ही", "बाहर नहीं जा सकते", "यात्रा नहीं", "सफर नहीं"
    ],
    "within_village": [
        "within_village", "village only", "village", "same village", "in village",
        "ఊరిలోనే", "మా ఊరిలోనే", "సొంత ఊరు",
        "गांव में", "गाँव में", "अपने गांव में"
    ],
    "within_block": [
        "within_block", "local_block", "local", "nearby", "within block", "block", "mandal",
        "స్థానికంగా", "మండలంలోనే", "మండలంలో", "దగ్గర్లోనే", "బ్లాక్",
        "आसपास", "ब्लॉक में", "पास में", "लोकल", "प्रखंड"
    ],
    "anywhere": [
        "anywhere", "district", "state", "within district", "any block", "can travel anywhere",
        "జిల్లా", "జిల్లా పరిధిలో", "జిల్లాలో ఎక్కడైనా", "రాష్ట్రం", "ఎక్కడైనా", "ఎక్కడికైనా వెళ్తా",
        "जिले में", "पूरे जिले में", "जिला", "कहीं भी", "राज्य में", "बाहर भी जा सकते हैं"
    ]
}

# Asset mappings
ASSET_SYNONYMS = {
    "sewing machine": [
        "sewing machine", "silai machine", "tailoring machine",
        "కుట్టు మిషన్", "కుట్టుమిషన్", "మిషన్",
        "सिलाई मशीन", "मशीन"
    ],
    "vehicle": [
        "vehicle", "bike", "motorcycle", "scooter", "two wheeler",
        "బండి", "మోటార్ సైకిల్", "స్కూటర్", "వాహనం",
        "गाड़ी", "बाइक", "मोटरसाइकिल", "स्कूटर", "वाहन"
    ],
    "smartphone": [
        "smartphone", "mobile", "phone", "android",
        "స్మార్ట్‌ఫోన్", "మొబైల్", "ఫోన్",
        "स्मार्टफोन", "मोबाइल", "फ़ोन"
    ]
}

def clean_input(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s\u0C00-\u0C7F\u0900-\u097F\+]", " ", text.lower())
    return " ".join(cleaned.split())

def _matches_pattern(pattern: str, text: str) -> bool:
    pat_clean = clean_input(pattern)
    if not pat_clean or not text:
        return False
    if pat_clean == text:
        return True
    return bool(re.search(rf"(?:^|\s){re.escape(pat_clean)}(?:\s|$)", text))

def normalize_trade(term: str) -> Optional[str]:
    """Map any input term to canonical trade name if recognized."""
    if not term:
        return None
    cleaned = clean_input(term)
    if not cleaned:
        return None
    # Check exact trade names first
    for trade in TRADE_SYNONYMS:
        if trade == cleaned:
            return trade
    # Check synonyms with word boundary
    for trade, syns in TRADE_SYNONYMS.items():
        for syn in syns:
            if _matches_pattern(syn, cleaned):
                return trade
    return None

def normalize_skill(term: str) -> Optional[str]:
    """Map any input term to canonical skill tag."""
    if not term:
        return None
    cleaned = clean_input(term)
    if not cleaned:
        return None
    for skill, syns in SKILL_SYNONYMS.items():
        if skill == cleaned:
            return skill
        for syn in syns:
            if _matches_pattern(syn, cleaned):
                return skill
    # If not in skills, check if it maps to a trade's primary skill
    trade_match = normalize_trade(term)
    if trade_match:
        default_skills = {
            "tailoring": "sewing",
            "catering": "cooking",
            "electrician": "wiring",
            "solar_technician": "solar_installation",
            "dairy_farming": "cattle_care",
            "beauty_wellness": "facial",
            "retail_sales": "customer_service"
        }
        return default_skills.get(trade_match)
    return None

def normalize_education(term: Optional[str]) -> str:
    """Map input education text to canonical level: none, primary, 8th, 10th, 12th, ITI, graduate."""
    if not term:
        return "none"
    cleaned = clean_input(term)
    if not cleaned:
        return "none"
    # Exact canonical keys check first
    canonical_order = ["graduate", "ITI", "12th", "10th", "8th", "primary", "none"]
    for edu in canonical_order:
        if cleaned == edu.lower():
            return edu
    # Check synonyms in specific order to avoid substring overlaps
    for edu in canonical_order:
        syns = EDUCATION_SYNONYMS.get(edu, [])
        for syn in syns:
            if _matches_pattern(syn, cleaned):
                return edu
    return "none"

def normalize_work_preference(term: Optional[str]) -> Optional[str]:
    """Map input work preference to self, wage, or either."""
    if not term:
        return None
    cleaned = clean_input(term)
    if not cleaned:
        return None
    for pref in ["either", "wage", "self"]:
        if pref == cleaned:
            return pref
        for syn in WORK_PREF_SYNONYMS.get(pref, []):
            if _matches_pattern(syn, cleaned):
                return pref
    return None

def normalize_mobility(term: Optional[str]) -> Optional[str]:
    """Map input mobility string to home_only, local_block, district, or state."""
    if not term:
        return None
    cleaned = clean_input(term)
    if not cleaned:
        return None
    for mob in ["home_only", "within_village", "within_block", "anywhere"]:
        if mob == cleaned:
            return mob
        for syn in MOBILITY_SYNONYMS.get(mob, []):
            if _matches_pattern(syn, cleaned):
                return mob
    return None

def normalize_asset(term: str) -> Optional[str]:
    """Map input asset text to canonical asset name."""
    if not term:
        return None
    cleaned = clean_input(term)
    if not cleaned:
        return None
    for asset, syns in ASSET_SYNONYMS.items():
        if asset == cleaned:
            return asset
        for syn in syns:
            if _matches_pattern(syn, cleaned):
                return asset
    return cleaned

def normalize_term(term: str) -> Optional[str]:
    """General mapper: checks trade, then skill, then asset, else returns cleaned string."""
    if not term:
        return None
    trade = normalize_trade(term)
    if trade:
        return trade
    skill = normalize_skill(term)
    if skill:
        return skill
    asset = normalize_asset(term)
    if asset:
        return asset
    return term.strip().lower()
