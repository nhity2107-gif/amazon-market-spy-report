from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from amazon_market_spy.cli import main
from amazon_market_spy.publish import COMMIT_MESSAGE, publish_report


class PublishTests(unittest.TestCase):
    def test_publish_report_command_copies_reports_and_adds_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            _write_reports(output_dir)
            (root / "images").mkdir()
            (root / "images" / "root-image.jpg").write_bytes(b"root")
            (output_dir / "images").mkdir()
            (output_dir / "images" / "output-image.jpg").write_bytes(b"output")
            commands: list[tuple[list[str], Path]] = []
            old_cwd = Path.cwd()

            try:
                os.chdir(root)
                with patch(
                    "amazon_market_spy.publish.subprocess.run",
                    side_effect=_fake_git(commands, remote_exists=False),
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        exit_code = main(
                            [
                                "publish-report",
                                "--output",
                                str(output_dir),
                                "--repo-url",
                                "https://example.com/report.git",
                                "--site-url",
                                "https://example.com/report/",
                            ]
                        )
            finally:
                os.chdir(old_cwd)

            publish_dir = root / "publish"
            self.assertEqual(exit_code, 0)
            self.assertEqual((publish_dir / "index.html").read_text(encoding="utf-8"), "priority")
            self.assertEqual((publish_dir / "priority_board.html").read_text(encoding="utf-8"), "priority")
            self.assertEqual((publish_dir / "products.html").read_text(encoding="utf-8"), "products")
            self.assertEqual((publish_dir / "top_winners.html").read_text(encoding="utf-8"), "winners")
            self.assertEqual((publish_dir / "new_breakouts.html").read_text(encoding="utf-8"), "breakouts")
            self.assertEqual((publish_dir / "fast_movers.html").read_text(encoding="utf-8"), "movers")
            self.assertEqual((publish_dir / "new_releases.html").read_text(encoding="utf-8"), "releases")
            self.assertEqual((publish_dir / "trends.html").read_text(encoding="utf-8"), "trends")
            self.assertEqual((publish_dir / "database.html").read_text(encoding="utf-8"), "database")
            self.assertEqual((publish_dir / "top_opportunities.html").read_text(encoding="utf-8"), "top")
            self.assertEqual((publish_dir / "image_gallery.html").read_text(encoding="utf-8"), "gallery")
            self.assertEqual((publish_dir / "all_opportunities.html").read_text(encoding="utf-8"), "all")
            self.assertEqual((publish_dir / "new_products.html").read_text(encoding="utf-8"), "new")
            self.assertEqual((publish_dir / "rising_products.html").read_text(encoding="utf-8"), "rising")
            self.assertEqual((publish_dir / "seller_intelligence.html").read_text(encoding="utf-8"), "sellers")
            self.assertEqual((publish_dir / "niche_intelligence.html").read_text(encoding="utf-8"), "niches")
            self.assertEqual((publish_dir / "source_explorer.html").read_text(encoding="utf-8"), "sources")
            self.assertEqual((publish_dir / "non_pod_excluded.html").read_text(encoding="utf-8"), "excluded")
            self.assertTrue((publish_dir / "images" / "output-image.jpg").exists())
            self.assertFalse((publish_dir / "images" / "root-image.jpg").exists())
            self.assertEqual(
                [command for command, _ in commands],
                [
                    ["git", "init"],
                    ["git", "branch", "-M", "main"],
                    ["git", "remote", "get-url", "origin"],
                    ["git", "remote", "add", "origin", "https://example.com/report.git"],
                    ["git", "add", "."],
                    ["git", "commit", "-m", COMMIT_MESSAGE],
                    ["git", "push", "-u", "origin", "main"],
                ],
            )
            self.assertTrue(all(cwd == publish_dir for _, cwd in commands))
            self.assertEqual(stdout.getvalue(), "Report published:\nhttps://example.com/report/\n")

    def test_publish_report_uses_root_images_and_updates_existing_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            publish_dir = root / "publish"
            _write_reports(output_dir)
            (root / "images").mkdir()
            (root / "images" / "root-image.jpg").write_bytes(b"root")
            commands: list[tuple[list[str], Path]] = []
            old_cwd = Path.cwd()

            try:
                os.chdir(root)
                with patch(
                    "amazon_market_spy.publish.subprocess.run",
                    side_effect=_fake_git(commands, remote_exists=True),
                ):
                    site_url = publish_report(
                        output_dir=output_dir,
                        publish_dir=publish_dir,
                        repo_url="https://example.com/changed.git",
                        site_url="https://example.com/site/",
                    )
            finally:
                os.chdir(old_cwd)

            self.assertEqual(site_url, "https://example.com/site/")
            self.assertTrue((publish_dir / "images" / "root-image.jpg").exists())
            self.assertIn(["git", "remote", "set-url", "origin", "https://example.com/changed.git"], [command for command, _ in commands])
            self.assertNotIn(["git", "remote", "add", "origin", "https://example.com/changed.git"], [command for command, _ in commands])


def _write_reports(output_dir: Path) -> None:
    output_dir.mkdir(parents=True)
    (output_dir / "priority_board.html").write_text("priority", encoding="utf-8")
    (output_dir / "products.html").write_text("products", encoding="utf-8")
    (output_dir / "top_winners.html").write_text("winners", encoding="utf-8")
    (output_dir / "new_breakouts.html").write_text("breakouts", encoding="utf-8")
    (output_dir / "fast_movers.html").write_text("movers", encoding="utf-8")
    (output_dir / "new_releases.html").write_text("releases", encoding="utf-8")
    (output_dir / "trends.html").write_text("trends", encoding="utf-8")
    (output_dir / "database.html").write_text("database", encoding="utf-8")
    (output_dir / "top_opportunities.html").write_text("top", encoding="utf-8")
    (output_dir / "image_gallery.html").write_text("gallery", encoding="utf-8")
    (output_dir / "all_opportunities.html").write_text("all", encoding="utf-8")
    (output_dir / "new_products.html").write_text("new", encoding="utf-8")
    (output_dir / "rising_products.html").write_text("rising", encoding="utf-8")
    (output_dir / "seller_intelligence.html").write_text("sellers", encoding="utf-8")
    (output_dir / "niche_intelligence.html").write_text("niches", encoding="utf-8")
    (output_dir / "source_explorer.html").write_text("sources", encoding="utf-8")
    (output_dir / "non_pod_excluded.html").write_text("excluded", encoding="utf-8")


def _fake_git(commands: list[tuple[list[str], Path]], remote_exists: bool):
    def run(
        command: list[str],
        cwd: Path,
        text: bool,
        capture_output: bool,
    ) -> subprocess.CompletedProcess[str]:
        commands.append((command, cwd))
        if command == ["git", "remote", "get-url", "origin"] and not remote_exists:
            return subprocess.CompletedProcess(command, 2, "", "error: No such remote 'origin'")
        return subprocess.CompletedProcess(command, 0, "", "")

    return run


if __name__ == "__main__":
    unittest.main()
