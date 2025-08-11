#!/usr/bin/env python3
"""Test to verify FVG and ORDERBLOCK column names without TradingSuite."""

import polars as pl
from project_x_py.indicators import FVG, ORDERBLOCK

# Create sample OHLCV data
data = pl.DataFrame({
    "open": [100.0, 101.0, 102.0, 101.5, 103.0] * 50,
    "high": [101.0, 102.5, 103.0, 102.0, 104.0] * 50,
    "low": [99.5, 100.5, 101.5, 100.0, 102.5] * 50,
    "close": [100.5, 102.0, 101.8, 102.5, 103.5] * 50,
    "volume": [1000, 1200, 1500, 900, 1100] * 50,
})

print("Original columns:", data.columns)
print()

# Apply FVG
print("Testing FVG indicator...")
data_with_fvg = data.pipe(FVG, min_gap_size=0.001, check_mitigation=True)
fvg_columns = [col for col in data_with_fvg.columns if 'fvg' in col.lower() or 'FVG' in col]
print(f"FVG columns added: {fvg_columns}")
print()

# Apply ORDERBLOCK
print("Testing ORDERBLOCK indicator...")
data_with_ob = data.pipe(ORDERBLOCK, min_volume_percentile=70)
ob_columns = [col for col in data_with_ob.columns if 'ob' in col.lower() or 'ORDERBLOCK' in col or 'order' in col.lower()]
print(f"ORDERBLOCK columns added: {ob_columns}")
print()

# Apply both
print("Testing both indicators together...")
data_with_both = (data
                  .pipe(FVG, min_gap_size=0.001, check_mitigation=True)
                  .pipe(ORDERBLOCK, min_volume_percentile=70))

print("All pattern-related columns after applying both indicators:")
for col in data_with_both.columns:
    if 'fvg' in col.lower() or 'ob' in col.lower() or 'order' in col.lower():
        print(f"  - {col}")
print()

# Check last row values
last_row = data_with_both.tail(1)
print("Last row pattern-related values:")
for col in last_row.columns:
    if 'fvg' in col.lower() or 'ob' in col.lower() or 'order' in col.lower():
        value = last_row[col][0]
        print(f"  {col}: {value}")
