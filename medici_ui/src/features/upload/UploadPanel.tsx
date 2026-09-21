import { FileUp, Upload } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
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

export function UploadPanel() {
  const dispatch = useAppDispatch();
  const uploadedDocs = useAppSelector((s) => s.upload.uploadedDocs);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parseMethod, setParseMethod] = useState<ParseMethod>(DEFAULT_PARSE_METHOD);
  const [error, setError] = useState<string | null>(null);

  const [uploadDocument, { isLoading }] = useUploadDocumentMutation();

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

    const docId = uuidv4();

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
    }
  };

  return (
    <div>
      <h3 className="text-xs font-semibold text-text-muted tracking-wider uppercase mb-3">
        📄 Document Upload
      </h3>

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className="border-2 border-dashed border-glass-border hover:border-primary/40 rounded-xl p-4 text-center cursor-pointer transition-colors duration-200 group"
      >
        <FileUp className="h-6 w-6 mx-auto mb-2 text-text-muted group-hover:text-primary-light transition-colors" />
        <p className="text-xs text-text-muted">
          Drop file here or <span className="text-primary-light">browse</span>
        </p>
        <p className="text-[10px] text-text-muted/60 mt-1">
          {ALLOWED_FILE_TYPES.join(', ')} • Max {MAX_FILE_SIZE_MB} MB
        </p>
      </div>

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
        <div className="mt-3 animate-[fade-in_0.2s_ease-out]">
          <div className="flex items-center gap-2 text-xs text-text-secondary bg-surface-800 rounded-lg px-3 py-2">
            <Upload className="h-3.5 w-3.5 text-primary-light shrink-0" />
            <span className="truncate flex-1">{selectedFile.name}</span>
            <span className="text-text-muted shrink-0">
              {formatFileSize(selectedFile.size)}
            </span>
          </div>

          <div className="mt-2">
            <label className="text-xs text-text-muted mb-1 block">Parse Method</label>
            <select
              value={parseMethod}
              onChange={(e) => setParseMethod(e.target.value as ParseMethod)}
              className="w-full bg-surface-800 border border-glass-border rounded-lg px-3 py-1.5 text-xs text-text-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
            >
              {Object.entries(PARSE_METHOD_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
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
                Processing…
              </>
            ) : (
              <>
                <Upload className="h-3.5 w-3.5" />
                Upload Document
              </>
            )}
          </Button>
        </div>
      )}

      {error && (
        <p className="mt-2 text-xs text-error animate-[fade-in_0.2s_ease-out]">
          ❌ {error}
        </p>
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
                className="flex items-center gap-2 text-xs text-text-secondary bg-surface-900/50 rounded-lg px-2.5 py-1.5"
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
