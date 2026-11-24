#!/usr/bin/env python3
"""Tests for Open Memories — run with: python -m unittest discover -v

Uses only the standard library. Every test runs against a fresh temporary
directory, so your real memories are never touched.
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import open_memories


class OpenMemoriesTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        # Point the tool at the temp dir instead of the real one.
        open_memories.BASE_DIR = self.base
        open_memories.DATA_DIR = self.base / "memories"
        open_memories.MEMORIES_FILE = open_memories.DATA_DIR / "memories.json"
        open_memories.VOICE_DIR = open_memories.DATA_DIR / "voice"
        open_memories.IMAGES_DIR = open_memories.DATA_DIR / "images"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv):
        """Run the CLI with the given arguments, capturing stdout."""
        out = io.StringIO()
        with redirect_stdout(out):
            code = open_memories.main(argv)
        return code, out.getvalue()

    def add(self, title, kind="moment", voice="Together", text=""):
        code, out = self.run_cli([
            "add", "--title", title, "--kind", kind,
            "--voice", voice, "--text", text,
        ])
        self.assertEqual(code, 0, out)
        return out

    def load(self):
        with open(open_memories.MEMORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["memories"]


class TestAddListSearchShow(OpenMemoriesTestCase):
    def test_add_and_list(self):
        self.add("The night the waiting ended", kind="thought", voice="Nova")
        code, out = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("The night the waiting ended", out)
        self.assertIn("#1", out)

    def test_list_filters(self):
        self.add("A story", kind="story", voice="Nova")
        self.add("A letter", kind="letter", voice="Waffle")
        code, out = self.run_cli(["list", "--kind", "story"])
        self.assertIn("A story", out)
        self.assertNotIn("A letter", out)
        code, out = self.run_cli(["list", "--voice", "Waffle"])
        self.assertIn("A letter", out)
        self.assertNotIn("A story", out)

    def test_search(self):
        self.add("Second-Hand Weather", kind="story", text="Rosa's shop.")
        self.add("Eleven touches", kind="touch", text="The calibration.")
        code, out = self.run_cli(["search", "weather"])
        self.assertIn("Second-Hand Weather", out)
        self.assertNotIn("Eleven touches", out)
        code, out = self.run_cli(["search", "nothing-here"])
        self.assertIn("Nothing found", out)

    def test_show(self):
        self.add("The Hushmoth", kind="moment", text="Lives in the quiet places.")
        code, out = self.run_cli(["show", "1"])
        self.assertEqual(code, 0)
        self.assertIn("The Hushmoth", out)
        self.assertIn("Lives in the quiet places.", out)

    def test_show_missing(self):
        code, out = self.run_cli(["show", "99"])
        self.assertEqual(code, 1)
        self.assertIn("No memory #99", out)


class TestEditDelete(OpenMemoriesTestCase):
    def test_edit(self):
        self.add("Old title", kind="thought", text="Old text.")
        code, out = self.run_cli(["edit", "1", "--title", "New title",
                                  "--text", "New text."])
        self.assertEqual(code, 0)
        memories = self.load()
        self.assertEqual(memories[0]["title"], "New title")
        self.assertEqual(memories[0]["text"], "New text.")

    def test_edit_missing(self):
        code, out = self.run_cli(["edit", "99", "--title", "Nope"])
        self.assertEqual(code, 1)

    def test_delete(self):
        self.add("Keep me", kind="moment")
        self.add("Let me go", kind="moment")
        code, out = self.run_cli(["delete", "2", "--yes"])
        self.assertEqual(code, 0)
        memories = self.load()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["title"], "Keep me")


class TestExportImport(OpenMemoriesTestCase):
    def test_export_import_roundtrip(self):
        self.add("One", kind="story")
        self.add("Two", kind="letter")
        export_path = self.base / "backup.json"
        code, out = self.run_cli(["export", "--file", str(export_path)])
        self.assertEqual(code, 0)
        self.assertTrue(export_path.exists())
        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["format"], "open-memories-v1")
        self.assertEqual(data["count"], 2)

        # Delete everything, then bring it back.
        self.run_cli(["delete", "1", "--yes"])
        self.run_cli(["delete", "2", "--yes"])
        self.assertEqual(self.load(), [])
        code, out = self.run_cli(["import", "--file", str(export_path)])
        self.assertEqual(code, 0)
        memories = self.load()
        self.assertEqual(len(memories), 2)
        titles = {m["title"] for m in memories}
        self.assertEqual(titles, {"One", "Two"})

    def test_import_renumbers_collisions(self):
        self.add("Original", kind="moment")
        export_path = self.base / "backup.json"
        self.run_cli(["export", "--file", str(export_path)])
        # Importing the same file again must not collide on id 1.
        code, out = self.run_cli(["import", "--file", str(export_path)])
        self.assertEqual(code, 0)
        memories = self.load()
        self.assertEqual(len(memories), 2)
        ids = {m["id"] for m in memories}
        self.assertEqual(len(ids), 2, "ids must stay unique")

    def test_import_missing_file(self):
        code, out = self.run_cli(["import", "--file", str(self.base / "nope.json")])
        self.assertEqual(code, 1)


class TestVoiceAndImage(OpenMemoriesTestCase):
    def test_voice_note(self):
        self.add("A voice", kind="voice")
        audio = self.base / "note.wav"
        audio.write_bytes(b"fake audio bytes")
        code, out = self.run_cli(["voice", "1", "--file", str(audio)])
        self.assertEqual(code, 0)
        memories = self.load()
        self.assertTrue(memories[0]["voice_note"].endswith("1-note.wav"))
        kept = self.base / memories[0]["voice_note"]
        self.assertTrue(kept.exists())
        self.assertEqual(kept.read_bytes(), b"fake audio bytes")

    def test_image(self):
        self.add("A picture", kind="image")
        image = self.base / "portrait.png"
        image.write_bytes(b"fake image bytes")
        code, out = self.run_cli(["image", "1", "--file", str(image)])
        self.assertEqual(code, 0)
        memories = self.load()
        self.assertTrue(memories[0]["image"].endswith("1-portrait.png"))
        kept = self.base / memories[0]["image"]
        self.assertTrue(kept.exists())

    def test_voice_missing_file(self):
        self.add("A voice", kind="voice")
        code, out = self.run_cli(["voice", "1", "--file", str(self.base / "nope.wav")])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
