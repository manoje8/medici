import type { ParseMethod } from '@/types';

export const STAGE_ICONS: Record<string, string> = {
  rewrite_query: '✏️',
  route: '🔀',
  plan: '📋',
  retrieve: '🔍',
  hop_check: '⚖️',
  grade: '📊',
  rewrite_for_refinement: '🔄',
  synthesize: '✨',
  direct_synthesize: '✨',
  handle_simple_response: '💬',
};

export const PARSE_METHOD_LABELS: Record<ParseMethod, string> = {
  google_doc_ai: 'Google Doc AI',
  docling: 'Docling',
  docling_md: 'Docling Markdown',
  python_docx: 'Python Docx',
};

export const ALLOWED_FILE_TYPES = ['pdf', 'txt', 'md', 'docx'] as const;

export const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'text/plain',
  'text/markdown',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
] as const;

export const MAX_FILE_SIZE_MB = 50;

export const HEALTH_CHECK_INTERVAL_MS = 30_000;

export const API_BASE_URL = '/api';

export const DEFAULT_PARSE_METHOD: ParseMethod = 'docling';

export const PROJECT_NAME = 'Medici';
