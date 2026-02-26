import { create } from 'zustand';
import type { AnalyzeResponse } from '@/types/api';

type AnalysisState = 'idle' | 'uploading' | 'analyzing' | 'completed' | 'error';

interface AppState {
  // Analysis state
  analysisState: AnalysisState;
  uploadedFile: File | null;
  skipPolicy: boolean;
  analysisResult: AnalyzeResponse | null;
  error: string | null;

  // Actions
  setAnalysisState: (state: AnalysisState) => void;
  setUploadedFile: (file: File | null) => void;
  setSkipPolicy: (skip: boolean) => void;
  setAnalysisResult: (result: AnalyzeResponse | null) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  analysisState: 'idle',
  uploadedFile: null,
  skipPolicy: false,
  analysisResult: null,
  error: null,

  // Actions
  setAnalysisState: (state) => set({ analysisState: state }),
  setUploadedFile: (file) => set({ uploadedFile: file }),
  setSkipPolicy: (skip) => set({ skipPolicy: skip }),
  setAnalysisResult: (result) => set({ analysisResult: result }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      analysisState: 'idle',
      uploadedFile: null,
      analysisResult: null,
      error: null,
    }),
}));
