import configparser
import threading
import time

from arte.system.client import Client
from arte.data import SocketDataManager
from arte.data.common_symbol_collector import CommonSymbolCollector

cfg = configparser.ConfigParser()
cfg.read("/media/park/hard2000/arte_config/config.ini")
config = cfg["REAL"]

mode = config["MODE"]
api_key = config["API_KEY"]
secret_key = config["SECRET_KEY"]
use_bot = config.getboolean("USE_BOT")

cl = Client(mode, api_key, secret_key, req_only=True)

reqc = cl.request_client
ex_info_per_symbol = reqc.get_exchange_information().symbols

for ex_info in ex_info_per_symbol:
    print(
        ex_info.symbol, ex_info.status, ex_info.baseAsset, ex_info.quoteAsset, ex_info.quantityPrecision,
    )


"""
self.symbol = ""
self.status = ""
self.maintMarginPercent = 0.0
self.requiredMarginPercent = 0.0
self.baseAsset = ""
self.quoteAsset = ""
self.pricePrecision = None
self.quantityPrecision = None
self.baseAssetPrecision = None
self.quotePrecision = None
self.orderTypes = list()
self.timeInForce = list()
self.filters = list()

"""
