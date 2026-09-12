"""Pydantic schema for Person A's Step 3 AI report classification."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ReportClassification(BaseModel):
    report_id: str
    work_type: str
    category: str
    severity: str = "medium"
    hazards: list[str] = []
    impact: list[str] = []
    location_hints: dict = {}
    persistence: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    needs_review: bool = False
