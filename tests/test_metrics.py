import numpy as np

from sarqa.detector.metrics import ap50, best_f1_threshold, prf

SQ = [0, 0, 10, 10]
OTHER = [50, 50, 60, 60]


def _p(boxes, scores):
    return (np.array(boxes, dtype=float).reshape(-1, 4), np.array(scores, dtype=float))


def test_perfect_detector_has_ap_one():
    gts = {"a": [SQ, OTHER]}
    assert ap50({"a": _p([SQ, OTHER], [0.9, 0.8])}, gts) == 1.0


def test_no_detections_has_ap_zero():
    assert ap50({"a": _p([], [])}, {"a": [SQ]}) == 0.0


def test_false_positive_ranked_first_lowers_ap():
    gts = {"a": [SQ]}
    good_first = ap50({"a": _p([SQ, OTHER], [0.9, 0.5])}, gts)
    bad_first = ap50({"a": _p([SQ, OTHER], [0.5, 0.9])}, gts)
    assert good_first == 1.0 and bad_first == 0.5


def test_duplicate_detection_counts_as_fp():
    gts = {"a": [SQ]}
    r = prf({"a": _p([SQ, SQ], [0.9, 0.8])}, gts, 0.5)
    assert (r["tp"], r["fp"], r["fn"]) == (1, 1, 0)


def test_prf_threshold_filters_by_score():
    gts = {"a": [SQ, OTHER]}
    preds = {"a": _p([SQ, OTHER], [0.9, 0.3])}
    assert prf(preds, gts, 0.5)["recall"] == 0.5
    assert prf(preds, gts, 0.2)["recall"] == 1.0


def test_best_f1_threshold_prefers_dropping_low_score_fp():
    gts = {"a": [SQ]}
    preds = {"a": _p([SQ, OTHER], [0.9, 0.2])}
    best = best_f1_threshold(preds, gts)
    assert best["f1"] == 1.0 and best["threshold"] > 0.2


def test_default_grid_reaches_099():
    # a detector whose scores sit near 1 must still be able to pick a threshold above 0.95
    gts = {"a": [SQ]}
    preds = {"a": _p([SQ, OTHER], [0.9999, 0.97])}
    assert best_f1_threshold(preds, gts)["threshold"] == 0.99
