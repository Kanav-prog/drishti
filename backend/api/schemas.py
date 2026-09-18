"""API request/response schemas with validation and sanitization."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_\-\s\.:,@/]")


def sanitize_text(value: str) -> str:
    cleaned = _SANITIZE_RE.sub("", value).strip()
    return cleaned


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("username")
    @classmethod
    def _sanitize_username(cls, value: str) -> str:
        return sanitize_text(value)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=10, max_length=256)
    role: str = Field(default="viewer", min_length=4, max_length=32)

    @field_validator("username", "role")
    @classmethod
    def _sanitize_fields(cls, value: str) -> str:
        return sanitize_text(value)


class BayesianInferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delay_minutes: int = Field(ge=0, le=600)
    time_of_day: str = Field(min_length=3, max_length=16)
    signal_cycle_time: float = Field(ge=0.1, le=60.0)
    maintenance_active: bool
    centrality_rank: int = Field(ge=0, le=100)
    traffic_density: float = Field(ge=0.0, le=1.0)

    @field_validator("time_of_day")
    @classmethod
    def _validate_time_of_day(cls, value: str) -> str:
        cleaned = sanitize_text(value).upper()
        if cleaned not in {"DAY", "NIGHT"}:
            raise ValueError("time_of_day must be DAY or NIGHT")
        return cleaned


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class TrainIsolationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[dict]


class AnomalyScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    train_id: str = Field(min_length=1, max_length=120)
    features: dict
    all_trains: list[dict] | None = None

    @field_validator("train_id")
    @classmethod
    def _sanitize_train_id(cls, value: str) -> str:
        return sanitize_text(value)


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: list[float] = Field(min_length=8, max_length=10000)
    horizon: int = Field(ge=1, le=256)
    method: str = Field(pattern="^(prophet|lstm)$")


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_type: str = Field(min_length=2, max_length=80)
    feature_names: list[str] = Field(min_length=1, max_length=256)
    train_matrix: list[list[float]] = Field(min_length=2, max_length=5000)
    row: list[float]


class DriftObserveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: dict[str, float]
    prediction: float


# ============================================================================
# Phase 5.4: Inference API Schemas
# ============================================================================

class MethodVoteBreakdown(BaseModel):
    """Individual method voting breakdown."""
    method: str
    score: float
    votes_danger: bool
    confidence: float


class InferencePredictRequest(BaseModel):
    """Single prediction request with traditional method inputs."""
    model_config = ConfigDict(extra="forbid")
    
    train_id: str = Field(min_length=1, max_length=128)
    features: list[list[float]] = Field(description="Shape (576, 15) - 24h sequence")
    
    # Traditional voting method inputs
    bayesian_risk: float = Field(ge=0.0, le=1.0, description="P(accident) from Bayesian network")
    anomaly_score: float = Field(ge=0.0, le=100.0, description="Isolation Forest anomaly score")
    dbscan_anomaly: bool = Field(description="DBSCAN outlier flag")
    causal_risk: float = Field(ge=0.0, le=1.0, description="Causal DAG risk score")
    
    # Neural model weights
    auc_weights: dict[str, float] | None = Field(default=None, description="AUC weights for models")
    
    @field_validator("train_id")
    @classmethod
    def _sanitize_train_id(cls, value: str) -> str:
        return sanitize_text(value)


class InferencePredictResponse(BaseModel):
    """Single prediction response with voting results."""
    train_id: str
    alert_fires: bool
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    consensus_risk: float
    methods_agreeing: int  # 0-5
    neural_predictions: dict[str, float]
    neural_latency_ms: float
    votes_breakdown: list[MethodVoteBreakdown]
    recommended_actions: list[str]
    explanation: str


class InferenceBatchRequest(BaseModel):
    """Batch prediction request."""
    model_config = ConfigDict(extra="forbid")
    
    job_id: str | None = Field(default=None, max_length=128)
    train_ids: list[str] = Field(min_length=1, max_length=100)
    features: list[list[list[float]]] = Field(description="Batch of (576, 15) sequences", max_length=100)
    aggregation: str = Field(default="mean", pattern="^(mean|median|max|min)$")
    auc_weights: dict[str, float] | None = Field(default=None)
    
    @field_validator("train_ids")
    @classmethod
    def _sanitize_ids(cls, value: list[str]) -> list[str]:
        return [sanitize_text(id_val) for id_val in value]


class BatchPredictionItem(BaseModel):
    """Single item in batch prediction results."""
    train_id: str
    neural_probability: float
    latency_ms: float


class InferenceBatchResponse(BaseModel):
    """Batch prediction response."""
    job_id: str
    status: str  # pending, running, complete, failed
    num_samples: int
    predictions: list[BatchPredictionItem]
    total_latency_ms: float
    aggregation: str


class ModelStatusResponse(BaseModel):
    """Model status and metadata response."""
    status: str  # ready, loading, error
    models_loaded: int
    registered_models: list[str]
    inference_metrics: dict
    timestamp: str


class VoteBreakdown(BaseModel):
    """Voting breakdown for streaming response."""
    method: str
    score: float
    votes_danger: bool
    confidence: float


class InferenceVotingResponse(BaseModel):
    """Voting response for streaming/API calls."""
    status: str
    sample_number: int
    train_id: str
    alert_fires: bool
    severity: str
    consensus_risk: float
    methods_agreeing: int
    neural_predictions: dict[str, float]
    neural_latency_ms: float
    recommended_actions: list[str]
