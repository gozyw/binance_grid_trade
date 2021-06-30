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
import json
import signal

def signal_handler(sig_num, frame):
    logger.info("receive signal %s set is_stop True", sig_num)
    global is_stop
    is_stop = True

def create_client(client_type, api_key, api_secret):
    if client_type == "spot":
        return BNClient(Client(api_key, api_secret))
    else:
        logger.error("unsupport client type")
        return None

def create_strategy(client, config):
    if config['strategy_type'] == "grid_v1":
        return GridRun(client = client, config = config)
    else:
        logger.error("unsupport strategy type")
        return None

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('usage: %s config_file' % sys.argv[0])
        sys.exit(1)

    config = None
    with open(sys.argv[1], 'r') as fh:
        content = ''.join(fh.readlines())
        config = json.loads(content)
    
    api_key = config['api_key']
    api_secret = config['api_secret']

    init_logger('run.log', level = logger.INFO)

    runners = []
    for cfg in config['strategy']:
        client = create_client(cfg['client_type'], api_key, api_secret)
        if not client:
            continue
        strategy = create_strategy(client, cfg)
        if not strategy:
            continue
        runners.append(strategy)
    if not runners:
        logger.info("no runner")
        sys.exit(0)
    global is_stop
    is_stop = False

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGUSR1, signal_handler)
    signal.signal(signal.SIGUSR2, signal_handler)    

    st = time.time()
    gain_map = {}
    while not is_stop:
        for runner in runners:
            try:
                runner.work_loop()
            except Exception as e:
                logger.exception(e)
        if time.time() - st > 10:
            changed = False
            for runner in runners:
                if runner.strategy_id not in gain_map:
                    gain_map[runner.strategy_id] = runner.get_total_gain()
                    changed = True
                else:
                    if runner.get_total_gain() > gain_map[runner.strategy_id]:
                        gain_map[runner.strategy_id] = runner.get_total_gain()
                        changed = True
            if changed:
                logger.info("gain %s", gain_map)
            st = time.time()
        time.sleep(1)
    logger.info("gain %s", gain_map)    
    logger.info("i'm exitted")    

