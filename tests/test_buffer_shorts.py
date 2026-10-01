"""Offline tests: every request is intercepted; temp files stay inside this package."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "buffer_shorts.py"
SPEC = importlib.util.spec_from_file_location("buffer_shorts", SCRIPT)
bs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bs)


def organizations(channels):
    return [{"id": "org", "name": "Org", "channels": channels}]


def channel(cid, service, name=None):
    return {"id": cid, "service": service, "name": name or service,
            "displayName": name or service}


class BufferShortsTests(unittest.TestCase):
    def setUp(self):
        local = SCRIPT.parents[1] / ".local" / "test-runs"
        local.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=local)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.publisher = bs.Publisher(self.root / "state")
        self.video = self.root / "short.mp4"
        self.video.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100)
        network = patch.object(bs.urllib.request, "urlopen",
                               side_effect=AssertionError("Unexpected live network"))
        network.start()
        self.addCleanup(network.stop)
        probe = patch.object(bs.shutil, "which", return_value=None)
        probe.start()
        self.addCleanup(probe.stop)

    def add(self, label="Cuenta", key="test-key", channels=None):
        with patch.object(bs, "discover", return_value=organizations(
                channels or [channel("yt", "youtube"), channel("ig", "instagram")])):
            return self.publisher.add_account(label, key)

    def plan(self, targets=None):
        if not self.publisher.config()["accounts"]:
            self.add()
        return self.publisher.prepare(self.video, targets or ["youtube"],
                                      "Título real", "Descripción real")

    def test_two_accounts_six_channels_keep_identity_and_group(self):
        first = self.add("Uno", "key1", [channel("a", "youtube"), channel("b", "instagram"), channel("c", "tiktok")])
        second = self.add("Dos", "key2", [channel("d", "youtube"), channel("e", "facebook"), channel("f", "linkedin")])
        self.assertEqual(len(self.publisher.channels()), 6)
        with self.assertRaisesRegex(bs.UserError, "ambiguo"):
            self.publisher.select(["youtube"])
        refs = [c["ref"] for c in first["channels"] + second["channels"]]
        group = self.publisher.group("Marca", refs)
        plan = self.plan(group["targets"] and refs)
        self.assertEqual(len(plan["entries"]), 6)
        self.assertEqual(len(self.publisher.config()["accounts"]), 2)

    def test_duplicate_key_does_not_create_second_account(self):
        self.add()
        with self.assertRaisesRegex(bs.UserError, "ya está"):
            self.publisher.add_account("Otra", "test-key")
        self.assertEqual(len(self.publisher.config()["accounts"]), 1)

    def test_no_fixed_three_channel_limit(self):
        self.add(channels=[channel(str(i), "youtube", "Canal " + str(i)) for i in range(5)])
        self.assertEqual(len(self.publisher.channels()), 5)

    def test_refresh_keeps_other_accounts_and_group(self):
        first = self.add()
        self.add("Otra", "other-key", [channel("fb", "facebook")])
        self.publisher.group("YT", [first["channels"][0]["ref"]])
        with patch.object(bs, "discover", return_value=organizations([channel("yt", "youtube"), channel("tk", "tiktok")])):
            self.publisher.refresh(first["account_id"])
        self.assertEqual({c["service"] for c in self.publisher.channels()}, {"youtube", "tiktok", "facebook"})
        self.assertIn("YT", self.publisher.config()["groups"])

    def test_prepare_does_not_contact_buffer_and_copy_ref_wins(self):
        account = self.add()
        ref = account["channels"][0]["ref"]
        with patch.object(bs, "graphql", side_effect=AssertionError("prepare contacted Buffer")):
            plan = self.publisher.prepare(self.video, [ref], "Base", "Descripción",
                {"youtube": {"title": "Por red"}, ref: {"title": "Por cuenta"}})
        self.assertEqual(plan["entries"][0]["copy"]["title"], "Por cuenta")
        self.assertFalse(plan["video_check"]["verified"])
        self.assertNotIn("test-key", json.dumps(plan))

    def test_youtube_separates_title_and_description(self):
        entry = self.plan()["entries"][0]
        data = bs.build_input(entry["target"], entry["copy"], "https://example.com/video.mp4")
        self.assertEqual(data["text"], "Descripción real")
        self.assertEqual(data["metadata"]["youtube"]["title"], "Título real")
        self.assertEqual(data["metadata"]["youtube"]["categoryId"], "24")
        self.assertEqual(data["mode"], "shareNow")

    def test_instagram_facebook_reels_and_tiktok_caption(self):
        for service in ["instagram", "facebook", "tiktok"]:
            with self.subTest(service=service):
                data = bs.build_input({"service": service, "channel_id": service},
                                      {"title": "Título", "description": "Descripción",
                                       "caption": "Caption específico"}, "https://example.com/v.mp4")
                self.assertEqual(data["text"], "Caption específico")
                if service in {"instagram", "facebook"}:
                    self.assertEqual(data["metadata"][service]["type"], "reel")
                else:
                    self.assertNotIn("tiktok", data["metadata"])

    def test_invalid_or_repeated_destination_is_rejected_before_upload(self):
        account = self.add()
        ref = account["channels"][0]["ref"]
        with self.assertRaises(bs.UserError):
            self.publisher.select(["missing"])
        with self.assertRaisesRegex(bs.UserError, "más de una"):
            self.publisher.select([ref, ref])

    def test_publish_requires_authorization_and_video_integrity(self):
        plan = self.plan()
        with self.assertRaisesRegex(bs.UserError, "autoriza"):
            self.publisher.publish(plan["plan"])
        self.video.write_bytes(self.video.read_bytes() + b"x")
        with self.assertRaisesRegex(bs.UserError, "cambió"):
            self.publisher.publish(plan["plan"], yes=True)

    def test_acceptance_is_not_sent_and_retry_does_not_duplicate(self):
        plan = self.plan()
        with patch.object(bs, "upload_video", return_value="https://example.com/v.mp4"), \
             patch.object(bs, "graphql", return_value={"createPost": {"post": {"id": "post1", "status": "sending"}}}) as api:
            result = self.publisher.publish(plan["plan"], yes=True)
            again = self.publisher.publish(plan["plan"], yes=True)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(result["results"][0]["status"], "sending")
        self.assertEqual(again["results"][0]["status"], "skipped")

    def test_status_confirms_delivery_and_returns_external_link(self):
        plan = self.plan()
        with patch.object(bs, "upload_video", return_value="https://example.com/v.mp4"), \
             patch.object(bs, "graphql", return_value={"createPost": {"post": {"id": "p", "status": "sending"}}}):
            self.publisher.publish(plan["plan"], yes=True)
        with patch.object(bs, "graphql", return_value={"post": {"id": "p", "status": "sent",
                "sentAt": "2026-10-01T12:00:00Z", "externalLink": "https://youtube.com/shorts/test",
                "error": None}}):
            result = self.publisher.status(plan["plan"])
        self.assertEqual(result["results"][0]["status"], "sent")
        self.assertIn("youtube.com", result["results"][0]["external_link"])

    def test_timeout_marks_unknown_and_blocks_republication(self):
        plan = self.plan()
        with patch.object(bs, "upload_video", return_value="https://example.com/v.mp4"), \
             patch.object(bs, "graphql", side_effect=bs.UserError("Timeout")):
            with self.assertRaises(bs.UserError):
                self.publisher.publish(plan["plan"], yes=True)
        with patch.object(bs, "upload_video", side_effect=AssertionError("reuploaded")), \
             patch.object(bs, "graphql", side_effect=AssertionError("duplicated")):
            result = self.publisher.publish(plan["plan"], yes=True)
        self.assertFalse(result["success"])
        self.assertEqual(result["results"][0]["status"], "blocked")

    def test_known_error_can_retry_but_malformed_response_cannot(self):
        plan = self.plan()
        with patch.object(bs, "upload_video", return_value="https://example.com/v.mp4"), \
             patch.object(bs, "graphql", return_value={"createPost": {"message": "Texto demasiado largo"}}):
            result = self.publisher.publish(plan["plan"], yes=True)
        self.assertFalse(result["success"])
        with patch.object(bs, "upload_video", return_value="https://example.com/v.mp4"), \
             patch.object(bs, "graphql", return_value={"createPost": {}}):
            result = self.publisher.publish(plan["plan"], yes=True)
        self.assertEqual(result["results"][0]["status"], "unknown")

    def test_two_accounts_use_the_correct_key_for_each_target(self):
        first = self.add("Uno", "key1", [channel("yt", "youtube")])
        second = self.add("Dos", "key2", [channel("ig", "instagram")])
        refs = [first["channels"][0]["ref"], second["channels"][0]["ref"]]
        plan = self.plan(refs)
        with patch.object(bs, "upload_video", return_value="https://example.com/v.mp4"), \
             patch.object(bs, "check_media_url"), \
             patch.object(bs, "graphql", side_effect=[
                 {"createPost": {"post": {"id": "p1", "status": "sending"}}},
                 {"createPost": {"post": {"id": "p2", "status": "sending"}}}]) as api:
            self.publisher.publish(plan["plan"], yes=True)
        self.assertEqual([call.args[0] for call in api.call_args_list], ["key1", "key2"])

    def test_account_output_never_prints_secret(self):
        self.add()
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            exit_code = bs.main(["--state-dir", str(self.publisher.state), "accounts", "list"])
        self.assertEqual(exit_code, 0)
        self.assertNotIn("test-key", output.getvalue())

    def test_http_rate_limit_returns_retry_after_without_key(self):
        error = urllib.error.HTTPError(bs.API_URL, 429, "Limit", {"Retry-After": "17"}, None)
        with patch.object(bs.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(bs.UserError, "17"):
                bs.graphql("secret", "query { account { id } }")

    def test_ai_generated_requires_real_boolean(self):
        target = {"service": "youtube", "channel_id": "yt"}
        copy = {"title": "Título", "description": "Texto", "ai_generated": False}
        result = bs.build_input(target, copy, "https://example.com/v.mp4")
        self.assertIs(result["metadata"]["youtube"]["isAiGenerated"], False)
        copy["ai_generated"] = "false"
        with self.assertRaisesRegex(bs.UserError, "booleano"):
            bs.build_input(target, copy, "https://example.com/v.mp4")

    def test_custom_media_must_match_local_video_hash(self):
        body = io.BytesIO(self.video.read_bytes())
        body.geturl = lambda: "https://example.com/video.mp4"
        with patch.object(bs.urllib.request, "urlopen", return_value=body):
            bs.check_media_url("https://example.com/video.mp4", bs.file_hash(self.video))
        other = io.BytesIO(b"\x00\x00\x00\x18ftypisom" + b"x" * 100)
        other.geturl = lambda: "https://example.com/video.mp4"
        with patch.object(bs.urllib.request, "urlopen", return_value=other):
            with self.assertRaisesRegex(bs.UserError, "mismo MP4"):
                bs.check_media_url("https://example.com/video.mp4", bs.file_hash(self.video))

    def uncertain_plan(self):
        plan = self.plan()
        with patch.object(bs, "upload_video", return_value="https://example.com/v.mp4"), \
             patch.object(bs, "graphql", side_effect=bs.UserError("Timeout")):
            with self.assertRaises(bs.UserError):
                self.publisher.publish(plan["plan"], yes=True)
        return plan

    def test_recovery_links_existing_post_and_verifies_channel(self):
        plan = self.uncertain_plan()
        ref = plan["entries"][0]["target"]["ref"]
        with patch.object(bs, "graphql", return_value={"post": {"id": "p", "channelId": "wrong", "status": "sent"}}):
            with self.assertRaisesRegex(bs.UserError, "otro canal"):
                self.publisher.recover(plan["plan"], ref, yes=True, post_id="p")
        with patch.object(bs, "graphql", return_value={"post": {"id": "p", "channelId": "yt", "status": "sent"}}):
            result = self.publisher.recover(plan["plan"], ref, yes=True, post_id="p")
        self.assertEqual(result["status"], "sent")
        with patch.object(bs, "graphql", side_effect=AssertionError("duplicated")):
            result = self.publisher.publish(plan["plan"], yes=True)
        self.assertEqual(result["results"][0]["status"], "skipped")

    def test_recovery_not_sent_needs_explicit_authorization(self):
        plan = self.uncertain_plan()
        ref = plan["entries"][0]["target"]["ref"]
        with self.assertRaisesRegex(bs.UserError, "autorizar"):
            self.publisher.recover(plan["plan"], ref, not_sent=True)
        result = self.publisher.recover(plan["plan"], ref, yes=True, not_sent=True)
        self.assertEqual(result["status"], "error")

    def test_status_shows_targets_not_yet_submitted(self):
        plan = self.plan()
        result = self.publisher.status(plan["plan"])
        self.assertEqual(result["results"][0]["status"], "not_submitted")

    def test_corrupt_configuration_returns_json_without_traceback(self):
        self.publisher.state.mkdir(parents=True)
        self.publisher.config_path.write_text("{broken", encoding="utf-8")
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            code = bs.main(["--state-dir", str(self.publisher.state), "accounts", "list"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["success"])

    def test_cli_help_works_without_configuration_or_network(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(SystemExit) as exc:
                bs.main(["--help"])
        self.assertEqual(exc.exception.code, 0)
        self.assertIn("prepare", output.getvalue())


if __name__ == "__main__":
    unittest.main()
