import urllib.request
import json
import io
import pypdf

base_url = 'http://127.0.0.1:8000'

def req(method, path, body=None):
    url = f'{base_url}{path}'
    data = json.dumps(body).encode('utf-8') if body else None
    headers = {'Content-Type': 'application/json'} if body else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request) as res:
        content_type = res.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            return res.status, json.loads(res.read().decode('utf-8'))
        return res.status, res.read()

def run_e2e_simulation():
    # 1. Reset seed
    status, data = req('POST', '/api/v1/seed/reset')
    print('Seed reset:', status, data.get('status'))

    # 2. Login
    status, pat = req('POST', '/api/v1/auth/login', {'phone_number': '9876543210', 'language': 'en'})
    token = pat['patient_token']
    session_id = pat['session_id']
    print(f'Logged in patient: {token}, session: {session_id}')

    # 3. Consent
    status, consent = req('POST', '/api/v1/intake/consent', {'patient_token': token, 'consent_given': True, 'preferred_language': 'en'})
    print('Consent recorded:', status)

    # 4. Vitals
    status, vitals = req('POST', '/api/v1/intake/vitals', {'patient_token': token, 'session_id': session_id, 'height_cm': 172.0, 'weight_kg': 68.0})
    print('Vitals recorded: BMI =', vitals.get('bmi'), vitals.get('bmi_category'))

    # 5. Multi-turn Dynamic Interview
    # Turn 1: Patient gives chief complaint + co-mentions severity & duration
    # Notice: "I have had severe headache and vomiting since 3 days"
    # Should extract: chief_complaint, symptom_severity, symptom_duration, associated_symptoms
    # Turn 2: Since duration, severity, and associated symptoms were co-extracted, AI asks modulating factors!
    # Turn 3: Chronic conditions + duration co-mention: "I have had diabetes for 4 years"
    # Turn 4: Current medications: "I take Metformin 500mg daily after food"
    # Turn 5: Allergies: "No allergies to any medicines or food"
    # Turn 6: Family history: "My father has hypertension and diabetes"
    # Turn 7: Lifestyle & Digestion: "Digestion is normal with no acidity, sleep is 7 hours"
    
    turns = [
        ('I have had severe headache and vomiting since 3 days', 'Turn 1: Chief + co-mentions'),
        ('Sitting in a dark room makes it better, noise and light make it worse', 'Turn 2: Modulating factors'),
        ('I have had diabetes for 4 years', 'Turn 3: Chronic conditions + duration co-mention'),
        ('I take Metformin 500mg daily after food', 'Turn 4: Current medications'),
        ('No allergies to any medicines or food', 'Turn 5: Allergies'),
        ('My father has hypertension and diabetes', 'Turn 6: Family history'),
        ('Digestion is normal with no acidity, sleep is 7 hours', 'Turn 7: Lifestyle & Digestion')
    ]

    import time
    # 5A. Get initial question
    status, current_q = req('GET', f'/api/v1/intake/question?patient_token={token}&session_id={session_id}')
    assert current_q is not None, "Failed to get initial question"

    latencies = []
    for patient_input, turn_label in turns:
        if not current_q:
            print(f'[{turn_label}]: Intake complete early!')
            break
        print(f'AI asked ({current_q["section_id"]}.{current_q["field_key"]}): "{current_q["prompt"]}"')

        # Time the turn: POST answer returning the piggybacked next_question in 1 roundtrip
        t0 = time.perf_counter()
        status, ans = req('POST', '/api/v1/intake/answer', {
            'patient_token': token,
            'session_id': session_id,
            'section_id': current_q['section_id'],
            'field_key': current_q['field_key'],
            'value': patient_input,
            'source': 'patient_said'
        })
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)
        print(f'   -> Patient replied: "{patient_input}" [Turn response time: {elapsed_ms:.1f}ms]')
        
        # Verify next_question was piggybacked in response
        assert "next_question" in ans, "next_question must be piggybacked in answer response"
        current_q = ans.get("next_question")

    print(f'\nAverage Turn Response Latency: {sum(latencies)/len(latencies):.1f}ms (Max: {max(latencies):.1f}ms, Min: {min(latencies):.1f}ms)')
    assert current_q is None, f'Expected None after all stages answered, got {current_q}'

    # 6. Patient Review
    status, review = req('GET', f'/api/v1/intake/review?patient_token={token}&session_id={session_id}')
    sections_dict = review.get("sections", {})
    print(f'Patient review retrieved. Sections count: {len(sections_dict)}')
    for sec_id, fields in sections_dict.items():
        print(f'  Section {sec_id}: {len(fields)} fields answered: {[f["field_key"] for f in fields]}')

    # 7. Submit Final Intake
    status, sub = req('POST', f'/api/v1/intake/submit?patient_token={token}&session_id={session_id}')
    print('Final intake submitted to queue:', status, sub.get('status'))
    assert sub.get('status') in ['completed', 'success']

    # 8. Doctor Case Review
    status, case = req('GET', f'/api/v1/doctor/case/{session_id}')
    sections_in_case = case.get("sections", {})
    total_fields = sum(len(f_list) for f_list in sections_in_case.values())
    print(f'Doctor case review retrieved. Status: {status}, Total fields across sections: {total_fields}')
    assert total_fields >= 7, f'Expected at least 7 clinical fields, got {total_fields}'

    # 9. Doctor Approval & PDF Generation
    status, app_res = req('POST', f'/api/v1/doctor/case/{session_id}/approve', {
        'doctor_id': 'DOC-OPD-ALLOPATHY-01',
        'doctor_notes': 'Clinical examination performed in Allopathy OPD. Vitals and history verified.'
    })
    print('Doctor approval completed:', status, app_res.get('status'), app_res.get('pdf_download_url'))
    assert app_res.get('status') == 'approved'

    # 10. PDF Download & Verification
    status, pdf_bytes = req('GET', f'/api/v1/doctor/case/{session_id}/pdf')
    print(f'PDF generated & downloaded: HTTP {status}, size: {len(pdf_bytes)} bytes')

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    print(f'PDF page count: {len(reader.pages)}')
    pdf_text = '\n'.join([page.extract_text() or '' for page in reader.pages])

    print('\n--- PDF Content Verification ---')
    assert 'Allopathy' in pdf_text, 'Missing Allopathy discipline in PDF'
    print('  [PASS] Allopathy discipline present in PDF')

    assert 'Not a diagnosis' in pdf_text or 'Draft prepared from patient answers' in pdf_text, 'Missing legal disclaimer'
    print('  [PASS] Legal disclaimer present in PDF')

    assert 'headache' in pdf_text.lower(), 'Missing chief complaint in PDF'
    print('  [PASS] Chief complaint present in PDF')

    assert 'metformin' in pdf_text.lower(), 'Missing medications in PDF'
    print('  [PASS] Medications present in PDF')

    # Strict check: ensure zero random/synthetic seed strings leaked into the PDF
    assert 'Ramesh Sharma' not in pdf_text, 'Random seed name Ramesh Sharma leaked into PDF!'
    assert 'AYUSH' not in pdf_text, 'AYUSH branding leaked into Allopathy PDF!'
    assert 'Mandagni' not in pdf_text, 'Ayurveda term Mandagni leaked into Allopathy PDF!'
    assert 'AI-Generated Consultation Summary' not in pdf_text, 'Speculative AI summary block found in PDF!'
    print('  [PASS] Zero random/synthetic seed data in PDF - strictly patient disclosed facts!')

    print('\nALL E2E VERIFICATIONS PASSED!')

if __name__ == '__main__':
    run_e2e_simulation()
