#!/usr/bin/env bash
set -euo pipefail

# Fixer script (oracle-style): overwrite the buggy program in /app so verifier tests pass.
# Mirrors the established pattern used by `eft-file-validation`.

export LANG=C.UTF-8
export LC_ALL=C.UTF-8

cat > /app/main.cob <<'COBOL'
*> Correct implementation for the Transaction Summarizer contract (instruction.md).

       identification division.
       program-id. MAIN.

       environment division.
       input-output section.
       file-control.
           select infile assign to ws-in-path
               organization is line sequential.

       data division.
       file section.
       fd  infile.
       01  in-line              pic x(512).

       working-storage section.
       01  ws-in-path           pic x(256).
       01  ws-arg-num           pic 9(4) comp value 0.

       01  ws-line              pic x(512).
       01  ws-line-trim         pic x(512).

       01  ws-acc               pic x(64).
       01  ws-acc10             pic x(10).
       01  ws-date              pic x(64).
       01  ws-amt               pic x(64).
       01  ws-desc              pic x(256).

       01  ws-line-no           pic 9(9) value 0.
       01  ws-line-no-z         pic 9(9) value 0.
    01  ws-line-no-disp      pic z(9).

       01  ws-records           pic 9(9) value 0.
    01  ws-records-z         pic 9(9) value 0.
    01  ws-records-str       pic x(12).

       01  ws-errors            pic 9(9) value 0.
    01  ws-errors-z          pic 9(9) value 0.
    01  ws-errors-str        pic x(12).

       01  ws-total-cents       pic 9(12) value 0.
    01  ws-total-z           pic 9(12) value 0.
    01  ws-total-str         pic x(20).

       01  ws-numval            pic s9(9)v99 comp-3 value 0.
       01  ws-cents             pic s9(12) comp-3 value 0.

    01  ws-amt-trim          pic x(64).
       01  ws-amt-whole         pic x(64).
       01  ws-amt-dec           pic x(64).
    01  ws-amt-whole2        pic x(64).
    01  ws-amt-dec2          pic x(2).
    01  ws-dot-count         pic 9 value 0.
    01  ws-dec3              pic x(3).
     01  ws-whole-scan        pic x(64).
    01  ws-pipe-count        pic 9 value 0.
    01  ws-skip-validate     pic 9 value 0.
    01  ws-line-error-flag   pic 9 value 0.

       01  ws-year-x            pic x(4).
       01  ws-mon-x             pic x(2).
       01  ws-day-x             pic x(2).
       01  ws-year              pic 9(4) value 0.
       01  ws-mon               pic 9(2) value 0.
       01  ws-day               pic 9(2) value 0.
       01  ws-dim               pic 9(2) value 0.
    01  ws-is-leap           pic 9 value 0.

       01  rem4                pic 9 value 0.
       01  rem100              pic 99 value 0.
       01  rem400              pic 999 value 0.
       01  quot                pic 9(9) value 0.

       01  ws-err-count         pic 9(2) value 0.
       01  ws-err-max           pic 9(2) value 20.
       01  ws-err-msg           pic x(120).
       01  ws-err-table.
           05 ws-err-line occurs 20 times pic x(180).

       01  idx                  pic 9(2) value 0.

    01  ws-json              pic x(4000).
    01  ws-json-ptr          pic 9(4) comp value 1.

    *> Display fields for JSON output (fix for missing definitions)
    01  ws-records-disp      pic x(12) value spaces.
    01  ws-errors-disp       pic x(12) value spaces.
    01  ws-total-disp        pic x(12) value spaces.

     *> Edited display (suppresses leading zeros) for JSON numbers
     01  ws-records-edit      pic z(9) value spaces.
     01  ws-errors-edit       pic z(9) value spaces.
     01  ws-total-edit        pic z(12) value spaces.

       procedure division.
       main-para.
           accept ws-arg-num from argument-number
           if ws-arg-num < 1
               move 'missing input path' to ws-err-msg
               move 0 to ws-line-no
               perform add-error
               perform emit-json
               stop run returning 2
           end-if

           accept ws-in-path from argument-value
           open input infile

           perform until 1 = 2
               move spaces to ws-line
               move spaces to ws-line-trim
               read infile into ws-line
                   at end exit perform
               end-read

               add 1 to ws-line-no

               move ws-line to ws-line-trim
               inspect ws-line-trim replacing all low-values by space
               inspect ws-line-trim replacing all x'0D' by space
               inspect ws-line-trim replacing all x'0A' by space
               move function trim(ws-line-trim) to ws-line-trim
               inspect ws-line-trim replacing all low-values by space

               if ws-line-trim = spaces
                   *> blank line: ignored but still counts for line numbering
                   continue
               else
                   add 1 to ws-records
                   perform parse-line
                   perform validate-line
               end-if
           end-perform

           close infile
           perform emit-json
           if ws-errors > 0
               stop run returning 2
           end-if
           stop run returning 0
           .

       parse-line.
           move spaces to ws-acc ws-date ws-amt ws-desc
           move 0 to ws-line-error-flag
           move 0 to ws-skip-validate

           *> Count pipe separators to detect unexpected field counts
           move 0 to ws-pipe-count
           inspect ws-line-trim tallying ws-pipe-count for all '|'
           if ws-pipe-count > 3
               move 'unexpected field count' to ws-err-msg
               perform add-error
               move 1 to ws-skip-validate
               exit paragraph
           end-if

           unstring ws-line-trim delimited by '|'
               into ws-acc ws-date ws-amt ws-desc
           end-unstring

           *> Normalize CRLF inputs and trim each field
           inspect ws-acc replacing all x'0D' by space
           inspect ws-acc replacing all x'0A' by space
           inspect ws-acc replacing all low-values by space
           move function trim(ws-acc) to ws-acc

           inspect ws-date replacing all x'0D' by space
           inspect ws-date replacing all x'0A' by space
           inspect ws-date replacing all low-values by space
           move function trim(ws-date) to ws-date

           inspect ws-amt replacing all x'0D' by space
           inspect ws-amt replacing all x'0A' by space
           inspect ws-amt replacing all low-values by space
           move function trim(ws-amt) to ws-amt

           inspect ws-desc replacing all x'0D' by space
           inspect ws-desc replacing all x'0A' by space
           inspect ws-desc replacing all low-values by space
           move function trim(ws-desc) to ws-desc
           .

       validate-line.
           if ws-skip-validate = 1
               move 0 to ws-skip-validate
               exit paragraph
           end-if
           perform validate-account
           perform validate-date
           perform validate-amount
           .

       validate-account.
           move function trim(ws-acc) to ws-acc10
           if function length(function trim(ws-acc)) not = 10
               move 'ACCOUNT must be exactly 10 digits' to ws-err-msg
               perform add-error
           else
               if ws-acc10 is not numeric
                   move 'ACCOUNT must be exactly 10 digits' to ws-err-msg
                   perform add-error
               end-if
           end-if
           .

       validate-date.
           if function length(function trim(ws-date)) not = 10
               move 'DATE must be a valid calendar date' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           if ws-date(5:1) not = '-' or ws-date(8:1) not = '-'
               move 'DATE must be a valid calendar date' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           move ws-date(1:4) to ws-year-x
           move ws-date(6:2) to ws-mon-x
           move ws-date(9:2) to ws-day-x

           if ws-year-x is not numeric or ws-mon-x is not numeric or ws-day-x is not numeric
               move 'DATE must be a valid calendar date' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           move function numval(ws-year-x) to ws-year
           move function numval(ws-mon-x) to ws-mon
           move function numval(ws-day-x) to ws-day

           if ws-mon < 1 or ws-mon > 12
               move 'DATE must be a valid calendar date' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           perform compute-leap

           *> Determine leap-year correctly: leap if (divisible by 4 AND (not divisible by 100 OR divisible by 400))
           move 0 to ws-is-leap
           if rem4 = 0
               if rem100 = 0
                   if rem400 = 0
                       move 1 to ws-is-leap
                   end-if
               else
                   move 1 to ws-is-leap
               end-if
           end-if

           evaluate ws-mon
               when 1
                   if ws-day < 1 or ws-day > 31
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 3
                   if ws-day < 1 or ws-day > 31
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 5
                   if ws-day < 1 or ws-day > 31
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 7
                   if ws-day < 1 or ws-day > 31
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 8
                   if ws-day < 1 or ws-day > 31
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 10
                   if ws-day < 1 or ws-day > 31
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 12
                   if ws-day < 1 or ws-day > 31
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 4
                   if ws-day < 1 or ws-day > 30
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 6
                   if ws-day < 1 or ws-day > 30
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 9
                   if ws-day < 1 or ws-day > 30
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 11
                   if ws-day < 1 or ws-day > 30
                       move 'DATE must be a valid calendar date' to ws-err-msg
                       perform add-error
                       exit paragraph
                   end-if
               when 2
                   if ws-is-leap = 1
                       if ws-day < 1 or ws-day > 29
                           move 'DATE must be a valid calendar date' to ws-err-msg
                           perform add-error
                           exit paragraph
                       end-if
                   else
                       if ws-day < 1 or ws-day > 28
                           move 'DATE must be a valid calendar date' to ws-err-msg
                           perform add-error
                           exit paragraph
                       end-if
                   end-if
               when other
                   move 'DATE must be a valid calendar date' to ws-err-msg
                   perform add-error
                   exit paragraph
           end-evaluate
           .

       compute-leap.
           divide ws-year by 4 giving quot remainder rem4
           divide ws-year by 100 giving quot remainder rem100
           divide ws-year by 400 giving quot remainder rem400
           .

       validate-amount.
           move spaces to ws-amt-whole ws-amt-dec
           if function length(function trim(ws-amt)) = 0
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           move function trim(ws-amt) to ws-amt-trim
           inspect ws-amt-trim replacing all low-values by space
           inspect ws-amt-trim replacing all x'0D' by space
           inspect ws-amt-trim replacing all x'0A' by space
           move function trim(ws-amt-trim) to ws-amt-trim

           *> Require exactly one decimal point.
           move 0 to ws-dot-count
           inspect ws-amt-trim tallying ws-dot-count for all '.'
           if ws-dot-count not = 1
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           unstring ws-amt-trim delimited by '.'
               into ws-amt-whole ws-amt-dec
           end-unstring

           move function trim(ws-amt-whole) to ws-amt-whole2
           move function trim(ws-amt-dec) to ws-amt-dec2

           move spaces to ws-dec3
           move function trim(ws-amt-dec) to ws-dec3

           if function length(function trim(ws-amt-whole)) = 0
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           move ws-amt-whole2 to ws-whole-scan
           inspect ws-whole-scan replacing all '0' by space
           inspect ws-whole-scan replacing all '1' by space
           inspect ws-whole-scan replacing all '2' by space
           inspect ws-whole-scan replacing all '3' by space
           inspect ws-whole-scan replacing all '4' by space
           inspect ws-whole-scan replacing all '5' by space
           inspect ws-whole-scan replacing all '6' by space
           inspect ws-whole-scan replacing all '7' by space
           inspect ws-whole-scan replacing all '8' by space
           inspect ws-whole-scan replacing all '9' by space
           move function trim(ws-whole-scan) to ws-whole-scan
           if ws-whole-scan not = spaces
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           *> Exactly 2 decimal digits: after move into X(3), the 3rd char must be space.
           if ws-dec3(1:1) = space or ws-dec3(2:1) = space
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           if ws-dec3(1:2) is not numeric
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           if ws-dec3(3:1) not = space
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           if ws-amt-dec2 is not numeric
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           *> If any prior validation error occurred for this line, do not include amount in totals
           if ws-line-error-flag = 1
               exit paragraph
           end-if

           compute ws-numval = function numval(ws-amt-trim)
           if ws-numval <= 0
               move 'AMOUNT must be > 0' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           compute ws-cents = ws-numval * 100
           add ws-cents to ws-total-cents
           .

       add-error.
           add 1 to ws-errors
           move 1 to ws-line-error-flag
           if ws-err-count < ws-err-max
               add 1 to ws-err-count
               move ws-line-no to ws-line-no-z
               move ws-line-no-z to ws-line-no-disp
               move spaces to ws-err-line(ws-err-count)
               string 'Line ' delimited by size
                      function trim(ws-line-no-disp) delimited by size
                      ': ' delimited by size
                      function trim(ws-err-msg) delimited by size
                      into ws-err-line(ws-err-count)
               end-string
           end-if
           .

       emit-json.
            move ws-records to ws-records-z
            move ws-errors to ws-errors-z
            move ws-total-cents to ws-total-z

            *> Format numbers as ASCII digits with no leading zeros
            move ws-records-z to ws-records-edit
            move ws-errors-z to ws-errors-edit
            move ws-total-z to ws-total-edit

            move ws-records-edit to ws-records-disp
            move ws-errors-edit to ws-errors-disp
            move ws-total-edit to ws-total-disp

            *> Ensure zero values render as '0' (PIC Z yields spaces for zero)
            if ws-records-z = 0
                move '0' to ws-records-disp
            end-if
            if ws-errors-z = 0
                move '0' to ws-errors-disp
            end-if
            if ws-total-z = 0
                move '0' to ws-total-disp
            end-if

            move spaces to ws-json
            move 1 to ws-json-ptr

                 string '{"records_processed":' delimited by size
                     function trim(ws-records-disp) delimited by size
                     ',"n_errors":' delimited by size
                     function trim(ws-errors-disp) delimited by size
                     ',"total_cents":' delimited by size
                     function trim(ws-total-disp) delimited by size
                     ',"errors":[' delimited by size
                     into ws-json with pointer ws-json-ptr
                 end-string

           if ws-err-count > 0
               perform varying idx from 1 by 1 until idx > ws-err-count
                   if idx > 1
                       string ',' delimited by size
                           into ws-json with pointer ws-json-ptr
                       end-string
                   end-if
                   string '"' delimited by size
                          function trim(ws-err-line(idx)) delimited by size
                          '"' delimited by size
                          into ws-json with pointer ws-json-ptr
                   end-string
               end-perform
           end-if

           string ']}' delimited by size
               into ws-json with pointer ws-json-ptr
           end-string

           display function trim(ws-json)
           .
COBOL

# Ensure the runner remains executable (in case the base image changes)
chmod +x /app/run_cobol.sh || true

exit 0
