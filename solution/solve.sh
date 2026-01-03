#!/bin/bash
# Oracle solution for Banking Reconciliation Engine - Final Robust Version

APP_DIR="environment/app"
mkdir -p $APP_DIR

cat > $APP_DIR/reconcile.cbl << 'EOF'
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
           05  WS-FILE-COUNT    PIC 9(05)    VALUE 0.
           05  WS-CALC-COUNT    PIC 9(05)    VALUE 0.
           05  WS-TOTAL-DEBITS  PIC 9(13)V99 VALUE 0.
           05  WS-TOTAL-CREDITS PIC 9(13)V99 VALUE 0.
           05  WS-CALC-NET      PIC S9(13)V99 VALUE 0.

       01  WS-TX-ARRAY.
           05  WS-TX-DATA OCCURS 1000 TIMES INDEXED BY TX-IDX.
               10  TX-ACC-ID   PIC X(10).
               10  TX-AMOUNT   PIC 9(13)V99.
               10  TX-DC-FLAG  PIC X(01).
               10  TX-REF      PIC X(20).

       01  WS-RECORD-DEFS.
           05  WS-TX-REC.
               10  FILLER       PIC X(02).
               10  WS-TX-ACC    PIC X(10).
               10  WS-TX-AMT    PIC 9(13)V99.
               10  WS-TX-DC     PIC X(01).
               10  WS-TX-REF    PIC X(20).

           05  WS-TRAILER.
               10  FILLER       PIC X(02).
               10  WS-TR-CNT    PIC 9(05).
               10  WS-TR-AMT    PIC S9(13)V99 SIGN IS LEADING SEPARATE.

       01  WS-CHECKSUM-CALC.
           05  WS-NUMERIC-ACC   PIC 9(10).
           05  WS-MOD-RESULT    PIC 9(02).
           05  WS-QUOTIENT      PIC 9(10).

       01  WS-REPORT-FIELDS.
           05  WS-DISP-COUNT    PIC 9(05).
           05  WS-DISP-NET      PIC S9(13)V99 SIGN IS LEADING SEPARATE.

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
           ELSE
               MOVE SPACES TO REPORT-LINE
               WRITE REPORT-LINE FROM "BATCH REJECTED"
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
           ADD 1 TO WS-FILE-COUNT
           MOVE IN-RECORD TO WS-TX-REC
           
           MOVE WS-TX-ACC TO WS-NUMERIC-ACC
           DIVIDE WS-NUMERIC-ACC BY 97 GIVING WS-QUOTIENT 
               REMAINDER WS-MOD-RESULT
           
           IF WS-MOD-RESULT NOT = 1
               WRITE AL-LINE FROM WS-TX-REC
           ELSE
               ADD 1 TO WS-CALC-COUNT
               SET TX-IDX TO WS-CALC-COUNT
               
               MOVE WS-TX-ACC TO TX-ACC-ID(TX-IDX)
               MOVE WS-TX-AMT TO TX-AMOUNT(TX-IDX)
               MOVE WS-TX-DC  TO TX-DC-FLAG(TX-IDX)
               MOVE WS-TX-REF TO TX-REF(TX-IDX)

               IF WS-TX-DC = 'D'
                   ADD WS-TX-AMT TO WS-TOTAL-DEBITS
               ELSE
                   ADD WS-TX-AMT TO WS-TOTAL-CREDITS
               END-IF
           END-IF.

       PROCESS-TRAILER.
           MOVE IN-RECORD TO WS-TRAILER
           
           COMPUTE WS-CALC-NET = WS-TOTAL-CREDITS - WS-TOTAL-DEBITS
           
           IF WS-CALC-NET NOT = WS-TR-AMT 
               OR WS-FILE-COUNT NOT = WS-TR-CNT
               MOVE 'Y' TO WS-REJECTED
           END-IF.

       GENERATE-REPORTS.
           MOVE SPACES TO REPORT-LINE
           WRITE REPORT-LINE FROM "BALANCED REPORT SUMMARY"
           
           MOVE WS-CALC-COUNT TO WS-DISP-COUNT
           MOVE SPACES TO REPORT-LINE
           STRING "TOTAL COUNT: " 
                  WS-DISP-COUNT 
                  DELIMITED BY SIZE INTO REPORT-LINE
           WRITE REPORT-LINE
           
           MOVE WS-CALC-NET TO WS-DISP-NET
           MOVE SPACES TO REPORT-LINE
           STRING "TOTAL NET: " 
                  WS-DISP-NET
                  DELIMITED BY SIZE INTO REPORT-LINE
           WRITE REPORT-LINE

           SET TX-IDX TO 1
           PERFORM UNTIL TX-IDX > WS-CALC-COUNT
               IF TX-AMOUNT(TX-IDX) > 10000.00
                   WRITE HV-LINE FROM WS-TX-DATA(TX-IDX)
               END-IF
               SET TX-IDX UP BY 1
           END-PERFORM.
EOF
chmod +x $APP_DIR/reconcile.cbl
