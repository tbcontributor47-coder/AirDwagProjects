package com.tbench.insurance;

import java.io.*;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

public class Validator {
    
    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyyMMdd");
    
    public static void main(String[] args) {
        try {
            BufferedReader reader;
            if (args.length > 0) {
                reader = new BufferedReader(new FileReader(args[0]), 65536);
            } else {
                reader = new BufferedReader(new InputStreamReader(System.in), 65536);
            }
            
            int exitCode = validate(reader);
            reader.close();
            System.exit(exitCode);
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            System.exit(1);
        }
    }
    
    private static int validate(BufferedReader reader) throws IOException {
        String line = reader.readLine();
        if (line == null || line.isEmpty() || line.charAt(0) != 'H') {
            System.out.println("INVALID FORMAT");
            return 1;
        }
        
        // Parse header - use direct string operations
        String headerDate = line.substring(1, 9);
        String todayDate = LocalDate.now().format(DATE_FMT);
        
        // BUG 3: Missing Date Check
        /*
        if (!headerDate.equals(todayDate)) {
            System.out.println("DATE_ERR");
            return 1;
        }
        */
        
        // Accumulators - use primitives only
        int count = 0;
        long totalPremCents = 0;
        long totalTaxCents = 0;
        long totalDueCents = 0;
        
        // Error level tracking (99 = valid)
        int errorLevel = 99;
        
        // Process policy records
        while ((line = reader.readLine()) != null) {
            if (line.isEmpty()) continue;
            
            char recType = line.charAt(0);
            
            if (recType == 'P') {
                // Parse policy record - direct substring + parse, no intermediate objects
                char[] policyNo = line.substring(1, 11).toCharArray();
                long premCents = parseLong(line, 31, 39);
                long taxCents = parseLong(line, 39, 47);
                long dueCents = parseLong(line, 47, 55);
                char risk = line.charAt(55);
                char country1 = line.charAt(56);
                char country2 = line.charAt(57);
                char[] account = line.substring(58, 68).toCharArray();
                int age = parseInt(line, 68, 71);
                
                // BUG 1: Removed IS NUMERIC check
                /*
                if (!isNumeric(account) || account[0] != '9') {
                    System.out.println("FORMAT_ERR");
                    return 1;
                }
                */
                if (account[0] != '9') { // Partial check
                    System.out.println("FORMAT_ERR");
                    return 1;
                }
                
                // BANNED_ERR (Priority 3)
                if ((country1 == 'R' && country2 == 'U') || (country1 == 'K' && country2 == 'P')) {
                    System.out.println("BANNED_ERR");
                    return 1;
                }
                
                // AGE_ERR (Priority 4)
                // BUG 4: Wrong upper age limit
                if (age < 18 || age > 150) {
                    System.out.println("AGE_ERR");
                    return 1;
                }
                
                // FISCAL_ERR (Priority 6)
                if (premCents > 10000000L || dueCents != premCents + taxCents) {
                    if (6 < errorLevel) errorLevel = 6;
                }
                
                // TAX_ERR (Priority 7) - inline calculation
                long expectedTaxCents = 0;
                if (risk == '3') {
                    expectedTaxCents = (premCents * 10L + 50L) / 100L;
                } else if (risk == '2') {
                    // BUG 2: Using 4% instead of 5%
                    expectedTaxCents = (premCents * 4L + 50L) / 100L;
                }
                
                if (taxCents != expectedTaxCents) {
                    if (7 < errorLevel) errorLevel = 7;
                }
                
                // CHECKSUM_ERR (Priority 8) - inline calculation
                int checksum = 0;
                for (int i = 0; i < 9; i++) {
                    checksum += (policyNo[i] - '0');
                }
                
                if ((checksum % 10) != (policyNo[9] - '0')) {
                    if (8 < errorLevel) errorLevel = 8;
                }
                
                // Accumulate
                count++;
                totalPremCents += premCents;
                totalTaxCents += taxCents;
                totalDueCents += dueCents;
                
            } else if (recType == 'T') {
                // Parse trailer
                int trlCount = parseInt(line, 1, 6);
                long trlPremCents = parseLong(line, 6, 18);
                long trlTaxCents = parseLong(line, 18, 30);
                long trlDueCents = parseLong(line, 30, 42);
                
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
        
        // Report error based on priority
        switch (errorLevel) {
            case 6:
                System.out.println("FISCAL_ERR");
                return 1;
            case 7:
                System.out.println("TAX_ERR");
                return 1;
            case 8:
                System.out.println("CHECKSUM_ERR");
                return 1;
            case 9:
                System.out.println("BATCH_SUM_ERR");
                return 1;
            default:
                System.out.println("VALID");
                return 0;
        }
    }
    
    // Fast integer parsing without creating String objects
    private static int parseInt(String s, int start, int end) {
        int result = 0;
        for (int i = start; i < end; i++) {
            result = result * 10 + (s.charAt(i) - '0');
        }
        return result;
    }
    
    private static long parseLong(String s, int start, int end) {
        long result = 0;
        for (int i = start; i < end; i++) {
            result = result * 10L + (s.charAt(i) - '0');
        }
        return result;
    }
    
    private static boolean isNumeric(char[] arr) {
        for (char c : arr) {
            if (c < '0' || c > '9') return false;
        }
        return true;
    }
}
