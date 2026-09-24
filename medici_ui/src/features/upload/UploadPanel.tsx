import { Camera, Check, ChevronDown, FileUp, Search, Upload, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { useUploadDocumentMutation } from '@/api/apiSlice';
import { Button } from '@/components/Button';
import { Spinner } from '@/components/Spinner';
import { addUploadedDoc } from '@/features/upload/uploadSlice';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import type { ParseMethod } from '@/types';
import {
  ALLOWED_FILE_TYPES,
  DEFAULT_PARSE_METHOD,
  MAX_FILE_SIZE_MB,
  PARSE_METHOD_LABELS,
} from '@/utils/constants';
import { formatFileSize, formatRelativeTime } from '@/utils/formatters';
import { Icon } from '@iconify/react';

type UploadPhase = 'idle' | 'uploading' | 'processing';

// How long to show "Uploading…" before switching the label to "Processing…".
// We don't get real upload-progress events from the mutation, so this just
// gives the user a sense that the file is on its way before parsing starts.
const PROCESSING_LABEL_DELAY_MS = 900;

export function UploadPanel() {
  const dispatch = useAppDispatch();
  const uploadedDocs = useAppSelector((s) => s.upload.uploadedDocs);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const parseMethodRef = useRef<HTMLDivElement>(null);
  const previewPopupRef = useRef<HTMLDivElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parseMethod, setParseMethod] = useState<ParseMethod>(DEFAULT_PARSE_METHOD);
  const [error, setError] = useState<string | null>(null);
  const [showOptions, setShowOptions] = useState(false);
  const [showParseMethodPopup, setShowParseMethodPopup] = useState(false);
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>('idle');

  const [uploadDocument, { isLoading }] = useUploadDocumentMutation();

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowOptions(false);
      }
      if (
        parseMethodRef.current &&
        !parseMethodRef.current.contains(e.target as Node)
      ) {
        setShowParseMethodPopup(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setShowOptions(false);
        setShowParseMethodPopup(false);
      }
    }
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const handleFileSelect = useCallback((file: File) => {
    setError(null);

    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!ALLOWED_FILE_TYPES.includes(ext as (typeof ALLOWED_FILE_TYPES)[number])) {
      setError(`Unsupported format. Allowed: ${ALLOWED_FILE_TYPES.join(', ')}`);
      return;
    }

    const sizeMb = file.size / (1024 * 1024);
    if (sizeMb > MAX_FILE_SIZE_MB) {
      setError(`File too large: ${sizeMb.toFixed(1)} MB. Max: ${MAX_FILE_SIZE_MB} MB`);
      return;
    }

    setSelectedFile(file);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect]
  );

  const handleUpload = async () => {
    if (!selectedFile) return;
    setError(null);
    setUploadPhase('uploading');

    const docId = uuidv4();

    const processingTimer = setTimeout(() => {
      setUploadPhase('processing');
    }, PROCESSING_LABEL_DELAY_MS);

    try {
      await uploadDocument({
        file: selectedFile,
        parseMethod,
        docId,
      }).unwrap();

      dispatch(
        addUploadedDoc({
          name: selectedFile.name,
          docId,
          method: parseMethod,
          timestamp: Date.now(),
        })
      );

      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ??
        'Upload failed. Please try again.';
      setError(msg);
    } finally {
      clearTimeout(processingTimer);
      setUploadPhase('idle');
    }
  };

  const handleCancelPreview = () => {
    if (isLoading) return;
    setSelectedFile(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleAddFilesClick = () => {
    setShowOptions(false);
    fileInputRef.current?.click();
  };

  const handleScreenshotClick = () => {
    setShowOptions(false);
    // TODO: wire up screenshot capture
  };

  const handleWebSearchClick = () => {
    setShowOptions(false);
    // TODO: wire up web search
  };

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setShowOptions((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={showOptions}
        aria-label="Add"
        className="flex items-center justify-center h-9 w-9 rounded-full text-text-secondary hover:text-text-primary hover:bg-surface-700 hover:cursor-pointer transition-colors"
      >
        <Icon icon="fluent:add-12-filled" height={20} width={20} />
      </button>

      {showOptions && (
        <div
          role="menu"
          className="absolute left-0 bottom-full mb-2 w-56 rounded-lg border border-glass-border bg-surface-800 shadow-lg py-1 z-10 animate-[fade-in_0.15s_ease-out]"
        >
          <button
            type="button"
            role="menuitem"
            onClick={handleAddFilesClick}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-secondary hover:bg-surface-700 hover:text-text-primary hover:cursor-pointer"
          >
            <FileUp className="h-3.5 w-3.5" />
            Add files or photos
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={handleScreenshotClick}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-secondary hover:bg-surface-700 hover:text-text-primary hover:cursor-pointer"
          >
            <Camera className="h-3.5 w-3.5" />
            Take a screenshot
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={handleWebSearchClick}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-secondary hover:bg-surface-700 hover:text-text-primary hover:cursor-pointer"
          >
            <Search className="h-3.5 w-3.5" />
            Web search
          </button>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_FILE_TYPES.map((t) => `.${t}`).join(',')}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileSelect(file);
        }}
        className="hidden"
      />

      {selectedFile && (
        <div
          ref={previewPopupRef}
          className="absolute left-0 bottom-full mb-2 w-72 rounded-lg border border-glass-border bg-surface-800 shadow-lg p-3 z-20 animate-[fade-in_0.2s_ease-out]"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">
              Upload
            </span>
            <button
              type="button"
              onClick={handleCancelPreview}
              aria-label="Cancel"
              disabled={isLoading}
              className="text-text-muted hover:text-text-primary hover:cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="flex items-center gap-2 text-xs text-text-secondary bg-surface-900/40 rounded-lg px-3 py-2">
            <Upload className="h-3.5 w-3.5 text-primary-light shrink-0" />
            <span className="truncate flex-1">{selectedFile.name}</span>
            <span className="text-text-muted shrink-0">
              {formatFileSize(selectedFile.size)}
            </span>
          </div>

          <div className="relative mt-2" ref={parseMethodRef}>
            <label className="text-xs text-text-muted mb-1 block">Parse Method</label>
            <button
              type="button"
              onClick={() => setShowParseMethodPopup((prev) => !prev)}
              aria-haspopup="menu"
              aria-expanded={showParseMethodPopup}
              disabled={isLoading}
              className="w-full flex items-center justify-between bg-surface-900/40 border border-glass-border rounded-lg px-3 py-1.5 text-xs text-text-primary hover:bg-surface-700 hover:cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary-light transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <span>{PARSE_METHOD_LABELS[parseMethod]}</span>
              <ChevronDown
                className={`h-3.5 w-3.5 text-text-muted transition-transform ${
                  showParseMethodPopup ? 'rotate-180' : ''
                }`}
              />
            </button>

            {showParseMethodPopup && (
              <div
                role="menu"
                className="absolute left-0 bottom-full mb-2 w-full rounded-lg border border-glass-border bg-surface-800 shadow-lg py-1 z-30 animate-[fade-in_0.15s_ease-out]"
              >
                {Object.entries(PARSE_METHOD_LABELS).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setParseMethod(value as ParseMethod);
                      setShowParseMethodPopup(false);
                    }}
                    className="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs text-text-secondary hover:bg-surface-700 hover:text-text-primary hover:cursor-pointer"
                  >
                    <span>{label}</span>
                    {value === parseMethod && (
                      <Check className="h-3.5 w-3.5 text-primary-light shrink-0" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          <Button
            variant="primary"
            size="sm"
            fullWidth
            className="mt-3"
            disabled={isLoading}
            onClick={handleUpload}
          >
            {isLoading ? (
              <>
                <Spinner size="sm" />
                {uploadPhase === 'processing' ? 'Processing…' : 'Uploading…'}
              </>
            ) : (
              <>
                <Upload className="h-3.5 w-3.5" />
                Upload Document
              </>
            )}
          </Button>

          {error && (
            <p className="mt-2 text-xs text-error animate-[fade-in_0.2s_ease-out]">
              {error}
            </p>
          )}
        </div>
      )}

      {uploadedDocs.length > 0 && (
        <div className="mt-4">
          <p className="text-[10px] text-text-muted uppercase tracking-wider mb-2">
            Uploaded ({uploadedDocs.length})
          </p>
          <div className="space-y-1.5 max-h-32 overflow-y-auto">
            {uploadedDocs.map((doc) => (
              <div
                key={doc.docId}
                className="flex items-center gap-2 text-xs text-text-secondary bg-surface-800 rounded-lg px-2.5 py-1.5"
              >
                <span className="text-success text-[10px]">✓</span>
                <span className="truncate flex-1">{doc.name}</span>
                <span className="text-text-muted text-[10px] shrink-0">
                  {formatRelativeTime(doc.timestamp)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
