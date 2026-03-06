import { MainContent } from './components/MainContent';
import { useAppStore } from './store/app';

function App() {
  const { analysisState, reset } = useAppStore();

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
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '8px',
              background: 'linear-gradient(135deg, var(--pf-accent), var(--pf-accent-deep))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: 'var(--pf-logo-shadow)',
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0 0 11.5 2 1.5 1.5 0 0 0 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5Z"/>
              </svg>
            </div>
            <span style={{
              fontSize: '16px', fontWeight: 700, color: 'var(--pf-text-1)',
              fontFamily: "'Outfit', sans-serif", letterSpacing: '-0.02em',
            }}>
              PreFlight
            </span>
          </div>

          {/* Right actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {analysisState === 'completed' && (
              <button
                onClick={reset}
                style={{
                  padding: '6px 14px', borderRadius: '8px',
                  border: '1px solid var(--pf-na-border)',
                  background: 'var(--pf-na-bg)', color: 'var(--pf-na-text)',
                  fontSize: '13px', fontFamily: "'DM Sans', sans-serif", cursor: 'pointer',
                }}
              >
                ↩ New Analysis
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        <MainContent />
      </div>
    </div>
  );
}

export default App;
