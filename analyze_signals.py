#!/usr/bin/env python3
"""Analyze why signals aren't generating."""

import re

# Read last part of log file
with open("trading_20250810.log") as f:
    lines = f.readlines()[-1000:]  # Last 1000 lines

# Track signal statistics
rsi_stats = {"oversold_count": 0, "crossed_up": 0, "values": []}
wae_stats = {"positive_explosion": 0, "positive_trend": 0, "both_positive": 0}
price_stats = {"breaks_up": 0, "breaks_down": 0}
pattern_stats = {"ob_found": 0, "fvg_found": 0}
trend_stats = {"long_only": 0, "short_only": 0, "no_trade": 0}

for line in lines:
    # RSI Analysis
    if "RSI:" in line:
        match = re.search(r"current=([\d.]+), oversold=(\w+), crossed_up=(\w+)", line)
        if match:
            rsi_val = float(match.group(1))
            oversold = match.group(2) == "True"
            crossed = match.group(3) == "True"
            rsi_stats["values"].append(rsi_val)
            if oversold:
                rsi_stats["oversold_count"] += 1
            if crossed:
                rsi_stats["crossed_up"] += 1

    # WAE Analysis
    if "WAE:" in line:
        match = re.search(r"explosion=([\d.-]+), trend=([\d.-]+), deadzone=([\d.-]+)", line)
        if match:
            explosion = float(match.group(1))
            trend = float(match.group(2))
            deadzone = float(match.group(3))
            if explosion > deadzone:
                wae_stats["positive_explosion"] += 1
                if trend > 0:
                    wae_stats["positive_trend"] += 1
                    wae_stats["both_positive"] += 1

    # Price Break Analysis
    if "Price:" in line:
        match = re.search(r"close=([\d.]+), prev_high=([\d.]+)", line)
        if match:
            close = float(match.group(1))
            prev_high = float(match.group(2))
            if close > prev_high:
                price_stats["breaks_up"] += 1
        elif "prev_low" in line:
            match = re.search(r"close=([\d.]+), prev_low=([\d.]+)", line)
            if match:
                close = float(match.group(1))
                prev_low = float(match.group(2))
                if close < prev_low:
                    price_stats["breaks_down"] += 1

    # Pattern Analysis
    if "Pattern result:" in line:
        if "OB=True" in line:
            pattern_stats["ob_found"] += 1
        if "FVG=True" in line:
            pattern_stats["fvg_found"] += 1

    # Trade Mode Analysis
    if "TRADE MODE:" in line:
        if "LONG_ONLY" in line:
            trend_stats["long_only"] += 1
        elif "SHORT_ONLY" in line:
            trend_stats["short_only"] += 1
        elif "NO_TRADE" in line:
            trend_stats["no_trade"] += 1

# Calculate statistics
total_signals = len(rsi_stats["values"])
if rsi_stats["values"]:
    avg_rsi = sum(rsi_stats["values"]) / len(rsi_stats["values"])
    min_rsi = min(rsi_stats["values"])
    max_rsi = max(rsi_stats["values"])
else:
    avg_rsi = min_rsi = max_rsi = 0

print("="*60)
print("SIGNAL ANALYSIS REPORT")
print("="*60)

print("\n1. RSI ANALYSIS:")
print(f"   Total signals checked: {total_signals}")
print(f"   Average RSI: {avg_rsi:.2f}")
print(f"   Min RSI: {min_rsi:.2f}, Max RSI: {max_rsi:.2f}")
print(f"   Times oversold (RSI < 30): {rsi_stats['oversold_count']} ({rsi_stats['oversold_count']/max(1,total_signals)*100:.1f}%)")
print(f"   Times crossed up above 40: {rsi_stats['crossed_up']} ({rsi_stats['crossed_up']/max(1,total_signals)*100:.1f}%)")

print("\n2. WAE ANALYSIS:")
print(f"   Explosion above deadzone: {wae_stats['positive_explosion']} times")
print(f"   Positive trend (>0): {wae_stats['positive_trend']} times")
print(f"   Both explosion AND positive trend: {wae_stats['both_positive']} times")

print("\n3. PRICE BREAK ANALYSIS:")
print(f"   Breaks above previous high: {price_stats['breaks_up']} times")
print(f"   Breaks below previous low: {price_stats['breaks_down']} times")

print("\n4. PATTERN ANALYSIS:")
print(f"   Order Blocks found: {pattern_stats['ob_found']} times")
print(f"   FVG patterns found: {pattern_stats['fvg_found']} times")

print("\n5. TREND ALIGNMENT:")
total_modes = sum(trend_stats.values())
if total_modes > 0:
    print(f"   LONG_ONLY mode: {trend_stats['long_only']} ({trend_stats['long_only']/total_modes*100:.1f}%)")
    print(f"   SHORT_ONLY mode: {trend_stats['short_only']} ({trend_stats['short_only']/total_modes*100:.1f}%)")
    print(f"   NO_TRADE mode: {trend_stats['no_trade']} ({trend_stats['no_trade']/total_modes*100:.1f}%)")

print("\n" + "="*60)
print("KEY FINDINGS:")
print("="*60)

issues = []

if rsi_stats["crossed_up"] == 0:
    issues.append("❌ RSI never crosses UP above 40 (needed for long entry)")

if wae_stats["both_positive"] == 0:
    issues.append("❌ WAE never has both positive explosion AND positive trend (needed for long)")

if price_stats["breaks_up"] == 0:
    issues.append("❌ Price never breaks above previous high (needed for long)")

if pattern_stats["ob_found"] == 0 and pattern_stats["fvg_found"] == 0:
    issues.append("❌ No Order Blocks or FVG patterns detected")

if trend_stats["long_only"] == 0 and trend_stats["short_only"] == 0:
    issues.append("❌ Trends never align sufficiently for trading")

for issue in issues:
    print(issue)

print("\nRECOMMENDATIONS:")
print("-" * 40)
print("1. The strategy is TOO RESTRICTIVE - requiring ALL 4 signals is unlikely")
print("2. Consider relaxing to 3 out of 4 signals")
print("3. WAE trend being negative while looking for longs suggests market mismatch")
print("4. Pattern detection (FVG/OB) may need lower thresholds")
print("5. Consider adding SHORT entry logic when bearish conditions present")
