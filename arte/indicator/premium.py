"""
Premium Indictor
Currently, only for upbit-binance premium
"""


class Premium:
    @staticmethod
    def calc(upbit_obj, binance_obj, exchange_rate):
        premium_dict = dict()
        for upbit_price, binance_price in zip(upbit_obj.price.items(), binance_obj.price.items()):
            if upbit_price[1] is not None and binance_price[1] is not None:
                premium_dict[binance_price[0]] = (
                    (float(upbit_price[1]) / (float(binance_price[1]) * exchange_rate)) - 1
                ) * 100

        return premium_dict
