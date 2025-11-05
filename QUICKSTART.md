# Quick Start Guide

## Get Up and Running in 5 Steps

### Step 1: Install Dependencies (2 minutes)

```bash
pip install schwab-py
```

Note: tkinter comes with Python by default on most systems.

### Step 2: Get Schwab API Credentials (5-7 days for approval)

1. Go to https://developer.schwab.com/
2. Create account and login
3. Click "My Apps" → "Create App"
4. Fill in:
   - App Name: (your choice)
   - Callback URL: `https://localhost:8080`
5. Submit and wait for approval (typically 3-7 business days)
6. Once approved, save your API Key and App Secret

### Step 3: Test Your Connection (2 minutes)

Create a `config.json` file:

```json
{
  "api_key": "YOUR_API_KEY",
  "app_secret": "YOUR_APP_SECRET",
  "callback_url": "https://localhost:8080"
}
```

Run the test script:

```bash
python test_connection.py
```

### Step 4: Start the Trading App (30 seconds)

```bash
python schwab_trader.py
```

1. Click Connect
2. If first time, browser opens for authorization
3. You should see "Connected successfully!"

### Step 5: Place Your First Order (1 minute)

1. Enter a Symbol (e.g., AAPL)
2. Choose BUY or SELL
3. Enter Quantity (start with 1)
4. Click Start Order

## What Happens?

For BUY orders:
1. Places order at BID - $0.01 (one tick below best bid)
2. Replaces at BID (top of book)
3. Replaces at BID - $0.01
4. Continues alternating until filled or stopped

For SELL orders:
1. Places order at ASK + $0.01 (one tick above best ask)
2. Replaces at ASK (top of book)
3. Replaces at ASK + $0.01
4. Continues alternating until filled or stopped

## Safety Tips

- Start with 1 share
- Use liquid stocks (tight spreads)
- Watch during market hours
- Test pause/stop buttons first
- Check exposure regularly

See README.md for detailed documentation.
