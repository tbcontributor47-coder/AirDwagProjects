import json
import subprocess
from pathlib import Path


def _write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _run(expected_obj, actual_obj, extra_args=None):
    if extra_args is None:
        extra_args = []

    # The verifier mounts tests at /tests; the app lives at /app.
    expected_path = Path("/tmp/expected.json")
    actual_path = Path("/tmp/actual.json")
    _write_json(expected_path, expected_obj)
    _write_json(actual_path, actual_obj)

    cmd = [
        "python3",
        "/app/compare_json.py",
        "--expected",
        str(expected_path),
        "--actual",
        str(actual_path),
        *extra_args,
    ]

    p = subprocess.run(cmd, text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def _assert_equal(rc, out):
    assert rc == 0
    assert out == "EQUAL\n"


def _assert_not_equal(rc, out):
    assert rc == 2
    lines = out.splitlines()
    assert lines[0] == "NOT_EQUAL"
    assert lines[1].startswith("FIRST_DIFF ")
    assert lines[2].startswith("EXPECTED ")
    assert lines[3].startswith("ACTUAL ")
    return lines


def test_equal_simple():
    rc, out, _ = _run({"a": 1}, {"a": 1})
    _assert_equal(rc, out)


def test_extra_key_fails():
    rc, out, _ = _run({"a": 1}, {"a": 1, "b": 2})
    lines = _assert_not_equal(rc, out)
    assert lines[1] == "FIRST_DIFF /b"


def test_missing_key_fails():
    rc, out, _ = _run({"a": 1, "b": 2}, {"a": 1})
    lines = _assert_not_equal(rc, out)
    assert lines[1] == "FIRST_DIFF /b"


def test_null_not_missing():
    rc, out, _ = _run({"a": None}, {})
    lines = _assert_not_equal(rc, out)
    assert lines[1] == "FIRST_DIFF /a"


def test_trailing_whitespace_ignored():
    rc, out, _ = _run({"s": "a \n"}, {"s": "a\n"})
    _assert_equal(rc, out)


def test_internal_whitespace_not_ignored():
    rc, out, _ = _run({"s": "a b"}, {"s": "a  b"})
    _assert_not_equal(rc, out)


def test_number_tolerance_equal():
    rc, out, _ = _run({"n": 1.0}, {"n": 1.0009}, ["--tolerance", "0.001"])
    _assert_equal(rc, out)


def test_number_tolerance_not_equal():
    rc, out, _ = _run({"n": 1.0}, {"n": 1.0009}, ["--tolerance", "0.0005"])
    _assert_not_equal(rc, out)


def test_array_order_sensitive_by_default():
    rc, out, _ = _run({"values": [1, 2]}, {"values": [2, 1]})
    lines = _assert_not_equal(rc, out)
    assert lines[1] == "FIRST_DIFF /values/0"


def test_items_array_order_insensitive():
    rc, out, _ = _run({"items": [{"id": 1}, {"id": 2}]}, {"items": [{"id": 2}, {"id": 1}]})
    _assert_equal(rc, out)


def test_items_multiset_duplicates():
    rc, out, _ = _run({"items": [1, 1, 2]}, {"items": [1, 2, 2]})
    lines = _assert_not_equal(rc, out)
    assert lines[1] == "FIRST_DIFF /items"


def test_ignore_pointer_nested_subtree():
    expected = {"meta": {"generated_at": "2020-01-01T00:00:00Z", "version": 1}, "data": {"x": 1}}
    actual = {"meta": {"generated_at": "2021-01-01T00:00:00Z", "version": 1}, "data": {"x": 1}}

    rc, out, _ = _run(expected, actual, ["--ignore", "/meta/generated_at"])
    _assert_equal(rc, out)

    # Ensure ignore does not mask other mismatches
    actual2 = {"meta": {"generated_at": "2021-01-01T00:00:00Z", "version": 2}, "data": {"x": 1}}
    rc2, out2, _ = _run(expected, actual2, ["--ignore", "/meta/generated_at"])
    lines = _assert_not_equal(rc2, out2)
    assert lines[1] == "FIRST_DIFF /meta/version"
