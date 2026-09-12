# Skill: Ingest Book with Microsoft MarkItDown

## Purpose

Convert a learner-provided book or document into a Markdown working source before the AI Learning Workspace analyzes, chunks, indexes, or builds a roadmap from it.

This skill uses Microsoft's MarkItDown project:

https://github.com/microsoft/markitdown

MarkItDown is a document-to-Markdown conversion utility intended for LLM and text-analysis workflows.

Use this skill when:
- a PDF book is added to the workspace
- an EPUB, DOCX, PPTX, HTML, or other supported learning source must be normalized
- the user says `/ingest-book`
- the user asks the agent to start working on a new book
- the ingestion pipeline needs a Markdown intermediate representation

This skill is an INGESTION skill.

It must not:
- mark material as learned
- modify mastery
- generate fake page citations
- silently mix content from multiple books
- overwrite the original source

---

# 1. Core Pipeline

Use this flow:

```text
Original Book
     ↓
Validate Source
     ↓
Compute Source Identity
     ↓
Microsoft MarkItDown
     ↓
Markdown Source
     ↓
Validate Conversion
     ↓
Detect Structure
     ↓
Create Book Manifest
     ↓
Prepare for Chunking
     ↓
Concept Extraction
     ↓
Roadmap / RAG Pipeline
```

The original source remains immutable.

Markdown is a derived artifact.

---

# 2. Book Isolation

Every ingestion belongs to exactly one:

```text
workspace_id
book_id
```

Never reuse another book's Markdown, chunks, embeddings, concepts, notes, or roadmap state unless an explicit cross-book workflow is being performed.

Suggested derived-source layout:

```text
data/
└── books/
    └── <book_id>/
        ├── source/
        │   └── original.pdf
        ├── derived/
        │   └── book.md
        ├── manifest.json
        └── ingestion/
            └── report.json
```

Do not assume this exact storage layout if the repository already defines another one. Follow current architecture/ADRs first.

---

# 3. Check MarkItDown Availability

Before conversion, check whether MarkItDown is available.

Example:

```bash
markitdown --help
```

or:

```bash
python -c "import markitdown; print('markitdown available')"
```

If missing, install only the dependency group needed for the source type when practical.

For PDF:

```bash
pip install 'markitdown[pdf]'
```

For broad local development support:

```bash
pip install 'markitdown[all]'
```

Do not repeatedly reinstall dependencies if already present.

Respect the repository's package manager and dependency-management conventions.

---

# 4. Convert PDF to Markdown

Preferred CLI form:

```bash
markitdown path/to/book.pdf -o path/to/book.md
```

Equivalent redirection:

```bash
markitdown path/to/book.pdf > path/to/book.md
```

Prefer explicit output files.

Never overwrite the original PDF.

---

# 5. Python Integration

When ingestion is part of application code rather than an agent-only workflow, use the MarkItDown Python API behind the project's document-conversion abstraction.

Conceptually:

```python
from markitdown import MarkItDown

converter = MarkItDown()
result = converter.convert("book.pdf")
markdown = result.markdown
```

Check the installed MarkItDown version/API before implementation because API details can evolve.

Do NOT scatter direct MarkItDown calls throughout the domain.

Prefer an abstraction such as:

```text
DocumentConverter

convert(source) -> ConvertedDocument
```

with:

```text
MarkItDownDocumentConverter
```

as an adapter.

---

# 6. Source Identity and Idempotency

Before conversion, calculate a stable content hash for the original source.

Example:

```text
SHA-256(original bytes)
```

Persist or record:

```text
source_hash
source_filename
source_type
converter
converter_version
converted_at
```

If the same source hash has already been successfully converted using the required converter/version and no forced reprocessing was requested, reuse the existing derived artifact.

Do not create duplicate book state because an ingestion command was retried.

---

# 7. Validate Markdown Output

Conversion success does NOT mean ingestion success.

After conversion validate:

### File

- output exists
- output is non-empty
- output is valid UTF-8 or normalized appropriately
- output size is plausible relative to source

### Content

Look for:
- headings
- paragraphs
- lists
- tables
- code blocks where applicable
- chapter boundaries
- table of contents
- repeated headers/footers
- obvious extraction corruption

### Book-level sanity

Estimate:
- character count
- word count
- heading count
- detected chapters
- suspicious empty regions

Record results in an ingestion report.

---

# 8. PDF Limitations

PDF is layout-oriented and conversion quality varies.

Do not assume MarkItDown perfectly reconstructs every PDF.

Pay special attention to:
- scanned books
- image-only pages
- multi-column layouts
- mathematical notation
- complex tables
- diagrams
- source-code formatting
- headers and footers
- page-number contamination
- hyphenated line wrapping

If extraction quality is clearly inadequate, STOP before concept extraction/roadmap generation and flag the source for an alternate extraction path.

Do not build a learning roadmap from obviously corrupted text.

---

# 9. OCR / Scanned PDF Handling

If the PDF appears scanned or contains important image-based text, determine whether the installed MarkItDown version/plugins support an appropriate OCR path.

Do not silently pretend an image-only PDF was successfully ingested.

Record:

```text
ocr_required
ocr_used
ocr_method
pages_affected
```

when available.

If OCR requires credentials, an external model, Azure service, or another dependency that is not configured, report that requirement rather than inventing extracted text.

---

# 10. Preserve Provenance

Markdown alone is not enough for source-grounded learning.

The ingestion pipeline must preserve provenance wherever technically possible.

Target metadata:

```text
book_id
chapter
section
source_page_start
source_page_end
source_filename
source_hash
```

If exact PDF page mapping is lost during conversion, explicitly record that limitation.

Never invent page numbers later.

If accurate page-level citation is a product requirement, design extraction/chunking so page provenance survives conversion.

---

# 11. Normalize Conservatively

The Markdown artifact should remain close to the source.

Allowed cleanup may include:
- normalizing whitespace
- removing clearly repeated headers/footers
- repairing obvious line-wrap artifacts
- preserving headings
- preserving code fences
- preserving tables where possible

Do NOT:
- summarize during normalization
- rewrite the author's explanation
- remove difficult sections because they seem unimportant
- merge chapters based solely on LLM preference
- inject general model knowledge

Derived Markdown represents BOOK KNOWLEDGE.

It must remain distinguishable from AI-generated material.

---

# 12. Detect Book Structure

After successful conversion, analyze Markdown structure.

Identify:

```text
Title
Authors
Table of Contents
Parts
Chapters
Sections
Subsections
Appendices
References
Index
```

Create stable identifiers for detected structural units.

Do not assume Markdown heading levels are always correct.

Use both:
- structural markers
- semantic analysis

when needed.

---

# 13. Create Book Manifest

Produce a machine-readable manifest.

Example:

```json
{
  "bookId": "...",
  "title": "...",
  "source": {
    "filename": "book.pdf",
    "type": "pdf",
    "sha256": "..."
  },
  "conversion": {
    "converter": "microsoft-markitdown",
    "version": "...",
    "status": "SUCCESS"
  },
  "markdown": {
    "path": "derived/book.md",
    "wordCount": 0,
    "headingCount": 0
  },
  "structure": {
    "chaptersDetected": 0
  },
  "quality": {
    "status": "PASS",
    "warnings": []
  }
}
```

Adapt the schema to the project's established domain model.

---

# 14. Ingestion Report

Create a report containing:

```text
Source
Source hash
Converter
Converter version
Conversion status
Markdown path
Word count
Heading count
Detected chapter count
OCR status
Warnings
Errors
Provenance limitations
Recommended next action
```

This report is operational metadata, not learner-facing book content.

---

# 15. Quality Gate

Classify conversion:

```text
PASS
PASS_WITH_WARNINGS
FAIL
```

### PASS

Safe to continue into chunking/concept extraction.

### PASS_WITH_WARNINGS

Usable, but known limitations exist.

Example:
- some tables degraded
- page provenance partial

### FAIL

Do not continue automatically.

Examples:
- almost empty output
- scanned source without usable OCR
- severe ordering corruption
- unreadable equations/code
- conversion crashed

---

# 16. Handoff to Learning Pipeline

Only after the quality gate passes:

```text
Markdown
   ↓
Semantic Chunking
   ↓
Embedding
   ↓
Chapter/Section Mapping
   ↓
Concept Extraction
   ↓
Knowledge Graph
   ↓
Roadmap Generation
   ↓
Ask-the-Book RAG
```

MarkItDown is the normalization stage, NOT the roadmap engine.

---

# 17. Chunking Requirements

Do not blindly split every N characters.

Chunk with awareness of:

```text
Chapter
Section
Subsection
Paragraph
Code Block
Table
Semantic Boundary
```

Every chunk should retain:

```text
workspace_id
book_id
chapter_id
section
source provenance
chunk index
source hash
```

Chunking must be deterministic/reproducible where practical.

---

# 18. Never Mix Knowledge Layers

Maintain:

```text
BOOK KNOWLEDGE
Markdown + source chunks

LEARNER KNOWLEDGE
Notes + answers + explanations

SYSTEM KNOWLEDGE
LLM/general knowledge
```

MarkItDown output belongs only to BOOK KNOWLEDGE.

---

# 19. Security

MarkItDown performs local I/O with the privileges of the running process.

Treat uploaded documents as untrusted inputs.

The agent/application should:
- use the narrowest required local file access
- avoid converting arbitrary unrelated paths
- avoid enabling third-party plugins by default
- avoid executing content extracted from documents
- keep ingestion scoped to approved workspace files

Do not enable plugins unless required and understood.

---

# 20. Agent Workflow

When the user provides a new book and asks to start working on it:

### Step 1

Wake up project context if necessary.

### Step 2

Identify the source file.

### Step 3

Create/resolve its `book_id`.

### Step 4

Compute source hash.

### Step 5

Check existing ingestion state.

### Step 6

Convert using MarkItDown.

### Step 7

Validate output.

### Step 8

Generate manifest/report.

### Step 9

If quality gate passes, continue to the project's book-analysis pipeline.

### Step 10

Update `.ai/CURRENT_TASK.md`, `.ai/PROJECT_STATE.md`, and handoff state when the ingestion represents meaningful project work.

---

# 21. Agent Output

After ingestion, report concisely:

```text
Book ingestion complete.

Source:
Java Concurrency in Practice.pdf

Converter:
Microsoft MarkItDown

Result:
PASS_WITH_WARNINGS

Markdown:
data/books/<book_id>/derived/book.md

Detected:
16 chapters
142 sections

Warnings:
Page-level provenance is incomplete for several extracted sections.

Next:
Run semantic chunking and concept extraction.
```

Do not claim the book has been learned merely because conversion succeeded.

---

# 22. Failure Behavior

If conversion fails:

```text
Book ingestion failed.

Stage:
Markdown conversion

Reason:
...

Original source:
Preserved

Learning state:
Unchanged

Recommended action:
...
```

Never leave partial conversion marked as successful.

---

# 23. Architecture Rule

MarkItDown is an infrastructure adapter.

Target architecture:

```text
BookIngestionService
        │
        ▼
DocumentConverter
        │
        └── MarkItDownDocumentConverter
```

The domain layer must not depend directly on MarkItDown.

This allows future adapters such as:

```text
PyMuPDFDocumentConverter
AzureDocumentIntelligenceConverter
EPUBDocumentConverter
```

without rewriting learning-domain logic.

---

# 24. Definition of Done

A book is successfully normalized when:

- original source is preserved
- source identity/hash is recorded
- Markdown exists
- conversion quality was checked
- book isolation is preserved
- provenance limitations are known
- manifest/report exists
- retrying is safe
- output is ready for semantic chunking
- no learner mastery/progress was falsely modified

Only then may downstream learning workflows begin.
