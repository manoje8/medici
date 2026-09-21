import type { Citation } from '@/types';

/**
 * Regex to match inline source citations:
 *   [Source: path/to/file | Section: section_name]
 */
const INLINE_SOURCE_RE =
  /\[Source:\s*(?<path>[^|\]]+?)\s*\|\s*Section:\s*(?<section>[^\]]+?)\s*\]/g;

/**
 * Regex to match confidence level lines:
 *   Confidence level: 85% (Based on multiple corroborating sources)
 */
const CONFIDENCE_RE =
  /Confidence level:\s*(?<pct>\d+)%\s*\((?<note>[^)]+)\)/i;

/**
 * Extract the basename from a file path, handling both Unix and Windows separators.
 */
function basename(filePath: string): string {
  const parts = filePath.replace(/\\/g, '/').split('/');
  return parts[parts.length - 1] ?? filePath;
}

export interface ParsedAnswer {
  cleanText: string;
  citations: Citation[];
  confidence: number | null;
  confidenceNote: string;
}

/**
 * Port of the Streamlit `ChatRenderer._parse_answer` method.
 *
 * Extracts inline `[Source: ... | Section: ...]` citations and
 * `Confidence level: N% (note)` metadata from a raw answer string.
 */
export function parseAnswer(raw: string): ParsedAnswer {
  const seen = new Map<string, number>();
  const citations: Citation[] = [];

  // Replace inline citations with numbered references [1], [2], ...
  const withRefs = raw.replace(INLINE_SOURCE_RE, (_match, path: string, section: string) => {
    const key = `${path.trim()}|||${section.trim()}`;
    if (!seen.has(key)) {
      const index = citations.length + 1;
      seen.set(key, index);
      citations.push({
        path: path.trim(),
        section: section.trim(),
        filename: basename(path.trim()),
        index,
      });
    }
    return `[${seen.get(key)}]`;
  });

  // Extract confidence metadata
  let confidence: number | null = null;
  let confidenceNote = '';
  const confMatch = CONFIDENCE_RE.exec(withRefs);
  let cleanText = withRefs;

  if (confMatch?.groups) {
    confidence = parseInt(confMatch.groups.pct, 10);
    confidenceNote = confMatch.groups.note.trim();
    cleanText = withRefs.replace(CONFIDENCE_RE, '').trim();
  }

  return { cleanText, citations, confidence, confidenceNote };
}

/**
 * Determine confidence CSS class and icon based on percentage.
 */
export function getConfidenceLevel(pct: number): {
  level: 'high' | 'medium' | 'low';
  icon: string;
  label: string;
} {
  if (pct >= 75) return { level: 'high', icon: '✅', label: 'High confidence' };
  if (pct >= 45) return { level: 'medium', icon: '⚠️', label: 'Moderate confidence' };
  return { level: 'low', icon: '❌', label: 'Low confidence' };
}
