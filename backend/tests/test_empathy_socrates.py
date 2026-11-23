import pytest
from backend.app.services.clinical_dialogue_engine import (
    ClinicalDialogueEngine,
    is_pain_complaint,
    get_pain_socrates_prompt,
    get_complaint_rule_out_prompt,
    get_empathy_bridge,
    VAGUE_DURATION_REGEX,
    VAGUE_MEDICINE_REGEX,
)

def test_vague_duration_detection():
    engine = ClinicalDialogueEngine()
    
    # 1. Vague Hindi phrasing
    extracted_hi = engine.parse_and_extract_entities(
        raw_text="kuch dino se hai aur bahut tez hai",
        current_field="symptom_duration",
        current_section="symptoms",
        language="hi"
    )
    extracted_map = {f[1]: f[2] for f in extracted_hi}
    assert extracted_map.get("symptom_duration_is_vague") == "true"
    assert extracted_map.get("symptom_severity") == "Severe"

    # 2. Specific duration should NOT be marked vague
    extracted_specific = engine.parse_and_extract_entities(
        raw_text="3 days se hai",
        current_field="symptom_duration",
        current_section="symptoms",
        language="hi"
    )
    extracted_map_spec = {f[1]: f[2] for f in extracted_specific}
    assert extracted_map_spec.get("symptom_duration_is_vague") is None

    # 3. Clarification of vague duration updates duration and clears vague flag
    clarified = engine.parse_and_extract_entities(
        raw_text="lagbhag 3 din se",
        current_field="symptom_duration_clarification",
        current_section="symptoms",
        language="hi"
    )
    clarified_map = {f[1]: f[2] for f in clarified}
    assert clarified_map.get("symptom_duration") == "lagbhag 3 din se"
    assert clarified_map.get("symptom_duration_clarified") == "lagbhag 3 din se"
    assert clarified_map.get("symptom_duration_is_vague") == "false"

def test_vague_medication_detection():
    engine = ClinicalDialogueEngine()

    # 1. Vague medicine phrasing
    extracted = engine.parse_and_extract_entities(
        raw_text="main ek safed goli leta hu",
        current_field="active_medications",
        current_section="current_medicines",
        language="hi"
    )
    extracted_map = {f[1]: f[2] for f in extracted}
    assert extracted_map.get("active_medications_is_vague") == "true"

    # 2. Specific medicine phrasing should NOT be marked vague
    extracted_specific = engine.parse_and_extract_entities(
        raw_text="Amlodipine 5mg daily",
        current_field="active_medications",
        current_section="current_medicines",
        language="en"
    )
    extracted_map_spec = {f[1]: f[2] for f in extracted_specific}
    assert extracted_map_spec.get("active_medications_is_vague") is None

    # 3. Clarifying vague medication
    clarified = engine.parse_and_extract_entities(
        raw_text="It is a BP tablet, doctor prescribed it for morning",
        current_field="clarified_active_meds",
        current_section="current_medicines",
        language="en"
    )
    clarified_map = {f[1]: f[2] for f in clarified}
    assert clarified_map.get("clarified_active_meds") == "It is a BP tablet, doctor prescribed it for morning"
    assert clarified_map.get("active_medications_is_vague") == "false"

def test_empathy_bridges():
    # Severe pain bridge
    data_sev = {"chief_complaint": "headache", "symptom_severity": "Severe"}
    bridge_en = get_empathy_bridge(data_sev, "en")
    assert "in so much pain" in bridge_en

    bridge_hi = get_empathy_bridge(data_sev, "hi")
    assert "इतनी तेज तकलीफ" in bridge_hi

    # Fever with body ache bridge
    data_fever = {"chief_complaint": "fever and severe body pain"}
    bridge_fev = get_empathy_bridge(data_fever, "en")
    assert "exhausting" in bridge_fev

def test_pain_socrates_flow():
    engine = ClinicalDialogueEngine()

    # Chest pain complaint
    answered = {
        "chief_complaint": "severe chest pain",
        "symptom_duration": "2 hours",
        "symptom_severity": "Severe"
    }
    q = engine.get_next_dynamic_question(answered, preferred_language="en")
    assert q is not None
    assert q.field_key == "pain_character_radiation"
    assert "heavy squeezing pressure" in q.prompt
    assert "left arm" in q.prompt
    # Bridge should be prepended
    assert "in so much pain" in q.prompt

    # Marathi translation check for headache
    answered_mr = {
        "chief_complaint": "डोकेदुखी",
        "symptom_duration": "२ दिवस",
        "symptom_severity": "तीव्र"
    }
    q_mr = engine.get_next_dynamic_question(answered_mr, preferred_language="mr")
    assert q_mr is not None
    assert q_mr.field_key == "pain_character_radiation"
    assert "धडधडल्यासारखी" in q_mr.prompt

def test_targeted_rule_out_flow():
    engine = ClinicalDialogueEngine()

    # Fever rule-out
    answered_fever = {
        "chief_complaint": "high fever",
        "symptom_duration": "3 days",
        "symptom_severity": "Moderate"
    }
    q_fev = engine.get_next_dynamic_question(answered_fever, preferred_language="en")
    assert q_fev is not None
    assert q_fev.field_key == "symptom_rule_out"
    assert "shivering chills" in q_fev.prompt
    assert "skin rash" in q_fev.prompt

    # Cough rule-out in Hindi
    answered_cough = {
        "chief_complaint": "खांसी",
        "symptom_duration": "4 दिन",
        "symptom_severity": "मध्यम"
    }
    q_cough = engine.get_next_dynamic_question(answered_cough, preferred_language="hi")
    assert q_cough is not None
    assert q_cough.field_key == "symptom_rule_out"
    assert "बलगम" in q_cough.prompt
    assert "खून" in q_cough.prompt

def test_vague_duration_triggers_clarification_question():
    engine = ClinicalDialogueEngine()

    answered = {
        "chief_complaint": "stomach pain",
        "symptom_duration": "kuch dino se",
        "symptom_duration_is_vague": "true",
        "symptom_severity": "Moderate"
    }
    q = engine.get_next_dynamic_question(answered, preferred_language="hi")
    assert q is not None
    assert q.field_key == "symptom_duration_clarification"
    assert "2-3 दिन या एक हफ्ते से ज्यादा" in q.prompt

def test_vague_medication_triggers_clarification_question():
    engine = ClinicalDialogueEngine()

    answered = {
        "chief_complaint": "fever",
        "symptom_duration": "2 days",
        "symptom_severity": "Mild",
        "symptom_rule_out": "No chills",
        "modulating_factors": "Rest",
        "known_chronic_conditions": "None",
        "active_medications": "I take one white tablet daily",
        "active_medications_is_vague": "true"
    }
    q = engine.get_next_dynamic_question(answered, preferred_language="en")
    assert q is not None
    assert q.field_key == "clarified_active_meds"
    assert "tablet strip" in q.prompt

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
