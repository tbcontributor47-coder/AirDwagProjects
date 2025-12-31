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
               
               * BUG: Naive assumption that ID matches across all files
               * It just reads one record from each file simultaneously.
               * If IDs are missing or mismatched, results will be wrong.
               
               MOVE SAL-ID TO WS-REP-ID
               COMPUTE WS-REP-TOTAL = SAL-AMOUNT + COMM-AMOUNT + 
                                      BONUS-AMOUNT
               
               WRITE REPORT-REC FROM WS-TOTAL-REPORT
               
               READ SALARY-FILE AT END MOVE 'Y' TO WS-EOF-SAL
               READ COMM-FILE   AT END MOVE 'Y' TO WS-EOF-COMM
               READ BONUS-FILE  AT END MOVE 'Y' TO WS-EOF-BONUS
           END-PERFORM.

           CLOSE SALARY-FILE COMM-FILE BONUS-FILE REPORT-FILE.
           STOP RUN.
