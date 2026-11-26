"""Train the AI Crop Doctor leaf-disease classifier.

Transfer learning: MobileNetV2 (ImageNet weights), fine-tuned on
  * PlantVillage "raw/color" images for tomato and potato (13 disease/healthy classes)
  * one extra class "Unsupported___other": real photos that are NOT tomato/potato
    leaves (other PlantVillage crops, CIFAR-10 photos, flower photos) so the model
    can say "I don't know this" instead of forcing a tomato/potato answer.

The data directory must contain one sub-folder per class (see ml/prepare_data.py).

Outputs (into backend/model/):
  crop_doctor.keras   trained Keras model (input: 224x224 RGB, 0-255 floats)
  labels.json         ordered class names
  ood_stats.npz       per-class embedding means + shared precision matrix used
                      for Mahalanobis out-of-distribution rejection (supported classes only)
  metrics.json        held-out test metrics, confusion matrix, OOD evaluation

Usage:
  python -m ml.train --data /path/to/combined --ood-eval /path/to/ood_eval [--init-from model.keras]
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

SUPPORTED_PREFIXES = ("Tomato___", "Potato___")
UNSUPPORTED = "Unsupported___other"
IMG = 224
SEED = 42
MIN_CONFIDENCE = 0.70  # keep in sync with app/config.py
MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
IMG_EXT = (".jpg", ".jpeg", ".png")


def list_split(data_dir: Path):
    classes = sorted(d.name for d in data_dir.iterdir()
                     if d.is_dir() and (d.name.startswith(SUPPORTED_PREFIXES) or d.name == UNSUPPORTED))
    rng = random.Random(SEED)
    split = {"train": [], "val": [], "test": []}
    for idx, c in enumerate(classes):
        files = sorted(str(p) for p in (data_dir / c).iterdir() if p.suffix.lower() in IMG_EXT)
        rng.shuffle(files)
        n = len(files)
        n_test, n_val = int(n * 0.15), int(n * 0.15)
        split["test"] += [(f, idx) for f in files[:n_test]]
        split["val"] += [(f, idx) for f in files[n_test:n_test + n_val]]
        split["train"] += [(f, idx) for f in files[n_test + n_val:]]
    return classes, split


def load_img(path, label):
    raw = tf.io.read_file(path)
    img = tf.io.decode_image(raw, channels=3, expand_animations=False)
    img = tf.image.resize(img, (IMG, IMG))
    return tf.cast(img, tf.float32), label


def make_ds(items, training: bool, batch=32):
    ds = tf.data.Dataset.from_tensor_slices(([p for p, _ in items], [l for _, l in items]))
    if training:
        ds = ds.shuffle(len(items), seed=SEED, reshuffle_each_iteration=True)
    ds = ds.map(load_img, num_parallel_calls=tf.data.AUTOTUNE)
    return ds.batch(batch).prefetch(tf.data.AUTOTUNE)


def build_model(num_classes: int):
    inp = keras.Input((IMG, IMG, 3), name="image")
    aug = keras.Sequential([
        layers.RandomFlip("horizontal_and_vertical"),
        layers.RandomRotation(0.15),
        layers.RandomZoom(0.15),
        layers.RandomContrast(0.2),
        layers.RandomBrightness(0.2, value_range=(0, 255)),
    ], name="augment")
    x = aug(inp)
    x = layers.Rescaling(1 / 127.5, offset=-1, name="mobilenet_preprocess")(x)
    base = keras.applications.MobileNetV2(include_top=False, weights="imagenet", input_shape=(IMG, IMG, 3))
    base.trainable = False
    x = base(x, training=False)
    emb = layers.GlobalAveragePooling2D(name="embedding")(x)
    x = layers.Dropout(0.3)(emb)
    out = layers.Dense(num_classes, activation="softmax", name="probs")(x)
    return keras.Model(inp, out, name="crop_doctor"), base


def embed_and_predict(model, ds):
    emb_model = keras.Model(model.input, [model.get_layer("embedding").output, model.output])
    embs, probs, ys = [], [], []
    for x, y in ds:
        e, p = emb_model(x, training=False)
        embs.append(e.numpy()); probs.append(p.numpy()); ys.append(y.numpy())
    return np.concatenate(embs), np.concatenate(probs), np.concatenate(ys)


def fit_ood(embs, ys, class_ids):
    means = np.stack([embs[ys == c].mean(0) for c in class_ids])
    mask = np.isin(ys, class_ids)
    lookup = {c: i for i, c in enumerate(class_ids)}
    centered = embs[mask] - means[[lookup[y] for y in ys[mask]]]
    cov = np.cov(centered, rowvar=False)
    cov = cov + 1e-3 * np.trace(cov) / cov.shape[0] * np.eye(cov.shape[0])  # shrinkage
    return means, np.linalg.inv(cov)


def mahalanobis_min(embs, means, precision):
    d = [np.einsum("ij,jk,ik->i", embs - m, precision, embs - m) for m in means]
    return np.sqrt(np.min(np.stack(d, 1), 1))


def decide(probs, dist, threshold, other_idx):
    """Same rule as app/inference.py. Returns array of 'ok' | 'uncertain' | 'unsupported'."""
    top = probs.argmax(1)
    conf = probs.max(1)
    out = np.where(conf >= MIN_CONFIDENCE, "ok", "uncertain").astype(object)
    out[(dist > threshold) | (top == other_idx)] = "unsupported"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="folder with one sub-folder per class")
    ap.add_argument("--ood-eval", help="folder of held-out OOD sub-folders (never used in training)")
    ap.add_argument("--init-from", help="existing .keras model whose MobileNetV2 weights initialise the base")
    ap.add_argument("--head-epochs", type=int, default=3)
    ap.add_argument("--ft-epochs", type=int, default=5)
    ap.add_argument("--ft-lr", type=float, default=1e-4)
    ap.add_argument("--unfreeze", type=int, default=60)
    args = ap.parse_args()
    tf.keras.utils.set_random_seed(SEED)
    data_dir = Path(args.data)
    classes, split = list_split(data_dir)
    print({k: len(v) for k, v in split.items()}, classes)
    n = len(classes)
    other_idx = classes.index(UNSUPPORTED) if UNSUPPORTED in classes else -1
    supported_ids = [i for i in range(n) if i != other_idx]
    train_ds, val_ds, test_ds = (make_ds(split["train"], True), make_ds(split["val"], False),
                                 make_ds(split["test"], False))
    counts = np.bincount([l for _, l in split["train"]], minlength=n)
    class_weight = {i: float(len(split["train"]) / (n * c)) for i, c in enumerate(counts)}

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    (MODEL_DIR / "labels.json").write_text(json.dumps(classes, indent=2))
    ckpt = MODEL_DIR / "crop_doctor.keras"
    t0 = time.time()
    history = {}
    model, base = build_model(n)
    if args.init_from:
        old = keras.models.load_model(args.init_from)
        old_base = next(l for l in old.layers if l.name.startswith("mobilenetv2"))
        base.set_weights(old_base.get_weights())
        print("base initialised from", args.init_from)
    model.compile(keras.optimizers.Adam(1e-3), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    history["head"] = model.fit(train_ds, validation_data=val_ds, epochs=args.head_epochs,
                                class_weight=class_weight, verbose=2).history
    model.save(ckpt)
    if args.ft_epochs > 0:
        base.trainable = True
        for layer in base.layers[:-args.unfreeze]:
            layer.trainable = False
        for layer in base.layers:
            if isinstance(layer, layers.BatchNormalization):
                layer.trainable = False
        model.compile(keras.optimizers.Adam(args.ft_lr), loss="sparse_categorical_crossentropy",
                      metrics=["accuracy"])
        cbs = [keras.callbacks.ModelCheckpoint(ckpt, monitor="val_accuracy", save_best_only=True),
               keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.3, patience=1)]
        history["finetune"] = model.fit(train_ds, validation_data=val_ds, epochs=args.ft_epochs,
                                        class_weight=class_weight, verbose=2, callbacks=cbs).history
        model = keras.models.load_model(ckpt)  # best epoch by validation accuracy
    train_secs = time.time() - t0
    evaluate(model, classes, split, other_idx, supported_ids, args, train_secs, history)


def evaluate(model, classes, split, other_idx, supported_ids, args, train_secs=None, history=None):
    n = len(classes)
    # Mahalanobis statistics from non-augmented training embeddings of the SUPPORTED classes
    tr_e, _, tr_y = embed_and_predict(model, make_ds(split["train"], False))
    means, precision = fit_ood(tr_e, tr_y, supported_ids)
    va_e, va_p, va_y = embed_and_predict(model, make_ds(split["val"], False))
    va_sup = np.isin(va_y, supported_ids)
    threshold = float(np.percentile(mahalanobis_min(va_e[va_sup], means, precision), 99))
    np.savez(MODEL_DIR / "ood_stats.npz", means=means.astype(np.float32),
             precision=precision.astype(np.float32), threshold=np.float32(threshold))

    # Held-out test split (never used for training, checkpoint selection or thresholds... except
    # checkpoint selection used val, threshold used val+train)
    te_e, te_p, te_y = embed_and_predict(model, make_ds(split["test"], False))
    te_pred = te_p.argmax(1)
    te_d = mahalanobis_min(te_e, means, precision)
    te_dec = decide(te_p, te_d, threshold, other_idx)
    cm = np.zeros((n, n), dtype=int)
    for t, p in zip(te_y, te_pred):
        cm[t, p] += 1
    per_class = {}
    for i, c in enumerate(classes):
        tp = cm[i, i]; prec = tp / max(cm[:, i].sum(), 1); rec = tp / max(cm[i].sum(), 1)
        per_class[c] = {"precision": round(float(prec), 4), "recall": round(float(rec), 4),
                        "f1": round(float(2 * prec * rec / max(prec + rec, 1e-9)), 4),
                        "support": int(cm[i].sum())}
    sup = np.isin(te_y, supported_ids)
    acc_mask = sup & (te_dec == "ok")
    final_rule = {
        "supported_test_images": int(sup.sum()),
        "coverage_ok": round(float(acc_mask.sum() / sup.sum()), 4),
        "accuracy_when_ok": round(float((te_pred[acc_mask] == te_y[acc_mask]).mean()), 4),
        "uncertain_rate": round(float((te_dec[sup] == "uncertain").mean()), 4),
        "wrongly_unsupported_rate": round(float((te_dec[sup] == "unsupported").mean()), 4),
        "other_class_test_images": int((~sup).sum()),
        "other_class_rejected_rate": round(float((te_dec[~sup] == "unsupported").mean()), 4) if (~sup).any() else None,
    }

    # Held-out OOD folders: crops / photo types that were NEVER used in training
    ood_eval = {}
    if args.ood_eval:
        rng = random.Random(SEED)
        for d in sorted(Path(args.ood_eval).iterdir()):
            files = sorted(str(p) for p in d.iterdir() if p.suffix.lower() in IMG_EXT)
            rng.shuffle(files)
            files = files[:300]
            e, p, _ = embed_and_predict(model, make_ds([(f, 0) for f in files], False))
            dist = mahalanobis_min(e, means, precision)
            dec = decide(p, dist, threshold, other_idx)
            ood_eval[d.name] = {
                "n": len(files),
                "final_rejected_or_uncertain": round(float((dec != "ok").mean()), 4),
                "final_unsupported": round(float((dec == "unsupported").mean()), 4),
                "wrong_confident_diagnosis": round(float((dec == "ok").mean()), 4),
                "by_other_class": round(float((p.argmax(1) == other_idx).mean()), 4),
                "by_mahalanobis": round(float((dist > threshold).mean()), 4),
            }

    metrics = {
        "dataset": ("PlantVillage (github.com/spMohanty/PlantVillage-Dataset, raw/color; Mohanty, Hughes & Salathe 2016, CC BY-SA 3.0) "
                    "for tomato/potato classes; 'Unsupported___other' = other PlantVillage crops (excluding grape "
                    "and pepper), CIFAR-10 training photos, TensorFlow flower photos (daisy, dandelion, roses)"),
        "classes": classes,
        "split_sizes": {k: len(v) for k, v in split.items()},
        "train_seconds": round(train_secs, 1) if train_secs else None,
        "history": {ph: {k: [round(float(x), 4) for x in v] for k, v in h.items()} for ph, h in (history or {}).items()},
        "test_accuracy_all_classes": round(float((te_pred == te_y).mean()), 4),
        "test_accuracy_supported_classes": round(float((te_pred[sup] == te_y[sup]).mean()), 4),
        "decision_rule": {"min_confidence": MIN_CONFIDENCE, "ood_threshold": threshold,
                          "rule": "unsupported if top class is Unsupported___other or Mahalanobis distance > "
                                  "threshold; else uncertain if confidence < min_confidence; else ok"},
        "final_rule_on_test_split": final_rule,
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "ood_evaluation_held_out": ood_eval,
    }
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({k: metrics[k] for k in ("test_accuracy_supported_classes", "final_rule_on_test_split",
                                                "ood_evaluation_held_out")}, indent=2))


if __name__ == "__main__":
    main()
