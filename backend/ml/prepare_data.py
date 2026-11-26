"""Build the training folder layout used by ml/train.py.

Downloads are NOT done here (see README "Re-training the model"); this script
expects:
  PV   = PlantVillage-Dataset/raw/color   (git clone of github.com/spMohanty/PlantVillage-Dataset)
  OOD  = folder containing cifar-10-batches-py/ and flower_photos/
         (storage.googleapis.com/tensorflow/tf-keras-datasets/cifar-10-python.tar.gz and
          storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz)

It creates
  OUT/combined/<Tomato___*|Potato___*>   symlinks to PlantVillage class folders
  OUT/combined/Unsupported___other       200 images per other PlantVillage class (grape and
                                         pepper excluded), 1500 CIFAR-10 train photos,
                                         500 each of daisy / dandelion / roses
  OUT/ood_eval/...                       held-out folders NEVER used for training:
                                         grape + pepper PlantVillage classes, 1000 CIFAR-10
                                         test photos, tulips, sunflowers

Usage: python -m ml.prepare_data --pv PV --ood OOD --out OUT
"""
import argparse
import pickle
import random
from pathlib import Path

from PIL import Image

HOLD_OUT_CROPS = ("Grape___", "Pepper,_bell___")
SUPPORTED = ("Tomato___", "Potato___")


def link(src: Path, dst: Path):
    if not dst.exists():
        dst.symlink_to(src.resolve())


def cifar(path: Path, out: Path, k: int, prefix: str, rng):
    d = pickle.load(open(path, "rb"), encoding="bytes")
    idx = list(range(len(d[b"data"])))
    rng.shuffle(idx)
    out.mkdir(parents=True, exist_ok=True)
    for i in idx[:k]:
        Image.fromarray(d[b"data"][i].reshape(3, 32, 32).transpose(1, 2, 0)).save(out / f"{prefix}_{i}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pv", required=True)
    ap.add_argument("--ood", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rng = random.Random(7)
    pv, ood, out = Path(a.pv), Path(a.ood), Path(a.out)
    comb, other, evald = out / "combined", out / "combined" / "Unsupported___other", out / "ood_eval"
    other.mkdir(parents=True, exist_ok=True)
    evald.mkdir(parents=True, exist_ok=True)
    for d in sorted(pv.iterdir()):
        if d.name.startswith(SUPPORTED):
            link(d, comb / d.name)
        elif d.name.startswith(HOLD_OUT_CROPS):
            link(d, evald / d.name)
        else:
            files = sorted(d.iterdir())
            rng.shuffle(files)
            for f in files[:200]:
                link(f, other / f"pv_{d.name.replace(' ', '_')}_{f.name}")
    cifar(ood / "cifar-10-batches-py" / "data_batch_1", other, 1500, "cifar", rng)
    cifar(ood / "cifar-10-batches-py" / "test_batch", evald / "cifar10_test", 1000, "cifar_test", rng)
    for fl in ("daisy", "dandelion", "roses"):
        for f in sorted((ood / "flower_photos" / fl).iterdir())[:500]:
            link(f, other / f"flower_{fl}_{f.name}")
    for fl in ("tulips", "sunflowers"):
        link(ood / "flower_photos" / fl, evald / f"flowers_{fl}")
    print("other:", len(list(other.iterdir())), "eval:", sorted(p.name for p in evald.iterdir()))


if __name__ == "__main__":
    main()
