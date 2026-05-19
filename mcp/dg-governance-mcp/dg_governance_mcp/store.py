from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dg_governance_mcp.models import (
    ChangeRecord,
    IncidentRecord,
    ProblemRecord,
    Service,
)


class GovernanceStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).resolve()
        self.records_dir = self.data_dir / "records"
        self.catalog_path = self.data_dir / "catalog" / "services.json"
        self.runbooks_dir = self.data_dir / "runbooks"
        self.records_dir.mkdir(parents=True, exist_ok=True)

    def _record_path(self, record_type: str, record_id: str) -> Path:
        target_dir = self.records_dir / record_type
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{record_id}.json"

    def write_record(self, record_type: str, record: Any) -> Path:
        payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
        record_id = payload["id"]
        path = self._record_path(record_type, record_id)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def read_record(self, record_type: str, record_id: str) -> dict[str, Any]:
        path = self._record_path(record_type, record_id)
        if not path.exists():
            raise FileNotFoundError(f"{record_type} record not found: {record_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_records(self, record_type: str) -> list[dict[str, Any]]:
        target_dir = self.records_dir / record_type
        if not target_dir.exists():
            return []
        records = []
        for path in sorted(target_dir.glob("*.json")):
            records.append(json.loads(path.read_text(encoding="utf-8")))
        return records

    def list_services(self) -> list[Service]:
        if not self.catalog_path.exists():
            return []
        raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        return [Service.model_validate(item) for item in raw]

    def get_service(self, service_name: str) -> Service | None:
        for service in self.list_services():
            if service.name == service_name:
                return service
        return None

    def search_runbooks(self, query: str) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        if not self.runbooks_dir.exists():
            return results
        q = query.lower().strip()
        for path in sorted(self.runbooks_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            haystack = f"{path.name}\n{text}".lower()
            if q in haystack:
                snippet_start = max(haystack.find(q) - 120, 0)
                snippet_end = min(snippet_start + 360, len(text))
                results.append(
                    {
                        "path": str(path.relative_to(self.data_dir)),
                        "title": path.stem.replace("-", " ").title(),
                        "snippet": text[snippet_start:snippet_end].strip(),
                    }
                )
        return results

    def update_incident(self, incident_id: str, updates: dict[str, Any]) -> IncidentRecord:
        current = self.read_record("incidents", incident_id)
        current.update(updates)
        record = IncidentRecord.model_validate(current)
        self.write_record("incidents", record)
        return record

    def write_incident(self, record: IncidentRecord) -> Path:
        return self.write_record("incidents", record)

    def write_change(self, record: ChangeRecord) -> Path:
        return self.write_record("changes", record)

    def write_problem(self, record: ProblemRecord) -> Path:
        return self.write_record("problems", record)
