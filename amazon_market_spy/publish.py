from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


DEFAULT_REPO_URL = "https://github.com/nhity2107-gif/amazon-market-spy-report.git"
DEFAULT_SITE_URL = "https://nhity2107-gif.github.io/amazon-market-spy-report/"
COMMIT_MESSAGE = "Update Amazon Market Spy report"

REPORT_PAGES = [
    "priority_board.html",
    "product_discovery.html",
    "products.html",
    "competitor.html",
    "trend_explorer.html",
    "product_detail.html",
    "top_winners.html",
    "new_breakouts.html",
    "fast_movers.html",
    "new_releases.html",
    "trends.html",
    "database.html",
    "top_opportunities.html",
    "image_gallery.html",
    "all_opportunities.html",
    "new_products.html",
    "rising_products.html",
    "seller_intelligence.html",
    "niche_intelligence.html",
    "source_explorer.html",
    "non_pod_excluded.html",
]

OPTIONAL_REPORT_PAGES = {
    "product_discovery.html",
    "competitor.html",
    "trend_explorer.html",
    "product_detail.html",
}


class PublishError(RuntimeError):
    """Raised when the GitHub Pages publish step cannot complete."""


def publish_report(
    output_dir: Path,
    publish_dir: Path = Path("publish"),
    repo_url: str = DEFAULT_REPO_URL,
    site_url: str = DEFAULT_SITE_URL,
) -> str:
    output_dir = Path(output_dir)
    publish_dir = Path(publish_dir)
    publish_dir.mkdir(parents=True, exist_ok=True)
    publish_dir = publish_dir.resolve()

    _copy_required_file(output_dir / "priority_board.html", publish_dir / "index.html")
    for page in REPORT_PAGES:
        if page in OPTIONAL_REPORT_PAGES:
            _copy_optional_file(output_dir / page, publish_dir / page)
        else:
            _copy_required_file(output_dir / page, publish_dir / page)
    _copy_images(output_dir, publish_dir)
    _copy_optional_tree(output_dir / "product_detail", publish_dir / "product_detail")
    _publish_with_git(publish_dir, repo_url)
    return site_url


def _copy_required_file(source: Path, target: Path) -> None:
    if not source.exists():
        raise PublishError(f"Required report not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_optional_file(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _copy_images(output_dir: Path, publish_dir: Path) -> None:
    image_source = _image_source(output_dir)
    image_target = publish_dir / "images"
    if image_target.exists():
        if image_target.is_dir():
            shutil.rmtree(image_target)
        else:
            image_target.unlink()
    if image_source is None:
        image_target.mkdir(parents=True, exist_ok=True)
        return
    shutil.copytree(image_source, image_target)


def _copy_optional_tree(source: Path, target: Path) -> None:
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    if source.is_dir():
        shutil.copytree(source, target)


def _image_source(output_dir: Path) -> Path | None:
    candidates = [output_dir / "images", output_dir.parent / "images", Path("images")]
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            key = candidate.resolve()
        except OSError:
            key = candidate.absolute()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_dir():
            return candidate
    return None


def _publish_with_git(publish_dir: Path, repo_url: str) -> None:
    _run_git(publish_dir, "init")
    _run_git(publish_dir, "branch", "-M", "main")
    remote = _run_git(publish_dir, "remote", "get-url", "origin", check=False)
    if remote.returncode == 0:
        _run_git(publish_dir, "remote", "set-url", "origin", repo_url)
    else:
        _run_git(publish_dir, "remote", "add", "origin", repo_url)
    _run_git(publish_dir, "add", ".")
    commit = _run_git(publish_dir, "commit", "-m", COMMIT_MESSAGE, check=False)
    if commit.returncode != 0 and not _nothing_to_commit(commit):
        raise PublishError(_git_error_message(("commit", "-m", COMMIT_MESSAGE), commit))
    _run_git(publish_dir, "push", "-u", "origin", "main")


def _run_git(
    publish_dir: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=publish_dir,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise PublishError(_git_error_message(args, result))
    return result


def _nothing_to_commit(result: subprocess.CompletedProcess[str]) -> bool:
    output = f"{result.stdout}\n{result.stderr}".lower()
    return "nothing to commit" in output or "working tree clean" in output


def _git_error_message(args: tuple[str, ...], result: subprocess.CompletedProcess[str]) -> str:
    details = (result.stderr or result.stdout or "").strip()
    command = "git " + " ".join(args)
    return f"{command} failed with exit code {result.returncode}: {details}"
