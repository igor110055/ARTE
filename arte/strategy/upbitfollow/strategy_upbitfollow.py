from collections import deque

import numpy as np
from transitions import Machine

from arte.indicator import IndicatorManager
from arte.indicator import Indicator

from arte.system.utils import Timer


def _symbolize_binance(pure_symbol, upper=False):
    bsymbol = pure_symbol.lower() + "usdt"
    if upper:
        bsymbol = bsymbol.upper()
    return bsymbol


def _symbolize_upbit(pure_symbol):
    usymbol = "KRW-" + pure_symbol.upper()
    return usymbol


class SignalState:

    states = ["idle", "buy_state", "buy_order_state", "sell_state", "sell_order_state"]

    def __init__(self, symbol, tm):
        self.symbol = symbol
        self.tm = tm

        transitions = [
            {"trigger": "proceed", "source": "idle", "dest": "sell_state", "conditions": "have_open_position"},
            {"trigger": "proceed", "source": "idle", "dest": "buy_state"},
            {
                "trigger": "proceed",
                "source": "buy_state",
                "dest": "buy_order_state",
                "conditions": ["binance_price_up", "upbit_price_stay"],  # , "premium_undershoot_mean"],
                "after": "buy_long",
            },
            # {
            #     "trigger": "proceed",
            #     "source": "sell_state",
            #     "dest": "sell_order_state",
            #     "conditions": ["price_decrease"],
            #     "after": "sell_long",
            # },
            {
                "trigger": "proceed",
                "source": "sell_state",
                "dest": "sell_order_state",
                "conditions": ["premium_increase"],
                "after": "sell_long",
            },
            {
                "trigger": "proceed",
                "source": "sell_state",
                "dest": "sell_order_state",
                "conditions": ["check_timeup"],
                "after": "sell_long",
            },
            {"trigger": "initialize", "source": "*", "dest": "idle"},  # , "before": "print_end"},
        ]
        m = Machine(
            model=self,
            states=SignalState.states,
            transitions=transitions,
            initial="idle",
            after_state_change="auto_proceed",
        )

        self.is_open = False
        self.premium_at_buy = None
        self.price_at_buy = None
        self.timer = Timer()

    def print_end(self, **kwargs):
        print(f"From {self.state} go back to Idle state.")

    def auto_proceed(self, **kwargs):
        if not self.state == "idle":
            if not self.proceed(**kwargs):
                self.initialize()

    def have_open_position(self, **kwargs):
        return self.is_open

    # Buy logic and ordering
    # def premium_over_threshold(self, **kwargs):
    #     premium = kwargs["premium_q"][-1]
    #     criteria_premium = kwargs["criteria_premium"]
    #     return premium > criteria_premium * 1.2

    def premium_undershoot_mean(self, **kwargs):
        premium_q = list(kwargs["premium_q"])
        change_rate = premium_q[-1] / (np.mean(premium_q))
        return change_rate < 0.99

    def binance_price_up(self, **kwargs):
        binance_price_q = kwargs["binance_price_q"]
        # change_rate = binance_price_q[-1] / binance_price_q[0]
        change_rate = binance_price_q[-1] / np.mean([binance_price_q[i] for i in range(8)])
        return change_rate > 1.005

    def upbit_price_stay(self, **kwargs):
        price_q = kwargs["price_q"]
        # change_rate = price_q[-1] / price_q[0]
        change_rate = price_q[-1] / np.mean([price_q[i] for i in range(9)])
        return change_rate < 1.001

    def buy_long(self, **kwargs):
        self.initialize()
        print("Passed all signals, Order Buy long")
        if self.tm.buy_long_market(symbol=self.symbol, krw=100000):
            self.is_open = True
            self.premium_at_buy = kwargs["premium_q"][-1]
            self.price_at_buy = kwargs["trade_price"]  # temp val - it need to change to result of order
            self.timer.start(kwargs["current_time"], "120S")

    # Sell logic and ordering
    def price_decrease(self, **kwargs):
        cur_price = kwargs["price_q"][-1]
        return cur_price < self.price_at_buy

    def premium_increase(self, **kwargs):
        premium_q = kwargs["premium_q"]
        return premium_q[-1] > (self.premium_at_buy * 1.1)

    def check_timeup(self, **kwargs):
        return self.timer.check_timeup(kwargs["current_time"])

    # def high_price(self, **kwargs):
    #     return kwargs["future_price"][self.symbol] > self.price_at_buy

    def sell_long(self, **kwargs):
        self.initialize()
        print("Passed all signals, Order Sell long")
        if self.tm.sell_long_market(symbol=self.symbol, ratio=1):
            self.is_open = False
            self.premium_at_buy = None
            self.price_at_buy = None


class ArbitrageBasic:
    """
    Upbit-Binance Pair Arbitrage 기초 전략
    """

    def __init__(self, trade_manager):
        self.tm = trade_manager
        self.im = IndicatorManager(indicators=[Indicator.PREMIUM])

        self.premium_threshold = 3
        self.premium_assets = []
        self.asset_signals = {}
        self.q_maxlen = 10
        self.init_price_counter = 0
        self.dict_price_q = {}
        self.dict_binance_price_q = {}
        self.dict_premium_q = {}

    def update(self, **kwargs):
        self.upbit_price = kwargs["upbit_price"]
        self.binance_spot_price = kwargs["binance_spot_price"]
        self.exchange_rate = kwargs["exchange_rate"]
        self.except_list = kwargs["except_list"]
        self.current_time = kwargs["current_time"]
        self.im.update_premium(self.upbit_price, self.binance_spot_price, self.exchange_rate)
        print(f'Upbit: {self.upbit_price.price}')
        print(f'Bspot: {self.binance_spot_price.price}')

    def initialize(self, common_symbols, except_list):
        self.except_list = except_list
        self.symbols_wo_excepted = []
        for symbol in common_symbols:
            if symbol not in self.except_list:
                self.symbols_wo_excepted.append(symbol)

        for symbol in self.symbols_wo_excepted:
            self.asset_signals[symbol] = SignalState(symbol=_symbolize_upbit(symbol), tm=self.tm)
            self.dict_price_q[symbol] = deque(maxlen=self.q_maxlen)
            self.dict_binance_price_q[symbol] = deque(maxlen=self.q_maxlen)
            self.dict_premium_q[symbol] = deque(maxlen=self.q_maxlen)

    def run(self):
        for symbol in self.symbols_wo_excepted:
            self.dict_price_q[symbol].append(self.upbit_price.price[symbol])
            self.dict_binance_price_q[symbol].append(self.binance_spot_price.price[symbol])
            self.dict_premium_q[symbol].append(self.im[Indicator.PREMIUM][-1][symbol])
            self.init_price_counter += 1

        if self.init_price_counter >= (self.q_maxlen * len(self.symbols_wo_excepted)):
            for symbol in self.symbols_wo_excepted:
                self.asset_signals[symbol].proceed(
                    premium_q=self.dict_premium_q[symbol],
                    price_q=self.dict_price_q[symbol],
                    binance_price_q=self.dict_binance_price_q[symbol],
                    trade_price=self.upbit_price.price[symbol],
                    current_time=self.current_time,
                )
