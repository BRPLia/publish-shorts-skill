"""Release privacy regression tests with synthetic secrets and local files only."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_release.py"
SPEC = importlib.util.spec_from_file_location("prepare_release", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        local = SCRIPT.parents[1] / ".local" / "test-runs"
        local.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=local)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in release.PUBLIC_FILES:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("public fixture\n", encoding="utf-8")

    def test_export_excludes_private_state_media_and_notes(self):
        fixtures = [".local/config.json", ".local/plans/plan.json", ".env",
                    "video.mp4", "bitacora.md", "_mini-agent.md", "evals/review.json"]
        for name in fixtures:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("SYNTHETIC_PRIVATE_DATA", encoding="utf-8")
        output, archive = self.root / "public", self.root / "release.zip"
        result = release.export_public(output, archive, self.source)
        self.assertFalse(result["runtime_state_included"])
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            self.assertIsNone(package.testzip())
            self.assertTrue(all(name.startswith("buffer-shorts-skill/") for name in names))
            for name in names:
                self.assertNotIn(b"SYNTHETIC_PRIVATE_DATA", package.read(name))
            self.assertNotIn("buffer-shorts-skill/.local/config.json", names)
        manifest = json.loads((output / "RELEASE-MANIFEST.json").read_text())
        self.assertEqual(len(manifest["files"]), len(release.PUBLIC_FILES))
        self.assertFalse((output / "bitacora.md").exists())

    def test_export_blocks_literal_secret_without_echoing_value(self):
        secret = "synthetic_private_access_value_1234567890"
        (self.source / "examples/copy.json").write_text(
            json.dumps({"api_key": secret}), encoding="utf-8")
        with self.assertRaises(ValueError) as exc:
            release.collect_public(self.source)
        self.assertNotIn(secret, str(exc.exception))
        self.assertIn("literal_secret_assignment", str(exc.exception))

    def test_export_blocks_absolute_personal_path(self):
        personal_path = chr(68) + ":" + "/" + "private-user/video.mp4"
        (self.source / "README.md").write_text(personal_path, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "absolute_personal_path"):
            release.collect_public(self.source)

    def test_missing_required_public_file_fails_closed(self):
        (self.source / "SKILL.md").unlink()
        with self.assertRaisesRegex(ValueError, "Falta"):
            release.collect_public(self.source)

    def test_output_with_unexpected_files_is_not_overwritten(self):
        output = self.root / "public"
        output.mkdir()
        private = output / "personal.json"
        private.write_text("keep me", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "otros archivos"):
            release.export_public(output, self.root / "release.zip", self.source)
        self.assertEqual(private.read_text(), "keep me")

    def test_repository_output_is_not_modified(self):
        output = self.root / "public"
        (output / ".git").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "repositorio"):
            release.export_public(output, self.root / "release.zip", self.source)

    def test_cannot_export_over_source_folder(self):
        with self.assertRaisesRegex(ValueError, "separada"):
            release.export_public(self.source, self.root / "release.zip", self.source)

    def test_real_public_source_passes_scan(self):
        entries = release.collect_public()
        self.assertEqual(set(entries), set(release.PUBLIC_FILES))


if __name__ == "__main__":
    unittest.main()
