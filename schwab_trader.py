"""
Schwab Trading Application with Alternating Order Strategy
This application allows users to place orders that alternate between top-of-book
and one tick away from top-of-book until filled or cancelled.
"""

import schwab
import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from threading import Thread
import json
from datetime import datetime
from enum import Enum


class OrderState(Enum):
    """Order placement states for alternating strategy"""
    AT_BOOK = "at_book"  # Order at top of book (BID for buy, ASK for sell)
    OFFSET_TICK = "offset_tick"  # Order offset by 1 tick (BID-1 for buy, ASK+1 for sell)


class SchwabTrader:
    """Main trading logic handler"""

    def __init__(self, api_key, app_secret, callback_url, token_path="token.json"):
        """
        Initialize Schwab trader

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
        self.account_hash = None

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
                # Use first account, can be modified to select specific account
                self.account_hash = accounts[0]['securitiesAccount']['accountId']
                return True
        return False

    async def get_quote(self, symbol):
        """
        Get current quote for symbol

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
        Get level 2 order book data

        Args:
            symbol: Stock or option symbol

        Returns:
            dict: Order book with bids and asks
        """
        # Note: Level 2 data access depends on account permissions
        # Using quotes as fallback for top of book
        quote = await self.get_quote(symbol)
        if quote:
            return {
                'bid': quote.get('bidPrice', 0),
                'ask': quote.get('askPrice', 0),
                'bid_size': quote.get('bidSize', 0),
                'ask_size': quote.get('askSize', 0),
                'tick_size': self._calculate_tick_size(quote.get('bidPrice', 0))
            }
        return None

    def _calculate_tick_size(self, price):
        """
        Calculate tick size based on price

        Args:
            price: Current price

        Returns:
            float: Tick size
        """
        if price >= 1.00:
            return 0.01
        else:
            return 0.0001  # For options and low-priced stocks

    async def place_order(self, symbol, side, quantity, price, order_type='LIMIT'):
        """
        Place an order

        Args:
            symbol: Stock or option symbol
            side: 'BUY' or 'SELL'
            quantity: Number of shares/contracts
            price: Limit price
            order_type: Order type (default: LIMIT)

        Returns:
            str: Order ID if successful
        """
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
                        'assetType': 'EQUITY'  # Change to 'OPTION' for options
                    }
                }
            ]
        }

        if order_type == 'LIMIT':
            order_spec['price'] = round(price, 2)

        response = await self.client.place_order(self.account_hash, order_spec)

        if response.status_code == 201:
            # Extract order ID from response headers
            location = response.headers.get('Location', '')
            order_id = location.split('/')[-1] if location else None
            return order_id

        return None

    async def cancel_order(self, order_id):
        """
        Cancel an order

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if successful
        """
        response = await self.client.cancel_order(order_id, self.account_hash)
        return response.status_code == 200

    async def replace_order(self, old_order_id, symbol, side, quantity, new_price):
        """
        Replace an existing order (cancel and replace)

        Args:
            old_order_id: Order ID to replace
            symbol: Stock or option symbol
            side: 'BUY' or 'SELL'
            quantity: Number of shares/contracts
            new_price: New limit price

        Returns:
            str: New order ID if successful
        """
        # Cancel old order
        await self.cancel_order(old_order_id)

        # Place new order
        new_order_id = await self.place_order(symbol, side, quantity, new_price)
        return new_order_id

    async def get_order_status(self, order_id):
        """
        Get status of an order

        Args:
            order_id: Order ID

        Returns:
            dict: Order status information
        """
        response = await self.client.get_order(order_id, self.account_hash)
        if response.status_code == 200:
            return response.json()
        return None

    async def calculate_next_price(self, symbol, side, state):
        """
        Calculate next price based on strategy state

        Args:
            symbol: Stock or option symbol
            side: 'BUY' or 'SELL'
            state: Current OrderState

        Returns:
            tuple: (price, next_state)
        """
        book = await self.get_order_book(symbol)
        if not book:
            return None, state

        tick_size = book['tick_size']

        if side == 'BUY':
            if state == OrderState.AT_BOOK:
                # Place at BID (top of book)
                price = book['bid']
                next_state = OrderState.OFFSET_TICK
            else:
                # Place at BID - 1 tick
                price = book['bid'] - tick_size
                next_state = OrderState.AT_BOOK
        else:  # SELL
            if state == OrderState.AT_BOOK:
                # Place at ASK (top of book)
                price = book['ask']
                next_state = OrderState.OFFSET_TICK
            else:
                # Place at ASK + 1 tick
                price = book['ask'] + tick_size
                next_state = OrderState.AT_BOOK

        return round(price, 4), next_state

    async def order_management_loop(self, log_callback):
        """
        Main order management loop with alternating strategy

        Args:
            log_callback: Function to call with log messages
        """
        self.is_running = True
        self.current_state = OrderState.OFFSET_TICK

        try:
            # Place initial order at offset tick (BID-1 or ASK+1)
            initial_price, next_state = await self.calculate_next_price(
                self.symbol, self.side, self.current_state
            )

            if initial_price is None:
                log_callback("ERROR: Could not retrieve market data")
                return

            log_callback(f"Placing initial order: {self.side} {self.quantity} {self.symbol} @ {initial_price}")
            self.current_order_id = await self.place_order(
                self.symbol, self.side, self.remaining_quantity, initial_price
            )

            if not self.current_order_id:
                log_callback("ERROR: Failed to place initial order")
                return

            log_callback(f"Order placed: ID {self.current_order_id}")
            self.current_state = next_state

            # Wait for confirmation (brief delay to allow order to post)
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
                        # Partial or full fill
                        new_fills = filled_qty - self.filled_quantity
                        self.filled_quantity = filled_qty
                        self.remaining_quantity = self.quantity - self.filled_quantity
                        log_callback(f"FILL: {new_fills} contracts filled. Total: {self.filled_quantity}/{self.quantity}")

                        if self.remaining_quantity == 0:
                            log_callback("Order fully filled!")
                            break

                    if status in ['FILLED', 'CANCELED', 'REJECTED', 'EXPIRED']:
                        if status != 'FILLED':
                            log_callback(f"Order status: {status}")

                        if self.remaining_quantity == 0:
                            break

                # Calculate next price based on alternating strategy
                new_price, next_state = await self.calculate_next_price(
                    self.symbol, self.side, self.current_state
                )

                if new_price is None:
                    log_callback("WARNING: Could not retrieve market data, retrying...")
                    await asyncio.sleep(1)
                    continue

                # Replace order
                log_callback(f"Replacing order: {self.side} {self.remaining_quantity} @ {new_price} [{self.current_state.value}]")
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

                # Wait before next replacement (adjust timing as needed)
                await asyncio.sleep(0.5)

        except Exception as e:
            log_callback(f"ERROR: {str(e)}")
        finally:
            self.is_running = False
            log_callback("Order management loop stopped")

    def start_order(self, symbol, side, quantity, log_callback):
        """
        Start the order management process

        Args:
            symbol: Stock or option symbol
            side: 'BUY' or 'SELL'
            quantity: Number of shares/contracts
            log_callback: Function to call with log messages
        """
        self.symbol = symbol.upper()
        self.side = side.upper()
        self.quantity = quantity
        self.filled_quantity = 0
        self.remaining_quantity = quantity

        # Start order loop in async context
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
        """
        Get current positions

        Returns:
            dict: Position information
        """
        response = await self.client.get_account(
            self.account_hash,
            fields='positions'
        )
        if response.status_code == 200:
            account_data = response.json()
            return account_data.get('securitiesAccount', {}).get('positions', [])
        return []

    def calculate_exposure(self, positions):
        """
        Calculate total exposure from positions

        Args:
            positions: List of position dictionaries

        Returns:
            dict: Exposure breakdown by symbol
        """
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


class TradingUI:
    """Tkinter-based UI for the trading application"""

    def __init__(self, root):
        self.root = root
        self.root.title("Schwab Trading Application")
        self.root.geometry("800x600")

        self.trader = None
        self.loop = None
        self.thread = None

        self.setup_ui()

    def setup_ui(self):
        """Setup the UI components"""

        # Configuration Frame
        config_frame = ttk.LabelFrame(self.root, text="Configuration", padding=10)
        config_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        ttk.Label(config_frame, text="API Key:").grid(row=0, column=0, sticky="w", pady=2)
        self.api_key_entry = ttk.Entry(config_frame, width=40)
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(config_frame, text="App Secret:").grid(row=1, column=0, sticky="w", pady=2)
        self.app_secret_entry = ttk.Entry(config_frame, width=40, show="*")
        self.app_secret_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(config_frame, text="Callback URL:").grid(row=2, column=0, sticky="w", pady=2)
        self.callback_entry = ttk.Entry(config_frame, width=40)
        self.callback_entry.insert(0, "https://localhost:8080")
        self.callback_entry.grid(row=2, column=1, padx=5, pady=2)

        self.connect_btn = ttk.Button(config_frame, text="Connect", command=self.connect)
        self.connect_btn.grid(row=3, column=1, pady=5)

        # Order Entry Frame
        order_frame = ttk.LabelFrame(self.root, text="Order Entry", padding=10)
        order_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        ttk.Label(order_frame, text="Symbol:").grid(row=0, column=0, sticky="w", pady=2)
        self.symbol_entry = ttk.Entry(order_frame, width=15)
        self.symbol_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(order_frame, text="Side:").grid(row=0, column=2, sticky="w", pady=2)
        self.side_var = tk.StringVar(value="BUY")
        side_combo = ttk.Combobox(order_frame, textvariable=self.side_var,
                                   values=["BUY", "SELL"], width=10, state="readonly")
        side_combo.grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(order_frame, text="Quantity:").grid(row=1, column=0, sticky="w", pady=2)
        self.quantity_entry = ttk.Entry(order_frame, width=15)
        self.quantity_entry.insert(0, "1")
        self.quantity_entry.grid(row=1, column=1, padx=5, pady=2)

        self.start_btn = ttk.Button(order_frame, text="Start Order",
                                     command=self.start_order, state="disabled")
        self.start_btn.grid(row=2, column=1, pady=10)

        # Control Frame
        control_frame = ttk.LabelFrame(self.root, text="Controls", padding=10)
        control_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        self.pause_btn = ttk.Button(control_frame, text="Pause",
                                     command=self.pause_order, state="disabled")
        self.pause_btn.grid(row=0, column=0, padx=5)

        self.resume_btn = ttk.Button(control_frame, text="Resume",
                                      command=self.resume_order, state="disabled")
        self.resume_btn.grid(row=0, column=1, padx=5)

        self.stop_btn = ttk.Button(control_frame, text="Stop",
                                    command=self.stop_order, state="disabled")
        self.stop_btn.grid(row=0, column=2, padx=5)

        # Exposure Frame
        exposure_frame = ttk.LabelFrame(self.root, text="Exposure", padding=10)
        exposure_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        self.exposure_label = ttk.Label(exposure_frame, text="Not connected")
        self.exposure_label.grid(row=0, column=0, sticky="w")

        self.refresh_btn = ttk.Button(exposure_frame, text="Refresh",
                                       command=self.refresh_exposure, state="disabled")
        self.refresh_btn.grid(row=0, column=1, padx=5)

        # Log Frame
        log_frame = ttk.LabelFrame(self.root, text="Activity Log", padding=10)
        log_frame.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=90)
        self.log_text.grid(row=0, column=0, sticky="nsew")

        # Configure grid weights
        self.root.grid_rowconfigure(4, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

    def log(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def connect(self):
        """Connect to Schwab API"""
        api_key = self.api_key_entry.get().strip()
        app_secret = self.app_secret_entry.get().strip()
        callback_url = self.callback_entry.get().strip()

        if not api_key or not app_secret:
            messagebox.showerror("Error", "Please enter API Key and App Secret")
            return

        self.log("Connecting to Schwab API...")

        # Create new event loop for async operations
        self.loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        self.thread = Thread(target=run_loop, daemon=True)
        self.thread.start()

        # Initialize trader
        self.trader = SchwabTrader(api_key, app_secret, callback_url)

        # Authenticate
        future = asyncio.run_coroutine_threadsafe(
            self.trader.authenticate(), self.loop
        )

        try:
            result = future.result(timeout=30)
            if result:
                self.log("Connected successfully!")
                self.start_btn.config(state="normal")
                self.refresh_btn.config(state="normal")
                self.connect_btn.config(state="disabled")
                self.refresh_exposure()
            else:
                self.log("ERROR: Connection failed")
                messagebox.showerror("Error", "Failed to connect to Schwab API")
        except Exception as e:
            self.log(f"ERROR: {str(e)}")
            messagebox.showerror("Error", f"Connection error: {str(e)}")

    def start_order(self):
        """Start the order management process"""
        symbol = self.symbol_entry.get().strip()
        side = self.side_var.get()

        try:
            quantity = int(self.quantity_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Quantity must be a number")
            return

        if not symbol:
            messagebox.showerror("Error", "Please enter a symbol")
            return

        if quantity <= 0:
            messagebox.showerror("Error", "Quantity must be greater than 0")
            return

        self.log(f"Starting order: {side} {quantity} {symbol}")

        # Start order in async context
        self.trader.start_order(symbol, side, quantity, self.log)

        # Update button states
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")

    def pause_order(self):
        """Pause the order management loop"""
        self.trader.pause()
        self.log("Order management paused")
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="normal")

    def resume_order(self):
        """Resume the order management loop"""
        self.trader.resume()
        self.log("Order management resumed")
        self.resume_btn.config(state="disabled")
        self.pause_btn.config(state="normal")

    def stop_order(self):
        """Stop the order management loop"""
        future = asyncio.run_coroutine_threadsafe(
            self.trader.stop(), self.loop
        )
        future.result(timeout=5)

        self.log("Order management stopped")

        # Update button states
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")

    def refresh_exposure(self):
        """Refresh exposure display"""
        if not self.trader:
            return

        future = asyncio.run_coroutine_threadsafe(
            self.trader.get_positions(), self.loop
        )

        try:
            positions = future.result(timeout=10)
            exposure = self.trader.calculate_exposure(positions)

            if exposure:
                exposure_text = " | ".join([
                    f"{sym}: {data['quantity']} (${data['market_value']:.2f})"
                    for sym, data in exposure.items()
                ])
                self.exposure_label.config(text=exposure_text)
            else:
                self.exposure_label.config(text="No positions")

            self.log("Exposure refreshed")
        except Exception as e:
            self.log(f"ERROR refreshing exposure: {str(e)}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = TradingUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
