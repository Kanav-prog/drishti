import sys
sys.path.insert(0, '.')
import torch
import numpy as np
from backend.ml.inference_models import ModelLoader, DeviceManager
from backend.ml.models.lstm_classifier import LSTMTemporalClassifier
from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint

print('\n' + '='*70)
print('PHASE 5.1: CHECKPOINT LOADING & INFERENCE ENGINE - QUICK TEST')
print('='*70)

# Test 1: DeviceManager
print('\nTest 1: Device Manager')
print('-'*70)
device = DeviceManager.get_device(prefer_gpu=False)
print(f'Device: {device}')
info = DeviceManager.get_device_info()
print(f'Info: {info}')

# Test 2: ModelLoader
print('\nTest 2: Model Loader')
print('-'*70)
loader = ModelLoader('./phase4_ensemble_checkpoints', device)
metrics = loader.get_ensemble_metrics()
print(f'Ensemble metrics loaded: {len(metrics)} keys')
print(f'  - Mean AUC: {metrics["avg_val_auc"]:.4f}')
print(f'  - Best model: {metrics["best_model"]} ({metrics["best_auc"]:.4f})')

rankings = loader.get_model_rankings()
print(f'Model rankings: {len(rankings)} models')
for ranking in rankings:
    print(f'  {ranking["rank"]}. {ranking["model"].upper()}: AUC={ranking["val_auc"]:.4f}')

# Load first model
model_name = rankings[0]['model']
# Use smaller hidden sizes to match checkpoint architecture
config = {'input_size': 15, 'hidden_size': 64, 'num_layers': 1, 'architecture': 'lstm'}
model, metadata = loader.load_model(LSTMTemporalClassifier, model_name, config)
print(f'Loaded {model_name}: AUC={metadata.best_auc:.4f}, params={metadata.total_parameters:,}')

# Test 3: EnsembleInference Engine
print('\nTest 3: Ensemble Inference Engine')
print('-'*70)
engine = create_ensemble_inference_from_checkpoint(
    checkpoint_dir="./phase4_ensemble_checkpoints",
    prefer_gpu=False,
)
models_list = engine.list_models()
print(f'Engine created with {len(models_list)} models:')
for m in models_list:
    print(f'  - {m}')

# Test 4: Batch Inference
print('\nTest 4: Batch Inference')
print('-'*70)
batch_size = 4
seq_len = 576
n_features = 15
features = np.random.randn(batch_size, seq_len, n_features).astype(np.float32)
print(f'Created batch: shape={features.shape}')

batch_result = engine.predict_batch(features)
print(f'Batch inference complete:')
print(f'  - Preprocessing: {batch_result.preprocessing_time_ms:.2f} ms')
print(f'  - Inference: {batch_result.inference_time_ms:.2f} ms')
print(f'  - Total latency: {batch_result.total_latency_ms:.2f} ms')

for model_name, pred_result in batch_result.predictions.items():
    print(f'  - {model_name}:')
    print(f'      Logits: {pred_result.logits}')
    print(f'      Probs: min={pred_result.probabilities.min():.4f}, max={pred_result.probabilities.max():.4f}')
    print(f'      Latency: {pred_result.latency_ms:.2f} ms')

# Test 5: Ensemble Aggregation
print('\nTest 5: Ensemble Aggregation')
print('-'*70)
ensemble_pred = engine.get_ensemble_prediction(batch_result, aggregation="mean")
print(f'Ensemble prediction (mean):')
print(f'  - Shape: {ensemble_pred.shape}')
print(f'  - Range: [{ensemble_pred.min():.4f}, {ensemble_pred.max():.4f}]')
print(f'  - Values: {ensemble_pred}')

# Test 6: Single Inference
print('\nTest 6: Single Sample Inference')
print('-'*70)
single_features = np.random.randn(seq_len, n_features).astype(np.float32)
predictions = engine.predict_single(single_features)
print(f'Single prediction:')
for model_name, prob in predictions.items():
    print(f'  - {model_name}: {prob:.4f}')

# Test 7: Model Status
print('\nTest 7: Model Status Report')
print('-'*70)
status = engine.get_model_status()
print(f'Device: {status["device"]}')
print(f'Models loaded: {status["num_models_loaded"]}')
for name, info in status['model_info'].items():
    print(f'  - {name}:')
    print(f'      Architecture: {info["architecture"]}')
    print(f'      Best AUC: {info["best_auc"]:.4f}')

print('\n' + '='*70)
print('[OK] Phase 5.1 checkpoint loading & inference engine test PASSED!')
print('='*70 + '\n')
