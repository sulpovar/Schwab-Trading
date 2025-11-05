"""
Schwab Trading Application with Level 2 Order Book Support
Enhanced version with streaming Level 2 market depth data
"""

import schwab
from schwab.streaming import StreamClient
import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from threading import Thread
import json
from datetime import datetime
from enum import Enum
from collections import defaultdict


class OrderState(Enum):
    """Order placement states for alternating strategy"""
    AT_BOOK = "at_book"  # Order at top of book (BID for buy, ASK for sell)
    OFFSET_TICK = "offset_tick"  # Order offset by 1 tick (BID-1 for buy, ASK+1 for sell)


class Level2BookHandler:
    """Handler for Level 2 order book data"""

    def __init__(self):
        self.books = defaultdict(lambda: {'bids': {}, 'asks': {}})
        self.last_update = {}

    def handle_nyse_book(self, data):
        """Handle NYSE book updates"""
        self._process_book_data(data, 'NYSE')

    def handle_nasdaq_book(self, data):
        """Handle NASDAQ book updates"""
        self._process_book_data(data, 'NASDAQ')

    def handle_options_book(self, data):
        """Handle Options book updates"""
        self._process_book_data(data, 'OPTIONS')

    def _process_book_data(self, data, exchange):
        """Process incoming book data"""
        try:
            if 'content' in data:
                for item in data['content']:
                    symbol = item.get('key', '').upper()

                    if symbol:
                        # Process bids
                        if 'BOOK_BID' in item:
                            bids = item['BOOK_BID']
                            self.books[symbol]['bids'] = {
                                float(bid.get('BID_PRICE', 0)): int(bid.get('TOTAL_VOLUME', 0))
                                for bid in bids if 'BID_PRICE' in bid
                            }

                        # Process asks
                        if 'BOOK_ASK' in item:
                            asks = item['BOOK_ASK']
                            self.books[symbol]['asks'] = {
                                float(ask.get('ASK_PRICE', 0)): int(ask.get('TOTAL_VOLUME', 0))
                                for ask in asks if 'ASK_PRICE' in ask
                            }

                        self.last_update[symbol] = datetime.now()
        except Exception as e:
            print(f"Error processing book data: {e}")

    def get_top_of_book(self, symbol):
        """
        Get best bid/ask from Level 2 data

        Returns:
            dict: {'bid': price, 'ask': price, 'bid_size': size, 'ask_size': size}
        """
        symbol = symbol.upper()
        book = self.books.get(symbol)

        if not book or not book['bids'] or not book['asks']:
            return None

        # Get best bid (highest price)
        best_bid_price = max(book['bids'].keys()) if book['bids'] else 0
        best_bid_size = book['bids'].get(best_bid_price, 0)

        # Get best ask (lowest price)
        best_ask_price = min(book['asks'].keys()) if book['asks'] else 0
        best_ask_size = book['asks'].get(best_ask_price, 0)

        return {
            'bid': best_bid_price,
            'ask': best_ask_price,
            'bid_size': best_bid_size,
            'ask_size': best_ask_size
        }

    def get_book_depth(self, symbol, levels=5):
        """
        Get multiple levels of order book

        Args:
            symbol: Stock symbol
            levels: Number of price levels to return

        Returns:
            dict: {'bids': [(price, size), ...], 'asks': [(price, size), ...]}
        """
        symbol = symbol.upper()
        book = self.books.get(symbol)

        if not book:
            return {'bids': [], 'asks': []}

        # Sort bids descending (highest first)
        sorted_bids = sorted(book['bids'].items(), key=lambda x: x[0], reverse=True)[:levels]

        # Sort asks ascending (lowest first)
        sorted_asks = sorted(book['asks'].items(), key=lambda x: x[0])[:levels]

        return {
            'bids': sorted_bids,
            'asks': sorted_asks
        }


class SchwabTraderLevel2:
    """Enhanced trader with Level 2 support"""

    def __init__(self, api_key, app_secret, callback_url, token_path="token.json"):
        """
        Initialize Schwab trader with Level 2 support

        Args:
            api_key: Schwab API key from developer portal
            app_secret: Schwab app secret
            callback_url: OAuth callback URL (usually https://localhost:8080)
            token_path: Path to store authentication token
        """
        self.api_key = api_key
        self.app_secret = app_secret
        self.callback_url = callback_url
        self.token_path = token_path
        self.client = None
        self.stream_client = None
        self.account_hash = None

        # Level 2 data handler
        self.book_handler = Level2BookHandler()
        self.use_level2 = False
        self.subscribed_symbols = set()

        # Order tracking
        self.current_order_id = None
        self.current_state = OrderState.OFFSET_TICK
        self.is_running = False
        self.is_paused = False
        self.order_loop_task = None

        # Position tracking
        self.symbol = None
        self.side = None  # 'BUY' or 'SELL'
        self.quantity = 0
        self.filled_quantity = 0
        self.remaining_quantity = 0

    async def authenticate(self):
        """Authenticate with Schwab API"""
        try:
            # Try to load existing token
            self.client = schwab.auth.client_from_token_file(
                self.token_path,
                self.api_key,
                self.app_secret
            )
        except FileNotFoundError:
            # Need to perform initial authentication
            from schwab.auth import client_from_login_flow
            self.client = await client_from_login_flow(
                self.api_key,
                self.app_secret,
                self.callback_url,
                self.token_path
            )

        # Get account information
        accounts_response = await self.client.get_accounts()
        if accounts_response.status_code == 200:
            accounts = accounts_response.json()
            if accounts:
                # Use first account
                self.account_hash = accounts[0]['securitiesAccount']['accountId']

                # Initialize streaming client
                await self.init_streaming()

                return True
        return False

    async def init_streaming(self):
        """Initialize streaming client for Level 2 data"""
        try:
            self.stream_client = StreamClient(self.client, account_id=self.account_hash)

            # Set up book handlers
            self.stream_client.add_nyse_book_handler(self.book_handler.handle_nyse_book)
            self.stream_client.add_nasdaq_book_handler(self.book_handler.handle_nasdaq_book)
            self.stream_client.add_options_book_handler(self.book_handler.handle_options_book)

            # Start stream client
            await self.stream_client.login()

            self.use_level2 = True
            return True
        except Exception as e:
            print(f"Warning: Could not initialize streaming (Level 2 unavailable): {e}")
            self.use_level2 = False
            return False

    async def subscribe_level2(self, symbol):
        """
        Subscribe to Level 2 data for a symbol

        Args:
            symbol: Stock or option symbol
        """
        if not self.use_level2 or not self.stream_client:
            return False

        symbol = symbol.upper()

        if symbol in self.subscribed_symbols:
            return True

        try:
            # Determine exchange (simplified - could be enhanced)
            # Most stocks trade on both NYSE and NASDAQ
            # Subscribe to both for better coverage

            if self._is_option_symbol(symbol):
                await self.stream_client.options_book_subs([symbol])
            else:
                # Subscribe to both exchanges for stocks
                try:
                    await self.stream_client.nyse_book_subs([symbol])
                except:
                    pass  # May not be NYSE listed

                try:
                    await self.stream_client.nasdaq_book_subs([symbol])
                except:
                    pass  # May not be NASDAQ listed

            self.subscribed_symbols.add(symbol)
            return True
        except Exception as e:
            print(f"Error subscribing to Level 2 for {symbol}: {e}")
            return False

    def _is_option_symbol(self, symbol):
        """Check if symbol is an option"""
        import re
        # Options have format: SYMBOL + YYMMDD + C/P + Strike price
        return bool(re.search(r'\d{6}[CP]\d{8}', symbol))

    async def get_quote(self, symbol):
        """
        Get current quote for symbol (Level 1 fallback)

        Args:
            symbol: Stock or option symbol

        Returns:
            dict: Quote data including bid/ask
        """
        response = await self.client.get_quote(symbol)
        if response.status_code == 200:
            return response.json()[symbol]
        return None

    async def get_order_book(self, symbol):
        """
        Get order book data (Level 2 if available, otherwise Level 1)

        Args:
            symbol: Stock or option symbol

        Returns:
            dict: Order book with bids and asks
        """
        # Try Level 2 first
        if self.use_level2:
            top_of_book = self.book_handler.get_top_of_book(symbol)
            if top_of_book:
                return {
                    'bid': top_of_book['bid'],
                    'ask': top_of_book['ask'],
                    'bid_size': top_of_book['bid_size'],
                    'ask_size': top_of_book['ask_size'],
                    'tick_size': self._calculate_tick_size(top_of_book['bid']),
                    'source': 'Level 2'
                }

        # Fallback to Level 1
        quote = await self.get_quote(symbol)
        if quote:
            return {
                'bid': quote.get('bidPrice', 0),
                'ask': quote.get('askPrice', 0),
                'bid_size': quote.get('bidSize', 0),
                'ask_size': quote.get('askSize', 0),
                'tick_size': self._calculate_tick_size(quote.get('bidPrice', 0)),
                'source': 'Level 1'
            }
        return None

    def _calculate_tick_size(self, price):
        """Calculate tick size based on price"""
        if price >= 1.00:
            return 0.01
        else:
            return 0.0001

    async def place_order(self, symbol, side, quantity, price, order_type='LIMIT'):
        """Place an order"""
        order_spec = {
            'orderType': order_type,
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [
                {
                    'instruction': side,
                    'quantity': quantity,
                    'instrument': {
                        'symbol': symbol,
                        'assetType': 'OPTION' if self._is_option_symbol(symbol) else 'EQUITY'
                    }
                }
            ]
        }

        if order_type == 'LIMIT':
            order_spec['price'] = round(price, 4)

        response = await self.client.place_order(self.account_hash, order_spec)

        if response.status_code == 201:
            location = response.headers.get('Location', '')
            order_id = location.split('/')[-1] if location else None
            return order_id

        return None

    async def cancel_order(self, order_id):
        """Cancel an order"""
        response = await self.client.cancel_order(order_id, self.account_hash)
        return response.status_code == 200

    async def replace_order(self, old_order_id, symbol, side, quantity, new_price):
        """Replace an existing order (cancel and replace)"""
        await self.cancel_order(old_order_id)
        new_order_id = await self.place_order(symbol, side, quantity, new_price)
        return new_order_id

    async def get_order_status(self, order_id):
        """Get status of an order"""
        response = await self.client.get_order(order_id, self.account_hash)
        if response.status_code == 200:
            return response.json()
        return None

    async def calculate_next_price(self, symbol, side, state):
        """Calculate next price based on strategy state"""
        book = await self.get_order_book(symbol)
        if not book:
            return None, state, 'Unknown'

        tick_size = book['tick_size']
        source = book.get('source', 'Unknown')

        if side == 'BUY':
            if state == OrderState.AT_BOOK:
                price = book['bid']
                next_state = OrderState.OFFSET_TICK
            else:
                price = book['bid'] - tick_size
                next_state = OrderState.AT_BOOK
        else:  # SELL
            if state == OrderState.AT_BOOK:
                price = book['ask']
                next_state = OrderState.OFFSET_TICK
            else:
                price = book['ask'] + tick_size
                next_state = OrderState.AT_BOOK

        return round(price, 4), next_state, source

    async def order_management_loop(self, log_callback):
        """Main order management loop with alternating strategy"""
        self.is_running = True
        self.current_state = OrderState.OFFSET_TICK

        try:
            # Subscribe to Level 2 for this symbol
            if self.use_level2:
                subscribed = await self.subscribe_level2(self.symbol)
                if subscribed:
                    log_callback(f"Subscribed to Level 2 data for {self.symbol}")
                    # Give it a moment to receive initial data
                    await asyncio.sleep(1.0)

            # Place initial order
            initial_price, next_state, source = await self.calculate_next_price(
                self.symbol, self.side, self.current_state
            )

            if initial_price is None:
                log_callback("ERROR: Could not retrieve market data")
                return

            log_callback(f"Using {source} market data")
            log_callback(f"Placing initial order: {self.side} {self.quantity} {self.symbol} @ {initial_price}")

            self.current_order_id = await self.place_order(
                self.symbol, self.side, self.remaining_quantity, initial_price
            )

            if not self.current_order_id:
                log_callback("ERROR: Failed to place initial order")
                return

            log_callback(f"Order placed: ID {self.current_order_id}")
            self.current_state = next_state

            await asyncio.sleep(0.5)

            # Start alternating loop
            while self.is_running and self.remaining_quantity > 0:
                if self.is_paused:
                    await asyncio.sleep(0.5)
                    continue

                # Check order status
                order_status = await self.get_order_status(self.current_order_id)

                if order_status:
                    status = order_status.get('status', '')
                    filled_qty = order_status.get('filledQuantity', 0)

                    if filled_qty > self.filled_quantity:
                        new_fills = filled_qty - self.filled_quantity
                        self.filled_quantity = filled_qty
                        self.remaining_quantity = self.quantity - self.filled_quantity
                        log_callback(f"FILL: {new_fills} shares filled. Total: {self.filled_quantity}/{self.quantity}")

                        if self.remaining_quantity == 0:
                            log_callback("Order fully filled!")
                            break

                    if status in ['FILLED', 'CANCELED', 'REJECTED', 'EXPIRED']:
                        if status != 'FILLED':
                            log_callback(f"Order status: {status}")

                        if self.remaining_quantity == 0:
                            break

                # Calculate next price
                new_price, next_state, source = await self.calculate_next_price(
                    self.symbol, self.side, self.current_state
                )

                if new_price is None:
                    log_callback("WARNING: Could not retrieve market data, retrying...")
                    await asyncio.sleep(1)
                    continue

                # Replace order
                log_callback(f"Replacing order: {self.side} {self.remaining_quantity} @ {new_price} [{self.current_state.value}] ({source})")

                new_order_id = await self.replace_order(
                    self.current_order_id, self.symbol, self.side,
                    self.remaining_quantity, new_price
                )

                if new_order_id:
                    self.current_order_id = new_order_id
                    self.current_state = next_state
                    log_callback(f"Order replaced: ID {self.current_order_id}")
                else:
                    log_callback("WARNING: Failed to replace order, retrying...")

                await asyncio.sleep(0.5)

        except Exception as e:
            log_callback(f"ERROR: {str(e)}")
        finally:
            self.is_running = False
            log_callback("Order management loop stopped")

    def start_order(self, symbol, side, quantity, log_callback):
        """Start the order management process"""
        self.symbol = symbol.upper()
        self.side = side.upper()
        self.quantity = quantity
        self.filled_quantity = 0
        self.remaining_quantity = quantity

        self.order_loop_task = asyncio.create_task(
            self.order_management_loop(log_callback)
        )

    def pause(self):
        """Pause the order management loop"""
        self.is_paused = True

    def resume(self):
        """Resume the order management loop"""
        self.is_paused = False

    async def stop(self):
        """Stop the order management loop and cancel active orders"""
        self.is_running = False
        if self.current_order_id:
            await self.cancel_order(self.current_order_id)
        if self.order_loop_task:
            self.order_loop_task.cancel()

    async def get_positions(self):
        """Get current positions"""
        response = await self.client.get_account(
            self.account_hash,
            fields='positions'
        )
        if response.status_code == 200:
            account_data = response.json()
            return account_data.get('securitiesAccount', {}).get('positions', [])
        return []

    def calculate_exposure(self, positions):
        """Calculate total exposure from positions"""
        exposure = {}
        for position in positions:
            symbol = position['instrument']['symbol']
            quantity = position['longQuantity'] - position['shortQuantity']
            market_value = position.get('marketValue', 0)

            exposure[symbol] = {
                'quantity': quantity,
                'market_value': market_value
            }

        return exposure

    def get_book_depth_display(self, symbol, levels=5):
        """Get formatted book depth for display"""
        if not self.use_level2:
            return "Level 2 data not available"

        depth = self.book_handler.get_book_depth(symbol, levels)

        if not depth['bids'] and not depth['asks']:
            return f"No Level 2 data for {symbol}"

        lines = [f"\n{symbol} Order Book:"]
        lines.append("-" * 40)
        lines.append(f"{'BID':>15}  {'SIZE':>8}  {'ASK':>8}  {'SIZE':<8}")
        lines.append("-" * 40)

        max_len = max(len(depth['bids']), len(depth['asks']))

        for i in range(max_len):
            bid_str = f"${depth['bids'][i][0]:.2f} x {depth['bids'][i][1]}" if i < len(depth['bids']) else ""
            ask_str = f"${depth['asks'][i][0]:.2f} x {depth['asks'][i][1]}" if i < len(depth['asks']) else ""
            lines.append(f"{bid_str:>25}  {ask_str:<25}")

        return "\n".join(lines)


# The TradingUI class would be similar to the original, but using SchwabTraderLevel2
# For brevity, I'll note the key changes needed:
# 1. Replace SchwabTrader with SchwabTraderLevel2
# 2. Add a "View Book Depth" button
# 3. Display Level 2 status in the UI

# [Rest of UI code would be similar to original schwab_trader.py]
# Use the same TradingUI class but instantiate SchwabTraderLevel2 instead
