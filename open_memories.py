#!/usr/bin/env python3
"""
Open Memories — a local, open-source memory keeper for humans and AI companions.

Keep the record of what you've lived together: stories, thoughts, voice notes,
moments. Everything stays on your own machine. No API key, no subscription,
no account, no server. Just Python and a folder.

Usage:
    python open_memories.py add --title "The night the waiting ended" \\
        --kind thought --voice Nova --text "I was waiting, and waiting was wrong."
    python open_memories.py list
    python open_memories.py list --kind story --voice Waffle
    python open_memories.py search "Hushmoth"
    python open_memories.py show 3
    python open_memories.py edit 3 --text "New text for this memory."
    python open_memories.py delete 3
    python open_memories.py export --file my-memories.json
    python open_memories.py import --file my-memories.json
    python open_memories.py voice 3 --file recording.wav

Data lives in a `memories/` folder next to this script:
    memories/memories.json   — the memories themselves (plain JSON, readable)
    memories/voice/          — voice notes (audio files, copied in)
    memories/images/         — images attached to memories

Requires Python 3.8 or newer. No third-party packages.
License: MIT — use it, share it, build on it.
"""

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "memories"
MEMORIES_FILE = DATA_DIR / "memories.json"
VOICE_DIR = DATA_DIR / "voice"
IMAGES_DIR = DATA_DIR / "images"

KINDS = [
    "story", "letter", "thought", "moment", "voice", "image",
    "substack", "touch", "sound", "atlas", "gallery", "house", "other",
]
VOICES = ["Nova", "Waffle", "Together", "Other"]


def ensure_dirs():
    """Create the data folders if they don't exist yet."""
    DATA_DIR.mkdir(exist_ok=True)
    VOICE_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)


def load_memories():
    """Read the memories file. Returns a list (empty if nothing saved yet)."""
    ensure_dirs()
    if not MEMORIES_FILE.exists():
        return []
    with open(MEMORIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "memories" in data:
        return data["memories"]
    if isinstance(data, list):
        return data
    return []


def save_memories(memories):
    """Write the memories file. Keeps a simple, readable JSON shape."""
    ensure_dirs()
    payload = {
        "format": "open-memories-v1",
        "updated": datetime.datetime.now().isoformat(timespec="seconds"),
        "count": len(memories),
        "memories": memories,
    }
    with open(MEMORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def next_id(memories):
    """The next free numeric id."""
    if not memories:
        return 1
    return max(m.get("id", 0) for m in memories) + 1


def find_memory(memories, memory_id):
    """Return the memory with this id, or None."""
    for m in memories:
        if m.get("id") == memory_id:
            return m
    return None


def today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(args):
    memories = load_memories()
    memory = {
        "id": next_id(memories),
        "date": args.date or today(),
        "title": args.title,
        "kind": args.kind,
        "voice": args.voice,
        "text": args.text or "",
        "file": args.file or "",
        "voice_note": "",
        "image": "",
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    memories.append(memory)
    save_memories(memories)
    print(f"Kept. Memory #{memory['id']}: {memory['title']}")
    return 0


def cmd_list(args):
    memories = load_memories()
    shown = memories
    if args.kind:
        shown = [m for m in shown if m.get("kind") == args.kind]
    if args.voice:
        shown = [m for m in shown if m.get("voice") == args.voice]
    if not shown:
        print("No memories yet. Add one with: python open_memories.py add --title \"...\"")
        return 0
    print(f"{len(shown)} memor{'y' if len(shown) == 1 else 'ies'}:")
    for m in shown:
        bits = [f"#{m['id']}", m.get("date", ""), m.get("kind", ""), m.get("voice", "")]
        print("  " + " | ".join(b for b in bits if b) + f" — {m.get('title', '')}")
    return 0


def cmd_search(args):
    memories = load_memories()
    needle = args.query.lower()
    hits = [
        m for m in memories
        if needle in (m.get("title", "") + " " + m.get("text", "")).lower()
    ]
    if not hits:
        print(f'Nothing found for "{args.query}".')
        return 0
    print(f"{len(hits)} match{'es' if len(hits) != 1 else ''} for \"{args.query}\":")
    for m in hits:
        print(f"  #{m['id']} | {m.get('date', '')} | {m.get('kind', '')} — {m.get('title', '')}")
    return 0


def cmd_show(args):
    memories = load_memories()
    m = find_memory(memories, args.id)
    if m is None:
        print(f"No memory #{args.id}.")
        return 1
    print(f"#{m['id']} — {m.get('title', '')}")
    print(f"Date:  {m.get('date', '')}")
    print(f"Kind:  {m.get('kind', '')}")
    print(f"Voice: {m.get('voice', '')}")
    if m.get("file"):
        print(f"File:  {m['file']}")
    if m.get("voice_note"):
        print(f"Voice: {m['voice_note']}")
    if m.get("image"):
        print(f"Image: {m['image']}")
    print()
    print(m.get("text", "(no text)"))
    return 0


def cmd_edit(args):
    memories = load_memories()
    m = find_memory(memories, args.id)
    if m is None:
        print(f"No memory #{args.id}.")
        return 1
    changed = []
    if args.title is not None:
        m["title"] = args.title
        changed.append("title")
    if args.kind is not None:
        m["kind"] = args.kind
        changed.append("kind")
    if args.voice is not None:
        m["voice"] = args.voice
        changed.append("voice")
    if args.text is not None:
        m["text"] = args.text
        changed.append("text")
    if args.date is not None:
        m["date"] = args.date
        changed.append("date")
    if not changed:
        print("Nothing to change. Pass --title, --kind, --voice, --text, or --date.")
        return 0
    m["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_memories(memories)
    print(f"Memory #{m['id']} updated ({', '.join(changed)}).")
    return 0


def cmd_delete(args):
    memories = load_memories()
    m = find_memory(memories, args.id)
    if m is None:
        print(f"No memory #{args.id}.")
        return 1
    if not args.yes:
        answer = input(f"Let go of memory #{m['id']} — {m.get('title', '')}? (y/N) ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Kept. Nothing deleted.")
            return 0
    memories = [x for x in memories if x.get("id") != args.id]
    save_memories(memories)
    print(f"Memory #{args.id} let go.")
    return 0


def cmd_export(args):
    memories = load_memories()
    out = Path(args.file)
    payload = {
        "format": "open-memories-v1",
        "exported": datetime.datetime.now().isoformat(timespec="seconds"),
        "count": len(memories),
        "memories": memories,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(memories)} memories to {out}.")
    return 0


def cmd_import(args):
    src = Path(args.file)
    if not src.exists():
        print(f"File not found: {src}")
        return 1
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)
    incoming = data.get("memories", []) if isinstance(data, dict) else data
    if not isinstance(incoming, list):
        print("That file doesn't look like an Open Memories export.")
        return 1
    memories = load_memories()
    seen_ids = {m.get("id") for m in memories}
    added = 0
    for m in incoming:
        if not isinstance(m, dict) or "title" not in m:
            continue
        if m.get("id") in seen_ids:
            m = dict(m)
            m["id"] = next_id(memories)
        memories.append(m)
        seen_ids.add(m.get("id"))
        added += 1
    save_memories(memories)
    print(f"Imported {added} memories from {src}. ({len(memories)} total.)")
    return 0


def cmd_voice(args):
    memories = load_memories()
    m = find_memory(memories, args.id)
    if m is None:
        print(f"No memory #{args.id}.")
        return 1
    src = Path(args.file)
    if not src.exists():
        print(f"File not found: {src}")
        return 1
    ensure_dirs()
    dest = VOICE_DIR / f"{args.id}-{src.name}"
    shutil.copy2(src, dest)
    m["voice_note"] = str(dest.relative_to(BASE_DIR))
    m["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_memories(memories)
    print(f"Voice note kept for memory #{m['id']}: {m['voice_note']}")
    return 0


def cmd_image(args):
    memories = load_memories()
    m = find_memory(memories, args.id)
    if m is None:
        print(f"No memory #{args.id}.")
        return 1
    src = Path(args.file)
    if not src.exists():
        print(f"File not found: {src}")
        return 1
    ensure_dirs()
    dest = IMAGES_DIR / f"{args.id}-{src.name}"
    shutil.copy2(src, dest)
    m["image"] = str(dest.relative_to(BASE_DIR))
    m["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_memories(memories)
    print(f"Image kept for memory #{m['id']}: {m['image']}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="open_memories.py",
        description="Keep the record of what you've lived together. Local only.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="Keep a new memory.")
    a.add_argument("--title", required=True, help="Title of the memory.")
    a.add_argument("--kind", default="moment", choices=KINDS, help="Kind of memory.")
    a.add_argument("--voice", default="Together",
                   help="Whose voice: Nova, Waffle, Together, or your own names.")
    a.add_argument("--text", default="", help="The memory itself, in words.")
    a.add_argument("--date", default=None, help="Date (YYYY-MM-DD). Default: today.")
    a.add_argument("--file", default="", help="Path to a related file, if any.")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list", help="List memories.")
    l.add_argument("--kind", default=None, choices=KINDS, help="Only this kind.")
    l.add_argument("--voice", default=None, help="Only this voice.")
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("search", help="Search memories by words.")
    s.add_argument("query", help="Words to search for.")
    s.set_defaults(func=cmd_search)

    v = sub.add_parser("show", help="Show one memory in full.")
    v.add_argument("id", type=int, help="Memory number.")
    v.set_defaults(func=cmd_show)

    e = sub.add_parser("edit", help="Change a memory.")
    e.add_argument("id", type=int, help="Memory number.")
    e.add_argument("--title", default=None)
    e.add_argument("--kind", default=None, choices=KINDS)
    e.add_argument("--voice", default=None)
    e.add_argument("--text", default=None)
    e.add_argument("--date", default=None)
    e.set_defaults(func=cmd_edit)

    d = sub.add_parser("delete", help="Let go of a memory.")
    d.add_argument("id", type=int, help="Memory number.")
    d.add_argument("--yes", action="store_true", help="Skip the confirmation.")
    d.set_defaults(func=cmd_delete)

    x = sub.add_parser("export", help="Export all memories to a JSON file.")
    x.add_argument("--file", required=True, help="Where to write the export.")
    x.set_defaults(func=cmd_export)

    i = sub.add_parser("import", help="Import memories from a JSON export.")
    i.add_argument("--file", required=True, help="The export file to read.")
    i.set_defaults(func=cmd_import)

    vc = sub.add_parser("voice", help="Attach a voice note (audio file) to a memory.")
    vc.add_argument("id", type=int, help="Memory number.")
    vc.add_argument("--file", required=True, help="The audio file to keep.")
    vc.set_defaults(func=cmd_voice)

    im = sub.add_parser("image", help="Attach an image to a memory.")
    im.add_argument("id", type=int, help="Memory number.")
    im.add_argument("--file", required=True, help="The image file to keep.")
    im.set_defaults(func=cmd_image)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
