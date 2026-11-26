"""Loads the trained Keras model and turns an image into an honest prediction.

Decision rules (in order):
  1. Unsupported: if the model's top class is "Unsupported___other" (trained on
     photos that are not tomato/potato leaves) OR the image embedding is far
     (Mahalanobis distance) from every supported training class, the image is
     "unsupported" - no disease is shown.
  2. Low confidence: if the top softmax probability is below MIN_CONFIDENCE the
     result is "uncertain" - we show the top candidates but no firm diagnosis.
  3. Otherwise "ok".
"""
import json
import threading

import numpy as np
from PIL import Image

from . import config

IMG = 224
UNSUPPORTED = "Unsupported___other"


class CropDoctorModel:
    def __init__(self, model_dir=config.MODEL_DIR):
        import tensorflow as tf  # imported lazily: slow import
        from tensorflow import keras

        self.labels: list[str] = json.loads((model_dir / "labels.json").read_text())
        model = keras.models.load_model(model_dir / "crop_doctor.keras")
        self._model = keras.Model(model.input, [model.get_layer("embedding").output, model.output])
        stats = np.load(model_dir / "ood_stats.npz")
        self.means = stats["means"].astype(np.float64)
        self.precision = stats["precision"].astype(np.float64)
        self.ood_threshold = float(stats["threshold"])
        metrics_path = model_dir / "metrics.json"
        self.metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
        self._lock = threading.Lock()
        self._tf = tf

    def _ood_distance(self, emb: np.ndarray) -> float:
        diffs = self.means - emb[None, :]
        d2 = np.einsum("ij,jk,ik->i", diffs, self.precision, diffs)
        return float(np.sqrt(d2.min()))

    def predict(self, img: Image.Image) -> dict:
        x = np.asarray(img.convert("RGB").resize((IMG, IMG), Image.BILINEAR), dtype=np.float32)[None]
        with self._lock:
            emb, probs = self._model(x, training=False)
        emb = emb.numpy()[0].astype(np.float64)
        probs = probs.numpy()[0]
        order = np.argsort(probs)[::-1]
        top_class = self.labels[order[0]]
        top_k = [{"class_id": self.labels[i], "confidence": round(float(probs[i]), 4)}
                 for i in order if self.labels[i] != UNSUPPORTED][:3]
        distance = self._ood_distance(emb)
        best = top_k[0]
        if top_class == UNSUPPORTED or distance > self.ood_threshold:
            status = "unsupported"
        elif best["confidence"] < config.MIN_CONFIDENCE:
            status = "uncertain"
        else:
            status = "ok"
        return {
            "status": status,
            "class_id": best["class_id"] if status == "ok" else None,
            "confidence": best["confidence"],
            "unsupported_probability": round(float(probs[self.labels.index(UNSUPPORTED)]), 4)
            if UNSUPPORTED in self.labels else None,
            "top_k": top_k,
            "ood_distance": round(distance, 2),
            "ood_threshold": round(self.ood_threshold, 2),
        }

    def info(self) -> dict:
        m = self.metrics
        return {
            "architecture": "MobileNetV2 (ImageNet pre-trained) fine-tuned, 224x224 input",
            "dataset": m.get("dataset"),
            "classes": [c for c in self.labels if c != UNSUPPORTED],
            "has_unsupported_class": UNSUPPORTED in self.labels,
            "test_accuracy_supported_classes": m.get("test_accuracy_supported_classes"),
            "final_rule_on_test_split": m.get("final_rule_on_test_split"),
            "split_sizes": m.get("split_sizes"),
            "min_confidence": config.MIN_CONFIDENCE,
            "ood_threshold": round(self.ood_threshold, 2),
            "ood_evaluation_held_out": m.get("ood_evaluation_held_out"),
            "per_class": m.get("per_class"),
        }


_model: CropDoctorModel | None = None
_model_lock = threading.Lock()


def get_model() -> CropDoctorModel:
    global _model
    with _model_lock:
        if _model is None:
            _model = CropDoctorModel()
        return _model
