import { create } from 'zustand';
import type { AnalyzeResponse, StepStatus } from '@/types/api';

type AnalysisState = 'idle' | 'uploading' | 'analyzing' | 'completed' | 'error';
type Theme = 'dark' | 'light';

const getInitialTheme = (): Theme => {
  if (typeof window !== 'undefined') {
    return (localStorage.getItem('pf-theme') as Theme) || 'dark';
  }
  return 'dark';
};

const applyTheme = (theme: Theme) => {
  document.documentElement.classList.remove('dark', 'light');
  document.documentElement.classList.add(theme);
  localStorage.setItem('pf-theme', theme);
};

interface AppState {
  theme: Theme;
  toggleTheme: () => void;

  analysisState: AnalysisState;
  uploadedFile: File | null;
  skipPolicy: boolean;
  analysisResult: AnalyzeResponse | null;
  liveSteps: StepStatus[];
  error: string | null;

  setAnalysisState: (state: AnalysisState) => void;
  setUploadedFile: (file: File | null) => void;
  setSkipPolicy: (skip: boolean) => void;
  setAnalysisResult: (result: AnalyzeResponse | null) => void;
  addOrUpdateLiveStep: (step: StepStatus) => void;
  clearLiveSteps: () => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialTheme = getInitialTheme();
applyTheme(initialTheme);

export const useAppStore = create<AppState>((set, get) => ({
  theme: initialTheme,
  toggleTheme: () => {
    const next = get().theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    set({ theme: next });
  },

  analysisState: 'idle',
  uploadedFile: null,
  skipPolicy: false,
  analysisResult: null,
  liveSteps: [],
  error: null,

  setAnalysisState: (state) => set({ analysisState: state }),
  setUploadedFile: (file) => set({ uploadedFile: file }),
  setSkipPolicy: (skip) => set({ skipPolicy: skip }),
  setAnalysisResult: (result) => set({ analysisResult: result }),
  addOrUpdateLiveStep: (step) =>
    set((state) => {
      const idx = state.liveSteps.findIndex((s) => s.step === step.step);
      if (idx >= 0) {
        const updated = [...state.liveSteps];
        updated[idx] = step;
        return { liveSteps: updated };
      }
      return { liveSteps: [...state.liveSteps, step] };
    }),
  clearLiveSteps: () => set({ liveSteps: [] }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      analysisState: 'idle',
      uploadedFile: null,
      analysisResult: null,
      liveSteps: [],
      error: null,
    }),
}));
