"""Slim pydantic response models -- a normalized subset of the noisy GitLab JSON.

IssueSummary and MergeRequestSummary are identical today but kept distinct so
either can evolve independently.
"""

from pydantic import BaseModel


class Author(BaseModel):
    username: str | None = None
    name: str | None = None


class ItemSummary(BaseModel):
    id: int
    iid: int | None = None
    title: str = ""
    state: str = ""
    author: Author | None = None
    created_at: str = ""
    web_url: str = ""
    project_id: int | None = None

    @classmethod
    def from_gitlab(cls, raw: dict) -> "ItemSummary":
        """Build a summary from a raw GitLab item; extra fields are ignored."""
        return cls.model_validate(raw)


class IssueSummary(ItemSummary):
    pass


class MergeRequestSummary(ItemSummary):
    pass


class ReportResponse(BaseModel):
    count: int
    truncated: bool
    items: list[ItemSummary]
