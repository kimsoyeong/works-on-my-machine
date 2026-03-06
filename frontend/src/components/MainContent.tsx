import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/store/app';
import { UploadCard } from './UploadCard';
import { PipelineBar } from './PipelineBar';
import { ResultSummary } from './ResultSummary';
import { ResultTabs } from './ResultTabs';
import { analyzeFileStream } from '@/services/api';

const STEP_MESSAGES: Record<string, string> = {
  '파일 업로드': '파일을 업로드하고 있습니다',
  'BiCep 변환': 'BiCep 코드를 변환하고 있습니다',
  'Policy 검증': '보안 정책을 검증하고 있습니다',
  'Recon 분석': '보안 취약점을 분석하고 있습니다',
  '결과 종합': '보고서를 생성하고 있습니다',
  'PreFlight 통합 보고서': '보고서를 생성하고 있습니다',
};

const TOTAL_STEPS = 5;

const ANALYSIS_STEPS = [
  { id: '파일 업로드', label: '아키텍처 업로드', desc: '다이어그램 분석 및 리소스 식별' },
  { id: 'BiCep 변환', label: 'IaC 템플릿 변환', desc: 'Bicep 코드 변환' },
  { id: 'Policy 검증', label: '보안 정책 검증', desc: '사내 보안 정책 위반 검사', parallel: true },
  { id: 'Recon 분석', label: '위협 시나리오 정찰', desc: '모의 환경 기반 취약점 및 위협 경로 탐색', parallel: true },
  { id: '결과 종합', label: '보고서 생성', desc: '통합 보안 리포트 및 개선 Bicep 코드 작성' },
];

function StepIcon({ status, icon }: { status: string; icon?: 'default' | 'upload' | 'code' | 'bot' }) {
  const base: React.CSSProperties = {
    width: '36px', height: '36px', borderRadius: '10px',
    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  };
  if (status === 'completed') return (
    <div style={{ ...base, background: '#f0fdf4', border: '1px solid rgba(22,163,74,0.15)' }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#16A34A" strokeWidth="2" strokeLinecap="round"><path d="M3.5 8.5l3 3 6-6.5"/></svg>
    </div>
  );
  if (status === 'in_progress') return (
    <div style={{ ...base, background: '#f5f3ff', border: '1px solid rgba(108,58,237,0.25)', animation: 'pf-icon-pulse 2.5s ease-in-out infinite' }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#6C3AED" strokeWidth="2" strokeLinecap="round" style={{ animation: 'pf-spin 1s linear infinite' }}><circle cx="8" cy="8" r="5" strokeDasharray="20 12"/></svg>
    </div>
  );
  if (icon === 'upload') return (
    <div style={{ ...base, background: '#f0f0f3', border: '1px solid rgba(0,0,0,0.07)' }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#B8B8C4" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 11V4" />
        <path d="M5 6.5L8 3.5L11 6.5" />
        <path d="M3 13h10" />
      </svg>
    </div>
  );
  if (icon === 'code') return (
    <div style={{ ...base, background: '#f0f0f3', border: '1px solid rgba(0,0,0,0.07)' }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#B8B8C4" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="5.5 4.5 2.5 8 5.5 11.5" />
        <polyline points="10.5 4.5 13.5 8 10.5 11.5" />
        <line x1="9" y1="3" x2="7" y2="13" />
      </svg>
    </div>
  );
  if (icon === 'bot') return (
    <div style={{ ...base, background: '#f0f0f3', border: '1px solid rgba(0,0,0,0.07)' }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#B8B8C4" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
        <line x1="8" y1="1.5" x2="8" y2="3.5" />
        <circle cx="8" cy="1.2" r="0.8" fill="#B8B8C4" stroke="none" />
        <rect x="3" y="3.5" width="10" height="8" rx="2.5" />
        <circle cx="6" cy="7.5" r="1.3" />
        <circle cx="10" cy="7.5" r="1.3" />
        <path d="M6 10h4" />
        <line x1="1.5" y1="7" x2="3" y2="7" />
        <line x1="13" y1="7" x2="14.5" y2="7" />
      </svg>
    </div>
  );
  return (
    <div style={{ ...base, background: '#f0f0f3', border: '1px solid rgba(0,0,0,0.07)' }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#B8B8C4" strokeWidth="1.5" strokeLinecap="round"><rect x="3" y="3" width="10" height="10" rx="2"/><path d="M6 7h4M6 9.5h2.5"/></svg>
    </div>
  );
}

function AnalyzingProgress({ onCancel }: { onCancel: () => void }) {
  const { liveSteps, uploadedFile, analysisStartTime } = useAppStore();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    if (uploadedFile && uploadedFile.type.startsWith('image/')) {
      const url = URL.createObjectURL(uploadedFile);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [uploadedFile]);

  useEffect(() => {
    if (!analysisStartTime) return;
    const tick = () => setElapsed(Math.floor((Date.now() - analysisStartTime) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [analysisStartTime]);

  const getStatus = (stepId: string) => {
    const s = liveSteps.find((l) => l.step === stepId);
    return s?.status || 'pending';
  };

  const completedCount = liveSteps.filter((s) => s.status === 'completed').length;
  const pct = Math.min(Math.round((completedCount / TOTAL_STEPS) * 100), 100);
  const elapsedStr = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;

  const inProgressSteps = liveSteps.filter((s) => s.status === 'in_progress');
  const heroSubtitle = inProgressSteps.length > 0
    ? STEP_MESSAGES[inProgressSteps[0].step] || inProgressSteps[0].step
    : '분석을 준비하고 있습니다';

  // Split steps into sequential and parallel
  const seqBefore = ANALYSIS_STEPS.filter(s => !s.parallel && ['파일 업로드', 'BiCep 변환'].includes(s.id));
  const parallelSteps = ANALYSIS_STEPS.filter(s => s.parallel);
  const seqAfter = ANALYSIS_STEPS.filter(s => !s.parallel && s.id === '결과 종합');

  const stepLabels = ['업로드', 'IaC 변환', '정책 · 시뮬레이션', '보고서'];
  const getProgressDotClass = (i: number) => {
    if (i < completedCount) return 'reached';
    if (i === completedCount) return 'current';
    return '';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      style={{ maxWidth: '720px', margin: '0 auto', padding: '32px 24px 40px' }}
    >
      {/* Hero — Animated radar + title */}
      <div style={{ textAlign: 'center', marginBottom: '36px' }}>
        <div style={{ position: 'relative', width: '80px', height: '80px', margin: '0 auto 16px' }}>
          <div style={{
            position: 'absolute', top: '50%', left: '50%', width: '100px', height: '100px',
            transform: 'translate(-50%, -50%)',
            background: 'radial-gradient(circle, rgba(108,58,237,0.07) 0%, transparent 70%)',
            borderRadius: '50%', pointerEvents: 'none',
          }} />
          <svg width="80" height="80" viewBox="0 0 88 88" fill="none" style={{ display: 'block' }}>
            <g transform="translate(44, 44)">
              <circle cx="0" cy="0" r="40" stroke="rgba(108,58,237,0.15)" strokeWidth="1.5" fill="none"/>
              <circle cx="0" cy="0" r="26" stroke="rgba(108,58,237,0.1)" strokeWidth="1" fill="none"/>
              <circle cx="0" cy="0" r="12" stroke="rgba(108,58,237,0.07)" strokeWidth="1" fill="none"/>
              <circle cx="0" cy="0" r="3" fill="#6C3AED" opacity="0.35"/>
              <g style={{ animation: 'pf-radar-sweep 3s linear infinite', transformOrigin: '0px 0px' }}>
                <line x1="0" y1="0" x2="26" y2="-30" stroke="#6C3AED" strokeWidth="2" strokeLinecap="round" opacity="0.6"/>
              </g>
              <circle cx="16" cy="-18" r="3" fill="#6C3AED">
                <animate attributeName="opacity" values="0.15;0.7;0.15" dur="2s" repeatCount="indefinite"/>
              </circle>
              <circle cx="-12" cy="14" r="2" fill="#6C3AED">
                <animate attributeName="opacity" values="0.1;0.4;0.1" dur="2.5s" repeatCount="indefinite"/>
              </circle>
            </g>
          </svg>
        </div>
        <h2 style={{
          margin: 0, fontSize: '20px', fontWeight: 700,
          color: 'var(--pf-text-1)', fontFamily: "'Outfit', sans-serif",
          letterSpacing: '-0.3px', marginBottom: '6px',
        }}>보안 취약점 스캐닝 중</h2>
        <p style={{
          margin: 0, fontSize: '14px', color: 'var(--pf-text-4)',
          fontFamily: "'DM Sans', sans-serif",
        }}>{heroSubtitle}</p>
      </div>

      {/* Steps timeline */}
      <div style={{ position: 'relative' }}>
        {/* Continuous vertical line */}
        <div style={{
          position: 'absolute', left: '17.5px', top: '18px', bottom: '18px',
          width: '1.5px', background: 'rgba(0,0,0,0.07)', zIndex: 0,
        }} />

      {/* Sequential steps before parallel */}
      {seqBefore.map((step, i) => {
        const status = getStatus(step.id);
        return (
          <div key={step.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '20px', position: 'relative', zIndex: 1 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: '36px' }}>
              <StepIcon status={status} icon={step.id === '파일 업로드' ? 'upload' : 'code'} />
            </div>
            <div style={{ flex: 1, paddingTop: '6px', paddingBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--pf-text-1)', fontFamily: "'DM Sans', sans-serif" }}>{step.label}</span>
                {status === 'completed' && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '100px', background: 'rgba(22,163,74,0.08)', color: '#16A34A' }}>완료</span>}
                {status === 'in_progress' && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '100px', background: 'rgba(108,58,237,0.08)', color: '#6C3AED' }}>진행 중</span>}
              </div>
              <p style={{ fontSize: '12px', color: 'var(--pf-text-4)', fontFamily: "'DM Sans', sans-serif", lineHeight: 1.6, marginTop: '2px' }}>{step.desc}</p>
              {/* Collapsible upload preview for first step */}
              {step.id === '파일 업로드' && status === 'completed' && previewUrl && (
                <>
                  <button onClick={() => setShowPreview(!showPreview)} style={{
                    display: 'inline-flex', alignItems: 'center', gap: '5px', marginTop: '10px',
                    padding: '4px 10px', fontSize: '11px', fontWeight: 600, color: 'var(--pf-text-4)',
                    background: '#f0f0f3', border: '1px solid rgba(0,0,0,0.07)', borderRadius: '8px',
                    cursor: 'pointer', fontFamily: "'DM Sans', sans-serif", transition: 'all 0.2s',
                  }}>
                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: showPreview ? 'rotate(180deg)' : 'none', transition: 'transform 0.3s' }}><path d="M4 6l4 4 4-4"/></svg>
                    {showPreview ? '접기' : '업로드 이미지 보기'}
                  </button>
                  {showPreview && (
                    <div style={{ marginTop: '12px', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(0,0,0,0.07)', background: 'white' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', borderBottom: '1px solid rgba(0,0,0,0.07)', background: '#f0f0f3' }}>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--pf-text-4)', fontFamily: "'DM Sans', sans-serif" }}>{uploadedFile?.name}</span>
                        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', color: 'var(--pf-text-5)' }}>{uploadedFile ? `${(uploadedFile.size / (1024 * 1024)).toFixed(1)} MB` : ''}</span>
                      </div>
                      <div style={{ padding: '12px' }}>
                        <img src={previewUrl} alt="아키텍처" style={{ width: '100%', display: 'block', maxHeight: '220px', objectFit: 'contain', borderRadius: '8px' }} />
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        );
      })}

      {/* Parallel group — wrapped in outer box */}
      {(() => {
        const anyActive = parallelSteps.some(s => getStatus(s.id) === 'in_progress');
        const allDone = parallelSteps.every(s => getStatus(s.id) === 'completed');
        return (
          <div style={{
            border: `1px solid ${anyActive ? 'rgba(108,58,237,0.15)' : 'rgba(0,0,0,0.06)'}`,
            borderRadius: '14px',
            position: 'relative', zIndex: 1,
            padding: '14px 20px 20px',
            background: anyActive ? '#faf8ff' : '#fafafa',
            transition: 'all 0.3s',
          }}>
            {/* Group label */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px',
              fontSize: '11px', fontWeight: 600, color: 'var(--pf-text-5)',
              fontFamily: "'DM Sans', sans-serif", textTransform: 'uppercase' as const, letterSpacing: '0.04em',
            }}>
              <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M8 2v4M8 10v4M2 8h4M10 8h4" />
              </svg>
              병렬 실행
              {allDone && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', fontWeight: 600, padding: '1px 6px', borderRadius: '100px', background: 'rgba(22,163,74,0.08)', color: '#16A34A', letterSpacing: 0, textTransform: 'none' as const }}>완료</span>}
            </div>
            {/* Parallel cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              {parallelSteps.map((step) => {
                const status = getStatus(step.id);
                const isActive = status === 'in_progress';
                return (
                  <div key={step.id} style={{
                    background: 'white', border: `1px solid ${isActive ? 'rgba(108,58,237,0.25)' : 'rgba(0,0,0,0.07)'}`,
                    borderRadius: '12px', padding: '16px',
                    boxShadow: isActive ? '0 0 0 3px rgba(108,58,237,0.06)' : 'none',
                    transition: 'all 0.3s',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                      <StepIcon status={status} icon="bot" />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--pf-text-1)', fontFamily: "'DM Sans', sans-serif" }}>{step.label}</span>
                      {status === 'completed' && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '100px', background: 'rgba(22,163,74,0.08)', color: '#16A34A', marginLeft: 'auto' }}>완료</span>}
                      {status === 'in_progress' && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '100px', background: 'rgba(108,58,237,0.08)', color: '#6C3AED', marginLeft: 'auto' }}>진행 중</span>}
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--pf-text-4)', fontFamily: "'DM Sans', sans-serif", lineHeight: 1.5 }}>{step.desc}</p>
                    {isActive && (
                      <div style={{ marginTop: '14px', width: '100%', height: '4px', background: '#f0f0f3', borderRadius: '100px', overflow: 'hidden' }}>
                        <div style={{ width: '40%', height: '100%', borderRadius: '100px', background: 'linear-gradient(90deg, #6C3AED, #8B5CF6)', animation: 'pf-indeterminate 1.8s ease-in-out infinite' }} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* Final step — Report */}
      {seqAfter.map((step) => {
        const status = getStatus(step.id);
        return (
          <div key={step.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '20px', position: 'relative', zIndex: 1, marginTop: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: '36px' }}>
              <StepIcon status={status} />
            </div>
            <div style={{ flex: 1, paddingTop: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '14px', fontWeight: 600, color: status === 'pending' ? 'var(--pf-text-5)' : 'var(--pf-text-1)', fontFamily: "'DM Sans', sans-serif" }}>{step.label}</span>
                {status === 'completed' && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '100px', background: 'rgba(22,163,74,0.08)', color: '#16A34A' }}>완료</span>}
                {status === 'in_progress' && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '100px', background: 'rgba(108,58,237,0.08)', color: '#6C3AED' }}>진행 중</span>}
              </div>
              <p style={{ fontSize: '12px', color: status === 'pending' ? 'var(--pf-text-5)' : 'var(--pf-text-4)', fontFamily: "'DM Sans', sans-serif", lineHeight: 1.6, marginTop: '2px' }}>{step.desc}</p>
            </div>
          </div>
        );
      })}
      </div>{/* end timeline wrapper */}

      {/* Progress section */}
      <div style={{ marginTop: '40px', paddingTop: '28px', borderTop: '1px solid rgba(0,0,0,0.07)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <span style={{ fontSize: '12px', color: 'var(--pf-text-4)', fontWeight: 500, fontFamily: "'DM Sans', sans-serif" }}>전체 진행률</span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '13px', fontWeight: 600, color: '#6C3AED' }}>{pct}%</span>
        </div>
        <div style={{ width: '100%', height: '6px', background: '#f0f0f3', borderRadius: '100px', overflow: 'hidden' }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            style={{ height: '100%', borderRadius: '100px', background: 'linear-gradient(90deg, #6C3AED, #8B5CF6)', position: 'relative' }}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '10px' }}>
          {stepLabels.map((label, i) => (
            <span key={label} style={{
              fontSize: '10px', fontWeight: getProgressDotClass(i) === 'current' ? 600 : 500,
              color: getProgressDotClass(i) === 'current' ? '#6C3AED' : getProgressDotClass(i) === 'reached' ? 'var(--pf-text-4)' : 'var(--pf-text-5)',
              fontFamily: "'DM Sans', sans-serif",
            }}>{label}</span>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes pf-radar-sweep { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes pf-icon-pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(108,58,237,0.2); } 50% { box-shadow: 0 0 0 6px rgba(108,58,237,0); } }
        @keyframes pf-indeterminate { 0% { transform: translateX(-100%); } 100% { transform: translateX(300%); } }
      `}</style>
    </motion.div>
  );
}


export function MainContent() {
  const [mounted, setMounted] = useState(false);

  const {
    analysisState,
    uploadedFile,
    setAnalysisState,
    setAnalysisResult,
    setError,
    addOrUpdateLiveStep,
    clearLiveSteps,
  } = useAppStore();

  useEffect(() => { setMounted(true); }, []);

  const handleAnalyze = async () => {
    if (!uploadedFile) return;
    clearLiveSteps();
    setAnalysisState('analyzing');
    setError(null);
    try {
      await analyzeFileStream(
        uploadedFile,
        (step) => addOrUpdateLiveStep(step),
        (result) => {
          if (result.status === 'success') {
            setAnalysisResult(result);
            setAnalysisState('completed');
          } else {
            setError(result.error ?? 'Analysis failed');
            setAnalysisState('error');
          }
        },
        (message) => { setError(message); setAnalysisState('error'); },
      );
    } catch (error) {
      console.error('Analysis error:', error);
      setError(error instanceof Error ? error.message : 'Network error');
      setAnalysisState('error');
    }
  };

  const isCompleted = analysisState === 'completed';
  const isAnalyzing = analysisState === 'analyzing';

  return (
    <div style={{ paddingTop: '60px' }}>
      {/* Results */}
      <AnimatePresence>
        {isCompleted && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 24px' }}
          >
            {/* Pipeline Bar — rounded card */}
            <div style={{
              padding: '16px 24px', borderRadius: '14px', marginBottom: '28px',
              background: '#ffffff',
              border: '1px solid rgba(0,0,0,0.06)',
            }}>
              <PipelineBar />
            </div>

            <ResultSummary />
            <div style={{ marginTop: '32px' }}><ResultTabs /></div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Analyzing: Progress Section */}
      <AnimatePresence>
        {isAnalyzing && (
          <AnalyzingProgress onCancel={() => { setAnalysisState('idle'); clearLiveSteps(); setError(null); }} />
        )}
      </AnimatePresence>

      {/* Upload / Hero (idle or error only) */}
      {!isCompleted && !isAnalyzing && (
        <div style={{
          maxWidth: '620px', margin: '0 auto', padding: '0 24px',
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          minHeight: 'calc(100vh - 60px)', justifyContent: 'center',
          paddingBottom: '120px',
        }}>
          {/* Hero — centered, Claude style */}
          <div style={{
            textAlign: 'center',
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(12px)',
            transition: 'all 0.7s cubic-bezier(0.4, 0, 0.2, 1) 0.1s',
            marginBottom: '20px',
          }}>
            {/* Top label — "Free plan · Upgrade" equivalent */}
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '4px 10px', borderRadius: '6px',
              background: 'rgba(108, 58, 237, 0.08)',
              border: '1px solid rgba(108, 58, 237, 0.18)',
              marginBottom: '20px',
            }}>
              <span style={{
                fontSize: '11.5px', color: 'var(--pf-text-5)',
                fontFamily: "'DM Sans', sans-serif", letterSpacing: '0.01em',
              }}>
                보안 정책 점검 · 취약점 탐지 · 위협 시뮬레이션
              </span>
            </div>

            {/* Logo + Title — same line */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              gap: '14px',
            }}>
              <svg width="42" height="42" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0 }}>
                <g transform="translate(36, 36)">
                  <circle cx="0" cy="0" r="32" stroke="#6C3AED" strokeWidth="2.5" fill="rgba(108,58,237,0.06)"/>
                  <circle cx="0" cy="0" r="20" stroke="#6C3AED" strokeWidth="1.5" fill="none" opacity="0.25"/>
                  <circle cx="0" cy="0" r="9" stroke="#6C3AED" strokeWidth="1.5" fill="none" opacity="0.15"/>
                  <circle cx="0" cy="0" r="2.5" fill="#6C3AED" opacity="0.4"/>
                  <line x1="0" y1="0" x2="20" y2="-24" stroke="#6C3AED" strokeWidth="2.5" strokeLinecap="round"/>
                  <circle cx="13" cy="-15" r="3.5" fill="#6C3AED"/>
                  <circle cx="-10" cy="12" r="2" fill="#6C3AED" opacity="0.35"/>
                </g>
              </svg>
              <h1 style={{
                margin: 0, fontSize: '36px', fontWeight: 700,
                color: 'var(--pf-text-1)', fontFamily: "'Outfit', sans-serif",
                lineHeight: 1.2, letterSpacing: '-0.03em',
              }}>
                아키텍처 보안 검증
              </h1>
            </div>

            {/* Description */}
            <p style={{
              margin: '14px auto 0', fontSize: '14px', color: 'var(--pf-text-4)',
              fontFamily: "'DM Sans', sans-serif", lineHeight: 1.7, maxWidth: '480px',
            }}>
              시스템 아키텍처 설계 단계에서 보안 정책 준수 여부를 검증하고, 목업 컨테이너 환경에서 위협 시나리오 정찰을 수행하여 잠재적 취약점을 사전에 탐색합니다.
            </p>
          </div>

          {/* Upload card + Disclaimer — stacked card style */}
          <div style={{
            width: '100%',
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(16px)',
            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.25s',
          }}>
            {/* Upload card */}
            <div style={{ position: 'relative', zIndex: 1 }}>
              <UploadCard onStartAnalysis={handleAnalyze} />
            </div>

            {/* Disclaimer — overlapping bottom bar */}
            <div style={{
              marginTop: '-12px',
              marginLeft: '12px',
              marginRight: '12px',
              paddingTop: '18px',
              paddingBottom: '6px',
              textAlign: 'center',
              background: 'rgba(0, 0, 0, 0.02)',
              border: '1px solid rgba(0,0,0,0.03)',
              borderTop: 'none',
              borderRadius: '0 0 12px 12px',
              position: 'relative',
              zIndex: 0,
            }}>
              <p style={{
                margin: 0, fontSize: '11.5px', color: 'var(--pf-text-5)',
                fontFamily: "'DM Sans', sans-serif", lineHeight: 1.6,
              }}>
                실제 침투 테스트를 대체하지 않습니다. 설계 리스크의 조기 발견과
                보안 검토 우선순위 수립에 활용하세요.
              </p>
            </div>
          </div>

          {/* Error */}
          <AnimatePresence>
            {analysisState === 'error' && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{
                  width: '100%', marginTop: '16px', padding: '14px 20px', borderRadius: '12px',
                  background: 'var(--pf-error-bg)',
                  border: '1px solid var(--pf-error-border)',
                  display: 'flex', alignItems: 'center', gap: '10px',
                }}
              >
                <span style={{ fontSize: '16px' }}>❌</span>
                <p style={{
                  margin: 0, fontSize: '13px', color: 'var(--pf-error-text)',
                  fontFamily: "'DM Sans', sans-serif",
                }}>
                  {useAppStore.getState().error || '분석 중 오류가 발생했습니다'}
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
