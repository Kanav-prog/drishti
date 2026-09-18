"""
Phase 5.4 API Endpoints: Inference Router
Exposes Phase 5.1-5.3 inference pipeline via FastAPI endpoints.

Routes:
- POST /api/inference/predict - Single prediction with voting
- POST /api/inference/batch - Batch predictions
- WS /ws/inference/stream - Real-time streaming predictions
- GET /api/inference/models - Model status and metadata
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List, Optional, Any
import logging
import json
import numpy as np
from datetime import datetime
import uuid
import asyncio

logger = logging.getLogger(__name__)

# Import models and infrastructure — wrapped so torch absence doesn't crash the server
_ml_available = False
_ml_unavailable_reason = ""

try:
    from backend.ml.batch_and_realtime_inference import InferencePipeline
    from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
    from backend.ml.neural_ensemble_voting import NeuralEnsembleVoter, NeuralPredictionInput, IntegratedInferencePipeline
    from backend.ml.ensemble import EnsembleVoter
    _ml_available = True
except ImportError as _e:
    _ml_unavailable_reason = f"ML dependencies missing: {_e}"
    logger.warning(f"[inference_router] {_ml_unavailable_reason}")
    # Stub classes so the module loads cleanly
    InferencePipeline = None
    EnsembleVoter = None
    NeuralEnsembleVoter = None
    NeuralPredictionInput = None
    IntegratedInferencePipeline = None
except Exception as _e:
    _ml_unavailable_reason = f"ML init error: {_e}"
    logger.warning(f"[inference_router] {_ml_unavailable_reason}")
    InferencePipeline = None
    EnsembleVoter = None
    NeuralEnsembleVoter = None
    NeuralPredictionInput = None
    IntegratedInferencePipeline = None

from backend.api.schemas import (
    InferencePredictRequest,
    InferenceBatchRequest,
    InferencePredictResponse,
    InferenceBatchResponse,
    ModelStatusResponse,
    InferenceVotingResponse,
)


# Initialize router
router = APIRouter(prefix="/api/inference", tags=["Inference"])

# Global pipeline (lazy-loaded on first request)
_pipeline: Optional[Any] = None
_pipeline_lock = asyncio.Lock()


async def get_inference_pipeline() -> Any:
    """
    Lazy-load and return the integrated inference pipeline.
    Uses async lock to ensure single initialization.
    Returns 503 if ML dependencies (e.g. torch) are not installed.
    """
    global _pipeline

    # Fast-fail if ML stack isn't available
    if not _ml_available:
        raise HTTPException(
            status_code=503,
            detail=f"Inference engine unavailable: {_ml_unavailable_reason}"
        )

    if _pipeline is None:
        async with _pipeline_lock:
            if _pipeline is None:
                logger.info("Initializing inference pipeline...")
                try:
                    ensemble = create_ensemble_inference_from_checkpoint()
                    batch_realtime = InferencePipeline(ensemble_inference=ensemble)
                    base_voter = EnsembleVoter()
                    neural_voter = NeuralEnsembleVoter(base_voter)
                    _pipeline = IntegratedInferencePipeline(
                        batch_realtime_pipeline=batch_realtime,
                        neural_voter=neural_voter,
                        ensemble_voter=base_voter,
                    )
                    logger.info("Inference pipeline initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize inference pipeline: {e}")
                    raise HTTPException(
                        status_code=503,
                        detail=f"Inference pipeline initialization failed: {str(e)}"
                    )

    return _pipeline


@router.on_event("startup")
async def startup_event():
    """Pre-load pipeline on startup."""
    logger.info("Loading inference pipeline on startup...")
    try:
        await get_inference_pipeline()
        logger.info("Inference pipeline pre-loaded successfully")
    except Exception as e:
        logger.warning(f"Could not pre-load pipeline on startup: {e}")


@router.post("/predict", response_model=InferencePredictResponse)
async def predict_single(
    request: InferencePredictRequest,
    pipeline: IntegratedInferencePipeline = Depends(get_inference_pipeline),
) -> Dict[str, Any]:
    """
    Run single prediction with neural voting.
    
    Args:
        request: Single sample prediction request
        
    Returns:
        Prediction result with voting breakdown
    """
    # Validate input shape (before entering try block to avoid catching HTTPException)
    features = np.array(request.features, dtype=np.float32)
    if features.shape != (576, 15):
        raise HTTPException(
            status_code=422,
            detail=f"Expected features shape (576, 15), got {features.shape}"
        )
    
    try:
        # Extract traditional method inputs
        traditional_inputs = {
            'bayesian_risk': request.bayesian_risk,
            'anomaly_score': request.anomaly_score,
            'dbscan_anomaly': request.dbscan_anomaly,
            'causal_risk': request.causal_risk,
        }
        
        # Get AUC weights
        auc_weights = request.auc_weights or {'lstm_model_2': 0.55}
        
        # Run prediction
        result = pipeline.predict_with_voting(
            features=features,
            train_id=request.train_id,
            bayesian_risk=traditional_inputs['bayesian_risk'],
            anomaly_score=traditional_inputs['anomaly_score'],
            dbscan_anomaly=traditional_inputs['dbscan_anomaly'],
            causal_risk=traditional_inputs['causal_risk'],
            auc_weights=auc_weights,
            timestamp=datetime.now().isoformat(),
            alert_id=str(uuid.uuid4()),
        )
        
        logger.info(f"Prediction for {request.train_id}: alert_fires={result['voting_result']['fires']}")
        
        return InferencePredictResponse(
            train_id=result['train_id'],
            alert_fires=result['voting_result']['fires'],
            severity=result['voting_result']['severity'],
            consensus_risk=result['voting_result']['consensus_risk'],
            methods_agreeing=result['voting_result']['methods_agreeing'],
            neural_predictions=result['neural_predictions'],
            neural_latency_ms=result['neural_latency_ms'],
            votes_breakdown=[
                {
                    'method': v['method'],
                    'score': v['score'],
                    'votes_danger': v['votes_danger'],
                    'confidence': v['confidence'],
                }
                for v in result['votes_breakdown']
            ],
            recommended_actions=result['voting_result']['actions'],
            explanation=result['voting_result']['explanation'],
        )
    
    except HTTPException:
        # Re-raise HTTPException as-is (validation errors)
        raise
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=InferenceBatchResponse)
async def predict_batch(
    request: InferenceBatchRequest,
    pipeline: IntegratedInferencePipeline = Depends(get_inference_pipeline),
) -> Dict[str, Any]:
    """
    Run batch predictions on multiple samples.
    
    Args:
        request: Batch prediction request with multiple samples
        
    Returns:
        Batch results with individual predictions
    """
    # Validate batch size (before try block)
    num_samples = len(request.train_ids)
    if num_samples == 0:
        raise HTTPException(status_code=422, detail="Empty batch")
    if num_samples > 100:
        raise HTTPException(status_code=422, detail="Batch size exceeds 100 samples")
    
    # Validate all features (before try block)
    features_list = []
    for i, feat in enumerate(request.features):
        feat_array = np.array(feat, dtype=np.float32)
        if feat_array.shape != (576, 15):
            raise HTTPException(
                status_code=422,
                detail=f"Sample {i}: expected shape (576, 15), got {feat_array.shape}"
            )
        features_list.append(feat_array)
    
    try:
        # Stack features
        features_batch = np.stack(features_list, axis=0)
        
        # Get AUC weights
        auc_weights = request.auc_weights or {'lstm_model_2': 0.55}
        
        # Run batch prediction
        batch_result = pipeline.batch_realtime_pipeline.batch_engine.predict_array(
            features=features_batch,
            job_id=request.job_id or f"batch_{uuid.uuid4()}",
            aggregation=request.aggregation or 'mean',
        )
        
        # Add voting results for each sample
        predictions = []
        for i, train_id in enumerate(request.train_ids):
            pred = {
                'train_id': train_id,
                'neural_probability': batch_result['ensemble_predictions'][i],
                'latency_ms': batch_result['batch_metrics']['total_latency_ms'] / num_samples,
            }
            predictions.append(pred)
        
        logger.info(f"Batch prediction complete: {num_samples} samples")
        
        return InferenceBatchResponse(
            job_id=batch_result['job_id'],
            status=batch_result['status'],
            num_samples=batch_result['num_samples'],
            predictions=predictions,
            total_latency_ms=batch_result['batch_metrics']['total_latency_ms'],
            aggregation=batch_result['ensemble_aggregation'],
        )
    
    except HTTPException:
        # Re-raise HTTPException as-is (validation errors)
        raise
    except Exception as e:
        logger.error(f"Batch prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/stream")
async def websocket_stream(
    websocket: WebSocket,
    train_id: str = Query(..., description="Train identifier"),
):
    """
    WebSocket for real-time streaming predictions.
    
    Client sends JSON: {"features": [576x15 list], "traditional_inputs": {...}}
    Server responds with: {"prediction": ..., "voting": ..., "latency_ms": ...}
    
    Args:
        websocket: WebSocket connection
        train_id: Train identifier for this stream
    """
    await websocket.accept()
    
    try:
        pipeline = await get_inference_pipeline()
        logger.info(f"WebSocket stream opened for {train_id}")
        
        sample_count = 0
        
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            try:
                # Validate input
                features = np.array(data['features'], dtype=np.float32)
                if features.shape != (576, 15):
                    await websocket.send_json({
                        'status': 'error',
                        'message': f'Expected shape (576, 15), got {features.shape}',
                    })
                    continue
                
                traditional = data.get('traditional_inputs', {
                    'bayesian_risk': 0.5,
                    'anomaly_score': 50.0,
                    'dbscan_anomaly': False,
                    'causal_risk': 0.5,
                })
                
                auc_weights = data.get('auc_weights', {'lstm_model_2': 0.55})
                
                # Run prediction
                result = pipeline.predict_with_voting(
                    features=features,
                    train_id=train_id,
                    bayesian_risk=traditional['bayesian_risk'],
                    anomaly_score=traditional['anomaly_score'],
                    dbscan_anomaly=traditional['dbscan_anomaly'],
                    causal_risk=traditional['causal_risk'],
                    auc_weights=auc_weights,
                    timestamp=datetime.now().isoformat(),
                    alert_id=str(uuid.uuid4()),
                )
                
                # Send response
                response = {
                    'status': 'success',
                    'sample_number': sample_count,
                    'train_id': train_id,
                    'alert_fires': result['voting_result']['fires'],
                    'severity': result['voting_result']['severity'],
                    'consensus_risk': result['voting_result']['consensus_risk'],
                    'methods_agreeing': result['voting_result']['methods_agreeing'],
                    'neural_predictions': result['neural_predictions'],
                    'neural_latency_ms': result['neural_latency_ms'],
                    'recommended_actions': result['voting_result']['actions'],
                }
                
                await websocket.send_json(response)
                sample_count += 1
                
            except Exception as e:
                logger.error(f"Prediction error on stream: {e}")
                await websocket.send_json({
                    'status': 'error',
                    'message': str(e),
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket stream closed for {train_id} after {sample_count} samples")
    
    except Exception as e:
        logger.error(f"WebSocket error for {train_id}: {e}")
        try:
            await websocket.send_json({
                'status': 'error',
                'message': f'Stream error: {str(e)}',
            })
        except:
            pass
        finally:
            await websocket.close()


@router.get("/models", response_model=ModelStatusResponse)
async def get_models_status(
    pipeline: IntegratedInferencePipeline = Depends(get_inference_pipeline),
) -> Dict[str, Any]:
    """
    Get status of loaded models and inference engine.
    
    Returns:
        Model status and metadata
    """
    try:
        # Get model status from ensemble
        status = pipeline.batch_realtime_pipeline.realtime_engine.get_metrics()
        
        # Get registered models
        ensemble_info = pipeline.batch_realtime_pipeline.ensemble_inference.get_model_status()
        
        return ModelStatusResponse(
            status='ready',
            models_loaded=len(ensemble_info.get('registered_models', [])),
            registered_models=ensemble_info.get('registered_models', []),
            inference_metrics=status,
            timestamp=datetime.now().isoformat(),
        )
    
    except Exception as e:
        logger.error(f"Failed to get model status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for inference service.
    Always returns a response — never crashes, never requires auth.
    Statuses: 'healthy' | 'degraded' | 'unavailable'
    """
    global _pipeline

    # If ML stack (torch etc.) not installed — report unavailable, not error
    if not _ml_available:
        return {
            'status': 'degraded',
            'service': 'inference',
            'models_loaded': False,
            'models_available': [
                'Bayesian Network (pgmpy)',
                'Isolation Forest (sklearn)',
                'Causal DAG (networkx)',
                'DBSCAN Trajectory',
            ],
            'models_standby': ['Neural Ensemble (LSTM) — torch not installed'],
            'reason': _ml_unavailable_reason,
            'note': '4 of 5 ML methods active via in-process runtime. LSTM in standby.',
            'timestamp': datetime.now().isoformat(),
        }

    if _pipeline is not None:
        return {
            'status': 'healthy',
            'service': 'inference',
            'models_loaded': True,
            'timestamp': datetime.now().isoformat(),
        }

    return {
        'status': 'degraded',
        'service': 'inference',
        'models_loaded': False,
        'reason': 'Pipeline not yet initialized — ML checkpoint files may be missing',
        'timestamp': datetime.now().isoformat(),
    }


@router.get("/status")
async def inference_status() -> Dict[str, Any]:
    """
    Simplified status endpoint — always responds with model metadata without
    requiring pipeline initialization. Safe to call on cold-start.
    """
    global _pipeline
    return {
        'status': 'ready' if _pipeline is not None else 'standby',
        'pipeline_loaded': _pipeline is not None,
        'models_registered': [
            'Bayesian Network (pgmpy)',
            'Isolation Forest (sklearn)',
            'Causal DAG (networkx)',
            'DBSCAN Trajectory Clustering',
            'Neural Ensemble (LSTM)',
        ],
        'ensemble_weights': {
            'bayesian': 0.40,
            'isolation_forest': 0.35,
            'causal_dag': 0.25,
        },
        'timestamp': datetime.now().isoformat(),
    }
