"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Book, listBooks, uploadBook, WORKSPACE_ID } from "@/lib/api";

const TERMINAL = new Set(["READY", "FAILED"]);

export default function BooksPage() {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setBooks(await listBooks(WORKSPACE_ID));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const busy =
      books !== null && books.some((book) => !TERMINAL.has(book.status));
    if (!busy) return;
    const timer = setInterval(() => void refresh(), 2500);
    return () => clearInterval(timer);
  }, [books, refresh]);

  const onUpload = async () => {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadBook(WORKSPACE_ID, file);
      if (fileInput.current) fileInput.current.value = "";
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <div className="panel">
        <h2 style={{ marginTop: 0 }}>Add a book</h2>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input type="file" ref={fileInput} accept=".pdf,.txt,.md" />
          <button onClick={onUpload} disabled={uploading}>
            {uploading ? "Uploading…" : "Upload"}
          </button>
        </div>
        <p className="muted">
          Ingestion runs in the background: parse → chapters → chunks →
          embeddings → concepts. The book becomes READY when done.
        </p>
      </div>

      {error && <p className="error-text">API error: {error}</p>}

      <div className="panel">
        <h2 style={{ marginTop: 0 }}>Your books</h2>
        {books === null && <p className="muted">Loading…</p>}
        {books !== null && books.length === 0 && (
          <p className="muted">No books yet — upload one above.</p>
        )}
        {books?.map((book) => (
          <div className="book-row" key={book.bookId}>
            <span>
              <a href={`/books/${book.bookId}`}>{book.title}</a>
              {book.author && (
                <span className="muted"> — {book.author}</span>
              )}
              {book.status === "FAILED" && book.error && (
                <div className="error-text">
                  failed at {book.error.stage}: {book.error.message}
                </div>
              )}
            </span>
            <span className={`status status-${book.status}`}>
              {book.status}
              {book.status === "READY" && ` · ${book.chunkCount ?? 0} chunks`}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}
