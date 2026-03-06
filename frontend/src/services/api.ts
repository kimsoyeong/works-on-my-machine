import axios from 'axios';
import type { AnalyzeResponse, StepStatus, SSEEvent } from '@/types/api';

const API_BASE = '/api/v1';

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const analyzeFile = async (
  file: File,
): Promise<AnalyzeResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post<AnalyzeResponse>('/analyze', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return data;
};

export const analyzeFileStream = async (
  file: File,
  onStep: (step: StepStatus) => void,
  onResult: (result: AnalyzeResponse) => void,
  onError: (message: string) => void,
): Promise<void> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/analyze/stream`, { method: 'POST', body: formData });
  if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';

    for (const event of events) {
      const dataLine = event.split('\n').find((l) => l.startsWith('data: '));
      if (!dataLine) continue;
      try {
        const parsed: SSEEvent = JSON.parse(dataLine.slice(6));
        if (parsed.type === 'step') onStep(parsed.data);
        else if (parsed.type === 'result') onResult(parsed.data);
        else if (parsed.type === 'error') onError(parsed.data.message);
      } catch {
        // ignore malformed events
      }
    }
  }
};
