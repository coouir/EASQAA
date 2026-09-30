"""Freeze procedure helpers: PROTOCOL hash rows, required files per split, gold-check sample."""
# ---------------------------------------------------------------- A3: freeze tools

PROTOCOL_SAMPLE = """# PROTOCOL.md

| 파일 | 상태 | SHA-256 |
|---|---|---|
| `splits/scenes.json` | 확정 (M0) | `%(a)s` |
| `splits/splits.json` | 확정 (M0) | `%(a)s` |
| `data/injected/*.json`, `data/corrected/*.json` | 미정 (M5) | — |
| test 문항 파일 | 미정 (M5) | — |

검증: sha256sum
""".replace("%(a)s", "a" * 64)


def test_update_protocol_replaces_adds_and_drops_the_placeholders():
    from sarqa.run.freeze_tools import update_protocol

    rows = {"splits/scenes.json": "b" * 64, "data/questions/test.json": "c" * 64,
            "data/injected/test_miss.json": "d" * 64}
    out = update_protocol(PROTOCOL_SAMPLE, rows, "확정 (M5)")
    assert f"| `splits/scenes.json` | 확정 (M5) | `{'b' * 64}` |" in out           # replaced in place
    assert f"`{'a' * 64}`" in out and out.count("splits/scenes.json") == 1
    assert out.index("splits/splits.json") < out.index("data/questions/test.json") < out.index("검증:")
    assert "미정" not in out and "data/injected/test_miss.json" in out
    assert update_protocol(out, rows, "확정 (M5)") == out                             # idempotent
    import pathlib
    import tempfile

    from sarqa.run.freeze import protocol_hashes
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "PROTOCOL.md"
        p.write_text(out, encoding="utf-8")
        assert protocol_hashes(p)["data/questions/test.json"] == "c" * 64


def test_hash_rows_reports_missing_files_and_required_sets_differ_by_split(tmp_path):
    from sarqa.run.freeze import required_files
    from sarqa.run.freeze_tools import hash_rows

    assert "data/questions/test.json" in required_files("test") and "data/questions/dev.json" in required_files("dev")
    assert len(required_files("test")) == 11 and len(required_files("dev")) == 11
    (tmp_path / "splits").mkdir()
    (tmp_path / "splits/scenes.json").write_text("{}")
    rows, missing = hash_rows(tmp_path, "test")
    assert list(rows) == ["splits/scenes.json"] and "data/injected/test_fp.json" in missing
    import hashlib
    assert rows["splits/scenes.json"] == hashlib.sha256(b"{}").hexdigest()
    import pytest
    with pytest.raises(ValueError):
        required_files("val")


def test_gold_check_sample_is_stratified_deterministic_and_covers_templates():
    from sarqa.questions.review import select_gold_check

    qs = [{"qid": f"T-{lv}-{i:03d}", "level": lv, "template": f"{lv}_t{i % 3}"}
          for lv, n in (("L1", 40), ("L2", 30), ("L3", 20), ("L4", 8), ("L5", 2)) for i in range(n)]
    a = select_gold_check(qs, 30)
    assert a == select_gold_check(qs, 30) and len(a) == 30
    from collections import Counter
    assert Counter(q["level"] for q in a) == {"L1": 12, "L2": 9, "L3": 6, "L4": 2, "L5": 1}
    # every template of a level is visited round robin, so a level with a quota of at least its template
    # count covers all of them; the two-question level cannot
    for lv, quota in (("L1", 12), ("L2", 9), ("L3", 6)):
        assert {q["template"] for q in a if q["level"] == lv} == {q["template"] for q in qs if q["level"] == lv}
    assert select_gold_check(qs, 500) == qs
