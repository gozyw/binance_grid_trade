#! /usr/bin/python3
import os
import sys
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
import math
import time
import logging as logger
from strategy.logger import init_logger
from strategy.grid_v1 import GridRun
from strategy.spot_client import BNClient
from strategy.mock_client import MockClient
import json
import signal

def signal_handler(sig_num, frame):
    logger.info("receive signal %s set is_stop True", sig_num)
    global is_stop
    is_stop = True
    
def create_strategy(client, config):
    if config['strategy_type'] == "grid_v1":
        return GridRun(client = client, config = config, verbose = False)
    else:
        logger.error("unsupport strategy type")
        return None

if __name__ == '__main__':
    
    config = {
        "strategy_id": "test02",
        "low_bound": 150,
        "up_bound": 400,
        "total_cash": 1250,
        "grid_num": 110,
        "target_symbol": "ADA",
        "base_symbol": "USDT",
        "price_round_num": 2,
        "quantity_round_num": 4,
        "sell_greedy_x": 1.00,
        "buy_greedy_x": 1.0,
        "grid_mode": "equal_percent",
        "run_target": "join",
        "client_type" : "spot",
        "strategy_type" : "grid_v1",
        "cache_type" : "mem"
    }

    init_logger('mock.log', level = logger.INFO)
    hi = [i for i in range(20, 80)]
    hs = [1.003]
    bl = config['up_bound'] / config['low_bound']
    ar = []
    mx, mi, ms = 0., -1, -1
    for i in hi:
        dg = math.pow(bl, 1.0 / i)
        for si in hs:
            config['grid_num'] = i
            config['sell_greedy_x'] = si
            mock_client = MockClient('bnb.record', 'BNB', 'USDT')
            runner = create_strategy(mock_client, config)
            runner.order_sleep = 0.
            while mock_client.has_next():
                runner.work_loop()
                mock_client.next()
            gain = runner.get_total_gain()
            ar.append([gain, i, config['sell_greedy_x']])
            logger.info('g:%s, gx:%s, gain:%s', i, config['sell_greedy_x'], runner.get_total_gain())
    sar = sorted(ar, key = lambda x: -x[0])
    for i in range(min(20, len(sar))):
        logger.info(sar[i])

