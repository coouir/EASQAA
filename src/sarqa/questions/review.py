"""Review sheets for the user: `docs/dev_questions.md` (wording) and `outputs/gold_check.csv` (SPEC §6.4
step 6: image, question, label-box summary, gold-solution result, path of an image with the boxes drawn).
"""

import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw

from sarqa.config import load_config, repo_path
from sarqa.questions.templates import TEMPLATES
from sarqa.tools.base import ToolContext


def _fmt(v) -> str:
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)


def write_review_md(questions: list[dict], path: str | Path, title: str) -> None:
    """One table per level with the exact question text and the gold answer, for wording review."""
    intro = ("문항 문구 검토용 표 (자동 생성: `sarqa questions review`). 문구·어휘·정답 풀이를 확인하고 "
             "고칠 곳을 알려 주세요. 정답은 라벨 상자에서 정답 풀이를 실행한 값입니다.")
    lines = [f"# {title}", "", intro, ""]
    for level in ("L1", "L2", "L3", "L4", "L5"):
        rows = [q for q in questions if q["level"] == level]
        if not rows:
            continue
        lines += [f"## {level} ({len(rows)}문항)", "",
                  "| qid | 템플릿 | 문구 | 정답 | 단위 | 호출 | 영상 |", "|---|---|---|---|---|---|---|"]
        for q in rows:
            lines.append(f"| {q['qid']} | `{q['template']}` | {q['text_ko']} | {_fmt(q['gold_answer'])} "
                         f"| {q['unit']} | {q['gold_calls']} | `{q['image_id']}` |")
        lines.append("")
    lines += ["## 템플릿별 문항 수", "", "| 템플릿 | 문항 수 | 상자 의존 | 분기 |", "|---|---|---|---|"]
    for tid, t in TEMPLATES.items():
        n = sum(q["template"] == tid for q in questions)
        lines.append(f"| `{tid}` | {n} | {'예' if t.box_dependent else '아니오'} | "
                     f"{'예' if t.has_branch else '아니오'} |")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _draw(ctx: ToolContext, image_id: str, out: Path) -> None:
    img = Image.fromarray(ctx.load_image(image_id)).convert("RGB")
    d = ImageDraw.Draw(img)
    for b in ctx.label_boxes.boxes(image_id):
        d.rectangle([b.x1, b.y1, b.x2, b.y2], outline=(255, 60, 60), width=2)
        d.text((b.x1, max(0, b.y1 - 11)), b.id, fill=(255, 255, 0))
    d.line([400, 0, 400, 800], fill=(80, 160, 255), width=1)
    d.line([0, 400, 800, 400], fill=(80, 160, 255), width=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def write_gold_check(questions: list[dict], ctx: ToolContext, csv_path: str | Path,
                     image_dir: str | Path | None = None) -> None:
    """CSV plus one annotated PNG per question (label boxes red, quadrant lines blue)."""
    image_dir = Path(image_dir or repo_path("outputs/gold_check"))
    fields = ["qid", "level", "template", "image_id", "scene", "n_ships", "text_ko", "gold_answer",
              "unit", "gold_calls", "label_boxes", "gold_steps", "annotated_image", "user_ok", "user_note"]
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        for q in questions:
            png = image_dir / f"{q['qid']}.png"
            _draw(ctx, q["image_id"], png)
            boxes = ctx.label_boxes.boxes(q["image_id"])
            inter = q["intermediates"]["label"]
            w.writerow({
                "qid": q["qid"], "level": q["level"], "template": q["template"],
                "image_id": q["image_id"],
                "scene": ctx.scenes.get(q["image_id"], ""), "n_ships": len(boxes),
                "text_ko": q["text_ko"], "gold_answer": _fmt(q["gold_answer"]), "unit": q["unit"],
                "gold_calls": q["gold_calls"],
                "label_boxes": " ".join(f"{b.id}:({b.x1},{b.y1},{b.x2},{b.y2})" for b in boxes),
                "gold_steps": json.dumps({k: v for k, v in inter.items()}, ensure_ascii=False)[:1500],
                "annotated_image": str(png), "user_ok": "", "user_note": ""})


def default_paths() -> dict:
    cfg = load_config()
    return {"dev": repo_path("data/questions/dev.json"),
            "review_md": repo_path("docs/dev_questions.md"),
            "gold_check": repo_path("outputs/gold_check.csv"), "cfg": cfg}
