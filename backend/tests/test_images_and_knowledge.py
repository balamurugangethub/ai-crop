import io
import json
import re

import pytest
from PIL import Image, ImageFilter

from app import knowledge
from app.image_check import ImageRejected, load_and_check
from conftest import IMAGES, ROOT


def _jpeg(img):
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def leaf():
    return Image.open(IMAGES / "Tomato___Early_blight.jpg").convert("RGB")


def test_real_leaf_passes_quality_checks():
    img, q = load_and_check((IMAGES / "Tomato___Early_blight.jpg").read_bytes())
    assert img.size == (256, 256)
    assert q["sharpness"] > 15


@pytest.mark.parametrize("data,code", [
    (b"", "empty_file"),
    (b"%PDF-1.4 not an image", "not_an_image"),
])
def test_rejects_non_images(data, code):
    with pytest.raises(ImageRejected) as e:
        load_and_check(data)
    assert e.value.code == code


def test_rejects_small_dark_bright_blurry():
    cases = {
        "too_small": leaf().resize((60, 60)),
        "too_dark": leaf().point(lambda v: v * 0.05),
        "too_bright": Image.new("RGB", (300, 300), (252, 252, 252)),
        "too_blurry": leaf().filter(ImageFilter.GaussianBlur(8)),
    }
    for code, img in cases.items():
        with pytest.raises(ImageRejected) as e:
            load_and_check(_jpeg(img))
        assert e.value.code == code, code


def test_rejects_gif_format():
    buf = io.BytesIO()
    leaf().save(buf, "GIF")
    with pytest.raises(ImageRejected) as e:
        load_and_check(buf.getvalue())
    assert e.value.code == "unsupported_format"


def test_knowledge_covers_every_model_class_in_both_languages():
    labels = json.loads((ROOT / "model" / "labels.json").read_text())
    for c in labels:
        if c == "Unsupported___other":
            continue
        for lang in ("en", "ta"):
            d = knowledge.get_disease(c, lang)
            assert d is not None, c
            assert d["language"] == lang
            assert d["name"] and d["crop_name"] and d["severity_note"]
            assert d["sources"] and all(s["url"].startswith("https://") for s in d["sources"])
            if not d["healthy"]:
                assert d["symptoms"] and d["do_now"] and d["prevention"]
        en, ta = knowledge.get_disease(c, "en"), knowledge.get_disease(c, "ta")
        for key in ("symptoms", "causes", "do_now", "prevention", "natural"):
            assert len(en[key]) == len(ta[key]), (c, key)


def test_knowledge_has_no_chemical_dosages():
    text = (ROOT / "app" / "knowledge" / "diseases.json").read_text(encoding="utf-8")
    dosage = re.compile(r"\d+(\.\d+)?\s*(ml|g|kg|l)\s*/\s*(l|ha|acre|litre)|per acre|ppm|lb/a", re.I)
    assert not dosage.search(text)
