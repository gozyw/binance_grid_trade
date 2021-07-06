#! /usr/bin/python3
import os
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from binance.exceptions import BinanceAPIException
import math
import time
import logging as logger
import json
import signal

class FileCache:
    def __init__(self, file_name):
        self.file_name = file_name
        cache_dir = os.path.abspath(os.path.join(os.path.dirname(
                    os.path.realpath(__file__)), '../data'))
        if not os.path.exists(cache_dir):
            os.mkdir(cache_dir)
        self.cache_file_name = os.path.join(cache_dir, self.file_name + '.data')

    def get_local_cache(self):
        if not os.path.exists(self.cache_file_name):
            return {}
        with open(self.cache_file_name, 'r') as fh:
            con = ''.join(fh.readlines())
            if len(con) < 2:
                return {}
            content = json.loads(con)
            return content
        return {}

    def save_local_cache(self, content):
        with open(self.cache_file_name, 'w') as fh:
            fh.write(json.dumps(content, indent = 4) + '\n')
        
