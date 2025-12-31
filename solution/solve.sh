#!/bin/bash
set -eu

cat <<EOF > merge.cbl
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MERGE-FILES.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SALARY-FILE ASSIGN TO "data/salary.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT COMM-FILE ASSIGN TO "data/comm.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT BONUS-FILE ASSIGN TO "data/bonus.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT REPORT-FILE ASSIGN TO "report.txt"
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD SALARY-FILE.
       01 SALARY-REC.
           05 SAL-ID          PIC 9(5).
           05 SAL-AMOUNT      PIC 9(6)V99.

       FD COMM-FILE.
       01 COMM-REC.
           05 COMM-ID         PIC 9(5).
           05 COMM-AMOUNT     PIC 9(6)V99.

       FD BONUS-FILE.
       01 BONUS-REC.
           05 BONUS-ID        PIC 9(5).
           05 BONUS-AMOUNT    PIC 9(6)V99.

       FD REPORT-FILE.
       01 REPORT-REC          PIC X(80).

       WORKING-STORAGE SECTION.
       01 WS-EOF-SAL          PIC X VALUE 'N'.
       01 WS-EOF-COMM         PIC X VALUE 'N'.
       01 WS-EOF-BONUS        PIC X VALUE 'N'.
       
       01 WS-CURRENT-ID       PIC 9(5).
       01 WS-TOTAL-COMP       PIC 9(7)V99.
       
       01 WS-TOTAL-REPORT.
           05 WS-REP-ID       PIC 9(5).
           05 FILLER          PIC X(5) VALUE " | TS:".
           05 WS-REP-TOTAL    PIC 9(7).99.

       PROCEDURE DIVISION.
           OPEN INPUT  SALARY-FILE COMM-FILE BONUS-FILE
                OUTPUT REPORT-FILE.

           READ SALARY-FILE AT END MOVE 'Y' TO WS-EOF-SAL.
           READ COMM-FILE   AT END MOVE 'Y' TO WS-EOF-COMM.
           READ BONUS-FILE  AT END MOVE 'Y' TO WS-EOF-BONUS.

           PERFORM UNTIL WS-EOF-SAL = 'Y' AND 
                         WS-EOF-COMM = 'Y' AND 
                         WS-EOF-BONUS = 'Y'
               
               * Determine the minimum ID among the current records
               PERFORM 100-FIND-MIN-ID
               
               MOVE WS-CURRENT-ID TO WS-REP-ID
               MOVE 0 TO WS-TOTAL-COMP
               
               * Process all files that match the minimum ID
               IF WS-EOF-SAL = 'N' AND SAL-ID = WS-CURRENT-ID
                   ADD SAL-AMOUNT TO WS-TOTAL-COMP
                   READ SALARY-FILE AT END MOVE 'Y' TO WS-EOF-SAL
               END-IF
               
               IF WS-EOF-COMM = 'N' AND COMM-ID = WS-CURRENT-ID
                   ADD COMM-AMOUNT TO WS-TOTAL-COMP
                   READ COMM-FILE AT END MOVE 'Y' TO WS-EOF-COMM
               END-IF
               
               IF WS-EOF-BONUS = 'N' AND BONUS-ID = WS-CURRENT-ID
                   ADD BONUS-AMOUNT TO WS-TOTAL-COMP
                   READ BONUS-FILE AT END MOVE 'Y' TO WS-EOF-BONUS
               END-IF
               
               MOVE WS-TOTAL-COMP TO WS-REP-TOTAL
               WRITE REPORT-REC FROM WS-TOTAL-REPORT
           END-PERFORM.

           CLOSE SALARY-FILE COMM-FILE BONUS-FILE REPORT-FILE.
           STOP RUN.

       100-FIND-MIN-ID.
           MOVE 99999 TO WS-CURRENT-ID.
           IF WS-EOF-SAL = 'N' AND SAL-ID < WS-CURRENT-ID
               MOVE SAL-ID TO WS-CURRENT-ID
           END-IF.
           IF WS-EOF-COMM = 'N' AND COMM-ID < WS-CURRENT-ID
               MOVE COMM-ID TO WS-CURRENT-ID
           END-IF.
           IF WS-EOF-BONUS = 'N' AND BONUS-ID < WS-CURRENT-ID
               MOVE BONUS-ID TO WS-CURRENT-ID
           END-IF.
EOF
# Copy the fixed merge.cbl to the app directory if needed
cp merge.cbl ../environment/app/merge.cbl
