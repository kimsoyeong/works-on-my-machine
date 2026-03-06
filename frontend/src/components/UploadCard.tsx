import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store/app';

const MAX_FILE_SIZE = 20 * 1024 * 1024;
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/jpg'];

interface UploadCardProps {
  onStartAnalysis?: () => void;
}

export function UploadCard({ onStartAnalysis }: UploadCardProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { uploadedFile, setUploadedFile, analysisState } = useAppStore();

  useEffect(() => {
    if (uploadedFile && uploadedFile.type.startsWith('image/')) {
      const url = URL.createObjectURL(uploadedFile);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setPreviewUrl(null);
    }
  }, [uploadedFile]);

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) return 'PNG, JPG 파일만 지원됩니다';
    if (file.size > MAX_FILE_SIZE) return '파일 크기는 20MB 이하여야 합니다';
    return null;
  };

  const handleFile = useCallback((file: File) => {
    const error = validateFile(file);
    if (error) { alert(error); return; }
    setUploadedFile(file);
  }, [setUploadedFile]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(e.type === 'dragenter' || e.type === 'dragover');
  }, []);

  const isAnalyzing = analysisState === 'analyzing';
  const canStart = !!uploadedFile && !isAnalyzing;

  return (
    <div style={{ opacity: isAnalyzing ? 0.5 : 1, pointerEvents: isAnalyzing ? 'none' : 'auto', transition: 'opacity 0.3s' }}>
      {/* Chat-input style card */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        style={{
          borderRadius: '20px',
          border: `1px solid ${isDragOver ? 'var(--pf-border-dashed-hover)' : 'rgba(0,0,0,0.08)'}`,
          background: isDragOver ? 'var(--pf-accent-drag-bg)' : 'var(--pf-surface)',
          backdropFilter: 'blur(20px)',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          overflow: 'hidden',
          boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".png,.jpg,.jpeg"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          style={{ display: 'none' }}
        />

        {/* Section header */}
        <div style={{ padding: '14px 18px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--pf-accent)' }} />
          <span style={{
            fontSize: '11px', fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase' as const,
            color: 'var(--pf-text-3)', fontFamily: "'DM Sans', sans-serif",
          }}>
            Architecture Diagram
          </span>
        </div>

        {/* Upper area — upload zone or preview */}
        {!uploadedFile ? (
          <div
            onClick={() => inputRef.current?.click()}
            style={{
              margin: '12px 16px 0',
              padding: '32px 24px',
              textAlign: 'center',
              cursor: 'pointer',
              borderRadius: '14px',
              border: `2px dashed ${isDragOver ? 'var(--pf-accent)' : 'rgba(0,0,0,0.1)'}`,
              background: isDragOver ? 'rgba(108,58,237,0.03)' : 'rgba(0,0,0,0.015)',
              transition: 'all 0.2s',
            }}
          >
            {/* Upload icon */}
            <div style={{
              width: '48px', height: '48px', borderRadius: '12px',
              background: 'rgba(0,0,0,0.04)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 14px',
            }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2M12 4v12M8 8l4-4 4 4" stroke="var(--pf-text-5)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <p style={{
              margin: 0, fontSize: '14px', color: 'var(--pf-text-3)',
              fontFamily: "'DM Sans', sans-serif", fontWeight: 500,
            }}>
              아키텍처 다이어그램을 드래그하거나 클릭하여 업로드
            </p>
            <p style={{
              margin: '6px 0 0', fontSize: '12px', color: 'var(--pf-text-5)',
              fontFamily: "'DM Sans', sans-serif",
            }}>
              PNG, JPG · 최대 20MB
            </p>
          </div>
        ) : (
          <div style={{ padding: '16px 16px 0' }}>
            {/* Image preview */}
            <div style={{
              borderRadius: '12px', overflow: 'hidden',
              background: 'var(--pf-preview-bg)',
              border: '1px solid var(--pf-preview-border)',
              position: 'relative',
            }}>
              {previewUrl && (
                <img
                  src={previewUrl}
                  alt="preview"
                  style={{ width: '100%', display: 'block', maxHeight: '200px', objectFit: 'contain' }}
                />
              )}
              {/* Scanline overlay */}
              <div style={{
                position: 'absolute', inset: 0,
                background: `repeating-linear-gradient(0deg, transparent, transparent 2px, var(--pf-scanline) 2px, var(--pf-scanline) 4px)`,
                pointerEvents: 'none',
              }} />
            </div>

            {/* File info */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '12px 4px 0',
            }}>
              <div style={{
                width: '24px', height: '24px', borderRadius: '50%',
                background: '#22c55e',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                  <path d="M3.5 8.5L6.5 11.5L12.5 4.5" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p style={{
                margin: 0, fontSize: '13px', fontWeight: 500, color: 'var(--pf-text-3)',
                fontFamily: "'DM Mono', monospace",
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                flex: 1,
              }}>
                {uploadedFile.name}
              </p>
              <button
                onClick={(e) => { e.stopPropagation(); setUploadedFile(null); }}
                className="pf-btn-change"
                style={{
                  padding: '4px 12px', borderRadius: '8px',
                  border: '1px solid var(--pf-btn-border)',
                  background: 'var(--pf-btn-bg)',
                  color: 'var(--pf-btn-text)', fontSize: '11px', cursor: 'pointer',
                  fontFamily: "'DM Sans', sans-serif", transition: 'all 0.2s',
                  flexShrink: 0,
                }}
              >
                변경
              </button>
            </div>
          </div>
        )}

        {/* Bottom bar — file info left, send button right */}
        <div style={{
          display: 'flex', justifyContent: uploadedFile ? 'space-between' : 'flex-end', alignItems: 'center',
          padding: '12px 16px',
        }}>
          {uploadedFile && (
            <span style={{
              fontSize: '12px', color: 'var(--pf-text-5)',
              fontFamily: "'DM Sans', sans-serif",
            }}>
              {`${(uploadedFile.size / (1024 * 1024)).toFixed(1)} MB`}
            </span>
          )}

          {/* Circular send button */}
          <button
            disabled={!canStart}
            onClick={onStartAnalysis}
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => setIsHovering(false)}
            style={{
              width: '36px', height: '36px', borderRadius: '10px',
              border: 'none',
              background: canStart
                ? (isHovering ? '#8B5CF6' : '#6C3AED')
                : 'var(--pf-border)',
              cursor: canStart ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.2s ease',
              boxShadow: 'none',
              flexShrink: 0,
            }}
          >
            {isAnalyzing ? (
              <span className="pf-spinner" />
            ) : (
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 13V3M4 7l4-4 4 4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes pf-spin { to { transform: rotate(360deg); } }
        .pf-spinner {
          width: 14px; height: 14px; border-radius: 50%;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          display: inline-block;
          animation: pf-spin 0.8s linear infinite;
        }
        .pf-btn-change:hover {
          border-color: rgba(239,68,68,0.4) !important;
          color: #f87171 !important;
        }
      `}</style>
    </div>
  );
}
