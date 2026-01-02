       IDENTIFICATION DIVISION.
       PROGRAM-ID. INS-REF-VALIDATOR.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INS-FILE ASSIGN TO "insurance.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD INS-FILE.
       01 INS-REC              PIC X(150).
       
       WORKING-STORAGE SECTION.
       01 WS-FLAGS.
           05 WS-EOF           PIC X VALUE 'N'.
           05 WS-TR-FOUND      PIC X VALUE 'N'.

       01 WS-SYS-DATE          PIC 9(8).
       01 WS-ERR-LEVEL         PIC 99 VALUE 99.

       01 WS-HDR-REC.
           05 HDR-TYPE         PIC X.
           05 HDR-DATE         PIC 9(8).
           05 HDR-BATCH        PIC X(10).
           05 HDR-STATE        PIC X(2).
           
       01 WS-POL-REC.
           05 POL-TYPE         PIC X.
           05 POL-NO           PIC 9(10).
           05 POL-HOLDER       PIC X(20).
           05 POL-PREM         PIC 9(6)V99.
           05 POL-TAX          PIC 9(6)V99.
           05 POL-TOTAL        PIC 9(6)V99.
           05 POL-RISK         PIC X.
           05 POL-COUNTRY      PIC X(2).
           05 POL-ACC          PIC 9(10).
           05 POL-AGE          PIC 9(3).

       01 WS-TRL-REC.
           05 TRL-TYPE         PIC X.
           05 TRL-COUNT        PIC 9(5).
           05 TRL-TOT-PREM     PIC 9(10)V99.
           05 TRL-TOT-TAX      PIC 9(10)V99.
           05 TRL-TOT-DUE      PIC 9(10)V99.
           
       01 WS-ACCUM.
           05 ACC-COUNT        PIC 9(10) VALUE 0.
           05 ACC-TOT-PREM     PIC 9(10)V99 VALUE 0.
           05 ACC-TOT-TAX      PIC 9(10)V99 VALUE 0.
           05 ACC-TOT-DUE      PIC 9(10)V99 VALUE 0.
           
       01 WS-WORK.
           05 WORK-TAX-CALC    PIC 9(7)V999.
           05 WORK-TAX-ROUND   PIC 9(6)V99.
           05 WORK-CHKSUM      PIC 9(5) VALUE 0.
           05 WORK-IDX         PIC 9(2).
           05 WORK-POL-STR     PIC X(10).
           05 WORK-POL-REDEF REDEFINES WORK-POL-STR.
              10 WORK-POL-DIGIT PIC 9 OCCURS 10 TIMES.
       01 WS-COUNT-MOD         PIC 9(5).

       PROCEDURE DIVISION.
           MOVE FUNCTION CURRENT-DATE(1:8) TO WS-SYS-DATE.
           OPEN INPUT INS-FILE.
           
           READ INS-FILE INTO WS-HDR-REC
           IF HDR-TYPE NOT = 'H'
               DISPLAY "INVALID FORMAT"
               STOP RUN RETURNING 1
           END-IF
           
           IF HDR-DATE NOT = WS-SYS-DATE
               DISPLAY "DATE_ERR"
               STOP RUN RETURNING 1
           END-IF
           
           PERFORM UNTIL WS-EOF = 'Y'
               READ INS-FILE AT END MOVE 'Y' TO WS-EOF
               NOT AT END
                   IF INS-REC(1:1) = 'P'
                       MOVE INS-REC TO WS-POL-REC
                       
                       IF INS-REC(59:10) IS NOT NUMERIC
                          OR INS-REC(59:1) NOT = '9'
                           DISPLAY "FORMAT_ERR"
                           STOP RUN RETURNING 1
                       END-IF

                       IF POL-COUNTRY = 'RU'
                          OR POL-COUNTRY = 'KP'
                           DISPLAY "BANNED_ERR"
                           STOP RUN RETURNING 1
                       END-IF

                       IF POL-AGE < 18 OR POL-AGE > 120
                           DISPLAY "AGE_ERR"
                           STOP RUN RETURNING 1
                       END-IF

                       IF POL-PREM > 100000.00
                          IF 6 < WS-ERR-LEVEL
                              MOVE 6 TO WS-ERR-LEVEL
                          END-IF
                       END-IF
                       IF POL-TOTAL NOT = POL-PREM + POL-TAX
                          IF 6 < WS-ERR-LEVEL
                              MOVE 6 TO WS-ERR-LEVEL
                          END-IF
                       END-IF

                       MOVE 0 TO WORK-TAX-CALC
                       IF POL-RISK = '3'
                           COMPUTE WORK-TAX-CALC = POL-PREM * 0.10
                       ELSE IF POL-RISK = '2'
                           COMPUTE WORK-TAX-CALC = POL-PREM * 0.05
                       ELSE
                           MOVE 0 TO WORK-TAX-CALC
                       END-IF END-IF
                       
                       ADD 0.005 TO WORK-TAX-CALC
                       MOVE WORK-TAX-CALC TO WORK-TAX-ROUND
                       IF POL-TAX NOT = WORK-TAX-ROUND
                           IF 7 < WS-ERR-LEVEL
                               MOVE 7 TO WS-ERR-LEVEL
                           END-IF
                       END-IF

                       MOVE 0 TO WORK-CHKSUM
                       MOVE POL-NO TO WORK-POL-STR
                       PERFORM VARYING WORK-IDX FROM 1 BY 1
                           UNTIL WORK-IDX > 9
                           ADD WORK-POL-DIGIT(WORK-IDX)
                               TO WORK-CHKSUM
                       END-PERFORM
                       
                       IF FUNCTION MOD(WORK-CHKSUM, 10)
                          NOT = WORK-POL-DIGIT(10)
                           IF 8 < WS-ERR-LEVEL
                               MOVE 8 TO WS-ERR-LEVEL
                           END-IF
                       END-IF
                       
                       ADD 1 TO ACC-COUNT
                       ADD POL-PREM TO ACC-TOT-PREM
                       ADD POL-TAX TO ACC-TOT-TAX
                       ADD POL-TOTAL TO ACC-TOT-DUE
                   END-IF
                   
                   IF INS-REC(1:1) = 'T'
                       MOVE INS-REC TO WS-TRL-REC
                       MOVE 'Y' TO WS-EOF
                       MOVE 'Y' TO WS-TR-FOUND
                       
                       MOVE FUNCTION MOD(ACC-COUNT, 100000) 
                         TO WS-COUNT-MOD
                       IF WS-COUNT-MOD NOT = TRL-COUNT
                           DISPLAY "COUNT_ERR"
                           STOP RUN RETURNING 1
                       END-IF
                       
                       IF ACC-TOT-PREM NOT = TRL-TOT-PREM
                          IF 9 < WS-ERR-LEVEL
                              MOVE 9 TO WS-ERR-LEVEL
                          END-IF
                       END-IF
                       IF ACC-TOT-TAX NOT = TRL-TOT-TAX
                          IF 9 < WS-ERR-LEVEL
                              MOVE 9 TO WS-ERR-LEVEL
                          END-IF
                       END-IF
                       IF ACC-TOT-DUE NOT = TRL-TOT-DUE
                          IF 9 < WS-ERR-LEVEL
                              MOVE 9 TO WS-ERR-LEVEL
                          END-IF
                       END-IF
                   END-IF
           END-READ
           END-PERFORM.

           IF WS-TR-FOUND NOT = 'Y'
               DISPLAY "COUNT_ERR"
               STOP RUN RETURNING 1
           END-IF

           EVALUATE WS-ERR-LEVEL
               WHEN 6
                   DISPLAY "FISCAL_ERR"
                   STOP RUN RETURNING 1
               WHEN 7
                   DISPLAY "TAX_ERR"
                   STOP RUN RETURNING 1
               WHEN 8
                   DISPLAY "CHECKSUM_ERR"
                   STOP RUN RETURNING 1
               WHEN 9
                   DISPLAY "BATCH_SUM_ERR"
                   STOP RUN RETURNING 1
               WHEN 99
                   DISPLAY "VALID"
                   STOP RUN RETURNING 0
           END-EVALUATE.

           CLOSE INS-FILE.
           STOP RUN.
