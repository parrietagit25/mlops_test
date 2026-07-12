"""Schemas de reportes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportFileInfo(BaseModel):
    name: str
    size_bytes: int
    content_type_hint: str


class ReportSummary(BaseModel):
    report_id: str = Field(..., description="Identificador seguro (date_time), no una ruta.")
    date: str
    time: str
    created_at: str
    suites_present: list[str] = Field(default_factory=list)
    has_summary: bool = False
    summary_excerpt: str | None = None
    files: list[ReportFileInfo] = Field(default_factory=list)
    total_size_bytes: int = 0
    status: str = Field(default="available", examples=["available", "partial"])


class ReportListResponse(BaseModel):
    reports: list[ReportSummary]
    count: int


class ReportLatestResponse(BaseModel):
    criterion: str = Field(
        ...,
        description="Criterio usado para elegir el más reciente.",
        examples=["Lexicographic max of reports/YYYY-MM-DD/HHMMSS directory names"],
    )
    report: ReportSummary | None = None


class ReportFileContentResponse(BaseModel):
    report_id: str
    filename: str
    media_type: str
    size_bytes: int
    truncated: bool = False
    content: str
