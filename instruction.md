You are given a JSON semantic comparison CLI at `/app/compare_json.py` that is currently buggy.

Goal
----
Fix `/app/compare_json.py` so it implements the exact runtime contract required by the verifier tests. The tests exercise a small but precise set of semantics — your implementation must follow them exactly.

High-level contract (what the tests expect)
----------------------------------------
- CLI invocation (must be accepted exactly as shown by the tests):

```
python3 /app/compare_json.py --expected <expected.json> --actual <actual.json> [--tolerance <float>] [--ignore <json-pointer>]...
```

- Output and exit codes:
  - When the two JSON values are considered equal: print exactly `EQUAL\n` to stdout and exit code `0`.
  - When they differ: print the following four lines to stdout and exit code `2`:

```
NOT_EQUAL
FIRST_DIFF <json-pointer>
EXPECTED <json>
ACTUAL <json>
```

	- `<json-pointer>` is the JSON Pointer (RFC 6901) identifying the first differing location; use `/` for the document root.
	- `<json>` is a single-line JSON serialization of the value at that pointer (use `json.dumps` with `ensure_ascii=False`, stable key ordering, and compact separators).

Notes:
- The tests call the program with `python3` and the app path `/app/compare_json.py`.
- Do not change the CLI flags or their names.
- The verifier checks exact output lines and prefixes, so spacing/newlines must match exactly.

Detailed semantic rules (implementation checklist)
-----------------------------------------------

Implement the comparison as a deterministic, depth-first traversal that reports the *first* semantic difference. Follow these steps precisely.

1) Argument parsing
   - Required: `--expected <path>` and `--actual <path>`.
   - Optional: `--tolerance <float>` default `0.0`.
   - Optional: `--ignore <json-pointer>`; may be repeated; collect into a list.
   - If argument parsing fails (missing required args, wrong types), print a concise usage message to stderr and exit non-zero; tests always call with valid args so this is not exercised.

2) Read and decode JSON files
   - Open both files as UTF-8 and parse with `json.load`.
   - On any I/O or JSON decode error, print an error to stderr and exit non-zero (tests don't expect specific stderr text).

3) Ignore set semantics
   - Each `--ignore` value is a JSON Pointer string (e.g. `/meta/generated_at`).
   - When comparing, treat an ignored pointer as: skip any difference that occurs at that pointer or inside the subtree rooted at that pointer.
   - Implementation rule: when you are about to report a difference at pointer `p`, first canonicalize `p` and all ignore pointers; if `p` is equal to one of the ignore pointers, or `p` is a descendant of an ignore pointer (i.e., it begins with `<ignore> + '/'`), then treat this difference as non-existent and continue searching for the next difference.

Note: `--ignore` accepts exact JSON Pointer strings and descendant matching only. Wildcard patterns (e.g. `/items/*/time`) are not required by the verifier; if you need to ignore multiple sibling elements, pass multiple `--ignore` arguments (one per pointer).

4) String normalization
   - For string values, ignore *trailing* whitespace when comparing. Concretely, compare `expected.rstrip()` to `actual.rstrip()`. Internal whitespace (spaces within the string) must be preserved and compared exactly.

5) Numeric tolerance
   - If both values are numbers (int or float), treat them as numerically comparable. If `abs(expected - actual) <= tolerance` then consider them equal; otherwise they differ.
   - Default `tolerance` is `0.0` (exact equality).

6) Object comparison
   - Compare object member names exactly.
   - For each key present in `expected`, in lexicographic order of keys, check:
	 - If the key is missing in `actual`, report FIRST_DIFF at that child pointer with `EXPECTED` the expected value and `ACTUAL` `null`.
	 - Else recursively compare the values for that key.
   - After checking expected keys, check for extra keys present in `actual` but not in `expected`. If any exist, report FIRST_DIFF at the (first in lexicographic order) extra key pointer, with `EXPECTED` `null` and `ACTUAL` the actual value.

7) Array comparison
   - Default: arrays are order-sensitive. Compare elements index-by-index; the first index where elements differ is the FIRST_DIFF pointer (e.g. `/values/0`). If lengths differ but shorter array matches the prefix of the longer, report FIRST_DIFF at the index equal to the length of the shorter array.

   - Special-case: when the *property name* for the array is exactly `items`, treat that array as a multiset (order-insensitive but multiplicity-sensitive). In this case:
	 - Compare the two arrays as multisets of semantic elements (elements compared using the same semantic rules described here).
	 - If the multisets differ (different element counts for at least one canonical element), report FIRST_DIFF at the array pointer itself (e.g. `/items`) with `EXPECTED` set to the expected array and `ACTUAL` set to the actual array.
	 - If the multisets are equal, arrays are considered equal regardless of element order.

   - Note: if the array is not under an object key (i.e., the root value is an array), the property-name special-case does not apply; the root array uses the default order-sensitive behavior.

8) Null vs missing
   - A missing object member and a `null` value are different: if `expected` has a key with value `null` and `actual` lacks that key, report a difference at the child pointer.

9) First-difference selection and JSON Pointer formatting
   - Traverse objects by expected-key lexicographic order and arrays by increasing index.
   - The first semantic mismatch you encounter (after applying ignores) is the one to report.
   - Use JSON Pointer syntax for pointers:
	 - The document root is `/`.
	 - For object member `foo` under root pointer `p`, child pointer is `p + '/' + escape('foo')` where escape replaces `~` with `~0` and `/` with `~1` per RFC6901.
	 - For array element at index `i`, child pointer is `p + '/' + str(i)`.

10) Output formatting of EXPECTED/ACTUAL
	- When reporting a difference, print `EXPECTED ` followed by a single-line JSON serialization of the expected value at the pointer, then a newline.
	- Print `ACTUAL ` followed by a single-line JSON serialization of the actual value at the pointer, then a newline.
	- Use `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))` for a stable, compact representation.

11) Exit codes
	- `0` when equal
	- `2` when not equal
	- Other non-zero codes may be used for I/O/usage errors (tests do not assert on those)

Pseudocode sketch (recursive comparator)
---------------------------------------

```
def compare(expected, actual, pointer):
	# ignore check before reporting differences
	if pointer_is_ignored(pointer):
		return None

	# type-sensitive handling
	if both are strings:
		if expected.rstrip() != actual.rstrip():
			return pointer, expected, actual
		return None

	if both are numbers:
		if abs(expected - actual) <= tolerance:
			return None
		return pointer, expected, actual

	if types differ:
		return pointer, expected, actual

	if both are dicts:
		for key in sorted(expected.keys()):
			if key not in actual:
				return child_ptr(key), expected[key], None
			d = compare(expected[key], actual[key], child_ptr(key))
			if d is not None:
				return d
		for key in sorted(actual.keys()):
			if key not in expected:
				return child_ptr(key), None, actual[key]
		return None

	if both are lists:
		if parent_key == 'items':
			# multiset compare using canonical element forms
			if multisets_differ(expected, actual):
				return pointer, expected, actual
			return None
		else:
			n = min(len(expected), len(actual))
			for i in range(n):
				d = compare(expected[i], actual[i], child_ptr_index(i))
				if d is not None:
					return d
			if len(expected) != len(actual):
				# first index where one array ends
				return pointer + '/' + str(n), (expected[n] if n < len(expected) else None), (actual[n] if n < len(actual) else None)
			return None

	# scalars (bool, None, strings already handled)
	if expected != actual:
		return pointer, expected, actual
	return None
```

Important implementation notes and examples
-------------------------------------------

- Trailing whitespace in strings is ignored: `"a \n"` equals `"a\n"`.
- Internal whitespace is significant: `"a b"` != `"a  b"`.
- Numeric tolerance: `--tolerance 0.001` makes `1.0` equal `1.0009` but not `1.0011`.
- Array default: `[1,2]` != `[2,1]` (FIRST_DIFF at `/values/0`).
- `items` arrays: `[ {"id":1}, {"id":2} ]` equals `[ {"id":2}, {"id":1} ]`.
- Multiset counts matter: `[1,1,2]` != `[1,2,2]` (FIRST_DIFF `/items`).
- Ignore pointer `/meta/generated_at` ignores changes under that subtree but does not mask other mismatches (see tests).

Formatting and stability
------------------------
- Use stable key ordering when serializing `EXPECTED` and `ACTUAL` to produce deterministic single-line JSON.
- Ensure you print exactly the lines described above (no extra whitespace, no extra lines).

Tests and local verification
----------------------------
- Run the task tests locally with:

```
bash /tests/test.sh
```

If all tests pass, your implementation matches the required contract.

Good luck — implement the comparator exactly as specified and avoid guessing behavior not covered above.

## Verifier tests (required coverage)

The verifier uses `pytest` and executes `/app/compare_json.py` as a subprocess. It asserts exact stdout lines and specific exit codes for equal vs not-equal.

### Complete test list (all tests must pass)

- `test_equal_simple` — Equal objects print `EQUAL` and exit `0`.
- `test_extra_key_fails` — Extra keys in actual are reported as the first diff.
- `test_missing_key_fails` — Missing keys in actual are reported as the first diff.
- `test_null_not_missing` — Missing and `null` are different.

- `test_trailing_whitespace_ignored` — Trailing whitespace in strings is ignored.
- `test_internal_whitespace_not_ignored` — Internal whitespace differences are not ignored.
- `test_unicode_and_whitespace_handling` — Unicode is preserved; trailing whitespace still ignored.

- `test_number_tolerance_equal` — Numeric values can be equal within `--tolerance`.
- `test_number_tolerance_not_equal` — Numeric values differ when outside tolerance.

- `test_array_order_sensitive_by_default` — Arrays are order-sensitive unless the special case applies.
- `test_items_array_order_insensitive` — Arrays under key `items` are order-insensitive.
- `test_items_multiset_duplicates` — `items` arrays compare as multisets (multiplicity matters).

- `test_ignore_pointer_nested_subtree` — `--ignore` skips differences at/under a JSON Pointer but does not mask other mismatches.
- `test_ignore_pointer_in_array` — Array-element pointer ignores work when specified explicitly.

- `test_type_mismatch_fails` — Type mismatches report the correct pointer.
- `test_boolean_vs_string_fails` — Boolean vs string mismatch reports the correct pointer.
- `test_large_integer_equality` — Large integers compare exactly.
