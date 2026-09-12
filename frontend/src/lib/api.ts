const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const WORKSPACE_ID =
  process.env.NEXT_PUBLIC_WORKSPACE_ID ?? "00000000-0000-0000-0000-000000000001";

export type BookStatus =
  | "UPLOADED"
  | "PARSING"
  | "CHUNKED"
  | "EMBEDDED"
  | "READY"
  | "FAILED";

export interface Book {
  bookId: string;
  title: string;
  author: string | null;
  status: BookStatus;
  error: { stage: string; message: string } | null;
  ingestedAt: string | null;
  chapterCount?: number;
  chunkCount?: number;
}

export interface Citation {
  chunkId: string;
  bookId: string;
  chapter: number | null;
  pageStart: number | null;
  pageEnd: number | null;
  section: string | null;
}

export interface AskResult {
  answer: string;
  bookGrounded: boolean;
  citations: Citation[];
  insufficientEvidence: boolean;
  generalKnowledgeNote: string | null;
  conversationId: string;
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
}

export async function listBooks(workspaceId: string): Promise<Book[]> {
  return handle<Book[]>(
    await fetch(`${API_BASE}/workspaces/${workspaceId}/books`, { cache: "no-store" }),
  );
}

export async function getBook(workspaceId: string, bookId: string): Promise<Book> {
  return handle<Book>(
    await fetch(`${API_BASE}/workspaces/${workspaceId}/books/${bookId}`, {
      cache: "no-store",
    }),
  );
}

export async function uploadBook(
  workspaceId: string,
  file: File,
): Promise<{ bookId: string; created: boolean; status: BookStatus }> {
  const form = new FormData();
  form.append("file", file);
  return handle(
    await fetch(`${API_BASE}/workspaces/${workspaceId}/books`, {
      method: "POST",
      body: form,
    }),
  );
}

export async function ask(
  workspaceId: string,
  bookId: string,
  question: string,
): Promise<AskResult> {
  return handle<AskResult>(
    await fetch(`${API_BASE}/workspaces/${workspaceId}/books/${bookId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  );
}

export function citationLabel(citation: Citation): string {
  const parts: string[] = [];
  if (citation.chapter !== null) parts.push(`Ch. ${citation.chapter}`);
  if (citation.pageStart !== null) {
    parts.push(
      citation.pageEnd !== null && citation.pageEnd !== citation.pageStart
        ? `pp. ${citation.pageStart}–${citation.pageEnd}`
        : `p. ${citation.pageStart}`,
    );
  }
  if (citation.section) parts.push(citation.section);
  return parts.length > 0 ? parts.join(" · ") : citation.chunkId.slice(0, 8);
}
