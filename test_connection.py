"""
Simple script to test Schwab API connection
Run this first to verify your credentials work before using the main application
"""

import schwab
import asyncio
import json
import os


async def test_connection():
    """Test connection to Schwab API"""

    # Load config if exists
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
            api_key = config.get('api_key')
            app_secret = config.get('app_secret')
            callback_url = config.get('callback_url', 'https://localhost:8080')
    else:
        # Prompt for credentials
        print("No config.json found. Please enter your credentials:")
        api_key = input("API Key: ").strip()
        app_secret = input("App Secret: ").strip()
        callback_url = input("Callback URL (default: https://localhost:8080): ").strip() or "https://localhost:8080"

    if not api_key or not app_secret:
        print("ERROR: API Key and App Secret are required")
        return

    print("\n" + "="*60)
    print("Testing Schwab API Connection")
    print("="*60 + "\n")

    token_path = "token.json"

    try:
        # Try to authenticate
        print("Attempting authentication...")

        if os.path.exists(token_path):
            print(f"Found existing token file: {token_path}")
            print("Attempting to use existing token...")
            try:
                client = schwab.auth.client_from_token_file(
                    token_path,
                    api_key,
                    app_secret
                )
                print("✓ Successfully loaded existing token")
            except Exception as e:
                print(f"✗ Could not load existing token: {e}")
                print("\nStarting new authentication flow...")
                os.remove(token_path)
                raise
        else:
            print("No existing token found. Starting authentication flow...")
            print("\nA browser window will open. Please:")
            print("1. Log in to your Schwab account")
            print("2. Authorize the application")
            print("3. Copy the URL you're redirected to")
            print("\nPress Enter when ready...")
            input()

            from schwab.auth import client_from_login_flow
            client = await client_from_login_flow(
                api_key,
                app_secret,
                callback_url,
                token_path
            )
            print("✓ Authentication successful!")

        # Test API calls
        print("\nTesting API endpoints...")

        # Get accounts
        print("\n1. Fetching account information...")
        accounts_response = await client.get_accounts()

        if accounts_response.status_code == 200:
            accounts = accounts_response.json()
            print(f"✓ Successfully retrieved {len(accounts)} account(s)")

            for i, account in enumerate(accounts, 1):
                account_info = account['securitiesAccount']
                account_id = account_info.get('accountId', 'N/A')
                account_type = account_info.get('type', 'N/A')
                print(f"\n   Account {i}:")
                print(f"   - ID: {account_id}")
                print(f"   - Type: {account_type}")

                # Get detailed account info with positions
                print(f"\n2. Fetching detailed information for account {i}...")
                account_hash = account_id
                detail_response = await client.get_account(
                    account_hash,
                    fields='positions'
                )

                if detail_response.status_code == 200:
                    detail = detail_response.json()
                    account_data = detail['securitiesAccount']

                    # Display balance info
                    if 'currentBalances' in account_data:
                        balances = account_data['currentBalances']
                        print(f"   ✓ Account Balances:")
                        print(f"     - Buying Power: ${balances.get('buyingPower', 0):,.2f}")
                        print(f"     - Cash Balance: ${balances.get('cashBalance', 0):,.2f}")

                    # Display positions
                    if 'positions' in account_data:
                        positions = account_data['positions']
                        print(f"\n   ✓ Positions: {len(positions)}")
                        for pos in positions[:5]:  # Show first 5
                            symbol = pos['instrument']['symbol']
                            qty = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
                            market_value = pos.get('marketValue', 0)
                            print(f"     - {symbol}: {qty} shares (${market_value:,.2f})")

                        if len(positions) > 5:
                            print(f"     ... and {len(positions) - 5} more")
                else:
                    print(f"   ✗ Failed to get account details: {detail_response.status_code}")

        else:
            print(f"✗ Failed to get accounts: {accounts_response.status_code}")
            print(f"   Response: {accounts_response.text}")
            return

        # Test quote retrieval
        print("\n3. Testing market data retrieval...")
        test_symbol = "AAPL"
        print(f"   Fetching quote for {test_symbol}...")

        quote_response = await client.get_quote(test_symbol)

        if quote_response.status_code == 200:
            quote_data = quote_response.json()
            quote = quote_data.get(test_symbol, {})

            print(f"   ✓ Successfully retrieved quote for {test_symbol}:")
            print(f"     - Last Price: ${quote.get('lastPrice', 0):.2f}")
            print(f"     - Bid: ${quote.get('bidPrice', 0):.2f} x {quote.get('bidSize', 0)}")
            print(f"     - Ask: ${quote.get('askPrice', 0):.2f} x {quote.get('askSize', 0)}")
        else:
            print(f"   ✗ Failed to get quote: {quote_response.status_code}")

        print("\n" + "="*60)
        print("✓ Connection test completed successfully!")
        print("="*60)
        print("\nYour credentials are working correctly.")
        print("You can now use the main trading application.\n")

    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        print("\nTroubleshooting tips:")
        print("1. Verify your API Key and App Secret are correct")
        print("2. Ensure your app is approved on developer.schwab.com")
        print("3. Check your callback URL matches: https://localhost:8080")
        print("4. Make sure you completed the browser authentication")
        return False

    return True


if __name__ == "__main__":
    result = asyncio.run(test_connection())
    if not result:
        exit(1)
