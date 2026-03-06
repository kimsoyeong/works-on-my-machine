import { Loader2 } from 'lucide-react';
import { useAppStore } from '@/store/app';
import type { StepStatus } from '@/types/api';

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

const getStepStatus = (stepId: string, steps: StepStatus[]): StepStatus['status'] => {
  const stepMap: Record<string, string> = {
    upload: '파일 업로드',
    bicep: 'BiCep 변환',
    policy: 'Policy 검증',
    recon: 'Recon 분석',
    result: '결과 종합',
  };
  const step = steps.find((s) => s.step === stepMap[stepId]);
  return step?.status || 'pending';
};

function PendingIcon({ icon }: { icon?: string }) {
  if (icon === 'upload') return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="#B8B8C4" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 11V4" /><path d="M5 6.5L8 3.5L11 6.5" /><path d="M3 13h10" />
    </svg>
  );
  if (icon === 'code') return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="#B8B8C4" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="5.5 4.5 2.5 8 5.5 11.5" /><polyline points="10.5 4.5 13.5 8 10.5 11.5" /><line x1="9" y1="3" x2="7" y2="13" />
    </svg>
  );
  if (icon === 'bot') return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="#B8B8C4" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="1.5" x2="8" y2="3.5" /><circle cx="8" cy="1.2" r="0.8" fill="#B8B8C4" stroke="none" />
      <rect x="3" y="3.5" width="10" height="8" rx="2.5" /><circle cx="6" cy="7.5" r="1.3" /><circle cx="10" cy="7.5" r="1.3" />
      <path d="M6 10h4" /><line x1="1.5" y1="7" x2="3" y2="7" /><line x1="13" y1="7" x2="14.5" y2="7" />
    </svg>
  );
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="#B8B8C4" strokeWidth="1.5" strokeLinecap="round">
      <rect x="3" y="3" width="10" height="10" rx="2"/><path d="M6 7h4M6 9.5h2.5"/>
    </svg>
  );
}

function StepChip({ label, status, icon }: { label: string; status: string; icon?: string }) {
  const done = status === 'completed';
  const running = status === 'in_progress';

  const bg = done ? '#f0fdf4' : running ? '#f5f3ff' : '#f5f5f7';
  const border = done ? 'rgba(22,163,74,0.2)' : running ? 'rgba(108,58,237,0.25)' : 'rgba(0,0,0,0.08)';
  const labelColor = done ? '#374151' : running ? '#374151' : '#9ca3af';

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: '7px',
      whiteSpace: 'nowrap' as const,
    }}>
      <div style={{
        width: '28px', height: '28px', borderRadius: '8px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: bg, border: `1px solid ${border}`, flexShrink: 0,
      }}>
        {done && (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#16A34A" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3.5 8.5l3 3 6-6.5"/>
          </svg>
        )}
        {running && (
          <Loader2 style={{ width: 14, height: 14, color: '#6C3AED', animation: 'pf-spin 1s linear infinite' }} />
        )}
        {!done && !running && <PendingIcon icon={icon} />}
      </div>
      <span style={{
        fontSize: '13px', fontWeight: 600, color: labelColor,
        fontFamily: "'DM Sans', sans-serif",
      }}>{label}</span>
    </div>
  );
}

function Arrow() {
  return (
    <svg width="40" height="10" viewBox="0 0 40 10" style={{ display: 'block', flexShrink: 0, margin: '0 4px' }}>
      <line x1="0" y1="5" x2="34" y2="5" stroke="#d1d5db" strokeWidth="1.5" />
      <polyline points="30,2 35,5 30,8" fill="none" stroke="#d1d5db" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function PipelineBar() {
  const { analysisResult, liveSteps, analysisState, elapsedSeconds } = useAppStore();
  const steps = (analysisState === 'completed' && analysisResult?.steps?.length)
    ? analysisResult.steps
    : liveSteps;

  const elapsed = elapsedSeconds != null ? formatElapsed(elapsedSeconds) : null;

  // Fork/merge geometry
  const H = 30;   // chip height (icon 28 + 2 border)
  const G = 6;    // gap between parallel chips
  const forkH = H * 2 + G;
  const topY = H / 2;
  const botY = H + G + H / 2;
  const midY = forkH / 2;
  const lc = '#d1d5db';

  return (
    <div style={{ width: '100%', position: 'relative' }}>
      {/* Pipeline — centered */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <StepChip label="업로드" status={getStepStatus('upload', steps)} icon="upload" />
        <Arrow />

        <StepChip label="IaC 변환" status={getStepStatus('bicep', steps)} icon="code" />
        <Arrow />

        {/* Parallel fork / merge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Fork connector */}
          <svg width="16" height={forkH} viewBox={`0 0 16 ${forkH}`} style={{ display: 'block', flexShrink: 0 }}>
            <line x1="0" y1={midY} x2="6" y2={midY} stroke={lc} strokeWidth="1.5" />
            <line x1="6" y1={topY} x2="6" y2={botY} stroke={lc} strokeWidth="1.5" />
            <line x1="6" y1={topY} x2="16" y2={topY} stroke={lc} strokeWidth="1.5" />
            <line x1="6" y1={botY} x2="16" y2={botY} stroke={lc} strokeWidth="1.5" />
          </svg>

          {/* Parallel steps */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: `${G}px` }}>
            <StepChip label="정책 검증" status={getStepStatus('policy', steps)} icon="bot" />
            <StepChip label="위협 정찰" status={getStepStatus('recon', steps)} icon="bot" />
          </div>

          {/* Merge connector */}
          <svg width="16" height={forkH} viewBox={`0 0 16 ${forkH}`} style={{ display: 'block', flexShrink: 0 }}>
            <line x1="0" y1={topY} x2="10" y2={topY} stroke={lc} strokeWidth="1.5" />
            <line x1="0" y1={botY} x2="10" y2={botY} stroke={lc} strokeWidth="1.5" />
            <line x1="10" y1={topY} x2="10" y2={botY} stroke={lc} strokeWidth="1.5" />
            <line x1="10" y1={midY} x2="16" y2={midY} stroke={lc} strokeWidth="1.5" />
          </svg>
        </div>

        <Arrow />
        <StepChip label="보고서 생성" status={getStepStatus('result', steps)} />
      </div>

      {/* Elapsed time — absolute right */}
      {elapsed && (
        <div style={{
          position: 'absolute', right: '0', top: '50%', transform: 'translateY(-50%)',
          display: 'inline-flex', alignItems: 'center', gap: '5px',
          padding: '6px 14px', borderRadius: '8px',
          background: 'rgba(0,0,0,0.03)',
          fontSize: '13px', color: '#94a3b8',
          fontFamily: "'DM Sans', sans-serif",
          whiteSpace: 'nowrap' as const,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span style={{ fontWeight: 600, color: 'var(--pf-text-3)', fontFamily: "'DM Mono', 'JetBrains Mono', monospace" }}>{elapsed}</span>
        </div>
      )}
    </div>
  );
}
