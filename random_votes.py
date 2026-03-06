import argparse
import random

import db


def random_votes(force: bool = False, seed: int | None = None) -> None:
    db.init_db()
    if seed is not None:
        random.seed(seed)

    classes = db.list_classes_ordered()
    criteria = db.list_criteria()
    jury_ids = db.list_jury_ids()

    if not jury_ids:
        print("No jury users found. Create jury codes first.")
        return
    if not classes or not criteria:
        print("No classes or criteria found.")
        return

    total_written = 0
    for jury_id in jury_ids:
        for cls in classes:
            existing = db.get_votes_for_user_class(jury_id, cls["class_id"])
            for crit in criteria:
                crit_id = int(crit["id"])
                if not force and crit_id in existing:
                    continue
                min_score = crit["min_score"] if crit["min_score"] is not None else 1
                max_score = crit["max_score"] if crit["max_score"] is not None else 10
                score = random.randint(int(min_score), int(max_score))
                db.upsert_vote(jury_id, cls["class_id"], crit_id, score)
                total_written += 1

    print(f"Random votes written: {total_written}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие оценки")
    parser.add_argument("--seed", type=int, default=None, help="Seed для случайных значений")
    args = parser.parse_args()
    random_votes(force=args.force, seed=args.seed)
