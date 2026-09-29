import numpy as np
import pytest

pytest.importorskip("torch")

from sarqa.detector import infer

SQ = [0, 0, 10, 10]


def test_apply_threshold_filters_boxes_and_scores():
    preds = {"a": (np.array([SQ, SQ], dtype=float), np.array([0.9, 0.2]))}
    out = infer.apply_threshold(preds, 0.5)
    assert out["a"][0].shape == (1, 4) and out["a"][1].tolist() == [0.9]


def test_error_summary_counts_by_tag():
    gts = {"a": np.array([SQ, [50, 50, 60, 60]], dtype=float), "b": np.array([SQ], dtype=float)}
    kept = {"a": (np.array([SQ], dtype=float), np.array([0.9])),
            "b": (np.array([SQ, [80, 80, 90, 90]], dtype=float), np.array([0.9, 0.8]))}
    s = infer.error_summary(kept, gts, {"a": "inshore", "b": "offshore"})
    assert s["overall"]["miss"] == 1 and s["overall"]["fp"] == 1
    assert s["inshore"]["miss"] == 1 and s["offshore"]["fp"] == 1


def test_set_threshold_in_config(tmp_path, monkeypatch):
    (tmp_path / "default.yaml").write_text("detector:\n  score_threshold: null    # note\n")
    monkeypatch.setattr(infer, "CONFIG_DIR", tmp_path)
    infer.set_threshold_in_config(0.42, force=False)
    assert "score_threshold: 0.42    # note" in (tmp_path / "default.yaml").read_text()
    infer.set_threshold_in_config(0.42, force=False)  # same value is fine
    with pytest.raises(SystemExit):
        infer.set_threshold_in_config(0.5, force=False)
    infer.set_threshold_in_config(0.5, force=True)
