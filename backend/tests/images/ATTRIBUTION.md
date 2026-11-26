# Test image attribution

These are real photos, used only by the automated tests. None of them was used
for training: the 13 `Tomato___*` / `Potato___*` images come from the held-out
**test** split produced by `ml/train.py` (seed 42), and the `ood_*` images come from
sources that were held out completely (grape and pepper classes, tulips).

* `Tomato___*.jpg`, `Potato___*.jpg`, `ood_grape.jpg`, `ood_pepper.jpg` —
  PlantVillage dataset, https://github.com/spMohanty/PlantVillage-Dataset (raw/color).
  Mohanty S.P., Hughes D.P., Salathé M. (2016) *Using deep learning for image-based plant
  disease detection*. Licensed CC BY-SA 3.0.
* `ood_tulip.jpg` — TensorFlow flower photos dataset, `tulips/10164073235_f29931d91e.jpg`,
  CC-BY by Jocelyn Kinghorn — https://www.flickr.com/photos/joceykinghorn/10164073235/
