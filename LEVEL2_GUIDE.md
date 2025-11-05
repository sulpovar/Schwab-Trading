# Level 2 Order Book Support Guide

## Summary

**YES, Schwab DOES provide Level 2 order book data through their API!**

The Schwab Trader API includes **streaming websockets** that provide real-time Level 2 market depth for:
- ✓ NYSE-listed stocks
- ✓ NASDAQ-listed securities
- ✓ Options contracts

## What You Get with Level 2

### Level 1 (Basic - Always Available):
```
Best Bid: $150.01 x 500
Best Ask: $150.02 x 300
```

### Level 2 (Full Depth - Requires Subscription):
```
BID SIDE:              ASK SIDE:
$150.01 x 500         $150.02 x 300
$150.00 x 1,200       $150.03 x 800
$149.99 x 750         $150.04 x 600
$149.98 x 900         $150.05 x 450
$149.97 x 1,100       $150.06 x 550
...                   ...
```

## Two Versions Available

### 1. Basic Version ([schwab_trader.py](schwab_trader.py))
- Uses Level 1 data (top of book only)
- No additional subscription needed
- Sufficient for the alternating order strategy
- **Recommended for most users**

### 2. Level 2 Version ([schwab_trader_level2.py](schwab_trader_level2.py))
- Uses streaming Level 2 order book data
- Shows full market depth
- Requires Level 2 subscription from Schwab
- Better for high-frequency or complex strategies

## Requirements for Level 2

### 1. Schwab Level 2 Subscription

Level 2 data requires a subscription from Schwab:

**Cost**: Usually $0 (FREE) if you meet requirements
- Make 30+ stock or options trades per quarter, OR
- Maintain $250k+ in Schwab accounts

**Otherwise**: Approximately $20-30/month

Check your eligibility at: [Schwab Level 2 Quotes](https://www.brokerage-review.com/expert/level2/charles-schwab-level-2-quotes.aspx)

### 2. Enable in Your Account

1. Log in to Schwab.com
2. Go to Trading → Trading Preferences
3. Enable "Level II Quotes"
4. Accept the agreement

### 3. API Access

Once enabled in your account, the API automatically has access through the streaming interface.

## How to Use Level 2 Version

### Installation (Same as Basic)

```bash
pip install schwab-py
```

### Usage

The Level 2 version works exactly like the basic version, but automatically:
1. Connects to streaming websockets
2. Subscribes to Level 2 data for your symbol
3. Uses real-time order book updates
4. Falls back to Level 1 if streaming unavailable

```python
# In your code, use SchwabTraderLevel2 instead of SchwabTrader
from schwab_trader_level2 import SchwabTraderLevel2

trader = SchwabTraderLevel2(api_key, app_secret, callback_url)
await trader.authenticate()

# Everything else is the same
trader.start_order("AAPL", "BUY", 100, log_callback)
```

## Benefits of Level 2 for Your Strategy

### For the Alternating Order Strategy:

**Basic Version (Level 1):**
- Gets best bid/ask every 0.5 seconds
- Places order at BID-1 or ASK+1
- Works perfectly fine

**Level 2 Version:**
- Receives real-time updates (milliseconds)
- Sees full book depth
- Can detect when best bid/ask changes instantly
- More responsive to market movements

### When Level 2 Helps Most:

1. **Fast-moving stocks** - Price changes happen quickly
2. **Thin order books** - See all available liquidity
3. **Large orders** - Understand depth before placing
4. **High-frequency strategies** - Need immediate updates

### When Level 1 is Fine:

1. **Liquid stocks** (AAPL, MSFT, SPY) - Tight spreads, stable quotes
2. **Small orders** - 1-100 shares typically fill at displayed prices
3. **Slower replacement timing** - If using 1+ second delays
4. **Learning/testing** - No need for premium data initially

## Technical Details

### Streaming API Access

The Level 2 version uses Schwab's websockets streaming API:

```python
# Automatic in schwab_trader_level2.py:
stream_client = StreamClient(client, account_id=account_hash)

# Subscribe to NYSE book
await stream_client.nyse_book_subs(['AAPL'])

# Subscribe to NASDAQ book
await stream_client.nasdaq_book_subs(['AAPL'])

# Subscribe to options book
await stream_client.options_book_subs(['AAPL250117C00150000'])
```

### Data Structure

Level 2 book data arrives as:

```python
{
    'content': [{
        'key': 'AAPL',
        'BOOK_BID': [
            {'BID_PRICE': 150.01, 'TOTAL_VOLUME': 500},
            {'BID_PRICE': 150.00, 'TOTAL_VOLUME': 1200},
            # ... more levels
        ],
        'BOOK_ASK': [
            {'ASK_PRICE': 150.02, 'TOTAL_VOLUME': 300},
            {'ASK_PRICE': 150.03, 'TOTAL_VOLUME': 800},
            # ... more levels
        ]
    }]
}
```

### Automatic Fallback

If Level 2 streaming fails to connect or no data is received:
- Application automatically falls back to Level 1 quotes
- Your strategy continues working
- Log shows which data source is being used

## Comparison Chart

| Feature | Basic (Level 1) | Level 2 Streaming |
|---------|----------------|-------------------|
| Top of book bid/ask | ✓ | ✓ |
| Full order book depth | ✗ | ✓ (5-10 levels) |
| Update speed | ~0.5s polling | Real-time (<100ms) |
| Subscription cost | FREE | $0-30/month |
| Setup complexity | Simple | Moderate |
| Data volume | Low | High |
| Best for | Most traders | Active/pro traders |

## My Recommendation

### Start with Basic Version ([schwab_trader.py](schwab_trader.py))

**Reasons:**
1. Your alternating strategy only needs top of book (which Level 1 provides)
2. Polling every 0.5 seconds is fast enough for most scenarios
3. No additional subscription cost
4. Simpler to test and debug
5. Works identically for the user

### Upgrade to Level 2 Later If:
1. You're trading very fast-moving stocks
2. You notice your orders aren't getting filled efficiently
3. You want to see full market depth
4. You qualify for free Level 2 (30+ trades/quarter)
5. You're developing high-frequency strategies

## Testing Level 2 Access

Use this script to test if you have Level 2 access:

```python
import asyncio
from schwab_trader_level2 import SchwabTraderLevel2

async def test_level2():
    trader = SchwabTraderLevel2(api_key, app_secret, callback_url)
    await trader.authenticate()

    if trader.use_level2:
        print("✓ Level 2 streaming available!")
        await trader.subscribe_level2("AAPL")
        await asyncio.sleep(2)  # Wait for data
        print(trader.get_book_depth_display("AAPL"))
    else:
        print("✗ Level 2 not available - using Level 1 fallback")

asyncio.run(test_level2())
```

## Troubleshooting Level 2

### "Level 2 data not available"
- Verify you have Level 2 enabled in your Schwab account
- Check you accepted the Level 2 agreement
- Ensure your API app has market data permissions

### "Could not initialize streaming"
- Check your token is valid
- Verify account has streaming permissions
- Try refreshing your authentication token

### "No Level 2 data for symbol"
- Symbol may not be available for streaming
- Try a major stock like AAPL, MSFT, or SPY
- Some symbols only stream on one exchange

## Conclusion

**Your Answer:** Yes, Schwab provides Level 2 order book data through their streaming API.

**What You Should Do:**
1. Start with the basic version ([schwab_trader.py](schwab_trader.py)) - it's sufficient
2. Test your strategy with Level 1 data
3. If needed later, upgrade to Level 2 version
4. Check if you qualify for free Level 2 from Schwab

The basic version will work great for your use case!
