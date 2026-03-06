import { useState, useEffect } from 'react';
import { MainContent } from './components/MainContent';
import { useAppStore } from './store/app';

function ScrollToTopButton() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 300);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  if (!visible) return null;

  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      style={{
        position: 'fixed', bottom: '24px', right: '24px', zIndex: 100,
        width: '40px', height: '40px', borderRadius: '12px',
        border: '1px solid var(--pf-border)',
        background: 'var(--pf-surface)',
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        cursor: 'pointer', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        transition: 'opacity 0.2s ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.8'; }}
      onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--pf-text-2)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="18 15 12 9 6 15" />
      </svg>
    </button>
  );
}

function NavAnalyzingBadge() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '8px',
      padding: '5px 14px', background: 'rgba(108,58,237,0.08)',
      border: '1px solid rgba(108,58,237,0.25)', borderRadius: '100px',
      fontSize: '12px', fontWeight: 600, color: '#6C3AED',
      fontFamily: "'DM Sans', sans-serif",
    }}>
      <div style={{
        width: '7px', height: '7px', borderRadius: '50%', background: '#6C3AED',
        animation: 'pf-pulse 2s ease-in-out infinite',
      }} />
      에이전트 실행 중
    </div>
  );
}

function NavAnalyzingRight({ onCancel }: { onCancel: () => void }) {
  const { analysisStartTime } = useAppStore();
  const [elapsed, setElapsed] = useState(0);
  const [cancelHover, setCancelHover] = useState(false);
  useEffect(() => {
    if (!analysisStartTime) return;
    const tick = () => setElapsed(Math.floor((Date.now() - analysisStartTime) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [analysisStartTime]);
  const elapsedStr = `경과 ${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;
  return (
    <>
      <span style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: '13px',
        color: 'var(--pf-text-4)', fontWeight: 500,
      }}>{elapsedStr}</span>
      <button
        onClick={onCancel}
        onMouseEnter={() => setCancelHover(true)}
        onMouseLeave={() => setCancelHover(false)}
        style={{
          padding: '7px 16px', borderRadius: '8px',
          border: `1px solid ${cancelHover ? 'rgba(220,38,38,0.25)' : 'var(--pf-border)'}`,
          background: cancelHover ? 'rgba(220,38,38,0.04)' : 'var(--pf-surface)',
          color: cancelHover ? '#DC2626' : 'var(--pf-text-4)',
          fontSize: '12px', fontWeight: 600,
          fontFamily: "'DM Sans', sans-serif",
          cursor: 'pointer', transition: 'all 0.2s',
        }}
      >
        분석 취소
      </button>
    </>
  );
}

function App() {
  const { analysisState, reset, setAnalysisState, clearLiveSteps, setError } = useAppStore();

  const handleCancelAnalysis = () => {
    setAnalysisState('idle');
    clearLiveSteps();
    setError(null);
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--pf-bg)', position: 'relative', overflow: 'hidden' }}>
      {/* Ambient background */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0 }}>
        <div style={{
          position: 'absolute', top: '-20%', left: '50%', transform: 'translateX(-50%)',
          width: '800px', height: '800px', borderRadius: '50%',
          background: 'radial-gradient(circle, var(--pf-ambient-1) 0%, transparent 70%)',
        }} />
        <div style={{
          position: 'absolute', bottom: '-10%', right: '-10%',
          width: '600px', height: '600px', borderRadius: '50%',
          background: 'radial-gradient(circle, var(--pf-ambient-2) 0%, transparent 70%)',
        }} />
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'radial-gradient(var(--pf-grid-dot) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }} />
      </div>

      {/* Header */}
      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
        borderBottom: '1px solid var(--pf-header-border)',
        background: 'var(--pf-header-bg)',
        backdropFilter: 'blur(20px)',
      }}>
        <div style={{
          maxWidth: '1200px', margin: '0 auto', padding: '0 24px',
          height: '60px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          {/* Logo + Analyzing Badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <svg width="28" height="28" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
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
            <span style={{
              fontSize: '16px', fontWeight: 700, color: 'var(--pf-text-1)',
              fontFamily: "'Outfit', sans-serif", letterSpacing: '-0.02em',
            }}>
              PreFlight
            </span>
            {analysisState === 'analyzing' && <NavAnalyzingBadge />}
          </div>

          {/* Right actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {analysisState === 'analyzing' && <NavAnalyzingRight onCancel={handleCancelAnalysis} />}
            {analysisState === 'completed' && (
              <button
                onClick={reset}
                style={{
                  padding: '6px 22px', borderRadius: '10px',
                  border: '1px solid rgba(108,58,237,0.25)',
                  background: 'rgba(108,58,237,0.08)', color: '#6C3AED',
                  fontSize: '15px', fontWeight: 600,
                  fontFamily: "'DM Sans', sans-serif", cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                ＋ 새 분석
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        <MainContent />
      </div>

      <ScrollToTopButton />
    </div>
  );
}

export default App;
