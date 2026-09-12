import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Learning Workspace",
  description: "Book Intelligence — Phase 1",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="app-header">
          <a href="/" className="app-title">
            AI Learning Workspace
          </a>
          <span className="app-subtitle">Book Intelligence · Phase 1</span>
        </header>
        <main className="app-main">{children}</main>
      </body>
    </html>
  );
}
