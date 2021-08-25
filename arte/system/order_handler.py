"""
OrderManager의 역할
1. 함수 하나로 사용하는 쉬운 오더 (파라미터를 최소화 시키는 방식 - 코딩 실수를 막기 위해)
2. 신청된 오더들을 기록 (오더 리스트)
3. 신청된 오더가 체결된 경우를 체크 (메인루프 안에서 정기적으로 확인 및 갱신)
4. 체결된 오더의 기록

나머지는 다 이미 api화가 되어있는듯?
- 오더 취소
- 포지션 / 밸런스 계산 및 시각화
- 레버리지 / 마진 변화
"""
import math
import time
from functools import wraps

from binance_f.constant.test import *
from binance_f.base.printobject import *
from binance_f.model.constant import *


def get_timestamp():
    return int(time.time())  # * 1000)


def _postprocess_order(method):
    @wraps(method)
    def _impl(self, *args, **kwargs):
        order = method(self, *args, **kwargs)
        message = f"Order {order.clientOrderId}: {order.side} {order.positionSide} {order.type} - {order.symbol} / Qty: {order.origQty}, Price: ${order.avgPrice}"
        self.bot.sendMessage(message)
        print(message)
        self.account.update()
        self.order_list.append(order)
        self.order_count += 1
        return order

    return _impl


class OrderHandler:
    """
    "특정" 에셋을 위한 오더 핸들러
    인스턴스를 만들때 symbol로 넣는 에셋 하나만을 거래합니다.
    다수의 에셋을 거래하고 싶다면 여러개의 오더핸들러가 필요합니다.
    실제 헷지 모드 세팅에서만 작동하며, 가상의 원웨이 모드를 구성합니다. 
    """

    def __init__(self, request_client, account, bot, symbol: str):
        self.request_client = request_client
        self.account = account
        self.bot = bot
        self.order_list = []
        self.order_count = 0
        self.symbol = symbol
        self.manager = None

    @_postprocess_order
    def _limit(self, order_side: OrderSide, position_side: PositionSide, price: float, quantity: float):
        result = self.request_client.post_order(
            symbol=self.symbol,
            side=order_side,
            positionSide=position_side,
            ordertype=OrderType.LIMIT,
            price=float(price),
            quantity=quantity,
            timeInForce=TimeInForce.GTC,
            newClientOrderId=self._generate_order_id(),
        )
        return result

    @_postprocess_order
    def _market(self, order_side: OrderSide, position_side: PositionSide, quantity: float):
        result = self.request_client.post_order(
            symbol=self.symbol,
            side=order_side,
            positionSide=position_side,
            ordertype=OrderType.MARKET,
            quantity=quantity,
            newClientOrderId=self._generate_order_id(),
            newOrderRespType=OrderRespType.RESULT,
        )
        return result

    def buy_limit(self, position_side: PositionSide, price, usdt=None, ratio=None):
        if bool(usdt) ^ bool(ratio):
            if ratio:
                usdt = self.account.usdt_balance * ratio
            if self.manager.positionSide in [PositionSide.INVALID, position_side]:
                return self._limit(OrderSide.BUY, position_side, price, self._usdt_to_quantity(usdt, price))
            else:
                print(
                    f"Cannot execute buy_{position_side}, you have already opened {self.manager.positionSide} position."
                )
                return None
        else:
            raise ValueError("You have to pass either quantity or ratio.")

    def buy_market(self, position_side: PositionSide, price, usdt=None, ratio=None):
        if bool(usdt) ^ bool(ratio):
            if ratio:
                usdt = self.account.usdt_balance * ratio
            if self.manager.positionSide in [PositionSide.INVALID, position_side]:
                return self._market(OrderSide.BUY, position_side, self._usdt_to_quantity(usdt, price))
            else:
                print(
                    f"Cannot execute buy_{position_side}, you have already opened {self.manager.positionSide} position."
                )
                return None
        else:
            raise ValueError("You have to pass either quantity or ratio.")

    def sell_limit(self, position_side: PositionSide, price, ratio):
        if self.manager.positionSide == position_side:
            return self._limit(
                OrderSide.SELL, position_side, price, self._asset_ratio_to_quantity(position_side, ratio)
            )
        else:
            print(f"Cannot execute sell_{position_side}, you dont have any {position_side} position.")
            return None

    def sell_market(self, position_side: PositionSide, ratio):
        if self.manager.positionSide == position_side:
            return self._market(OrderSide.SELL, position_side, self._asset_ratio_to_quantity(position_side, ratio))
        else:
            print(f"Cannot execute sell_{position_side}, you dont have any {position_side} position.")
            return None

    def _get_ticker_price(self):
        result = self.request_client.get_symbol_price_ticker(symbol=self.symbol)
        return result[0].price

    def _usdt_to_quantity(self, usdt, price, unit_float=3):
        return math.floor((usdt / price) * (10 ** unit_float)) / (10 ** unit_float)

    def _asset_ratio_to_quantity(self, position_side: PositionSide, ratio, unit_float=3):
        asset_quantity = abs(self.account.positions[self.symbol][position_side].positionAmt)
        return math.floor((asset_quantity * ratio) * (10 ** unit_float)) / (10 ** unit_float)

    def _generate_order_id(self):
        _id = self.symbol + str(get_timestamp()) + f"num{self.order_count:05}"
        return _id

    def update(self):
        """
        주 목적 - 리미트 주문이 filled 되는지를 검사하여 로컬에 반영
        """
        for o in self.order_list:
            if o.type == "LIMIT":
                if o.status == "NEW":
                    result = self.request_client.get_order(self.symbol, origClientOrderId=o.clientOrderId)
                    if o.status != result.status:
                        print(
                            f"""Status Changed - Order {result.clientOrderId}: {o.status} -> {result.status} /
                            {result.side} {result.type} - {result.symbol} / Qty: {result.origQty}, Price: ${result.price}"""
                        )
                        o.status = result.status  # NEEDFIX: it should update whole instance
                        self.account.update()


if __name__ == "__main__":
    from arte.client import Client
    from arte.system.account import Account
    from arte.system.telegram_bot import SimonManager

    cl = Client(mode="TEST", req_only=True)
    oh = OrderHandler(cl.request_client, Account(cl.request_client), SimonManager(), "ETHUSDT")
