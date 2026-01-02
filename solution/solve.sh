#!/bin/bash
set -eu

# This script fixes the buggy COBOL validator and implements the Java migration

echo "Fixing COBOL validator bugs..."

# Find the COBOL file
if [ -f "validate.cbl" ]; then
    COBOL_FILE="validate.cbl"
elif [ -f "environment/app/validate.cbl" ]; then
    COBOL_FILE="environment/app/validate.cbl"
elif [ -f "../environment/app/validate.cbl" ]; then
    COBOL_FILE="../environment/app/validate.cbl"
elif [ -f "/app/validate.cbl" ]; then
    COBOL_FILE="/app/validate.cbl"
else
    echo "ERROR: Cannot find validate.cbl"
    exit 1
fi

echo "Found COBOL file at: $COBOL_FILE"

# Convert to Unix line endings first for easier processing
dos2unix "$COBOL_FILE" 2>/dev/null || sed -i 's/\r$//' "$COBOL_FILE"

# BUG FIX 1: Uncomment date validation (lines 90-94)
# Remove the "BUG 3" comment line
sed -i '/\* BUG 3: Missing Date Check/d' "$COBOL_FILE"

# Uncomment the date check lines - exact pattern matching
sed -i 's/^      \*     IF HDR-DATE NOT = WS-SYS-DATE$/            IF HDR-DATE NOT = WS-SYS-DATE/' "$COBOL_FILE"
sed -i 's/^      \*         DISPLAY "DATE_ERR"$/                DISPLAY "DATE_ERR"/' "$COBOL_FILE"
sed -i 's/^      \*         STOP RUN RETURNING 1$/                STOP RUN RETURNING 1/' "$COBOL_FILE"
sed -i 's/^      \*     END-IF$/            END-IF/' "$COBOL_FILE"

# BUG FIX 2: Fix tax rate for Risk '2' from 0.04 to 0.05
sed -i 's/COMPUTE WORK-TAX-CALC = POL-PREM \* 0\.04/COMPUTE WORK-TAX-CALC = POL-PREM * 0.05/' "$COBOL_FILE"

# BUG FIX 3: Uncomment numeric validation (lines 104-107)
# Remove the "BUG 1" comment line
sed -i '/\* BUG 1: Removed IS NUMERIC check/d' "$COBOL_FILE"

# Uncomment the numeric check lines - exact pattern matching
sed -i 's/^      \*                 IF INS-REC(59:10) IS NOT NUMERIC$/                        IF INS-REC(59:10) IS NOT NUMERIC/' "$COBOL_FILE"
sed -i 's/^      \*                     DISPLAY "FORMAT_ERR"$/                            DISPLAY "FORMAT_ERR"/' "$COBOL_FILE"
sed -i 's/^      \*                     STOP RUN RETURNING 1$/                            STOP RUN RETURNING 1/' "$COBOL_FILE"
sed -i 's/^      \*                 END-IF$/                        END-IF/' "$COBOL_FILE"

echo "COBOL bugs fixed!"

# Now implement the Java validator
echo "Implementing Java validator..."

# Find the Java source directory
if [ -d "src/main/java/com/tbench/insurance" ]; then
    JAVA_DIR="src/main/java/com/tbench/insurance"
elif [ -d "environment/app/src/main/java/com/tbench/insurance" ]; then
    JAVA_DIR="environment/app/src/main/java/com/tbench/insurance"
elif [ -d "../environment/app/src/main/java/com/tbench/insurance" ]; then
    JAVA_DIR="../environment/app/src/main/java/com/tbench/insurance"
elif [ -d "/app/src/main/java/com/tbench/insurance" ]; then
    JAVA_DIR="/app/src/main/java/com/tbench/insurance"
else
    echo "ERROR: Cannot find Java source directory"
    exit 1
fi

echo "Found Java directory at: $JAVA_DIR"

# Create ULTRA-OPTIMIZED Validator.java - every microsecond counts
cat > "$JAVA_DIR/Validator.java" <<'EOFJAVA'
package com.tbench.insurance;

import java.io.*;

public class Validator {
    
    // Pre-computed date string to avoid LocalDate overhead
    private static final String TODAY;
    
    static {
        java.time.LocalDate now = java.time.LocalDate.now();
        int y = now.getYear();
        int m = now.getMonthValue();
        int d = now.getDayOfMonth();
        TODAY = String.format("%04d%02d%02d", y, m, d);
    }
    
    public static void main(String[] args) {
        try {
            // Use FileInputStream with large buffer for maximum throughput
            InputStream in;
            if (args.length > 0) {
                in = new BufferedInputStream(new FileInputStream(args[0]), 131072);
            } else {
                in = new BufferedInputStream(System.in, 131072);
            }
            
            System.exit(validate(in));
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            System.exit(1);
        }
    }
    
    private static int validate(InputStream in) throws IOException {
        byte[] buf = new byte[256];
        int len = readLine(in, buf);
        
        if (len < 1 || buf[0] != 'H') {
            System.out.println("INVALID FORMAT");
            return 1;
        }
        
        // DATE_ERR (Priority 1) - compare bytes directly
        if (buf[1] != TODAY.charAt(0) || buf[2] != TODAY.charAt(1) ||
            buf[3] != TODAY.charAt(2) || buf[4] != TODAY.charAt(3) ||
            buf[5] != TODAY.charAt(4) || buf[6] != TODAY.charAt(5) ||
            buf[7] != TODAY.charAt(6) || buf[8] != TODAY.charAt(7)) {
            System.out.println("DATE_ERR");
            return 1;
        }
        
        int count = 0;
        long totalPremCents = 0;
        long totalTaxCents = 0;
        long totalDueCents = 0;
        int errorLevel = 99;
        
        while ((len = readLine(in, buf)) > 0) {
            byte recType = buf[0];
            
            if (recType == 'P') {
                // Parse directly from bytes - no String allocation
                long premCents = parseLong(buf, 31, 39);
                long taxCents = parseLong(buf, 39, 47);
                long dueCents = parseLong(buf, 47, 55);
                byte risk = buf[55];
                byte country1 = buf[56];
                byte country2 = buf[57];
                int age = parseInt(buf, 68, 71);
                
                // FORMAT_ERR (Priority 2) - check numeric and starts with 9
                if (!isNumeric(buf, 58, 68) || buf[58] != '9') {
                    System.out.println("FORMAT_ERR");
                    return 1;
                }
                
                // BANNED_ERR (Priority 3)
                if ((country1 == 'R' && country2 == 'U') || (country1 == 'K' && country2 == 'P')) {
                    System.out.println("BANNED_ERR");
                    return 1;
                }
                
                // AGE_ERR (Priority 4)
                if (age < 18 || age > 120) {
                    System.out.println("AGE_ERR");
                    return 1;
                }
                
                // FISCAL_ERR (Priority 6)
                if (premCents > 10000000L || dueCents != premCents + taxCents) {
                    if (6 < errorLevel) errorLevel = 6;
                }
                
                // TAX_ERR (Priority 7)
                long expectedTaxCents = 0;
                if (risk == '3') {
                    expectedTaxCents = (premCents * 10L + 50L) / 100L;
                } else if (risk == '2') {
                    expectedTaxCents = (premCents * 5L + 50L) / 100L;
                }
                
                if (taxCents != expectedTaxCents) {
                    if (7 < errorLevel) errorLevel = 7;
                }
                
                // CHECKSUM_ERR (Priority 8)
                int checksum = (buf[1] - '0') + (buf[2] - '0') + (buf[3] - '0') +
                               (buf[4] - '0') + (buf[5] - '0') + (buf[6] - '0') +
                               (buf[7] - '0') + (buf[8] - '0') + (buf[9] - '0');
                
                if ((checksum % 10) != (buf[10] - '0')) {
                    if (8 < errorLevel) errorLevel = 8;
                }
                
                count++;
                totalPremCents += premCents;
                totalTaxCents += taxCents;
                totalDueCents += dueCents;
                
            } else if (recType == 'T') {
                int trlCount = parseInt(buf, 1, 6);
                long trlPremCents = parseLong(buf, 6, 18);
                long trlTaxCents = parseLong(buf, 18, 30);
                long trlDueCents = parseLong(buf, 30, 42);
                
                // COUNT_ERR (Priority 5)
                if (count != trlCount) {
                    System.out.println("COUNT_ERR");
                    return 1;
                }
                
                // BATCH_SUM_ERR (Priority 9)
                if (totalPremCents != trlPremCents || totalTaxCents != trlTaxCents || totalDueCents != trlDueCents) {
                    if (9 < errorLevel) errorLevel = 9;
                }
                
                break;
            }
        }
        
        // Report error
        switch (errorLevel) {
            case 6: System.out.println("FISCAL_ERR"); return 1;
            case 7: System.out.println("TAX_ERR"); return 1;
            case 8: System.out.println("CHECKSUM_ERR"); return 1;
            case 9: System.out.println("BATCH_SUM_ERR"); return 1;
            default: System.out.println("VALID"); return 0;
        }
    }
    
    // Read a line into byte buffer, return length (excluding newline)
    private static int readLine(InputStream in, byte[] buf) throws IOException {
        int pos = 0;
        int b;
        while ((b = in.read()) != -1) {
            if (b == '\n') break;
            if (b != '\r') buf[pos++] = (byte) b;
        }
        return pos;
    }
    
    // Parse int from byte array
    private static int parseInt(byte[] buf, int start, int end) {
        int result = 0;
        for (int i = start; i < end; i++) {
            result = result * 10 + (buf[i] - '0');
        }
        return result;
    }
    
    // Parse long from byte array
    private static long parseLong(byte[] buf, int start, int end) {
        long result = 0;
        for (int i = start; i < end; i++) {
            result = result * 10L + (buf[i] - '0');
        }
        return result;
    }
    
    // Check if bytes are all digits
    private static boolean isNumeric(byte[] buf, int start, int end) {
        for (int i = start; i < end; i++) {
            byte b = buf[i];
            if (b < '0' || b > '9') return false;
        }
        return true;
    }
}
EOFJAVA

echo "Java validator implementation complete!"

# Build the Java JAR if we can find Maven
if command -v mvn &> /dev/null; then
    echo "Building Java JAR with Maven..."
    
    # Find pom.xml
    if [ -f "pom.xml" ]; then
        POM_DIR="."
    elif [ -f "environment/app/pom.xml" ]; then
        POM_DIR="environment/app"
    elif [ -f "../environment/app/pom.xml" ]; then
        POM_DIR="../environment/app"
    elif [ -f "/app/pom.xml" ]; then
        POM_DIR="/app"
    else
        echo "WARNING: Cannot find pom.xml, skipping Maven build"
        POM_DIR=""
    fi
    
    if [ -n "$POM_DIR" ]; then
        cd "$POM_DIR"
        mvn clean package -DskipTests -q
        echo "Java JAR built successfully at $POM_DIR/target/validator.jar"
    fi
else
    echo "WARNING: Maven not found, skipping Java build"
fi

echo "All fixes applied successfully."
