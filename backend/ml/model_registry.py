"""Model versioning with MLflow (if available) and local fallback registry."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ModelVersionRecord:
    model_name: str
    version: str
    created_at: str
    backend: str
    metrics: dict[str, float]
    params: dict[str, Any]
    artifact_path: str | None = None


class ModelRegistry:
    """Simple registry abstraction that prefers MLflow and falls back to local JSON."""

    def __init__(self, local_registry_path: str = "models/registry.json") -> None:
        self.local_registry_path = Path(local_registry_path)
        self.local_registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._mlflow = None
        self._mlflow_available = False

        try:
            import mlflow  # type: ignore

            self._mlflow = mlflow
            self._mlflow_available = True
        except Exception:
            self._mlflow = None
            self._mlflow_available = False

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_local(self) -> list[dict[str, Any]]:
        if not self.local_registry_path.exists():
            return []
        return json.loads(self.local_registry_path.read_text(encoding="utf-8"))

    def _save_local(self, rows: list[dict[str, Any]]) -> None:
        self.local_registry_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def register_model(
        self,
        *,
        model_name: str,
        metrics: dict[str, float],
        params: dict[str, Any],
        artifact_path: str | None = None,
    ) -> ModelVersionRecord:
        now = self._now_iso()

        rows = self._load_local()
        version = str(len([r for r in rows if r["model_name"] == model_name]) + 1)

        backend = "mlflow" if self._mlflow_available else "local-json"

        if self._mlflow_available and self._mlflow is not None:
            with self._mlflow.start_run(run_name=f"{model_name}_v{version}"):
                self._mlflow.log_params(params)
                self._mlflow.log_metrics(metrics)
                if artifact_path:
                    artifact = Path(artifact_path)
                    if artifact.exists():
                        self._mlflow.log_artifact(str(artifact))

        record = ModelVersionRecord(
            model_name=model_name,
            version=version,
            created_at=now,
            backend=backend,
            metrics=metrics,
            params=params,
            artifact_path=artifact_path,
        )
        rows.append(asdict(record))
        self._save_local(rows)
        return record

    def list_versions(self, model_name: str | None = None) -> list[ModelVersionRecord]:
        rows = self._load_local()
        if model_name:
            rows = [r for r in rows if r["model_name"] == model_name]
        return [ModelVersionRecord(**row) for row in rows]
