import React, { useState, useEffect, useRef } from 'react';
import { 
  Mic, MicOff, Volume2, VolumeX, FastForward, Check, X, 
  HelpCircle, AlertOctagon, Type, Sliders, ArrowRight, Sparkles, Send, Edit3, RotateCcw
} from 'lucide-react';
import { audioManager } from '../../audio/audio_manager';
import { liveAudioClient } from '../../audio/live_audio_client';
import { fetchNextQuestion, recordAnswer, resetIntakeSession } from '../../services/api';
import ConversationEndScreen from './ConversationEndScreen';

const QUESTION_CHIPS = {
  known_chronic_conditions: [
    { label: 'None / No Illness (कोई नहीं)', value: 'None, no known chronic illness' },
    { label: 'Diabetes / शुगर (मधुमेह)', value: 'Type 2 Diabetes Mellitus' },
    { label: 'High BP / रक्तचाप (बीपी)', value: 'High Blood Pressure (Hypertension)' },
    { label: 'Asthma / दमा', value: 'Bronchial Asthma' },
    { label: 'Acidity / गैस / पित्त', value: 'Hyperacidity and digestive gas' },
    { label: 'Thyroid / थायराइड', value: 'Hypothyroidism' }
  ],
  allergies_list: [
    { label: 'No Allergies (कोई एलर्जी नहीं)', value: 'No known allergies to food, drugs or herbs' },
    { label: 'Dust & Smoke', value: 'Allergy to dust and vehicular smoke' },
    { label: 'Skin Rash / Hives', value: 'Skin allergy with itching and red rash' },
    { label: 'Drug / Antibiotic Allergy', value: 'Allergic reaction to specific antibiotics' }
  ],
  active_medications: [
    { label: 'No Medicines (कोई दवा नहीं)', value: 'No regular or active medicines' },
    { label: 'Daily BP Tablet', value: 'Amlodipine 5mg once daily for BP' },
    { label: 'Diabetes Tablet', value: 'Metformin 500mg daily after meals' },
    { label: 'Antacid / Acidity Pill', value: 'Pantoprazole 40mg daily before meals' },
    { label: 'Painkiller / Paracetamol', value: 'Paracetamol 650mg as needed for pain or fever' },
    { label: 'Vitamins / Calcium', value: 'Multivitamin and calcium supplements' }
  ],
  family_health_history: [
    { label: 'No Major Family Illness', value: 'No significant family history of chronic illness' },
    { label: 'Diabetes in Family', value: 'Father has diabetes' },
    { label: 'High BP in Family', value: 'Mother has hypertension' },
    { label: 'Heart Disease in Family', value: 'Family history of heart problems' }
  ],
  chief_complaint: [
    { label: 'Fever & Bodyache (बुखार)', value: 'Fever with generalized body ache and weakness' },
    { label: 'Cough & Cold (खांसी जुकाम)', value: 'Dry cough and throat irritation with runny nose' },
    { label: 'Knee / Joint Pain (घुटनों में दर्द)', value: 'Knee stiffness and joint pain, especially in morning' },
    { label: 'Acidity / Stomach Pain (पेट दर्द)', value: 'Burning sensation in chest and stomach acidity' },
    { label: 'Headache & Migraine (सिरदर्द)', value: 'Throbbing headache and dizziness' },
    { label: 'Fatigue & Tiredness (थकान)', value: 'Severe fatigue, lack of energy and disturbed sleep' }
  ],
  symptom_duration: [
    { label: '1 - 2 Days', value: '2 days' },
    { label: '3 - 5 Days', value: '4 days' },
    { label: '1 - 2 Weeks', value: '10 days' },
    { label: 'More than 1 Month', value: '6 weeks' }
  ],
  symptom_severity: [
    { label: 'Mild (हल्का / कमी)', value: 'Mild discomfort, able to perform daily tasks' },
    { label: 'Moderate (मध्यम)', value: 'Moderate pain, disrupts work and daily routine' },
    { label: 'Severe (तेज़ / जास्त)', value: 'Severe pain, unable to rest or work' }
  ],
  associated_symptoms: [
    { label: 'No Other Symptoms (कोई अन्य नहीं)', value: 'No other associated symptoms, just the main complaint' },
    { label: 'Fever & Chills (बुखार / ताप)', value: 'Mild fever with feeling of chills' },
    { label: 'Nausea & Vomiting (उल्टी / मळमळ)', value: 'Nausea, loss of appetite and feeling like vomiting' },
    { label: 'Headache & Dizziness (सिरदर्द / चक्कर)', value: 'Persistent headache and dizziness' },
    { label: 'Generalized Weakness (कमजोरी / थकवा)', value: 'General body ache and extreme fatigue' }
  ],
  diabetes_history: [
    { label: 'Under 1 Year (1 साल से कम)', value: 'Diagnosed less than 1 year ago, sugar mostly normal' },
    { label: '1 - 5 Years (1-5 साल)', value: 'Diagnosed 1 to 5 years ago, checking sugar regularly' },
    { label: 'Over 5 Years (5 साल से ज्यादा)', value: 'Longstanding diabetes over 5 years' }
  ],
  bp_medication_status: [
    { label: 'Daily BP Tablet (रोजाना दवा)', value: 'Taking prescribed BP tablet daily without missing' },
    { label: 'Sometimes / Irregular (अनियमित)', value: 'Taking BP tablet irregularly when feeling dizzy' },
    { label: 'Not on Medicines (दवा नहीं लेता)', value: 'Diagnosed high BP but currently not taking medicine' }
  ],
  asthma_inhaler_status: [
    { label: 'Daily Inhaler (रोजाना)', value: 'Using regular daily inhaler or nebulizer' },
    { label: 'As Needed (जरूरत पड़ने पर)', value: 'Only using SOS inhaler during acute breathlessness' },
    { label: 'Stable / No Recent Attack', value: 'Stable asthma, no major attack in past 6 months' }
  ],
  medicine_source_type: [
    { label: 'Doctor Prescribed (डॉक्टर की सलाह)', value: 'Formally prescribed by a licensed allopathic doctor' },
    { label: 'Self-Started / Pharmacy (बिना पर्ची)', value: 'Over-the-counter medicine purchased directly from pharmacy' },
    { label: 'Prescription from Specialist', value: 'Prescribed by clinical specialist during prior hospital visit' }
  ],
  allergy_reaction_type: [
    { label: 'Skin Rash & Itching (दाने व खाज)', value: 'Allergic reaction presents with red skin rash and intense itching' },
    { label: 'Swelling of Face/Lips (सूजन)', value: 'Facial and lip swelling' },
    { label: 'Breathing Tightness (सांस में तकलीफ)', value: 'Throat tightness and difficulty breathing' }
  ],
  agni_digestion_quality: [
    { label: 'Normal / Regular Digestion', value: 'Normal digestion and regular bowel movements' },
    { label: 'Slow / Heaviness after meals', value: 'Sluggish digestion with abdominal bloating and heaviness' },
    { label: 'Hyperacidity / Heartburn', value: 'Frequent heartburn, acid reflux and burning sensation' }
  ],
  modulating_factors: [
    { label: 'Better with Rest (आराम से राहत)', value: 'Symptoms improve significantly with physical rest' },
    { label: 'Worse with Movement (चलने से बढ़ता है)', value: 'Discomfort increases with physical exertion or movement' },
    { label: 'Relieved by Warm Water / Food', value: 'Discomfort decreases after warm liquids or light food' },
    { label: 'Constant / No Change', value: 'Discomfort remains constant, nothing noticeably alters it' }
  ],
  symptom_duration_clarification: [
    { label: '2 - 3 Days (2 से 3 दिन)', value: 'About 2 to 3 days' },
    { label: '4 - 7 Days / 1 Week (लगभग 1 हफ्ता)', value: 'About 4 to 7 days, roughly one week' },
    { label: '1 - 2 Weeks (1 से 2 हफ्ते)', value: 'Around 1 to 2 weeks' },
    { label: 'More than a Month (1 महीने से ज्यादा)', value: 'More than one month' }
  ],
  pain_character_radiation: [
    { label: 'Sharp & Piercing (तेज चुभन वाला)', value: 'Sharp, stabbing or piercing pain' },
    { label: 'Throbbing / Pulsing (धड़कन जैसा / नस फड़कना)', value: 'Throbbing, pulsing pain like a heartbeat' },
    { label: 'Dull & Heavy Ache (भारीपन / मंद दर्द)', value: 'Dull, continuous heavy ache or pressure' },
    { label: 'Burning / Heat Sensation (जलन / जळजळ)', value: 'Burning sensation or acid-like irritation' },
    { label: 'Spreading to Arm / Neck (हाथ या गर्दन में फैलना)', value: 'Spreading to left arm, neck, or jaw' },
    { label: 'Radiating to Back / Legs (पीठ या पैरों में खिंचाव)', value: 'Radiating down to back or legs' },
    { label: 'Localized (एक ही जगह रहता है)', value: 'Localized in one spot, does not radiate' }
  ],
  symptom_rule_out: [
    { label: 'No Chills, Rash or Urine Burning (कोई कंपकंपी/दाने नहीं)', value: 'No shivering chills, no rash, and no burning urination' },
    { label: 'Severe Shivering Chills (तेज कंपकंपी / थंडी)', value: 'Severe shivering chills with fever' },
    { label: 'Dry Cough, No Phlegm or Blood (सूखी खांसी, खून नहीं)', value: 'Dry cough without phlegm and no blood' },
    { label: 'Phlegm Present, No Blood (बलगम है, खून नहीं)', value: 'Cough with phlegm but no blood' },
    { label: 'Morning Stiffness > 30 Mins (सुबह जोड़ों में अकड़न)', value: 'Joint stiffness lasting more than 30 minutes in morning' },
    { label: 'No Neck Stiffness or Blurred Vision (गर्दन अकड़न नहीं)', value: 'No neck stiffness and clear vision' },
    { label: 'Able to Keep Fluids Down, No Blood (पानी पच रहा है)', value: 'Able to drink fluids, no blood in stool or vomit' }
  ],
  clarified_active_meds: [
    { label: 'Daily BP Tablet in Morning (रोज सुबह बीपी की गोली)', value: 'Daily blood pressure tablet taken in the morning' },
    { label: 'Diabetes Tablet after Meals (शुगर की गोली खाने के बाद)', value: 'Diabetes tablet taken daily after meals' },
    { label: 'Antacid Empty Stomach (सुबह खाली पेट गैस की गोली)', value: 'Antacid tablet taken empty stomach in the morning' },
    { label: 'Paracetamol Only When Needed (सिर्फ जरूरत पड़ने पर)', value: 'Paracetamol taken only SOS when pain or fever occurs' },
    { label: 'Have Physical Prescription to Show (डॉक्टर को पर्ची दिखाएंगे)', value: 'Patient has physical medicine strip/prescription to show doctor' }
  ]
};

export default function VoiceInterview({ 
  patient, 
  session, 
  onLanguageChange,
  onInterviewFinished, 
  onRedFlagTriggered, 
  onSessionExpired 
}) {
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [state, setState] = useState('tap_to_start'); // 'tap_to_start' | 'speaking' | 'listening' | 'reviewing' | 'processing'
  const [liveCaptions, setLiveCaptions] = useState('');
  const [draftAnswer, setDraftAnswer] = useState('');
  const [isMicActive, setIsMicActive] = useState(false);
  const [failures, setFailures] = useState(0);
  const [largeText, setLargeText] = useState(false);
  const [speed, setSpeed] = useState(1.0);
  const [turnLatency, setTurnLatency] = useState(null);
  const [loading, setLoading] = useState(false);
  const [micNotice, setMicNotice] = useState(null);
  const [liveNotice, setLiveNotice] = useState(null);
  const [autoAdvanceCountdown, setAutoAdvanceCountdown] = useState(null);

  const currentQuestionRef = useRef(null);
  const draftAnswerRef = useRef('');
  const isSubmittingRef = useRef(false);
  const autoAdvanceTimerRef = useRef(null);
  const autoAdvanceIntervalRef = useRef(null);
  const liveFallbackTimerRef = useRef(null);
  const handleConfirmAndNextRef = useRef(null);
  const startListeningTurnRef = useRef(null);

  // Keep references constantly synced with state
  currentQuestionRef.current = currentQuestion;
  draftAnswerRef.current = draftAnswer;

  const clearAutoAdvance = () => {
    if (autoAdvanceTimerRef.current) {
      clearTimeout(autoAdvanceTimerRef.current);
      autoAdvanceTimerRef.current = null;
    }
    if (autoAdvanceIntervalRef.current) {
      clearInterval(autoAdvanceIntervalRef.current);
      autoAdvanceIntervalRef.current = null;
    }
    setAutoAdvanceCountdown(null);
  };

  const scheduleAutoAdvance = (text, delayMs = 1200) => {
    clearAutoAdvance();
    const candidate = (text || draftAnswerRef.current || '').trim();
    if (!candidate || candidate.length < 2) return;

    setAutoAdvanceCountdown(Math.ceil(delayMs / 1000));
    const targetTime = Date.now() + delayMs;

    autoAdvanceIntervalRef.current = setInterval(() => {
      const remainingMs = targetTime - Date.now();
      if (remainingMs <= 0) {
        if (autoAdvanceIntervalRef.current) {
          clearInterval(autoAdvanceIntervalRef.current);
          autoAdvanceIntervalRef.current = null;
        }
      } else {
        setAutoAdvanceCountdown(Math.ceil(remainingMs / 1000));
      }
    }, 100);

    autoAdvanceTimerRef.current = setTimeout(() => {
      clearAutoAdvance();
      if (handleConfirmAndNextRef.current) {
        handleConfirmAndNextRef.current(candidate);
      }
    }, delayMs);
  };

  const lang = patient.preferred_language || 'en';

  useEffect(() => {
    audioManager.requestWakeLock();
    audioManager.prewarmAudio();

    // Connect WebSocket for Gemini Live API & Backend Triage Stream
    if (session?.session_id && patient?.patient_token) {
      liveAudioClient.connect({
        sessionId: session.session_id,
        patientToken: patient.patient_token,
        language: lang,
        onNotice: (msg) => {
          setLiveNotice(msg);
        },
        onTranscript: (speaker, text) => {
          if (liveFallbackTimerRef.current) {
            clearTimeout(liveFallbackTimerRef.current);
            liveFallbackTimerRef.current = null;
          }
          if (speaker === 'patient') {
            const cleanText = (text || '').trim();
            if (cleanText) {
              draftAnswerRef.current = cleanText;
              setDraftAnswer((prev) => {
                if (!prev) return cleanText;
                if (prev.includes(cleanText)) return prev;
                return `${prev} ${cleanText}`.trim();
              });
              setState('listening');
              scheduleAutoAdvance(cleanText, 1200);
            }
          } else if (speaker === 'assistant') {
            setLiveCaptions((prev) => {
              if (!prev || prev === currentQuestionRef.current?.prompt) return text;
              return prev.includes(text) ? prev : `${prev} ${text}`.trim();
            });
          }
        },
        onSpeechStart: () => {
          if (liveFallbackTimerRef.current) {
            clearTimeout(liveFallbackTimerRef.current);
            liveFallbackTimerRef.current = null;
          }
          clearAutoAdvance();
          setState('speaking');
          audioManager.stopListening();
          liveAudioClient.stopAudioCapture();
          setIsMicActive(false);
        },
        onSpeechEnd: () => {
          if (startListeningTurnRef.current) {
            startListeningTurnRef.current();
          }
        },
        onLiveFallback: (prompt, fallbackLang) => {
          if (liveFallbackTimerRef.current) {
            clearTimeout(liveFallbackTimerRef.current);
            liveFallbackTimerRef.current = null;
          }
          setState('speaking');
          audioManager.speak(prompt, fallbackLang || lang, () => {
            if (startListeningTurnRef.current) {
              startListeningTurnRef.current();
            }
          });
        },
        onRedFlag: (alert) => {
          onRedFlagTriggered(alert);
        },
        onLatency: (ms) => {
          setTurnLatency(ms);
        }
      });
    }

    return () => {
      clearAutoAdvance();
      if (liveFallbackTimerRef.current) {
        clearTimeout(liveFallbackTimerRef.current);
        liveFallbackTimerRef.current = null;
      }
      audioManager.stopSpeaking();
      audioManager.stopListening();
      audioManager.releaseWakeLock();
      liveAudioClient.disconnect();
    };
  }, [session?.session_id, patient?.patient_token, lang]);

  const applyQuestion = (q) => {
    clearAutoAdvance();
    isSubmittingRef.current = false;
    if (liveFallbackTimerRef.current) {
      clearTimeout(liveFallbackTimerRef.current);
      liveFallbackTimerRef.current = null;
    }
    setLoading(false);
    setDraftAnswer('');
    draftAnswerRef.current = '';
    audioManager.clearTranscript();
    setIsMicActive(false);

    if (!q || q.is_interview_complete) {
      setState('finished');
      onInterviewFinished();
      return;
    }

    currentQuestionRef.current = q;
    setCurrentQuestion(q);
    setLiveCaptions(q.prompt);
    setState('speaking');

    const isLive = liveAudioClient.isConnected && (liveAudioClient.adapterType === 'LiveAdapter' || !liveAudioClient.adapterType);
    if (isLive) {
      audioManager.stopSpeaking();
      liveAudioClient.askQuestion(q.prompt, lang);

      // 5.5s safety timeout: if Gemini Live cloud audio fails to arrive, fallback to local voice
      liveFallbackTimerRef.current = setTimeout(() => {
        if (!liveAudioClient.isPlaying) {
          console.warn('Gemini Live speech start timeout, falling back to local speech');
          audioManager.speak(q.prompt, lang, () => {
            if (startListeningTurnRef.current) {
              startListeningTurnRef.current(q);
            }
          });
        }
      }, 5500);
    } else {
      audioManager.speak(q.prompt, lang, () => {
        if (startListeningTurnRef.current) {
          startListeningTurnRef.current(q);
        }
      });
    }
  };

  const loadQuestion = async (failCount = failures) => {
    setLoading(true);
    setDraftAnswer('');
    draftAnswerRef.current = '';
    audioManager.clearTranscript();
    setIsMicActive(false);
    try {
      const q = await fetchNextQuestion(patient.patient_token, session.session_id, failCount);
      applyQuestion(q);
    } catch (err) {
      console.error('Failed to get question:', err);
      setLoading(false);
      if (err.message === 'SESSION_EXPIRED' && onSessionExpired) {
        onSessionExpired();
      }
    }
  };

  const handleRepeatQuestion = () => {
    const q = currentQuestionRef.current;
    if (!q) return;
    clearAutoAdvance();
    if (liveFallbackTimerRef.current) {
      clearTimeout(liveFallbackTimerRef.current);
      liveFallbackTimerRef.current = null;
    }
    setState('speaking');
    audioManager.stopSpeaking();
    liveAudioClient.stopAudioPlayback();

    const isLive = liveAudioClient.isConnected && (liveAudioClient.adapterType === 'LiveAdapter' || !liveAudioClient.adapterType);
    if (isLive) {
      liveAudioClient.askQuestion(q.prompt, lang);
      liveFallbackTimerRef.current = setTimeout(() => {
        if (!liveAudioClient.isPlaying) {
          audioManager.speak(q.prompt, lang, () => {
            if (startListeningTurnRef.current) {
              startListeningTurnRef.current(q);
            }
          });
        }
      }, 5500);
    } else {
      audioManager.speak(q.prompt, lang, () => {
        if (startListeningTurnRef.current) {
          startListeningTurnRef.current(q);
        }
      });
    }
  };

  const handleInitialStart = () => {
    liveAudioClient.ensureAudioContext();
    loadQuestion(0);
  };

  const startListeningTurn = (q = currentQuestionRef.current) => {
    clearAutoAdvance();
    setState('listening');
    setIsMicActive(true);
    setMicNotice(null);

    // Give browser speech recognition clean exclusive access to microphone
    audioManager.startListening(
      lang,
      (interim, final, fullText) => {
        const text = fullText || final || interim;
        if (text && text.trim()) {
          const cleanText = text.trim();
          draftAnswerRef.current = cleanText;
          setDraftAnswer(cleanText);
          setMicNotice(null);
          // Calibrated silence auto-advance: 1.2s of silence triggers turn progression
          scheduleAutoAdvance(cleanText, 1200);
        }
      },
      (friendlyErr) => {
        if (!draftAnswerRef.current || !draftAnswerRef.current.trim()) {
          setMicNotice(typeof friendlyErr === 'string' ? friendlyErr : 'Microphone unavailable. Use quick chips or type below.');
          setFailures((prev) => prev + 1);
        }
      },
      (finalText) => {
        if (finalText && finalText.trim()) {
          const cleanFinal = finalText.trim();
          draftAnswerRef.current = cleanFinal;
          setDraftAnswer(cleanFinal);
          scheduleAutoAdvance(cleanFinal, 1200);
        }
      },
      (status) => {
        if (status === 'listening') {
          setIsMicActive(true);
        } else if (status === 'stopped' || status === 'error' || status === 'unsupported') {
          if (status !== 'stopped') {
            setIsMicActive(false);
          }
        }
      }
    );
  };

  const toggleMic = () => {
    clearAutoAdvance();
    if (isMicActive) {
      audioManager.stopListening();
      liveAudioClient.stopAudioCapture();
      setIsMicActive(false);
    } else {
      audioManager.stopSpeaking();
      liveAudioClient.stopAudioPlayback();
      audioManager.setCommittedText(draftAnswerRef.current || draftAnswer);
      startListeningTurn();
    }
  };

  const handleSelectChip = (chipValue) => {
    clearAutoAdvance();
    audioManager.stopSpeaking();
    liveAudioClient.stopAudioPlayback();
    audioManager.stopListening();
    liveAudioClient.stopAudioCapture();
    setIsMicActive(false);

    const q = currentQuestionRef.current;
    const isMulti = q?.question_type === 'multi_select_or_text' || q?.field_key === 'known_chronic_conditions';

    if (isMulti) {
      let updated = chipValue;
      if (chipValue.includes('None') || chipValue.includes('कोई नहीं')) {
        updated = chipValue;
      } else {
        const prev = draftAnswerRef.current || '';
        if (prev && !prev.includes('None') && !prev.includes('कोई नहीं')) {
          const items = prev.split(', ').map(s => s.trim()).filter(Boolean);
          if (items.includes(chipValue)) {
            updated = items.filter(i => i !== chipValue).join(', ');
          } else {
            updated = [...items, chipValue].join(', ');
          }
        }
      }
      draftAnswerRef.current = updated;
      setDraftAnswer(updated);
      audioManager.setCommittedText(updated);
      // Multi-select: auto-advance after 1.5s pause so patient can tap multiple chips or wait
      if (updated.trim()) {
        scheduleAutoAdvance(updated, 1500);
      }
    } else {
      draftAnswerRef.current = chipValue;
      setDraftAnswer(chipValue);
      audioManager.setCommittedText(chipValue);
      // Single-select: 800ms auto-advance gives immediate visual feedback then advances automatically
      scheduleAutoAdvance(chipValue, 800);
    }
  };

  const handleConfirmAndNext = async (textToSubmit = null) => {
    clearAutoAdvance();
    if (isSubmittingRef.current) return;

    const q = currentQuestionRef.current;
    const text = (textToSubmit || draftAnswerRef.current || draftAnswer || '').trim();
    if (!text || !q) {
      console.warn('handleConfirmAndNext: skipped due to missing text or question', { text, q });
      return;
    }

    isSubmittingRef.current = true;
    audioManager.stopListening();
    audioManager.stopSpeaking();
    liveAudioClient.stopAudioPlayback();
    liveAudioClient.stopAudioCapture();
    setIsMicActive(false);
    setState('processing');

    const t0 = performance.now();
    try {
      const res = await recordAnswer({
        patient_token: patient.patient_token,
        session_id: session.session_id,
        section_id: q.section_id,
        field_key: q.field_key,
        value: text,
        source: 'patient_said',
        confidence: 0.95,
        transcript_quote: text
      });

      const elapsed = Math.round(performance.now() - t0);
      setTurnLatency(elapsed);

      // Check if emergency red-flag triggered
      if (res.status === 'emergency_halt') {
        onRedFlagTriggered(res.red_flag);
        return;
      }

      setFailures(0);

      // Fast-path: immediately use piggybacked next question to eliminate the 2nd HTTP roundtrip
      if (res.is_interview_complete || res.next_question !== undefined) {
        applyQuestion(res.next_question);
      } else {
        loadQuestion(0);
      }
    } catch (err) {
      console.error('Answer submission error:', err);
      setState('listening');
    } finally {
      isSubmittingRef.current = false;
    }
  };

  // Keep references to functions updated for event listeners and timers
  handleConfirmAndNextRef.current = handleConfirmAndNext;
  startListeningTurnRef.current = startListeningTurn;

  // Barge-In interrupt
  const handleBargeIn = () => {
    clearAutoAdvance();
    audioManager.stopSpeaking();
    liveAudioClient.stopAudioPlayback();
    liveAudioClient.bargeIn();
    startListeningTurn();
  };

  const handleSkipQuestion = async () => {
    clearAutoAdvance();
    if (isSubmittingRef.current) return;
    const q = currentQuestionRef.current;
    if (!q) return;

    isSubmittingRef.current = true;
    audioManager.stopSpeaking();
    audioManager.stopListening();
    liveAudioClient.stopAudioPlayback();
    liveAudioClient.stopAudioCapture();
    setIsMicActive(false);

    try {
      const res = await recordAnswer({
        patient_token: patient.patient_token,
        session_id: session.session_id,
        section_id: q.section_id,
        field_key: q.field_key,
        value: 'Skipped by patient',
        source: 'skipped',
        confidence: 1.0,
        transcript_quote: 'Skipped by patient'
      });

      setFailures(0);
      if (res.is_interview_complete || res.next_question !== undefined) {
        applyQuestion(res.next_question);
      } else {
        loadQuestion(0);
      }
    } catch (e) {
      console.error('Skip question error:', e);
    } finally {
      isSubmittingRef.current = false;
    }
  };

  const handleResetSession = async () => {
    clearAutoAdvance();
    audioManager.stopSpeaking();
    liveAudioClient.stopAudioPlayback();
    audioManager.stopListening();
    liveAudioClient.stopAudioCapture();
    setIsMicActive(false);
    setLoading(true);
    setDraftAnswer('');
    draftAnswerRef.current = '';
    audioManager.clearTranscript();
    try {
      if (session?.session_id && patient?.patient_token) {
        await resetIntakeSession(patient.patient_token, session.session_id);
      }
      loadQuestion(0);
    } catch (e) {
      console.warn('Reset session notice:', e);
      loadQuestion(0);
    } finally {
      setLoading(false);
    }
  };

  const handleSpeedChange = (newSpeed) => {
    setSpeed(newSpeed);
    audioManager.speechRate = newSpeed;
  };

  if (state === 'finished') {
    return (
      <ConversationEndScreen
        patient={patient}
        session={session}
        isSubmitted={false}
        onReviewRequested={() => onInterviewFinished && onInterviewFinished()}
        onSubmittedToQueue={() => onInterviewFinished && onInterviewFinished()}
      />
    );
  }

  if (state === 'tap_to_start') {
    return (
      <div className="max-w-md mx-auto text-center p-8 bg-white rounded-2xl border border-slate-200 shadow-sm space-y-6">
        <div className="w-20 h-20 bg-emerald-100 text-emerald-800 rounded-full flex items-center justify-center mx-auto shadow-inner">
          <Mic className="w-10 h-10" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Ready for Voice Intake</h2>
          <p className="text-sm text-slate-500 mt-1">
            Tap the button below to start. The assistant will ask questions one at a time.
          </p>
        </div>
        <button
          onClick={handleInitialStart}
          className="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-bold py-4 rounded-xl shadow-lg transition text-lg flex items-center justify-center space-x-2 min-h-touch"
        >
          <span>Tap to Start Voice Interview</span>
          <ArrowRight className="w-6 h-6" />
        </button>
      </div>
    );
  }

  const chips = currentQuestion ? (QUESTION_CHIPS[currentQuestion.field_key] || []) : [];

  return (
    <div className="max-w-xl mx-auto space-y-4">
      {/* Top Controls: Language Switcher, Large Text Toggle & Speed Selector */}
      <div className="flex flex-wrap items-center justify-between gap-2 bg-white px-4 py-2.5 rounded-xl border border-slate-200 text-xs">
        {/* Language selector */}
        <div className="flex items-center space-x-1">
          <span className="text-slate-500 text-[11px] font-semibold mr-1">Speech Lang:</span>
          {[
            { code: 'en', label: 'English' },
            { code: 'hi', label: 'हिन्दी' },
            { code: 'mr', label: 'मराठी' }
          ].map((l) => (
            <button
              key={l.code}
              type="button"
              onClick={() => {
                if (onLanguageChange && lang !== l.code) {
                  onLanguageChange(l.code);
                }
              }}
              className={`px-2.5 py-1 rounded-lg font-bold transition text-xs ${
                lang === l.code
                  ? 'bg-emerald-700 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setLargeText(!largeText)}
            className={`flex items-center space-x-1 px-3 py-1.5 rounded font-medium border transition ${
              largeText ? 'bg-emerald-700 text-white border-emerald-700' : 'bg-slate-50 text-slate-700 border-slate-200'
            }`}
          >
            <Type className="w-3.5 h-3.5" />
            <span>{largeText ? 'Normal' : 'Large'}</span>
          </button>

          <span className="text-slate-400">|</span>

          <span className="text-slate-500">Speed:</span>
          {[0.8, 1.0, 1.2].map((s) => (
            <button
              key={s}
              onClick={() => handleSpeedChange(s)}
              className={`px-2 py-1 rounded font-medium ${
                speed === s ? 'bg-emerald-100 text-emerald-800 font-bold' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {s}x
            </button>
          ))}
        </div>

        {turnLatency && (
          <span className="text-slate-400 text-[10px]">Turn: {turnLatency}ms</span>
        )}
      </div>

      {/* Main Conversation Visualizer & Live Captions */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 space-y-5 text-center">
        {/* Status Badge */}
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-slate-100">
          <span className={`w-2.5 h-2.5 rounded-full ${
            state === 'speaking' ? 'bg-emerald-600 animate-pulse' :
            isMicActive ? 'bg-red-600 animate-ping' : 'bg-slate-400'
          }`} />
          <span className="text-slate-700">
            {state === 'speaking' && 'Assistant Speaking...'}
            {state === 'listening' && (isMicActive ? 'Listening to You...' : 'Ready for Answer')}
            {state === 'processing' && 'AI Extracting Details...'}
          </span>
        </div>

        {/* Section Title */}
        <p className="text-xs font-bold text-emerald-800 uppercase tracking-widest">
          {currentQuestion?.section_title || 'OPD Intake'}
        </p>

        {/* Spoken Question */}
        <div className="min-h-[70px] flex flex-col items-center justify-center px-2 space-y-2">
          <p className={`font-semibold text-slate-800 leading-snug transition-all ${
            largeText ? 'text-2xl' : 'text-lg'
          }`}>
            "{liveCaptions}"
          </p>
          <div className="flex items-center justify-center space-x-2">
            <button
              type="button"
              onClick={handleRepeatQuestion}
              className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition"
            >
              <Volume2 className="w-3.5 h-3.5 text-emerald-700" />
              <span>Hear Question Again</span>
            </button>
            <button
              type="button"
              onClick={handleResetSession}
              title="Reset questionnaire and start fresh from Question 1"
              className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium text-slate-500 hover:text-slate-800 bg-slate-50 hover:bg-slate-100 border border-slate-200 transition"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
              <span>Start Over (Q1)</span>
            </button>
          </div>
        </div>

        {/* Gemini Live Adapter Status Notice */}
        {liveNotice && (
          <div className="p-2.5 bg-blue-50 border border-blue-200 rounded-xl text-blue-900 text-xs flex items-center justify-between text-left">
            <div className="flex items-center space-x-1.5">
              <Sparkles className="w-4 h-4 text-blue-600 flex-shrink-0" />
              <span className="text-[11px] font-medium">{liveNotice}</span>
            </div>
            <button onClick={() => setLiveNotice(null)} className="text-blue-400 hover:text-blue-700 ml-2">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Microphone Notice / Insecure Origin Alert */}
        {micNotice && (
          <div className="p-3 bg-amber-50 border border-amber-300 rounded-xl text-amber-900 text-xs flex items-start space-x-2 text-left">
            <AlertOctagon className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold">{micNotice}</p>
              <p className="text-[11px] text-amber-700 mt-0.5">Tip: On mobile, use HTTPS or tap any quick-response option below.</p>
            </div>
            <button onClick={() => setMicNotice(null)} className="text-amber-500 hover:text-amber-800">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Quick-Response Chips (One-Tap Options for Fast & Accurate Entry) */}
        {chips.length > 0 && (
          <div className="pt-1 text-left space-y-1.5">
            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              Quick One-Tap Options:
            </p>
            <div className="flex flex-wrap gap-2">
              {chips.map((chip, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSelectChip(chip.value)}
                  className={`px-3 py-2 rounded-xl text-xs font-semibold transition border ${
                    (draftAnswer === chip.value || (draftAnswer && draftAnswer.includes(chip.value)))
                      ? 'bg-emerald-700 text-white border-emerald-700 shadow-sm'
                      : 'bg-emerald-50/70 hover:bg-emerald-100 text-emerald-900 border-emerald-200'
                  }`}
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Always-Accessible Input & Speech Area */}
        <div className="space-y-3 pt-2 text-left">
          {/* Active Listening Indicator */}
          {isMicActive && (
            <div className="flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs font-semibold">
              <div className="flex items-center space-x-2">
                <span className="w-3 h-3 rounded-full bg-red-600 animate-ping flex-shrink-0" />
                <span>
                  Listening in {lang === 'hi' ? 'Hindi (हिन्दी)' : lang === 'mr' ? 'Marathi (मराठी)' : 'English'}... Speak into microphone.
                </span>
              </div>
              <button
                type="button"
                onClick={toggleMic}
                className="px-2.5 py-1 bg-white border border-red-300 rounded-lg text-red-700 hover:bg-red-100 text-[11px] font-bold"
              >
                Pause Mic
              </button>
            </div>
          )}

          {/* Quick Speak Button if mic is off */}
          {!isMicActive && state === 'listening' && (
            <div className="text-center pt-1 pb-1">
              <button
                type="button"
                onClick={toggleMic}
                className="inline-flex items-center space-x-2 px-5 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow transition"
              >
                <Mic className="w-4 h-4" />
                <span>Tap to Speak Your Answer ({lang.toUpperCase()})</span>
              </button>
            </div>
          )}

          <div className="relative flex items-center">
            <input
              type="text"
              value={draftAnswer}
              onChange={(e) => {
                clearAutoAdvance();
                const val = e.target.value;
                draftAnswerRef.current = val;
                setDraftAnswer(val);
                audioManager.setCommittedText(val);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.target.value || draftAnswerRef.current).trim()) {
                  handleConfirmAndNext(e.target.value || draftAnswerRef.current);
                }
              }}
              placeholder={`Speak or type answer in ${lang === 'hi' ? 'Hindi / English' : lang === 'mr' ? 'Marathi / English' : 'English'}...`}
              className="w-full px-4 py-3.5 pr-24 rounded-xl border border-slate-300 bg-white text-sm font-medium text-slate-900 focus:border-emerald-600 focus:outline-none shadow-sm"
            />
            <div className="absolute right-2 flex items-center space-x-1.5">
              <button
                type="button"
                onClick={toggleMic}
                title={isMicActive ? "Pause Microphone" : "Start Speaking"}
                className={`p-2 rounded-lg font-bold text-xs flex items-center space-x-1 transition ${
                  isMicActive ? 'bg-red-600 text-white animate-pulse' : 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                }`}
              >
                {isMicActive ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Automatic Progression Indicator */}
          {autoAdvanceCountdown !== null && (
            <div className="flex items-center justify-between p-2.5 bg-emerald-100/90 border border-emerald-300 rounded-xl text-emerald-950 text-xs font-semibold animate-pulse shadow-sm">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-emerald-700 flex-shrink-0" />
                <span>Auto-advancing in {autoAdvanceCountdown}s... (no need to press button)</span>
              </div>
              <button
                type="button"
                onClick={() => clearAutoAdvance()}
                className="px-2 py-0.5 bg-white border border-emerald-300 rounded-md text-[11px] text-emerald-800 hover:bg-emerald-50 font-bold"
              >
                Pause
              </button>
            </div>
          )}

          {/* Understood Echo & Confirmation (Large Touch Buttons as requested in brief) */}
          {draftAnswer && (
            <div className="p-3.5 bg-emerald-50 rounded-xl border border-emerald-300 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800 flex items-center space-x-1">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Assistant Understood:</span>
                </span>
                {autoAdvanceCountdown !== null ? (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-extrabold bg-emerald-700 text-white animate-pulse shadow-sm">
                    <span>⚡ Auto-advancing in {autoAdvanceCountdown}s</span>
                  </span>
                ) : (
                  <span className="text-[10px] text-emerald-700 font-medium">Verify or Edit</span>
                )}
              </div>
              <p className="text-sm font-bold text-emerald-950">
                "{draftAnswer}"
              </p>
              <div className="pt-1 flex items-center space-x-3">
                <button
                  onClick={() => handleConfirmAndNext(draftAnswer)}
                  disabled={loading || isSubmittingRef.current}
                  className="flex-1 bg-emerald-700 hover:bg-emerald-800 text-white font-bold py-3 px-4 rounded-xl shadow flex items-center justify-center space-x-2 min-h-touch text-sm transition"
                >
                  <Check className="w-5 h-5" />
                  <span>{autoAdvanceCountdown !== null ? `Send Immediately (${autoAdvanceCountdown}s)` : 'Yes, Confirm & Next'}</span>
                </button>
                <button
                  onClick={() => {
                    clearAutoAdvance();
                    draftAnswerRef.current = '';
                    setDraftAnswer('');
                    audioManager.clearTranscript();
                    startListeningTurn();
                  }}
                  className="px-4 py-3 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 font-semibold rounded-xl text-xs min-h-touch"
                >
                  <X className="w-4 h-4 inline mr-1" />
                  <span>Clear</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Audio / Interrupt Button */}
        {state === 'speaking' && (
          <div className="pt-1">
            <button
              onClick={handleBargeIn}
              className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-full shadow transition inline-flex items-center space-x-2 text-xs"
            >
              <VolumeX className="w-4 h-4" />
              <span>Interrupt & Speak</span>
            </button>
          </div>
        )}
      </div>

      {/* Bottom Auxiliary Controls: Always Visible Skip & Finish Options */}
      <div className="flex items-center justify-between pt-1">
        <button
          type="button"
          onClick={() => {
            audioManager.stopSpeaking();
            liveAudioClient.stopAudioPlayback();
            audioManager.stopListening();
            liveAudioClient.stopAudioCapture();
            setState('finished');
            onInterviewFinished();
          }}
          className="px-3.5 py-2 bg-emerald-50 hover:bg-emerald-100 rounded-xl border border-emerald-200 text-emerald-800 font-semibold text-xs flex items-center space-x-1.5 min-h-touch shadow-sm transition"
        >
          <Check className="w-3.5 h-3.5 text-emerald-600" />
          <span>Finish & View Summary</span>
        </button>

        <button
          type="button"
          onClick={handleSkipQuestion}
          className="px-4 py-2 bg-white rounded-xl border border-slate-200 hover:border-slate-300 text-slate-600 font-medium text-xs flex items-center space-x-1.5 min-h-touch shadow-sm transition"
        >
          <FastForward className="w-4 h-4 text-slate-400" />
          <span>Skip Question</span>
        </button>
      </div>
    </div>
  );
}
