from pydantic import BaseModel, ConfigDict, Field, field_validator

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "I could not find enough material in this book to answer confidently."
)


class LLMCitation(BaseModel):
    chunk_id: str = Field(min_length=1, alias="chunkId")


class AskLLMResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    answer: str = Field(min_length=1)
    book_grounded: bool = Field(alias="bookGrounded")
    citations: list[LLMCitation] = Field(default_factory=list)
    insufficient_evidence: bool = Field(default=False, alias="insufficientEvidence")
    general_knowledge_note: str | None = Field(
        default=None, alias="generalKnowledgeNote"
    )

    @field_validator("answer")
    @classmethod
    def answer_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer must not be blank")
        return value.strip()


class CitationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chunk_id: str = Field(alias="chunkId")
    book_id: str = Field(alias="bookId")
    chapter: int | None = None
    page_start: int | None = Field(default=None, alias="pageStart")
    page_end: int | None = Field(default=None, alias="pageEnd")
    section: str | None = None


class AskResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    answer: str
    book_grounded: bool = Field(alias="bookGrounded")
    citations: list[CitationOut] = Field(default_factory=list)
    insufficient_evidence: bool = Field(default=False, alias="insufficientEvidence")
    general_knowledge_note: str | None = Field(
        default=None, alias="generalKnowledgeNote"
    )
    conversation_id: str = Field(alias="conversationId")


ASK_SYSTEM_PROMPT = (
    "You answer questions about a book using ONLY the numbered passages provided.\n"
    "Rules:\n"
    "1. Cite every passage you use by adding its passage_id to citations.\n"
    "2. Mention chapter and page in the answer text, e.g. (Ch. 3, pp. 41-42), "
    "only for passages you cited.\n"
    "3. If the passages do not contain enough information, set insufficientEvidence=true "
    "and bookGrounded=false, and leave citations empty.\n"
    "4. Any explanation beyond the book goes ONLY into generalKnowledgeNote, never "
    "into the book-grounded answer.\n"
    "Respond with ONLY a JSON object of shape:\n"
    '{"answer": "...", "bookGrounded": true, '
    '"citations": [{"chunkId": "..."}], "insufficientEvidence": false, '
    '"generalKnowledgeNote": null}'
)
