"""Verifier tests for Terraform Drift Audit.

Tests call `python /app/drift_audit.py` to match the runtime contract.
"""

import json
import subprocess
import tempfile
import copy
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


def test_very_deep_nesting() -> None:
    """Handles extremely deep nesting (10 levels) with proper flattening."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        # Build a deeply nested structure
        def build_nested(level: int) -> dict:
            if level == 0:
                return "value"
            return {"level": build_nested(level - 1)}
        
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "deep",
                    "attributes": {"config": build_nested(10)}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "deep",
                    "attributes": {"config": build_nested(10)}
                }
            ]
        }
        # Change the deepest value
        current_obj["resources"][0]["attributes"]["config"]["level"]["level"]["level"]["level"]["level"]["level"]["level"]["level"]["level"]["level"] = "changed"
        
        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.deep"]
        expected_path = ".".join(["config"] + ["level"] * 10)
        assert diffs == [
            {"attribute": expected_path, "expected": "value", "actual": "changed"}
        ]


def test_many_attributes() -> None:
    """Handles a large number of attributes (50) efficiently."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        attrs_ideal = {f"attr_{i}": f"value_{i}" for i in range(50)}
        attrs_current = attrs_ideal.copy()
        attrs_current["attr_25"] = "changed"
        
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "many",
                    "attributes": attrs_ideal
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "many",
                    "attributes": attrs_current
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.many"]
        assert diffs == [
            {"attribute": "attr_25", "expected": "value_25", "actual": "changed"}
        ]


def test_unicode_in_values() -> None:
    """Handles unicode characters in attribute values."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "unicode_val",
                    "attributes": {"description": "café au lait"}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "unicode_val",
                    "attributes": {"description": "café au thé"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.unicode_val"]
        assert diffs == [
            {"attribute": "description", "expected": "café au lait", "actual": "café au thé"}
        ]


def test_special_chars_in_keys() -> None:
    """Handles special characters in attribute keys, including escaping."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "special",
                    "attributes": {"key.with.dots": "value1", "key with spaces": "value2", "key-with-dashes": "value3"}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "special",
                    "attributes": {"key.with.dots": "changed1", "key with spaces": "changed2", "key-with-dashes": "value3"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.special"]
        assert diffs == [
            {"attribute": "key\\.with\\.dots", "expected": "value1", "actual": "changed1"},
            {"attribute": "key with spaces", "expected": "value2", "actual": "changed2"}
        ]


def test_child_modules_deep() -> None:
    """Handles deep child module hierarchies in Terraform-like format."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "values": {
                "root_module": {
                    "child_modules": [
                        {
                            "child_modules": [
                                {
                                    "resources": [
                                        {"type": "aws_instance", "name": "nested", "values": {"ami": "ami-1"}}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
        }
        current_obj = {
            "values": {
                "root_module": {
                    "child_modules": [
                        {
                            "child_modules": [
                                {
                                    "resources": [
                                        {"type": "aws_instance", "name": "nested", "values": {"ami": "ami-2"}}
                                    ]
                                }
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

        diffs = report["attribute_drift"]["aws_instance.nested"]
        assert diffs == [
            {"attribute": "ami", "expected": "ami-1", "actual": "ami-2"}
        ]


def test_ignore_partial_matches() -> None:
    """Ignores should match partial prefixes correctly."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "partial",
                    "attributes": {"tags.Environment": "prod", "tags.EnvName": "prod-env"}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "partial",
                    "attributes": {"tags.Environment": "dev", "tags.EnvName": "dev-env"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit(["--ignore", "tags.Env", str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.partial"]
        # Should ignore tags.EnvName but not tags.Environment
        assert diffs == [
            {"attribute": "tags.Environment", "expected": "prod", "actual": "dev"}
        ]


def test_escaped_dots_complex() -> None:
    """Complex escaping of dots in nested keys."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "escaped",
                    "attributes": {"a.b.c": {"d.e": "value1"}}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "escaped",
                    "attributes": {"a.b.c": {"d.e": "value2"}}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.escaped"]
        assert diffs == [
            {"attribute": "a\\.b\\.c.d\\.e", "expected": "value1", "actual": "value2"}
        ]


def test_lists_with_nested_dicts_atomic() -> None:
    """Lists containing dicts are treated as atomic, not flattened."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_security_group",
                    "name": "atomic",
                    "attributes": {
                        "rules": [
                            {"port": 80, "protocol": "tcp"},
                            {"port": 443, "protocol": "tcp"}
                        ]
                    }
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_security_group",
                    "name": "atomic",
                    "attributes": {
                        "rules": [
                            {"port": 80, "protocol": "tcp"},
                            {"port": 443, "protocol": "udp"}
                        ]
                    }
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_security_group.atomic"]
        # The whole list is compared as atomic
        assert diffs == [
            {"attribute": "rules", "expected": [{"port": 80, "protocol": "tcp"}, {"port": 443, "protocol": "tcp"}], "actual": [{"port": 80, "protocol": "tcp"}, {"port": 443, "protocol": "udp"}]}
        ]


def test_null_values() -> None:
    """Handles null values correctly."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "null",
                    "attributes": {"optional": None}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "null",
                    "attributes": {"optional": "present"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.null"]
        assert diffs == [
            {"attribute": "optional", "expected": None, "actual": "present"}
        ]


def test_empty_strings() -> None:
    """Handles empty strings as values."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "empty",
                    "attributes": {"description": ""}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "empty",
                    "attributes": {"description": "not empty"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.empty"]
        assert diffs == [
            {"attribute": "description", "expected": "", "actual": "not empty"}
        ]


def test_large_numbers() -> None:
    """Handles large integer values."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "large",
                    "attributes": {"big_num": 9223372036854775807}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "large",
                    "attributes": {"big_num": 9223372036854775806}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.large"]
        assert diffs == [
            {"attribute": "big_num", "expected": 9223372036854775807, "actual": 9223372036854775806}
        ]


def test_case_sensitivity() -> None:
    """Keys are case-sensitive."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "case",
                    "attributes": {"Key": "value1", "key": "value2"}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "case",
                    "attributes": {"Key": "changed1", "key": "value2"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.case"]
        assert diffs == [
            {"attribute": "Key", "expected": "value1", "actual": "changed1"}
        ]


def test_mixed_formats_with_child_modules() -> None:
    """Mixed formats with child modules in Terraform-like."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "values": {
                "root_module": {
                    "resources": [
                        {"type": "aws_vpc", "name": "main", "values": {"cidr": "10.0.0.0/16"}}
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {"type": "aws_instance", "name": "child", "values": {"ami": "ami-1"}}
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
                        {"type": "aws_vpc", "name": "main", "values": {"cidr": "10.0.0.0/16"}}
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {"type": "aws_instance", "name": "child", "values": {"ami": "ami-2"}}
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

        diffs = report["attribute_drift"]["aws_instance.child"]
        assert diffs == [
            {"attribute": "ami", "expected": "ami-1", "actual": "ami-2"}
        ]


def test_ignore_with_unicode() -> None:
    """Ignores work with unicode paths."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "unicode_ignore",
                    "attributes": {"café": "value1", "café.au_lait": "value2"}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "unicode_ignore",
                    "attributes": {"café": "changed1", "café.au_lait": "changed2"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit(["--ignore", "café", str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.unicode_ignore"]
        # Should ignore both café and café.au_lait since café is prefix
        assert diffs == []


def test_boolean_values() -> None:
    """Handles boolean values correctly."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "bool",
                    "attributes": {"enabled": True}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "bool",
                    "attributes": {"enabled": False}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.bool"]
        assert diffs == [
            {"attribute": "enabled", "expected": True, "actual": False}
        ]


def test_type_coercion_traps() -> None:
    """Handles type differences that look similar (string vs number, bool vs string)."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "type_trap",
                    "attributes": {"count": 123, "enabled": True}
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "type_trap",
                    "attributes": {"count": "123", "enabled": "true"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.type_trap"]
        assert diffs == [
            {"attribute": "count", "expected": 123, "actual": "123"},
            {"attribute": "enabled", "expected": True, "actual": "true"}
        ]


def test_extreme_nesting_50_levels() -> None:
    """Handles extremely deep nesting (50 levels) without stack overflow."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        def build_nested_50(level: int) -> dict:
            if level == 0:
                return "deep_value"
            return {"nested": build_nested_50(level - 1)}
        
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "extreme",
                    "attributes": {"config": build_nested_50(50)}
                }
            ]
        }
        current_obj = copy.deepcopy(ideal_obj)
        # Change the deepest value
        deep = current_obj["resources"][0]["attributes"]["config"]
        for _ in range(49):
            deep = deep["nested"]
        deep["nested"] = "changed_deep_value"

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.extreme"]
        expected_path = ".".join(["config"] + ["nested"] * 50)
        assert diffs == [
            {"attribute": expected_path, "expected": "deep_value", "actual": "changed_deep_value"}
        ]


def test_ignore_edge_cases() -> None:
    """Ignores with partial matches, escaped paths, and multiple prefixes."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "ignore_edge",
                    "attributes": {
                        "tags.Env": "prod",
                        "tags.Environment": "prod",
                        "config.network.ip": "10.0.0.1",
                        "config.network\\.ip": "10.0.0.2"
                    }
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "ignore_edge",
                    "attributes": {
                        "tags.Env": "dev",
                        "tags.Environment": "dev",
                        "config.network.ip": "10.0.0.3",
                        "config.network\\.ip": "10.0.0.4"
                    }
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit(["--ignore", "tags.Env", "--ignore", "config.network", str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.ignore_edge"]
        # Should ignore tags.Env* and config.network*, but not config.network\.ip
        assert diffs == [
            {"attribute": "config.network\\.ip", "expected": "10.0.0.2", "actual": "10.0.0.4"}
        ]


def test_unicode_bombs() -> None:
    """Handles rare unicode characters, zero-width spaces, and RTL text."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "unicode_bomb",
                    "attributes": {"key\u200B": "value1", "key\u200E": "value2", "key\u202E": "value3"}  # zero-width, LTR, RTL
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "unicode_bomb",
                    "attributes": {"key\u200B": "changed1", "key\u200E": "changed2", "key\u202E": "changed3"}
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.unicode_bomb"]
        assert len(diffs) == 3
        # Exact matching may vary, but ensure differences are detected


def test_large_inputs_1000_attributes() -> None:
    """Handles resources with 1000 attributes efficiently."""
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        attrs_ideal = {f"attr_{i}": f"value_{i}" for i in range(1000)}
        attrs_current = attrs_ideal.copy()
        attrs_current["attr_500"] = "changed"
        
        ideal_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "large",
                    "attributes": attrs_ideal
                }
            ]
        }
        current_obj = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "large",
                    "attributes": attrs_current
                }
            ]
        }

        ideal = write_json(tmpdir, "ideal.json", ideal_obj)
        current = write_json(tmpdir, "current.json", current_obj)

        code, out, err = run_audit([str(ideal), str(current)])
        assert code == 0, err
        report = parse_report(out)

        diffs = report["attribute_drift"]["aws_instance.large"]
        assert diffs == [
            {"attribute": "attr_500", "expected": "value_500", "actual": "changed"}
        ]
