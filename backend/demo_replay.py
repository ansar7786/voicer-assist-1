"""
Cached demo replay scripts for SIH26097 Live Voice Prototype (Phase 7, FR-68).
Provides pre-recorded deterministic turn-by-turn conversational flow for Persona A and Persona B.
Allows fully offline / cached demonstration without live API connection.
"""
from typing import Dict, Any
from backend.schema import ProfileSchema
from backend.engine import compute_pathways


def get_demo_replay(persona_id: str) -> Dict[str, Any]:
    norm_id = persona_id.strip().lower()
    if norm_id in ("persona_a", "a", "persona-a"):
        return _build_persona_a_replay()
    elif norm_id in ("persona_b", "b", "persona-b"):
        return _build_persona_b_replay()
    else:
        raise ValueError(f"Unknown persona: '{persona_id}'. Valid options: 'persona_a', 'persona_b'")


def _build_persona_a_replay() -> Dict[str, Any]:
    # Profile A: 10th pass, sewing machine, home_only, wants own work, max 3 months
    profile_data = {
        "education_level": "10th",
        "skills": ["tailoring", "embroidery"],
        "assets": ["sewing machine"],
        "interests": ["tailoring"],
        "mobility": "home_only",
        "max_training_months": 3,
        "work_preference": "self",
        "location_block": "Anandapuram",
    }
    pathways_res = compute_pathways(ProfileSchema(**profile_data))

    return {
        "persona_id": "persona_a",
        "title": "Persona A: Lakshmi (Tailoring / Self-Employment)",
        "language": "te",
        "description": "10th pass, knows stitching & embroidery, owns sewing machine, home-based self-employment, max 3 months duration.",
        "turns": [
            {
                "turn_index": 1,
                "user_text": "నమస్తే అండి, నేను 10వ తరగతి చదువుకున్నాను. నాకు కుట్టుపని మరియు ఎంబ్రాయిడరీ పని వచ్చు.",
                "user_translation": "Hello, I studied up to 10th class. I know tailoring and embroidery work.",
                "assistant_text": "నమస్కారం అండి! మీరు 10వ తరగతి చదివారు మరియు మీకు కుట్టుపని, ఎంబ్రాయిడరీ వచ్చు అని నమోదు చేశాను. మీకు ఎలాంటి పని చేయడానికి ఆసక్తి ఉంది?",
                "assistant_translation": "Hello! I noted that you completed 10th and know tailoring & embroidery. What kind of work are you interested in?",
                "tool_call": {
                    "name": "update_profile",
                    "args": {
                        "education_level": "10th",
                        "skills": ["tailoring", "embroidery"],
                        "interests": ["tailoring"],
                    },
                },
                "profile_snapshot": {
                    "education_level": "10th",
                    "skills": ["tailoring", "embroidery"],
                    "interests": ["tailoring"],
                },
                "confidence_snapshot": {
                    "education_level": "stated",
                    "skills": "stated",
                    "interests": "stated",
                },
                "confirmed": False,
                "pathways": [],
            },
            {
                "turn_index": 2,
                "user_text": "నా దగ్గర ఇంట్లోనే కుట్టుమిషన్ ఉంది. ప్రయాణం చేయలేను, ఇంట్లోనే ఉంటూ స్వయం ఉపాధి పొందాలి. 3 నెలల కంటే ఎక్కువ శిక్షణ తీసుకోలేను.",
                "user_translation": "I have a sewing machine at home. Cannot travel, want home-based self employment, max 3 months training.",
                "assistant_text": "అర్థమైంది అండి. మీ వద్ద కుట్టుమిషన్ ఉంది, ప్రయాణం చేయలేరు (హోమ్-ఓన్లీ), స్వయం ఉపాధి కోరుకుంటున్నారు మరియు గరిష్టంగా 3 నెలలు కేటాయించగలరు. ఈ వివరాలన్నీ సరిగ్గానే ఉన్నాయా?",
                "assistant_translation": "Understood. You own a sewing machine, cannot travel (home only), prefer self-employment, and maximum 3 months. Are these details correct?",
                "tool_call": {
                    "name": "update_profile",
                    "args": {
                        "assets": ["sewing machine"],
                        "mobility": "home_only",
                        "work_preference": "self",
                        "max_training_months": 3,
                    },
                },
                "profile_snapshot": {
                    "education_level": "10th",
                    "skills": ["tailoring", "embroidery"],
                    "interests": ["tailoring"],
                    "assets": ["sewing machine"],
                    "mobility": "home_only",
                    "work_preference": "self",
                    "max_training_months": 3,
                },
                "confidence_snapshot": {
                    "education_level": "stated",
                    "skills": "stated",
                    "interests": "stated",
                    "assets": "stated",
                    "mobility": "stated",
                    "work_preference": "stated",
                    "max_training_months": "stated",
                },
                "confirmed": False,
                "pathways": [],
            },
            {
                "turn_index": 3,
                "user_text": "అవును, అన్నీ సరిగ్గా ఉన్నాయి.",
                "user_translation": "Yes, everything is correct.",
                "assistant_text": "ధన్యవాదాలు! మీ ప్రొఫైల్ వివరాలను ధృవీకరించాను. మీ ప్రాధాన్యతలకు సరిపోయే 2 అనుకూలమైన జీవనోపాధి మార్గాలను కనుగొన్నాను. సెల్ఫ్ ఎంప్లాయ్డ్ టైలర్ మరియు హ్యాండ్ ఎంబ్రాయిడరర్ శిక్షణలు మీకు అత్యంత అనుకూలమైనవి.",
                "assistant_translation": "Thank you! I confirmed your profile. I found 2 feasible livelihood pathways matching your preferences: Self Employed Tailor and Hand Embroiderer.",
                "tool_call": {
                    "name": "confirm_profile",
                    "args": {
                        "summary": "10th pass, tailoring skills, sewing machine, home only, self employment, max 3 months",
                    },
                },
                "profile_snapshot": profile_data,
                "confidence_snapshot": {k: "stated" for k in profile_data},
                "confirmed": True,
                "pathways": [p.model_dump() for p in pathways_res.pathways],
                "excluded": [e.model_dump() for e in pathways_res.excluded],
            },
        ],
    }


def _build_persona_b_replay() -> Dict[str, Any]:
    # Profile B: catering experience, wage work, urgent income, local block travel
    profile_data = {
        "education_level": "8th",
        "skills": ["catering", "cooking"],
        "interests": ["catering"],
        "mobility": "local_block",
        "max_training_months": 4,
        "work_preference": "wage",
        "urgency_of_income": "urgent",
        "location_block": "Bheemunipatnam",
    }
    pathways_res = compute_pathways(ProfileSchema(**profile_data))

    return {
        "persona_id": "persona_b",
        "title": "Persona B: Ramesh (Hospitality / Wage Employment)",
        "language": "hi",
        "description": "8th pass, local cooking & catering experience, seeks wage employment, urgent income, can travel within block.",
        "turns": [
            {
                "turn_index": 1,
                "user_text": "नमस्ते, मैंने 8वीं कक्षा तक पढ़ाई की है। मुझे शादी-समारोहों में खाना बनाने और कैटरिंग का अनुभव है।",
                "user_translation": "Hello, I studied till 8th grade. I have experience in cooking and catering at local events.",
                "assistant_text": "नमस्ते रमेश जी! आपने 8वीं तक पढ़ाई की है और आपको कैटरिंग और कुकिंग का अनुभव है। मैंने इसे आपकी प्रोफाइल में जोड़ दिया है। आप किस तरह का रोजगार तलाश रहे हैं?",
                "assistant_translation": "Hello Ramesh ji! I noted that you completed 8th and have catering & cooking experience. What kind of employment are you seeking?",
                "tool_call": {
                    "name": "update_profile",
                    "args": {
                        "education_level": "8th",
                        "skills": ["catering", "cooking"],
                        "interests": ["catering"],
                    },
                },
                "profile_snapshot": {
                    "education_level": "8th",
                    "skills": ["catering", "cooking"],
                    "interests": ["catering"],
                },
                "confidence_snapshot": {
                    "education_level": "stated",
                    "skills": "stated",
                    "interests": "stated",
                },
                "confirmed": False,
                "pathways": [],
            },
            {
                "turn_index": 2,
                "user_text": "मुझे नियमित वेतन (सैलरी) वाली नौकरी चाहिए, तुरंत आय की आवश्यकता है, और मैं अपने ब्लॉक के भीतर यात्रा कर सकता हूँ।",
                "user_translation": "I need a regular salaried wage job, urgent income needed, and I can travel within my block.",
                "assistant_text": "बहुत अच्छा! आप वेतन आधारित नौकरी चाहते हैं, स्थानीय ब्लॉक में यात्रा कर सकते हैं और आपको तुरंत आय की आवश्यकता है। क्या ये सभी विवरण सही हैं?",
                "assistant_translation": "Great! You prefer wage employment, can travel locally within the block, and need urgent income. Are all these details correct?",
                "tool_call": {
                    "name": "update_profile",
                    "args": {
                        "work_preference": "wage",
                        "mobility": "local_block",
                        "urgency_of_income": "urgent",
                        "max_training_months": 4,
                    },
                },
                "profile_snapshot": {
                    "education_level": "8th",
                    "skills": ["catering", "cooking"],
                    "interests": ["catering"],
                    "work_preference": "wage",
                    "mobility": "local_block",
                    "urgency_of_income": "urgent",
                    "max_training_months": 4,
                },
                "confidence_snapshot": {
                    "education_level": "stated",
                    "skills": "stated",
                    "interests": "stated",
                    "work_preference": "stated",
                    "mobility": "stated",
                    "urgency_of_income": "stated",
                    "max_training_months": "stated",
                },
                "confirmed": False,
                "pathways": [],
            },
            {
                "turn_index": 3,
                "user_text": "हाँ, बिल्कुल सही है।",
                "user_translation": "Yes, absolutely correct.",
                "assistant_text": "धन्यवाद! आपकी प्रोफाइल कन्फर्म कर दी गई है। आपके लिए असिस्टेंट कुक और फूड सर्विस स्टीवर्ड के पाठ्यक्रम उपलब्ध हैं, जिनमें तुरंत प्लेसमेंट के अवसर भी शामिल हैं।",
                "assistant_translation": "Thank you! Profile confirmed. Assistant Cook and Food Service Steward courses are matched for you, offering wage employment opportunities.",
                "tool_call": {
                    "name": "confirm_profile",
                    "args": {
                        "summary": "8th pass, catering experience, wage employment, urgent income, local block mobility",
                    },
                },
                "profile_snapshot": profile_data,
                "confidence_snapshot": {k: "stated" for k in profile_data},
                "confirmed": True,
                "pathways": [p.model_dump() for p in pathways_res.pathways],
                "excluded": [e.model_dump() for e in pathways_res.excluded],
            },
        ],
    }
