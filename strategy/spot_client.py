#! /usr/bin/python3
import os
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from binance.enums import HistoricalKlinesType
import math
import time
import logging as logger
import json
import signal

class BNClient:
    def __init__(self, client):
        self._client = client

    def trade_fee(self):
        return 0.00075

    def get_cur_sell(self, symbol):
        depth = self._client.get_order_book(symbol=symbol)
        if depth is None or 'asks' not in depth or len(depth['asks']) < 1:
            return None
        return depth['asks'][0]

    def get_cur_buy(self, symbol):
        depth = self._client.get_order_book(symbol=symbol)
        if depth is None or 'bids' not in depth or len(depth['bids']) < 1:
            return None
        return depth['bids'][0]

    def is_ok(self):
        r = self._client.get_account()
        return r is not None and r.get('canTrade', False) is True;

    def get_asset_balance(self, symbol):
        r = self._client.get_account()
        if r is None or 'balances' not in r:
            return None
        for tp in r.get('balances', []):
            if tp.get('asset', '') == symbol:
                return tp
        return None

    def get_all_open_orders(self, symbol):
        r = self._client.get_open_orders(symbol = symbol)
        res = [x for x in r if x['symbol'] == symbol]
        return res

    def get_order(self, symbol, order_id):
        r = self._client.get_order(symbol = symbol, origClientOrderId = order_id)
        return r

    def cancel_order(self, symbol, order_id):
        r = self._client.cancel_order(symbol = symbol, origClientOrderId = order_id)
        return r

    def create_limit_order(self, symbol, side, quantity, price, client_order_id, time_in_force = 'GTC'):
        r = self._client.create_order(
            symbol = symbol,
            side = side,
            quantity = quantity,
            price = price,
            type = Client.ORDER_TYPE_LIMIT,
            timeInForce = 'GTC',
            newClientOrderId = client_order_id,
            timestamp = int(time.time()))
        return r
        
    def account_info(self):
        r = self._client.get_account()
        print(r)

    def get_historical_klines(self, symbol, interval, start_str, end_str = None, limit = 500):
        r = self._client.get_historical_klines(
            symbol = symbol,
            interval = interval,
            start_str = start_str,
            end_str = end_str,
            limit = limit,
            klines_type = HistoricalKlinesType.SPOT
        )
