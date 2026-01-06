import json
import logging
import os
import threading
import time

import pandas as pd

try:
    from nautilus_trader.model.currencies import register_currency
    from nautilus_trader.model.enums import CurrencyType, OrderSide
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.instruments import CurrencyPair
    from nautilus_trader.model.objects import Currency, Price, Quantity

    from tradingview_scraper.portfolio_engines.nautilus_strategy import INITIAL_CASH_VAL, NautilusRebalanceStrategy

    HAS_NAUTILUS = True
except ImportError:
    HAS_NAUTILUS = False
    NautilusRebalanceStrategy = object

logger = logging.getLogger(__name__)


class LiveRebalanceStrategy(NautilusRebalanceStrategy):
    """
    Live execution strategy that watches a JSON file for target weight updates.
    """

    def __init__(self, weights_file: str, venue_str: str = "BINANCE", *args, **kwargs):
        super().__init__(pd.DataFrame(), *args, **kwargs)  # Start with empty weights
        self.weights_file = weights_file
        self.venue_str = venue_str
        self.last_mtime = 0
        self.running = False

    def on_start(self):
        # 1. Shadow Mode Injection (If cache is empty)
        if HAS_NAUTILUS and not self.cache.instruments():
            logger.warning("Shadow Mode detected (Empty Instrument Cache). Injecting dummy instruments...")
            self._inject_dummy_instruments()

        super().on_start()
        self.running = True
        self.watcher_thread = threading.Thread(target=self._watch_file, daemon=True)
        self.watcher_thread.start()
        logger.info(f"Started LiveRebalanceStrategy watching {self.weights_file}")

    def _inject_dummy_instruments(self):
        """Injects dummy CurrencyPair instruments for Shadow Mode."""
        # We need to know WHICH symbols to inject.
        # Ideally, we read the weights file immediately to get the universe.
        # Or we just inject a few standard ones if we don't know yet.
        # Better: Load weights now to get the symbol list.
        try:
            if os.path.exists(self.weights_file):
                with open(self.weights_file, "r") as f:
                    data = json.load(f)
                weights_map = data.get("weights", data)
                symbols = list(weights_map.keys())
            else:
                logger.warning("Weights file not found for instrument injection. Injecting fallback BTC/ETH.")
                symbols = ["BTCUSDT", "ETHUSDT"]
        except Exception:
            symbols = ["BTCUSDT", "ETHUSDT"]

        venue = Venue(self.venue_str)

        def get_currency(code):
            try:
                return Currency.from_str(code)
            except ValueError:
                # Mock registration
                # iso4217=999 is generic for user-defined
                c = Currency(code, 8, 999, code, CurrencyType.CRYPTO)
                register_currency(c)
                return c

        # Assume Quote Currency is USDT for Crypto
        quote_code = "USDT"
        quote_curr = get_currency(quote_code)

        for raw_symbol in symbols:
            # Handle suffix if present
            if "." in raw_symbol:
                base_code = raw_symbol.split(".")[0].replace(quote_code, "")
                clean_symbol = raw_symbol.split(".")[0]
            else:
                base_code = raw_symbol.replace(quote_code, "")
                clean_symbol = raw_symbol

            base_curr = get_currency(base_code)

            # Create InstrumentId
            # If raw_symbol has no dot, we construct it: SYMBOL.VENUE
            # Nautilus expects Symbol object, Venue object
            sym = Symbol(clean_symbol)
            inst_id = InstrumentId(sym, venue)

            # Create CurrencyPair
            inst = CurrencyPair(
                instrument_id=inst_id,
                raw_symbol=Symbol(clean_symbol),
                base_currency=base_curr,
                quote_currency=quote_curr,
                price_precision=2,
                size_precision=5,
                price_increment=Price.from_str("0.01"),
                size_increment=Quantity.from_str("0.00001"),
                lot_size=Quantity.from_str("0.00001"),  # Optional, but good for validation
                max_quantity=Quantity.from_str("1000000"),
                min_quantity=Quantity.from_str("0.00001"),
                max_price=Price.from_str("1000000"),
                min_price=Price.from_str("0.01"),
                margin_init=0,
                margin_maint=0,
                maker_fee=0,
                taker_fee=0,
                ts_event=0,
                ts_init=0,
            )

            # Inject
            # In a Strategy, self.cache is usually read-only interface.
            # We might need to access the underlying provider or engine?
            # But wait, self.instrument_provider is usually available on the node, not strategy.
            # Strategy has self.cache which is an InstrumentCache.
            # Let's try adding to cache directly if method exists (it usually does on the concrete cache implementation).

            # HACK: Access internal cache if public API forbids
            # Typically strategy.cache is `InstrumentCache`.
            # If it doesn't have `add_instrument`, we are stuck.
            # But in Nautilus tests, one can add to cache.

            try:
                if hasattr(self.cache, "add_instrument"):
                    self.cache.add_instrument(inst)
                elif hasattr(self.cache, "_instruments"):
                    self.cache._instruments[inst_id] = inst  # Very dirty hack
                logger.info(f"Injected dummy instrument: {inst_id}")
            except Exception as e:
                logger.error(f"Failed to inject {inst_id}: {e}")

    def _get_live_equity(self) -> float:
        """Returns Portfolio NAV, with fallback for Shadow/Disconnected mode."""
        nav = self._get_nav()  # Base class method
        if nav < 1.0:
            # Assume Shadow Mode / Disconnected
            return 100_000.0
        return nav

    def _rebalance_portfolio(self):
        """Iterates through all known instruments and adjusts positions."""

    def on_stop(self):
        super().on_stop()
        self.running = False

    def _watch_file(self):
        """Polls the weights file for changes."""
        while self.running:
            try:
                if os.path.exists(self.weights_file):
                    mtime = os.path.getmtime(self.weights_file)
                    if mtime > self.last_mtime:
                        self.last_mtime = mtime
                        self._load_weights()
            except Exception as e:
                logger.error(f"Error watching weights file: {e}")

            time.sleep(5)  # Check every 5 seconds

    def _load_weights(self):
        """Loads weights from JSON and triggers rebalance."""
        try:
            # Expected format: {"timestamp": "2025-01-01...", "weights": {"BTCUSDT": 0.5, ...}}
            # Or just flat dict: {"BTCUSDT": 0.5}
            with open(self.weights_file, "r") as f:
                data = json.load(f)

            if "weights" in data:
                weights_map = data["weights"]
            else:
                weights_map = data

            # Convert to DataFrame expected by base class
            # We treat this as the "Latest" weights, so index is effectively "Now"
            # We replace the entire target_weights DF to avoid lookup issues
            df = pd.DataFrame([weights_map])
            df.index = pd.to_datetime([pd.Timestamp.now(tz="UTC")])

            self.target_weights = df
            logger.info(f"Loaded new target weights: {weights_map}")

            # Trigger Rebalance immediately
            self._rebalance_portfolio()

        except Exception as e:
            logger.error(f"Failed to load weights: {e}")

    def _rebalance_portfolio(self):
        """Iterates through all known instruments and adjusts positions."""
        if not HAS_NAUTILUS:
            return

        # We need to iterate over UNION of current holdings and new targets
        # Nautilus 'portfolio.positions' gives current holdings.
        # 'target_weights' gives new targets.

        all_symbols = set(self.target_weights.columns)
        # for pos in self.portfolio.positions():
        #     all_symbols.add(str(pos.instrument_id))

        logger.info(f"Rebalancing {len(all_symbols)} symbols...")

        for symbol_str in all_symbols:
            # Robust Parsing: Append Venue if missing
            if "." not in symbol_str and self.venue_str:
                symbol_str = f"{symbol_str}.{self.venue_str}"

            # We need the Instrument object to trade.
            # If we hold it, we have it. If it's new target, we might need to find it.
            try:
                instrument_id = InstrumentId.from_str(symbol_str)
                instrument = self.cache.instrument(instrument_id)

                if not instrument:
                    logger.warning(f"Instrument {symbol_str} not found in cache. Cannot trade.")
                    continue

                # Get target weight (default 0.0)
                # Since target_weights is 1-row DF of "latest", just take the value
                if symbol_str in self.target_weights.columns:
                    weight = self.target_weights.iloc[0][symbol_str]
                else:
                    weight = 0.0

                # Calculate quantity
                # We mock a 'bar' with latest price for the base class method?
                # Or we override calculation.
                # Let's get price from cache or last quote.

                # Nautilus `cache.bar(bar_type)`?
                # Or `portfolio.net_position` value?

                last_quote = self.cache.quote_tick(instrument_id)
                if last_quote:
                    price = last_quote.bid_price  # Conservative? Or mid?
                else:
                    # Fallback to last bar?
                    # For now, if no price, skip
                    logger.warning(f"No price for {symbol_str}, skipping.")
                    continue

                # Use base class logic but inject price manually?
                # Base class `_calculate_target_qty` expects a `bar`.
                # Let's override `_calculate_target_qty` or write custom logic here.

                # Custom logic for Live:
                equity = self._get_live_equity()
                target_value = equity * weight * 0.95  # Buffer

                current_qty = float(self.portfolio.net_position(instrument_id))

                if price <= 0:
                    continue

                raw_qty = target_value / float(price)

                # Apply limits (Step Size, Min Notional)
                # Reuse base class catalog logic if possible, or reimplement
                # ... (Simplified for now)

                qty = raw_qty  # TODO: Apply rounding

                delta = qty - current_qty

                # Execute
                if abs(delta * float(price)) > 10.0:  # Min trade $10 (Binance limit approx)
                    self._execute_rebalance_live(instrument, delta)

            except Exception as e:
                logger.error(f"Error rebalancing {symbol_str}: {e}")

    def _get_live_equity(self) -> float:
        # Sum cash + positions using real account data
        # Nautilus Portfolio should have this updated via data feed
        return self._get_nav()  # Base class method

    def _execute_rebalance_live(self, instrument, delta):
        # Similar to base class but logged specific for live

        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        qty = abs(delta)

        # Rounding logic needed here based on Instrument spec
        # instrument.size_precision, instrument.size_increment

        logger.info(f"Submitting {side} {qty} {instrument.id}")
        order = self.order_factory.market(instrument.id, side, Quantity.from_scalar(qty, instrument.size_precision))
        self.submit_order(order)
