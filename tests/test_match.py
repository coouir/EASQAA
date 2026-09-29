import numpy as np

from sarqa.detector.match import classify_detections, error_types, iou_matrix, match_boxes

SQ = [0, 0, 10, 10]


def test_iou_matrix_values_and_shapes():
    m = iou_matrix([SQ, [0, 0, 10, 5]], [SQ])
    assert m.shape == (2, 1)
    assert m[0, 0] == 1.0 and m[1, 0] == 0.5
    assert iou_matrix([], [SQ]).shape == (0, 1)
    assert iou_matrix([[0, 0, 0, 0]], [[0, 0, 0, 0]])[0, 0] == 0.0


def test_boundary_iou_050_is_matched():
    m = match_boxes([[0, 0, 10, 5]], [SQ])  # IoU exactly 0.5
    assert m.pairs == [(0, 0, 0.5)]


def test_just_below_050_is_miss_plus_fp():
    e = classify_detections([[0, 0, 10, 4.9]], [SQ])
    assert e.miss == [0] and e.fp == [0] and e.loc == []


def test_iou_075_is_not_loc_but_just_below_is():
    assert classify_detections([[0, 0, 10, 7.5]], [SQ]).loc == []  # IoU exactly 0.75
    e = classify_detections([[0, 0, 10, 7.4]], [SQ])
    assert len(e.loc) == 1 and e.miss == [] and e.fp == []


def test_perfect_match_has_no_errors():
    e = classify_detections([SQ], [SQ])
    assert (e.miss, e.fp, e.loc) == ([], [], [])


def test_synthetic_mix_of_miss_fp_loc():
    labels = [SQ, [100, 100, 110, 110], [200, 200, 210, 210]]
    dets = [[0, 0, 10, 7.0], [100, 100, 110, 110], [500, 500, 510, 510]]
    e = classify_detections(dets, labels)
    assert e.miss == [2] and e.fp == [2]
    assert [(d, lab) for d, lab, _ in e.loc] == [(0, 0)]


def test_matching_is_one_to_one_and_greedy_by_iou():
    labels = [[0, 0, 10, 10]]
    dets = [[0, 0, 10, 6], [0, 0, 10, 9]]  # both overlap the label; 0.9 wins
    m = match_boxes(dets, labels)
    assert [(d, lab) for d, lab, _ in m.pairs] == [(1, 0)]
    assert m.unmatched_dets == [0] and m.unmatched_labels == []


def test_empty_inputs():
    e = classify_detections(np.zeros((0, 4)), [SQ])
    assert e.miss == [0] and e.fp == []
    e = classify_detections([SQ], np.zeros((0, 4)))
    assert e.miss == [] and e.fp == [0]


def test_error_types_thresholds_can_be_overridden():
    m = match_boxes([[0, 0, 10, 8]], [SQ])
    assert error_types(m, loc_iou=0.9).loc and not error_types(m, loc_iou=0.7).loc
