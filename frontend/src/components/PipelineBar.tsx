import { motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { useAppStore } from '@/store/app';
import type { StepStatus } from '@/types/api';

const STEPS = [
  { id: 'upload', label: 'Upload', x: 90, y: 100, emoji: '📤', accent: '99,102,241' },    // indigo
  { id: 'bicep', label: 'BiCep', x: 270, y: 100, emoji: '⚙️', accent: '99,102,241' },     // indigo
  { id: 'policy', label: 'Policy', x: 460, y: 46, emoji: '🛡️', accent: '249,115,22' },    // orange
  { id: 'recon', label: 'Recon', x: 460, y: 154, emoji: '🔍', accent: '16,185,129' },     // emerald
  { id: 'result', label: 'Reporting', x: 650, y: 100, emoji: '📊', accent: '245,158,11' }, // amber
];

const NODE_S = 64;
const NODE_R = 14;

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

export function PipelineBar() {
  const { analysisResult, liveSteps, analysisState } = useAppStore();
  const steps = (analysisState === 'completed' && analysisResult?.steps?.length)
    ? analysisResult.steps
    : liveSteps;

  const c = {
    line: '#d1d5db',
    lineActive: '#4f46e5',
    nodeOff: '#f1f5f9',
    nodeOffStroke: '#d1d5db',
    labelOff: '#9ca3af',
    labelOn: '#1f2937',
    badge: '#22c55e',
  };

  const isLineActive = (from: string) => getStepStatus(from, steps) === 'completed';

  const lineProps = (from: string, delay: number) => ({
    stroke: isLineActive(from) ? c.lineActive : c.line,
    strokeWidth: 2,
    fill: 'none' as const,
    initial: { pathLength: 0 } as const,
    animate: { pathLength: 1 } as const,
    transition: { duration: 0.5, delay },
  });

  return (
    <div style={{ width: '100%', overflowX: 'auto', paddingBottom: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: '760px' }}>
        <svg width="760" height="230" viewBox="0 0 760 230" style={{ display: 'block', margin: '0 auto' }}>
          {/* Lines: Upload -> BiCep */}
          <motion.line x1={90 + NODE_S / 2} y1="100" x2={270 - NODE_S / 2} y2="100" {...lineProps('upload', 0)} />

          {/* BiCep -> Policy */}
          <motion.path d={`M ${270 + NODE_S / 2} 100 C ${370} 100, ${400} 46, ${460 - NODE_S / 2} 46`} {...lineProps('bicep', 0.1)} />

          {/* BiCep -> Recon */}
          <motion.path d={`M ${270 + NODE_S / 2} 100 C ${370} 100, ${400} 154, ${460 - NODE_S / 2} 154`} {...lineProps('bicep', 0.1)} />

          {/* Policy -> Result */}
          <motion.path d={`M ${460 + NODE_S / 2} 46 C ${560} 46, ${590} 100, ${650 - NODE_S / 2} 100`} {...lineProps('policy', 0.2)} />

          {/* Recon -> Result */}
          <motion.path d={`M ${460 + NODE_S / 2} 154 C ${560} 154, ${590} 100, ${650 - NODE_S / 2} 100`} {...lineProps('recon', 0.2)} />

          {/* Step nodes */}
          {STEPS.map((step, index) => {
            const status = getStepStatus(step.id, steps);
            const isActive = status === 'in_progress' || status === 'completed';
            const isCompleted = status === 'completed';
            const isRunning = status === 'in_progress';

            return (
              <g key={step.id}>
                {/* Node background */}
                <motion.rect
                  x={step.x - NODE_S / 2}
                  y={step.y - NODE_S / 2}
                  width={NODE_S}
                  height={NODE_S}
                  rx={NODE_R}
                  ry={NODE_R}
                  fill={isActive ? `rgba(${step.accent},0.08)` : c.nodeOff}
                  stroke={isActive ? `rgba(${step.accent},0.6)` : c.nodeOffStroke}
                  strokeWidth={1.5}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: index * 0.08, type: 'spring', stiffness: 200 }}
                />

                {/* Emoji */}
                <foreignObject
                  x={step.x - NODE_S / 2}
                  y={step.y - NODE_S / 2}
                  width={NODE_S}
                  height={NODE_S}
                >
                  <div style={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '26px',
                    lineHeight: 1,
                    filter: isActive ? 'none' : 'grayscale(0.6) opacity(0.5)',
                    transition: 'filter 0.3s ease',
                  }}>
                    {step.emoji}
                  </div>
                </foreignObject>

                {/* Status badge: green check or spinner */}
                {isCompleted && (
                  <g>
                    <circle
                      cx={step.x + NODE_S / 2 - 4}
                      cy={step.y - NODE_S / 2 + 4}
                      r={9}
                      fill={c.badge}
                      stroke="#ffffff"
                      strokeWidth={2}
                    />
                    <text
                      x={step.x + NODE_S / 2 - 4}
                      y={step.y - NODE_S / 2 + 4}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="white"
                      fontSize="10"
                      fontWeight="bold"
                    >
                      ✓
                    </text>
                  </g>
                )}

                {isRunning && (
                  <foreignObject
                    x={step.x + NODE_S / 2 - 14}
                    y={step.y - NODE_S / 2 - 6}
                    width={20}
                    height={20}
                  >
                    <div style={{
                      width: '20px',
                      height: '20px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: '#ffffff',
                      borderRadius: '50%',
                      border: `2px solid ${c.lineActive}`,
                    }}>
                      <Loader2
                        style={{
                          width: 12,
                          height: 12,
                          color: c.lineActive,
                          animation: 'pf-spin 1s linear infinite',
                        }}
                      />
                    </div>
                  </foreignObject>
                )}

                {/* Label */}
                <text
                  x={step.x}
                  y={step.y + NODE_S / 2 + 18}
                  textAnchor="middle"
                  fill={isActive ? c.labelOn : c.labelOff}
                  fontSize="13"
                  fontWeight="500"
                  fontFamily="'DM Sans', sans-serif"
                >
                  {step.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
