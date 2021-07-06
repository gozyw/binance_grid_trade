#! /usr/bin/python3
import os
import sys
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from binance.exceptions import BinanceAPIException
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

    init_logger('record.log', level = logger.INFO)

    client = create_client('spot', api_key, api_secret)

    global is_stop
    is_stop = False

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGUSR1, signal_handler)
    signal.signal(signal.SIGUSR2, signal_handler)    

    st = time.time()
    coin_pair = ['ATAUSDT', 'BNBUSDT', 'ADAUSDT']
    fh = {
        'ATAUSDT': open('ata.record', 'a+'),
        'BNBUSDT': open('bnb.record', 'a+'),
        'ADAUSDT': open('ada.record', 'a+'),
    }
    last_buy = {}
    last_sell = {}
    while not is_stop:
        for cp in coin_pair:
            try:
                s = client.get_cur_sell(symbol=cp)
                b = client.get_cur_buy(symbol=cp)
                if s and b:
                    if cp not in last_buy:
                        last_buy[cp] = -1.0
                        last_sell[cp] = -1.0
                    if str(s[0]) != str(last_sell[cp]) or str(b[0]) != str(last_buy[cp]):
                        fh[cp].write('%s %s %s\n' % (time.time(), s[0], b[0]))
                        last_buy[cp], last_sell[cp] = b[0], s[0]
                
            except Exception as e:
                logger.error(e)
        time.sleep(1)
    for p in fh.values():
        p.close()
