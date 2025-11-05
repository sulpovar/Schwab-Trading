# Schwab Trading Application

A Python-based trading application for Charles Schwab accounts with an alternating order placement strategy. This application automatically places orders that alternate between top-of-book and one tick away from top-of-book until filled or cancelled.

## Features

- **Alternating Order Strategy**: Places orders that alternate between:
  - For BUY: BID (top of book) ↔ BID - 1 tick
  - For SELL: ASK (top of book) ↔ ASK + 1 tick
- **Real-time Order Management**: Automatically replaces orders based on current market conditions
- **Partial Fill Handling**: Continues managing unfilled quantity after partial fills
- **Pause/Resume/Stop Controls**: Full control over order execution
- **Exposure Tracking**: View current positions and market value
- **Simple UI**: Easy-to-use Tkinter interface

## Prerequisites

1. **Schwab Developer Account**
   - Go to [https://developer.schwab.com/](https://developer.schwab.com/)
   - Create an account and register a new application
   - Note your API Key (Client ID) and App Secret

2. **Python 3.8 or higher**

3. **Schwab Brokerage Account**
   - You need an active Schwab brokerage account
   - Account must have API trading permissions enabled

## Installation

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

Note: If you encounter issues with `tkinter-async`, you can remove it from requirements.txt as the core functionality uses threading instead.

### Step 2: Set Up Schwab API Application

1. Visit [https://developer.schwab.com/](https://developer.schwab.com/)
2. Click "My Apps" and create a new app
3. Set the callback URL to: `https://localhost:8080`
4. Wait for Schwab to approve your application (can take several days)
5. Once approved, note your:
   - API Key (Client ID)
   - App Secret

### Step 3: Configure the Application

You have two options:

**Option A: Enter credentials in the UI**
- Launch the application and enter your credentials in the Configuration section

**Option B: Create a config file** (recommended for repeated use)

Create a file named `config.json`:

```json
{
  "api_key": "YOUR_API_KEY_HERE",
  "app_secret": "YOUR_APP_SECRET_HERE",
  "callback_url": "https://localhost:8080"
}
```

## Usage

### Starting the Application

```bash
python schwab_trader.py
```

### First-Time Authentication

1. Click "Connect" button
2. A browser window will open for Schwab authentication
3. Log in to your Schwab account
4. Authorize the application
5. You'll be redirected to `localhost:8080` - copy the full URL
6. The application will save your token for future use (valid for 7 days)

### Placing Orders

1. **Enter Symbol**: Stock ticker (e.g., AAPL) or option symbol
2. **Select Side**: Choose BUY or SELL
3. **Enter Quantity**: Number of shares or contracts (default: 1)
4. **Click "Start Order"**

The application will:
1. Retrieve current order book data
2. Place initial order at BID-1 (for BUY) or ASK+1 (for SELL)
3. Wait for confirmation
4. Replace order at BID (for BUY) or ASK (for SELL)
5. Continue alternating until filled or stopped

### Controls

- **Pause**: Temporarily pause order replacements (order remains active)
- **Resume**: Resume order replacements
- **Stop**: Cancel active order and stop the management loop

### Monitoring

- **Activity Log**: Shows all order activity, fills, and errors
- **Exposure**: Click "Refresh" to see current positions and market values
- **Fill Notifications**: Displays partial and full fills with quantities

## How the Alternating Strategy Works

### For BUY Orders:

```
Initial: Place at BID - 1 tick
Step 1:  Replace at BID (top of book)
Step 2:  Replace at BID - 1 tick
Step 3:  Replace at BID (top of book)
...continues until filled or stopped
```

### For SELL Orders:

```
Initial: Place at ASK + 1 tick
Step 1:  Replace at ASK (top of book)
Step 2:  Replace at ASK + 1 tick
Step 3:  Replace at ASK (top of book)
...continues until filled or stopped
```

### Tick Size Calculation

- Stocks >= $1.00: tick size = $0.01
- Stocks < $1.00 and options: tick size = $0.0001

## Important Notes

### API Rate Limits

- Schwab enforces rate limits on API calls
- The application includes 0.5-second delays between order replacements
- Adjust timing in code if you encounter rate limit errors

### Token Expiration

- Tokens are valid for 7 days
- After expiration, you'll need to re-authenticate
- The application will prompt you when re-authentication is needed

### Market Hours

- Orders can only be placed during market hours
- Extended hours trading may require session type changes in code

### Order Types

- Currently supports LIMIT orders only
- Duration is set to DAY
- Session is set to NORMAL (regular market hours)

### Partial Fills

- Application tracks filled quantity
- Continues managing remaining unfilled quantity
- Shows fill notifications in the activity log

## Customization

### Changing Tick Offset

Edit the `calculate_next_price` method in [schwab_trader.py](schwab_trader.py):

```python
# For BUY orders, change offset from 1 tick to 2 ticks:
price = book['bid'] - (2 * tick_size)

# For SELL orders, change offset from 1 tick to 2 ticks:
price = book['ask'] + (2 * tick_size)
```

### Adjusting Replacement Timing

Change the sleep duration in the `order_management_loop` method:

```python
# Current: 0.5 seconds between replacements
await asyncio.sleep(0.5)

# Change to 1 second:
await asyncio.sleep(1.0)
```

### Supporting Options

The code includes basic option support. To use options:

1. Enter the full option symbol (e.g., `AAPL250117C00150000`)
2. Modify the `place_order` method to detect option symbols:

```python
# In place_order method, change:
'assetType': 'EQUITY'

# To:
'assetType': 'OPTION' if self._is_option_symbol(symbol) else 'EQUITY'
```

3. Add option symbol detection:

```python
def _is_option_symbol(self, symbol):
    """Check if symbol is an option"""
    # Options typically have 6 digits for expiration date
    import re
    return bool(re.search(r'\d{6}[CP]\d{8}', symbol))
```

## Troubleshooting

### "Failed to connect to Schwab API"

- Verify your API Key and App Secret are correct
- Ensure your application is approved by Schwab
- Check that your callback URL matches exactly: `https://localhost:8080`

### "Could not retrieve market data"

- Verify the symbol is correct
- Check that markets are open
- Ensure you have market data permissions for the symbol

### "Failed to place initial order"

- Check your account has sufficient buying power
- Verify the symbol exists and is tradeable
- Ensure your account has trading permissions

### Browser doesn't open for authentication

- Manually copy the authorization URL from the console
- Paste it into your browser
- Complete authentication and copy the redirect URL

### Token expired

- Delete the `token.json` file
- Click "Connect" again to re-authenticate

## Security Best Practices

1. **Never share your API Key or App Secret**
2. **Do not commit `config.json` or `token.json` to version control**
3. **Use strong Schwab account password and 2FA**
4. **Review order activity regularly**
5. **Test with small quantities first**

## Disclaimer

This application is for educational purposes. Use at your own risk. The author is not responsible for any trading losses. Always test with paper trading or small quantities before using with real money.

## API Documentation

- [Schwab Developer Portal](https://developer.schwab.com/)
- [schwab-py Documentation](https://schwab-py.readthedocs.io/)

## Support

For issues with:
- **This application**: Check the activity log for error messages
- **Schwab API**: Contact Schwab Developer Support
- **schwab-py library**: Visit the [GitHub repository](https://github.com/alexgolec/schwab-py)

## Version History

- **v1.0** (2025-01-05): Initial release
  - Alternating order strategy
  - Basic UI with pause/stop controls
  - Exposure tracking
  - Partial fill support
