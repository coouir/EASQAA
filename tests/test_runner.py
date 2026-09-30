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
    assert len({q["qid"] for q, _ in first_block}) == 1 and sorted(c.id for _, c in first_block) == [1, 2, 6, 7, 8, 9, 10, 11]
    orders = {tuple(c.id for _, c in p1[i * 8:(i + 1) * 8]) for i in range(5)}
    assert len(orders) > 1                                       # the condition order differs between questions
    assert {tuple(sorted(o)) for o in orders} == {(1, 2, 6, 7, 8, 9, 10, 11)}
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
                meta={k: None for k in R.META_KEYS}, run_index=0, started_at="2026-10-01T00:00:00Z", server=None)
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


def test_pilot_b_subset_is_thirty_deterministic_questions_with_the_level_mix():
    from sarqa.run.pilot import pilot_b_subset

    qs = [{**q, "qid": f"D-{lv}-{i:03d}", "level": lv, "box_dependent": i % 5 != 0}
          for lv in ("L1", "L2", "L3", "L4", "L5") for i, q in enumerate([make_questions(1)[0]] * 25, 1)]
    a, b = pilot_b_subset(qs), pilot_b_subset(qs)
    assert a == b and len(a) == 30
    from collections import Counter
    assert Counter(q["level"] for q in a) == {"L1": 6, "L2": 7, "L3": 8, "L4": 7, "L5": 2}
    assert all(q["box_dependent"] for q in a)                 # enough box-dependent ones exist in every level


# ---------------------------------------------------------------- A2: server identity, order file, timestamps

def test_records_carry_run_index_start_time_server_and_prompt_tokens(tmp_path, patched, monkeypatch):
    from sarqa.run.server import ServerIdentity

    class Watch:
        def __init__(self, host):
            pass

        def identity(self):
            return ServerIdentity(4242, "2026-10-01T00:00:00Z")

    monkeypatch.setattr(RN, "ServerWatch", Watch)
    run_it(tmp_path, patched, [1, 2])
    recs = RN.load_records(tmp_path)
    assert R.validate_record(recs[0]) == []
    assert sorted(r["run_index"] for r in recs) == list(range(12))
    assert all(r["server"] == {"pid": 4242, "started_at": "2026-10-01T00:00:00Z"} for r in recs)
    assert all(r["started_at"].endswith("Z") and len(r["started_at"]) == 20 for r in recs)
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["servers"] == [{"pid": 4242, "started_at": "2026-10-01T00:00:00Z", "runs": 12,
                             "first_run_index": 0, "last_run_index": 11}]


def test_a_changed_server_is_logged_and_the_run_continues(tmp_path, patched, monkeypatch):
    from sarqa.run.server import ServerIdentity

    ids = iter([ServerIdentity(1, "a")] + [ServerIdentity(1, "a")] * 3 + [ServerIdentity(2, "b")] * 20)

    class Watch:
        def __init__(self, host):
            pass

        def identity(self):
            return next(ids)

    monkeypatch.setattr(RN, "ServerWatch", Watch)
    lines = []
    RN.run([1], "dev", make_questions(), tmp_path, FakeLLM([]), ctx=patched, log=lines.append, agent=fake_agent)
    warn = [x for x in lines if "server process changed" in x]
    assert len(warn) == 1 and "no automatic restart" in warn[0]
    recs = sorted(RN.load_records(tmp_path), key=lambda r: r["run_index"])
    assert len(recs) == 6 and [r["server"]["pid"] for r in recs] == [1, 1, 1, 2, 2, 2]
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert [s["pid"] for s in m["servers"]] == [1, 2]


def test_order_file_is_saved_hashed_in_the_manifest_and_stable_on_resume(tmp_path, patched):
    run_it(tmp_path, patched, [1, 2], limit=4)
    first = (tmp_path / "order.json").read_text()
    doc = json.loads(first)
    assert len(doc["runs"]) == 12 and [r["run_index"] for r in doc["runs"]] == list(range(12))
    run_it(tmp_path, patched, [1, 2])                            # resume with the same arguments
    assert (tmp_path / "order.json").read_text() == first
    m = json.loads((tmp_path / "manifest.json").read_text())
    import hashlib
    assert m["order_files"] == {"order.json": hashlib.sha256(first.encode()).hexdigest()}
    recs = RN.load_records(tmp_path)
    by_id = {r["run_id"]: r["run_index"] for r in recs}
    assert all(by_id[x["run_id"]] == x["run_index"] for x in doc["runs"])       # records follow the saved order
    run_it(tmp_path, patched, [1])                                # a different plan gets its own file
    assert (tmp_path / "order.json").read_text() == first
    assert len(list(tmp_path.glob("order_*.json"))) == 1


def test_prompt_tokens_max_is_the_largest_single_call():
    q = {**QUESTION_FOR_TOKENS}
    llm = FakeLLM([INTERP_FOR_TOKENS, {"reading": [], "decision": None, "action": {"type": "answer", "answer": 3, "unit": "ships"}}])
    llm_calls = []
    orig = llm.chat

    def chat(messages, schema, seed, timeout=300):
        r = orig(messages, schema, seed, timeout)
        r.tokens_in = 100 * (len(llm_calls) + 1)
        llm_calls.append(1)
        return r

    llm.chat = chat
    from sarqa.agents import run_agent
    rec = run_agent("stepwise", q, mini_context(), llm)
    assert rec["prompt_tokens_max"] == 200 and rec["tokens_in"] == 300


QUESTION_FOR_TOKENS = {"qid": "D-L1-001", "level": "L1", "image_id": "m3.jpg", "text_ko": "몇 척인가?",
                       "answer_type": "int", "unit": "ships", "gold_answer": 3, "tolerance": {"rel": 0.0},
                       "budget": 4, "gold_calls": 1}
INTERP_FOR_TOKENS = {"interpretation": blank_interpretation(target="ship_count", unit="ships")}


def test_keep_alive_is_sent_with_every_request(monkeypatch):
    from sarqa.agents.llm import OllamaClient

    sent = {}

    def fake_post(self, path, body, timeout):
        sent.update(body)
        return {"message": {"content": "{}"}, "prompt_eval_count": 5, "eval_count": 1}

    monkeypatch.setattr(OllamaClient, "_post", fake_post)
    OllamaClient().chat([{"role": "user", "content": "x"}], {"type": "object"}, seed=1)
    assert sent["keep_alive"] == -1 and sent["options"]["seed"] == 1 and sent["think"] is False


# ---------------------------------------------------------------- server identity from /proc (fake proc tree)

def _fake_proc(tmp_path, pid=777, port=11434, inode=99999, ticks=123456, btime=1_700_000_000):
    proc = tmp_path / "proc"
    (proc / "net").mkdir(parents=True)
    (proc / "net" / "tcp").write_text(
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
        f"   0: 0100007F:{port:04X} 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 {inode} 1 x\n"
        f"   1: 0100007F:1F90 00000000:0000 01 00000000:00000000 00:00000000 00000000  1000        0 555 1 x\n")
    (proc / "stat").write_text(f"cpu  1 2 3\nbtime {btime}\n")
    d = proc / str(pid)
    (d / "fd").mkdir(parents=True)
    (d / "fd" / "5").symlink_to(f"socket:[{inode}]")
    (d / "stat").write_text(f"{pid} (ollama serve) S 1 1 1 0 -1 4194560 0 0 0 0 0 0 0 0 20 0 8 0 {ticks} 1 2 3\n")
    return proc


def test_server_identity_from_proc(tmp_path):
    import datetime as dt
    import os

    from sarqa.run.server import ServerWatch, find_pid, port_of, start_time

    proc = _fake_proc(tmp_path)
    assert port_of("http://localhost:11434") == 11434 and port_of("localhost:11435") == 11435
    assert find_pid(11434, proc) == 777 and find_pid(9999, proc) is None
    hz = os.sysconf("SC_CLK_TCK")
    expect = dt.datetime.fromtimestamp(1_700_000_000 + 123456 / hz, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert start_time(777, proc) == expect
    w = ServerWatch("http://localhost:11434", proc)
    ident = w.identity()
    assert (ident.pid, ident.started_at) == (777, expect) and w.identity() == ident
    (proc / "777" / "stat").write_text((proc / "777" / "stat").read_text().replace("123456", "999999"))
    assert w.identity().started_at != expect                     # same pid reused with a new start time = a new server
    assert ServerWatch("http://gpu-box.example:11434", proc).identity() is None       # remote host: unknown
