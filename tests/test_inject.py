"""Injection and correction on hand-made boxes (SPEC §8.2, §8.3, §13)."""

import pytest

from sarqa.detector.match import classify_detections, iou_matrix
from sarqa.inject.calibrate import SIZE_BINS, size_bin, stratum
from sarqa.inject.correct import correct
from sarqa.inject.inject import KINDS, check_injection, inject

ALL = [f"{b}|{s}" for b in SIZE_BINS for s in ("inshore", "offshore")]
CFG = {
    "size_cuts_long_side_px": [30.0, 60.0],
    "miss_rate": dict.fromkeys(ALL, 0.5), "loc_rate": dict.fromkeys(ALL, 1.0),
    "fp_counts": {"inshore": [3], "offshore": [1, 2]},
    "fp_wh": {"inshore": [[24, 18], [30, 30]], "offshore": [[24, 18]]},
    "fp_xy": {"inshore": [[100.0, 100.0], [650.0, 200.0], [300.0, 700.0]],
              "offshore": [[400.0, 400.0], [120.0, 600.0]]},
    "loc_samples": [[0.2, 0.0, 0.0, 0.0], [0.0, -0.15, 0.05, -0.05], [-0.12, 0.1, 0.1, 0.0]],
    "rules": {"fp_max_iou_with_label": 0.1, "loc_iou_range": [0.5, 0.75], "max_redraws": 50},
}
LABELS = [(100, 100, 140, 140), (300, 300, 350, 340), (500, 100, 560, 130), (600, 600, 640, 660),
          (50, 500, 90, 545), (700, 50, 745, 95)]


def test_size_bins_and_strata():
    assert [size_bin(v, [30, 60]) for v in (10, 30, 31, 60, 61)] == ["small", "small", "mid", "mid", "large"]
    assert stratum(45, "inshore", [30, 60]) == "mid|inshore"


# ---------------------------------------------------------------- correct

DET = [(100, 100, 140, 140),       # exact
       (300, 300, 340, 340),       # loc: IoU with label 2 = 1600/2000 -> wait, see below
       (500, 100, 560, 130),       # exact
       (10, 10, 30, 30)]           # fp


def test_correct_each_kind_fixes_only_its_error():
    labels = [(100, 100, 140, 140), (300, 300, 350, 340), (500, 100, 560, 130), (600, 600, 640, 660)]
    det = [(100, 100, 140, 140), (312, 300, 362, 340), (500, 100, 560, 130), (10, 10, 30, 30)]
    before = classify_detections(det, labels)
    assert len(before.miss) == 1 and len(before.fp) == 1 and len(before.loc) == 1
    for kind, expect in (("miss", (0, 1, 1)), ("fp", (1, 0, 1)), ("loc", (1, 1, 0))):
        after = classify_detections(correct(kind, det, labels), labels)
        assert (len(after.miss), len(after.fp), len(after.loc)) == expect, kind
    assert correct("fp", det, labels) == [d for d in det if d != (10, 10, 30, 30)]
    assert (600, 600, 640, 660) in correct("miss", det, labels)
    assert (300, 300, 350, 340) in correct("loc", det, labels) and (312, 300, 362, 340) not in correct("loc", det, labels)
    assert correct("miss", det, labels)[:4] == det                      # detections kept in place


def test_a_pair_at_exactly_iou_075_is_not_a_location_error():
    labels = [(0, 0, 100, 100)]
    det = [(0, 0, 100, 75)]                                              # IoU exactly 0.75
    assert correct("loc", det, labels) == det
    det2 = [(0, 0, 100, 74)]
    assert correct("loc", det2, labels) == labels


def test_correct_rejects_unknown_kind():
    with pytest.raises(ValueError):
        correct("swap", [], [])


# ---------------------------------------------------------------- inject

@pytest.mark.parametrize("kind", KINDS)
def test_injection_is_reproducible_and_only_of_its_own_kind(kind):
    a = inject(kind, "img1.jpg", LABELS, "inshore", CFG, seed=7)
    b = inject(kind, "img1.jpg", LABELS, "inshore", CFG, seed=7)
    assert a == b
    assert check_injection(kind, a, LABELS) == []
    other_seed = inject(kind, "img1.jpg", LABELS, "inshore", CFG, seed=8)
    other_image = inject(kind, "img2.jpg", LABELS, "inshore", CFG, seed=7)
    assert kind == "fp" or (a.boxes != other_seed.boxes or a.boxes != other_image.boxes)


def test_miss_drops_labels_by_stratum_rate():
    none = {**CFG, "miss_rate": dict.fromkeys(ALL, 0.0)}
    allrate = {**CFG, "miss_rate": dict.fromkeys(ALL, 1.0)}
    assert inject("miss", "i", LABELS, "inshore", none, 1).boxes == LABELS
    inj = inject("miss", "i", LABELS, "inshore", allrate, 1)
    assert inj.boxes == [] and inj.changed == list(range(6))
    only_small = {**CFG, "miss_rate": {**dict.fromkeys(ALL, 0.0), "small|inshore": 1.0}}
    assert inject("miss", "i", LABELS, "inshore", only_small, 1).boxes == LABELS   # no ship <= 30 px
    only_mid_inshore = {**CFG, "miss_rate": {**dict.fromkeys(ALL, 0.0), "mid|inshore": 1.0}}
    assert inject("miss", "i", LABELS, "inshore", only_mid_inshore, 1).boxes == []
    assert inject("miss", "i", LABELS, "offshore", only_mid_inshore, 1).boxes == LABELS  # other scene


def test_fp_boxes_come_from_the_empirical_distribution_and_avoid_labels():
    inj = inject("fp", "i", LABELS, "inshore", CFG, seed=3)
    added = inj.boxes[len(LABELS):]
    assert inj.added == 3 and len(added) == 3 and inj.boxes[:len(LABELS)] == LABELS
    m = iou_matrix(added, LABELS)
    assert (m <= 0.1).all()
    assert all((b[2] - b[0], b[3] - b[1]) in {(24, 18), (30, 30)} for b in added
               if min(b[0], b[1]) > 0 and max(b[2], b[3]) < 800)
    offshore = [inject("fp", f"i{k}", LABELS, "offshore", CFG, seed=3).added for k in range(30)]
    assert set(offshore) == {1, 2}


def test_fp_that_cannot_be_placed_is_counted_as_failed_not_forced():
    crowded = {**CFG, "fp_xy": {"inshore": [[120.0, 120.0]], "offshore": [[120.0, 120.0]]},
               "fp_wh": {"inshore": [[40, 40]], "offshore": [[40, 40]]}}
    inj = inject("fp", "i", LABELS, "inshore", crowded, seed=1)
    assert inj.added == 0 and inj.failed == 3 and inj.boxes == LABELS


def test_loc_perturbs_within_iou_range_and_leaves_the_rest_alone():
    inj = inject("loc", "i", LABELS, "inshore", CFG, seed=5)
    assert len(inj.boxes) == len(LABELS) and inj.changed
    for i, (new, old) in enumerate(zip(inj.boxes, LABELS, strict=True)):
        if i in inj.changed:
            iou = float(iou_matrix([new], [old])[0, 0])
            assert 0.5 <= iou < 0.75
        else:
            assert new == old
    never = {**CFG, "loc_rate": dict.fromkeys(ALL, 0.0)}
    assert inject("loc", "i", LABELS, "inshore", never, 1).boxes == LABELS


def test_loc_gives_up_on_a_box_when_no_sample_reaches_the_range():
    hopeless = {**CFG, "loc_samples": [[3.0, 3.0, 0.0, 0.0]]}
    inj = inject("loc", "i", LABELS, "inshore", hopeless, 1)
    assert inj.boxes == LABELS and inj.failed == len(LABELS) and not inj.changed


def test_check_injection_flags_errors_of_another_kind():
    inj = inject("miss", "i", LABELS, "inshore", CFG, seed=2)
    assert check_injection("miss", inj, LABELS) == []
    assert any("unexpected" in p or "!=" in p for p in check_injection("fp", inj, LABELS))
    inj.boxes.append((5, 5, 15, 15))
    assert any("unexpected fp" in p for p in check_injection("miss", inj, LABELS))


def test_unknown_kind_is_rejected():
    with pytest.raises(ValueError):
        inject("swap", "i", LABELS, "inshore", CFG, 1)


# ---------------------------------------------------------------- with the real dev data

@pytest.mark.data
def test_calibration_on_dev_reproduces_the_frozen_yaml_numbers():
    from sarqa.inject.calibrate import calibrate, load_injection

    fresh, frozen = calibrate("dev"), load_injection()
    for key in ("miss_rate", "loc_rate", "size_cuts_long_side_px", "dev_totals"):
        assert fresh[key] == frozen[key]
    assert set(fresh["miss_rate"]) == set(ALL)
    assert all(0 <= v <= 1 for v in fresh["miss_rate"].values())
    with pytest.raises(ValueError):
        calibrate("test")
