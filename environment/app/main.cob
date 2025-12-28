*> Buggy baseline implementation (intentionally wrong in multiple ways).
*>
*> This is designed to compile and run, but produce incorrect results.
*> Intentional bugs include:
*> - Counts blank lines as records_processed
*> - Treats month/day 00 as valid
*> - Accepts AMOUNT with wrong decimal precision
*> - Converts dollars to cents using x10 (should be x100)
*> - Emits total_cents as a JSON string (should be integer)

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
       01  ws-acc               pic x(64).
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

       01  ws-err-count         pic 9(2) value 0.
       01  ws-err-max           pic 9(2) value 20.
       01  ws-err-msg           pic x(120).
       01  ws-err-table.
           05 ws-err-line occurs 20 times pic x(180).

       01  ws-mm                pic 9(2) value 0.
       01  ws-dd                pic 9(2) value 0.
       01  idx                  pic 9(2) value 0.

       01  ws-json              pic x(4000).
       01  ws-json-ptr          pic 9(4) comp value 1.

       procedure division.
       main-para.
           accept ws-arg-num from argument-number
           if ws-arg-num < 1
               add 1 to ws-errors
               move 1 to ws-err-count
               move 'Line 0: missing input path' to ws-err-line(1)
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

               *> BUG: counts blank lines as records
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
           if function length(function trim(ws-acc)) not = 10
               move 'ACCOUNT must be exactly 10 digits' to ws-err-msg
               perform add-error
           end-if

           if function length(function trim(ws-date)) not = 10
               move 'DATE must be a valid calendar date' to ws-err-msg
               perform add-error
           else
               move ws-date(6:2) to ws-mm
               move ws-date(9:2) to ws-dd

               *> BUG: allows 00 month/day
               if ws-mm > 12
                   move 'DATE must be a valid calendar date' to ws-err-msg
                   perform add-error
               end-if
               if ws-dd > 31
                   move 'DATE must be a valid calendar date' to ws-err-msg
                   perform add-error
               end-if
           end-if

           *> BUG: does not enforce exactly 2 decimals
           if function length(function trim(ws-amt)) = 0
               move 'AMOUNT must have exactly 2 decimals' to ws-err-msg
               perform add-error
           else
               compute ws-numval = function numval(function trim(ws-amt))
               if ws-numval <= 0
                   move 'AMOUNT must be > 0' to ws-err-msg
                   perform add-error
               else
                   *> BUG: dollars->cents multiplier is x10 (should be x100)
                   compute ws-cents = ws-numval * 10
                   add ws-cents to ws-total-cents
               end-if
           end-if
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

           *> BUG: total_cents is a JSON string
           string '{"records_processed":' delimited by size
                  function trim(ws-records-z) delimited by size
                  ',"n_errors":' delimited by size
                  function trim(ws-errors-z) delimited by size
                  ',"total_cents":"' delimited by size
                  function trim(ws-total-z) delimited by size
                  '","errors":[' delimited by size
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
