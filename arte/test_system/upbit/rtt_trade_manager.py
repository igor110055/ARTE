"""
Upbit
"""
import sys
from functools import wraps
from decimal import Decimal, getcontext

getcontext().prec = 6

from binance_f.model.constant import *
from .test_account import Account
from .test_order_handler import OrderHandler
from arte.test_system.test_order_recorder import TestOrderRecorder


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


class RTTUpbitTradeManager:
    def __init__(self, init_krw=100000, *args, **kwargs):
        self.account = Account(init_balance=init_krw)
        self.order_handler = OrderHandler(self.account)

        backtest_id = None
        if "backtest_id" in kwargs:
            backtest_id = kwargs["backtest_id"]

        self.order_recorder = TestOrderRecorder(backtest_id=backtest_id)

        self.test_current_time = None
        self.orderbook = None

        self.bot = None
        if "bot" in kwargs:
            self.bot = kwargs["bot"]
        if "max_order_count" in kwargs:
            self.max_order_count = kwargs["max_order_count"]

        # state manage
        self.symbols_state = dict()

    def _init_symbol_state(self):
        return dict(order_count=0, positionSize=0, positionSide=PositionSide.INVALID)

    def calc_market_order_price_qty(self, symbol, buy_or_sell, krw=None):
        if buy_or_sell == "BUY":
            ask_price = self.orderbook[symbol]["ask_list"][0]
            ask_qty = self.orderbook[symbol]["ask_list"][1]
            if ask_price * ask_qty >= krw:
                return ask_price
            else:
                return None
        elif buy_or_sell == "SELL":
            return self.orderbook[symbol]["bid_list"][0]

    @_process_order
    def buy_long_market(self, symbol, krw=None, ratio=None):
        if self.symbols_state[symbol]["order_count"] < self.max_order_count:
            market_trade_price = self.calc_market_order_price_qty(symbol=symbol[4:], buy_or_sell="BUY", krw=krw)
            if market_trade_price:
                return self.order_handler.open_long_market(
                    symbol=symbol, price=market_trade_price, krw=krw, ratio=ratio
                )
            else:
                return None

    @_process_order
    def sell_long_market(self, symbol, ratio):
        market_trade_price = self.calc_market_order_price_qty(symbol=symbol[4:], buy_or_sell="SELL")
        return self.order_handler.close_long_market(symbol=symbol, price=market_trade_price, ratio=ratio)

    def _postprocess_order(self, order):
        symbol = order.symbol
        if order.side == OrderSide.BUY:
            self.symbols_state[symbol]["order_count"] += 1
            self.symbols_state[symbol]["positionSize"] = float(
                Decimal(self.symbols_state[symbol]["positionSize"] + order.origQty)
            )
            self.symbols_state[symbol]["positionSide"] = order.positionSide

        elif order.side == OrderSide.SELL:
            self.symbols_state[symbol]["positionSize"] = float(
                Decimal(self.symbols_state[symbol]["positionSize"] - order.origQty)
            )
            if self.symbols_state[symbol]["positionSize"] < sys.float_info.epsilon:
                self.symbols_state[symbol] = self._init_symbol_state()

        self._process_order_record(order)

    def _process_order_record(self, order):
        self.order_recorder.test_order_to_order_dict(order, self.test_current_time)

    def update(self, test_current_time, orderbook):
        self.test_current_time = test_current_time
        self.orderbook = orderbook


if __name__ == "__main__":
    from arte.data.upbit_orderbook_parser import UpbitOrderbookParser

    tm = RTTUpbitTradeManager(init_krw=400000, max_order_count=3)
    symbol = "KRW-AXS"

    orderbook = UpbitOrderbookParser([symbol])
    orderbook._orderbook[symbol[4:]] = {
        "ask_list": [101, 1],
        "bid_list": [99, 1],
        "total_ask_size": 100,
        "total_bid_size": 100,
    }
    tm.update(test_current_time=0, orderbook=orderbook)
    tm.buy_long_market(symbol=symbol, krw=100000)
    tm.sell_long_market(symbol=symbol, ratio=1)

