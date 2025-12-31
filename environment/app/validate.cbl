       IDENTIFICATION DIVISION.
       PROGRAM-ID. INS-VALIDATOR.
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
           05 ACC-COUNT        PIC 9(5) VALUE 0.
           05 ACC-TOT-PREM     PIC 9(10)V99 VALUE 0.
           05 ACC-TOT-TAX      PIC 9(10)V99 VALUE 0.
           05 ACC-TOT-DUE      PIC 9(10)V99 VALUE 0.

       PROCEDURE DIVISION.
           MOVE FUNCTION CURRENT-DATE(1:8) TO WS-SYS-DATE.
           OPEN INPUT INS-FILE.
           
           READ INS-FILE INTO WS-HDR-REC
           IF HDR-TYPE NOT = 'H'
               DISPLAY "INVALID FORMAT"
               STOP RUN RETURNING 1
           END-IF
           
      * BUG: Fails to validate Header Date against System Date
           
           PERFORM UNTIL WS-EOF = 'Y'
               READ INS-FILE AT END MOVE 'Y' TO WS-EOF
               NOT AT END
                   IF INS-REC(1:1) = 'P'
                       MOVE INS-REC TO WS-POL-REC
                       
      * BUG: Fails to check Policy Checksum
      * BUG: Fails to check Fiscal Integrity (Prem + Tax = Total)
      * BUG: Fails to check Risk-based Tax calculation
      * BUG: Fails to check Banned Countries
      * BUG: Fails to check Account Format or Age range
                       
                       ADD 1 TO ACC-COUNT
                       ADD POL-PREM TO ACC-TOT-PREM
                       ADD POL-TAX TO ACC-TOT-TAX
                       ADD POL-TOTAL TO ACC-TOT-DUE
                   END-IF
                   
                   IF INS-REC(1:1) = 'T'
                       MOVE INS-REC TO WS-TRL-REC
                       MOVE 'Y' TO WS-EOF
                       MOVE 'Y' TO WS-TR-FOUND
                       
      * BUG: Fails to validate aggregate sums, only checks count
                       IF ACC-COUNT NOT = TRL-COUNT
                           DISPLAY "COUNT_ERR"
                           STOP RUN RETURNING 1
                       END-IF
                       
                       DISPLAY "VALID"
                   END-IF
           END-READ
           END-PERFORM.

           IF WS-TR-FOUND NOT = 'Y'
               DISPLAY "BATCH_SUM_ERR"
               STOP RUN RETURNING 1
           END-IF

           CLOSE INS-FILE.
           STOP RUN.
