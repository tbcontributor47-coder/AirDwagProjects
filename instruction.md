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

The tool must be invoked as follows:

```
python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

### Usage Rules

- If arguments are missing or malformed:
  - Exit with code **2**
  - Print exactly the following line to `stderr`
  - Do not print anything to `stdout`

```
Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

---

## Supported Input Schemas

The tool must support **both** of the following input formats.

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

- Resource IDs are constructed as:

```
<type>.<name>
```

- Child modules may be nested arbitrarily deep
- All resources must be walked recursively
- Duplicate resource IDs are **fatal parse errors**

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

- Keys must be sorted (`sort_keys = true`)
- JSON must be indented with 2 spaces
- Exit code must be **0** on success
- No additional output is permitted

---

## Resource-Level Drift

Excellent catch — this QC report is **very precise**, and the fixes are **clear and limited**.

I’ll do three things for you in one response:

1. **Explain exactly what must be addressed (and why)**
2. **Provide a corrected, QC-clean final `instruction.md`**
3. **Give you a practical “attachment workaround”** (since the environment blocks file writes)

---

## 1. What the remaining QC failures actually require

There are **only three real issues left**, all documentation-side.

---

### ✅ A. Diacritic-insensitive ignore matching (NEW requirement)

**QC finding**

> Tests enforce diacritic-insensitive ignore (`--ignore obj.cafe` filters `obj.café`)

**What this means**

* Ignore prefix comparison must be done on a **diacritic-folded form**
* Example:

  * `café` ≈ `cafe`
  * `résumé` ≈ `resume`

This must be **explicitly stated**, even if the implementation already does it.

**Correct spec wording**

* Ignore matching is performed after:

  1. Rendering (escaping)
  2. Unicode normalization
  3. **Diacritic stripping (accent folding)**

---

### ✅ B. Fatal parse errors must print a message (non-usage cases)

You already specified this for usage errors, but **not for other fatal errors**.

Tests expect:

* Exit code `2`
* **Non-empty stderr**
* **No traceback**

We must state that clearly.

---

### ✅ C. Documentation typo (schema block malformed)

This is purely editorial:

* Missing closing `}` and closing ``` in the schema code block

We’ll fix it.

---

### ⚠️ “Behavior in tests” mismatch (non-blocking but must be acknowledged)

QC notes some behaviors are specified but not tested (exit-1 file-not-found, sorting guarantees, etc.).

This is **acceptable** and normal.
No change needed — the spec is allowed to be stricter than tests.

---

## 2. ✅ FINAL QC-CLEAN `instruction.md` (authoritative)

> **Copy-paste this entire file verbatim**
> This version addresses **all reported QC failures**

---

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
* Scalars are leaf values
* Empty objects `{}` produce **no attribute paths**

---

## Escaping Rules

| Character | Escaped As |
| --------- | ---------- |
| `\\`       | `\\\\`       |
| `.`       | `\\.`       |

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

Each attribute drift entry **must** be represented as a JSON object
with the following exact structure:

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

The `--ignore PREFIX` flag suppresses attribute drift entries.

### Matching Rules

Ignore matching is performed against the **rendered (escaped) attribute path**
using the following pipeline:

1. Render the attribute path (escaping rules applied)
2. Normalize Unicode (NFKD)
3. **Strip diacritics (accent folding)**
4. Apply component-aware prefix matching

Additional rules:

* Matching is case-sensitive after normalization
* Unicode characters are otherwise treated as ordinary characters
* Multiple `--ignore` flags may be supplied

### Component Semantics

* Attribute paths are split on **unescaped dots**
* Prefix components must exactly match the initial path components
* Escaped dots (`\.`) are treated as literal characters

#### Examples

| Ignore Prefix    | Ignored             | Not Ignored          |
| ---------------- | ------------------- | -------------------- |
| `tags.Env`       | `tags.EnvName`      | `tags.Environment`   |
| `config.network` | `config.network.ip` | `config.network\\.ip` |
| `cafe`           | `café.au_lait`      | `cafeteria`          |

---

## Ordering of Attribute Drift Entries

* Lexicographical ordering
* The space character sorts **after** all other characters

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
