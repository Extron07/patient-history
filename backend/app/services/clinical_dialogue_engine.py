import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from backend.app.schemas.intake import QuestionResponse

logger = logging.getLogger("clinical_dialogue_engine")

# The exact clinical history taking flow
STAGE_ORDER = [
    "symptoms",
    "pre_existing_conditions",
    "current_medicines",
    "allergies",
    "family_history",
    "lifestyle"
]

STAGE_TITLES = {
    "symptoms": {
        "en": "Current Symptoms & Concerns",
        "hi": "वर्तमान लक्षण और तकलीफ",
        "mr": "सध्याची लक्षणे आणि त्रास"
    },
    "pre_existing_conditions": {
        "en": "Medical Background & Chronic Conditions",
        "hi": "पूर्व-मौजूदा स्वास्थ्य स्थितियां",
        "mr": "मागील आजार किंवा आरोग्याच्या समस्या"
    },
    "current_medicines": {
        "en": "Active Medications & Prescriptions",
        "hi": "वर्तमान दवाइयां",
        "mr": "सध्याची औषधे"
    },
    "allergies": {
        "en": "Allergies & Drug Reactions",
        "hi": "एलर्जी और रिएक्शन",
        "mr": "अ‍ॅलर्जी आणि रिएक्शन"
    },
    "family_history": {
        "en": "Family Health History",
        "hi": "पारिवारिक इतिहास",
        "mr": "कौटुंबिक इतिहास"
    },
    "lifestyle": {
        "en": "General Lifestyle & Digestion",
        "hi": "सामान्य जीवनशैली और दिनचर्या",
        "mr": "सामान्य जीवनशैली आणि सवयी"
    }
}

def has_positive_condition(text: str, keywords: List[str]) -> bool:
    """
    Evaluates whether the patient affirmatively confirmed a condition/keyword.
    Prevents asking follow-up questions when a patient denied an illness (e.g. 'No diabetes' or 'None').
    """
    if not text:
        return False
    lower = text.lower()
    
    # Explicit general negations
    general_negations = [
        'none', 'no illness', 'no disease', 'no chronic', 'healthy', 'nothing',
        'nil', 'deny', 'denies', 'koi nahi', 'kahi nahi', 'nahi hai', 'no problem',
        'कोई नहीं', 'काही नाही', 'नाही', 'नहीं', 'काही आजार नाही', 'no regular',
        'no medicines', 'no medicine', 'no allergy', 'no allergies', 'fit'
    ]
    if any(gn in lower for gn in general_negations) and not any(pos in lower for pos in ['except', 'but', 'परंतु', 'लेकिन', 'फक्त']):
        return False

    for kw in keywords:
        if kw in lower:
            # Check localized negation right before or after the keyword
            neg_before = re.search(rf'\b(no|not|neither|nor|without|deny|denies|never|zero)\s+(?:have\s+|had\s+|known\s+|history of\s+)?{re.escape(kw)}\b', lower)
            neg_after = re.search(rf'\b{re.escape(kw)}\s+(?:nahi|nahin|nako|illadhu|illa|नहीं|नाही)\b', lower)
            neg_sentence = re.search(rf'\b(don\'t|dont|do not)\s+have\s+{re.escape(kw)}\b', lower)
            
            if not neg_before and not neg_after and not neg_sentence:
                return True
    return False


CHRONIC_CONDITIONS_CATALOG = [
    {
        "id": "diabetes",
        "keywords": ["diabetes", "sugar", "diabetic", "madhumeh", "मधुमेह", "शुगर"],
        "standard_name": "Type 2 Diabetes Mellitus",
        "labels": {"en": "diabetes", "hi": "शुगर (डायबिटीज)", "mr": "मधुमेह"},
        "follow_up": {
            "en": "Understood. Regarding your diabetes, what specific symptoms or concerns bring you to the clinic today—such as weakness, dizziness, pain, or is this for a routine checkup?",
            "hi": "समझ गया। अपनी शुगर (डायबिटीज) को लेकर आज आपको क्या मुख्य तकलीफ या समस्या हो रही है—जैसे कमजोरी, चक्कर, या यह रूटीन जांच के लिए है?",
            "mr": "समजले. तुमच्या मधुमेहाबद्दल, आज तुम्हाला काय मुख्य त्रास किंवा लक्षणे जाणवत आहेत—जसे अशक्तपणा, चक्कर, की ही नियमित तपासणी आहे?"
        }
    },
    {
        "id": "hypertension",
        "keywords": ["bp", "blood pressure", "hypertension", "high pressure", "high bp", "रक्तचाप", "बीपी", "उच्च रक्तदाब"],
        "standard_name": "Hypertension (High BP)",
        "labels": {"en": "blood pressure", "hi": "बीपी (रक्तचाप)", "mr": "उच्च रक्तदाब (बीपी)"},
        "follow_up": {
            "en": "Understood. Regarding your blood pressure, what specific symptoms or concerns bring you to the clinic today—such as headache, dizziness, breathlessness, or is this for a routine checkup?",
            "hi": "समझ गया। अपने बीपी (रक्तचाप) को लेकर आज आपको क्या मुख्य तकलीफ महसूस हो रही है—जैसे सिरदर्द, चक्कर, सांस फूलना, या यह रूटीन चेकअप के लिए है?",
            "mr": "समजले. तुमच्या रक्तदाबाबद्दल (बीपी), आज तुम्हाला काय मुख्य त्रास जाणवत आहे—जसे डोकेदुखी, चक्कर, धाप लागणे, की ही नियमित तपासणी आहे?"
        }
    },
    {
        "id": "thyroid",
        "keywords": ["thyroid", "hypothyroid", "hyperthyroid", "थायराइड", "थायरॉईड"],
        "standard_name": "Hypothyroidism / Thyroid Disorder",
        "labels": {"en": "thyroid", "hi": "थायराइड", "mr": "थायरॉईड"},
        "follow_up": {
            "en": "Understood. Regarding your thyroid, what specific symptoms or troubles bring you to the clinic today—such as fatigue, weight changes, neck swelling, or is this for a routine checkup?",
            "hi": "समझ गया। अपने थायराइड को लेकर आज आपको क्या तकलीफ महसूस हो रही है—जैसे थकान, वजन में बदलाव, गले में सूजन, या यह रूटीन जांच के लिए है?",
            "mr": "समजले. तुमच्या थायरॉईडबद्दल, आज तुम्हाला काय त्रास जाणवत आहे—जसे थकवा, वजनातील बदल, की ही नियमित तपासणी आहे?"
        }
    },
    {
        "id": "asthma",
        "keywords": ["asthma", "dama", "wheezing", "दमा"],
        "standard_name": "Bronchial Asthma",
        "labels": {"en": "asthma", "hi": "दमा", "mr": "दमा"},
        "follow_up": {
            "en": "Understood. Regarding your asthma, are you currently having acute breathlessness, coughing, or chest tightness, or did you come for an inhaler review?",
            "hi": "समझ गया। अपने दमे को लेकर क्या अभी आपको सांस फूलने, खांसी या छाती में जकड़न की तकलीफ हो रही है, या आप दवा/इनहेलर दिखाने आए हैं?",
            "mr": "समजले. तुमच्या दम्याबद्दल, सध्या तुम्हाला धाप लागणे, खोकला किंवा छातीत जडपणा जाणवत आहे का?"
        }
    },
    {
        "id": "arthritis",
        "keywords": ["arthritis", "gout", "sandhivata", "joint problem", "संधिवात", "गठिया"],
        "standard_name": "Joint Arthritis",
        "labels": {"en": "arthritis or joint trouble", "hi": "गठिया / जोड़ों की समस्या", "mr": "संधिवात"},
        "follow_up": {
            "en": "Understood. Regarding your joint condition, which specific joints are currently troubling you, and is there swelling or morning stiffness?",
            "hi": "समझ गया। जोड़ों की समस्या को लेकर अभी आपको किस जोड़ में सबसे ज्यादा दर्द हो रहा है, और क्या वहां सूजन या अकड़न भी है?",
            "mr": "समजले. सांधेदुखीबद्दल, सध्या तुम्हाला कोणत्या सांध्यामध्ये जास्त त्रास होत आहे आणि तिथे सूज किंवा ताठरता आहे का?"
        }
    },
    {
        "id": "migraine",
        "keywords": ["migraine", "माइग्रेन", "मायग्रेन"],
        "standard_name": "Migraine",
        "labels": {"en": "migraine", "hi": "माइग्रेन", "mr": "मायग्रेन"},
        "follow_up": {
            "en": "Understood. Regarding your migraine, are you currently having a severe headache episode, nausea, or sensitivity to light?",
            "hi": "समझ गया। माइग्रेन को लेकर क्या अभी आपको तेज सिरदर्द, उल्टी का मन या रोशनी से परेशानी हो रही है?",
            "mr": "समजले. मायग्रेनबद्दल, सध्या तुम्हाला तीव्र डोकेदुखी, मळमळ किंवा प्रकाशाचा त्रास होत आहे का?"
        }
    },
    {
        "id": "acidity",
        "keywords": ["acidity", "gerd", "gastric", "acid reflux", "gastritis", "एसिडिटी", "गैस", "पित्त"],
        "standard_name": "Acidity / Gastritis",
        "labels": {"en": "acidity or gastric trouble", "hi": "एसिडिटी और गैस", "mr": "पित्त आणि अ‍ॅसिडिटी"},
        "follow_up": {
            "en": "Understood. Regarding your acidity or gastric trouble, are you experiencing burning in the chest, sour burps, or stomach pain?",
            "hi": "समझ गया। एसिडिटी को लेकर क्या आपको सीने में जलन, खट्टी डकारें या पेट में दर्द महसूस हो रहा है?",
            "mr": "समजले. पित्त किंवा अ‍ॅसिडिटीबद्दल, छातीत जळजळ, आंबट ढेकर किंवा पोटात दुखत आहे का?"
        }
    }
]

ACUTE_ILLNESS_CATALOG = [
    {
        "id": "dengue",
        "keywords": ["dengue", "डेंगू", "डेंग्यू"],
        "labels": {"en": "Dengue", "hi": "डेंगू", "mr": "डेंग्यू"}
    },
    {
        "id": "typhoid",
        "keywords": ["typhoid", "टाइफाइड", "टायफॉईड"],
        "labels": {"en": "Typhoid", "hi": "टाइफाइड", "mr": "टायफॉईड"}
    },
    {
        "id": "malaria",
        "keywords": ["malaria", "मलेरिया", "हिवताप"],
        "labels": {"en": "Malaria", "hi": "मलेरिया", "mr": "हिवताप"}
    },
    {
        "id": "jaundice",
        "keywords": ["jaundice", "hepatitis", "पीलिया", "कावीळ"],
        "labels": {"en": "Jaundice", "hi": "पीलिया (Jaundice)", "mr": "कावीळ"}
    },
    {
        "id": "pneumonia",
        "keywords": ["pneumonia", "निमोनिया"],
        "labels": {"en": "Pneumonia", "hi": "निमोनिया", "mr": "निमोनिया"}
    },
    {
        "id": "viral_fever",
        "keywords": ["viral fever", "viral", "flu", "वायरल बुखार", "वायरल"],
        "labels": {"en": "Viral fever", "hi": "वायरल बुखार", "mr": "व्हायरल ताप"}
    },
    {
        "id": "food_poisoning",
        "keywords": ["food poisoning", "loose motions", "diarrhea", "दस्त", "जुलाब", "उल्टी दस्त"],
        "labels": {"en": "Food poisoning / Diarrhea", "hi": "दस्त व पेट का इन्फेक्शन", "mr": "जुलाब आणि इन्फेक्शन"}
    },
    {
        "id": "uti",
        "keywords": ["uti", "urine infection", "urinary infection", "पेशाब में इन्फेक्शन", "लघवीला जळजळ"],
        "labels": {"en": "Urinary tract infection", "hi": "पेशाब में इन्फेक्शन", "mr": "मूत्रमार्गाचा संसर्ग"}
    }
]

EXPLICIT_SYMPTOM_REGEX = re.compile(
    r'\b(headache|stomach pain|chest pain|joint pain|knee pain|back pain|abdominal pain|throat pain|body ache|body pain|'
    r'fever|cough|cold|vomiting|nausea|dizziness|rash|itching|breathlessness|swelling|weakness|fatigue|loose motion|loose motions|diarrhea|'
    r'burning|pain|ache|stiffness|cramps|'
    r'बुखार|खांसी|जुकाम|सिरदर्द|पेट दर्द|घुटनों में दर्द|जोड़ों का दर्द|बदन दर्द|उल्टी|चक्कर|कमजोरी|दाने|खुजली|सांस फूलना|सूजन|थकान|दस्त|जलन|दर्द|'
    r'ताप|खोकला|सर्दी|डोकेदुखी|पोटदुखी|गुडघेदुखी|सांधेदुखी|अंगदुखी|मळमळ|उलटी|चक्कर|अशक्तपणा|खाज|सूज|थकवा|जुलाब|जळजळ|वेदना)\b',
    re.IGNORECASE
)

PAIN_KEYWORDS = [
    "headache", "stomach pain", "chest pain", "back pain", "joint pain", "knee pain", 
    "throat pain", "body ache", "body pain", "abdominal pain", "neck pain", "pain", "ache",
    "सिरदर्द", "पेट दर्द", "छाती में दर्द", "घुटनों में दर्द", "जोड़ों का दर्द", "बदन दर्द", "कमर दर्द", "दर्द",
    "डोकेदुखी", "पोटदुखी", "छातीत दुखणे", "गुडघेदुखी", "सांधेदुखी", "अंगदुखी", "पाठीचे दुखणे", "वेदना"
]

VAGUE_DURATION_REGEX = re.compile(
    r'\b(thode din|thoda din|kuch din|kuch dino|some days|a few days|few days|recently|a while|kaahi divas|kahi divsapasun|kai divas|thoda time|kuch samay|kuch der|thode divas|kahi divas)\b',
    re.IGNORECASE
)

VAGUE_MEDICINE_REGEX = re.compile(
    r'\b(white tablet|small pill|small tablet|one tablet|one pill|some pills?|some medicines?|'
    r'ek goli|safed goli|choti goli|goli leta|dawa leta|dawa khata|bp tablet|bp ki goli|sugar pill|sugar ki goli|'
    r'ek tablet|kuch dawa|roz ek goli|fakt ek goli|ek goli gheto|roz goli gheto)\b',
    re.IGNORECASE
)

def is_pain_complaint(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(pk in lower for pk in PAIN_KEYWORDS)

def get_pain_socrates_prompt(chief: str) -> Dict[str, str]:
    lower = chief.lower()
    if any(k in lower for k in ["chest", "छाती"]):
        return {
            "en": "Does the chest pain feel like heavy squeezing pressure, burning, or sharp, and does it spread to your left arm, neck, or back?",
            "hi": "क्या छाती का दर्द भारी दबाव, जलन या तेज चुभन जैसा लगता है, और क्या यह आपके बाएं हाथ, गले या पीठ की तरफ फैलता है?",
            "mr": "छातीतील दुखणे जडपणा, जळजळ किंवा दाबासारखे वाटते का आणि ते डाव्या हाताकडे, मानेकडे किंवा पाठीकडे पसरते का?"
        }
    elif any(k in lower for k in ["headache", "migraine", "सिरदर्द", "डोकेदुखी", "मायग्रेन", "माइग्रेन"]):
        return {
            "en": "Does your headache feel throbbing like a heartbeat, heavy, or sharp, and does it spread down to your neck or behind your eyes?",
            "hi": "क्या सिरदर्द धड़कन की तरह (नस फड़कना), भारीपन या तेज चुभन जैसा है, और क्या यह गर्दन या आंखों की तरफ जाता है?",
            "mr": "डोकेदुखी धडधडल्यासारखी, जड किंवा तीव्र आहे का आणि ती मानेकडे किंवा डोळ्यांच्या मागे पसरते का?"
        }
    elif any(k in lower for k in ["stomach", "abdominal", "पेट", "पोट"]):
        return {
            "en": "Does the stomach pain feel burning, cramping in waves, or a dull ache, and does it spread to your back?",
            "hi": "क्या पेट में जलन, मरोड़ या तेज चुभन महसूस होती है, और क्या यह दर्द पीठ की ओर भी जाता है?",
            "mr": "पोटात जळजळ, मुरडा किंवा तीव्र दुखणे जाणवते का आणि ते पाठीकडे पसरते का?"
        }
    elif any(k in lower for k in ["back", "spine", "कमर", "पाठी"]):
        return {
            "en": "Does the back pain feel like a deep dull ache or sharp stiffness, and does it shoot down into your hips or legs?",
            "hi": "क्या कमर दर्द में भारी अकड़न या तेज दर्द है, और क्या यह नीचे कूल्हों या पैरों की तरफ खिंचता है?",
            "mr": "पाठीत जडपणा किंवा तीव्र वेदना आहेत का आणि त्या खाली मांड्या किंवा पायांकडे उतरतात का?"
        }
    elif any(k in lower for k in ["joint", "knee", "घुटनों", "जोड़ों", "गुडघे", "सांधे"]):
        return {
            "en": "Does the joint pain feel stiff, throbbing, or sharp, and does it spread to neighboring joints or cause difficulty bending?",
            "hi": "क्या जोड़ों में तेज दर्द, अकड़न या चुभन महसूस होती है, और क्या पैर मोड़ने या चलने में परेशानी होती है?",
            "mr": "सांध्यामध्ये तीव्र वेदना, ताठरता किंवा टोचल्यासारखे वाटते का आणि पाय दुमडताना त्रास होतो का?"
        }
    else:
        return {
            "en": "How does the pain feel—is it a dull ache, sharp, throbbing, or burning, and does it spread anywhere else?",
            "hi": "यह दर्द कैसा महसूस होता है—मीठा-मीठा दर्द, तेज चुभन, धड़कन जैसा या जलन, और क्या यह कहीं और फैलता है?",
            "mr": "हे दुखणे कसे वाटते—मंद, तीव्र, धडधडणारे की जळजळणारे, आणि ते इतरत्र कुठे पसरते का?"
        }

def get_complaint_rule_out_prompt(chief: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """
    Returns (rule_out_id, prompts_dict) for targeted clinical rule-outs.
    """
    lower = chief.lower()
    if any(k in lower for k in ["fever", "बुखार", "ताप", "dengue", "typhoid", "malaria"]):
        return "fever_rule_out", {
            "en": "With the fever, do you have severe shivering chills, any skin rash, or burning sensation while passing urine?",
            "hi": "बुखार के साथ क्या आपको तेज कंपकंपी (ठंड लगना), शरीर पर दाने या पेशाब में जलन की समस्या भी है?",
            "mr": "तापाबरोबर तुम्हाला तीव्र थंडी वाजणे, अंगावर पुरळ किंवा लघवीला जळजळ असा काही त्रास आहे का?"
        }
    elif any(k in lower for k in ["cough", "cold", "खांसी", "खोकला", "कफ"]):
        return "cough_rule_out", {
            "en": "Is your cough completely dry or producing phlegm, and have you noticed any blood or breathlessness with it?",
            "hi": "क्या खांसी सूखी है या बलगम वाली, और क्या इसमें कभी खून दिखा या सांस फूलने की समस्या हुई है?",
            "mr": "खोकला कोरडा आहे की कफ पडतो, आणि कफात कधी रक्ताचा अंश किंवा धाप लागणे जाणवले आहे का?"
        }
    elif any(k in lower for k in ["knee", "joint", "arthritis", "घुटनों", "जोड़ों", "गुडघे", "सांधे"]):
        return "joint_rule_out", {
            "en": "In the morning, do your joints stay stiff for more than half an hour, and is there visible swelling or warmth?",
            "hi": "सुबह उठने पर क्या जोड़ों में आधे घंटे से ज्यादा अकड़न रहती है, और क्या जोड़ों में सूजन या गर्माहट महसूस होती है?",
            "mr": "सकाळी उठल्यावर सांधे अर्ध्या तासापेक्षा जास्त ताठरतात का आणि सांध्यावर सूज किंवा उष्णता जाणवते का?"
        }
    elif any(k in lower for k in ["vomit", "nausea", "loose motion", "diarrhea", "उल्टी", "दस्त", "मळमळ", "जुलाब"]):
        return "gi_rule_out", {
            "en": "Are you able to keep water or fluids down, and have you noticed any blood or severe stomach cramping?",
            "hi": "क्या पानी पीने पर भी उल्टी हो रही है, और क्या पेट में तेज मरोड़ या मल में खून दिखा है?",
            "mr": "पाणी प्यायल्यावरही उलटी होते का आणि पोटात तीव्र मुरडा किंवा शौचात रक्त दिसले आहे का?"
        }
    elif any(k in lower for k in ["headache", "migraine", "सिरदर्द", "डोकेदुखी"]):
        return "headache_rule_out", {
            "en": "With this headache, do you experience nausea, visual blurriness or flashes, or stiffness in your neck?",
            "hi": "सिरदर्द के साथ क्या आपको उल्टी का मन, आंखों के आगे धुंधलापन या गर्दन में अकड़न महसूस होती है?",
            "mr": "डोकेदुखीसोबत मळमळ, डोळ्यांसमोर अंधारी किंवा मानेमध्ये ताठरता जाणवते का?"
        }
    return None

def get_empathy_bridge(answered_data: Dict[str, str], lang: str) -> str:
    """
    Returns an empathetic conversational bridge phrase based on what the patient shared.
    """
    sev = (answered_data.get("symptom_severity") or "").lower()
    chief = (answered_data.get("chief_complaint") or "").lower()

    if any(s in sev for s in ["severe", "very bad", "unbearable", "तेज़", "तेज", "तीव्र", "असह्य"]):
        bridges = {
            "en": "I'm sorry to hear you've been in so much pain. Let's make sure the doctor has all the details. ",
            "hi": "यह जानकर दुख हुआ कि आपको इतनी तेज तकलीफ हो रही है। आइए डॉक्टर साहब के लिए पूरी जानकारी नोट कर लेते हैं। ",
            "mr": "तुम्हाला इतका तीव्र त्रास होत आहे हे ऐकून वाईट वाटले. डॉक्टर साहेबांसाठी आपण हे व्यवस्थित नोंदवून घेऊया. "
        }
        return bridges.get(lang, bridges["en"])

    if any(f in chief for f in ["fever", "बुखार", "ताप"]) and any(b in chief for b in ["body", "pain", "बदन", "अंगदुखी"]):
        bridges = {
            "en": "Understood. Having fever with generalized body aches can be really exhausting. ",
            "hi": "जी समझ गया। बुखार और बदन दर्द काफी कमजोरी ला देता है। ",
            "mr": "समजले. ताप आणि अंगदुखीमुळे खूप थकवा जाणवतो. "
        }
        return bridges.get(lang, bridges["en"])

    return ""


class ClinicalDialogueEngine:
    """
    Intelligent dynamic patient history taking engine.
    Follows the clinical consultation flow (Symptoms -> Medical History -> Medications -> Allergies -> Family History -> Lifestyle).
    Dynamically generates contextual follow-up questions instead of rigid hardcoded questions,
    acknowledging what the patient previously shared and asking only for missing clinical dimensions.
    """

    def _detect_chronic_condition(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        for cond in CHRONIC_CONDITIONS_CATALOG:
            if has_positive_condition(text, cond["keywords"]):
                return cond
        return None

    def _detect_acute_illness(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        for acute in ACUTE_ILLNESS_CATALOG:
            if has_positive_condition(text, acute["keywords"]):
                return acute
        return None

    def _clean_symptom_phrase(self, chief: str, lang: str) -> str:
        """
        Cleans up the chief complaint string so it flows naturally in conversational prompts.
        Avoids awkward phrasing like 'Does anything make your I have been having fever feel better'.
        """
        if not chief:
            return "your symptoms" if lang == "en" else ("आपकी समस्या" if lang == "hi" else "तुमचा त्रास")
        
        c = chief.strip()
        words = c.split()
        lower = c.lower()

        # 1. Check if patient named an acute illness (Dengue, Typhoid, Malaria, etc.)
        acute = self._detect_acute_illness(c)
        if acute:
            return acute["labels"].get(lang, acute["labels"]["en"])

        # 2. Check if patient named a chronic condition (Diabetes, High BP, etc.)
        chronic = self._detect_chronic_condition(c)
        if chronic and not bool(EXPLICIT_SYMPTOM_REGEX.search(c)):
            return chronic["labels"].get(lang, chronic["labels"]["en"])

        preambles = ["i have", "i'm having", "im having", "i am having", "suffering from", "feeling", "mujhe", "mala", "मला", "मुझे"]
        has_preamble = any(lower.startswith(p) for p in preambles)
        
        if len(words) <= 3 and not has_preamble:
            return c
        
        # 3. Extract common core symptom keywords if present across English, Hindi, and Marathi
        symptom_match = EXPLICIT_SYMPTOM_REGEX.search(lower)
        if symptom_match:
            return symptom_match.group(0)
            
        if lang == "hi":
            return "आपकी समस्या"
        elif lang == "mr":
            return "तुमचा त्रास"
        else:
            return "your symptoms"

    def parse_and_extract_entities(
        self,
        raw_text: str,
        current_field: str,
        current_section: str,
        language: str = "en"
    ) -> List[Tuple[str, str, str]]:
        """
        Extracts clinical entities strictly from what the patient disclosed.
        Section scoping guarantees that answers in one section (e.g. lifestyle sleep hours or family history)
        never overwrite fields in other sections (e.g. symptom duration or personal chronic illness).
        """
        extracted = []
        text = raw_text.strip()
        lower = text.lower()

        # 1. Primary field assignment (strictly store patient's provided text)
        extracted.append((current_section, current_field, text))

        # 2. Extract symptom-level co-mentions ONLY when patient is discussing symptoms
        if current_section == "symptoms":
            # 2A. If patient mentioned a chronic disease during chief complaint, auto-populate pre_existing_conditions!
            chronic_match = self._detect_chronic_condition(text)
            if chronic_match:
                extracted.append(("pre_existing_conditions", "known_chronic_conditions", chronic_match["standard_name"]))
                diab_dur = re.search(r'(\b\d+\s*(?:years?|months?|साल|वर्षे|महिने)\b)', lower)
                if diab_dur and chronic_match["id"] == "diabetes":
                    extracted.append(("pre_existing_conditions", "diabetes_history", diab_dur.group(0).strip()))

            # 2B. Check if patient indicated a routine follow-up / checkup visit without acute symptoms
            is_routine = any(rw in lower for rw in [
                "routine", "checkup", "regular check", "sugar test", "bp check", "follow up", 
                "follow-up", "normal check", "medicine refill", "रूटीन", "चेकअप", "जांच", "तपासणी"
            ])
            has_sym = bool(EXPLICIT_SYMPTOM_REGEX.search(lower))
            if is_routine and not has_sym:
                if current_field != "symptom_duration":
                    extracted.append(("symptoms", "symptom_duration", "Routine follow-up / Checkup"))
                if current_field != "symptom_severity":
                    extracted.append(("symptoms", "symptom_severity", "None / Asymptomatic"))
                if current_field != "associated_symptoms":
                    extracted.append(("symptoms", "associated_symptoms", "Routine checkup and regular evaluation"))
                if current_field != "modulating_factors":
                    extracted.append(("symptoms", "modulating_factors", "Not applicable"))

            # 2C. Extract Duration if co-mentioned in chief complaint
            dur_match = re.search(
                r'(\b\d+\s*(?:days?|weeks?|months?|years?|hours?|दिन|हफ्ते|महीने|साल|घंटे|दिवस|आठवडे|महिने|वर्षे|तास|दिवसांपासून)\b|\bsince\s+[a-zA-Z0-9\s]+|\bfrom\s+\d+\s*(?:days?|weeks?|months?|hours?)\b)',
                lower
            )
            if dur_match and current_field != "symptom_duration":
                extracted.append(("symptoms", "symptom_duration", dur_match.group(0).strip()))

            # Check if duration is vague (e.g. "thode din se", "kuch dino se", "some days", "a few days")
            if current_field in ["chief_complaint", "symptom_duration"]:
                if VAGUE_DURATION_REGEX.search(lower) and not re.search(r'\b\d+\s*(?:days?|weeks?|months?|years?|hours?|दिन|हफ्ते|महीने|दिवस|आठवडे)\b', lower):
                    extracted.append(("symptoms", "symptom_duration_is_vague", "true"))

            if current_field == "symptom_duration_clarification":
                extracted.append(("symptoms", "symptom_duration", text))
                extracted.append(("symptoms", "symptom_duration_clarified", text))
                extracted.append(("symptoms", "symptom_duration_is_vague", "false"))

            if current_field == "pain_character_radiation":
                extracted.append(("symptoms", "pain_character_radiation", text))

            if current_field == "symptom_rule_out":
                extracted.append(("symptoms", "symptom_rule_out", text))
                extracted.append(("symptoms", "associated_symptoms", text))

            # 2D. Extract Severity if co-mentioned
            sev_match = re.search(
                r'\b(severe|mild|moderate|very bad|unbearable|tez|bahut tez|thoda|हल्का|हल्की|तेज़|तेज|मध्यम|तीव्र|जास्त|असह्य)\b',
                lower
            )
            if sev_match and current_field != "symptom_severity":
                s_val = sev_match.group(0).lower()
                if s_val in ["severe", "very bad", "unbearable", "tez", "bahut tez", "तेज़", "तेज", "तीव्र", "असह्य"]:
                    extracted.append(("symptoms", "symptom_severity", "Severe"))
                elif s_val in ["mild", "thoda", "हल्का", "हल्की"]:
                    extracted.append(("symptoms", "symptom_severity", "Mild"))
                elif s_val in ["moderate", "मध्यम"]:
                    extracted.append(("symptoms", "symptom_severity", "Moderate"))

            # 2E. Extract Associated Symptoms if co-mentioned
            assoc_keywords = [
                ("vomit", "Vomiting"),
                ("उल्टी", "उल्टी (Vomiting)"),
                ("मळमळ", "मळमळ (Nausea)"),
                ("nausea", "Nausea"),
                ("dizziness", "Dizziness"),
                ("चक्कर", "चक्कर (Dizziness)"),
                ("fever", "Fever"),
                ("बुखार", "बुखार (Fever)"),
                ("ताप", "ताप (Fever)"),
                ("cough", "Cough"),
                ("खांसी", "खांसी (Cough)"),
                ("खोकला", "खोकला (Cough)"),
                ("weakness", "Weakness"),
                ("कमजोरी", "कमजोरी (Weakness)"),
                ("थकवा", "थकवा (Weakness)")
            ]
            for kw, val in assoc_keywords:
                if kw in lower and current_field != "associated_symptoms":
                    extracted.append(("symptoms", "associated_symptoms", val))
                    break

        # 3. Extract Personal Chronic Diseases ONLY when patient affirmatively confirms pre_existing_conditions
        if current_section == "pre_existing_conditions":
            has_diabetes = has_positive_condition(text, ["diabetes", "sugar", "मधुमेह", "शुगर"])
            if has_diabetes:
                diab_dur = re.search(r'(\b\d+\s*(?:years?|months?|साल|वर्षे|महिने)\b)', lower)
                if diab_dur and current_field != "diabetes_history":
                    extracted.append(("pre_existing_conditions", "diabetes_history", diab_dur.group(0).strip()))

        # 4. Extract Medicines if co-mentioned affirmatively during medical history or medications
        if current_section in ["pre_existing_conditions", "current_medicines"]:
            if current_field != "active_medications":
                med_keywords = ["metformin", "amlodipine", "paracetamol", "pantoprazole", "insulin", "aspirin", "tablet", "दवा", "औषध"]
                if has_positive_condition(text, med_keywords):
                    extracted.append(("current_medicines", "active_medications", text))

            if current_field == "active_medications":
                if VAGUE_MEDICINE_REGEX.search(lower) and not any(kw in lower for kw in ["metformin", "amlodipine", "pantoprazole", "paracetamol", "telmisartan", "atorvastatin", "insulin"]):
                    extracted.append(("current_medicines", "active_medications_is_vague", "true"))

            if current_field == "clarified_active_meds":
                extracted.append(("current_medicines", "clarified_active_meds", text))
                extracted.append(("current_medicines", "active_medications_is_vague", "false"))

        return extracted

    def get_next_dynamic_question(
        self,
        answered_data: Dict[str, str],
        preferred_language: str = "en",
        speech_failures: int = 0
    ) -> Optional[QuestionResponse]:
        """
        Dynamically formulates the next clinical interview question following the consultation flow:
        Symptoms -> Medical History -> Medications -> Allergies -> Family History -> Lifestyle.
        Never repeats fields that are already answered or co-extracted.
        Respects negations so patients are never asked follow-ups for illnesses they denied.
        """
        lang = preferred_language if preferred_language in ["en", "hi", "mr"] else "en"
        show_tap = speech_failures >= 2

        # -------------------------------------------------------------
        # STAGE 1: Current Symptoms & Concerns
        # -------------------------------------------------------------
        chief = answered_data.get("chief_complaint")
        duration = answered_data.get("symptom_duration")
        severity = answered_data.get("symptom_severity")
        associated = answered_data.get("associated_symptoms")
        modulating = answered_data.get("modulating_factors")

        duration_is_vague = (answered_data.get("symptom_duration_is_vague") == "true")
        duration_clarified = answered_data.get("symptom_duration_clarified")
        pain_char = answered_data.get("pain_character_radiation")
        rule_out = answered_data.get("symptom_rule_out")

        # 1A. Initial open-ended chief complaint
        if not chief:
            prompts = {
                "en": "Hello! I am your AI clinical assistant. What primary health problem or symptoms bring you to the clinic today?",
                "hi": "नमस्ते! मैं आपका डिजिटल क्लिनिकल सहायक हूँ। आज आपको क्या मुख्य तकलीफ या समस्या हो रही है?",
                "mr": "नमस्कार! मी तुमचा डिजिटल क्लिनिकल सहाय्यक आहे. आज तुम्हाला काय मुख्य त्रास किंवा लक्षणे जाणवत आहेत?"
            }
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id="sym_chief",
                field_key="chief_complaint",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=1,
                total_section_questions=3,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        clean_chief = self._clean_symptom_phrase(chief, lang)
        detected_chronic = self._detect_chronic_condition(chief)
        detected_acute = self._detect_acute_illness(chief)
        has_symptom = bool(EXPLICIT_SYMPTOM_REGEX.search(chief))
        ro_data = get_complaint_rule_out_prompt(chief)

        # Case I: Patient stated a chronic condition in chief complaint (e.g. "I have diabetes", "I have BP")
        # Ask what specific symptoms or concerns bring them to the clinic today instead of "is the discomfort mild, moderate, or severe"
        if detected_chronic and not has_symptom and not associated:
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id=f"sym_chronic_reason_{detected_chronic['id']}",
                field_key="associated_symptoms",
                prompt=detected_chronic["follow_up"][lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=3,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # Case II: Patient stated an acute diagnosed illness (e.g. "I have dengue", "I have typhoid", "मुझे पीलिया है")
        if detected_acute and not duration:
            acute_name = detected_acute["labels"].get(lang, detected_acute["labels"]["en"])
            acute_prompts = {
                "en": f"Understood, you have been diagnosed with {acute_name}. Since how many days have you had this, and what symptoms are you currently experiencing, such as fever, weakness, or body ache?",
                "hi": f"समझ गया, आपको {acute_name} की समस्या है। यह तकलीफ आपको कितने दिनों से है, और अभी आपको बुखार, कमजोरी या बदन दर्द जैसी क्या तकलीफ महसूस हो रही है?",
                "mr": f"समजले, तुम्हाला {acute_name} चा त्रास आहे. हा त्रास तुम्हाला किती दिवसांपासून आहे आणि सध्या ताप, अशक्तपणा किंवा अंगदुखी यांसारखी काय लक्षणे जाणवत आहेत?"
            }
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id=f"sym_acute_{detected_acute['id']}",
                field_key="symptom_duration",
                prompt=acute_prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=3,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 1B. Dynamic symptom elaboration
        bridge = get_empathy_bridge(answered_data, lang)

        # 1B-i. Duration and Severity
        if not duration or not severity:
            if not duration and not severity:
                target_field = "symptom_duration"
                if clean_chief in ["your symptoms", "these symptoms"]:
                    en_prompt = f"{bridge}I understand you are experiencing these symptoms. Since how many days have you had this, and is the discomfort mild, moderate, or severe?"
                else:
                    en_prompt = f"{bridge}I understand you are experiencing {clean_chief}. Since how many days have you had this, and is the discomfort mild, moderate, or severe?"

                if clean_chief in ["आपकी समस्या", "आपकी तकलीफ"]:
                    hi_prompt = f"{bridge}समझ गया, आपको यह समस्या है। यह तकलीफ आपको कितने दिनों से हो रही है, और यह हल्की है या बहुत तेज?"
                else:
                    hi_prompt = f"{bridge}समझ गया, आपको {clean_chief} की समस्या है। यह तकलीफ आपको कितने दिनों से हो रही है, और यह हल्की है या बहुत तेज?"

                if clean_chief in ["तुमचा त्रास", "या त्रासात"]:
                    mr_prompt = f"{bridge}समजले, तुम्हाला हा त्रास होत आहे. हा त्रास तुम्हाला किती दिवसांपासून होत आहे आणि तो सौम्य आहे की तीव्र?"
                else:
                    mr_prompt = f"{bridge}समजले, तुम्हाला {clean_chief} चा त्रास होत आहे. हा त्रास तुम्हाला किती दिवसांपासून होत आहे आणि तो सौम्य आहे की तीव्र?"
            elif not duration:
                target_field = "symptom_duration"
                en_prompt = f"{bridge}Since how many days or hours have you been experiencing this discomfort?"
                hi_prompt = f"{bridge}यह तकलीफ आपको कितने दिनों या घंटों से हो रही है?"
                mr_prompt = f"{bridge}हा त्रास तुम्हाला किती दिवसांपासून किंवा तासांपासून होत आहे?"
            else:
                target_field = "symptom_severity"
                en_prompt = f"{bridge}How intense or severe is the discomfort right now—is it mild, moderate, or severe?"
                hi_prompt = f"{bridge}यह तकलीफ अभी कितनी तेज है—हल्की, मध्यम या बहुत ज्यादा?"
                mr_prompt = f"{bridge}हा त्रास सध्या किती तीव्र आहे—सौम्य, मध्यम की खूप जास्त?"

            prompts = {"en": en_prompt, "hi": hi_prompt, "mr": mr_prompt}
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id=f"sym_dyn_{target_field}",
                field_key=target_field,
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=3,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 1B-ii. Clarification for Vague Duration (e.g., "thode din se", "some days")
        if duration_is_vague and not duration_clarified:
            clarify_prompts = {
                "en": "To help the doctor assess this accurately, could you estimate about how many days that has been—for example, 2 to 3 days, or more than a week?",
                "hi": "डॉक्टर साहब के सटीक आकलन के लिए, क्या आप बता सकते हैं कि यह लगभग कितने दिनों से है—जैसे 2-3 दिन या एक हफ्ते से ज्यादा?",
                "mr": "डॉक्टरांच्या अचूक अंदाजासाठी, साधारण किती दिवस झाले असावेत—उदा. २ ते ३ दिवस की एका आठवड्यापेक्षा जास्त?"
            }
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id="sym_clarify_duration",
                field_key="symptom_duration_clarification",
                prompt=clarify_prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=3,
                total_section_questions=4,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 1B-iii. Pain SOCRATES (Character & Radiation) for pain complaints
        if is_pain_complaint(chief) and not pain_char:
            pain_prompts = get_pain_socrates_prompt(chief)
            p_prompt = f"{bridge}{pain_prompts[lang]}"
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id="sym_pain_socrates",
                field_key="pain_character_radiation",
                prompt=p_prompt,
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=3,
                total_section_questions=4,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 1B-iv. Targeted Complaint Rule-Out (Review of Systems)
        if ro_data and not rule_out:
            ro_id, ro_prompts = ro_data
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id=f"sym_ro_{ro_id}",
                field_key="symptom_rule_out",
                prompt=ro_prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=3,
                total_section_questions=4,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 1B-v. Associated Symptoms (Fallback if complaint had no specific rule-out)
        if not ro_data and not associated:
            target_field = "associated_symptoms"
            if clean_chief in ["your symptoms", "these symptoms"]:
                en_prompt = "Are you experiencing any other symptoms with this, such as fever, vomiting, dizziness, or weakness?"
            else:
                en_prompt = f"Are you experiencing any other symptoms along with {clean_chief}, such as fever, vomiting, dizziness, or weakness?"

            prompts = {
                "en": en_prompt,
                "hi": "क्या इसके साथ आपको बुखार, उल्टी, चक्कर या कमजोरी जैसी कोई अन्य तकलीफ भी हो रही है?",
                "mr": "या त्रासासोबत तुम्हाला ताप, मळमळ, चक्कर किंवा अशक्तपणा यांसारखे काही इतर त्रास होत आहेत का?"
            }
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id=f"sym_dyn_{target_field}",
                field_key=target_field,
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=3,
                total_section_questions=4,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 1B-vi. Modulating factors (Relieving / Aggravating)
        already_detailed = bool(duration_clarified or (is_pain_complaint(chief) and ro_data and pain_char and rule_out))
        if not modulating and not already_detailed:
            target_field = "modulating_factors"
            if clean_chief in ["your symptoms", "these symptoms"]:
                en_prompt = "Noted. Does anything make your symptoms feel better or worse, such as resting, eating, or walking?"
            else:
                en_prompt = f"Noted. Does anything make your {clean_chief} feel better or worse, such as resting, eating, or walking?"

            prompts = {
                "en": en_prompt,
                "hi": "क्या किसी चीज़ से आपकी तकलीफ में आराम मिलता है या यह बढ़ती है, जैसे आराम करने से या चलने-फिरने से?",
                "mr": "काही विशिष्ट केल्याने या त्रासात आराम पडतो की तो वाढतो, जसे विश्रांती किंवा हालचाल?"
            }
            return QuestionResponse(
                section_id="symptoms",
                section_title=STAGE_TITLES["symptoms"][lang],
                question_id=f"sym_dyn_{target_field}",
                field_key=target_field,
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=4,
                total_section_questions=4,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # -------------------------------------------------------------
        # STAGE 2: Pre-existing Chronic Conditions
        # -------------------------------------------------------------
        chronic = answered_data.get("known_chronic_conditions")
        diabetes_fu = answered_data.get("diabetes_history")
        bp_fu = answered_data.get("bp_medication_status")
        asthma_fu = answered_data.get("asthma_inhaler_status")

        if not chronic:
            prompts = {
                "en": "Thank you for explaining your symptoms. Now regarding your medical background: Do you have any chronic conditions like diabetes, high blood pressure, asthma, or thyroid issues?",
                "hi": "लक्षणों की जानकारी के लिए धन्यवाद। अब आपके मेडिकल बैकग्राउंड के बारे में: क्या आपको पहले से कोई पुरानी बीमारी है जैसे शुगर (डायबिटीज), बीपी, दमा या थायराइड?",
                "mr": "लक्षणे सांगितल्याबद्दल धन्यवाद. आता तुमच्या मागील आरोग्याविषयी: तुम्हाला मधुमेह (शुगर), उच्च रक्तदाब (बीपी), दमा किंवा थायरॉईड यांसारखा कोणताही जुना आजार आहे का?"
            }
            return QuestionResponse(
                section_id="pre_existing_conditions",
                section_title=STAGE_TITLES["pre_existing_conditions"][lang],
                question_id="pec_chronic",
                field_key="known_chronic_conditions",
                prompt=prompts[lang],
                language=lang,
                question_type="multi_select_or_text",
                allowed_follow_ups=[],
                question_index=1,
                total_section_questions=2,
                is_last_in_section=False,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # Dynamic follow-ups ONLY if patient affirmatively confirmed the condition:
        # 2A. Diabetes follow-up
        if has_positive_condition(chronic, ["diabetes", "sugar", "मधुमेह", "शुगर"]) and not diabetes_fu:
            prompts = {
                "en": "How long have you had diabetes, and do you check your blood sugar levels regularly?",
                "hi": "आपको शुगर (मधुमेह) कितने समय से है, और क्या आप नियमित रूप से शुगर की जांच करते हैं?",
                "mr": "तुम्हाला मधुमेह किती वर्षांपासून आहे आणि तुम्ही रक्तातील साखरेची नियमित तपासणी करता का?"
            }
            return QuestionResponse(
                section_id="pre_existing_conditions",
                section_title=STAGE_TITLES["pre_existing_conditions"][lang],
                question_id="pec_diabetes_fu",
                field_key="diabetes_history",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=2,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 2B. Hypertension follow-up
        if has_positive_condition(chronic, ["blood pressure", "bp", "hypertension", "रक्तचाप", "बीपी"]) and not bp_fu:
            prompts = {
                "en": "For your blood pressure, do you take regular daily BP tablets prescribed by a doctor?",
                "hi": "रक्तचाप (बीपी) के लिए क्या आप डॉक्टर द्वारा दी गई रोजाना बीपी की गोली लेते हैं?",
                "mr": "रक्तदाबासाठी (बीपी) तुम्ही डॉक्टरांनी दिलेली नियमित गोळी रोज घेता का?"
            }
            return QuestionResponse(
                section_id="pre_existing_conditions",
                section_title=STAGE_TITLES["pre_existing_conditions"][lang],
                question_id="pec_bp_fu",
                field_key="bp_medication_status",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=2,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 2C. Asthma follow-up
        if has_positive_condition(chronic, ["asthma", "दमा", "श्वास"]) and not asthma_fu:
            prompts = {
                "en": "Do you use a regular daily inhaler for asthma, or only occasionally when breathless?",
                "hi": "दमे के लिए क्या आप रोजाना इनहेलर लेते हैं, या सिर्फ सांस फूलने पर कभी-कभार?",
                "mr": "दम्यासाठी तुम्ही दररोज इनहेलर वापरता की फक्त धाप लागल्यावर कधीतरी?"
            }
            return QuestionResponse(
                section_id="pre_existing_conditions",
                section_title=STAGE_TITLES["pre_existing_conditions"][lang],
                question_id="pec_asthma_fu",
                field_key="asthma_inhaler_status",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=2,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # -------------------------------------------------------------
        # STAGE 3: Current Medications
        # -------------------------------------------------------------
        meds = answered_data.get("active_medications")
        med_source = answered_data.get("medicine_source_type")
        meds_vague = (answered_data.get("active_medications_is_vague") == "true")
        clarified_meds = answered_data.get("clarified_active_meds")

        if not meds:
            prompts = {
                "en": "Got it. Regarding your medicines: Are you currently taking any regular tablets, such as for blood pressure, diabetes, or daily pain relief?",
                "hi": "समझ गया। आपकी दवाइयों के बारे में: क्या आप वर्तमान में नियमित रूप से कोई दवाई ले रहे हैं, जैसे बीपी, शुगर, गैस या दर्द निवारक गोलियां?",
                "mr": "समजले. सध्या तुम्ही कोणतीही नियमित औषधे घेत आहात का, जसे बीपी, शुगर, अ‍ॅसिडिटी किंवा वेदनाशामक गोळ्या?"
            }
            return QuestionResponse(
                section_id="current_medicines",
                section_title=STAGE_TITLES["current_medicines"][lang],
                question_id="meds_active",
                field_key="active_medications",
                prompt=prompts[lang],
                language=lang,
                question_type="multi_select_or_text",
                allowed_follow_ups=[],
                question_index=1,
                total_section_questions=1,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 3A. Clarify vague medications (e.g. "ek safed goli", "small white pill", "bp tablet")
        if meds_vague and not clarified_meds:
            prompts = {
                "en": "Could you tell me the name on the tablet strip, or what time of day and what condition the doctor prescribed it for?",
                "hi": "क्या आपको उस गोली का नाम याद है, या डॉक्टर साहब ने उसे किस समय और किस बीमारी के लिए लेने को कहा था?",
                "mr": "त्या गोळीचे नाव आठवते का, किंवा डॉक्टरांनी ती कोणत्या वेळी आणि कशासाठी घेण्यास सांगितली होती?"
            }
            return QuestionResponse(
                section_id="current_medicines",
                section_title=STAGE_TITLES["current_medicines"][lang],
                question_id="meds_clarify",
                field_key="clarified_active_meds",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=2,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # 3B. Follow-up if taking active medicines
        if has_positive_condition(meds, ["tablet", "medicine", "pill", "daily", "दवा", "गोली", "औषध", "mg", "dose", "amlodipine", "metformin", "pantoprazole", "paracetamol"]) and not med_source:
            prompts = {
                "en": "Were these medicines formally prescribed by a doctor, and are you taking them without missing doses?",
                "hi": "क्या ये दवाइयां डॉक्टर द्वारा लिखी गई हैं, और क्या आप इन्हें नियमित रूप से ले रहे हैं?",
                "mr": "ही औषधे डॉक्टरांच्या सल्ल्याने सुरू केली आहेत का आणि तुम्ही ती न चुकता वेळेवर घेता का?"
            }
            return QuestionResponse(
                section_id="current_medicines",
                section_title=STAGE_TITLES["current_medicines"][lang],
                question_id="meds_source",
                field_key="medicine_source_type",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=2,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # -------------------------------------------------------------
        # STAGE 4: Allergies & Drug Reactions
        # -------------------------------------------------------------
        allergies = answered_data.get("allergies_list")
        reaction_fu = answered_data.get("allergy_reaction_type")

        if not allergies:
            prompts = {
                "en": "Understood. Next, for medication safety: Do you have any known allergies to medicines (such as penicillin or pain injections), foods, or dust?",
                "hi": "समझ गया। अब दवाइयों की सुरक्षा के लिए: क्या आपको किसी दवाई (जैसे पेनिसिलिन या इंजेक्शन), किसी खाने की चीज़ या धूल से कोई एलर्जी है?",
                "mr": "समजले. आता औषध सुरक्षेविषयी: तुम्हाला कोणत्याही औषधाची (उदा. पेनिसिलिन, इंजेक्शन), अन्नाची किंवा धुळीची काही अ‍ॅलर्जी आहे का?"
            }
            return QuestionResponse(
                section_id="allergies",
                section_title=STAGE_TITLES["allergies"][lang],
                question_id="alg_general",
                field_key="allergies_list",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=1,
                total_section_questions=1,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # Follow-up if allergic
        if has_positive_condition(allergies, ["allergy", "allergic", "reaction", "एलर्जी", "अ‍ॅलर्जी", "rash", "itching", "penicillin", "dust"]) and not reaction_fu:
            prompts = {
                "en": "What specific reaction occurs when you are exposed—such as skin itching, hives, swelling, or breathing tightness?",
                "hi": "एलर्जी होने पर आपको क्या रिएक्शन होता है—जैसे त्वचा पर खुजली, लाल दाने, सूजन या सांस में तकलीफ?",
                "mr": "अ‍ॅलर्जीमुळे काय त्रास होतो—जसे त्वचेवर खाज, पुरळ, चेहऱ्यावर सूज किंवा श्वास घेण्यास अडचण?"
            }
            return QuestionResponse(
                section_id="allergies",
                section_title=STAGE_TITLES["allergies"][lang],
                question_id="alg_reaction",
                field_key="allergy_reaction_type",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=2,
                total_section_questions=2,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # -------------------------------------------------------------
        # STAGE 5: Family Health History
        # -------------------------------------------------------------
        family = answered_data.get("family_health_history")
        if not family:
            prompts = {
                "en": "Noted. Does anyone in your immediate family (parents or siblings) have a history of heart disease, diabetes, high blood pressure, or kidney illness?",
                "hi": "क्या आपके परिवार (माता-पिता या भाई-बहन) में किसी को दिल की बीमारी, शुगर, बीपी या किडनी की कोई समस्या रही है?",
                "mr": "तुमच्या कुटुंबात (आई-वडील किंवा भावंडे) कोणाला हृदयविकार, मधुमेह, उच्च रक्तदाब किंवा मूत्रपिंडाचा आजार आहे का?"
            }
            return QuestionResponse(
                section_id="family_history",
                section_title=STAGE_TITLES["family_history"][lang],
                question_id="fam_history",
                field_key="family_health_history",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=1,
                total_section_questions=1,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # -------------------------------------------------------------
        # STAGE 6: General Lifestyle & Digestion
        # -------------------------------------------------------------
        lifestyle = answered_data.get("agni_digestion_quality")
        if not lifestyle:
            prompts = {
                "en": "Lastly, how is your daily digestion and sleep? Do you experience acidity, constipation, or disturbed sleep?",
                "hi": "अंतिम सवाल: आपका पाचन और नींद कैसी रहती है? क्या पेट में एसिडिटी, कब्ज या नींद में कोई परेशानी होती है?",
                "mr": "शेवटचा प्रश्न: तुमचे पचन आणि झोप कशी आहे? गॅस, अ‍ॅसिडिटी, बद्धकोष्ठता किंवा झोपेत काही त्रास होतो का?"
            }
            return QuestionResponse(
                section_id="lifestyle",
                section_title=STAGE_TITLES["lifestyle"][lang],
                question_id="life_digestion",
                field_key="agni_digestion_quality",
                prompt=prompts[lang],
                language=lang,
                question_type="text",
                allowed_follow_ups=[],
                question_index=1,
                total_section_questions=1,
                is_last_in_section=True,
                is_interview_complete=False,
                speech_failures=speech_failures,
                show_tap_fallback=show_tap
            )

        # All clinical consultation stages have been thoroughly explored
        logger.info("Clinical history taking complete across all stages.")
        return None

clinical_dialogue_engine = ClinicalDialogueEngine()
