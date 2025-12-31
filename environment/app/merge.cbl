       IDENTIFICATION DIVISION.
       PROGRAM-ID. REAL-ESTATE-MERGE.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SITE-FILE ASSIGN TO WS-FILE-NAME
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT ALL-SITES-FILE ASSIGN TO "all_sites.dat"
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD SITE-FILE.
       01 SITE-REC            PIC X(152).
       
       FD ALL-SITES-FILE.
       01 ALL-SITES-REC       PIC X(152).

       WORKING-STORAGE SECTION.
       01 WS-FILE-NAME        PIC X(30).
       01 WS-FILE-COUNT       PIC 9 VALUE 1.
       01 WS-EOF              PIC X VALUE 'N'.
       
       01 WS-HEADER.
          05 WS-HDR-DATE      PIC 9(8).
          05 WS-HDR-PAT       PIC X(10).
          
       01 WS-DETAIL.
          05 WS-OWNER         PIC X(20).
          05 WS-ACC           PIC X(20).
          05 WS-SNO           PIC 9(5).
          05 WS-LOC           PIC X(30).
          05 WS-DET           PIC X(50).
          05 WS-AGREE         PIC X.
          05 WS-PHONE         PIC X(15).
          05 WS-VALUE         PIC 9(9)V99.

       01 WS-TRAILER.
          05 WS-TR-COUNT      PIC 9(5).
          05 WS-TR-TOTAL      PIC 9(9)V99.
          05 WS-TR-COMP       PIC 9(9)V99.
          05 WS-TR-PEND       PIC 9(9)V99.
          05 WS-TR-PAT        PIC X(10).

       PROCEDURE DIVISION.
           OPEN OUTPUT ALL-SITES-FILE.
           
           PERFORM VARYING WS-FILE-COUNT FROM 1 BY 1 UNTIL WS-FILE-COUNT > 5
               STRING "data/site" WS-FILE-COUNT ".dat" DELIMITED BY SIZE
                      INTO WS-FILE-NAME
               
               OPEN INPUT SITE-FILE
      * BUG: Fails to read Header, treats Header as Detail
      * BUG: Fails to validate Date or Header pattern
               MOVE 'N' TO WS-EOF
               PERFORM UNTIL WS-EOF = 'Y'
                   READ SITE-FILE AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
      * BUG: Fails to detect Trailer, treats Trailer as Detail
                       WRITE ALL-SITES-REC FROM SITE-REC
               END-READ
               END-PERFORM
               
               CLOSE SITE-FILE
           END-PERFORM.

           CLOSE ALL-SITES-FILE.
           STOP RUN.
