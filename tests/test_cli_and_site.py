from pathlib import Path

from priorart.cli import main
from priorart.sitegen import build_site

ROOT = Path(__file__).resolve().parents[1]


def test_validate_privacy_and_sample_search() -> None:
    assert main(["validate"]) == 0
    assert main(["privacy"]) == 0
    assert (
        main(
            [
                "search",
                "sourceFileMap debugger",
                "--include-examples",
                "--embedder",
                "hash",
                "--expect-id",
                "example-windows-debugger-path",
                "--json",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "search",
                "sourceFileMap debugger",
                "--embedder",
                "hash",
                "--expect-id",
                "example-windows-debugger-path",
            ]
        )
        == 1
    )


def test_site_lists_the_example(tmp_path: Path) -> None:
    count = build_site(ROOT, tmp_path)
    assert count == 2
    page = (tmp_path / "fixes" / "example-windows-debugger-path.html").read_text(encoding="utf-8")
    guide = (tmp_path / "domains" / "example-windows-debugger.html").read_text(encoding="utf-8")
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Example only" in page
    assert "sourceFileMap" in page
    assert "Root cause" in page
    assert "Related fixes" in guide
    assert "example-windows-debugger-path" in index
    assert "Ignored by search" in index
