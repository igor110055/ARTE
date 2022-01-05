#!/usr/bin/env python3
from setuptools import setup

setup(
    name="arte",
    version="1.0.2",
    packages=[
        "binance_f",
        "binance_f.impl",
        "binance_f.impl.utils",
        "binance_f.exception",
        "binance_f.model",
        "binance_f.base",
        "binance_f.constant",
        "arte",
        "arte.data",
        "arte.indicator",
        "arte.test_system",
        "arte.test_system.binance",
        "arte.test_system.upbit",
        # "arte.strategy",
        "arte.system",
        "arte.system.binance",
        "arte.system.upbit"
    ],
    install_requires=[
        "black",
        "requests",
        "python-telegram-bot",
        "apscheduler==3.6.3",
        "websocket-client",
        "urllib3",
        "tzlocal<3.0",
        "pyupbit",
        "python-binance",
        "tqdm",
        "pandas",
        "numpy",
        # "ta-lib",
    ],
)
