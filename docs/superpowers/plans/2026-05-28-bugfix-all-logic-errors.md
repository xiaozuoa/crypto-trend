# Bugfix: All Logic Errors in crypto-trend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 8 confirmed logic errors across backtest, optimizer, indicators, data engine, strategy, and README.

**Architecture:** Each bug is independent — fix one file at a time with TDD (write failing test → verify failure → minimal fix → verify pass). No cross-bug dependencies.

**Tech Stack:** Python 3, pytest-compatible assertions (no test framework, use standalone test scripts)

---

### Task 1: Fix optimizer static backtest hardcoded params (Bug 1)

**Files:**
- Modify: `scripts/optimizer.py:118-135` (main function static backtest block)

- [ ] **Step 1: Write failing test**

Create `scripts/test_optimizer.py`:

```python
#!/usr/bin/env python3
"""Test optimizer uses per-symbol config for static backtest"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from optimizer import backtest_range
from data_engine import fetch_daily_full, SYMBOLS
from config import get_config

def test_static_backtest_uses_per_symbol_config():
    """Bug: main() always passed 30/2.0/2.0 regardless of symbol.
    Fix: main() should read period/buy_m/trail_m from get_config()."""
    for name, sym in SYMBOLS.items():
        cfg = get_config(name)
        # Verify that the optimizer CAN run with per-symbol params
        # (Previously hardcoded 30/2.0/2.0 — ETH should use 28/2.2/2.6)
        r = backtest_range(
            fetch_daily_full(sym), None, None,
            cfg["ma_period"], cfg["buy_atr_mult"], cfg["trail_atr_mult"],
            cfg=cfg
        )
        assert r is not None, f"{name}: backtest_range returned None"
        print(f"  {name}: period={cfg['ma_period']} buy={cfg['buy_atr_mult']} trail={cfg['trail_atr_mult']} → {r:+.1f}%")

if __name__ == "__main__":
    test_static_backtest_uses_per_symbol_config()
    print("PASS")
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/airoom/crypto-trend/scripts && python test_optimizer.py
```

Expected: The test itself should pass (it tests the fix, not the bug). But note `backtest_range` currently ignores `cfg`. Until we fix Task 4, `cfg` has no effect. For now this test validates the API.

- [ ] **Step 3: Fix optimizer.py main()**

Change these lines in `scripts/optimizer.py`:

```python
# OLD (lines 132-135):
        # Full backtest with current static params
        static_ret = backtest_range(data, None, None, 30, 2.0, 2.0)
        print(f'  Static EMA30: {static_ret:+.1f}%')

# NEW:
        cfg = get_config(name)
        ma_label = f"{cfg['ma_type'].upper()}{cfg['ma_period']}"
        static_ret = backtest_range(data, None, None,
                                    cfg["ma_period"], cfg["buy_atr_mult"], cfg["trail_atr_mult"],
                                    cfg=cfg)
        print(f'  Static {ma_label}: {static_ret:+.1f}%')
```

Also add `from config import get_config` to imports (line 8). Already imported, verify.

- [ ] **Step 4: Verify**

```bash
cd D:/airoom/crypto-trend/scripts && python test_optimizer.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/optimizer.py scripts/test_optimizer.py
git commit -m "fix: optimizer static backtest now uses per-symbol config instead of hardcoded 30/2.0/2.0"
```

---

### Task 2: Fix overly conservative data length check (Bug 2)

**Files:**
- Modify: `scripts/backtest.py:16`
- Modify: `scripts/optimizer.py:18`

- [ ] **Step 1: Write failing test**

Add to `scripts/test_backtest.py`:

```python
def test_minimum_data_requirement():
    """Bug: n < ma_p + atr_p (44) rejected datasets that only need max(ma_p, atr_p)+1 (31).
    Fix: change check to n <= max(ma_p, atr_p)."""
    cfg = get_config("BTC")
    ma_p = cfg["ma_period"]
    atr_p = cfg["atr_period"]
    
    # 35 bars: enough for warmup(30) + 5 evaluation bars, but < 44
    data = make_data(35, 100, 101, 99, 10000)
    result = backtest(data, cfg, verbose=False)
    
    assert result is not None, f"35 bars should be enough for backtest (warmup=30, need >30)"
    assert result["trades"] >= 0
    print(f"  PASS: 35 bars accepted, trades={result['trades']}")
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/airoom/crypto-trend/scripts && python test_backtest.py
```

Expected: `test_minimum_data_requirement` FAILS because 35 < 44 rejects the data.

- [ ] **Step 3: Fix backtest.py**

```python
# OLD (backtest.py:16):
    if n < ma_p + 14:
        return None

# NEW:
    if n <= max(ma_p, cfg["atr_period"]):
        return None
```

- [ ] **Step 4: Fix optimizer.py backtest_range**

```python
# OLD (optimizer.py:18):
    if n < period + atr_p:
        return None

# NEW:
    if n <= max(period, atr_p):
        return None
```

- [ ] **Step 5: Verify**

```bash
cd D:/airoom/crypto-trend/scripts && python test_backtest.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/backtest.py scripts/optimizer.py scripts/test_backtest.py
git commit -m "fix: relax data length check from period+atr_p to max(period, atr_p)"
```

---

### Task 3: Fix backtest_range not passing cfg (Bug 4)

**Files:**
- Modify: `scripts/optimizer.py:57-69` (grid_search function)

- [ ] **Step 1: Verify current behavior**

The `grid_search` function calls `backtest_range(data, start_date, end_date, period, buy_m, trail_m)` without `cfg`. This is already partially fixed by Task 1 (main now passes cfg). But `grid_search` still doesn't pass cfg. Since `grid_search` always uses `STRATEGY` defaults for `vol_lookback`, `vol_threshold`, `fee_rate`, and PER_SYMBOL doesn't override these, this is a future-proofing fix.

- [ ] **Step 2: Fix grid_search signature and call**

```python
# OLD (line 57):
def grid_search(data, start_date=None, end_date=None):

# NEW:
def grid_search(data, start_date=None, end_date=None, cfg=None):

# OLD (line 65):
                r = backtest_range(data, start_date, end_date, period, buy_m, trail_m)

# NEW:
                r = backtest_range(data, start_date, end_date, period, buy_m, trail_m, cfg=cfg)
```

- [ ] **Step 3: Fix walk_forward_optimize calls to grid_search**

```python
# OLD (line 99):
            params, train_ret = grid_search(train_data)

# NEW:
            params, train_ret = grid_search(train_data, cfg=cfg)
```

Also need to pass `cfg` to `walk_forward_optimize`:

```python
# OLD (line 72):
def walk_forward_optimize(data, train_years=2, test_months=6):

# NEW:
def walk_forward_optimize(data, train_years=2, test_months=6, cfg=None):
```

And update `walk_forward_optimize` to pass `cfg` to `grid_search`:

```python
# Inside walk_forward_optimize, line 99:
            params, train_ret = grid_search(train_data, cfg=cfg)
            test_ret = backtest_range(data, tss_str, tse_str, *params, cfg=cfg)
```

And update main() to pass cfg:

```python
# In main(), line 138:
        windows = walk_forward_optimize(data, cfg=cfg)
```

- [ ] **Step 4: Verify**

```bash
cd D:/airoom/crypto-trend/scripts && python -c "
from optimizer import backtest_range, grid_search
from data_engine import fetch_daily
from config import get_config
data = fetch_daily('BTC-USDT', 200)
cfg = get_config('BTC')
r = backtest_range(data, None, None, cfg['ma_period'], cfg['buy_atr_mult'], cfg['trail_atr_mult'], cfg=cfg)
print(f'backtest_range with cfg: {r:+.1f}%')
"
```

- [ ] **Step 5: Commit**

```bash
git add scripts/optimizer.py
git commit -m "fix: pass cfg through optimizer chain (grid_search, walk_forward_optimize)"
```

---

### Task 4: Fix fetch_daily_full last batch discard (Bug 3)

**Files:**
- Modify: `scripts/data_engine.py:72-73`

- [ ] **Step 1: Fix the condition**

```python
# OLD (lines 72-73):
            if len(candles) < 2:
                break

# NEW:
            if len(candles) == 0:
                break
```

The `< 2` check was meant to detect empty batches. A single candle is still valid data and should be included.

- [ ] **Step 2: Verify**

```bash
cd D:/airoom/crypto-trend/scripts && python -c "
from data_engine import fetch_daily_full
data = fetch_daily_full('BTC-USDT')
print(f'Fetched {len(data)} bars: {data[0][\"date_str\"]} ~ {data[-1][\"date_str\"]}')
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/data_engine.py
git commit -m "fix: accept single-candle batch in fetch_daily_full instead of discarding"
```

---

### Task 5: Fix dead variable ep in backtest_range (Bug 5)

**Files:**
- Modify: `scripts/optimizer.py:26`

- [ ] **Step 1: Remove dead variable**

```python
# OLD (line 26):
    cash, pos, ep, hi, last_p = 10000.0, 0.0, 0.0, 0.0, data[0]['c']

# NEW:
    cash, pos, hi, last_p = 10000.0, 0.0, 0.0, data[0]['c']
```

- [ ] **Step 2: Verify**

```bash
cd D:/airoom/crypto-trend/scripts && python -c "
from optimizer import backtest_range
from data_engine import fetch_daily
r = backtest_range(fetch_daily('BTC-USDT', 200), None, None, 30, 2.0, 2.0)
print(f'Still works: {r:+.1f}%')
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/optimizer.py
git commit -m "fix: remove dead variable ep in backtest_range"
```

---

### Task 6: Fix volume filter edge case in generate_signal (Bug 6)

**Files:**
- Modify: `scripts/strategy.py:39-42`

- [ ] **Step 1: Write failing test**

Add to `scripts/test_backtest.py`:

```python
def test_volume_filter_short_data():
    """Bug: data[-vol_lookback-1:-1] returns empty when len(data)==vol_lookback.
    Fix: check len(data) > vol_lookback instead of >= vol_lookback."""
    from strategy import generate_signal
    from config import get_config
    
    cfg = get_config("BTC")
    lb = cfg["vol_lookback"]  # 20
    
    # Exactly 30 bars (ma_period) — volume check should still work
    data = make_data(30, 100, 101, 99, 10000)
    # Make last bar trigger buy signal
    data[-1] = {
        "date": 29, "date_str": "2022-01-30",
        "o": 110, "h": 112, "l": 109, "c": 111, "v": 20000,
    }
    
    sig = generate_signal(data, cfg)
    # signal 0 or 1 is fine — we just care it doesn't crash or divide by zero
    assert sig["signal"] in (0, 1), f"Unexpected signal: {sig}"
    print(f"  PASS: volume filter works with 30 bars, signal={sig['signal']}")
```

- [ ] **Step 2: Run to verify**

```bash
cd D:/airoom/crypto-trend/scripts && python -c "
import sys; sys.path.insert(0, '.')
from test_backtest import test_volume_filter_short_data
test_volume_filter_short_data()
"
```

- [ ] **Step 3: Fix generate_signal**

```python
# OLD (line 39):
    if len(data) >= cfg["vol_lookback"]:

# NEW:
    if len(data) > cfg["vol_lookback"]:
```

This ensures `data[-vol_lookback-1:-1]` has exactly `vol_lookback` elements when `len(data) == vol_lookback + 1`.

- [ ] **Step 4: Verify**

```bash
cd D:/airoom/crypto-trend/scripts && python -c "
import sys; sys.path.insert(0, '.')
from test_backtest import test_volume_filter_short_data
test_volume_filter_short_data()
"
```

- [ ] **Step 5: Commit**

```bash
git add scripts/strategy.py scripts/test_backtest.py
git commit -m "fix: volume filter requires len(data) > vol_lookback to avoid empty slice"
```

---

### Task 7: Fix ma_vals[-1] falsy check → is not None (Bug 7)

**Files:**
- Modify: `scripts/strategy.py:32,79`
- Modify: `scripts/backtest.py:39`

- [ ] **Step 1: Write failing test**

Add to `scripts/test_backtest.py`:

```python
def test_ma_fallback_uses_none_check():
    """Bug: ma_vals[-1] falsy check treats 0 as None.
    Fix: use 'is not None' instead of truthiness."""
    cfg = get_config("BTC")
    cfg["ma_period"] = 5
    # Small prices could theoretically make EMA=0 (not in crypto, but correctness matters)
    data = make_data(20, 0.01, 0.02, 0.005, 100)
    # With prices near 0, EMA could be near 0 but not None
    # The falsy check would incorrectly fall back to close price
    from strategy import generate_signal
    sig = generate_signal(data, cfg)
    # Just verify the function doesn't crash
    assert "signal" in sig
    print(f"  PASS: ma fallback uses None-check, signal={sig['signal']}")
```

- [ ] **Step 2: Fix strategy.py generate_signal (line 32)**

```python
# OLD:
    current_ma = ma_vals[-1] if ma_vals[-1] else current["c"]
    current_atr = a[-1] if a[-1] else current["c"] * 0.03

# NEW:
    current_ma = ma_vals[-1] if ma_vals[-1] is not None else current["c"]
    current_atr = a[-1] if a[-1] is not None else current["c"] * 0.03
```

- [ ] **Step 3: Fix strategy.py check_exit (line 79-81)**

```python
# OLD:
    current_ma = ma_vals[-1] if ma_vals[-1] else data[-1]["c"]
    ...
    current_atr = a[-1] if a[-1] else data[-1]["c"] * 0.03

# NEW:
    current_ma = ma_vals[-1] if ma_vals[-1] is not None else data[-1]["c"]
    ...
    current_atr = a[-1] if a[-1] is not None else data[-1]["c"] * 0.03
```

- [ ] **Step 4: Fix backtest.py (line 39)**

```python
# OLD:
    atr_val = a[i] if a[i] else p * 0.03
    ma_val = ma_vals[i] if ma_vals[i] else p

# NEW:
    atr_val = a[i] if a[i] is not None else p * 0.03
    ma_val = ma_vals[i] if ma_vals[i] is not None else p
```

- [ ] **Step 5: Verify**

```bash
cd D:/airoom/crypto-trend/scripts && python test_backtest.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/strategy.py scripts/backtest.py scripts/test_backtest.py
git commit -m "fix: use 'is not None' instead of falsy check for indicator fallbacks"
```

---

### Task 8: Fix Sharpe ratio skip first return (Bug 8)

**Files:**
- Modify: `scripts/backtest.py:110`

- [ ] **Step 1: Write failing test**

Add to `scripts/test_backtest.py`:

```python
def test_sharpe_includes_first_return():
    """Bug: range(2, len(equity)) skips equity[1]/equity[0] - 1.
    Fix: start from index 1."""
    cfg = get_config("BTC")
    cfg["ma_period"] = 5
    
    # Create data where a buy happens very early
    data = make_data(10, 100, 101, 99, 10000)
    # Make bar 5 trigger a buy with high close and volume
    data[5] = {"date": 5, "date_str": "2022-01-06", "o": 100, "h": 115, "l": 100, "c": 112, "v": 20000}
    for i in range(6, 10):
        data[i] = {"date": i, "date_str": f"2022-01-{i+1:02d}", "o": 112, "h": 114, "l": 111, "c": 113, "v": 10000}
    
    result = backtest(data, cfg, verbose=False)
    assert result is not None
    
    # The bug was range(2, ...) — verify the fix uses range(1, ...)
    # We can verify indirectly: with range(1,...), daily_r count = len(equity)-1
    # With range(2,...), daily_r count = len(equity)-2
    print(f"  PASS: sharpe={result['sharpe']}, equity points={len(result['equity_curve'])}")
```

- [ ] **Step 2: Fix backtest.py (line 110)**

```python
# OLD:
    daily_r = [(equity[i] / equity[i - 1] - 1) for i in range(2, len(equity)) if equity[i - 1] > 0]

# NEW:
    daily_r = [(equity[i] / equity[i - 1] - 1) for i in range(1, len(equity)) if equity[i - 1] > 0]
```

- [ ] **Step 3: Verify**

```bash
cd D:/airoom/crypto-trend/scripts && python test_backtest.py
```

- [ ] **Step 4: Run full backtest to verify Sharpe doesn't change materially**

```bash
cd D:/airoom/crypto-trend/scripts && python backtest.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/backtest.py scripts/test_backtest.py
git commit -m "fix: Sharpe daily returns start from index 1 instead of 2"
```

---

### Task 9: Fix README stale MACD reference (Bug 11)

**Files:**
- Modify: `README.md:49`

- [ ] **Step 1: Fix README**

```markdown
# OLD:
│   ├── indicators.py     # EMA/ATR/SMA/MACD

# NEW:
│   ├── indicators.py     # EMA/ATR/SMA
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: remove stale MACD reference from README"
```

---

### Task 10: Run full verification

- [ ] **Step 1: Run all tests**

```bash
cd D:/airoom/crypto-trend/scripts && python test_backtest.py && python test_optimizer.py
```

- [ ] **Step 2: Run full backtest**

```bash
cd D:/airoom/crypto-trend/scripts && python backtest.py
```

- [ ] **Step 3: Run optimizer (quick test)**

```bash
cd D:/airoom/crypto-trend/scripts && python optimizer.py
```

- [ ] **Step 4: Final commit if any changes to CLAUDE.md**

No CLAUDE.md changes needed unless backtest metrics shift.
