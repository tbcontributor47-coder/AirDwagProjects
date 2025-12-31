#!/bin/bash
set -eu

cat <<EOF > merge.cbl
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REAL-ESTATE-VALIDATOR.
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
       
       01 WS-SYS-DATE.
          05 WS-SYS-YYYY      PIC 9(4).
          05 WS-SYS-MM        PIC 9(2).
          05 WS-SYS-DD        PIC 9(2).
          
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
          
       01 WS-ACCUM.
          05 WS-ACC-COUNT     PIC 9(5) VALUE 0.
          05 WS-ACC-TOTAL     PIC 9(9)V99 VALUE 0.
          05 WS-ACC-COMP      PIC 9(9)V99 VALUE 0.
          05 WS-ACC-PEND      PIC 9(9)V99 VALUE 0.

       PROCEDURE DIVISION.
           MOVE FUNCTION CURRENT-DATE(1:8) TO WS-SYS-DATE.
           
           OPEN OUTPUT ALL-SITES-FILE.
           
           PERFORM VARYING WS-FILE-COUNT FROM 1 BY 1 
               UNTIL WS-FILE-COUNT > 5
               STRING "data/site" WS-FILE-COUNT ".dat" 
                   DELIMITED BY SIZE INTO WS-FILE-NAME
               
               OPEN INPUT SITE-FILE
               
               READ SITE-FILE INTO WS-HEADER
               IF WS-HDR-DATE NOT = WS-SYS-DATE OR 
                  WS-HDR-PAT NOT = "HHHHHHHHHH"
                   DISPLAY "INVALID HEADER IN " WS-FILE-NAME
                   STOP RUN RETURNING 1
               END-IF
               
               MOVE 0 TO WS-ACCUM
               MOVE 'N' TO WS-EOF
               PERFORM UNTIL WS-EOF = 'Y'
                   READ SITE-FILE AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
                       IF SITE-REC(39:10) = "TTTTTTTTTT"
                           MOVE 'Y' TO WS-EOF
                           MOVE SITE-REC TO WS-TRAILER
                           IF WS-ACC-COUNT NOT = WS-TR-COUNT OR
                              WS-ACC-TOTAL NOT = WS-TR-TOTAL OR
                              WS-ACC-COMP NOT = WS-TR-COMP OR
                              WS-ACC-PEND NOT = WS-TR-PEND
                               DISPLAY "TRAILER MISMATCH IN " 
                                   WS-FILE-NAME
                               STOP RUN RETURNING 1
                           END-IF
                       ELSE
                           MOVE SITE-REC TO WS-DETAIL
                           ADD 1 TO WS-ACC-COUNT
                           ADD WS-VALUE TO WS-ACC-TOTAL
                           IF WS-AGREE = 'Y'
                               ADD WS-VALUE TO WS-ACC-COMP
                           ELSE
                               ADD WS-VALUE TO WS-ACC-PEND
                           END-IF
                           WRITE ALL-SITES-REC FROM SITE-REC
                       END-IF
               END-READ
               END-PERFORM
               
               CLOSE SITE-FILE
           END-PERFORM.

           CLOSE ALL-SITES-FILE.
           STOP RUN.
EOF
