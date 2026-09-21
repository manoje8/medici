/* ── Types ── */

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  confidence?: number;
  confidenceNote?: string;
  cacheHit?: boolean;
  sources?: string[];
}

export interface Citation {
  path: string;
  section: string;
  filename: string;
  index: number;
}

export interface UploadedDoc {
  name: string;
  docId: string;
  method: string;
  timestamp: number;
}

export interface SSEEvent {
  type: 'progress' | 'token' | 'done' | 'error' | 'stream_break';
  node?: string;
  message?: string;
  content?: string;
  answer?: string;
  sources?: string[];
  cache_hit?: boolean;
  cache_similarity?: number;
  token_usage?: Record<string, unknown>;
  query_was_rewritten?: boolean;
  session_id?: string;
  images?: string[];
}

export interface PipelineStage {
  id: string;
  node: string;
  message: string;
  icon: string;
  timestamp: number;
}

export interface HealthStatus {
  status: 'ok' | 'degraded';
  service: string;
  dependencies: Record<string, string>;
}

export interface AuthStatus {
  auth_configured: boolean;
  access_token?: string;
  token_type?: string;
  auth_mode: boolean;
  message?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  auth_mode: boolean;
  auth_configured?: boolean;
  message?: string;
}

export type ParseMethod =
  | 'google_doc_ai'
  | 'docling'
  | 'docling_md'
  | 'python_docx';

export interface QueryResponse {
  answer: string;
  session_id: string;
  sources: string[];
  images: string[];
  query_was_rewritten: boolean;
  cache_hit: boolean;
  cache_similarity?: number;
  token_usage: Record<string, unknown>;
}
