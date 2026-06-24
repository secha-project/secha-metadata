import lineage


def test_lineage_docs_are_current() -> None:
    """The committed docs/lineage_<vendor>.md must match what lineage.py generates."""
    assert lineage.main(["--check"]) == 0, "lineage docs are stale — run: python lineage.py"
