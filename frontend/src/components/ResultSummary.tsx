import { useState } from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '@/store/app';

const SEVERITY = [
  { key: 'Critical', label: 'Critical', color: '#ef4444' },
  { key: 'High', label: 'High', color: '#6366f1' },
  { key: 'Medium', label: 'Med', color: '#cbd5e1' },
  { key: 'Low', label: 'Low', color: '#cbd5e1' },
] as const;

function calcScore(
  counts: Record<string, number>,
  violations: number,
  totalPolicies: number,
  reproFidelity: number | null,
): number {
  const confidence = reproFidelity != null ? reproFidelity / 100 : 0.5;

  // 정책준수 점수 (65점 만점, Bicep 직접 분석 — 고신뢰)
  const policyScore = totalPolicies > 0
    ? 65 * (1 - violations / totalPolicies)
    : 65;

  // 잠재 취약점 점수 (재현율에 따라 배점 유동, 최대 35점)
  const vulnMax = 35 * confidence;
  const c = counts['Critical'] || 0;
  const h = counts['High'] || 0;
  const m = counts['Medium'] || 0;
  const l = counts['Low'] || 0;
  const vulnDeduct = c * 15 + h * 8 + m * 4 + l * 1;
  const vulnScore = Math.max(0, vulnMax - vulnDeduct);

  // 100점 정규화
  const maxTotal = 65 + vulnMax;
  return Math.round((policyScore + vulnScore) / maxTotal * 100);
}

function getGrade(score: number) {
  if (score >= 90) return { letter: 'A', color: '#22c55e', message: '양호' };
  if (score >= 75) return { letter: 'B', color: '#6366f1', message: '경미한 개선 필요' };
  if (score >= 60) return { letter: 'C', color: '#a78bfa', message: '개선 권고' };
  if (score >= 40) return { letter: 'D', color: '#f97316', message: '주의 필요' };
  return { letter: 'F', color: '#ef4444', message: '즉시 조치 필요' };
}

function ScoreGauge({ score, color }: { score: number; color: string }) {
  const size = 140;
  const sw = 10;
  const r = (size - sw) / 2;
  const circ = 2 * Math.PI * r;
  const arcLen = circ * (270 / 360);
  const filled = arcLen * (score / 100);
  const gap = circ - arcLen;

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(135deg)' }}>
      <circle cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke="#e2e8f0" strokeWidth={sw}
        strokeDasharray={`${arcLen} ${gap}`}
        strokeLinecap="round" />
      {score > 0 && (
        <circle cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth={sw}
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeLinecap="round" />
      )}
    </svg>
  );
}

const cardBase: React.CSSProperties = {
  padding: '20px',
  borderRadius: '14px',
  background: 'var(--pf-surface)',
  border: '1px solid var(--pf-border)',
};

const titleStyle = (color?: string): React.CSSProperties => ({
  fontSize: '13px',
  fontWeight: 600,
  color: color || '#64748b',
  fontFamily: "'DM Sans', sans-serif",
  marginBottom: '8px',
});

const bigNum: React.CSSProperties = {
  fontSize: '32px',
  fontWeight: 800,
  color: 'var(--pf-text-1)',
  fontFamily: "'Outfit', sans-serif",
  lineHeight: 1,
};

const subText: React.CSSProperties = {
  fontSize: '14px',
  color: '#94a3b8',
  fontFamily: "'DM Sans', sans-serif",
};

/** 델타 pill: higherIsBetter=true면 양수가 초록, false면 양수가 빨강 */
function DeltaPill({ value, suffix, higherIsBetter = true }: {
  value: number; suffix?: string; higherIsBetter?: boolean;
}) {
  if (value === 0) return null;
  const isPositive = value > 0;
  const isGood = higherIsBetter ? isPositive : !isPositive;
  const color = isGood ? '#22c55e' : '#ef4444';
  const bg = isGood ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)';
  const arrow = isPositive ? '\u2191' : '\u2193';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '2px',
      padding: '2px 8px', borderRadius: '6px',
      background: bg, color, fontSize: '11px', fontWeight: 700,
      fontFamily: "'DM Mono', monospace", marginLeft: '6px',
    }}>
      {arrow}{Math.abs(value)}{suffix || ''}
    </span>
  );
}

const GRADE_INFO = [
  { letter: 'A', range: '90–100', color: '#22c55e', label: '양호' },
  { letter: 'B', range: '75–89', color: '#6366f1', label: '경미한 개선 필요' },
  { letter: 'C', range: '60–74', color: '#a78bfa', label: '개선 권고' },
  { letter: 'D', range: '40–59', color: '#f97316', label: '주의 필요' },
  { letter: 'F', range: '0–39', color: '#ef4444', label: '즉시 조치 필요' },
] as const;

function GradeInfoIcon() {
  const [show, setShow] = useState(false);
  return (
    <div
      style={{ position: 'absolute', top: '12px', right: '12px' }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <div style={{
        width: '20px', height: '20px', borderRadius: '50%',
        border: '1.5px solid #cbd5e1', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        cursor: 'help', color: '#94a3b8', fontSize: '12px',
        fontWeight: 700, fontFamily: "'DM Sans', sans-serif",
        transition: 'border-color 0.15s',
        ...(show ? { borderColor: '#94a3b8' } : {}),
      }}>
        i
      </div>
      {show && (
        <div style={{
          position: 'absolute', top: '28px', right: 0,
          background: '#1e293b', borderRadius: '10px',
          padding: '12px 14px', zIndex: 50, width: '200px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
        }}>
          <div style={{
            fontSize: '11px', fontWeight: 700, color: '#94a3b8',
            fontFamily: "'DM Sans', sans-serif", marginBottom: '8px',
          }}>
            등급 기준
          </div>
          {GRADE_INFO.map(({ letter, range, color, label }) => (
            <div key={letter} style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '4px 0', fontSize: '12px',
              fontFamily: "'DM Sans', sans-serif",
            }}>
              <span style={{
                width: '20px', fontWeight: 800, color,
                fontFamily: "'Outfit', sans-serif", textAlign: 'center',
              }}>{letter}</span>
              <span style={{
                color: '#cbd5e1', fontFamily: "'DM Mono', monospace",
                fontSize: '11px', minWidth: '50px',
              }}>{range}</span>
              <span style={{ color: '#94a3b8', fontSize: '11px' }}>{label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DetailLink({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        position: 'absolute', top: '18px', right: '20px',
        padding: 0, border: 'none', background: 'none',
        cursor: 'pointer', fontSize: '12px', fontWeight: 600,
        color: '#6C3AED', fontFamily: "'DM Sans', sans-serif",
        display: 'flex', alignItems: 'center', gap: '2px',
        transition: 'opacity 0.15s',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.7'; }}
      onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
    >
      상세 보기 &gt;
    </button>
  );
}

function navigateToSection(section: string) {
  useAppStore.getState().setReportSection(section);
  // 보고서 탭 영역으로 스크롤
  setTimeout(() => {
    document.getElementById('report-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 50);
}

export function ResultSummary() {
  const { analysisResult, previousResult } = useAppStore();

  if (!analysisResult?.security) return null;

  const { security, policy } = analysisResult;
  const counts = security.severity_counts || {};
  const total = security.vulnerability_summary || 0;
  const scenarios = security.attack_scenarios || [];
  const attackCount = scenarios.length;
  const reproduction = security.reproduction_fidelity;
  const reproDetails = security.reproduction_details || {};
  const policyViolations = policy?.violations ?? 0;
  const policyRecommendations = policy?.recommendations ?? 0;
  const totalPolicies = policyViolations + policyRecommendations;

  const score = calcScore(counts, policyViolations, totalPolicies, reproduction);
  const grade = getGrade(score);
  const hasCritical = (counts['Critical'] || 0) > 0 || (counts['High'] || 0) > 0;

  // Attack scenario classification by severity
  const atkSuccess = scenarios.filter(s => s.severity === 'Critical' || s.severity === 'High').length;
  const atkPartial = scenarios.filter(s => s.severity === 'Medium').length;
  const atkBlocked = scenarios.filter(s => s.severity === 'Low').length;

  // Delta calculations (compared to previous result)
  const prev = previousResult?.security;
  const prevPolicy = previousResult?.policy;
  const prevScore = prev
    ? calcScore(
        prev.severity_counts || {},
        prevPolicy?.violations ?? 0,
        (prevPolicy?.violations ?? 0) + (prevPolicy?.recommendations ?? 0),
        prev.reproduction_fidelity,
      )
    : null;
  const dScore = prevScore != null ? score - prevScore : null;
  const dViolations = prevPolicy != null ? policyViolations - (prevPolicy.violations ?? 0) : null;
  const dTotal = prev ? total - (prev.vulnerability_summary || 0) : null;
  const dAttack = prev ? attackCount - (prev.attack_scenarios || []).length : null;
  const dRepro = prev?.reproduction_fidelity != null && reproduction != null
    ? reproduction - prev.reproduction_fidelity : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ width: '100%', maxWidth: '72rem', margin: '0 auto' }}
    >
      {/* Alert Banner */}
      {(score < 60 || hasCritical) && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '14px',
          padding: '16px 20px', borderRadius: '14px', marginBottom: '20px',
          background: `${grade.color}0F`,
          border: `1px solid ${grade.color}33`,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: '10px', flexShrink: 0,
            background: `${grade.color}20`, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ fontSize: 18, color: grade.color }}>⚠</span>
          </div>
          <div>
            <div style={{
              fontSize: '15px', fontWeight: 700, color: grade.color,
              fontFamily: "'Outfit', sans-serif", marginBottom: '2px',
            }}>{grade.message}</div>
            <div style={{
              fontSize: '13px', color: '#64748b',
              fontFamily: "'DM Sans', sans-serif",
            }}>
              {(counts['Critical'] || 0) > 0 && `Critical 취약점 ${counts['Critical']}건`}
              {(counts['Critical'] || 0) > 0 && policyViolations > 0 && ' · '}
              {policyViolations > 0 && `정책 위반 ${policyViolations}건`}
              {(policyViolations > 0 || (counts['Critical'] || 0) > 0) && atkSuccess > 0 && ' · '}
              {atkSuccess > 0 && `위협 시뮬레이션 ${atkSuccess}/${attackCount}건 침투 성공`}
            </div>
          </div>
        </div>
      )}

      {/* Dashboard Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1.3fr 1.3fr',
        gridTemplateRows: 'auto auto',
        gap: '12px',
        marginBottom: '4px',
      }}>
        {/* 보안 등급 — spans 2 rows */}
        <div style={{
          ...cardBase,
          gridRow: '1 / 3',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px 16px',
          textAlign: 'center',
          position: 'relative',
        }}>
          <GradeInfoIcon />
          <div style={titleStyle()}>보안 등급</div>
          <div style={{ position: 'relative', width: 140, height: 140, margin: '8px auto' }}>
            <ScoreGauge score={score} color={grade.color} />
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <span style={{
                fontSize: '48px', fontWeight: 800, color: grade.color,
                fontFamily: "'Outfit', sans-serif", lineHeight: 1,
              }}>
                {grade.letter}
              </span>
              <span style={{
                fontSize: '14px', fontWeight: 600, color: '#64748b',
                fontFamily: "'DM Sans', sans-serif", marginTop: '4px',
              }}>
                {score}/100
                {dScore != null && dScore !== 0 && <DeltaPill value={dScore} higherIsBetter />}
              </span>
            </div>
          </div>
          <div style={{
            marginTop: '16px', padding: '6px 16px', borderRadius: '8px',
            background: `${grade.color}18`, color: grade.color,
            fontSize: '13px', fontWeight: 600, fontFamily: "'DM Sans', sans-serif",
          }}>
            {grade.message}
          </div>
        </div>

        {/* 정책 위반 */}
        <div style={{ ...cardBase, position: 'relative' }}>
          <div style={titleStyle()}>정책 위반</div>
          {totalPolicies > 0 && <DetailLink onClick={() => navigateToSection('policy')} />}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span style={bigNum}>{policyViolations}</span>
            <span style={subText}>/{totalPolicies} 정책</span>
            {dViolations != null && dViolations !== 0 && <DeltaPill value={dViolations} higherIsBetter={false} />}
          </div>
          {totalPolicies > 0 && (
            <>
              <div style={{
                display: 'flex', height: '10px', borderRadius: '5px',
                overflow: 'hidden', marginTop: '14px',
              }}>
                {policyViolations > 0 && (
                  <div style={{ flex: policyViolations, background: '#ef4444', borderRadius: '5px' }} />
                )}
                {policyRecommendations > 0 && (
                  <div style={{ flex: policyRecommendations, background: '#e2e8f0' }} />
                )}
              </div>
              <div style={{ display: 'flex', gap: '16px', marginTop: '10px' }}>
                {policyViolations > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b', fontFamily: "'DM Sans', sans-serif" }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
                    위반 {policyViolations}
                  </div>
                )}
                {policyRecommendations > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b', fontFamily: "'DM Sans', sans-serif" }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#cbd5e1', display: 'inline-block' }} />
                    권고 {policyRecommendations}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* 발견 취약점 */}
        <div style={{ ...cardBase, position: 'relative' }}>
          <div style={titleStyle()}>발견 취약점</div>
          {total > 0 && <DetailLink onClick={() => navigateToSection('vulns')} />}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span style={bigNum}>{total}</span>
            <span style={subText}>건</span>
            {dTotal != null && dTotal !== 0 && <DeltaPill value={dTotal} higherIsBetter={false} />}
          </div>
          {total > 0 && (
            <>
              <div style={{
                display: 'flex', height: '10px', borderRadius: '5px',
                overflow: 'hidden', marginTop: '14px',
              }}>
                {SEVERITY.map(({ key, color }) => {
                  const count = counts[key] || 0;
                  if (count === 0) return null;
                  return <div key={key} style={{ flex: count, background: color }} />;
                })}
              </div>
              <div style={{ display: 'flex', gap: '14px', marginTop: '10px', flexWrap: 'wrap' }}>
                {SEVERITY.map(({ key, label, color }) => {
                  const count = counts[key] || 0;
                  if (count === 0) return null;
                  const merged = key === 'Medium' ? `Med·Low ${(counts['Medium'] || 0) + (counts['Low'] || 0)}` : null;
                  if (key === 'Low' && (counts['Medium'] || 0) > 0) return null;
                  return (
                    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b', fontFamily: "'DM Sans', sans-serif" }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block' }} />
                      {merged || `${label} ${count}`}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* 위협 시나리오 */}
        <div style={{ ...cardBase, position: 'relative' }}>
          <div style={titleStyle()}>위협 시나리오</div>
          {attackCount > 0 && <DetailLink onClick={() => navigateToSection('attacks')} />}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span style={bigNum}>{attackCount}</span>
            <span style={subText}>건 수행</span>
            {dAttack != null && dAttack !== 0 && <DeltaPill value={dAttack} higherIsBetter={false} />}
          </div>
          {attackCount > 0 && (
            <>
              <div style={{
                display: 'flex', height: '10px', borderRadius: '5px',
                overflow: 'hidden', marginTop: '14px',
              }}>
                {atkSuccess > 0 && <div style={{ flex: atkSuccess, background: '#ef4444' }} />}
                {atkPartial > 0 && <div style={{ flex: atkPartial, background: '#6366f1' }} />}
                {atkBlocked > 0 && <div style={{ flex: atkBlocked, background: '#e2e8f0' }} />}
              </div>
              <div style={{ display: 'flex', gap: '16px', marginTop: '10px' }}>
                {atkSuccess > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b', fontFamily: "'DM Sans', sans-serif" }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
                    침투 성공 {atkSuccess}
                  </div>
                )}
                {atkPartial > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b', fontFamily: "'DM Sans', sans-serif" }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#6366f1', display: 'inline-block' }} />
                    부분 {atkPartial}
                  </div>
                )}
                {atkBlocked > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b', fontFamily: "'DM Sans', sans-serif" }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#e2e8f0', display: 'inline-block' }} />
                    차단 {atkBlocked}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* 아키텍처 재현율 */}
        <div style={{ ...cardBase, position: 'relative' }}>
          <div style={titleStyle()}>아키텍처 재현율</div>
          {reproduction != null && <DetailLink onClick={() => navigateToSection('docker')} />}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
            <span style={{ ...bigNum, color: reproduction != null && reproduction >= 100 ? '#22c55e' : reproduction != null && reproduction >= 50 ? '#6366f1' : '#ef4444' }}>{reproduction ?? 'N/A'}</span>
            {reproduction != null && (
              <span style={{ fontSize: '20px', fontWeight: 700, color: '#94a3b8', fontFamily: "'Outfit', sans-serif" }}>%</span>
            )}
            {dRepro != null && dRepro !== 0 && <DeltaPill value={dRepro} suffix="%" higherIsBetter />}
          </div>
          {Object.keys(reproDetails).length > 0 && (
            <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {Object.entries(reproDetails).map(([label, val]) => {
                const match = String(val).match(/(\d+)\s*\/\s*(\d+)/);
                const current = match ? parseInt(match[1]) : 0;
                const total = match ? parseInt(match[2]) : 1;
                const pct = total > 0 ? (current / total) * 100 : 0;
                const barColor = pct >= 100 ? '#22c55e' : pct >= 50 ? '#6366f1' : '#ef4444';
                const shortLabel = label.replace('재현', '').replace(/\s+/g, '').trim();
                return (
                  <div key={label} style={{
                    display: 'flex', alignItems: 'center', gap: '8px',
                    fontSize: '12px', fontFamily: "'DM Sans', sans-serif",
                  }}>
                    <span style={{ color: '#64748b', minWidth: '52px', flexShrink: 0 }}>{shortLabel}</span>
                    <div style={{
                      flex: 1, height: '8px', borderRadius: '4px',
                      background: '#e2e8f0', overflow: 'hidden',
                    }}>
                      <div style={{
                        width: `${pct}%`, height: '100%', borderRadius: '4px',
                        background: barColor, transition: 'width 0.3s ease',
                      }} />
                    </div>
                    <span style={{
                      fontWeight: 700, color: 'var(--pf-text-2)',
                      fontFamily: "'DM Mono', monospace", fontSize: '12px',
                      minWidth: '28px', textAlign: 'right', flexShrink: 0,
                    }}>{String(val).replace(/\s*\(.*\)/, '')}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

    </motion.div>
  );
}
