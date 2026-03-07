import { MicrophoneIcon, StopIcon } from '@heroicons/react/24/solid';
import { useState } from 'react';
import { recordings as recordingsApi } from '../api';
import { useAuth } from '../hooks/useAuth';
import { useRecorder } from '../hooks/useRecorder';

const WHISPER_MODELS = [
  { value: 'tiny', label: 'Tiny (fastest)' },
  { value: 'base', label: 'Base' },
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium (recommended)' },
  { value: 'large-v3', label: 'Large v3 (best)' },
];

const WHISPER_LANGUAGES = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'fi', label: 'Finnish' },
  { value: 'sv', label: 'Swedish' },
  { value: 'no', label: 'Norwegian' },
  { value: 'da', label: 'Danish' },
  { value: 'de', label: 'German' },
  { value: 'fr', label: 'French' },
  { value: 'es', label: 'Spanish' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'nl', label: 'Dutch' },
  { value: 'pl', label: 'Polish' },
  { value: 'ru', label: 'Russian' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ko', label: 'Korean' },
  { value: 'ar', label: 'Arabic' },
];

export function VoiceRecorder({ pageId, onRecordingComplete }) {
  const { user } = useAuth();
  const recorder = useRecorder();
  const [model, setModel] = useState('medium');
  const [language, setLanguage] = useState(user?.whisper_language ?? 'en');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const handleToggle = async () => {
    if (recorder.isRecording) {
      const blob = await recorder.stop();
      if (!blob || blob.size === 0) return;
      setUploading(true);
      setUploadError('');
      recorder.setProcessing();
      try {
        const result = await recordingsApi.upload(pageId, blob, model, language);
        onRecordingComplete(result);
      } catch (err) {
        setUploadError(err.message || 'Upload failed');
      } finally {
        setUploading(false);
        recorder.setIdle();
      }
    } else {
      await recorder.start();
    }
  };

  const pct = Math.min((recorder.elapsed / (recorder.maxMinutes * 60)) * 100, 100);

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-4 shadow-sm">
      <div className="flex items-center gap-4">
        {/* Record/stop button */}
        <button
          onClick={handleToggle}
          disabled={uploading}
          aria-label={recorder.isRecording ? 'Stop recording' : 'Start recording'}
          className={`w-14 h-14 flex-shrink-0 flex items-center justify-center rounded-full transition-all focus:outline-none focus:ring-2 focus:ring-offset-2
            ${recorder.isRecording
              ? 'bg-red-500 hover:bg-red-600 focus:ring-red-500 animate-pulse'
              : 'bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500'}
            ${uploading ? 'opacity-50 cursor-not-allowed' : ''}
          `}
        >
          {recorder.isRecording
            ? <StopIcon className="w-6 h-6 text-white" aria-hidden="true" />
            : <MicrophoneIcon className="w-6 h-6 text-white" aria-hidden="true" />
          }
        </button>

        <div className="flex-1 min-w-0">
          {/* Status text */}
          <p className="text-sm font-medium text-gray-900 dark:text-white">
            {uploading ? 'Transcribing and processing…' :
             recorder.isRecording ? `Recording ${recorder.formattedTime} / ${recorder.maxMinutes}:00` :
             'Tap to record'}
          </p>

          {/* Model and language selectors (only when idle) */}
          {!recorder.isRecording && !uploading && (
            <div className="mt-1.5 flex flex-wrap gap-2">
              <div>
                <label htmlFor="whisper-model" className="sr-only">Whisper model</label>
                <select
                  id="whisper-model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="text-xs bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1 text-gray-600 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                >
                  {WHISPER_MODELS.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="whisper-language" className="sr-only">Language</label>
                <select
                  id="whisper-language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="text-xs bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1 text-gray-600 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                >
                  {WHISPER_LANGUAGES.map((l) => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Duration progress bar */}
          {recorder.isRecording && (
            <div className="mt-2 h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-red-500 rounded-full transition-all duration-1000"
                style={{ width: `${pct}%` }}
                role="progressbar"
                aria-valuenow={recorder.elapsed}
                aria-valuemax={recorder.maxMinutes * 60}
                aria-label="Recording duration"
              />
            </div>
          )}

          {/* Upload progress */}
          {uploading && (
            <div className="mt-2 h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-500 rounded-full animate-pulse w-full" />
            </div>
          )}
        </div>
      </div>

      {/* Errors */}
      {(recorder.error || uploadError) && (
        <p role="alert" className="mt-2 text-xs text-red-600 dark:text-red-400">
          {recorder.error || uploadError}
        </p>
      )}
    </div>
  );
}
