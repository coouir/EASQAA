import json

from sarqa.analysis.language_comparison import main, render, stats


def _rec(qid, level, correct, fail=None):
    return {"qid": qid, "level": level, "condition": 1, "correct": correct, "status": "exec_fail" if fail else "ok",
            "fail_kind": fail, "tool_calls": 2, "wall_ms": 4000, "tokens_in": 100, "run_id": qid}


def _cls(qid, correct, stage):
    return {"qid": qid, "condition": 1, "agent_error": not correct, "first_deviation_stage_name": stage}


def _dump(tmp_path, recs, cls):
    tmp_path.mkdir()
    (tmp_path / "condition_01.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    (tmp_path / "classified.jsonl").write_text("\n".join(json.dumps(c) for c in cls) + "\n")


def test_stats_and_report_compare_the_same_questions(tmp_path):
    ko = [_rec("D-L1-001", "L1", True), _rec("D-L2-001", "L2", False, "budget_exceeded"), _rec("D-L3-001", "L3", False)]
    en = [_rec("D-L1-001", "L1", True), _rec("D-L2-001", "L2", True), _rec("D-L3-001", "L3", False)]
    _dump(tmp_path / "ko", ko, [_cls("D-L1-001", True, None), _cls("D-L2-001", False, "exec_fail"),
                                _cls("D-L3-001", False, "interpretation")])
    _dump(tmp_path / "en", en, [_cls("D-L1-001", True, None), _cls("D-L2-001", True, None),
                                _cls("D-L3-001", False, "calculation")])
    out = tmp_path / "out.md"
    assert main(["--ko", str(tmp_path / "ko"), "--en", str(tmp_path / "en"), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "| 정확도 | 1/3 (0.333) | 2/3 (0.667) |" in text
    assert "| 첫 이탈이 해석인 건수 | 1 | 0 |" in text and "D-L2-001 | 오답 (budget_exceeded) | 정답 (ok)" in text
    s = stats({r["qid"]: r for r in ko}, {})
    assert s["fails"] == 1 and s["by_level"]["L2"] == (0, 1) and render(s, s, {}, {}).count("정오가 다른 문항 (0건)") == 1
