import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from backend.app.core.config import settings
from backend.app.schemas.intake import QuestionResponse
from backend.app.services.clinical_dialogue_engine import has_positive_condition

logger = logging.getLogger("question_engine")

SECTION_ORDER = [
    "symptoms",
    "pre_existing_conditions",
    "current_medicines",
    "allergies",
    "family_history",
    "lifestyle"
]

class QuestionEngine:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (settings.CONFIG_DIR / "question_bank.json")
        self.bank = self._load_bank()
        self.max_symptom_questions = self.bank.get("_metadata", {}).get("max_symptom_questions", 13)

    def _load_bank(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load question_bank.json: {e}")
            return {"sections": []}

    def get_section(self, section_id: str) -> Optional[Dict[str, Any]]:
        for sec in self.bank.get("sections", []):
            if sec.get("id") == section_id:
                return sec
        return None

    def get_next_question(
        self,
        current_section: str,
        answered_fields: List[str],
        symptom_questions_asked: int = 0,
        consecutive_speech_failures: int = 0,
        preferred_language: str = "en",
        answered_data: Optional[Dict[str, str]] = None
    ) -> Optional[QuestionResponse]:
        """
        Determines the next official clinical question to present.
        Enforces section ordering, required fields, symptom caps, and dynamic relevant follow-ups.
        """
        curr_idx = SECTION_ORDER.index(current_section) if current_section in SECTION_ORDER else 0

        # Iterate through remaining sections starting from current_section
        for s_idx in range(curr_idx, len(SECTION_ORDER)):
            sec_id = SECTION_ORDER[s_idx]
            sec_data = self.get_section(sec_id)
            if not sec_data:
                continue

            sec_title = sec_data.get("title", {}).get(
                preferred_language,
                sec_data.get("title", {}).get("en", sec_id)
            )
            questions = sec_data.get("questions", [])

            # Check if this is symptoms and cap exceeded
            if sec_id == "symptoms" and symptom_questions_asked >= self.max_symptom_questions:
                continue

            for q_idx, q in enumerate(questions):
                field_key = q.get("field")

                # If primary question is not answered yet, present it
                if field_key not in answered_fields:
                    prompt_text = q.get("prompt", {}).get(
                        preferred_language,
                        q.get("prompt", {}).get("en", "")
                    )
                    
                    show_tap = consecutive_speech_failures >= 2
                    is_last_in_sec = (q_idx == len(questions) - 1) and not q.get("follow_ups")

                    return QuestionResponse(
                        section_id=sec_id,
                        section_title=sec_title,
                        question_id=q.get("id"),
                        field_key=field_key,
                        prompt=prompt_text,
                        language=preferred_language,
                        question_type=q.get("type", "text"),
                        allowed_follow_ups=q.get("follow_ups", []),
                        question_index=q_idx + 1,
                        total_section_questions=len(questions),
                        is_last_in_section=is_last_in_sec,
                        is_interview_complete=False,
                        speech_failures=consecutive_speech_failures,
                        show_tap_fallback=show_tap
                    )

                # If primary question IS answered, check if any dynamic follow-up is triggered
                if answered_data and q.get("follow_ups"):
                    parent_val = (answered_data.get(field_key) or "").lower()
                    for fu in q.get("follow_ups", []):
                        fu_field = fu.get("field")
                        if fu_field and fu_field not in answered_fields:
                            cond = fu.get("condition_keyword", "").lower()
                            matches = False
                            if cond == "diabetes":
                                matches = has_positive_condition(parent_val, ["diabetes", "sugar", "मधुमेह", "शुगर"])
                            elif cond == "blood pressure":
                                matches = has_positive_condition(parent_val, ["blood pressure", "bp", "रक्तचाप", "बीपी", "hypertension"])
                            elif cond == "asthma":
                                matches = has_positive_condition(parent_val, ["asthma", "दमा", "श्वास"])
                            elif cond == "any_medicine":
                                matches = has_positive_condition(parent_val, ["tablet", "medicine", "pill", "daily", "दवा", "गोली", "औषध", "mg"])
                            elif cond in ["yes", "any_allergy"]:
                                matches = has_positive_condition(parent_val, ["allergy", "allergic", "reaction", "एलर्जी", "अ‍ॅलर्जी", "rash", "itching"])

                            if matches:
                                prompt_text = fu.get("follow_up_prompt", {}).get(
                                    preferred_language,
                                    fu.get("follow_up_prompt", {}).get("en", "")
                                )
                                show_tap = consecutive_speech_failures >= 2
                                return QuestionResponse(
                                    section_id=sec_id,
                                    section_title=sec_title,
                                    question_id=f"{q.get('id')}_{fu_field}",
                                    field_key=fu_field,
                                    prompt=prompt_text,
                                    language=preferred_language,
                                    question_type="text",
                                    allowed_follow_ups=[],
                                    question_index=q_idx + 1,
                                    total_section_questions=len(questions),
                                    is_last_in_section=False,
                                    is_interview_complete=False,
                                    speech_failures=consecutive_speech_failures,
                                    show_tap_fallback=show_tap
                                )

        # If all sections complete
        return None

    def advance_section(self, current_section: str) -> Optional[str]:
        """Advances to the next logical section in the predefined sequence."""
        if current_section not in SECTION_ORDER:
            return None
        idx = SECTION_ORDER.index(current_section)
        if idx + 1 < len(SECTION_ORDER):
            return SECTION_ORDER[idx + 1]
        return None

question_engine = QuestionEngine()
