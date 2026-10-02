"""Human check, version for one labeller (SPEC §11.5): first-deviation stage only, balanced order, guide on top.

    python -m sarqa.analysis.human_check --runs outputs/runs --questions data/questions/test.json \
        --classified outputs/analysis/classified.jsonl --out outputs/analysis

Reads the existing human sample (`human_sample_KEY/human_sample_key.csv` lists its runs, nothing there is changed)
and writes only new files:
  <out>/human_sample/human_check.html      guide on top, one card per run in the new order, stage select + note, CSV export
  <out>/human_sample/guide.html            the guide alone
  <out>/human_sample/human_order.csv       rank, run_id (nothing about the automatic labels)
  <out>/human_sample_KEY/human_order_strata.csv   rank, run_id, condition, stratum (opens the labels: keep closed)
Only runs with an agent error are labelled (input_only runs have no first deviation stage).

Order: strata = condition x automatic first-deviation stage. Runs inside a stratum are shuffled (fixed seed), then
the strata are visited round by round in a fixed random order, one run per stratum per round, so that stopping after
any number of runs (60, 100) leaves the strata as even as the sample allows.
"""

import argparse
import csv
import html
import json
import random
from pathlib import Path

from sarqa.analysis.human_sample import _trace_lines
from sarqa.analysis.main_run_human import form_row

SEED = 20261002
STAGE_CHOICES = (("interpretation", "1 질문 해석"), ("tool_selection", "2 도구 선택·호출"), ("result_reading", "3 결과 해석"),
                 ("planning_branch", "4 계획·분기"), ("calculation", "5 계산"), ("answer_formatting", "6 답 형식화"),
                 ("exec_fail", "0 실행 실패 (1~6단계 이탈 없이 최종 답이 없음)"), ("unknown", "판정할 수 없음"))
EXAMPLE_STAGES = ("interpretation", "tool_selection", "result_reading", "planning_branch", "calculation",
                  "answer_formatting", "exec_fail")

GUIDE_TABLE = (   # SPEC §11.3, wording kept
    ("0", "실행 실패", "최종 답이 없음. 실패 전의 턴에서 1~6단계 이탈이 있으면 그것을 첫 이탈 단계로, 없으면 첫 이탈 단계 = 실행 실패"),
    ("1", "질문 해석", ("`interpretation`의 필드 중 정답 풀이가 쓰는 필드가 `gold_interpretation`과 다르다. 닫힌 어휘이므로 enum은 정확히 비교하고, 기준값은 수치로 비교한다. "
          "<b>이 표본에서는 대상(target), 영역(region), 필터(filters), 분기 조건(branch)만 본다</b> (단위·답 유형은 판정하지 않는다, docs/deviations.md 2026-10-01)")),
    ("2", "도구 선택·호출", ("정답 풀이와 허용 대안 풀이 중 에이전트 실행과 가장 가까운 것을 기준으로, ① 필요한 정보를 어떤 도구로도 얻지 않고 답했다(호출 누락, 조기 종료 포함) "
          "② 필요한 정보를 얻으려 다른 도구를 불렀다 ③ `calc` 이외 도구의 인자(영역, 선박 ID, query 종류)가 틀렸다. 단 누락된 호출이 정답 풀이의 `foreach` 안에 있으면 4단계(반복 누락)")),
    ("3", "결과 해석", "`reading`(또는 `decision.condition_value`)의 값이 `from`이 가리키는 도구 출력의 값과 다르다(전사 오류). 또는 필요한 값을 다른 호출·필드에서 읽었다(선택 오류)"),
    ("4", "계획·분기", ("① 분기: 분기 조건을 에이전트가 받은 도구 출력의 실제 값에 적용했을 때의 분기와 `chosen`이 다르다(조건값을 잘못 읽은 경우는 3단계, 기준값·비교를 잘못 해석한 경우는 1단계가 먼저 잡는다) "
          "② 반복 누락: `foreach`의 대상 일부만 처리했다 ③ 순서: 아직 얻지 않은 값을 쓰려 했다")),
    ("5", "계산", "`calc`의 연산이나 인자(값·참조)가 정답 풀이와 다르다(받은 입력 기준). 값으로 적은 인자는 자신의 읽기·도구 출력과 비교한다. `calc` 없이 스스로 계산했으면 최종 값을 자신의 읽기로 계산한 값과 비교한다"),
    ("6", "답 형식화", "값은 자신의 중간 상태로 맞는데 최종 답의 전사·단위·반올림(허용 오차 초과)·범주 이름·JSON 형식이 다르다"),
)
GUIDE_RULES = (
    "<b>각 단계는 그 에이전트가 받은 입력을 기준으로 본다.</b> 앞 단계가 틀렸어도 뒤 단계는 &ldquo;받은 것을 올바르게 처리했는가&rdquo;만 본다. 받은 상자(파란 상자)가 틀렸어도 그 상자로 올바르게 처리했다면 이탈이 아니다.",
    "<b>가장 이른 턴의 이탈을 고른다. 같은 턴이면 위 표에서 앞 단계(번호가 작은 단계)를 고른다.</b> 일괄 계획은 계획 전체가 1턴, 답 생성 호출이 다음 턴이다. 질문 해석은 0턴(단계별) 또는 계획과 같은 1턴(일괄)에 적힌다.",
    ("<b>무해한 이탈은 제외한다.</b> 읽기 값·`calc` 인자·분기 선택은 그 값이 뒤의 어떤 호출·분기·답에도 쓰이지 않았거나, 올바른 값으로 바꿔도 정답 풀이의 나머지 결과가 같으면 무해하다. "
    "질문 해석은 정답 풀이가 쓰지 않는 필드만 다르거나, 쓰는 필드가 달라도 실제 호출·분기·답이 정답 해석대로 이뤄졌으면 무해하다. 쓰이지 않은 추가 호출, 오류를 받은 뒤 다시 호출해 복구한 도구 오류도 무해하다."),
    "<b>질문 해석은 대상, 영역, 필터, 분기 조건만으로 판정한다.</b>",
    "고를 수 있는 이탈이 하나도 없는데 답이 없으면 &ldquo;실행 실패&rdquo;, 어떤 단계인지 가를 수 없으면 &ldquo;판정할 수 없음&rdquo;을 고른다.",
)
CONSTRUCTED = {   # no clean real run outside the sample is available for these stages, so the examples are made up
    "result_reading": ("구성 예 (실제 실행 아님)", "이 영상의 선박은 몇 척인가?",
                       "c1 spatial_query count → {count: 4, ship_ids: [s1, s2, s3, s4]}\n[reading] c1.count = 6 (도구 출력은 4)\n[final answer] {\"value\": 6, \"unit\": \"ships\"}",
                       "도구는 4를 돌려줬는데 6으로 옮겨 적었다. 호출과 해석은 맞다 → 3단계."),
    "planning_branch": ("구성 예 (실제 실행 아님)", "분기 조건: 선박 수 ≥ 3 이면 then, 아니면 else.",
                        "c1 spatial_query count → {count: 5}\n[reading] c1.count = 5 (맞게 읽음)\n[decision] condition_value 5, threshold 3, cmp >=, chosen = else",
                        "받은 값 5에 조건을 적용하면 then인데 else를 골랐다. 값(3단계)과 기준값·비교(1단계)는 맞다 → 4단계."),
    "answer_formatting": ("구성 예 (실제 실행 아님)", "가장 긴 선박의 길이는? (정답 유형 float, 단위 px)",
                          "c3 calc max → {result: 61.0}\n[final answer] {\"value\": 61.0, \"unit\": \"ships\"}",
                          "값은 자신의 계산 결과와 같고 단위만 다르다 → 6단계."),
}


def eligible(key_rows: list[dict]) -> list[dict]:
    """Runs of the existing sample that have an agent error (they have a first deviation stage)."""
    return [k for k in key_rows if k["auto_cell"] != "input_only" and k["auto_first_deviation"] != "none"]


def balanced_order(items: list[dict], stratum, seed: int = SEED) -> list[dict]:
    """Round-robin over strata (fixed random order, shuffled inside), so every prefix is as even as possible."""
    rng = random.Random(seed)
    groups: dict = {}
    for it in sorted(items, key=lambda x: x["run_id"]):
        groups.setdefault(stratum(it), []).append(it)
    keys = sorted(groups, key=str)
    for k in keys:
        rng.shuffle(groups[k])
    out = []
    while any(groups.values()):
        order = [k for k in keys if groups[k]]
        rng.shuffle(order)
        out += [groups[k].pop() for k in order]
    return out


def _clip(line: str, n: int = 400) -> str:
    return line if len(line) <= n else line[:n] + " …"


def pick_examples(classified: list[dict], recs: dict, questions: dict, exclude: set) -> dict:
    """One short real run per stage, from agent-error runs of conditions 1/2 (then 4/5) that are not in the sample."""
    out = {}
    for stage in EXAMPLE_STAGES:
        if stage in CONSTRUCTED:
            continue
        pool = [c for c in classified if c["run_id"] not in exclude and c["agent_error"] and c["condition"] in (1, 2, 4, 5)
                and c["first_deviation_stage_name"] == stage and c["cell"] == "agent_only"]
        if stage == "tool_selection":   # a clear wrong call, not an extra one whose harm needs a replay to see
            pool = [c for c in pool if any(d["kind"] in ("wrong_tool", "wrong_args", "missing_call") and d["stage"] == 2 and not d["harmless"]
                                           and d["turn"] == c["first_deviation_turn"] for d in c["deviations"])]
        def second_deviation(c):   # a second deviation would give the labeller something to argue about
            return sum(not d["harmless"] for d in c["deviations"]) > 1

        pool.sort(key=lambda c: (c["condition"] not in (1, 2), second_deviation(c), len("\n".join(_trace_lines(recs[c["run_id"]]))), c["run_id"]))
        if not pool:
            continue
        c = pool[0]
        rec, q = recs[c["run_id"]], questions[c["qid"]]
        dev = next((d for d in c["deviations"] if d["stage"] == c["first_deviation_stage"] and not d["harmless"]), None)
        out[stage] = {"run_id": c["run_id"], "condition": c["condition"], "question": q["text_ko"], "gold": q["gold_answer"],
                      "program": json.dumps(q["program"], ensure_ascii=False), "gold_interpretation": json.dumps(q["gold_interpretation"], ensure_ascii=False),
                      "trace": "\n".join(_clip(x) for x in _trace_lines(rec)), "fail": rec.get("fail_kind") or "",
                      "why": f"{dev['kind']}: {dev['detail']}" if dev else f"fail_kind = {rec.get('fail_kind')}: {rec.get('error_detail')}"}
    return out


def guide_html(examples: dict) -> str:
    e = html.escape
    rows = "".join(f"<tr><td>{n}</td><td>{e(name)}</td><td>{desc}</td></tr>" for n, name, desc in GUIDE_TABLE)
    names = {n: name for n, name, _ in GUIDE_TABLE}
    stage_no = {"interpretation": "1", "tool_selection": "2", "result_reading": "3", "planning_branch": "4",
                "calculation": "5", "answer_formatting": "6", "exec_fail": "0"}
    ex = []
    for stage in EXAMPLE_STAGES:
        n = stage_no[stage]
        if stage in CONSTRUCTED:
            tag, qtxt, trace, why = CONSTRUCTED[stage]
            ex.append(f"<h4>{n} {e(names[n])} — {tag}</h4><p>{e(qtxt)}</p><pre>{e(trace)}</pre><p>→ {e(why)}</p>")
        elif stage in examples:
            x = examples[stage]
            ex.append(f"<h4>{n} {e(names[n])} — 실행 {x['run_id']} (조건 {x['condition']}, 표본 밖)</h4><p>{e(x['question'])} 정답 {e(str(x['gold']))}</p>"
                      f"<pre>gold 해석: {e(x['gold_interpretation'])}\ngold 풀이: {e(x['program'])}\n\n{e(x['trace'])}</pre><p>→ {e(x['why'])}</p>")
    rules = "".join(f"<li>{r}</li>" for r in GUIDE_RULES)
    return (f"<div class='guide'><h2>분류 기준표 (SPEC §11.3)</h2><p>건마다 에이전트 기록에서 <b>첫 이탈 단계</b>를 하나 고른다 (입력 오류 원인은 고르지 않는다).</p>"
            f"<table><tr><th>순서</th><th>단계</th><th>이탈로 판정하는 조건 (받은 입력 기준)</th></tr>{rows}</table><h3>규칙</h3><ol>{rules}</ol>"
            f"<h3>단계별 예</h3>{''.join(ex)}</div>")


CSS = ("body{font-family:sans-serif;max-width:1100px;margin:auto}section{border-top:3px solid #666;margin:1.5em 0}"
       "pre{white-space:pre-wrap;word-break:break-all;background:#f4f4f4;padding:.5em;font-size:12px;max-height:300px;overflow:auto}"
       ".g{display:grid;grid-template-columns:420px 1fr;gap:1em}.c{font-size:12px;color:#555}"
       ".guide{background:#fffbe6;border:1px solid #cc9;padding:0 1em 1em}.guide table{border-collapse:collapse;font-size:13px}"
       ".guide td,.guide th{border:1px solid #bbb;padding:3px 6px;vertical-align:top}#bar{position:sticky;top:0;background:#fff;padding:4px;border-bottom:1px solid #999}")

SCRIPT = """
const KEY='human_check_v1';let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
function save(){const v={};document.querySelectorAll('section').forEach(s=>{const o={};s.querySelectorAll('[data-f]').forEach(e=>o[e.dataset.f]=e.value);v[s.dataset.run]=o});
 try{localStorage.setItem(KEY,JSON.stringify(v))}catch(e){};count()}
function count(){const n=[...document.querySelectorAll("select[data-f='human_first_deviation']")].filter(e=>e.value).length;document.getElementById('n').textContent=n}
document.querySelectorAll('section').forEach(s=>{const o=saved[s.dataset.run]||{};s.querySelectorAll('[data-f]').forEach(e=>{if(o[e.dataset.f])e.value=o[e.dataset.f];e.addEventListener('change',save);e.addEventListener('input',save)})});count();
function dl(){const cols=['rank','run_id','human_first_deviation','human_note'];let out=[cols.join(',')];
 document.querySelectorAll('section').forEach(s=>{const v={rank:s.dataset.rank,run_id:s.dataset.run};s.querySelectorAll('[data-f]').forEach(e=>v[e.dataset.f]=e.value);
 out.push(cols.map(c=>'"'+String(v[c]||'').replace(/"/g,'""')+'"').join(','))});
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\\ufeff'+out.join('\\n')],{type:'text/csv'}));a.download='human_labels.csv';a.click()}
"""


def card(rank: int, total: int, r: dict) -> str:
    e = html.escape
    opts = "<option value=''></option>" + "".join(f"<option value='{k}'>{e(v)}</option>" for k, v in STAGE_CHOICES)
    img = f"<img src='{e(r['image'])}' width='400'>" if r["image"] else ""
    return (f"<section data-run='{r['run_id']}' data-rank='{rank}'><h3>#{rank}/{total} · {r['qid']} · 조건 {r['condition']} ({r['method']}, {e(r['input'])}) · {r['level']}</h3>"
            f"<p><b>{e(r['question'])}</b></p><p>gold <b>{e(str(r['gold_answer']))}</b> {r['unit']} · 받은 상자로 도달 가능한 답 "
            f"<b>{e(str(r['answer_reachable_from_received_boxes']))}</b> · 에이전트 답 {e(r['agent_answer'])} {e(r['fail_kind'])}</p>"
            f"<div class='g'><div>{img}<p class='c'>빨강 = 라벨 상자, 파랑 = 이 실행이 받은 상자, 초록 = 사분면 선</p></div>"
            f"<div><h4>gold 풀이</h4><pre>{e(r['gold_solution'])}</pre></div></div><h4>에이전트 기록</h4><pre>{e(r['agent_record'])}</pre>"
            f"<p>첫 이탈 단계 <select data-f='human_first_deviation'>{opts}</select> 메모 <input data-f='human_note' size='50'></p></section>")


def page(rows: list[dict], guide: str) -> str:
    cards = "".join(card(i + 1, len(rows), r) for i, r in enumerate(rows))
    return (f"<!doctype html><meta charset='utf-8'><title>human check</title><style>{CSS}</style>"
            f"<div id='bar'>분류한 건수 <b id='n'>0</b> / {len(rows)} · 앞에서부터 순서대로 (60건이나 100건에서 멈춰도 층이 고르게 남는 순서) · "
            f"<button onclick='dl()'>CSV 내려받기</button> (입력은 이 브라우저에 자동 저장됨)</div>{guide}"
            f"<h2>{len(rows)}건</h2><p>자동 분류는 어디에도 없다. 기준표, 질문, gold 풀이, 에이전트 기록만 보고 고른다.</p>{cards}<script>{SCRIPT}</script>")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def build(runs_dir: Path, questions: list[dict], classified: list[dict], out: Path) -> dict:
    from sarqa.run.runner import load_records

    form_dir, key_dir = out / "human_sample", out / "human_sample_KEY"
    with open(key_dir / "human_sample_key.csv", encoding="utf-8-sig", newline="") as f:
        key_rows = list(csv.DictReader(f))
    by_id = {c["run_id"]: c for c in classified}
    items = [dict(k, stratum=(int(k["condition"]), k["auto_first_deviation"])) for k in eligible(key_rows)]
    ordered = balanced_order(items, lambda x: x["stratum"])
    recs = {r["run_id"]: r for r in load_records(runs_dir)}
    by_q = {q["qid"]: q for q in questions}
    rows = []
    for it in ordered:
        c, rec = by_id[it["run_id"]], recs[it["run_id"]]
        image = f"images/{c['run_id']}.png"
        if not (form_dir / image).exists():
            raise SystemExit(f"missing image {form_dir / image}")
        rows.append(form_row(c, rec, by_q[c["qid"]], image))
    guide = guide_html(pick_examples(classified, recs, by_q, {k["run_id"] for k in key_rows}))
    (form_dir / "human_check.html").write_text(page(rows, guide), encoding="utf-8")
    (form_dir / "guide.html").write_text(f"<!doctype html><meta charset='utf-8'><title>guide</title><style>{CSS}</style>{guide}", encoding="utf-8")
    write_csv(form_dir / "human_order.csv", [{"rank": i + 1, "run_id": r["run_id"]} for i, r in enumerate(rows)])
    write_csv(key_dir / "human_order_strata.csv", [{"rank": i + 1, "run_id": it["run_id"], "condition": it["stratum"][0], "stratum_stage": it["stratum"][1]}
                                                   for i, it in enumerate(ordered)])
    lens = sorted(len(r["agent_record"]) + len(r["gold_solution"]) + len(r["question"]) for r in rows)
    return {"runs": len(rows), "html": str(form_dir / "human_check.html"), "chars_median": lens[len(lens) // 2], "chars_p90": lens[int(.9 * len(lens))]}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", default="outputs/runs")
    p.add_argument("--questions", default="data/questions/test.json")
    p.add_argument("--classified", default="outputs/analysis/classified.jsonl")
    p.add_argument("--out", default="outputs/analysis")
    a = p.parse_args(argv)
    questions = json.loads(Path(a.questions).read_text(encoding="utf-8"))["questions"]
    classified = [json.loads(x) for x in Path(a.classified).read_text(encoding="utf-8").splitlines() if x.strip()]
    print(json.dumps(build(Path(a.runs), questions, classified, Path(a.out)), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
