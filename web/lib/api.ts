// Relative by default: the browser talks to Next.js on the same origin,
// which proxies /api/* to FastAPI internally. For local development
// against a separately-hosted backend, set NEXT_PUBLIC_API_URL
// (e.g. http://127.0.0.1:8000).
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export const EXAMINATIONS = [
  "PT 1",
  "PT 2",
  "Half Yearly Examination",
  "Annual Examination",
] as const;

export const CLASSES = [
  "I",
  "II",
  "III",
  "IV",
  "V",
  "VI",
  "VII",
  "VIII",
  "IX",
  "X",
  "XI",
  "XII",
] as const;

export interface PaperSettingsInput {
  examination: string;
  session: string;
  class_name: string;
  subject: string;
  subject_code: string;
  max_marks: string;
  time: string;
}

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  source_blocks: number[];
  question_number: number | null;
  section: string | null;
  details: Record<string, unknown>;
}

export interface SpellingSuggestion {
  original: string;
  suggested: string;
  source_blocks: number[];
  question_number: number | null;
  context: string;
  confidence: string;
  status: string;
}

export interface AnalyzeResponse {
  filename: string;
  summary: {
    sections: number;
    questions: number;
    instructions: number;
    has_instructions: boolean;
    spelling_suggestions: number;
    has_errors: boolean;
  };
  validation: {
    errors: ValidationIssue[];
    warnings: ValidationIssue[];
    info: ValidationIssue[];
    summary: {
      total: number;
      errors: number;
      warnings: number;
      info: number;
      has_errors: boolean;
    };
  };
  spelling: {
    suggestions: SpellingSuggestion[];
    summary: {
      total_suggestions: number;
      texts_checked: number;
      words_checked: number;
      custom_dictionary_size: number;
    };
  };
}

async function friendlyError(res: Response, fallback: string): Promise<Error> {
  try {
    const data = await res.json();
    const message = data?.error?.message;
    if (typeof message === "string" && message.length > 0) return new Error(message);
  } catch {
    /* fall through */
  }
  return new Error(fallback);
}

export async function analyzePaper(file: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file, file.name);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: form });
  } catch {
    throw new Error(
      "Could not reach the processing server. Please make sure it is running and try again."
    );
  }
  if (!res.ok) {
    throw await friendlyError(
      res,
      "Unable to read the question paper. Please check that the DOCX file is valid."
    );
  }
  return res.json();
}

export interface GeneratedPaper {
  blob: Blob;
  filename: string;
}

export async function generatePaper(
  file: File,
  settings: PaperSettingsInput
): Promise<GeneratedPaper> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("examination", settings.examination);
  form.append("session", settings.session);
  form.append("class_name", settings.class_name);
  form.append("subject", settings.subject);
  form.append("subject_code", settings.subject_code);
  form.append("max_marks", settings.max_marks);
  form.append("time", settings.time);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/generate`, { method: "POST", body: form });
  } catch {
    throw new Error(
      "Could not reach the processing server. Please make sure it is running and try again."
    );
  }
  if (!res.ok) {
    throw await friendlyError(
      res,
      "Question paper generation failed. Please try again."
    );
  }
  const blob = await res.blob();
  const headerName = res.headers.get("X-File-Name");
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  return { blob, filename: headerName ?? match?.[1] ?? "VPS_Question_Paper.docx" };
}
