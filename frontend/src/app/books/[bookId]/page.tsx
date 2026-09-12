"use client";

import { use, useCallback, useEffect, useState } from "react";
import {
  ask,
  Citation,
  citationLabel,
  getBook,
  Book,
  WORKSPACE_ID,
} from "@/lib/api";

interface ChatEntry {
  kind: "user" | "assistant" | "note";
  text: string;
  citations?: Citation[];
  insufficient?: boolean;
}

export default function BookPage({
  params,
}: {
  params: Promise<{ bookId: string }>;
}) {
  const { bookId } = use(params);
  const [book, setBook] = useState<Book | null>(null);
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshBook = useCallback(async () => {
    try {
      setBook(await getBook(WORKSPACE_ID, bookId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [bookId]);

  useEffect(() => {
    void refreshBook();
  }, [refreshBook]);

  const onAsk = async () => {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    setEntries((prev) => [...prev, { kind: "user", text }]);
    setQuestion("");
    try {
      const result = await ask(WORKSPACE_ID, bookId, text);
      setEntries((prev) => [
        ...prev,
        {
          kind: "assistant",
          text: result.answer,
          citations: result.citations,
          insufficient: result.insufficientEvidence,
        },
        ...(result.generalKnowledgeNote
          ? [
              {
                kind: "note" as const,
                text: result.generalKnowledgeNote,
              },
            ]
          : []),
      ]);
    } catch (e) {
      setEntries((prev) => [
        ...prev,
        { kind: "note", text: `Request failed: ${e instanceof Error ? e.message : String(e)}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const ready = book?.status === "READY";

  return (
    <>
      <div className="panel">
        <h2 style={{ marginTop: 0 }}>{book ? book.title : "…"}</h2>
        {book?.author && <p className="muted">{book.author}</p>}
        {book && (
          <span className={`status status-${book.status}`}>
            {book.status}
            {book.status === "READY" &&
              ` · ${book.chapterCount ?? 0} chapters · ${book.chunkCount ?? 0} chunks`}
          </span>
        )}
        {book?.status === "FAILED" && book.error && (
          <p className="error-text">
            Ingestion failed at {book.error.stage}: {book.error.message}
          </p>
        )}
      </div>

      <div className="panel">
        <div className="chat-messages">
          {entries.length === 0 && (
            <p className="muted">
              {ready
                ? "Ask a question about this book. Answers cite chapters and pages from the book only."
                : "The book must be READY before you can ask questions."}
            </p>
          )}
          {entries.map((entry, index) => {
            if (entry.kind === "user") {
              return (
                <div key={index} className="message message-user">
                  {entry.text}
                </div>
              );
            }
            if (entry.kind === "note") {
              return (
                <div key={index} className="message message-note">
                  General knowledge (not from the book): {entry.text}
                </div>
              );
            }
            return (
              <div
                key={index}
                className={`message message-assistant${entry.insufficient ? " insufficient" : ""}`}
              >
                {entry.insufficient && (
                  <div className="muted" style={{ marginBottom: 6 }}>
                    Not answerable from this book.
                  </div>
                )}
                {entry.text}
                {entry.citations && entry.citations.length > 0 && (
                  <div className="citations">
                    <span className="muted">Citations: </span>
                    {entry.citations.map((citation) => (
                      <span className="citation-chip" key={citation.chunkId}>
                        {citationLabel(citation)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="ask-form">
          <input
            type="text"
            placeholder={
              ready ? "Ask about this book…" : "Book is not READY yet"
            }
            value={question}
            disabled={!ready || busy}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void onAsk();
            }}
          />
          <button onClick={onAsk} disabled={!ready || busy || !question.trim()}>
            {busy ? "Thinking…" : "Ask"}
          </button>
        </div>
      </div>
    </>
  );
}
