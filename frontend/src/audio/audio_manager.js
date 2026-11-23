export class AudioManager {
  constructor() {
    this.synth = typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null;
    this.recognition = null;
    this.wakeLock = null;
    this.speechRate = 1.0;
    this.isListening = false;
    this.activeUtterance = null;
    this.activeLanguage = 'en';
    this.committedText = ''; // Accumulates speech across pauses and Chrome recognition restarts
    this.setupRecognition();

    // Pre-warm voices eagerly to eliminate cold-start speech synthesis delay
    if (this.synth) {
      try {
        this.synth.getVoices();
        if ('onvoiceschanged' in this.synth) {
          this.synth.onvoiceschanged = () => {
            try { this.synth.getVoices(); } catch (e) {}
          };
        }
      } catch (e) {}
    }
  }

  prewarmAudio() {
    if (this.synth) {
      try {
        this.synth.getVoices();
        this.synth.cancel();
      } catch (e) {}
    }
  }

  isSpeechSupported() {
    if (typeof window === 'undefined') return false;
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  setupRecognition() {
    if (typeof window === 'undefined') return;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      try {
        if (this.recognition) {
          try { this.recognition.abort(); } catch (e) {}
        }
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.maxAlternatives = 1;
      } catch (e) {
        console.warn('SpeechRecognition initialization error:', e);
      }
    }
  }

  setCommittedText(text) {
    this.committedText = (text || '').trim();
  }

  clearTranscript() {
    this.committedText = '';
  }

  async requestWakeLock() {
    if (typeof navigator !== 'undefined' && 'wakeLock' in navigator) {
      try {
        this.wakeLock = await navigator.wakeLock.request('screen');
      } catch (err) {
        console.warn('Wake Lock request skipped:', err);
      }
    }
  }

  releaseWakeLock() {
    if (this.wakeLock) {
      this.wakeLock.release().catch(() => {});
      this.wakeLock = null;
    }
  }

  speak(text, language = 'en', onEnd = null) {
    if (!this.synth) {
      if (onEnd) onEnd();
      return;
    }

    // Barge-in: cancel any active speech first
    this.synth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    this.activeUtterance = utterance; // Prevent Chrome garbage collection bug
    utterance.rate = this.speechRate;
    
    // Select matching language voice if present
    if (language === 'hi') utterance.lang = 'hi-IN';
    else if (language === 'mr') utterance.lang = 'mr-IN';
    else utterance.lang = 'en-IN';

    let ended = false;
    const safeEnd = () => {
      if (!ended) {
        ended = true;
        this.activeUtterance = null;
        if (onEnd) onEnd();
      }
    };

    utterance.onend = () => {
      safeEnd();
    };

    utterance.onerror = (e) => {
      console.warn('Speech synthesis error or interrupt:', e);
      safeEnd();
    };

    // Chrome fallback timeout in case onend never fires
    const timeoutMs = Math.max(3000, Math.min(10000, (text.length / 15) * 1000));
    setTimeout(() => {
      if (!ended && this.synth && !this.synth.speaking) {
        safeEnd();
      }
    }, timeoutMs);

    this.synth.speak(utterance);
  }

  stopSpeaking() {
    if (this.synth) {
      this.synth.cancel();
      this.activeUtterance = null;
    }
  }

  startListening(language = 'en', onResult, onError, onFinal, onStatusChange) {
    this.activeLanguage = language;
    this.isListening = true;

    if (!this.recognition) {
      this.setupRecognition();
    }

    if (!this.recognition) {
      this.isListening = false;
      const msg = 'Speech recognition requires HTTPS or localhost. Quick-tap options and typing are ready below.';
      if (onError) onError(msg);
      if (onStatusChange) onStatusChange('unsupported');
      return;
    }

    // Assign appropriate BCP-47 language tag
    if (language === 'hi') this.recognition.lang = 'hi-IN';
    else if (language === 'mr') this.recognition.lang = 'mr-IN';
    else this.recognition.lang = 'en-IN';

    let sessionFinal = '';

    // Accumulate all phrases across pauses and restarts
    this.recognition.onresult = (event) => {
      sessionFinal = '';
      let sessionInterim = '';

      for (let i = 0; i < event.results.length; ++i) {
        const res = event.results[i];
        if (res.isFinal) {
          sessionFinal += res[0].transcript + ' ';
        } else {
          sessionInterim += res[0].transcript;
        }
      }

      // Combine already committed text from earlier pauses + current session final + interim
      const fullText = [this.committedText, sessionFinal, sessionInterim]
        .filter(Boolean)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();

      if (onResult) {
        onResult(sessionInterim.trim(), sessionFinal.trim(), fullText);
      }
      if (fullText && onFinal) {
        onFinal(fullText);
      }
    };

    this.recognition.onerror = (err) => {
      const errCode = err?.error || '';
      console.warn('Speech recognition event error:', errCode, err);

      // In case of language pack missing on some OS builds (e.g. Marathi), fallback to Hindi
      if (errCode === 'language-not-supported' && this.recognition.lang === 'mr-IN') {
        console.warn('mr-IN not supported in browser, falling back to hi-IN');
        this.recognition.lang = 'hi-IN';
        try { this.recognition.start(); return; } catch (e) {}
      }

      // Normal pauses, silence, and internal aborts: do not treat as fatal error
      if (errCode === 'no-speech' || errCode === 'aborted') {
        if (onStatusChange && this.isListening) onStatusChange('listening');
        return;
      }

      // Audio capture device busy: retry smoothly after brief pause
      if (errCode === 'audio-capture') {
        console.warn('Audio device momentarily busy, scheduling restart...');
        setTimeout(() => {
          if (this.isListening && this.recognition) {
            try { this.recognition.start(); } catch (e) {}
          }
        }, 250);
        return;
      }

      let friendlyMsg = 'Microphone not available.';
      if (errCode === 'not-allowed') {
        this.isListening = false;
        friendlyMsg = 'Microphone permission denied. Please allow microphone access or tap quick chips below.';
      } else if (errCode === 'network' || errCode === 'service-not-allowed') {
        friendlyMsg = 'Speech service temporarily unavailable. Use quick chips or type below.';
      }

      if (onError) onError(friendlyMsg);
      if (onStatusChange) onStatusChange('error');
    };

    // Auto-restart if browser stops due to silence while the interview turn is still active
    this.recognition.onend = () => {
      // Commit what was finalized in this session into this.committedText so it survives the restart
      if (sessionFinal && sessionFinal.trim()) {
        this.committedText = [this.committedText, sessionFinal]
          .filter(Boolean)
          .join(' ')
          .replace(/\s+/g, ' ')
          .trim();
        sessionFinal = '';
      }

      if (this.isListening) {
        try {
          this.recognition.start();
          if (onStatusChange) onStatusChange('listening');
        } catch (e) {
          // Re-instantiate if recognition was aborted
          setTimeout(() => {
            if (this.isListening && this.recognition) {
              try {
                this.recognition.start();
                if (onStatusChange) onStatusChange('listening');
              } catch (err2) {
                // If instance needs re-init
                this.setupRecognition();
                if (this.recognition && this.isListening) {
                  try {
                    if (this.activeLanguage === 'hi') this.recognition.lang = 'hi-IN';
                    else if (this.activeLanguage === 'mr') this.recognition.lang = 'mr-IN';
                    else this.recognition.lang = 'en-IN';
                    this.recognition.start();
                    if (onStatusChange) onStatusChange('listening');
                  } catch (err3) {
                    this.isListening = false;
                    if (onStatusChange) onStatusChange('stopped');
                  }
                }
              }
            }
          }, 150);
        }
      } else {
        if (onStatusChange) onStatusChange('stopped');
      }
    };

    try {
      this.recognition.start();
      if (onStatusChange) onStatusChange('listening');
    } catch (err) {
      if (err.name === 'InvalidStateError') {
        // Recognition already running
        if (onStatusChange) onStatusChange('listening');
      } else {
        console.warn('Recognition start exception:', err);
        this.setupRecognition();
        try {
          this.recognition.start();
          if (onStatusChange) onStatusChange('listening');
        } catch (retryErr) {
          this.isListening = false;
          if (onError) onError('Could not start microphone. You can tap quick options below.');
          if (onStatusChange) onStatusChange('error');
        }
      }
    }
  }

  stopListening() {
    this.isListening = false;
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {}
    }
  }
}

export const audioManager = new AudioManager();
