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

       01  ws-records           pic 9(9) value 0.
       01  ws-records-z         pic 9(9) value 0.

       01  ws-errors            pic 9(9) value 0.
       01  ws-errors-z          pic 9(9) value 0.

       01  ws-total-cents       pic 9(12) value 0.
       01  ws-total-z           pic 9(12) value 0.

       01  ws-numval            pic s9(9)v99 comp-3 value 0.
       01  ws-cents             pic s9(12) comp-3 value 0.

    01  ws-amt-trim          pic x(64).
       01  ws-amt-whole         pic x(64).
       01  ws-amt-dec           pic x(64).
    01  ws-amt-whole2        pic x(64).
    01  ws-amt-dec2          pic x(2).

       01  ws-year-x            pic x(4).
       01  ws-mon-x             pic x(2).
       01  ws-day-x             pic x(2).
       01  ws-year              pic 9(4) value 0.
       01  ws-mon               pic 9(2) value 0.
       01  ws-day               pic 9(2) value 0.
       01  ws-dim               pic 9(2) value 0.

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
               read infile into ws-line
                   at end exit perform
               end-read

               add 1 to ws-line-no
               move function trim(ws-line) to ws-line-trim
               if function length(ws-line-trim) = 0
                   *> blank line: ignored but still counts for line numbering
                   continue
               end-if

               add 1 to ws-records
               perform parse-line
               perform validate-line
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
           unstring ws-line delimited by '|'
               into ws-acc ws-date ws-amt ws-desc
           end-unstring
           .

       validate-line.
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

           compute ws-year = function numval(ws-year-x)
           compute ws-mon  = function numval(ws-mon-x)
           compute ws-day  = function numval(ws-day-x)

           if ws-mon < 1 or ws-mon > 12
               move 'DATE must be a valid calendar date' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           if ws-day < 1
               move 'DATE must be a valid calendar date' to ws-err-msg
               perform add-error
               exit paragraph
           end-if

           perform compute-days-in-month
           if ws-day > ws-dim
               move 'DATE must be a valid calendar date' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           .

       compute-days-in-month.
           move 31 to ws-dim
           evaluate ws-mon
               when 4
               when 6
               when 9
               when 11
                   move 30 to ws-dim
               when 2
                   perform compute-leap
                   if rem4 = 0
                       if rem100 not = 0
                           move 29 to ws-dim
                       else
                           if rem400 = 0
                               move 29 to ws-dim
                           else
                               move 28 to ws-dim
                           end-if
                       end-if
                   else
                       move 28 to ws-dim
                   end-if
               when other
                   continue
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

           unstring ws-amt-trim delimited by '.'
               into ws-amt-whole ws-amt-dec
           end-unstring

           move function trim(ws-amt-whole) to ws-amt-whole2
           move function trim(ws-amt-dec) to ws-amt-dec2

           if function length(function trim(ws-amt-whole)) = 0
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           if ws-amt-whole2 is not numeric
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           if function length(function trim(ws-amt-dec)) not = 2
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
               exit paragraph
           end-if
           if ws-amt-dec2 is not numeric
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
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
           if ws-err-count < ws-err-max
               add 1 to ws-err-count
               move ws-line-no to ws-line-no-z
               move spaces to ws-err-line(ws-err-count)
               string 'Line ' delimited by size
                      function trim(ws-line-no-z) delimited by size
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

           move spaces to ws-json
           move 1 to ws-json-ptr

            string '{"records_processed":' delimited by size
                function numval-c(ws-records-z) delimited by size
                ',"n_errors":' delimited by size
                function numval-c(ws-errors-z) delimited by size
                ',"total_cents":' delimited by size
                function numval-c(ws-total-z) delimited by size
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
