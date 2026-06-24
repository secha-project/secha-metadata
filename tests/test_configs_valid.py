from validate import validate


def test_all_metadata_valid_and_cross_referenced() -> None:
    errors = validate()
    assert errors == [], "metadata problems:\n" + "\n".join(errors)
