// Browser-native transcription. Audio is never posted to our backend.
export function setupSpeech({ input, onChange, onListening }) {
  const button = document.querySelector('#speech-toggle');
  const status = document.querySelector('#speech-status');
  const interim = document.querySelector('#speech-interim');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const supported = Boolean(Recognition && window.isSecureContext);
  let listening = false;
  let locked = false;
  let base = '';
  let hadError = false;
  let recognition;

  if (!supported) {
    button.disabled = true;
    status.textContent = window.isSecureContext
      ? 'Speech isn’t supported here. Try Chrome, or type below.'
      : 'Speech requires HTTPS or localhost. You can still type.';
  } else {
    recognition = new Recognition();
    recognition.lang = 'en-US';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = event => {
      let final = '';
      let partial = '';
      for (const result of Array.from(event.results)) {
        if (result.isFinal) final += result[0].transcript + ' ';
        else partial += result[0].transcript;
      }
      input.value = [base, final.trim()].filter(Boolean).join(' ').slice(0, input.maxLength);
      interim.textContent = partial;
      interim.hidden = !partial;
      onChange();
    };
    recognition.onerror = event => {
      hadError = true;
      const errors = {
        'not-allowed': 'Microphone permission was denied. Allow it in your browser, or type.',
        'service-not-allowed': 'Speech service is unavailable in this browser. Please type.',
        'audio-capture': 'No microphone is available. Please type instead.',
        'no-speech': 'No speech detected. Try again, or type your issue.',
        'network': 'Speech service connection failed. Your existing text is safe.',
      };
      status.textContent = errors[event.error] || 'Recording stopped. You can retry or keep typing.';
      finish();
    };
    recognition.onend = finish;
  }

  function finish() {
    listening = false;
    input.readOnly = false;
    interim.hidden = true;
    button.setAttribute('aria-pressed', 'false');
    button.querySelector('span').textContent = 'Dictate your issue';
    button.disabled = !supported || locked;
    if (!hadError) status.textContent = 'Review names, account numbers, and amounts before sending.';
    onListening(false);
  }

  button.addEventListener('click', () => {
    if (listening) {
      status.textContent = 'Finishing transcription…';
      recognition.stop();
      return;
    }
    base = input.value.trim();
    hadError = false;
    try {
      recognition.start();
      listening = true;
      input.readOnly = true;
      button.setAttribute('aria-pressed', 'true');
      button.querySelector('span').textContent = 'Stop recording';
      status.textContent = 'Listening… speak your billing issue.';
      onListening(true);
    } catch {
      hadError = true;
      status.textContent = 'Could not start the microphone. Please retry or type.';
      finish();
    }
  });
  window.addEventListener('pagehide', () => recognition?.abort());
  return { setDisabled(value) { locked = value; button.disabled = !supported || locked; } };
}
