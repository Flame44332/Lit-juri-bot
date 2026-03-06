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

CLASS_ORDER = [
    "9.1", "9.2", "9.3", "9.4", "9.5", "9.6",
    "10.1", "10.2", "10.3", "10.4", "10.5", "10.6",
    "11.1", "11.2", "11.3", "11.4", "11.5", "11.6",
]


def seed(force: bool = False) -> None:
    db.init_db()
    for idx, class_id in enumerate(CLASS_ORDER):
        cls = db.get_class(class_id)
        if not cls:
            continue
        song = SEED_SONGS[idx % len(SEED_SONGS)]
        if not force and cls["song_title"]:
            continue
        db.update_class_song(class_id, song)
        db.update_class_order(class_id, idx + 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Перезаписать песни даже если они уже заданы")
    args = parser.parse_args()
    seed(force=args.force)
    print("Seed completed")
