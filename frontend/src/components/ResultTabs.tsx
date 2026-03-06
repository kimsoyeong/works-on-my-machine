import { motion } from 'framer-motion';
import { Download, FileCode } from 'lucide-react';
import { useAppStore } from '@/store/app';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const downloadBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '8px',
  padding: '10px 20px',
  background: 'var(--pf-surface)',
  border: '1px solid var(--pf-accent-faint-border)',
  borderRadius: '12px',
  color: 'var(--pf-accent-text)',
  fontSize: '14px',
  fontWeight: 500,
  fontFamily: "'DM Sans', sans-serif",
  cursor: 'pointer',
  transition: 'all 0.2s ease',
};

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ResultTabs() {
  const { analysisResult } = useAppStore();

  if (!analysisResult?.security) {
    return null;
  }

  const report = analysisResult.security?.final_report || '';
  const improvedBicep = analysisResult.security?.improved_bicep_code || '';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ width: '100%', maxWidth: '56rem', margin: '0 auto' }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '16px',
      }}>
        <h2 style={{
          fontSize: '20px',
          fontWeight: 700,
          color: 'var(--pf-text-1)',
          fontFamily: "'Outfit', sans-serif",
          paddingLeft: '14px',
          borderLeft: '3px solid var(--pf-accent)',
          margin: 0,
        }}>
          Security Report
        </h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => downloadBlob(report, 'security_report.md', 'text/markdown')}
            style={downloadBtnStyle}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--pf-accent)';
              e.currentTarget.style.background = 'var(--pf-accent-faint-bg)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--pf-accent-faint-border)';
              e.currentTarget.style.background = 'var(--pf-surface)';
            }}
          >
            <Download style={{ width: 16, height: 16 }} />
            Report
          </button>
          {improvedBicep && (
            <button
              onClick={() => downloadBlob(improvedBicep, 'improved.bicep', 'text/plain')}
              style={downloadBtnStyle}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--pf-accent)';
                e.currentTarget.style.background = 'var(--pf-accent-faint-bg)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--pf-accent-faint-border)';
                e.currentTarget.style.background = 'var(--pf-surface)';
              }}
            >
              <FileCode style={{ width: 16, height: 16 }} />
              Improved Bicep
            </button>
          )}
        </div>
      </div>

      <div style={{
        background: 'var(--pf-surface)',
        border: '1px solid var(--pf-border)',
        borderRadius: '16px',
        padding: '28px',
        overflowY: 'auto',
      }}>
        <div className="pf-report">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
        </div>
      </div>
    </motion.div>
  );
}
