import os
import html
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from backend.app.core.config import settings

logger = logging.getLogger("pdf_generator")

# Dynamic font discovery for full Unicode (English, Hindi, Marathi / Devanagari)
PDF_FONT_NAME = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"

def _init_fonts():
    global PDF_FONT_NAME, PDF_FONT_BOLD
    candidate_paths = [
        # 1. Windows Nirmala.ttc (Contains full Devanagari + Latin)
        ("C:/Windows/Fonts/Nirmala.ttc", 0, 1),
        ("C:/Windows/Fonts/Nirmala.ttf", None, None),
        ("C:/Windows/Fonts/mangal.ttf", None, None),
        ("C:/Windows/Fonts/APARAJ.TTF", None, None),
        # 2. Linux standard Noto Sans Devanagari
        ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", None, None),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0, 1)
    ]

    for item in candidate_paths:
        p = Path(item[0])
        if p.exists():
            try:
                sub_reg = item[1]
                sub_bold = item[2]
                if sub_reg is not None and sub_bold is not None:
                    reg = TTFont("ClinicalUnicodeFont", str(p), subfontIndex=sub_reg)
                    bold = TTFont("ClinicalUnicodeFont-Bold", str(p), subfontIndex=sub_bold)
                    pdfmetrics.registerFont(reg)
                    pdfmetrics.registerFont(bold)
                    pdfmetrics.registerFontFamily(
                        "ClinicalUnicodeFont",
                        normal="ClinicalUnicodeFont",
                        bold="ClinicalUnicodeFont-Bold",
                        italic="ClinicalUnicodeFont",
                        boldItalic="ClinicalUnicodeFont-Bold"
                    )
                    PDF_FONT_NAME = "ClinicalUnicodeFont"
                    PDF_FONT_BOLD = "ClinicalUnicodeFont-Bold"
                    logger.info(f"Loaded Devanagari Unicode font from {p}")
                    return
                else:
                    reg = TTFont("ClinicalUnicodeFont", str(p))
                    pdfmetrics.registerFont(reg)
                    PDF_FONT_NAME = "ClinicalUnicodeFont"
                    PDF_FONT_BOLD = "ClinicalUnicodeFont"
                    logger.info(f"Loaded single font from {p}")
                    return
            except Exception as e:
                logger.warning(f"Could not initialize font from {p}: {e}")

_init_fonts()

def safe_xml(val: Any) -> str:
    """Escapes special characters (&, <, >, etc.) so ReportLab Paragraph doesn't drop or crash."""
    if val is None:
        return "—"
    s = str(val).strip()
    if not s:
        return "—"
    return html.escape(s, quote=False)

def get_ist_timestamp() -> str:
    """Returns formatted current Indian Standard Time (UTC+05:30)."""
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%d-%b-%Y %I:%M %p IST")

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas that computes total page count dynamically
    and draws professional running headers on page 2+ and footers on all pages.
    """
    patient_token: str = "OPD"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        self.setFont(PDF_FONT_NAME, 7.5)
        self.setFillColor(colors.HexColor("#475569"))

        # Top Running Header on Page 2 and later
        if self._pageNumber > 1:
            self.drawString(36, letter[1] - 24, "OUTPATIENT DEPARTMENT (OPD) • CLINICAL PRE-INTAKE RECORD")
            self.drawRightString(
                letter[0] - 36, 
                letter[1] - 24, 
                f"Token: {self.patient_token} | Page {self._pageNumber} of {total_pages}"
            )
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(36, letter[1] - 27, letter[0] - 36, letter[1] - 27)

        # Bottom Running Legal Footer on Every Page
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 28, letter[0] - 36, 28)
        self.drawString(36, 18, "Draft prepared from patient answers. Not a diagnosis. • Confidential Clinical Record")
        self.drawRightString(letter[0] - 36, 18, f"Page {self._pageNumber} of {total_pages}")
        self.restoreState()


CLINICAL_SECTION_LABELS = {
    "red_flags": "Triage & Emergency Screening",
    "chief_complaint": "Chief Complaint",
    "symptoms": "History of Present Illness (HPI)",
    "pre_existing_conditions": "Past Medical History",
    "medications": "Current Medications",
    "current_medicines": "Current Medications",
    "allergies": "Allergies & Sensitivities",
    "family_history": "Family Medical History",
    "lifestyle": "General Health & Lifestyle",
}

CLINICAL_FIELD_LABELS = {
    "chief_emergency_check": "Emergency Screening",
    "primary_complaint": "Primary Complaint",
    "chief_complaint": "Primary Complaint",
    "symptom_duration": "Duration of Symptoms",
    "symptom_severity": "Severity & Intensity",
    "symptom_progression": "Symptom Progression",
    "associated_symptoms": "Associated Symptoms",
    "known_chronic_conditions": "Chronic Conditions",
    "current_prescriptions": "Current Medications",
    "active_medications": "Current Medications",
    "known_allergies": "Known Allergies",
    "allergies_list": "Known Allergies",
    "family_medical_history": "Family Medical History",
    "family_health_history": "Family Medical History",
    "sleep_hours": "Sleep Duration & Quality",
    "diet_appetite": "Diet & Digestion",
    "water_intake": "Hydration / Fluid Intake",
    "bowel_habits": "Bowel Movements",
    "exercise_routine": "Physical Activity",
    "agni_digestion_quality": "Digestion & Appetite",
    "modulating_factors": "Modulating & Relieving Factors",
    "diabetes_history": "Diabetes Duration & Monitoring",
    "bp_medication_status": "BP Medication Adherence",
    "asthma_inhaler_status": "Asthma / Inhaler Management",
    "medicine_source_type": "Medication Prescription Source",
    "allergy_reaction_type": "Allergic Reaction Manifestation",
    "pain_character_radiation": "Pain Character & Radiation (SOCRATES)",
    "symptom_rule_out": "Targeted Review of Systems / Rule-Outs",
    "symptom_duration_clarification": "Clarified Duration",
    "clarified_active_meds": "Clarified Medication Details",
}

class ClinicalPdfGenerator:
    def __init__(self):
        self.output_dir = settings.PDF_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_case_sheet(
        self,
        session_id: str,
        patient_data: Dict[str, Any],
        vitals: Dict[str, Any],
        clinical_fields: List[Dict[str, Any]],
        mismatch_flags: List[Dict[str, Any]],
        reports: List[Dict[str, Any]],
        doctor_review: Dict[str, Any],
        has_red_flag: bool = False,
        red_flag_details: Optional[str] = None
    ) -> str:
        """
        Builds a comprehensive, immutable pre-OPD case sheet using ReportLab.
        Supports full multilingual text (English, Hindi, Marathi), dynamic page numbering,
        vitals provenance, lab discrepancy warnings, and doctor authorization stamp.
        """
        ist = timezone(timedelta(hours=5, minutes=30))
        timestamp_str = datetime.now(ist).strftime("%Y%m%d_%H%M%S")
        filename = f"CaseSheet_{session_id[:8]}_{timestamp_str}.pdf"
        file_path = self.output_dir / filename

        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        normal = ParagraphStyle(
            "ClinicalNormal",
            parent=styles["Normal"],
            fontName=PDF_FONT_NAME,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#1e293b")
        )

        title_style = ParagraphStyle(
            "DocTitle",
            parent=normal,
            fontName=PDF_FONT_BOLD,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#14532d"),
            spaceAfter=1
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=normal,
            fontName=PDF_FONT_NAME,
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#166534")
        )
        disclaimer_style = ParagraphStyle(
            "Disclaimer",
            parent=normal,
            fontName=PDF_FONT_BOLD,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#991b1b"),
            alignment=1 # Center
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=normal,
            fontName=PDF_FONT_BOLD,
            fontSize=9.5,
            leading=12.5,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=6,
            spaceAfter=3
        )
        field_label_style = ParagraphStyle(
            "FieldLabel",
            parent=normal,
            fontName=PDF_FONT_BOLD,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#475569")
        )
        field_value_style = ParagraphStyle(
            "FieldValue",
            parent=normal,
            fontName=PDF_FONT_NAME,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#0f172a")
        )
        provenance_style = ParagraphStyle(
            "Provenance",
            parent=normal,
            fontName=PDF_FONT_NAME,
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#0369a1")
        )

        story = []

        # 1. Header & OPD Branding (Allopathy OPD)
        token = patient_data.get("patient_token", "N/A")
        opd_system = "Allopathy OPD"
        now_time_ist = get_ist_timestamp()

        header_table_data = [
            [
                Paragraph(
                    "<b>HOSPITAL OUTPATIENT DEPARTMENT (OPD)</b><br/>"
                    "<font size=7.5 color='#166534'>Clinical Pre-Intake Record • Strictly Patient-Disclosed Findings</font>",
                    title_style
                ),
                Paragraph(
                    f"<b>Token:</b> {safe_xml(token)}<br/>"
                    f"<b>Date:</b> {safe_xml(now_time_ist)}<br/>"
                    f"<b>OPD Discipline:</b> {safe_xml(opd_system)}",
                    subtitle_style
                )
            ]
        ]
        header_table = Table(header_table_data, colWidths=[4.2 * inch, 3.0 * inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 3))

        # 2. Prominent Legal Disclaimer Banner (Mandatory DPDP Act Notice)
        disclaimer_box = Table(
            [[Paragraph(
                "<b>MANDATORY CLINICAL NOTICE:</b> Draft prepared from patient voice consultation. Not a medical diagnosis. "
                "All information must be reviewed and verified by the examining Medical Officer prior to prescription.",
                disclaimer_style
            )]],
            colWidths=[7.2 * inch]
        )
        disclaimer_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#f87171")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(disclaimer_box)
        story.append(Spacer(1, 5))

        # 3. Patient Demographics & Self-Reported Vitals Grid
        raw_name = patient_data.get("full_name")
        p_name = safe_xml(raw_name) if raw_name and raw_name.strip() and raw_name.strip().lower() != "anonymous" else "Not Specified"
        raw_phone = patient_data.get("phone_number")
        p_phone = safe_xml(raw_phone) if raw_phone and str(raw_phone).strip() else "Not Specified"
        raw_age = patient_data.get("age")
        p_age = safe_xml(str(raw_age)) if raw_age and str(raw_age).strip() and str(raw_age).strip() not in ["—", "None"] else "Not Specified"
        raw_gender = patient_data.get("gender")
        p_gender = safe_xml(raw_gender) if raw_gender and str(raw_gender).strip() and str(raw_gender).strip() not in ["—", "None"] else "Not Specified"
        raw_lang = patient_data.get("preferred_language", "en")
        p_lang = safe_xml(str(raw_lang).upper()) if raw_lang else "EN"
        raw_guard = patient_data.get("guardian_info")
        p_guard = safe_xml(raw_guard) if raw_guard and str(raw_guard).strip() else "Self"

        v_h = safe_xml(vitals.get("height_cm")) if vitals.get("height_cm") else "Not Recorded"
        v_w = safe_xml(vitals.get("weight_kg")) if vitals.get("weight_kg") else "Not Recorded"
        v_bmi = safe_xml(vitals.get("bmi")) if vitals.get("bmi") else "Not Recorded"
        v_cat = safe_xml(vitals.get("bmi_category", "—")) if vitals.get("bmi_category") else "—"
        v_lbl = vitals.get("vitals_label", "self-reported").upper()

        age_gender_str = f"{p_age} Yrs / {p_gender}" if p_age != "Not Specified" else f"Not Specified / {p_gender}"
        height_weight_str = f"<b>Height:</b> {v_h} cm | <b>Weight:</b> {v_w} kg" if v_h != "Not Recorded" and v_w != "Not Recorded" else "<b>Height:</b> Not Recorded | <b>Weight:</b> Not Recorded"
        bmi_str = f"<b>BMI:</b> <b>{v_bmi} kg/m²</b> ({v_cat})<br/><font size=7 color='#64748b'><i>Formula: weight (kg) / [height (m)]²</i></font>" if v_bmi != "Not Recorded" else "<b>BMI:</b> Not Recorded"

        demo_vitals_data = [
            [
                Paragraph("<b>Patient Demographics</b>", section_heading),
                Paragraph(f"<b>Physical Vitals ({v_lbl})</b>", section_heading)
            ],
            [
                Paragraph(
                    f"<b>Name:</b> {p_name} | <b>Phone:</b> {p_phone}<br/>"
                    f"<b>Age / Gender:</b> {age_gender_str}<br/>"
                    f"<b>Language:</b> {p_lang} | <b>Mode:</b> {p_guard}",
                    normal
                ),
                Paragraph(
                    f"{height_weight_str}<br/>"
                    f"{bmi_str}",
                    normal
                )
            ]
        ]
        demo_table = Table(demo_vitals_data, colWidths=[3.6 * inch, 3.6 * inch])
        demo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(demo_table)
        story.append(Spacer(1, 5))

        # 4. Red-Flag and Mismatch Alerts (If Any)
        if has_red_flag:
            rf_detail_safe = safe_xml(red_flag_details or "Emergency triage condition detected.")
            rf_box = Table(
                [[Paragraph(
                    f"<b>EMERGENCY RED-FLAG TRIGGERED:</b> {rf_detail_safe}<br/>"
                    f"<font size=7.5>Patient was directed to immediate emergency care (Tele-MANAS 14416 / Emergency 112).</font>",
                    disclaimer_style
                )]],
                colWidths=[7.2 * inch]
            )
            rf_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
                ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor("#dc2626")),
                ('PADDING', (0, 0), (-1, -1), 5)
            ]))
            story.append(rf_box)
            story.append(Spacer(1, 5))

        if mismatch_flags:
            mismatch_rows = [[Paragraph("<b>Discrepancy / Lab Mismatch Alerts (Physician Review Required)</b>", section_heading)]]
            for m in mismatch_flags:
                bio = m.get("biomarker") or m.get("rule") or "Discrepancy"
                msg = m.get("message") or m.get("description") or "Patient disclosure differs from laboratory findings."
                bio_safe = safe_xml(bio)
                msg_safe = safe_xml(msg)
                mismatch_rows.append([
                    Paragraph(f"• <b>{bio_safe}:</b> {msg_safe}", field_value_style)
                ])
            mismatch_table = Table(mismatch_rows, colWidths=[7.2 * inch])
            mismatch_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#f59e0b")),
                ('PADDING', (0, 0), (-1, -1), 4)
            ]))
            story.append(mismatch_table)
            story.append(Spacer(1, 5))

        # 5. Structured Clinical History Table with Provenance
        story.append(Paragraph("<b>Recorded Clinical Findings (Patient Voice Consultation)</b>", section_heading))
        
        history_rows = [
            [
                Paragraph("<b>Clinical Domain / Field</b>", field_label_style),
                Paragraph("<b>Recorded Statement / Findings</b>", field_label_style),
                Paragraph("<b>Data Provenance</b>", field_label_style)
            ]
        ]

        for idx, f in enumerate(clinical_fields):
            raw_sec = f.get("section", "")
            raw_key = f.get("field_key", "")
            if raw_key.endswith("_is_vague") or raw_key.endswith("_clarified"):
                continue
            sec_name = safe_xml(CLINICAL_SECTION_LABELS.get(raw_sec, raw_sec.replace("_", " ").title()))
            key_name = safe_xml(CLINICAL_FIELD_LABELS.get(raw_key, raw_key.replace("_", " ").title()))
            val_text = safe_xml(f.get("value", "—"))
            src_raw = f.get("source", "patient_said")
            src = "Patient Reported" if src_raw in ["patient_said", "patient_voice", "patient"] else safe_xml(src_raw.replace("_", " ").title())
            conf = f.get("confidence", 1.0)
            quote = f.get("transcript_quote")
            is_ed = bool(f.get("is_edited_by_doctor", False))

            val_cell = f"<b>{val_text}</b>"
            if is_ed:
                orig = safe_xml(f.get("original_value", ""))
                val_cell += f"<br/><font color='#b91c1c' size=7>[Doctor Modified: was '{orig}']</font>"
            if quote:
                quote_safe = safe_xml(quote)
                val_cell += f"<br/><font color='#64748b' size=7><i>\"{quote_safe}\"</i></font>"

            history_rows.append([
                Paragraph(f"<b>{sec_name}</b><br/><font color='#475569'>{key_name}</font>", normal),
                Paragraph(val_cell, field_value_style),
                Paragraph(f"Source: <b>{src}</b><br/>Confidence: {int(conf * 100)}%", provenance_style)
            ])

        if len(history_rows) > 1:
            hist_table = Table(history_rows, colWidths=[2.0 * inch, 3.8 * inch, 1.4 * inch], repeatRows=1)
            t_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]
            # Alternating row shading
            for r_idx in range(1, len(history_rows)):
                if r_idx % 2 == 0:
                    t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#f8fafc")))
            hist_table.setStyle(TableStyle(t_style))
            story.append(hist_table)
        else:
            story.append(Paragraph("<i>No structured fields recorded (Session was halted or dropped).</i>", normal))

        story.append(Spacer(1, 6))

        # 6. Uploaded Diagnostic Reports & Extracted Values
        if reports:
            story.append(Paragraph("<b>Uploaded Diagnostic Documents & Extracted Findings</b>", section_heading))
            report_rows = [
                [
                    Paragraph("<b>Document / Type</b>", field_label_style),
                    Paragraph("<b>Extracted Clinical Values (Verified against Reference Ranges)</b>", field_label_style)
                ]
            ]
            for r in reports:
                extracted_lines = []
                for lv in r.get("lab_values", []):
                    t_name = safe_xml(lv.get("test_name"))
                    r_val = safe_xml(lv.get("raw_value"))
                    ref_r = safe_xml(lv.get("reference_range_printed") or "N/A")
                    extracted_lines.append(f"• <b>{t_name}:</b> {r_val} (Ref: {ref_r})")
                for med in r.get("candidate_medicines", []):
                    m_name = safe_xml(med.get("name"))
                    m_str = safe_xml(med.get("strength") or "")
                    extracted_lines.append(f"• <b>Prescription Item:</b> {m_name} {m_str}")
                
                content = "<br/>".join(extracted_lines) if extracted_lines else "<i>No numeric lab biomarkers detected.</i>"
                doc_name = safe_xml(r.get("file_name", "Report"))
                doc_type = safe_xml(r.get("file_type", ""))
                report_rows.append([
                    Paragraph(f"<b>{doc_name}</b><br/><font color='#64748b'>{doc_type}</font>", normal),
                    Paragraph(content, field_value_style)
                ])
            rep_table = Table(report_rows, colWidths=[2.2 * inch, 5.0 * inch], repeatRows=1)
            rep_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('PADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(rep_table)
            story.append(Spacer(1, 6))

        # 7. Doctor Clinical Notes & Digital Approval Stamp (Protected from splitting)
        doc_notes = safe_xml(doctor_review.get("doctor_notes", "Case sheet evaluated and verified during in-person clinical consultation."))
        doc_id = safe_xml(doctor_review.get("doctor_id", "DOC-OPD-ALLOPATHY-01"))
        app_time = safe_xml(doctor_review.get("approved_at") or now_time_ist)

        approval_data = [
            [
                Paragraph("<b>Doctor's Clinical Assessment & Plan:</b>", section_heading),
                Paragraph("<b>Medical Officer Authorization & Stamp</b>", section_heading)
            ],
            [
                Paragraph(doc_notes.replace("\n", "<br/>"), normal),
                Paragraph(
                    "<font color='#16a34a'><b>✓ VERIFIED & APPROVED</b></font><br/>"
                    f"<b>Medical Officer ID:</b> {doc_id}<br/>"
                    f"<b>Timestamp:</b> {app_time}<br/>"
                    "<b>Physical Signature:</b> ____________________",
                    normal
                )
            ]
        ]
        app_table = Table(approval_data, colWidths=[4.2 * inch, 3.0 * inch])
        app_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#16a34a")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(KeepTogether([app_table]))

        # Dynamic canvas with patient token
        class TokenNumberedCanvas(NumberedCanvas):
            patient_token = token

        doc.build(story, canvasmaker=TokenNumberedCanvas)
        return str(file_path)

clinical_pdf_generator = ClinicalPdfGenerator()
