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

  const { uploadedFile, skipPolicy, setUploadedFile, setSkipPolicy, analysisState } = useAppStore();

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

  return (
    <div style={{ opacity: isAnalyzing ? 0.5 : 1, pointerEvents: isAnalyzing ? 'none' : 'auto', transition: 'opacity 0.3s' }}>
      {/* Upload zone card */}
      <div style={{
        background: 'var(--pf-surface)',
        border: '1px solid var(--pf-border)',
        borderRadius: '20px',
        padding: '24px',
        backdropFilter: 'blur(20px)',
      }}>
        {/* Section label */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <div style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: 'var(--pf-accent)',
            boxShadow: '0 0 8px var(--pf-accent-shadow)',
          }} />
          <span style={{
            fontSize: '12px', fontWeight: 600, color: 'var(--pf-text-3)',
            fontFamily: "'DM Sans', sans-serif",
            textTransform: 'uppercase', letterSpacing: '0.08em',
          }}>
            Architecture Diagram
          </span>
        </div>

        {/* Drop zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => !uploadedFile && inputRef.current?.click()}
          style={{
            position: 'relative',
            border: `1.5px dashed ${isDragOver ? 'var(--pf-border-dashed-hover)' : uploadedFile ? 'var(--pf-border-dashed-file)' : 'var(--pf-border-dashed)'}`,
            borderRadius: '16px',
            padding: uploadedFile ? '0' : '48px 32px',
            textAlign: 'center',
            cursor: uploadedFile ? 'default' : 'pointer',
            background: isDragOver
              ? 'var(--pf-accent-drag-bg)'
              : uploadedFile
                ? 'var(--pf-surface-subtle)'
                : 'var(--pf-surface-inset)',
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            overflow: 'hidden',
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".png,.jpg,.jpeg"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            style={{ display: 'none' }}
          />

          {!uploadedFile ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '56px', height: '56px', borderRadius: '14px',
                background: `linear-gradient(135deg, var(--pf-accent-gradient-from), var(--pf-accent-gradient-to))`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '22px',
              }}>
                📐
              </div>
              <div>
                <p style={{
                  margin: 0, fontSize: '14px', fontWeight: 500, color: 'var(--pf-text-2)',
                  fontFamily: "'DM Sans', sans-serif",
                }}>
                  아키텍처 다이어그램을 드래그하거나 클릭하여 업로드
                </p>
                <p style={{
                  margin: '8px 0 0', fontSize: '12px', color: 'var(--pf-text-4)',
                  fontFamily: "'DM Sans', sans-serif",
                }}>
                  PNG, JPG · 최대 20MB
                </p>
              </div>
            </div>
          ) : (
            <div>
              {/* Preview */}
              <div style={{ padding: '16px 16px 0', position: 'relative' }}>
                <div style={{
                  borderRadius: '10px', overflow: 'hidden',
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
              </div>

              {/* File info bar */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '14px 20px',
                borderTop: '1px solid var(--pf-border-muted)',
                marginTop: '16px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '8px',
                    background: `linear-gradient(135deg, var(--pf-file-icon-from), var(--pf-file-icon-to))`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px',
                  }}>
                    🖼
                  </div>
                  <div>
                    <p style={{
                      margin: 0, fontSize: '13px', fontWeight: 500, color: 'var(--pf-text-2)',
                      fontFamily: "'DM Mono', monospace", letterSpacing: '-0.01em',
                      maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {uploadedFile.name}
                    </p>
                    <p style={{
                      margin: '2px 0 0', fontSize: '11px', color: 'var(--pf-text-4)',
                      fontFamily: "'DM Sans', sans-serif",
                    }}>
                      {(uploadedFile.size / (1024 * 1024)).toFixed(1)} MB
                    </p>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setUploadedFile(null); }}
                  className="pf-btn-change"
                  style={{
                    padding: '6px 14px', borderRadius: '8px',
                    border: '1px solid var(--pf-btn-border)',
                    background: 'var(--pf-btn-bg)',
                    color: 'var(--pf-btn-text)', fontSize: '12px', cursor: 'pointer',
                    fontFamily: "'DM Sans', sans-serif", transition: 'all 0.2s',
                  }}
                >
                  변경
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Options & CTA */}
      <div style={{ marginTop: '16px' }}>
        {/* Skip Policy Toggle */}
        <div
          onClick={() => setSkipPolicy(!skipPolicy)}
          style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '14px 20px', borderRadius: '12px',
            background: 'var(--pf-surface-subtle)',
            border: '1px solid var(--pf-border-subtle)',
            cursor: 'pointer', transition: 'all 0.2s',
          }}
        >
          <div style={{
            width: '36px', height: '20px', borderRadius: '10px',
            background: skipPolicy
              ? `linear-gradient(135deg, var(--pf-accent), var(--pf-accent-hover))`
              : 'var(--pf-toggle-off)',
            position: 'relative', transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            flexShrink: 0,
            boxShadow: skipPolicy ? '0 0 12px var(--pf-accent-shadow)' : 'none',
          }}>
            <div style={{
              position: 'absolute', top: '2px',
              left: skipPolicy ? '18px' : '2px',
              width: '16px', height: '16px', borderRadius: '50%',
              background: '#fff',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            }} />
          </div>
          <div>
            <span style={{
              fontSize: '13px', fontWeight: 500, color: 'var(--pf-text-2)',
              fontFamily: "'DM Sans', sans-serif",
            }}>
              Skip Policy Validation
            </span>
            <p style={{
              margin: '2px 0 0', fontSize: '11px', color: 'var(--pf-text-4)',
              fontFamily: "'DM Sans', sans-serif",
            }}>
              정책 검증 단계를 건너뛰고 바로 취약점 분석을 수행합니다
            </p>
          </div>
        </div>

        {/* CTA Button */}
        <button
          disabled={!uploadedFile || isAnalyzing}
          onClick={onStartAnalysis}
          onMouseEnter={() => setIsHovering(true)}
          onMouseLeave={() => setIsHovering(false)}
          style={{
            width: '100%', marginTop: '12px',
            padding: '16px 24px', borderRadius: '14px', border: 'none',
            background: isHovering
              ? `linear-gradient(135deg, var(--pf-accent), var(--pf-accent-hover))`
              : `linear-gradient(135deg, var(--pf-accent-deep), var(--pf-accent))`,
            color: '#fff', fontSize: '15px', fontWeight: 600,
            fontFamily: "'DM Sans', sans-serif",
            cursor: uploadedFile && !isAnalyzing ? 'pointer' : 'not-allowed',
            opacity: uploadedFile && !isAnalyzing ? 1 : 0.5,
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
            letterSpacing: '-0.01em',
            boxShadow: isHovering && uploadedFile
              ? 'var(--pf-cta-shadow-hover)'
              : 'var(--pf-cta-shadow)',
            transform: isHovering && uploadedFile ? 'translateY(-1px)' : 'translateY(0)',
          }}
        >
          {isAnalyzing ? (
            <>
              <span className="pf-spinner" />
              분석 중...
            </>
          ) : (
            <>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 14V2M3 7l5-5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              분석 시작
            </>
          )}
        </button>
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
