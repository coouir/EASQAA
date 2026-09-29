"""Runner: conditions table, order, resume, failure handling, freeze guard (SPEC §9, §10, §13)."""

import hashlib
import json
import subprocess

import pytest

from sarqa.agents import common as C
from sarqa.agents.llm import FakeLLM, seed_for
from sarqa.boxes import BoxProvider
from sarqa.questions.vocab import blank_interpretation
from sarqa.run import records as R
from sarqa.run import runner as RN
from sarqa.run.conditions import load_conditions, parse_selection, priority_groups, total_runs
from sarqa.run.freeze import check_freeze, protocol_hashes
from tools_fixtures import MINI_BOXES, mini_context


def make_questions(n=6):
    return [{"qid": f"D-L1-{i:03d}", "level": "L1", "image_id": "m3.jpg", "text_ko": "몇 척인가?",
             "answer_type": "int", "unit": "ships", "gold_answer": 3, "tolerance": {"rel": 0.0},
             "budget": 4, "gold_calls": 1, "box_dependent": True,
             "program": {"steps": [{"id": "s1", "op": "detect_ships", "args": {"image_id": "IMG"}}],
                         "answer": "$s1.count"}} for i in range(1, n + 1)]


class Pool:
    def __init__(self, split):
        self.split = split

    def get(self, cond):
        return BoxProvider("label", MINI_BOXES)


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(RN, "ProviderPool", Pool)
    monkeypatch.setattr(R, "data_hash", lambda split: "d" * 64)
    return mini_context()


def fake_agent(method, question, tool_ctx, llm, *, repeat=0, wall_limit_s=300):
    rec = C.base_record(question, method, repeat, seed_for(question["qid"], repeat))
    rec.update(status="ok", answer={"value": 3, "unit": "ships"}, answer_raw="{}", correct=True,
               answer_format_ok=True, interpretation={}, tool_calls=1, llm_calls=3, wall_ms=1500)
    return rec


def run_it(tmp_path, ctx, selection, questions=None, **kw):
    kw.setdefault("agent", fake_agent)
    return RN.run(selection, "dev", questions or make_questions(), tmp_path, FakeLLM([]),
                  ctx=ctx, log=lambda *_: None, **kw)


# ---------------------------------------------------------------- conditions

def test_condition_table_adds_up_to_3960_runs():
    conds = load_conditions()
    assert sorted(conds) == list(range(1, 12))
    assert total_runs("test") == 360 * 11 == 3960 and total_runs("dev") == 990
    assert {c.id for c in conds.values() if c.repeat == 1} == {3}
    assert {c.id for c in conds.values() if c.method == "batch"} == {4, 5}
    assert sorted(c for g in priority_groups() for c in g) == list(range(1, 12))
    assert conds[6].input == "injected:miss" and conds[11].kind == "loc" and conds[1].kind is None


def test_selection_follows_the_priority_order():
    assert parse_selection("all") == [1, 2, 6, 7, 8, 9, 10, 11, 3, 4, 5]
    assert parse_selection("5,1,2") == [1, 2, 5]
    with pytest.raises(ValueError):
        parse_selection("1,99")


def test_plan_is_priority_ordered_question_major_and_deterministic():
    qs = make_questions(5)
    p1 = RN.plan(qs, parse_selection("all"), seed=1)
    assert p1 == RN.plan(qs, parse_selection("all"), seed=1)
    conds = [c.id for _, c in p1]
    assert conds.index(3) > max(i for i, c in enumerate(conds) if c in (1, 2, 6, 7, 8, 9, 10, 11))
    assert min(i for i, c in enumerate(conds) if c in (4, 5)) > conds.index(3)
    first_block = p1[:8]
    assert len({q["qid"] for q, _ in first_block}) == 1 and [c.id for _, c in first_block] == [1, 2, 6, 7, 8, 9, 10, 11]
    assert [q["qid"] for q, _ in RN.plan(qs, [1], 1)] != [q["qid"] for q, _ in RN.plan(qs, [1], 2)] \
        or len(qs) < 3


# ---------------------------------------------------------------- running

def test_records_have_the_full_schema_and_provenance(tmp_path, patched):
    run_it(tmp_path, patched, [1, 3])
    recs = RN.load_records(tmp_path)
    assert len(recs) == 12
    for r in recs:
        assert R.validate_record(r) == [], r
        assert r["reachable_answer"] == 3 and r["boxes_hash"] and r["meta"]["data_hash"] == "d" * 64
        assert set(R.META_KEYS) <= set(r["meta"])
    c1 = {r["qid"]: r for r in recs if r["condition"] == 1}
    c3 = {r["qid"]: r for r in recs if r["condition"] == 3}
    assert all(c1[q]["seed"] != c3[q]["seed"] and c3[q]["repeat"] == 1 for q in c1)
    assert R.run_id(1, "D-L1-001", 0) != R.run_id(3, "D-L1-001", 1)


def test_resume_skips_recorded_runs_and_never_duplicates(tmp_path, patched):
    first = run_it(tmp_path, patched, [1, 2], limit=5)
    assert sum(s["n"] for s in first.values()) == 5
    calls = []

    def counting(*a, **k):
        calls.append(a[1]["qid"])
        return fake_agent(*a, **k)

    run_it(tmp_path, patched, [1, 2], agent=counting)
    assert len(calls) == 12 - 5
    ids = [r["run_id"] for r in RN.load_records(tmp_path)]
    assert len(ids) == len(set(ids)) == 12
    run_it(tmp_path, patched, [1, 2], agent=counting)      # nothing left
    assert len(calls) == 7
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["total_runs"] == 12 and all(v["duplicates"] == 0 for v in m["files"].values())


def test_a_torn_last_line_is_survived(tmp_path, patched):
    run_it(tmp_path, patched, [1], limit=3)
    f = RN.path_of(tmp_path, 1)
    f.write_text(f.read_text() + '{"run_id": "torn", "cond')             # a kill in mid-write
    assert len(RN.load_records(tmp_path)) == 3
    run_it(tmp_path, patched, [1])
    recs = RN.load_records(tmp_path)
    assert len(recs) == 6 and len({r["run_id"] for r in recs}) == 6


def test_an_exception_in_a_run_becomes_a_record_and_the_run_goes_on(tmp_path, patched):
    def flaky(method, q, *a, **k):
        if q["qid"] == "D-L1-002":
            raise RuntimeError("boom")
        return fake_agent(method, q, *a, **k)

    run_it(tmp_path, patched, [1], agent=flaky)
    recs = {r["qid"]: r for r in RN.load_records(tmp_path)}
    assert len(recs) == 6
    bad = recs["D-L1-002"]
    assert bad["status"] == "exec_fail" and bad["fail_kind"] == "runner_exception"
    assert "boom" in bad["error_detail"] and R.validate_record(bad) == []
    assert recs["D-L1-003"]["correct"]


def test_real_agents_with_a_scripted_model_produce_valid_records(tmp_path, patched):
    q = {**make_questions(1)[0], "answer_type": "int"}
    interp = {"interpretation": blank_interpretation(target="ship_count", unit="ships")}
    step = {"reading": [], "decision": None,
            "action": {"type": "tool", "tool": "detect_ships", "args": {"image_id": "m3.jpg"}}}
    ans = {"reading": [{"from": "c1", "field": "count", "value": 3}], "decision": None,
           "action": {"type": "answer", "answer": 3, "unit": "ships"}}
    RN.run([1], "dev", [q], tmp_path, FakeLLM([interp, step, ans]), ctx=patched, log=lambda *_: None)
    (rec,) = RN.load_records(tmp_path)
    assert rec["correct"] and R.validate_record(rec) == [] and rec["reachable_answer"] == 3


def test_summary_numbers():
    recs = [{"status": "ok", "correct": True, "fail_kind": None, "tool_calls": 2, "llm_calls": 4, "wall_ms": 2000},
            {"status": "exec_fail", "correct": False, "fail_kind": "format_error", "tool_calls": 1,
             "llm_calls": 2, "wall_ms": 4000}]
    s = RN.summarize(recs)
    assert s["accuracy"] == 0.5 and s["fail_rate"] == 0.5 and s["fail_kinds"] == {"format_error": 1}
    assert s["mean_wall_s"] == 3.0 and s["format_error_rate"] == 0.5


def test_validate_record_flags_bad_records():
    good = fake_agent("stepwise", make_questions(1)[0], None, None)
    good.update(run_id="x", condition=1, input="label", reachable_answer=3, boxes_hash="h",
                meta={k: None for k in R.META_KEYS})
    assert R.validate_record(good) == []
    assert R.validate_record({**good, "status": "weird"})
    assert R.validate_record({**good, "status": "exec_fail", "fail_kind": "nope"})
    assert R.validate_record({k: v for k, v in good.items() if k != "turns"})


# ---------------------------------------------------------------- freeze guard

def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src/sarqa/analysis").mkdir(parents=True)
    (root / "configs").mkdir()
    (root / "data").mkdir()
    (root / "src/sarqa/core.py").write_text("x = 1\n")
    (root / "src/sarqa/analysis/a.py").write_text("y = 1\n")
    (root / "configs/default.yaml").write_text("seed: 1\n")
    (root / "pyproject.toml").write_text("[project]\n")
    (root / "data/test.json").write_text('{"q": 1}')
    digest = hashlib.sha256((root / "data/test.json").read_bytes()).hexdigest()
    (root / "PROTOCOL.md").write_text(f"| file | hash |\n|---|---|\n| `data/test.json` | `{digest}` |\n"
                                      "| `data/other.json` | — |\n")
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    git(root, "tag", "freeze-v1")
    (root / ".gitignore").write_text("")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "ignore")
    return root


REQUIRED = ["data/test.json"]


def test_guard_passes_on_a_clean_frozen_tree(repo):
    assert check_freeze(repo, REQUIRED) == []
    assert protocol_hashes(repo / "PROTOCOL.md").keys() == {"data/test.json"}


def test_guard_refuses_a_dirty_tree(repo):
    (repo / "notes.txt").write_text("x")
    assert any("not clean" in p for p in check_freeze(repo, REQUIRED))


def test_guard_refuses_frozen_file_changes_but_not_analysis_or_docs(repo):
    (repo / "src/sarqa/analysis/a.py").write_text("y = 2\n")
    (repo / "README.md").write_text("docs")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "analysis and docs only")
    assert check_freeze(repo, REQUIRED) == []
    (repo / "src/sarqa/core.py").write_text("x = 2\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change frozen code")
    assert any("frozen files changed" in p and "core.py" in p for p in check_freeze(repo, REQUIRED))
    git(repo, "tag", "freeze-v2")                                       # newest tag is the reference
    assert check_freeze(repo, REQUIRED) == []


def test_guard_refuses_hash_mismatch_missing_row_and_missing_tag(repo):
    (repo / "data/test.json").write_text('{"q": 2}')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "data changed")
    assert any("does not match" in p for p in check_freeze(repo, REQUIRED))
    assert any("no hash for data/absent.json" in p for p in check_freeze(repo, ["data/absent.json"]))
    git(repo, "tag", "-d", "freeze-v1")
    assert any("no freeze-v* tag" in p for p in check_freeze(repo, REQUIRED))


def test_run_refuses_the_test_split_when_the_guard_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(RN, "check_freeze", lambda root: ["no freeze-v* tag exists"])
    called = []
    with pytest.raises(RN.FreezeGuardError, match="no freeze-v"):
        RN.run([1], "test", make_questions(1), tmp_path, FakeLLM([]), agent=lambda *a, **k: called.append(1),
               log=lambda *_: None)
    assert not called and not list(tmp_path.glob("*.jsonl"))
