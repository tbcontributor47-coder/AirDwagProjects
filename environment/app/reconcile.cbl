       IDENTIFICATION DIVISION.
       PROGRAM-ID. RECONCILE.
       
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO "input.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT BALANCED-REPORT ASSIGN TO "balanced_report.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT HIGH-VALUE-REPORT ASSIGN TO "high_value.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT ANOMALY-LOG ASSIGN TO "anomalies.dat"
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD  INPUT-FILE.
       01  IN-RECORD.
           05  IN-TYPE        PIC X(02).
           05  IN-DATA        PIC X(98).

       FD  BALANCED-REPORT.
       01  REPORT-LINE        PIC X(100).

       FD  HIGH-VALUE-REPORT.
       01  HV-LINE            PIC X(100).

       FD  ANOMALY-LOG.
       01  AL-LINE            PIC X(100).

       WORKING-STORAGE SECTION.
       01  WS-FLAGS.
           05  WS-EOF          PIC X(01) VALUE 'N'.
           05  WS-REJECTED     PIC X(01) VALUE 'N'.

       01  WS-TOTALS.
           05  WS-TOTAL-DEBITS  PIC 9(13)V99 VALUE 0.
           05  WS-TOTAL-CREDITS PIC 9(13)V99 VALUE 0.
           05  WS-CALC-COUNT    PIC 9(05)    VALUE 0.
           05  WS-CALC-NET      PIC S9(13)V99 VALUE 0.

       01  WS-TRAILER-DATA.
           05  WS-TR-COUNT      PIC 9(05).
           05  WS-TR-NET        PIC S9(13)V99.

       01  WS-TX-ARRAY.
           05  WS-TX-DATA OCCURS 50 TIMES INDEXED BY TX-IDX.
               10  TX-ACC-ID   PIC X(10).
               10  TX-AMOUNT   PIC 9(13)V99.
               10  TX-DC-FLAG  PIC X(01).
               10  TX-REF      PIC X(20).

       01  WS-RECORD-DEFS.
           05  WS-HEADER.
               10  WS-HD-TYPE   PIC X(02).
               10  WS-HD-BATCH  PIC X(10).
               10  WS-HD-DATE   PIC X(08).
           
           05  WS-TX-REC.
               10  WS-TX-TYPE   PIC X(02).
               10  WS-TX-ACC    PIC X(10).
               10  WS-TX-AMT    PIC 9(13)V99.
               10  WS-TX-DC     PIC X(01).
               10  WS-TX-REF    PIC X(20).

           05  WS-TRAILER.
               10  WS-TR-TYPE   PIC X(02).
               10  WS-TR-CNT    PIC 9(05).
               10  WS-TR-AMT    PIC S9(13)V99.

       PROCEDURE DIVISION.
       MAIN-PROCEDURE.
           OPEN INPUT INPUT-FILE
                OUTPUT BALANCED-REPORT
                       HIGH-VALUE-REPORT
                       ANOMALY-LOG
           
           PERFORM READ-INPUT-FILE
           PERFORM UNTIL WS-EOF = 'Y' OR WS-REJECTED = 'Y'
               EVALUATE IN-TYPE
                   WHEN '01'
                       CONTINUE
                   WHEN '02'
                       PERFORM PROCESS-TRANSACTION
                   WHEN '03'
                       PERFORM PROCESS-TRAILER
               END-EVALUATE
               PERFORM READ-INPUT-FILE
           END-PERFORM
           
           IF WS-REJECTED = 'N'
               PERFORM GENERATE-REPORTS
           END-IF

           CLOSE INPUT-FILE
                 BALANCED-REPORT
                 HIGH-VALUE-REPORT
                 ANOMALY-LOG
           GOBACK.

       READ-INPUT-FILE.
           READ INPUT-FILE
               AT END MOVE 'Y' TO WS-EOF
           END-READ.

       PROCESS-TRANSACTION.
           MOVE IN-RECORD TO WS-TX-REC
           
           ADD 1 TO WS-CALC-COUNT
           SET TX-IDX TO WS-CALC-COUNT
           
           *> BUG: Lack of array bounds check will crash if count > 50
           MOVE WS-TX-ACC TO TX-ACC-ID(TX-IDX)
           MOVE WS-TX-AMT TO TX-AMOUNT(TX-IDX)
           MOVE WS-TX-DC  TO TX-DC-FLAG(TX-IDX)
           MOVE WS-TX-REF TO TX-REF(TX-IDX)

           IF WS-TX-DC = 'D'
               ADD WS-TX-AMT TO WS-TOTAL-DEBITS
           ELSE
               ADD WS-TX-AMT TO WS-TOTAL-CREDITS
           END-IF.

       PROCESS-TRAILER.
           MOVE IN-RECORD TO WS-TRAILER
           MOVE WS-TR-CNT TO WS-TR-COUNT
           MOVE WS-TR-AMT TO WS-TR-NET
           
           *> BUG: Symmetrical mismatch error in business logic
           COMPUTE WS-CALC-NET = WS-TOTAL-DEBITS - WS-TOTAL-CREDITS

           IF WS-CALC-COUNT NOT = WS-TR-COUNT
               DISPLAY "WARNING: COUNT MISMATCH"
           END-IF.

       GENERATE-REPORTS.
           WRITE REPORT-LINE FROM "BALANCED REPORT SUMMARY"
           STRING "TOTAL COUNT: " WS-CALC-COUNT 
                  DELIMITED BY SIZE INTO REPORT-LINE
           WRITE REPORT-LINE
           STRING "TOTAL NET: " WS-CALC-NET
                  DELIMITED BY SIZE INTO REPORT-LINE
           WRITE REPORT-LINE.

           SET TX-IDX TO 1
           PERFORM UNTIL TX-IDX > WS-CALC-COUNT
               IF TX-AMOUNT(TX-IDX) > 1000.00
                   WRITE HV-LINE FROM WS-TX-DATA(TX-IDX)
               END-IF
               SET TX-IDX UP BY 1
           END-PERFORM.
