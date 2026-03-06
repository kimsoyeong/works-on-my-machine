import { motion } from 'framer-motion';
import { useAppStore } from '@/store/app';

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

const SEVERITY = [
  { key: 'Critical', color: '#ef4444', bg: 'rgba(239,68,68,0.10)' },
  { key: 'High', color: '#fdba74', bg: 'rgba(253,186,116,0.10)' },
  { key: 'Medium', color: '#3b82f6', bg: 'rgba(59,130,246,0.10)' },
  { key: 'Low', color: '#22c55e', bg: 'rgba(34,197,94,0.10)' },
] as const;

export function ResultSummary() {
  const { analysisResult, elapsedSeconds } = useAppStore();

  if (!analysisResult?.security) {
    return null;
  }

  const { security, policy } = analysisResult;
  const counts = security.severity_counts || {};
  const total = security.vulnerability_summary || 0;
  const attackCount = security.attack_scenarios?.length || 0;
  const reproduction = security.reproduction_fidelity;
  const elapsed = elapsedSeconds != null ? formatElapsed(elapsedSeconds) : null;
  const policyViolations = policy?.violations ?? 0;
  const policyRecommendations = policy?.recommendations ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ width: '100%', maxWidth: '56rem', margin: '0 auto' }}
    >
      <h2 style={{
        fontSize: '20px',
        fontWeight: 700,
        color: 'var(--pf-text-1)',
        fontFamily: "'Outfit', sans-serif",
        marginBottom: '18px',
        paddingLeft: '14px',
        borderLeft: '3px solid var(--pf-accent)',
      }}>
        Analysis Summary
      </h2>

      {/* Header: total count */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: '12px',
      }}>
        <div style={{
          fontFamily: "'Outfit', sans-serif",
          fontSize: '16px',
          fontWeight: 600,
          color: '#334155',
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
        }}>
          Vulnerabilities
          <span style={{ fontSize: '22px', color: 'var(--pf-accent)', fontWeight: 700 }}>
            {total}
          </span>
        </div>
      </div>

      {/* Severity progress bar */}
      {total > 0 && (
        <motion.div
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          style={{ transformOrigin: 'left', marginBottom: '10px' }}
        >
          <div style={{
            display: 'flex',
            height: '28px',
            borderRadius: '8px',
            overflow: 'hidden',
            background: '#f1f5f9',
          }}>
            {SEVERITY.map(({ key, color }) => {
              const count = counts[key] || 0;
              if (count === 0) return null;
              return (
                <div
                  key={key}
                  style={{
                    flex: count,
                    background: color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    fontSize: '11px',
                    fontWeight: 600,
                    fontFamily: "'Outfit', sans-serif",
                    minWidth: count > 0 ? '24px' : 0,
                  }}
                >
                  {count}
                </div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: '20px',
        marginBottom: '18px',
      }}>
        {SEVERITY.map(({ key, color }) => (
          <div key={key} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: '#64748b',
          }}>
            <span style={{
              width: '10px',
              height: '10px',
              borderRadius: '3px',
              background: color,
              display: 'inline-block',
              flexShrink: 0,
            }} />
            {key}{' '}
            <span style={{ fontWeight: 700, color: '#334155' }}>
              {counts[key] || 0}
            </span>
          </div>
        ))}
      </div>

      {/* Meta footer */}
      <div style={{
        display: 'flex',
        gap: '24px',
        paddingTop: '14px',
        borderTop: '1px solid #f1f5f9',
        fontSize: '13px',
        color: '#64748b',
        flexWrap: 'wrap',
      }}>
        <div>
          Policy Violations{' '}
          <span style={{ fontWeight: 700, color: policyViolations > 0 ? '#ef4444' : '#334155' }}>
            {policyViolations}
          </span>
        </div>
        <div>
          Recommendations{' '}
          <span style={{ fontWeight: 700, color: '#334155' }}>{policyRecommendations}</span>
        </div>
        <div>
          Attack Scenarios{' '}
          <span style={{ fontWeight: 700, color: '#334155' }}>{attackCount}</span>
        </div>
        {reproduction != null && (
          <div>
            Reproduction{' '}
            <span style={{ fontWeight: 700, color: '#334155' }}>{reproduction}%</span>
          </div>
        )}
        {elapsed && (
          <div>
            Elapsed{' '}
            <span style={{ fontWeight: 700, color: '#334155' }}>{elapsed}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
