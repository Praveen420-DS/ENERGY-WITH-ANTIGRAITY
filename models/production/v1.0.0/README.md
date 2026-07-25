# Production package v1.0.0

Frozen Random Forest inference package. Load through `ml_service.inference`, not by reconstructing features.

```python
from ml_service.inference import predict_one
result = predict_one(request)
```

Reproduce with:

`python scripts/week2_package_production_model.py --version v1.0.0`

Run validation with:

`python scripts/test_production_inference.py`

The package does not load training data, retrain, expose an API endpoint, or deploy anything.
