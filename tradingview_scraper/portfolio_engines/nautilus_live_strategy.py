import json
import logging
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional, cast
from unittest.mock import MagicMock

import pandas as pd

# Standard types
Strategy: Any = object
OrderSide: Any = object
InstrumentId: Any = object
Quantity: Any = object
Venue: Any = object
Symbol: Any = object
Currency: Any = object
CurrencyType: Any = object
Price: Any = object
CurrencyPair: Any = object
register_currency: Any = lambda c: None

try:
    from nautilus_trader.model.currencies import register_currency as _register_currency
    from nautilus_trader.model.enums import CurrencyType as _CurrencyType
    from nautilus_trader.model.enums import OrderSide as _OrderSide
    from nautilus_trader.model.identifiers import InstrumentId as _InstrumentId
    from nautilus_trader.model.identifiers import Symbol as _Symbol
    from nautilus_trader.model.identifiers import Venue as _Venue
    from nautilus_trader.model.instruments import CurrencyPair as _CurrencyPair
    from nautilus_trader.model.objects import Currency as _Currency
    from nautilus_trader.model.objects import Price as _Price
    from nautilus_trader.model.objects import Quantity as _Quantity
    from nautilus_trader.trading.strategy import Strategy as _Strategy

    from tradingview_scraper.portfolio_engines.nautilus_strategy import INITIAL_CASH_VAL, NautilusRebalanceStrategy

    Strategy = _Strategy
    OrderSide = _OrderSide
    InstrumentId = _InstrumentId
    Symbol = _Symbol
    Venue = _Venue
    Currency = _Currency
    CurrencyType = _CurrencyType
    Price = _Price
    Quantity = _Quantity
    CurrencyPair = _CurrencyPair
    register_currency = _register_currency
    HAS_NAUTILUS = True
except ImportError:
    HAS_NAUTILUS = False
    INITIAL_CASH_VAL = 100_000.0

    class NautilusRebalanceStrategy(object):  # type: ignore
        def __init__(self, *args, **kwargs):
            self.cache: Any = MagicMock()
            self.portfolio: Any = MagicMock()
            self.target_weights = pd.DataFrame()

        def on_start(self):
            pass

        def on_stop(self):
            pass

        def _get_nav(self) -> float:
            return 0.0


logger = logging.getLogger(__name__)


class LiveRebalanceStrategy(NautilusRebalanceStrategy):  # type: ignore
    """
    Live execution strategy that watches a JSON file for target weight updates.
    """

    def __init__(self, weights_file: str, venue_str: str = "BINANCE", mode: str = "SHADOW", *args, **kwargs):
        super().__init__(pd.DataFrame(), *args, **kwargs)
        self.weights_file = weights_file
        self.venue_str = venue_str
        self.mode = mode.upper()
        self.last_mtime = 0
        self.running = False

    def on_start(self):
        if HAS_NAUTILUS and not self.cache.instruments():
            logger.warning("Shadow Mode detected (Empty Instrument Cache). Injecting dummy instruments...")
            self._inject_dummy_instruments()

        super().on_start()
        self.running = True
        self.watcher_thread = threading.Thread(target=self._watch_file, daemon=True)
        self.watcher_thread.start()
        logger.info(f"Started LiveRebalanceStrategy watching {self.weights_file} [MODE={self.mode}]")

    def _inject_dummy_instruments(self):
        """Injects dummy CurrencyPair instruments for Shadow Mode."""
        try:
            if os.path.exists(self.weights_file):
                with open(self.weights_file, "r") as f:
                    data = json.load(f)
                weights_map = data.get("weights", data)
                symbols = list(weights_map.keys())
            else:
                symbols = ["BTCUSDT", "ETHUSDT"]
        except Exception:
            symbols = ["BTCUSDT", "ETHUSDT"]

        venue = Venue(self.venue_str)

        quote_code = "USDT"
        try:
            quote_curr = Currency.from_str(quote_code)
        except Exception:
            quote_curr = Currency(quote_code, 8, 999, quote_code, CurrencyType.CRYPTO)
            register_currency(quote_curr)

        for raw_symbol in symbols:
            clean_symbol = raw_symbol.split(".")[0] if "." in raw_symbol else raw_symbol
            base_code = clean_symbol.replace(quote_code, "")
            try:
                base_curr = Currency.from_str(base_code)
            except Exception:
                base_curr = Currency(base_code, 8, 999, base_code, CurrencyType.CRYPTO)
                register_currency(base_curr)

            sym_obj = Symbol(clean_symbol)
            inst_id = InstrumentId(sym_obj, venue)

            inst = CurrencyPair(
                instrument_id=inst_id,
                raw_symbol=sym_obj,
                base_currency=base_curr,
                quote_currency=quote_curr,
                price_precision=2,
                size_precision=5,
                price_increment=Price.from_str("0.01"),
                size_increment=Quantity.from_str("0.00001"),
                lot_size=Quantity.from_str("0.00001"),
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

            try:
                if hasattr(self.cache, "add_instrument"):
                    self.cache.add_instrument(inst)
                elif hasattr(self.cache, "_instruments"):
                    self.cache._instruments[inst_id] = inst
                logger.info(f"Injected dummy instrument: {inst_id}")
            except Exception as e:
                logger.error(f"Failed to inject {inst_id}: {e}")

    def _get_live_equity(self) -> float:
        nav = self._get_nav()
        if nav < 1.0:
            return 100_000.0
        return nav

    def _get_nav(self) -> float:
        """Robustly extracts total equity from portfolio."""
        if not HAS_NAUTILUS:
            return 0.0
        total_cash = 0.0
        try:
            venue_id = Venue(self.venue_str)
            account = self.portfolio.account(venue_id)
            for balance in account.balances():
                money_obj = getattr(balance, "total", balance)
                if hasattr(money_obj, "as_double"):
                    total_cash += money_obj.as_double()
                elif hasattr(money_obj, "float_value"):
                    total_cash += money_obj.float_value()
                else:
                    total_cash += float(money_obj)
        except Exception as e:
            logger.debug(f"Could not get cash balance: {e}")

        pos_value = 0.0
        for pos in self.portfolio.positions():
            try:
                last_quote = self.cache.quote_tick(pos.instrument_id)
                if last_quote:
                    price = float(last_quote.bid_price if pos.quantity > 0 else last_quote.ask_price)
                else:
                    last_bar = self.cache.bar(pos.instrument_id)
                    price = float(last_bar.close) if last_bar else 0.0
                pos_value += float(pos.quantity) * price
            except Exception as e:
                logger.debug(f"Failed to calc position value for {pos.instrument_id}: {e}")
        return total_cash + pos_value

    def on_stop(self):
        super().on_stop()
        self.running = False

    def _watch_file(self):
        while self.running:
            try:
                if os.path.exists(self.weights_file):
                    mtime = os.path.getmtime(self.weights_file)
                    if mtime > self.last_mtime:
                        self.last_mtime = mtime
                        self._load_weights()
            except Exception as e:
                logger.error(f"Error watching weights file: {e}")
            time.sleep(5)

    def _load_weights(self):
        try:
            with open(self.weights_file, "r") as f:
                data = json.load(f)
            weights_map = data.get("weights", data)
            df = pd.DataFrame([weights_map])
            df.index = pd.to_datetime([pd.Timestamp.now(tz="UTC")])
            self.target_weights = df
            logger.info(f"Loaded new target weights: {weights_map}")
            self._rebalance_portfolio()
        except Exception as e:
            logger.error(f"Failed to load weights: {e}")

    def _rebalance_portfolio(self):
        if not HAS_NAUTILUS or self.target_weights.empty:
            return

        targets = self.target_weights.iloc[0]
        target_symbols = set(targets.index)
        current_holdings = {str(pos.instrument_id) for pos in self.portfolio.positions()}
        all_symbols = target_symbols | current_holdings

        logger.info(f"Rebalancing {len(all_symbols)} symbols...")

        for symbol_str in all_symbols:
            nautilus_symbol = f"{symbol_str.split(':')[1]}.{symbol_str.split(':')[0]}" if ":" in symbol_str else symbol_str
            try:
                instrument_id = InstrumentId.from_str(nautilus_symbol)
                instrument = self.cache.instrument(instrument_id)
                if not instrument:
                    continue

                weight = float(targets.get(symbol_str, targets.get(nautilus_symbol, 0.0)))
                last_quote = self.cache.quote_tick(instrument_id)
                if last_quote:
                    price = float(last_quote.bid_price if weight < 0 else last_quote.ask_price)
                else:
                    last_bar = self.cache.bar(instrument_id)
                    price = float(last_bar.close) if last_bar else 0.0

                if price <= 0:
                    continue

                equity = self._get_live_equity()
                target_value = equity * weight * 0.98
                current_qty = float(self.portfolio.net_position(instrument_id))
                raw_qty = target_value / price

                step_size = float(getattr(instrument, "size_increment", 0.00001))
                qty = math.floor(raw_qty / step_size) * step_size if step_size > 0 else raw_qty
                delta = qty - current_qty

                if abs(delta * price) > max(10.0, equity * 0.001):
                    self._execute_rebalance_live(instrument, delta)
            except Exception as e:
                logger.error(f"Error rebalancing {symbol_str}: {e}")

    def _execute_rebalance_live(self, instrument, delta):
        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        qty = abs(delta)
        if self.mode == "SHADOW":
            logger.info(f"✨ [SHADOW ORDER] {side} {qty:.4f} {instrument.id}")
            return
        logger.info(f"🚀 [LIVE ORDER] Submitting {side} {qty:.4f} {instrument.id}")
        try:
            order = self.order_factory.market(instrument.id, side, Quantity.from_scalar(qty, instrument.size_precision))
            self.submit_order(order)
        except Exception as e:
            logger.error(f"Failed to submit order for {instrument.id}: {e}")
