import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import { useAppStore } from '@/store/app';
import type { StepStatus } from '@/types/api';

const STEPS = [
  { id: 'upload', label: 'Upload', x: 80, y: 80, color: '#3b82f6' },
  { id: 'bicep', label: 'BiCep', x: 280, y: 80, color: '#3b82f6' },
  { id: 'policy', label: 'Policy', x: 480, y: 40, color: '#f97316' },
  { id: 'recon', label: 'Recon', x: 480, y: 120, color: '#10b981' },
  { id: 'result', label: 'Reporting', x: 680, y: 80, color: '#f59e0b' },
];

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

const getHexagonPath = (cx: number, cy: number, size: number) => {
  const points = [];
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 3) * i - Math.PI / 2;
    const x = cx + size * Math.cos(angle);
    const y = cy + size * Math.sin(angle);
    points.push(`${x},${y}`);
  }
  return `M ${points.join(' L ')} Z`;
};

export function PipelineBar() {
  const { analysisResult, liveSteps, analysisState, theme } = useAppStore();
  const steps = (analysisState === 'completed' && analysisResult?.steps?.length)
    ? analysisResult.steps
    : liveSteps;

  const isDark = theme === 'dark';

  // Theme-aware colors for SVG (CSS vars don't work in SVG attributes)
  const c = {
    line: isDark ? 'rgba(51,65,85,0.5)' : '#d1d5db',
    lineActive: isDark ? '#a5b4fc' : '#1f2937',
    arrow: isDark ? 'rgba(51,65,85,0.5)' : '#d1d5db',
    arrowActive: isDark ? '#a5b4fc' : '#1f2937',
    nodeOff: isDark ? '#1e293b' : '#e5e7eb',
    nodeOffStroke: isDark ? '#334155' : '#d1d5db',
    labelOff: isDark ? '#64748b' : '#9ca3af',
    labelOn: isDark ? '#e2e8f0' : '#1f2937',
    iconPending: isDark ? '#4b5563' : '#d1d5db',
  };

  const StepIcon = ({ status, size = 16 }: { status: StepStatus['status']; size?: number }) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="text-white" style={{ width: size, height: size }} />;
      case 'in_progress':
        return <Loader2 className="text-white animate-spin" style={{ width: size, height: size }} />;
      case 'error':
        return <XCircle className="text-red-500" style={{ width: size, height: size }} />;
      default:
        return <Circle style={{ width: size, height: size, color: c.iconPending }} />;
    }
  };

  const isLineActive = (from: string) => getStepStatus(from, steps) === 'completed';

  return (
    <div className="w-full overflow-x-auto pb-4">
      <div className="flex items-center justify-center min-w-[800px]">
        <svg width="800" height="180" viewBox="0 0 800 180" className="mx-auto">
          <defs>
            <marker id="arr" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
              <polygon points="0 0, 10 3, 0 6" fill={c.arrow} />
            </marker>
            <marker id="arr-on" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
              <polygon points="0 0, 10 3, 0 6" fill={c.arrowActive} />
            </marker>
          </defs>

          {/* Upload -> BiCep */}
          <motion.line
            x1="120" y1="80" x2="240" y2="80"
            stroke={isLineActive('upload') ? c.lineActive : c.line}
            strokeWidth="2"
            markerEnd={isLineActive('upload') ? 'url(#arr-on)' : 'url(#arr)'}
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
            transition={{ duration: 0.5 }}
          />

          {/* BiCep -> Policy */}
          <motion.path
            d="M 320 80 L 360 80 L 440 40"
            stroke={isLineActive('bicep') ? c.lineActive : c.line}
            strokeWidth="2" fill="none"
            markerEnd={isLineActive('bicep') ? 'url(#arr-on)' : 'url(#arr)'}
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          />

          {/* BiCep -> Recon */}
          <motion.path
            d="M 320 80 L 360 80 L 440 120"
            stroke={isLineActive('bicep') ? c.lineActive : c.line}
            strokeWidth="2" fill="none"
            markerEnd={isLineActive('bicep') ? 'url(#arr-on)' : 'url(#arr)'}
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          />

          {/* Policy -> Result */}
          <motion.path
            d="M 520 40 L 560 40 L 640 80"
            stroke={isLineActive('policy') ? c.lineActive : c.line}
            strokeWidth="2" fill="none"
            markerEnd={isLineActive('policy') ? 'url(#arr-on)' : 'url(#arr)'}
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          />

          {/* Recon -> Result */}
          <motion.path
            d="M 520 120 L 560 120 L 640 80"
            stroke={isLineActive('recon') ? c.lineActive : c.line}
            strokeWidth="2" fill="none"
            markerEnd={isLineActive('recon') ? 'url(#arr-on)' : 'url(#arr)'}
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          />

          {/* Step nodes */}
          {STEPS.map((step, index) => {
            const status = getStepStatus(step.id, steps);
            const isActive = status === 'in_progress' || status === 'completed';

            return (
              <g key={step.id}>
                <motion.path
                  d={getHexagonPath(step.x, step.y, 28)}
                  fill={isActive ? step.color : c.nodeOff}
                  stroke={isActive ? step.color : c.nodeOffStroke}
                  strokeWidth="2"
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: index * 0.1, type: 'spring', stiffness: 200 }}
                />

                <foreignObject x={step.x - 8} y={step.y - 8} width="16" height="16">
                  <div className="flex items-center justify-center w-full h-full">
                    <StepIcon status={status} size={16} />
                  </div>
                </foreignObject>

                <text
                  x={step.x} y={step.y + 45}
                  textAnchor="middle"
                  className="text-xs font-medium"
                  fill={isActive ? c.labelOn : c.labelOff}
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
