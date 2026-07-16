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

    @classmethod
    def from_gitlab(cls, raw: dict) -> "ItemSummary":
        """Build a summary from a raw GitLab item; extra fields are ignored.

        A subclass can override this if its resource ever needs custom mapping;
        today the shared field set is enough, so both use this as-is.
        """
        return cls.model_validate(raw)


class IssueSummary(ItemSummary):
    pass


class MergeRequestSummary(ItemSummary):
    pass


class ReportResponse(BaseModel):
    count: int
    truncated: bool
    items: list[ItemSummary]
