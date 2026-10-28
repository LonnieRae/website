import hashlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

loader = importlib.machinery.SourceFileLoader("fetch_journey_media",
                                              str(Path(__file__).parents[1] / "fetch-journey-media"))
spec = importlib.util.spec_from_loader(loader.name, loader)
fetch = importlib.util.module_from_spec(spec)
loader.exec_module(fetch)

REPO = "winnowwallet/winnow"
SHA = "0123456789abcdef0123456789abcdef01234567"


def entry(data, **fields):
    return dict(fields, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def artifact_zip(run_id=7, sha=SHA, tamper=None, video=True, result="passed"):
    files = {"screenshots/01-onboarding.png": b"\x89PNG\r\n\x1a\nfirst",
             "screenshots/04-home-funded.png": b"\x89PNG\r\n\x1a\nsecond",
             fetch.VIDEO: b"recording"}
    evidence = {"version": 2, "source_sha": sha, "result": "passed",
                "run_url": f"https://github.com/{REPO}/actions/runs/{run_id}",
                "tests": [{"name": "testCreateReceiveSendConfirm", "result": result, "seconds": 1.5}],
                "screenshots": [entry(files[f"screenshots/{n}.png"], name=n, test="testCreateReceiveSendConfirm",
                                      width=4, height=8) for n in ("01-onboarding", "04-home-funded")],
                "video": entry(files[fetch.VIDEO], width=720, height=1566, duration_seconds=3.0,
                               path=fetch.VIDEO) if video else None}
    if not video:
        evidence["video_omitted"] = "no ffmpeg"
    if tamper:
        tamper(files, evidence)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(fetch.MANIFEST, json.dumps(evidence))
        for name, data in files.items():
            bundle.writestr(name, data)
    return buffer.getvalue()


def run(run_id, branch="main", status="completed", conclusion="success", sha=SHA):
    return {"id": run_id, "head_branch": branch, "status": status, "conclusion": conclusion, "head_sha": sha,
            "path": ".github/workflows/ci.yml", "event": "push"}


class FakeClient:
    def __init__(self, runs, artifacts, archives):
        self.runs, self.artifacts, self.archives, self.calls = runs, artifacts, archives, []

    def json(self, path):
        self.calls.append(path)
        if "/actions/workflows/" in path:
            return {"workflow_runs": [r for r in self.runs.values() if r["conclusion"] == "success"]}
        if path.endswith("/artifacts?name=journey-media&per_page=10"):
            return {"artifacts": self.artifacts.get(int(path.split("/runs/")[1].split("/")[0]), [])}
        return self.runs[int(path.rsplit("/", 1)[1])]

    def download(self, url, limit=fetch.MAX_ARCHIVE):
        return self.archives[url]


def artifact(number, expired=False):
    return {"id": number, "name": "journey-media", "expired": expired, "created_at": "2026-10-28T00:00:00Z",
            "archive_download_url": f"https://api.github.com/artifacts/{number}/zip", "size_in_bytes": 100}


class FetchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.docs = Path(temporary.name) / "docs"
        (self.docs / "screenshots").mkdir(parents=True)
        (self.docs / "videos").mkdir()
        (self.docs / fetch.VIDEO).write_bytes(b"committed recording")

    def args(self, run_id=None, strict=False):
        return fetch.argparse.Namespace(repo=REPO, branch="main", workflow="ci.yml", run_id=run_id, wait=0,
                                        out=self.docs, strict=strict)

    def test_newest_successful_run_with_the_artifact_is_placed(self):
        client = FakeClient({9: run(9), 8: run(8, conclusion="failure"), 7: run(7)},
                            {9: [artifact(90, expired=True)], 7: [artifact(70)]},
                            {"https://api.github.com/artifacts/70/zip": artifact_zip(7)})
        evidence = fetch.fetch(client, self.args())
        self.assertEqual(evidence["run_url"], f"https://github.com/{REPO}/actions/runs/7")
        self.assertEqual((self.docs / fetch.VIDEO).read_bytes(), b"recording")
        self.assertEqual((self.docs / "screenshots/04-home-funded.png").read_bytes(), b"\x89PNG\r\n\x1a\nsecond")
        self.assertEqual(json.loads((self.docs / fetch.MANIFEST).read_text())["version"], 2)

    def test_the_dispatched_run_comes_first(self):
        client = FakeClient({9: run(9), 7: run(7)}, {9: [artifact(90)], 7: [artifact(70)]},
                            {"https://api.github.com/artifacts/70/zip": artifact_zip(7)})
        fetch.fetch(client, self.args(run_id=7))
        self.assertEqual(client.calls[0], f"/repos/{REPO}/actions/runs/7")

    def test_a_dispatched_run_on_another_branch_falls_back_to_main(self):
        client = FakeClient({9: run(9), 5: run(5, branch="feature")}, {9: [artifact(90)], 5: [artifact(50)]},
                            {"https://api.github.com/artifacts/90/zip": artifact_zip(9)})
        evidence = fetch.fetch(client, self.args(run_id=5))
        self.assertTrue(evidence["run_url"].endswith("/runs/9"))

    def test_no_usable_run_is_unusable(self):
        client = FakeClient({9: run(9)}, {9: []}, {})
        with self.assertRaisesRegex(fetch.Unusable, "no successful ci.yml run on main"):
            fetch.fetch(client, self.args())

    def check_rejected(self, pattern, **kwargs):
        archive = artifact_zip(**kwargs)
        with self.assertRaisesRegex(fetch.Unusable, pattern):
            fetch.verify(archive, run(7))

    def test_a_changed_file_is_rejected(self):
        self.check_rejected("01-onboarding.png does not match",
                            tamper=lambda files, _: files.update({"screenshots/01-onboarding.png": b"\x89PNG\r\n\x1a\nX"}))

    def test_a_missing_file_is_rejected(self):
        self.check_rejected("no videos/wallet-journey.mp4", tamper=lambda files, _: files.pop(fetch.VIDEO))

    def test_a_failed_test_is_rejected(self):
        self.check_rejected("not every test passed", result="failed")

    def test_media_without_video_is_rejected(self):
        self.check_rejected("published no video: no ffmpeg", video=False)

    def test_media_from_another_run_or_commit_is_rejected(self):
        self.check_rejected("is not run 7", run_id=8)
        self.check_rejected("commit is not run 7", sha="f" * 40)

    def test_an_oversized_file_is_rejected(self):
        big = b"\x00" * (fetch.MAX_BYTES + 1)

        def grow(files, evidence):
            files[fetch.VIDEO] = big
            evidence["video"].update(bytes=len(big), sha256=hashlib.sha256(big).hexdigest())
        self.check_rejected("over the 25 MiB", tamper=grow)

    def test_paths_outside_the_manifest_are_never_written(self):
        archive = artifact_zip(tamper=lambda files, _: files.update({"../escape.png": b"x", "index.html": b"x"}))
        _, files = fetch.verify(archive, run(7))
        self.assertEqual(sorted(files), [fetch.MANIFEST, "screenshots/01-onboarding.png",
                                         "screenshots/04-home-funded.png", fetch.VIDEO])

    def test_failure_keeps_the_committed_media_and_exits_0_unless_strict(self):
        with mock.patch.dict(fetch.os.environ, {"WALLET_ARTIFACTS_TOKEN": "", "GITHUB_TOKEN": ""}), \
                mock.patch.object(fetch.sys, "stderr", io.StringIO()) as stderr:
            self.assertEqual(fetch.main(["--out", str(self.docs)]), 0)
            self.assertIn("keeping the committed media", stderr.getvalue())
            self.assertEqual(fetch.main(["--out", str(self.docs), "--strict"]), 1)
        self.assertEqual((self.docs / fetch.VIDEO).read_bytes(), b"committed recording")
        self.assertFalse((self.docs / fetch.MANIFEST).exists())

    def test_an_empty_dispatched_run_id_means_none(self):
        with mock.patch.object(fetch, "fetch") as fetched, \
                mock.patch.dict(fetch.os.environ, {"WALLET_ARTIFACTS_TOKEN": "t"}):
            fetch.main(["--run-id", "", "--out", str(self.docs)])
        self.assertIsNone(fetched.call_args[0][1].run_id)

    def test_the_token_never_follows_a_redirect(self):
        seen = []

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def urlopen(request, timeout):
            seen.append(request)
            return Response(b"{}")
        with mock.patch.object(fetch.urllib.request, "urlopen", urlopen):
            fetch.Client("secret").json("/repos/x/y")
        self.assertEqual(seen[0].unredirected_hdrs.get("Authorization"), "Bearer secret")
        self.assertNotIn("Authorization", seen[0].headers)


if __name__ == "__main__":
    unittest.main()
