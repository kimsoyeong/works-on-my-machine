import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/store/app';
import { UploadCard } from './UploadCard';
import { PipelineBar } from './PipelineBar';
import { ResultSummary } from './ResultSummary';
import { ResultTabs } from './ResultTabs';
import { analyzeFileStream } from '@/services/api';

const FeaturePill = ({ icon, text }: { icon: string; text: string }) => (
  <div style={{
    display: 'flex', alignItems: 'center', gap: '6px',
    padding: '6px 14px',
    background: 'var(--pf-accent-faint-bg)',
    border: '1px solid var(--pf-accent-faint-border)',
    borderRadius: '100px',
    fontSize: '12px', color: 'var(--pf-accent-text-light)',
    fontFamily: "'DM Sans', sans-serif", letterSpacing: '0.02em',
  }}>
    <span style={{ fontSize: '13px' }}>{icon}</span>
    {text}
  </div>
);

export function MainContent() {
  const [mounted, setMounted] = useState(false);

  const {
    analysisState,
    uploadedFile,
    skipPolicy,
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
        uploadedFile, skipPolicy,
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
      {/* Pipeline Bar */}
      <AnimatePresence>
        {(isAnalyzing || isCompleted) && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            style={{
              borderBottom: '1px solid var(--pf-header-border)',
              background: 'var(--pf-pipeline-bg)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
              <PipelineBar />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      <AnimatePresence>
        {isCompleted && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 24px' }}
          >
            <ResultSummary />
            <div style={{ marginTop: '32px' }}><ResultTabs /></div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Upload / Hero */}
      {!isCompleted && (
        <div style={{ maxWidth: '680px', margin: '0 auto', padding: '0 24px' }}>
          {/* Hero */}
          <div style={{
            paddingTop: '32px', paddingBottom: '20px',
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(12px)',
            transition: 'all 0.7s cubic-bezier(0.4, 0, 0.2, 1) 0.1s',
          }}>
            <div style={{
              display: 'inline-flex', padding: '4px 12px', borderRadius: '6px',
              background: 'var(--pf-badge-bg)',
              border: '1px solid var(--pf-badge-border)',
              fontSize: '11px', color: 'var(--pf-badge-text)',
              fontFamily: "'DM Mono', monospace", marginBottom: '12px', letterSpacing: '0.04em',
            }}>
              SHIFT-LEFT SECURITY
            </div>

            <h1 style={{
              margin: 0, fontSize: '36px', fontWeight: 800,
              color: 'var(--pf-text-1)', fontFamily: "'Outfit', sans-serif",
              lineHeight: 1.2, letterSpacing: '-0.03em',
            }}>
              설계 단계{' '}
              <span style={{
                background: `linear-gradient(135deg, var(--pf-accent-text), var(--pf-accent-text-grad-end))`,
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                color: 'transparent',
              }}>
                보안 위험 분석
              </span>
            </h1>

            <p style={{
              margin: '10px 0 0', fontSize: '15px', color: 'var(--pf-text-4)',
              fontFamily: "'DM Sans', sans-serif", lineHeight: 1.7, maxWidth: '520px',
            }}>
              IaC 템플릿의 보안 정책을 검증하고, 목업 컨테이너 환경에서
              공격 시뮬레이션을 수행해 검증 우선순위를 제시합니다.
            </p>

            <p style={{
              margin: '8px 0 0', fontSize: '12px', color: 'var(--pf-text-5)',
              fontFamily: "'DM Sans', sans-serif", lineHeight: 1.6,
            }}>
              실제 침투 테스트를 대체하는 도구가 아닙니다. IaC 정책 위반과 설계 리스크를
              배포 전에 조기 발견하고, 보안 검토 우선순위를 정하는 데 활용하세요.
            </p>

            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
              <FeaturePill icon="🔍" text="설계 취약점 탐지" />
              <FeaturePill icon="⚡" text="공격 시나리오 식별" />
              <FeaturePill icon="📋" text="검증 우선순위 리포트" />
            </div>
          </div>

          {/* Upload */}
          <div style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(16px)',
            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.25s',
          }}>
            <UploadCard onStartAnalysis={handleAnalyze} />
          </div>

          {/* Error */}
          <AnimatePresence>
            {analysisState === 'error' && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{
                  marginTop: '16px', padding: '14px 20px', borderRadius: '12px',
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

          {/* Footer */}
          <div style={{
            padding: '20px 0', textAlign: 'center',
            opacity: mounted ? 0.5 : 0,
            transition: 'all 1s cubic-bezier(0.4, 0, 0.2, 1) 0.6s',
          }}>
            <p style={{
              margin: 0, fontSize: '11px', color: 'var(--pf-text-5)',
              fontFamily: "'DM Mono', monospace",
            }}>
              Powered by PreFlight Engine · Design-time threat modeling
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
