from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    sev1 = "SEV1"
    sev2 = "SEV2"
    sev3 = "SEV3"
    sev4 = "SEV4"


class ChangeRisk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, Enum):
    investigating = "investigating"
    identified = "identified"
    monitoring = "monitoring"
    resolved = "resolved"


class Service(BaseModel):
    name: str
    tier: Literal["tier-0", "tier-1", "tier-2", "tier-3"]
    owner: str
    critical_user_journey: bool = False
    sli: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class GovernanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "chatgpt-principal-engineer"


class IncidentCreateRequest(BaseModel):
    service: str
    severity: Severity
    summary: str
    symptoms: list[str] = Field(default_factory=list)
    customer_impact: str
    detected_by: str = "manual"

    @field_validator("summary", "customer_impact")
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value.strip()


class IncidentRecord(GovernanceRecord):
    type: Literal["incident"] = "incident"
    status: IncidentStatus = IncidentStatus.investigating
    service: str
    severity: Severity
    summary: str
    symptoms: list[str]
    customer_impact: str
    detected_by: str
    timeline: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class IncidentUpdateRequest(BaseModel):
    incident_id: str
    status: IncidentStatus
    update: str
    next_actions: list[str] = Field(default_factory=list)


class ChangeCreateRequest(BaseModel):
    service: str
    title: str
    risk: ChangeRisk
    reason: str
    implementation_plan: list[str]
    validation_plan: list[str]
    rollback_plan: list[str]
    planned_window_utc: str

    @field_validator("implementation_plan", "validation_plan", "rollback_plan")
    @classmethod
    def require_steps(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("at least one step is required")
        return value


class ChangeRecord(GovernanceRecord):
    type: Literal["change"] = "change"
    service: str
    title: str
    risk: ChangeRisk
    reason: str
    implementation_plan: list[str]
    validation_plan: list[str]
    rollback_plan: list[str]
    planned_window_utc: str
    approval_state: Literal["draft", "approved", "rejected"] = "draft"
    policy_findings: list[str] = Field(default_factory=list)


class ProblemCreateRequest(BaseModel):
    related_incident_id: str
    service: str
    problem_statement: str
    suspected_causes: list[str] = Field(default_factory=list)


class ProblemRecord(GovernanceRecord):
    type: Literal["problem"] = "problem"
    related_incident_id: str
    service: str
    problem_statement: str
    suspected_causes: list[str]
    investigation_status: Literal["open", "mitigated", "closed"] = "open"


class DeploymentReviewRequest(BaseModel):
    service: str
    change_id: str | None = None
    image_tag: str
    environment: Literal["dev", "staging", "prod"]
    checks: dict[str, bool] = Field(default_factory=dict)


class DeploymentReview(BaseModel):
    service: str
    environment: str
    decision: Literal["go", "no-go"]
    findings: list[str]
    required_actions: list[str]
