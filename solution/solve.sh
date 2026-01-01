#!/bin/bash
set -eu

mkdir -p src/main/java/com/finance
cat <<EOF > src/main/java/com/finance/CommissionService.java
package com.finance;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class CommissionService {
    public BigDecimal calculatePayout(BigDecimal grossPremium) {
        BigDecimal commission = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        BigDecimal remaining = grossPremium.setScale(2, RoundingMode.HALF_UP);

        // Tier 1: 5% on first 10,000
        BigDecimal t1Amount = remaining.min(new BigDecimal("10000.00"));
        commission = commission.add(t1Amount.multiply(new BigDecimal("0.05")).setScale(2, RoundingMode.HALF_UP));
        remaining = remaining.subtract(t1Amount);

        // Tier 2: 10% on next 40,000
        BigDecimal t2Amount = remaining.min(new BigDecimal("40000.00"));
        commission = commission.add(t2Amount.multiply(new BigDecimal("0.10")).setScale(2, RoundingMode.HALF_UP));
        remaining = remaining.subtract(t2Amount);

        // Tier 3: 15% on remainder
        if (remaining.compareTo(BigDecimal.ZERO) > 0) {
            commission = commission.add(remaining.multiply(new BigDecimal("0.15")).setScale(2, RoundingMode.HALF_UP));
        }

        // Withholding Tax
        BigDecimal taxRate = commission.compareTo(new BigDecimal("2500.00")) > 0 
            ? new BigDecimal("0.12") : new BigDecimal("0.05");
        BigDecimal tax = commission.multiply(taxRate).setScale(2, RoundingMode.HALF_UP);

        return commission.subtract(tax).setScale(2, RoundingMode.HALF_UP);
    }
}
EOF
