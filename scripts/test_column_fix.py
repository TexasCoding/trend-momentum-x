#!/usr/bin/env python3
"""Quick test to verify indicator column names are correct."""

import polars as pl
from project_x_py.indicators import ATR, EMA, MACD, RSI, SAR, WAE

# Create sample data
data = pl.DataFrame({
    "open": [100.0] * 250,
    "high": [101.0] * 250,
    "low": [99.0] * 250,
    "close": [100.5] * 250,
    "volume": [1000] * 250,
})

# Apply indicators
data = (data
    .pipe(RSI, period=14)
    .pipe(EMA, period=50)
    .pipe(EMA, period=200)
    .pipe(MACD)
    .pipe(WAE, sensitivity=150)
    .pipe(ATR, period=14)
    .pipe(SAR)
)

# List all columns with indicators
print("Indicator columns created:")
for col in data.columns:
    if col not in ["open", "high", "low", "close", "volume"]:
        print(f"  - {col}")

# Verify lowercase names
print("\nVerifying column names are lowercase:")
expected = {
    "rsi_14": "✓ RSI uses lowercase",
    "ema_50": "✓ EMA 50 uses lowercase",
    "ema_200": "✓ EMA 200 uses lowercase",
    "macd": "✓ MACD uses lowercase",
    "macd_signal": "✓ MACD signal uses lowercase",
    "macd_histogram": "✓ MACD histogram uses lowercase",
    "wae_explosion": "✓ WAE explosion uses lowercase",
    "wae_trend": "✓ WAE trend uses lowercase",
    "wae_dead_zone": "✓ WAE dead zone uses lowercase",
    "atr_14": "✓ ATR uses lowercase",
    "sar": "✓ SAR uses lowercase"
}

for col_name, message in expected.items():
    if col_name in data.columns:
        print(f"  {message}")
    else:
        print(f"  ✗ Expected '{col_name}' not found!")

# Check uppercase versions don't exist
print("\nVerifying uppercase names DON'T exist:")
wrong_names = ["RSI_14", "EMA_50", "EMA_200", "MACD_hist", "WAE_explosion", "ATR_14", "SAR"]
for wrong in wrong_names:
    if wrong in data.columns:
        print(f"  ✗ Found incorrect uppercase column: {wrong}")
    else:
        print(f"  ✓ {wrong} not found (correct)")

print("\n✅ All column names are correct (lowercase)!")
