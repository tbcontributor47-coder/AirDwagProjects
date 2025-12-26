"""Verifier tests for Terraform Drift Audit.

Tests call `python /app/drift_audit.py` to match the runtime contract.
"""

import json
import subprocess
import tempfile
from pathlib import Path


USAGE_LINE = (
    "Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>"
)


def run_audit(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["python", "/app/drift_audit.py", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def write_json(tmpdir: Path, name: str, obj: object) -> Path:
    path = tmpdir / name
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def parse_report(stdout: str) -> dict:
    return json.loads(stdout)


def test_usage_message_is_exact() -> None:
    """Usage errors must print the exact usage line."""
    code, out, err = run_audit([])
    assert code == 2
    assert out == ""
    assert err == USAGE_LINE + "\n"
    assert "Traceback" not in err


def test_missing_file_is_io_error_no_traceback() -> None:
    """Missing input files are I/O errors (exit 1) without tracebacks."""
    code, out, err = run_audit(["/tmp/nope_ideal.json", "/tmp/nope_current.json"])
    assert code == 1
    assert out == ""
    assert err.strip() != ""
    assert "Traceback" not in err


def test_invalid_json_is_parse_error_no_traceback() -> None:
    """Invalid JSON is a parse error (exit 2) without tracebacks."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal = tmpdir / "ideal.json"
        current = tmpdir / "current.json"
        ideal.write_text("{", encoding="utf-8")
        current.write_text("{}", encoding="utf-8")

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 2
        assert out == ""
        assert err.strip() != ""
        assert "Traceback" not in err


def test_simplified_format_drift_report_is_deterministic() -> None:
    """Detects drift in simplified snapshot format with deterministic ordering."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {
                        "instance_type": "t3.micro",
                        "ami": "ami-0abc1234",
                        "monitoring": True,
                    },
                },
                {
                    "type": "aws_s3_bucket",
                    "name": "logs",
                    "attributes": {"versioning": True, "encrypted": True},
                },
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {
                        "instance_type": "t3.small",
                        "ami": "ami-0abc1234",
                        "monitoring": False,
                    },
                },
                {
                    "type": "aws_s3_bucket",
                    "name": "logs",
                    "attributes": {"versioning": True, "encrypted": False},
                },
                {
                    "type": "aws_security_group",
                    "name": "debug",
                    "attributes": {"ingress_rules": 1},
                },
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        assert report["audit_timestamp"] == "STATIC"
        assert report["missing_resources"] == []
        assert report["extra_resources"] == ["aws_security_group.debug"]

        # drift_detected should match presence of any drift
        assert report["drift_detected"] is True

        drift = report["attribute_drift"]
        assert sorted(drift.keys()) == list(drift.keys())

        # Ensure per-resource entries are sorted by attribute
        for entries in drift.values():
            attrs = [e["attribute"] for e in entries]
            assert attrs == sorted(attrs)

        # Spot-check expected drifts
        web = drift["aws_instance.web"]
        assert {e["attribute"] for e in web} == {"instance_type", "monitoring"}

        logs = drift["aws_s3_bucket.logs"]
        assert {e["attribute"] for e in logs} == {"encrypted"}


def test_nested_attributes_are_flattened_and_lists_are_atomic() -> None:
    """Flattens nested dict attributes with dot paths; lists compare atomically."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {
                        "tags": {"Environment": "prod"},
                        "security_groups": ["sg-1", "sg-2"],
                    },
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {
                        "tags": {"Environment": "dev"},
                        "security_groups": ["sg-1"],
                    },
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)
        drift = report["attribute_drift"]["aws_instance.web"]
        assert {e["attribute"] for e in drift} == {"security_groups", "tags.Environment"}


def test_attributes_present_only_on_one_side_are_reported_as_null() -> None:
    """Reports expected/actual as null when attribute exists only in one snapshot."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_s3_bucket",
                    "name": "logs",
                    "attributes": {"encrypted": True},
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_s3_bucket",
                    "name": "logs",
                    "attributes": {"encrypted": True, "kms_key_id": "abc"},
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_s3_bucket.logs"]
        assert diffs == [
            {"attribute": "kms_key_id", "expected": None, "actual": "abc"}
        ]


def test_ignore_prefix_filters_attribute_drift_entries() -> None:
    """`--ignore PREFIX` removes drift entries whose attribute starts with PREFIX."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {"tags": {"Environment": "prod"}, "monitoring": True},
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {"tags": {"Environment": "dev"}, "monitoring": False},
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit(["--ignore", "tags", str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.web"]
        assert diffs == [{"attribute": "monitoring", "expected": True, "actual": False}]


def test_terraform_like_format_is_supported_and_child_modules_are_walked() -> None:
    """Supports Terraform-like `values.root_module` format and recurses child modules."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "type": "aws_instance",
                            "name": "web",
                            "values": {"instance_type": "t3.micro"},
                        }
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {
                                    "type": "aws_s3_bucket",
                                    "name": "logs",
                                    "values": {"versioning": True},
                                }
                            ]
                        }
                    ],
                }
            }
        }
        current_obj = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "type": "aws_instance",
                            "name": "web",
                            "values": {"instance_type": "t3.small"},
                        }
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {
                                    "type": "aws_s3_bucket",
                                    "name": "logs",
                                    "values": {"versioning": True},
                                }
                            ]
                        }
                    ],
                }
            }
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        assert report["missing_resources"] == []
        assert report["extra_resources"] == []

        diffs = report["attribute_drift"]["aws_instance.web"]
        assert diffs == [
            {"attribute": "instance_type", "expected": "t3.micro", "actual": "t3.small"}
        ]


def test_duplicate_resource_ids_are_parse_errors() -> None:
    """Duplicate normalized resource ids must be rejected as parse errors."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {"type": "aws_instance", "name": "web", "attributes": {}},
                {"type": "aws_instance", "name": "web", "attributes": {}},
            ]
        }
        current_obj = {"resources": []}

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 2
        assert out == ""
        assert err.strip() != ""
        assert "Traceback" not in err


def test_attribute_paths_escape_dots_in_keys() -> None:
    """Keys containing '.' must be escaped as '\\.' in dot-delimited attribute paths."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {"tags": {"Environment.Name": "prod"}},
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {"tags": {"Environment.Name": "dev"}},
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.web"]
        assert diffs == [
            {
                "attribute": "tags.Environment\\.Name",
                "expected": "prod",
                "actual": "dev",
            }
        ]


def test_ignore_prefix_matches_escaped_attribute_paths() -> None:
    """--ignore prefixes are matched against the rendered (escaped) attribute paths."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {"tags": {"Environment.Name": "prod"}},
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {"tags": {"Environment.Name": "dev"}},
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit(
            ["--ignore", "tags.Environment\\.Name", str(ideal), str(current)]
        )
        assert code == 0, err
        report = parse_report(out)

        assert report["attribute_drift"] == {}
        assert report["missing_resources"] == []
        assert report["extra_resources"] == []
        assert report["drift_detected"] is False


def test_deeply_nested_attributes_flattened_correctly() -> None:
    """Handles deeply nested attributes (3+ levels) with proper dot-path flattening."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {
                        "config": {
                            "network": {
                                "interfaces": {
                                    "eth0": {"ip": "10.0.0.1", "mask": "255.255.255.0"}
                                }
                            }
                        }
                    },
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {
                        "config": {
                            "network": {
                                "interfaces": {
                                    "eth0": {"ip": "10.0.0.2", "mask": "255.255.255.0"}
                                }
                            }
                        }
                    },
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.web"]
        assert diffs == [
            {"attribute": "config.network.interfaces.eth0.ip", "expected": "10.0.0.1", "actual": "10.0.0.2"}
        ]


def test_complex_lists_with_dicts_are_atomic() -> None:
    """Lists containing dicts are treated as atomic values, not recursively flattened."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_security_group",
                    "name": "sg",
                    "attributes": {
                        "rules": [
                            {"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0"},
                            {"port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0"}
                        ]
                    },
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_security_group",
                    "name": "sg",
                    "attributes": {
                        "rules": [
                            {"port": 80, "protocol": "tcp", "cidr": "10.0.0.0/8"},
                            {"port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0"}
                        ]
                    },
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_security_group.sg"]
        assert diffs == [
            {"attribute": "rules", "expected": ideal_obj["resources"][0]["attributes"]["rules"], "actual": current_obj["resources"][0]["attributes"]["rules"]}
        ]


def test_unicode_and_special_chars_in_keys() -> None:
    """Handles unicode characters and special chars in attribute keys with proper escaping."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {"tags": {"Env.Name": "prod", "café": "yes"}},
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {"tags": {"Env.Name": "dev", "café": "no"}},
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.web"]
        expected_diffs = [
            {"attribute": "tags.Env\\.Name", "expected": "prod", "actual": "dev"},
            {"attribute": "tags.café", "expected": "yes", "actual": "no"}
        ]
        assert diffs == expected_diffs


def test_multiple_child_modules_with_conflicts() -> None:
    """Handles multiple child modules with potential resource id conflicts."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "values": {
                "root_module": {
                    "resources": [
                        {"type": "aws_instance", "name": "root", "values": {"ami": "ami-1"}}
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {"type": "aws_instance", "name": "child1", "values": {"ami": "ami-2"}}
                            ]
                        },
                        {
                            "resources": [
                                {"type": "aws_instance", "name": "child2", "values": {"ami": "ami-3"}}
                            ]
                        }
                    ]
                }
            }
        }
        current_obj = {
            "values": {
                "root_module": {
                    "resources": [
                        {"type": "aws_instance", "name": "root", "values": {"ami": "ami-1"}}
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {"type": "aws_instance", "name": "child1", "values": {"ami": "ami-4"}}
                            ]
                        },
                        {
                            "resources": [
                                {"type": "aws_instance", "name": "child2", "values": {"ami": "ami-3"}}
                            ]
                        }
                    ]
                }
            }
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        assert report["missing_resources"] == []
        assert report["extra_resources"] == []

        diffs = report["attribute_drift"]
        assert "aws_instance.root" not in diffs
        assert "aws_instance.child2" not in diffs
        assert diffs["aws_instance.child1"] == [
            {"attribute": "ami", "expected": "ami-2", "actual": "ami-4"}
        ]


def test_ignore_with_partial_prefix_matches() -> None:
    """--ignore should match prefixes exactly, not partial strings."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {
                        "tags": {"Environment": "prod", "EnvName": "prod-env"},
                        "monitoring": True
                    },
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "attributes": {
                        "tags": {"Environment": "dev", "EnvName": "dev-env"},
                        "monitoring": False
                    },
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit(["--ignore", "tags.Env", str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.web"]
        # Should ignore tags.EnvName but not tags.Environment
        assert diffs == [
            {"attribute": "monitoring", "expected": True, "actual": False},
            {"attribute": "tags.Environment", "expected": "prod", "actual": "dev"}
        ]


def test_mixed_formats_in_same_snapshot() -> None:
    """Handles snapshots mixing simplified and terraform-like formats (edge case)."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        # Ideal: simplified format
        ideal_obj = {
            "resources": [
                {"type": "aws_instance", "name": "web", "attributes": {"ami": "ami-1"}}
            ]
        }
        # Current: terraform-like format
        current_obj = {
            "values": {
                "root_module": {
                    "resources": [
                        {"type": "aws_instance", "name": "web", "values": {"ami": "ami-2"}}
                    ]
                }
            }
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.web"]
        assert diffs == [
            {"attribute": "ami", "expected": "ami-1", "actual": "ami-2"}
        ]
