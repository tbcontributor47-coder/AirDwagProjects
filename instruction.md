# Terraform Drift Audit – Correctness and Robustness Task

Your task is to **fix and complete the Terraform drift audit tool** located at:

```
/app/drift_audit.py
```

The current implementation is intentionally **buggy and incomplete**.
You must update it so that it behaves **exactly as specified** in this document.

The final implementation must be **general**, **deterministic**, and **robust to edge cases**.

---

## Goal of the Tool

The drift audit tool compares two infrastructure snapshots:

- **Ideal state** – the expected configuration
- **Current state** – the observed configuration

It produces a JSON report describing:

1. Resources that are missing
2. Resources that are extra
3. Attribute-level configuration drift

The tool must work across **multiple schema formats**, support **deeply nested attributes**, and provide **precise filtering controls**.

---

## Command-Line Interface

```
python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

### Usage Rules

If arguments are missing or malformed:

- Exit with code **2**
- Print **exactly** the following line to `stderr`
- Print nothing to `stdout`

```
Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

---

## Supported Input Schemas

The tool must support **both** input formats.

### 1. Simplified Snapshot Format

```json
{
  "resources": [
    {
      "type": "aws_instance",
      "name": "web",
      "attributes": {
        "instance_type": "t3.micro"
      }
    }
  ]
}
```

### 2. Terraform-Like Snapshot Format

```json
{
  "values": {
    "root_module": {
      "resources": [
        {
          "type": "aws_instance",
          "name": "web",
          "values": {
            "instance_type": "t3.micro"
          }
        }
      ],
      "child_modules": [
        {
          "resources": [
            {
              "type": "aws_s3_bucket",
              "name": "logs",
              "values": {
                "versioning": true
              }
            }
          ]
        }
      ]
    }
  }
}
```

### Normalization Rules

* Resource IDs are constructed as:

```
<type>.<name>
```

* Child modules may be nested arbitrarily deep
* All resources must be walked recursively
* Duplicate resource IDs are **fatal parse errors**

---

## Output Format

The tool must write **only JSON** to `stdout`:

```json
{
  "audit_timestamp": "STATIC",
  "drift_detected": true,
  "missing_resources": [],
  "extra_resources": [],
  "attribute_drift": {}
}
```

### Output Requirements

* Keys must be sorted (`sort_keys = true`)
* JSON must be indented with 2 spaces
* Exit code must be **0** on success
* No additional output is permitted

---

## Resource-Level Drift

### Missing Resources

A resource is missing if it exists in the ideal snapshot but not in the current snapshot.

### Extra Resources

A resource is extra if it exists in the current snapshot but not in the ideal snapshot.

### Ordering

Both lists must be sorted lexicographically.

---

## Attribute Drift Detection

### Attribute Flattening

* Dictionaries recurse
* Lists are **atomic**
* Scalars (string, number, boolean, null) are leaf values
* Empty objects `{}` produce **no attribute paths**

---

## Escaping Rules

| Character | Escaped As |
| --------- | ---------- |
| \         | \\         |
| .         | \.         |

* Backslashes must be escaped **before** dots
* Unicode characters must be preserved
* Escaping applies only to keys, not values

---

## Attribute Comparison Rules

* Comparisons use **strict equality**
* No type coercion is allowed

### Missing Attributes

* Only in ideal → `actual = null`
* Only in current → `expected = null`

---

## Attribute Drift Entry Schema

Each attribute drift entry **must** be represented as a JSON object with the following exact structure:

```json
{
  "attribute": "<string>",
  "expected": <any JSON value or null>,
  "actual": <any JSON value or null>
}
```

All three fields are **required**.

---

## Ignore Filtering (`--ignore`)

The `--ignore PREFIX` flag suppresses attribute drift entries whose paths match the given prefix.

Ignore matching is performed against the **rendered (escaped) attribute path**. Matching is case-sensitive and uses exact string comparison (no Unicode normalization). Multiple `--ignore` flags may be supplied.

### Matching Behavior

Paths and prefixes are split into components on **unescaped dots**. Escaped dots (`\.`) are treated as literal characters within component names and do not split components.

**Single-component matching:** When both path and prefix have a single component, they are compared after unescaping (converting `\.` to `.` and `\\` to `\`). A path matches if it equals the prefix or starts with the prefix as a substring.

**Multi-component matching:** This applies when the path has multiple components. The path must have at least as many components as the prefix.

- If the prefix has multiple components: all leading components of the prefix (all except the last) must match the corresponding leading components of the path exactly.
- The component at position `len(prefix_components) - 1` of the path is compared with the last component of the prefix. Both are compared as strings (components are used as-extracted from the split operation, not unescaped). The path matches if:
  - These components are equal, or
  - The path's component starts with the prefix's component as a substring, and the remainder (the substring of the path's component that follows the prefix's component) is non-empty and its first character is an uppercase letter (A-Z) or digit (0-9)

For example, with prefix `tags.Env` (2 components) and path `tags.EnvName` (2 components): the first component `tags` matches exactly. The final components are `Env` and `EnvName`. Since `EnvName` starts with `Env` and the remainder `Name` begins with uppercase `N`, it matches. However, with path `tags.Environment`: the remainder is `ironment`, which begins with lowercase `i`, so it does not match.

#### Examples

| Ignore Prefix    | Ignored             | Not Ignored          | Notes                                                                 |
| ---------------- | ------------------- | -------------------- | --------------------------------------------------------------------- |
| `tags.Env`       | `tags.EnvName`      | `tags.Environment`   | `EnvName` remainder "Name" starts with uppercase; `Environment` remainder "ironment" starts with lowercase |
| `config.network` | `config.network.ip` | `config.network\.ip` | Escaped dot keeps `network\.ip` as single component, so it doesn't match `network` |
| `café`           | `café`, `café.au_lait` | -                   | Single-component prefix matches exactly or as substring; multi-component path matches when first component equals prefix |

---

## Ordering of Attribute Drift Entries

* Lexicographical ordering
* The space character (`" "`) sorts **after** all other characters

---

## Error Handling

### Exit Code 2 (Fatal Errors)

* Invalid JSON
* Unsupported schema
* Duplicate resource IDs
* Invalid CLI usage

For all fatal errors:

* Exit with code **2**
* Write a **non-empty, human-readable message** to `stderr`
* Do **not** emit a traceback
* Do **not** write to `stdout`

### Exit Code 1 (File Errors)

* Input file not found

---

## Performance Expectations

The implementation must handle:

* Thousands of attributes
* Extremely deep nesting (50+ levels)
* Unicode and special-character-heavy keys

The solution must be **general**, not hardcoded.

---

## Files

* Input: `/app/drift_audit.py`
* Output: `/app/drift_audit.py` (modified in place)

No other files may be created or modified.

---

## Completion Criteria

The task is complete **only if all verifier checks pass**.

The verifier behavior is authoritative.