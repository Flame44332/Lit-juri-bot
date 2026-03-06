from dataclasses import dataclass
import json
import os

import db
from services.utils import now_local_str


@dataclass
class ResultRow:
    class_id: str
    song_title: str
    total: int
    vocal_total: int
    video_total: int
    vocal_video_total: int
    performance_total: int
    parallel: int
    performance_order: int


def _get_vocal_criterion_ids() -> list[int]:
    criteria = db.list_criteria()
    ids: list[int] = []
    for c in criteria:
        name = str(c["name"]).strip().lower()
        group_key = (c["group_key"] or "").strip().lower()
        if group_key == "vocal" or name.startswith("вокал"):
            ids.append(int(c["id"]))
    return ids


def _get_video_criterion_ids() -> list[int]:
    criteria = db.list_criteria()
    ids: list[int] = []
    for c in criteria:
        name = str(c["name"]).strip().lower()
        group_key = (c["group_key"] or "").strip().lower()
        if group_key == "video" or name.startswith("видео"):
            ids.append(int(c["id"]))
    return ids


def _get_performance_criterion_ids() -> list[int]:
    criteria = db.list_criteria()
    ids: list[int] = []
    for c in criteria:
        name = str(c["name"]).strip().lower()
        group_key = (c["group_key"] or "").strip().lower()
        if group_key == "performance" or name.startswith("яркость"):
            ids.append(int(c["id"]))
    return ids


def _collect_scores_by_class_and_jury(
    vocal_ids: list[int], video_ids: list[int], performance_ids: list[int]
) -> dict[str, dict[int, dict[str, int]]]:
    criterion_group: dict[int, str] = {}
    for cid in vocal_ids:
        criterion_group.setdefault(int(cid), "vocal")
    for cid in video_ids:
        criterion_group.setdefault(int(cid), "video")
    for cid in performance_ids:
        criterion_group.setdefault(int(cid), "performance")

    if not criterion_group:
        return {}

    criterion_ids = sorted(criterion_group.keys())
    placeholders = ",".join("?" for _ in criterion_ids)
    with db.get_conn() as conn:
        rows = conn.execute(
            f"SELECT class_id, telegram_id, criterion_id, score FROM votes WHERE criterion_id IN ({placeholders})",
            criterion_ids,
        ).fetchall()

    result: dict[str, dict[int, dict[str, int]]] = {}
    for row in rows:
        class_id = str(row["class_id"])
        jury_id = int(row["telegram_id"])
        criterion_id = int(row["criterion_id"])
        score = int(row["score"] or 0)
        group = criterion_group.get(criterion_id)
        if not group:
            continue
        jury_scores = result.setdefault(class_id, {}).setdefault(
            jury_id, {"vocal": 0, "video": 0, "performance": 0}
        )
        jury_scores[group] += score

    return result


def _sort_rows(rows: list[ResultRow]) -> list[ResultRow]:
    return sorted(
        rows,
        key=lambda r: (-r.total, -r.performance_total, r.performance_order, r.class_id),
    )


def _build_awards(rows: list[ResultRow]) -> dict:
    if not rows:
        return {"grand_prix": None, "parallels": []}
    ordered = _sort_rows(rows)
    grand_prix = ordered[0] if ordered else None
    by_parallel: dict[int, list[ResultRow]] = {}
    for row in ordered:
        if grand_prix and row.class_id == grand_prix.class_id:
            continue
        by_parallel.setdefault(int(row.parallel), []).append(row)
    parallels = []
    for parallel in sorted(by_parallel.keys()):
        candidates = by_parallel.get(parallel, [])
        gold = candidates[0] if len(candidates) > 0 else None
        silver = candidates[1] if len(candidates) > 1 else None
        parallels.append(
            {
                "parallel": parallel,
                "gold": gold,
                "silver": silver,
            }
        )
    return {"grand_prix": grand_prix, "parallels": parallels}


def get_results() -> list[ResultRow]:
    classes = db.list_classes_ordered()
    vocal_ids = _get_vocal_criterion_ids()
    video_ids = _get_video_criterion_ids()
    performance_ids = _get_performance_criterion_ids()
    scores_by_class = _collect_scores_by_class_and_jury(vocal_ids, video_ids, performance_ids)

    rows: list[ResultRow] = []
    for cls in classes:
        class_id = cls["class_id"]
        class_scores = scores_by_class.get(class_id, {})
        vocal_total = 0
        video_total = 0
        performance_total = 0
        final_total = 0
        for jury_scores in class_scores.values():
            vocal_jury = int(jury_scores.get("vocal", 0) or 0)
            video_jury = int(jury_scores.get("video", 0) or 0)
            performance_jury = int(jury_scores.get("performance", 0) or 0)
            vocal_total += vocal_jury
            video_total += video_jury
            performance_total += performance_jury
            final_total += (vocal_jury + video_jury) * performance_jury
        rows.append(
            ResultRow(
                class_id=class_id,
                song_title=cls["song_title"] or "—",
                total=final_total,
                vocal_total=vocal_total,
                video_total=video_total,
                vocal_video_total=vocal_total + video_total,
                performance_total=performance_total,
                parallel=int(cls["parallel"]),
                performance_order=int(cls["performance_order"] or 0),
            )
        )

    return _sort_rows(rows)


def count_jury_voted() -> int:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT telegram_id) AS cnt FROM votes"
        ).fetchone()
        return int(row["cnt"])


def format_results(title: str, results: list[ResultRow], jury_voted: int, jury_total: int) -> str:
    lines: list[str] = []
    lines.append(f"🏆 {title}")
    lines.append("")
    awards = _build_awards(results)
    grand_prix = awards.get("grand_prix")
    if grand_prix:
        lines.append(
            f"Гран-при: {grand_prix.class_id} — {grand_prix.song_title} — {grand_prix.total} балл."
        )
    else:
        lines.append("Гран-при: —")

    lines.append("")
    if awards.get("parallels"):
        lines.append("Параллели:")
        for item in awards["parallels"]:
            parallel = item["parallel"]
            gold = item.get("gold")
            silver = item.get("silver")
            lines.append(f"{parallel} параллель:")
            if gold:
                lines.append(f"🥇 Золото: {gold.class_id} — {gold.song_title} — {gold.total} балл.")
            else:
                lines.append("🥇 Золото: —")
            if silver:
                lines.append(f"🥈 Серебро: {silver.class_id} — {silver.song_title} — {silver.total} балл.")
            else:
                lines.append("🥈 Серебро: —")
    else:
        lines.append("Параллели: —")

    lines.append("")
    lines.append("Полный рейтинг:")
    for idx, row in enumerate(results, start=1):
        lines.append(
            f"{idx}. {row.class_id} — {row.song_title} — {row.total} балл. "
            f"(вокал+видео {row.vocal_video_total}, яркость {row.performance_total})"
        )

    lines.append("")
    lines.append(f"Жюри с оценками: {jury_voted}/{jury_total}")
    lines.append(f"Сформировано: {now_local_str()}")
    return "\n".join(lines)


def build_results_payload(title: str = "Итоги голосования") -> dict:
    res = get_results()
    awards = _build_awards(res)
    return {
        "title": title,
        "generated_at": now_local_str(),
        "jury_voted": count_jury_voted(),
        "jury_total": db.count_jury(),
        "classes": [
            {
                "class_id": r.class_id,
                "song_title": r.song_title,
                "total": r.total,
                "vocal_total": r.vocal_total,
                "video_total": r.video_total,
                "vocal_video_total": r.vocal_video_total,
                "performance_total": r.performance_total,
                "parallel": r.parallel,
                "performance_order": r.performance_order,
            }
            for r in res
        ],
        "awards": {
            "grand_prix": _award_payload(awards.get("grand_prix")),
            "parallels": [
                {
                    "parallel": item["parallel"],
                    "gold": _award_payload(item.get("gold")),
                    "silver": _award_payload(item.get("silver")),
                }
                for item in awards.get("parallels", [])
            ],
        },
    }


def _award_payload(row: ResultRow | None) -> dict | None:
    if not row:
        return None
    return {
        "class_id": row.class_id,
        "song_title": row.song_title,
        "total": row.total,
        "vocal_total": row.vocal_total,
        "video_total": row.video_total,
        "vocal_video_total": row.vocal_video_total,
        "performance_total": row.performance_total,
        "parallel": row.parallel,
        "performance_order": row.performance_order,
    }


def export_results_json(path: str, title: str = "Итоги голосования") -> None:
    payload = build_results_payload(title=title)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
