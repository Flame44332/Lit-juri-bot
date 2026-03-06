import argparse

import db

SEED_ENTRIES = [
    ("10.6", "Arabian night"),
    ("11.2", "Heads will roll - yeah yeah yeahs"),
    ("11.1", "A little party never kill nobody- Marlie Grace"),
    ("9.4", "How bad can I be"),
    ("10.2", "Another Brick in the Wall"),
    ("9.1", "Chess"),
    ("10.4", "Another day of sun"),
    ("9.6", "Monster high"),
    ("11.5", "Andrew Underberg - Hell's Greatest Dad"),
    ("9.5", "Friend like me"),
    ("9.3", "Rewrite the stars"),
    ("10.1", "La sein"),
    ("10.5", "Poppuri"),
    ("11.6", "The greatest show"),
    ("11.4", "Diamonds are a girl's best friend"),
    ("10.3", "Be our Guest"),
    ("9.2", "Shut up and dance"),
    ("11.3", "Hot Wings (I Wanna Party)"),
]

SEED_BY_CLASS = {class_id: song for class_id, song in SEED_ENTRIES}
SEED_SONGS = [song for _, song in SEED_ENTRIES]


def seed(force: bool = False) -> None:
    db.init_db()
    classes = db.list_classes_ordered()
    for idx, cls in enumerate(classes, start=1):
        class_id = cls["class_id"]
        song = SEED_BY_CLASS.get(class_id, SEED_SONGS[(idx - 1) % len(SEED_SONGS)])
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
