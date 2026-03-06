import { create } from 'zustand';
import type { AnalyzeResponse, StepStatus } from '@/types/api';

type AnalysisState = 'idle' | 'uploading' | 'analyzing' | 'completed' | 'error';

interface AppState {
  analysisState: AnalysisState;
  uploadedFile: File | null;
  analysisResult: AnalyzeResponse | null;
  previousResult: AnalyzeResponse | null;
  liveSteps: StepStatus[];
  error: string | null;
  analysisStartTime: number | null;
  elapsedSeconds: number | null;
  reportSection: string;

  setAnalysisState: (state: AnalysisState) => void;
  setUploadedFile: (file: File | null) => void;
  setAnalysisResult: (result: AnalyzeResponse | null) => void;
  setPreviousResult: (result: AnalyzeResponse | null) => void;
  addOrUpdateLiveStep: (step: StepStatus) => void;
  clearLiveSteps: () => void;
  setError: (error: string | null) => void;
  setReportSection: (section: string) => void;
  reset: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  analysisState: 'idle',
  uploadedFile: null,
  analysisResult: null,
  previousResult: null,
  liveSteps: [],
  error: null,
  analysisStartTime: null,
  elapsedSeconds: null,
  reportSection: 'policy',

  setAnalysisState: (state) => {
    if (state === 'analyzing') {
      set({ analysisState: state, analysisStartTime: Date.now(), elapsedSeconds: null });
    } else if (state === 'completed' || state === 'error') {
      const start = get().analysisStartTime;
      const elapsed = start ? Math.round((Date.now() - start) / 1000) : null;
      set({ analysisState: state, elapsedSeconds: elapsed });
    } else {
      set({ analysisState: state });
    }
  },
  setUploadedFile: (file) => set({ uploadedFile: file }),
  setAnalysisResult: (result) => set({ analysisResult: result }),
  setPreviousResult: (result) => set({ previousResult: result }),
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
  setReportSection: (section) => set({ reportSection: section }),
  reset: () =>
    set({
      analysisState: 'idle',
      uploadedFile: null,
      analysisResult: null,
      previousResult: null,
      liveSteps: [],
      error: null,
      analysisStartTime: null,
      elapsedSeconds: null,
      reportSection: 'policy',
    }),
}));
