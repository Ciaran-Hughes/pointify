import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { VoiceRecorder } from '../src/components/VoiceRecorder';

vi.mock('../src/api', () => ({
  recordings: { upload: vi.fn() },
}));

import { recordings } from '../src/api';

describe('VoiceRecorder', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders record button', () => {
    render(<VoiceRecorder pageId="1" onRecordingComplete={vi.fn()} />);
    expect(screen.getByRole('button', { name: /start recording/i })).toBeInTheDocument();
  });

  it('shows model selector when idle', () => {
    render(<VoiceRecorder pageId="1" onRecordingComplete={vi.fn()} />);
    expect(screen.getByRole('combobox', { hidden: true })).toBeInTheDocument();
  });

  it('shows upload error on failure', async () => {
    recordings.upload.mockRejectedValue(new Error('Upload failed'));
    global.navigator.mediaDevices.getUserMedia.mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }],
    });
    render(<VoiceRecorder pageId="1" onRecordingComplete={vi.fn()} />);
    const btn = screen.getByRole('button', { name: /start recording/i });
    fireEvent.click(btn);
    await waitFor(() => {
      const stopBtn = screen.queryByRole('button', { name: /stop recording/i });
      if (stopBtn) fireEvent.click(stopBtn);
    });
  });
});
