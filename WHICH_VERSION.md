# Which Version Should I Use?

## Quick Answer

**Use [schwab_trader.py](schwab_trader.py) (the basic version)**

It's sufficient for your alternating order strategy and requires no additional subscriptions.

## The Two Versions

### Version 1: schwab_trader.py (RECOMMENDED)
- ✓ Uses Level 1 market data (best bid/ask)
- ✓ FREE - no subscription needed
- ✓ Simple and reliable
- ✓ Perfect for your use case
- ✓ Polls quotes every 0.5 seconds
- ✓ Works with all stocks and options

**Start here. This is what you need.**

### Version 2: schwab_trader_level2.py (ADVANCED)
- ✓ Uses Level 2 streaming (full order book)
- ⚠ Requires Schwab Level 2 subscription ($0-30/month)
- ✓ Real-time websocket updates
- ✓ Shows multiple price levels
- ✓ Better for high-frequency trading
- ⚠ More complex setup

**Only upgrade if you need full market depth.**

## Why the Basic Version is Enough

Your strategy alternates between:
1. Top of book (BID for buy, ASK for sell)
2. One tick away (BID-1 for buy, ASK+1 for sell)

**Both versions do this identically.**

The only difference:
- **Basic**: Gets top bid/ask every 0.5 seconds (plenty fast)
- **Level 2**: Gets top bid/ask in real-time (<100ms)

For most trading, 0.5 seconds is more than sufficient.

## When to Upgrade to Level 2

Consider Level 2 if:
- [ ] You're trading very volatile stocks (price moves every millisecond)
- [ ] You need to see full order book depth
- [ ] You qualify for FREE Level 2 from Schwab (30+ trades/quarter)
- [ ] You're building high-frequency strategies
- [ ] Basic version isn't responsive enough

Otherwise, stick with the basic version.

## Setup Comparison

### Basic Version Setup:
```bash
pip install schwab-py
python schwab_trader.py
```
Done. No subscription needed.

### Level 2 Version Setup:
```bash
pip install schwab-py
# 1. Enable Level 2 in Schwab account settings
# 2. Accept Level 2 agreement
# 3. Possibly pay $20-30/month (unless you qualify for free)
python schwab_trader_level2.py
```
More steps, potential cost.

## Performance Comparison

### For Your Alternating Order Strategy:

**Basic Version:**
- Order placed at BID-1: $150.00
- (0.5s later) Check market, replace at BID: $150.01
- (0.5s later) Check market, replace at BID-1: $150.00
- **Total time per cycle: ~1 second**

**Level 2 Version:**
- Order placed at BID-1: $150.00
- (real-time) Replace at BID: $150.01
- (real-time) Replace at BID-1: $150.00
- **Total time per cycle: ~0.5 seconds**

**Difference: 0.5 seconds per cycle**

For most trading, this doesn't matter. If the spread is $0.01 and moves every few seconds, both versions perform identically.

## Cost Comparison

| Version | Monthly Cost | When Free |
|---------|-------------|-----------|
| Basic (Level 1) | $0 | Always |
| Level 2 | $0-30 | 30+ trades/quarter OR $250k+ balance |

## My Recommendation

1. **Install the basic version** ([schwab_trader.py](schwab_trader.py))
2. **Test your strategy** with real small orders
3. **Monitor performance** - are you getting fills?
4. **If it works well** (it will), keep using it
5. **If you want more** (unlikely), upgrade later

## Files You Need

### To Use Basic Version (RECOMMENDED):
- [schwab_trader.py](schwab_trader.py) ← Main application
- [test_connection.py](test_connection.py) ← Test your API credentials
- [requirements.txt](requirements.txt) ← Dependencies
- [README.md](README.md) ← Full documentation
- [QUICKSTART.md](QUICKSTART.md) ← Fast setup guide

### To Use Level 2 Version:
- [schwab_trader_level2.py](schwab_trader_level2.py) ← Level 2 enhanced version
- [LEVEL2_GUIDE.md](LEVEL2_GUIDE.md) ← Level 2 setup guide
- Plus all the basic version files

## Bottom Line

**Start with [schwab_trader.py](schwab_trader.py)**

It has everything you need:
- ✓ Symbol entry
- ✓ BUY/SELL selection
- ✓ Quantity input
- ✓ Order book access (top of book)
- ✓ Alternating order strategy (BID ↔ BID-1 or ASK ↔ ASK+1)
- ✓ Fill notifications
- ✓ Exposure tracking
- ✓ Pause/Stop buttons

All working perfectly with Level 1 data.

Save the Level 2 version for later if you ever need it.
