# Fix JSON Semantic Comparison Tool

You are given a JSON semantic comparison CLI at `/app/compare_json.py` that is currently buggy. The verifier tests expect specific behavior that the current implementation does not match.

## Your Task

Fix `/app/compare_json.py` to correctly compare two JSON files according to the semantic rules described below. The implementation must match the exact behavior expected by the verifier tests.

## CLI Usage

The program accepts the following command-line arguments:

```
python3 /app/compare_json.py --expected <expected.json> --actual <actual.json> [--tolerance <float>] [--ignore <json-pointer>]...
```

- `--expected`: Path to the expected JSON file (required)
- `--actual`: Path to the actual JSON file (required)
- `--tolerance`: Numeric comparison tolerance (optional, default: 0.0)
- `--ignore`: JSON Pointer to ignore during comparison (optional, may be repeated)

## Expected Output and Exit Codes

- **Equal JSONs**: Print exactly `EQUAL\n` to stdout and exit with code `0`
- **Different JSONs**: Print the following four lines to stdout and exit with code `2`:
  ```
  NOT_EQUAL
  FIRST_DIFF <json-pointer>
  EXPECTED <json>
  ACTUAL <json>
  ```
  - `<json-pointer>` is a JSON Pointer (RFC 6901) identifying the first differing location; use `/` for the document root
  - `<json>` is a single-line JSON serialization using `json.dumps` with `ensure_ascii=False`, `sort_keys=True`, and `separators=(',', ':')`

## Requirements

### JSON Pointer Format

Use RFC 6901 JSON Pointer syntax:
- Document root is `/`
- Object keys: escape `~` as `~0` and `/` as `~1`
- Array indices: use numeric indices (e.g., `/items/0`)

### Comparison Semantics

1. **String Comparison**: Trailing whitespace is ignored (compare `expected.rstrip()` to `actual.rstrip()`). Internal whitespace differences are significant.

2. **Numeric Comparison**: Numbers (int or float) are compared with tolerance. If `abs(expected - actual) <= tolerance`, they are considered equal.

3. **Object Comparison**: 
   - Compare keys in lexicographic order
   - Missing keys in `actual` are reported as differences (EXPECTED has value, ACTUAL is `null`)
   - Extra keys in `actual` are reported as differences (EXPECTED is `null`, ACTUAL has value)
   - Missing keys and `null` values are different

4. **Array Comparison**:
   - Default behavior: Arrays are order-sensitive. Compare element-by-element at each index.
   - Special case: Arrays under the key `items` are treated as multisets (order-insensitive, but multiplicity matters). Compare the two arrays as multisets, applying ignore filters and canonicalization to each element before counting.

5. **Ignore Semantics**: When `--ignore <pointer>` is specified, skip any difference at that pointer or in any descendant of that pointer. A pointer `p` is a descendant of ignore pointer `i` if `p` starts with `i + '/'`.

6. **First Difference**: Traverse objects in lexicographic key order and arrays by index. Report the first semantic difference encountered (after applying ignore filters).

7. **Type Mismatches**: Type mismatches (e.g., string vs number, boolean vs string) are reported as differences at the current pointer.

## Constraints

- Only modify `/app/compare_json.py`
- Do not change the CLI argument names or structure
- Output format must match exactly (line breaks, spacing, JSON serialization)
- The verifier checks exact output, so precision matters

## Intentional Bugs

The current implementation has the following bugs:

1. **Ignore pointer logic incomplete**: The ignore check only matches exact pointer strings, but it should also match any pointer that is a descendant of an ignored path (i.e., starts with the ignore path followed by `/`).

2. **JSON Pointer escaping missing**: Object keys in JSON Pointers must escape `~` as `~0` and `/` as `~1` per RFC 6901. The current implementation does not perform this escaping.

3. **String whitespace normalization incorrect**: The implementation strips all whitespace from strings, but it should only ignore trailing whitespace. Internal whitespace differences should be preserved and compared exactly.

4. **Array special case not implemented**: Arrays under the key `items` should be compared as multisets (order-insensitive but multiplicity-sensitive). The current implementation treats all arrays as order-sensitive.

5. **Numeric tolerance comparison incorrect**: The tolerance comparison uses `<` instead of `<=`, causing values at the exact tolerance boundary to be incorrectly reported as different.

## Hints

- The ignore pointer logic is in the `_is_ignored` function
- JSON Pointer construction happens in the `_first_diff` function when building child pointers
- String comparison logic is in the string handling section of `_first_diff`
- Array comparison logic is in the list handling section of `_first_diff`
- Numeric tolerance comparison is in the number handling section of `_first_diff`

## Verifier Tests

The verifier uses `pytest` and executes `/app/compare_json.py` as a subprocess. It asserts exact stdout lines and specific exit codes.

### Complete test list (all tests must pass)

- `test_equal_simple` — Equal objects print `EQUAL` and exit `0`
- `test_extra_key_fails` — Extra keys in actual are reported as the first diff
- `test_missing_key_fails` — Missing keys in actual are reported as the first diff
- `test_null_not_missing` — Missing and `null` are different
- `test_trailing_whitespace_ignored` — Trailing whitespace in strings is ignored
- `test_internal_whitespace_not_ignored` — Internal whitespace differences are not ignored
- `test_unicode_and_whitespace_handling` — Unicode is preserved; trailing whitespace still ignored
- `test_number_tolerance_equal` — Numeric values can be equal within `--tolerance`
- `test_number_tolerance_not_equal` — Numeric values differ when outside tolerance
- `test_array_order_sensitive_by_default` — Arrays are order-sensitive unless the special case applies
- `test_items_array_order_insensitive` — Arrays under key `items` are order-insensitive
- `test_items_multiset_duplicates` — `items` arrays compare as multisets (multiplicity matters)
- `test_ignore_pointer_nested_subtree` — `--ignore` skips differences at/under a JSON Pointer but does not mask other mismatches
- `test_ignore_pointer_in_array` — Array-element pointer ignores work when specified explicitly
- `test_type_mismatch_fails` — Type mismatches report the correct pointer
- `test_boolean_vs_string_fails` — Boolean vs string mismatch reports the correct pointer
- `test_large_integer_equality` — Large integers compare exactly

## Testing Locally

Run the task tests locally with:

```bash
bash /tests/test.sh
```

If all tests pass, your implementation matches the required contract.
