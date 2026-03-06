import argparse

import db

SEED_SONGS = [
    "Skyfall",
    "Rolling in the Deep",
    "Someone Like You",
    "Halo",
    "Believer",
    "Counting Stars",
    "Lovely",
    "Shallow",
    "Fix You",
    "Let It Be",
    "Radioactive",
    "Demons",
    "Perfect",
    "Bad Guy",
    "Take Me to Church",
    "Lovely Day",
    "Viva La Vida",
    "Shape of You",
]

def seed(force: bool = False) -> None:
    db.init_db()
    classes = db.list_classes_ordered()
    for idx, cls in enumerate(classes, start=1):
        class_id = cls["class_id"]
        song = SEED_SONGS[(idx - 1) % len(SEED_SONGS)]
        if not force and cls["song_title"]:
            db.update_class_order(class_id, idx)
            continue
        db.update_class_song(class_id, song)
        db.update_class_order(class_id, idx)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Перезаписать песни даже если они уже заданы")
    args = parser.parse_args()
    seed(force=args.force)
    print("Seed completed")
