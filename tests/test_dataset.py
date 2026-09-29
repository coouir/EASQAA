import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sarqa.detector.dataset import HRSIDDetection


def test_flip_mirrors_boxes(tmp_path, monkeypatch):
    from PIL import Image

    (tmp_path / "JPEGImages").mkdir()
    Image.new("RGB", (800, 800)).save(tmp_path / "JPEGImages" / "a.jpg")
    ds = HRSIDDetection(["a.jpg"], {"a.jpg": np.array([[10, 20, 30, 40]], dtype=np.float32)}, True)
    ds.root = tmp_path / "JPEGImages"
    monkeypatch.setattr(torch, "rand", lambda n: torch.zeros(n))  # always flip
    img, target, _ = ds[0]
    assert img.shape == (3, 800, 800)
    assert target["boxes"].tolist() == [[770.0, 20.0, 790.0, 40.0]]
    ds.train = False
    assert ds[0][1]["boxes"].tolist() == [[10.0, 20.0, 30.0, 40.0]]
