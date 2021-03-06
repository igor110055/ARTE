from functools import wraps
from decimal import Decimal, getcontext

getcontext().prec = 6

from binance_f.model.constant import *
from .test_account import TestAccount
from .test_order_handler import TestOrderHandler
from arte.test_system.bt_order_recorder import BackTestOrderRecorder


def _process_order(method):
    @wraps(method)
    def _impl(self, **kwargs):
        print(kwargs)
        kwargs["symbol"] = kwargs["symbol"].upper()
        if kwargs["symbol"] not in self.symbols_state:
            self.symbols_state[kwargs["symbol"]] = self._init_symbol_state()
        order = method(self, **kwargs)
        if order:
            self._postprocess_order(order)
        return order

    return _impl


class BackTestBinanceTradeManager:
    def __init__(self, init_usdt=5000, *args, **kwargs):
        self.account = TestAccount(init_balance=init_usdt)
        self.order_handler = TestOrderHandler(self.account)
        self.order_recorder = BackTestOrderRecorder()
        self.test_current_time = None
        self.future_prices = None

        self.bot = None
        if "bot" in kwargs:
            self.bot = kwargs["bot"]
        if "max_order_count" in kwargs:
            self.max_order_count = kwargs["max_order_count"]

        # state manage
        self.symbols_state = dict()

    def _init_symbol_state(self):
        return dict(order_count=0, positionSize=0, positionSide=PositionSide.INVALID)

    @_process_order
    def buy_long_market(self, symbol, usdt=None, ratio=None):
        if self.symbols_state[symbol]["order_count"] < self.max_order_count:
            return self.order_handler.open_long_market(
                symbol=symbol, price=self.future_prices[symbol[:-4]], usdt=usdt, ratio=ratio
            )

    @_process_order
    def buy_short_market(self, symbol, usdt=None, ratio=None):
        if self.symbols_state[symbol]["order_count"] < self.max_order_count:
            return self.order_handler.open_short_market(
                symbol=symbol, price=self.future_prices[symbol[:-4]], usdt=usdt, ratio=ratio
            )

    @_process_order
    def sell_long_market(self, symbol, ratio):
        return self.order_handler.close_long_market(symbol=symbol, price=self.future_prices[symbol[:-4]], ratio=ratio)

    @_process_order
    def sell_short_market(self, symbol, ratio):
        return self.order_handler.close_short_market(symbol=symbol, price=self.future_prices[symbol[:-4]], ratio=ratio)

    def _postprocess_order(self, order):
        symbol = order.symbol
        if self._is_buy_or_sell(order) == "BUY":
            self.symbols_state[symbol]["order_count"] += 1
            self.symbols_state[symbol]["positionSize"] = float(
                Decimal(self.symbols_state[symbol]["positionSize"] + order.origQty)
            )
            self.symbols_state[symbol]["positionSide"] = order.positionSide

        elif self._is_buy_or_sell(order) == "SELL":
            self.symbols_state[symbol]["positionSize"] = float(
                Decimal(self.symbols_state[symbol]["positionSize"] - order.origQty)
            )
            if self.symbols_state[symbol]["positionSize"] == 0:
                self.symbols_state[symbol] = self._init_symbol_state()

        self._process_order_record(order)
        # message = f"Order {order.clientOrderId}: {order.side} {order.positionSide} {order.type} - {order.symbol} / Qty: {order.origQty}, Price: ${order.avgPrice}"

    def _process_order_record(self, order):
        self.order_recorder.test_order_to_order_dict(order, self.test_current_time)

    @staticmethod
    def _is_buy_or_sell(order):
        if ((order.side == OrderSide.BUY) & (order.positionSide == PositionSide.LONG)) or (
            (order.side == OrderSide.SELL) & (order.positionSide == PositionSide.SHORT)
        ):
            return "BUY"
        elif ((order.side == OrderSide.SELL) & (order.positionSide == PositionSide.LONG)) or (
            (order.side == OrderSide.BUY) & (order.positionSide == PositionSide.SHORT)
        ):
            return "SELL"
        else:
            raise ValueError("Cannot check order is buy or sell")

    def update(self, test_current_time, future_prices):
        self.test_current_time = test_current_time
        self.future_prices = future_prices

    def end_bt(self):
        return self.order_recorder.return_records()


if __name__ == "__main__":
    tm = BackTestBinanceTradeManager(init_usdt=1000, max_order_count=3)
    tm.buy_long_market(symbol="ethusdt", price=2783, usdt=100)
    tm.sell_long_market(symbol="ethusdt", price=2700, ratio=0.5)
    # tm.buy_short_market("ethusdt", price=2783, usdt=100)
    # tm.sell_short_market("ethusdt", price=2700, ratio=1)
