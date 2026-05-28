# Fix B1+C1: Strategy Design & Backtest Accuracy

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix trail_stop capping (B1) and backtest entry price look-ahead bias (C1)

**Architecture:** Two independent fixes. B1 caps trail_stop in check_exit to never exceed entry_price. C1 shifts backtest entry from signal-bar-close to next-bar-open, matching real execution timing. Existing tests adjusted for the 1-bar entry shift.

**Tech Stack:** Python 3 + standalone test assertions

---

### Task 1: Fix B1 — trail_stop cap at entry_price

**Files:**
- Modify: `scripts/strategy.py:90`
- Modify: `scripts/test_backtest.py`

- [ ] **Step 1: Write failing test**

Add to `scripts/test_backtest.py` before `if __name__ == "__main__":`:

```python
def test_trail_stop_never_above_entry():
    """B1: trail_stop = highest - trail_atr*ATR can exceed entry_price
    on wide-range entry days (high >> close), causing profitable exits.
    Fix: cap trail_stop at entry_price * 0.995."""
    cfg = get_config("BTC")
    cfg["ma_period"] = 5
    cfg["atr_period"] = 5

    # Flat data, then wide-range entry with high >> close
    data = make_data(30, 100, 101, 99, 10000)
    data.append({"date": 30, "date_str": "2022-01-31", "o": 119, "h": 140, "l": 118, "c": 120, "v": 30000})
    data.append({"date": 31, "date_str": "2022-02-01", "o": 120, "h": 123, "l": 119, "c": 122, "v": 10000})

    ce = check_exit(data, 120, cfg, entry_date="2022-01-31", stored_highest=140)
    # Before fix: trail_stop = 140 - 2*ATR(~8) = ~124 > entry(120)
    # After fix: trail_stop <= 120 * 0.995 = 119.4
    assert ce.get("trail_stop", 999) <= 120 * 0.995 + 0.01, \
        f"trail_stop ({ce.get('trail_stop')}) must not exceed entry_price ({120})"
    print(f"  PASS: trail_stop={ce['trail_stop']:.1f} capped at entry=120")
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/airoom/crypto-trend/scripts && python -c "
import sys; sys.path.insert(0, '.')
from test_backtest import test_trail_stop_never_above_entry
test_trail_stop_never_above_entry()
"
```

Expected: FAIL — trail_stop exceeds entry_price

- [ ] **Step 3: Fix check_exit**

In `scripts/strategy.py`, after the trail_stop calculation line (~line 90), add cap:

```python
    trail_stop = highest - cfg["trail_atr_mult"] * current_atr
    if trail_stop > entry_price * 0.995:
        trail_stop = entry_price * 0.995
```

- [ ] **Step 4: Verify pass**

```bash
cd D:/airoom/crypto-trend/scripts && python -c "
import sys; sys.path.insert(0, '.')
from test_backtest import test_trail_stop_never_above_entry
test_trail_stop_never_above_entry()
"
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
cd D:/airoom/crypto-trend/scripts && python test_backtest.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/strategy.py scripts/test_backtest.py
git commit -m "fix(B1): cap trail_stop at entry_price to prevent premature profitable exits on wide-range entry days"
```

---

### Task 2: Fix C1 — backtest entry at next bar open

**Files:**
- Modify: `scripts/backtest.py:68-79` (entry block)
- Modify: `scripts/backtest.py:86-97` (force-close entry_date ref)
- Modify: `scripts/test_backtest.py` (add test, adjust existing tests for 1-bar shift)

- [ ] **Step 1: Write failing test**

Add to `scripts/test_backtest.py`:

```python
def test_backtest_entry_at_next_open():
    """C1: backtest enters at signal bar close (look-ahead bias).
    Live: signal at close, execute NEXT day. Fix: entry at next bar open."""
    cfg = get_config("BTC")
    cfg["ma_period"] = 5
    cfg["atr_period"] = 5

    # Signal bar close=122, next bar open=124 (gap up before execution)
    data = make_data(30, 100, 101, 99, 10000)
    data.append({"date": 30, "date_str": "2022-01-31", "o": 100, "h": 125, "l": 100, "c": 122, "v": 30000})
    data.append({"date": 31, "date_str": "2022-02-01", "o": 124, "h": 126, "l": 122, "c": 125, "v": 10000})
    data.append({"date": 32, "date_str": "2022-02-02", "o": 125, "h": 127, "l": 100, "c": 103, "v": 10000})

    r = backtest(data, cfg, verbose=False)
    assert r["trades"] >= 1, f"should have trade, got {r['trades']}"
    t = r["trades_list"][0]
    # Before fix: entry_price = 122 (signal bar close, look-ahead)
    # After fix: entry_price = 124 (next bar open, realistic)
    assert t["entry_price"] == 124, \
        f"entry at next open=124, got {t['entry_price']}"
    print(f"  PASS: entry={t['entry_price']} (next open, not signal close 122)")
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/airoom/crypto-trend/scripts && python -c "
import sys; sys.path.insert(0, '.')
from test_backtest import test_backtest_entry_at_next_open
test_backtest_entry_at_next_open()
"
```

Expected: FAIL — entry_price=122 (old behavior)

- [ ] **Step 3: Fix backtest.py entry block**

Replace the entry block in `scripts/backtest.py` (lines ~68-79):

OLD:
```python
        elif p > ma_val + cfg["buy_atr_mult"] * atr_val:
            vol_ok = True
            if i >= max(warmup, cfg["vol_lookback"]):
                avg_vol = sum(d["v"] for d in data[i - cfg["vol_lookback"]:i]) / cfg["vol_lookback"]
                if data[i]["v"] < avg_vol * cfg["vol_threshold"]:
                    vol_ok = False
            if vol_ok:
                position = (cash * fee_mult) / p
                entry_price = p
                highest = data[i]["h"]
                entry_date = data[i]["date_str"]
                cash = 0
```

NEW:
```python
        elif p > ma_val + cfg["buy_atr_mult"] * atr_val:
            vol_ok = True
            if i >= max(warmup, cfg["vol_lookback"]):
                avg_vol = sum(d["v"] for d in data[i - cfg["vol_lookback"]:i]) / cfg["vol_lookback"]
                if data[i]["v"] < avg_vol * cfg["vol_threshold"]:
                    vol_ok = False
            if vol_ok and i + 1 < n:
                # Enter at next bar open (realistic: signal at close, execute next day)
                entry_price = data[i + 1]["o"]
                position = (cash * fee_mult) / entry_price
                highest = data[i + 1]["h"]
                entry_date = data[i + 1]["date_str"]
                cash = 0
```

- [ ] **Step 4: Adjust existing tests for 1-bar entry shift**

Tests `test_highest_tracks_entry_day_high` and `test_equity_no_double_fee` use specific entry bars. After the C1 fix, entry shifts forward by 1 bar. Adjust test data to ensure entry still triggers.

For `test_highest_tracks_entry_day_high`: the entry bar's next bar open must still allow the exit scenario. Add one more bar after the exit bar to provide the "next open" for the exit bar.

For `test_equity_no_double_fee`: same adjustment — add one bar after the entry trigger.

For `test_signal_trail_stop_uses_high`: this tests `generate_signal` (not backtest), no adjustment needed.

For `test_backtest_warmup_uses_max_periods`: adjust data to account for 1-bar shift.

For `test_volume_filter_with_low_ma_period`: add one bar after entry trigger.

- [ ] **Step 5: Verify all tests pass**

```bash
cd D:/airoom/crypto-trend/scripts && python test_backtest.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/backtest.py scripts/test_backtest.py
git commit -m "fix(C1): backtest entry at next bar open instead of signal bar close, eliminating look-ahead bias"
```

---

### Task 3: Run full verification

- [ ] **Step 1: Full test suite**

```bash
cd D:/airoom/crypto-trend/scripts && python test_backtest.py
```

- [ ] **Step 2: Verify backtest metrics still reasonable**

```bash
cd D:/airoom/crypto-trend/scripts && timeout 30 python backtest.py || true
```

- [ ] **Step 3: Final commit if needed**

```bash
# Update CLAUDE.md with new improvements
```
