from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractedConceptOut(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class ConceptListOut(BaseModel):
    concepts: list[ExtractedConceptOut]


class ExtractedRelationshipOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_concept: str = Field(min_length=1, alias="fromConcept")
    to_concept: str = Field(min_length=1, alias="toConcept")
    relation: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("relation")
    @classmethod
    def relation_known(cls, value: str) -> str:
        allowed = {
            "PREREQUISITE_OF",
            "RELATED_TO",
            "CONTRASTS_WITH",
            "IMPLEMENTED_BY",
            "CAUSES",
            "PREVENTS",
            "EXAMPLE_OF",
            "PART_OF",
        }
        upper = value.strip().upper()
        if upper not in allowed:
            raise ValueError(f"relation must be one of {sorted(allowed)}")
        return upper

    @field_validator("from_concept", "to_concept")
    @classmethod
    def concept_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("concept reference must not be blank")
        return value.strip()


class RelationshipListOut(BaseModel):
    relationships: list[ExtractedRelationshipOut]
