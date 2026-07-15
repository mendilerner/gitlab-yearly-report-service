"""Slim pydantic response models.

Raw GitLab issue/MR objects are large and noisy; we return a normalized subset.
IssueSummary and MergeRequestSummary are intentionally identical in shape today
but kept distinct so either can evolve independently (e.g. MRs gaining
merge-specific fields) without touching the other.
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


class IssueSummary(ItemSummary):
    pass


class MergeRequestSummary(ItemSummary):
    pass


class ReportResponse(BaseModel):
    count: int
    truncated: bool
    items: list[ItemSummary]
