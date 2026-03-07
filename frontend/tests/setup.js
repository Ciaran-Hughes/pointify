import '@testing-library/jest-dom';

// Mock window.matchMedia (not implemented in jsdom)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Mock MediaRecorder for tests
global.MediaRecorder = class {
  constructor() {
    this.state = 'inactive';
    this.ondataavailable = null;
    this.onstop = null;
  }
  start() { this.state = 'recording'; }
  stop() { this.state = 'inactive'; if (this.onstop) this.onstop(); }
  addEventListener() {}
  removeEventListener() {}
};

// Mock getUserMedia
global.navigator.mediaDevices = {
  getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }),
};

// Suppress ResizeObserver errors in tests
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
