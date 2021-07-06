#! /usr/bin/python3
import os
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from binance.enums import HistoricalKlinesType
import math
import time
import logging as logger
import json
import signal

class MockClient:
    def __init__(self, record_file, target_symbol, base_symbol, max_line = 100000):
        self.record = []
        with open(record_file, 'r') as fh:
            for line in fh.readlines():
                content = line.split(' ')
                self.record.append([float(content[1]), float(content[2])])
                if len(self.record) >= max_line:
                    break
        self.cur_index = 0
        self.base_val = 1000000.
        self.target_val = 0.
        self.target_symbol = target_symbol
        self.base_symbol = base_symbol
        self.close_orders = {}
        self.open_orders = {}

    def next(self):
        sell_price = self.get_cur_sell('')
        buy_price = self.get_cur_buy('')
        sr = []
        for oid in self.open_orders.keys():
            order = self.open_orders[oid]
            if order['side'] == 'SELL' and order['price'] < sell_price:
                sr.append(oid)
                self.base_val += order['price'] * order['origQty'] * (1.0 - self.trade_fee())
                self.target_val -= order['origQty']
                self.open_orders[oid]['executedQty'] = order['origQty']
                self.open_orders[oid]['status'] = 'FILLED'
            elif order['side'] == 'BUY' and order['price'] > buy_price:
                sr.append(oid)
                self.base_val -= order['price'] * order['origQty'] * (1.0 + self.trade_fee())
                self.target_val += order['origQty']
                self.open_orders[oid]['executedQty'] = order['origQty']
                self.open_orders[oid]['status'] = 'FILLED'
        for oid in sr:
            self.close_orders[oid] = self.open_orders[oid]
            self.open_orders.pop(oid)
        self.cur_index += 1
        
    def has_next(self):
        return self.cur_index + 1 < len(self.record)
    
    def trade_fee(self):
        return 0.00075

    def get_cur_sell(self, symbol):
        return self.record[self.cur_index][0]

    def get_cur_buy(self, symbol):
        return self.record[self.cur_index][1]
        
    def is_ok(self):
        return True
    
    def get_asset_balance(self, symbol):
        if symbol == self.base_symbol:
            return self.base_val
        elif symbol == self.target_symbol:
            return self.target_val
        
    def get_all_open_orders(self, symbol):
        return self.open_orders.values()

    def get_order(self, symbol, order_id):
        if order_id in self.open_orders:
            return self.open_orders[order_id]
        elif order_id in self.close_orders:
            return self.close_orders[order_id]
        return {}

    def cancel_order(self, symbol, order_id):
        if order_id in self.open_orders:
            self.open_orders[order_id]['status'] = 'CANCELED'
            self.close_orders[order_id] = self.open_orders[order_id]
            self.open_orders.pop(order_id)

    def create_limit_order(self, symbol, side, quantity, price, client_order_id, time_in_force = 'GTC'):
        order = {
            'symbol': symbol,
            'side': side,
            'origQty': quantity,
            'executedQty': 0.0,
            'price': price,
            'type': 'LIMIT',
            'clientOrderId': client_order_id,
            'status': "NEW"
        }
        if client_order_id in self.open_orders or client_order_id in self.close_orders:
            raise Exception('duplicated order id')
        self.open_orders[client_order_id] = order
        return order
        
    def account_info(self):
        return None
