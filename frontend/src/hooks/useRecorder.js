import { useCallback, useEffect, useRef, useState } from 'react';

const MAX_MINUTES = 5;
const MAX_MS = MAX_MINUTES * 60 * 1000;

export function useRecorder() {
  const [state, setState] = useState('idle'); // idle | recording | processing
  const [elapsed, setElapsed] = useState(0); // seconds
  const [error, setError] = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const intervalRef = useRef(null);
  const startTimeRef = useRef(null);
  const autoStopRef = useRef(null);
  const streamRef = useRef(null);

  const cleanup = useCallback(() => {
    clearInterval(intervalRef.current);
    clearTimeout(autoStopRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  const start = useCallback(async () => {
    setError(null);
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.start(500); // collect chunks every 500ms
      startTimeRef.current = Date.now();
      setState('recording');
      setElapsed(0);

      intervalRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);

      // Auto-stop at 5 minutes
      autoStopRef.current = setTimeout(() => {
        stop();
      }, MAX_MS);
    } catch (err) {
      setError(err.message || 'Microphone access denied');
      cleanup();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const stop = useCallback(() => {
    return new Promise((resolve) => {
      const mr = mediaRecorderRef.current;
      if (!mr || mr.state === 'inactive') {
        resolve(null);
        return;
      }
      mr.onstop = () => {
        cleanup();
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setState('idle');
        setElapsed(0);
        resolve(blob);
      };
      mr.stop();
    });
  }, [cleanup]);

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return {
    state,
    elapsed,
    formattedTime: formatTime(elapsed),
    maxMinutes: MAX_MINUTES,
    isRecording: state === 'recording',
    error,
    start,
    stop,
    setProcessing: () => setState('processing'),
    setIdle: () => setState('idle'),
  };
}
