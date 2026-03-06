import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import { useAppStore } from '@/store/app';
import { analyzeFileStream } from '@/services/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const COLLAPSED_LINES = 15;

/* ── Table helpers ── */

function TableHeader({ columns }: { columns: string[] }) {
  return (
    <thead>
      <tr style={{ borderBottom: '1px solid var(--pf-border)' }}>
        {columns.map((h, i) => (
          <th key={i} style={{
            padding: '10px 12px', textAlign: 'left', fontSize: 11,
            color: '#9CA3AF', fontWeight: 500, textTransform: 'uppercase',
            letterSpacing: '0.5px', whiteSpace: 'nowrap',
            fontFamily: "'DM Sans', sans-serif",
          }}>{h}</th>
        ))}
      </tr>
    </thead>
  );
}

function HoverRow({ children }: { children: React.ReactNode }) {
  return (
    <tr
      style={{ borderBottom: '1px solid var(--pf-border)', transition: 'background 0.15s' }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--pf-surface-subtle)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
    >{children}</tr>
  );
}

const td: React.CSSProperties = {
  padding: '12px', fontSize: 13, color: 'var(--pf-text-1)',
  fontFamily: "'DM Sans', sans-serif", verticalAlign: 'top',
};

const tdMono: React.CSSProperties = {
  ...td, fontFamily: "'DM Mono', monospace", fontSize: 12, color: '#9CA3AF',
};

const tdMuted: React.CSSProperties = { ...td, color: '#6B7280', fontSize: 12 };

/* ── Badge components ── */

function StatusIcon({ status }: { status: string }) {
  if (status === 'pass') return <span style={{ color: '#059669', fontSize: 14 }}>&#10003;</span>;
  if (status === 'fail') return <span style={{ color: '#DC2626', fontSize: 14 }}>&#10007;</span>;
  return <span style={{ color: '#EA580C', fontSize: 14 }}>&#9680;</span>;
}

function SeverityBadge({ severity }: { severity: string }) {
  const config: Record<string, { label: string; color: string; bg: string }> = {
    critical: { label: 'Critical', color: '#DC2626', bg: 'rgba(220,38,38,0.06)' },
    high: { label: 'High', color: '#EA580C', bg: 'rgba(234,88,12,0.06)' },
    medium: { label: 'Medium', color: '#CA8A04', bg: 'rgba(202,138,4,0.06)' },
    low: { label: 'Low', color: '#16A34A', bg: 'rgba(22,163,74,0.06)' },
  };
  const c = config[severity.toLowerCase()] || config.medium;
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
      background: c.bg, color: c.color, border: `1px solid ${c.color}22`,
      textTransform: 'uppercase', letterSpacing: '0.5px',
    }}>{c.label}</span>
  );
}

function AttackResultBadge({ result }: { result: string }) {
  const config: Record<string, { label: string; color: string; icon: string }> = {
    success: { label: '침투 성공', color: '#DC2626', icon: '\u2717' },
    partial: { label: '정보 노출', color: '#EA580C', icon: '\u25D0' },
    blocked: { label: '차단됨', color: '#059669', icon: '\u2713' },
  };
  const c = config[result] || config.partial;
  return (
    <span style={{
      fontSize: 11, fontWeight: 500, color: c.color,
      display: 'flex', alignItems: 'center', gap: 4,
    }}>
      <span style={{ fontSize: 13 }}>{c.icon}</span>{c.label}
    </span>
  );
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  return (
    <div style={{ flex: 1, height: 6, background: 'var(--pf-border)', borderRadius: 3, overflow: 'hidden' }}>
      <div style={{
        width: `${max > 0 ? (value / max) * 100 : 0}%`, height: '100%',
        background: color, borderRadius: 3, transition: 'width 0.8s ease',
      }} />
    </div>
  );
}

/* ── Section heading ── */

function SectionHeading({ title, description }: { title: string; description: string }) {
  return (
    <>
      <h3 style={{
        fontSize: 16, fontWeight: 700, marginBottom: 4,
        fontFamily: "'Outfit', sans-serif", color: 'var(--pf-text-1)',
      }}>{title}</h3>
      <p style={{
        fontSize: 13, color: '#9CA3AF', marginBottom: 20,
        fontFamily: "'DM Sans', sans-serif",
      }}>{description}</p>
    </>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div style={{
      textAlign: 'center', padding: 24, color: '#9CA3AF',
      fontSize: 13, fontFamily: "'DM Sans', sans-serif",
    }}>{message}</div>
  );
}

/* ── Bicep code block ── */

function BicepCodeBlock({ code, onRevalidate }: { code: string; onRevalidate: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const lines = code.split('\n');
  const isLong = lines.length > COLLAPSED_LINES + 5;
  const displayCode = !expanded && isLong
    ? lines.slice(0, COLLAPSED_LINES).join('\n')
    : code;

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h3 style={{
          fontSize: 16, fontWeight: 700, marginBottom: 4,
          fontFamily: "'Outfit', sans-serif", color: 'var(--pf-text-1)',
        }}>개선된 Bicep 코드</h3>
        <p style={{ fontSize: 13, color: '#9CA3AF', fontFamily: "'DM Sans', sans-serif" }}>
          보안 보고서 기반으로 취약점이 수정된 인프라 코드입니다.
        </p>
      </div>

      <div style={{ borderRadius: 12, overflow: 'hidden', position: 'relative' }}>
        <SyntaxHighlighter
          language="typescript"
          style={oneDark}
          showLineNumbers
          lineNumberStyle={{ minWidth: '3em', paddingRight: '16px', color: '#636d83', fontSize: '12px' }}
          customStyle={{
            margin: 0, padding: '20px 16px', fontSize: '13px', lineHeight: 1.7,
            borderRadius: isLong && !expanded ? '12px 12px 0 0' : '12px',
            fontFamily: "'DM Mono', 'Fira Code', monospace",
          }}
        >
          {displayCode}
        </SyntaxHighlighter>

        {isLong && !expanded && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, height: '60px',
            background: 'linear-gradient(transparent, #282c34)',
            pointerEvents: 'none', borderRadius: '0 0 12px 12px',
          }} />
        )}

        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              width: '100%', padding: '10px', background: '#21252b', border: 'none',
              borderTop: '1px solid #383d47', borderRadius: '0 0 12px 12px',
              color: '#abb2bf', fontSize: '13px', fontWeight: 500,
              fontFamily: "'DM Sans', sans-serif", cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
              transition: 'color 0.2s ease',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#61afef'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = '#abb2bf'; }}
          >
            {expanded ? (
              <><ChevronUp style={{ width: 16, height: 16 }} /> 코드 접기</>
            ) : (
              <><ChevronDown style={{ width: 16, height: 16 }} /> 전체 코드 보기 ({lines.length}줄)</>
            )}
          </button>
        )}
      </div>

      <button
        onClick={onRevalidate}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
          width: '100%', marginTop: '16px', padding: '14px 20px',
          background: 'var(--pf-accent)', border: 'none', borderRadius: '12px',
          color: '#fff', fontSize: '15px', fontWeight: 600,
          fontFamily: "'DM Sans', sans-serif", cursor: 'pointer',
          transition: 'opacity 0.2s ease',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.85'; }}
        onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
      >
        <RefreshCw style={{ width: 17, height: 17 }} />
        개선된 Bicep으로 재검증
      </button>
    </div>
  );
}

/* ── Main component ── */

const SUB_TABS = [
  { id: 'policy', label: '정책 준수 검토' },
  { id: 'controls', label: '보안 통제 검토' },
  { id: 'vulns', label: '취약점 우선순위' },
  { id: 'attacks', label: '위협 시뮬레이션' },
  { id: 'docker', label: '아키텍처 재현' },
  { id: 'checklist', label: '검증 체크리스트' },
] as const;

export function ResultTabs() {
  const {
    analysisResult, reportSection,
    setUploadedFile, setAnalysisState, setAnalysisResult,
    setPreviousResult, setError, addOrUpdateLiveStep, clearLiveSteps,
    setReportSection,
  } = useAppStore();
  const [activeTab, setActiveTab] = useState<'report' | 'bicep'>('report');
  const [vulnFilter, setVulnFilter] = useState<string>('all');
  const prevSection = useRef(reportSection);

  // 상세 보기 클릭 시 report 탭으로 자동 전환
  useEffect(() => {
    if (reportSection !== prevSection.current) {
      prevSection.current = reportSection;
      if (activeTab !== 'report') setActiveTab('report');
    }
  }, [reportSection, activeTab]);

  if (!analysisResult?.security) return null;

  const { security, policy } = analysisResult;
  const report = security.final_report || '';
  const improvedBicep = security.improved_bicep_code || '';
  const hasBicep = !!improvedBicep;

  /* Data */
  const violations = policy?.violation_details || [];
  const recommendations = policy?.recommendation_details || [];
  const policyItems = [
    ...violations.map(v => ({ ...v, result: 'violation' as const })),
    ...recommendations.map(r => ({ ...r, result: 'advisory' as const })),
  ];
  const vulns = security.vulnerabilities || [];
  const scenarios = security.attack_scenarios || [];
  const reproDetails = security.reproduction_details || {};
  const reproFidelity = security.reproduction_fidelity;
  const checklist = security.verification_checklist || [];

  const getAttackResult = (severity: string) => {
    const s = severity.toLowerCase();
    if (s === 'critical' || s === 'high') return 'success';
    if (s === 'medium') return 'partial';
    return 'blocked';
  };
  const successCount = scenarios.filter(s => getAttackResult(s.severity) === 'success').length;
  const partialCount = scenarios.filter(s => getAttackResult(s.severity) === 'partial').length;

  /* Actions */
  const downloadFile = () => {
    if (activeTab === 'report') {
      downloadBlob(report, 'security_report.md', 'text/markdown');
    } else {
      downloadBlob(improvedBicep, 'improved.bicep', 'text/plain');
    }
  };

  const handleRevalidate = async () => {
    setPreviousResult(analysisResult);
    const file = new File([improvedBicep], 'improved.bicep', { type: 'text/plain' });
    setUploadedFile(file);
    clearLiveSteps();
    setAnalysisState('analyzing');
    setError(null);
    try {
      await analyzeFileStream(
        file,
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
      console.error('Revalidation error:', error);
      setError(error instanceof Error ? error.message : 'Network error');
      setAnalysisState('error');
    }
  };

  return (
    <motion.div
      id="report-tabs"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ width: '100%', maxWidth: '72rem', margin: '0 auto' }}
    >
      <div style={{
        background: 'var(--pf-surface)', borderRadius: 12,
        border: '1px solid var(--pf-border)', overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}>
        {/* ── Main tab bar ── */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--pf-border)', padding: '0 24px' }}>
          {[
            { id: 'report' as const, label: '\uD83D\uDCCB 보고서' },
            ...(hasBicep ? [{ id: 'bicep' as const, label: '\u2699 개선된 Bicep' }] : []),
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
              padding: '14px 20px', border: 'none', background: 'transparent', cursor: 'pointer',
              fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? 'var(--pf-text-1)' : 'var(--pf-text-4)',
              borderBottom: activeTab === tab.id ? '2px solid var(--pf-accent)' : '2px solid transparent',
              transition: 'all 0.2s', fontFamily: "'DM Sans', sans-serif",
            }}>{tab.label}</button>
          ))}
          <div style={{ flex: 1 }} />
          <button
            onClick={downloadFile}
            style={{
              padding: '8px 16px', margin: '8px 0', borderRadius: 8, fontSize: 12,
              border: '1px solid var(--pf-border)', background: 'transparent',
              color: 'var(--pf-text-4)', cursor: 'pointer', fontWeight: 500,
              fontFamily: "'DM Sans', sans-serif", transition: 'border-color 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--pf-text-5)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--pf-border)'; }}
          >{'\u2193'} 다운로드</button>
        </div>

        {/* ── Content ── */}
        <div style={{ padding: 24 }}>

          {/* ═══ REPORT TAB ═══ */}
          {activeTab === 'report' && (
            <div>
              {/* Sub-tabs */}
              <div style={{ display: 'flex', gap: 6, marginBottom: 24, flexWrap: 'wrap' }}>
                {SUB_TABS.map(s => (
                  <button key={s.id} onClick={() => setReportSection(s.id)} style={{
                    padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
                    border: `1px solid ${reportSection === s.id ? 'var(--pf-accent)' : 'var(--pf-border)'}`,
                    background: reportSection === s.id ? 'var(--pf-accent-faint-bg)' : 'transparent',
                    color: reportSection === s.id ? 'var(--pf-accent)' : 'var(--pf-text-4)',
                    cursor: 'pointer', transition: 'all 0.2s',
                    fontFamily: "'DM Sans', sans-serif",
                  }}>{s.label}</button>
                ))}
              </div>

              {/* ── 정책 준수 검토 ── */}
              {reportSection === 'policy' && (
                <div>
                  <SectionHeading
                    title="보안 정책 준수 검토"
                    description={`${policyItems.length}개 설계 정책 중 ${violations.length}건 위반, ${recommendations.length}건 권고 사항이 발견되었습니다.`}
                  />
                  {policyItems.length > 0 ? (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <TableHeader columns={['정책', '결과', '설명']} />
                      <tbody>
                        {policyItems.map((p, i) => (
                          <HoverRow key={i}>
                            <td style={{ ...tdMono, whiteSpace: 'nowrap' }}>{p.rule}</td>
                            <td style={td}>
                              <span style={{
                                fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                                background: p.result === 'violation' ? 'rgba(220,38,38,0.06)' : 'rgba(202,138,4,0.06)',
                                color: p.result === 'violation' ? '#DC2626' : '#CA8A04',
                              }}>{p.result === 'violation' ? '위반' : '정책권고'}</span>
                            </td>
                            <td style={{ ...tdMuted, maxWidth: 400 }}>{p.message}</td>
                          </HoverRow>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <EmptyState message="정책 위반 사항이 없습니다." />
                  )}
                </div>
              )}

              {/* ── 보안 통제 검토 ── */}
              {reportSection === 'controls' && (
                <div>
                  <SectionHeading
                    title="설계 수준 보안 통제 검토"
                    description="Bicep 설정 기준 보안 통제 항목별 적용 여부입니다."
                  />
                  {policyItems.length > 0 ? (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <TableHeader columns={['상태', '보안 통제', '설명', '평가']} />
                      <tbody>
                        {policyItems.map((p, i) => (
                          <HoverRow key={i}>
                            <td style={{ ...td, width: 40, textAlign: 'center' }}>
                              <StatusIcon status={p.result === 'violation' ? 'fail' : 'partial'} />
                            </td>
                            <td style={{ ...td, fontWeight: 500 }}>{p.rule}</td>
                            <td style={tdMuted}>{p.message}</td>
                            <td style={{ ...td, whiteSpace: 'nowrap', minWidth: 80 }}>
                              <span style={{
                                fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 4,
                                background: p.result === 'violation' ? 'rgba(220,38,38,0.06)' : 'rgba(202,138,4,0.06)',
                                color: p.result === 'violation' ? '#DC2626' : '#CA8A04',
                              }}>{p.result === 'violation' ? '미흡' : '권고'}</span>
                            </td>
                          </HoverRow>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="pf-report">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                    </div>
                  )}
                </div>
              )}

              {/* ── 취약점 우선순위 ── */}
              {reportSection === 'vulns' && (() => {
                const criticalCount = vulns.filter(v => v.severity.toLowerCase() === 'critical').length;
                const highCount = vulns.filter(v => v.severity.toLowerCase() === 'high').length;
                const mediumCount = vulns.filter(v => v.severity.toLowerCase() === 'medium').length;
                const lowCount = vulns.filter(v => v.severity.toLowerCase() === 'low').length;
                const filters = [
                  { id: 'all', label: '전체', count: vulns.length, color: 'var(--pf-accent)', bg: 'var(--pf-accent-faint-bg)' },
                  { id: 'Critical', label: 'Critical', count: criticalCount, color: '#DC2626', bg: 'rgba(220,38,38,0.06)' },
                  { id: 'High', label: 'High', count: highCount, color: '#EA580C', bg: 'rgba(234,88,12,0.06)' },
                  { id: 'Medium', label: 'Medium', count: mediumCount, color: '#CA8A04', bg: 'rgba(202,138,4,0.06)' },
                  { id: 'Low', label: 'Low', count: lowCount, color: '#16A34A', bg: 'rgba(22,163,74,0.06)' },
                ].filter(f => f.id === 'all' || f.count > 0);
                const filteredVulns = vulnFilter === 'all'
                  ? vulns
                  : vulns.filter(v => v.severity.toLowerCase() === vulnFilter.toLowerCase());
                return (
                  <div>
                    <SectionHeading
                      title="취약점 우선순위"
                      description="발견된 취약점을 심각도 기준으로 정렬합니다."
                    />
                    {vulns.length > 0 && (
                      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
                        {filters.map(f => {
                          const active = vulnFilter === f.id;
                          return (
                            <button key={f.id} onClick={() => setVulnFilter(f.id)} style={{
                              padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500,
                              border: `1px solid ${active ? f.color : 'var(--pf-border)'}`,
                              background: active ? f.bg : 'transparent',
                              color: active ? f.color : 'var(--pf-text-4)',
                              cursor: 'pointer', transition: 'all 0.2s',
                              fontFamily: "'DM Sans', sans-serif",
                            }}>
                              {f.label} ({f.count})
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {filteredVulns.length > 0 ? (
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <TableHeader columns={['ID', '심각도', '위험', '리소스', '설명']} />
                        <tbody>
                          {filteredVulns.map((v, i) => (
                            <HoverRow key={i}>
                              <td style={tdMono}>{v.id}</td>
                              <td style={td}><SeverityBadge severity={v.severity} /></td>
                              <td style={{ ...td, fontWeight: 500, maxWidth: 260 }}>{v.title}</td>
                              <td style={td}>
                                <span style={{
                                  padding: '2px 8px', borderRadius: 4,
                                  background: 'var(--pf-surface-subtle)',
                                  border: '1px solid var(--pf-border)',
                                  fontSize: 12, color: '#6B7280',
                                }}>{v.affected_resource}</span>
                              </td>
                              <td style={{ ...tdMuted, maxWidth: 300 }}>{v.description}</td>
                            </HoverRow>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <EmptyState message="취약점 데이터가 없습니다." />
                    )}
                  </div>
                );
              })()}

              {/* ── 위협 시뮬레이션 ── */}
              {reportSection === 'attacks' && (
                <div>
                  <SectionHeading
                    title="위협 시뮬레이션 결과"
                    description="Docker 재현 환경에서 수행된 위협 시뮬레이션 결과입니다."
                  />
                  {scenarios.length > 0 && (
                    <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
                      {[
                        { label: '침투 성공', count: successCount, color: '#DC2626', bg: 'rgba(220,38,38,0.06)' },
                        { label: '정보 노출', count: partialCount, color: '#EA580C', bg: 'rgba(234,88,12,0.06)' },
                      ].map((s, i) => (
                        <div key={i} style={{
                          padding: '12px 20px', borderRadius: 8, background: s.bg,
                          border: `1px solid ${s.color}22`, flex: 1, textAlign: 'center',
                        }}>
                          <div style={{
                            fontSize: 24, fontWeight: 800, color: s.color,
                            fontFamily: "'Outfit', sans-serif",
                          }}>{s.count}</div>
                          <div style={{
                            fontSize: 11, color: '#9CA3AF', marginTop: 2,
                            fontFamily: "'DM Sans', sans-serif",
                          }}>{s.label}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {scenarios.length > 0 ? (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <TableHeader columns={['공격 표면', '수행한 공격', '결과', '위험도']} />
                      <tbody>
                        {scenarios.map((s, i) => (
                          <HoverRow key={i}>
                            <td style={td}>
                              <span style={{
                                padding: '2px 8px', borderRadius: 4,
                                background: 'var(--pf-surface-subtle)',
                                border: '1px solid var(--pf-border)',
                                fontSize: 12, fontWeight: 500,
                              }}>{s.container}</span>
                            </td>
                            <td style={td}>{s.objective}</td>
                            <td style={td}><AttackResultBadge result={getAttackResult(s.severity)} /></td>
                            <td style={td}><SeverityBadge severity={s.severity} /></td>
                          </HoverRow>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <EmptyState message="위협 시뮬레이션 데이터가 없습니다." />
                  )}

                  {/* 분석 결론 */}
                  {(() => {
                    let text = security.simulation_conclusion || '';
                    if (!text) {
                      const m = report.match(/(?:4\.3|시뮬레이션 결과 해석)[^\n]*\n+([\s\S]*?)(?=\n---|\n#\s|\n##\s\d|$)/i);
                      if (m) text = m[1].replace(/^>\s*/gm, '').trim();
                    }
                    if (!text || text.length < 10) return null;
                    return (
                      <div style={{
                        marginTop: 24, padding: '16px 20px', borderRadius: 10,
                        background: 'var(--pf-surface-subtle)',
                        border: '1px solid var(--pf-border)',
                      }}>
                        <div style={{
                          fontSize: 13, fontWeight: 700, color: 'var(--pf-text-1)',
                          fontFamily: "'Outfit', sans-serif", marginBottom: 6,
                        }}>분석 결론</div>
                        <div className="pf-report" style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.7 }}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* ── 아키텍처 재현 ── */}
              {reportSection === 'docker' && (() => {
                const resourceRepro = security.resource_reproduction || [];
                return (
                  <div>
                    <SectionHeading
                      title="아키텍처 재현 현황"
                      description={`Bicep 리소스의 Docker 환경 재현 상태입니다.${reproFidelity != null ? ` 전체 재현율: ${reproFidelity}%` : ''}`}
                    />

                    {/* 리소스별 Docker 재현 테이블 */}
                    {resourceRepro.length > 0 && (
                      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 32 }}>
                        <TableHeader columns={['상태', '리소스', 'DOCKER 이미지', '비고']} />
                        <tbody>
                          {resourceRepro.map((r, i) => (
                            <HoverRow key={i}>
                              <td style={{ ...td, width: 48, textAlign: 'center' }}>
                                <StatusIcon status={r.status === 'pass' ? 'pass' : 'partial'} />
                              </td>
                              <td style={{ ...td, fontWeight: 500 }}>{r.resource}</td>
                              <td style={tdMono}>{r.docker_image}</td>
                              <td style={tdMuted}>{r.note}</td>
                            </HoverRow>
                          ))}
                        </tbody>
                      </table>
                    )}

                    {/* 재현 점수 상세 */}
                    {Object.keys(reproDetails).length > 0 ? (
                      <div>
                        <h4 style={{
                          fontSize: 14, fontWeight: 600, marginBottom: 12,
                          fontFamily: "'Outfit', sans-serif", color: 'var(--pf-text-1)',
                        }}>재현 점수 상세</h4>
                        {Object.entries(reproDetails).map(([label, val]) => {
                          const match = String(val).match(/(\d+)\s*\/\s*(\d+)/);
                          const current = match ? parseInt(match[1]) : 0;
                          const total = match ? parseInt(match[2]) : 1;
                          const pct = total > 0 ? (current / total) * 100 : 0;
                          const barColor = pct >= 100 ? '#22c55e' : pct >= 50 ? '#6366f1' : '#ef4444';
                          return (
                            <div key={label} style={{
                              display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10,
                            }}>
                              <span style={{
                                fontSize: 13, color: '#6B7280', width: 120, flexShrink: 0,
                                fontFamily: "'DM Sans', sans-serif",
                              }}>{label}</span>
                              <ProgressBar value={current} max={total} color={barColor} />
                              <span style={{
                                fontSize: 13, fontFamily: "'DM Mono', monospace",
                                color: 'var(--pf-text-1)', width: 50, textAlign: 'right',
                                flexShrink: 0, fontWeight: 600,
                              }}>{String(val).replace(/\s*\(.*\)/, '')}</span>
                            </div>
                          );
                        })}
                      </div>
                    ) : resourceRepro.length === 0 ? (
                      <EmptyState message="재현 상세 데이터가 없습니다." />
                    ) : null}
                  </div>
                );
              })()}

              {/* ── 검증 체크리스트 ── */}
              {reportSection === 'checklist' && (() => {
                const isViolated = (item: string) => {
                  const lower = item.toLowerCase();
                  return violations.some(v => {
                    const rule = (v.rule || '').toLowerCase();
                    const msg = (v.message || '').toLowerCase();
                    return lower.includes(rule) || rule.includes(lower)
                      || lower.split(/\s+/).some(w => w.length > 2 && (rule.includes(w) || msg.includes(w)));
                  });
                };
                const passCount = checklist.filter(item => !isViolated(item)).length;
                const failCount = checklist.length - passCount;
                return (
                  <div>
                    <SectionHeading
                      title="보안 검증 체크리스트"
                      description={`최종 보안 검증 항목별 통과 여부입니다. 통과 ${passCount}건, 수정 필요 ${failCount}건`}
                    />
                    {checklist.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {checklist.map((item, i) => {
                          const failed = isViolated(item);
                          return (
                            <div key={i} style={{
                              display: 'flex', alignItems: 'center', gap: 14,
                              padding: '14px 20px', borderRadius: 10,
                              background: failed ? 'rgba(220,38,38,0.03)' : 'var(--pf-surface-subtle)',
                              border: `1px solid ${failed ? 'rgba(220,38,38,0.15)' : 'var(--pf-border)'}`,
                            }}>
                              <StatusIcon status={failed ? 'fail' : 'pass'} />
                              <span style={{
                                fontSize: 14, fontWeight: 500, flex: 1,
                                color: 'var(--pf-text-1)', fontFamily: "'DM Sans', sans-serif",
                              }}>{item}</span>
                              <span style={{
                                fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
                                color: failed ? '#DC2626' : '#059669',
                                fontFamily: "'DM Sans', sans-serif",
                              }}>{failed ? '수정 필요' : '적용(OK)'}</span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <EmptyState message="체크리스트 항목이 없습니다." />
                    )}
                  </div>
                );
              })()}
            </div>
          )}

          {/* ═══ BICEP TAB ═══ */}
          {activeTab === 'bicep' && (
            <BicepCodeBlock code={improvedBicep} onRevalidate={handleRevalidate} />
          )}
        </div>
      </div>
    </motion.div>
  );
}
