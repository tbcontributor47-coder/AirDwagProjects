# Solution Review - Critical Issues Found

## Summary
The `solve.sh` solution is **INCOMPLETE** and will fail multiple tests. Several critical validation rules and bug fixes are missing.

## Missing Validations (Will Fail Tests)

### 1. Account Validation Rules Missing
The `validate_accounts` method (lines 164-182) only checks basic format (`^\d{8,20}$`). Missing:

- **Forbidden prefixes check**: Must reject accounts where `acct8[:4]` is `0000`, `0001`, `0010`, or `0100`
- **First 4 digits rule**: First 4 digits of `acct8` cannot consist solely of `0` and `1`
- **Last 4 digits rule**: Last 4 digits of `acct8` cannot contain the digit `0`
- **eftno validation**: Must be non-empty and alphanumeric (letters/digits only)
- **bank_code validation**: 
  - Must start with a digit (0-9)
  - Must contain only uppercase letters and digits (no lowercase, no punctuation)
  - Error must include `must start with a digit` when violated

**Tests that will fail:**
- `test_account_forbidden_prefixes`
- `test_account_first_four_only_zeros_and_ones`
- `test_account_last_four_cannot_have_zeros`
- `test_eftno_and_bank_code_alphanumeric_constraints`
- `test_bank_code_must_start_with_digit`
- `test_bank_code_no_lowercase_or_special_chars`

### 2. 0-Day Retention Bug Not Fixed
Line 243-244:
```python
if not is_dup:
    self.record_file(file_hash, filename, processed)
```

**Bug**: Should not insert into DB when `retention_days <= 0`

**Fix needed:**
```python
if not is_dup and self.retention_days > 0:
    self.record_file(file_hash, filename, processed)
```

**Tests that will fail:**
- `test_retention_days_ignored_bug` (specifically the DB count check)

### 3. records_processed Logic Incorrect
Line 218-219:
```python
# For parsing/validation we ignore empty lines anywhere in the file
data_lines = [ln for ln in lines if ln != ""]
```

**Bug**: Spec says to only drop trailing empty lines, not all empty lines

**Fix needed**: Only remove empty lines from the end, not from the middle

**Tests that may fail:**
- Tests that expect empty lines in the middle to be counted as records

### 4. Payee Name Whitespace Not Collapsed
Line 200:
```python
if payee_name.strip().lower() != db_name.strip().lower():
```

**Bug**: Spec requires collapsing internal whitespace to single space before comparison

**Fix needed**: Use regex or replace to collapse multiple whitespace to single space

**Tests that may fail:**
- `test_payee_name_mismatch` (if test cases use whitespace variations)

## Bugs That ARE Fixed ✅

1. ✅ Record length validation (strict check)
2. ✅ Duplicate detection uses hash-only (no filename in WHERE clause)
3. ✅ Retention days parameter honored (no hardcoding to 5)
4. ✅ Hash canonicalization (trailing whitespace stripped per line)
5. ✅ Clearing account exact match (no substring matching)
6. ✅ Error messages include line numbers

## Required Fixes

The solution needs significant additions to `validate_accounts` method and fixes to:
1. Add account validation rules (forbidden prefixes, first-4, last-4)
2. Add eftno and bank_code validation
3. Fix 0-day retention to skip DB inserts
4. Fix records_processed to only drop trailing empty lines
5. Fix payee name comparison to collapse whitespace

