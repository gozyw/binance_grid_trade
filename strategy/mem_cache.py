#! /usr/bin/python3
import os
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from binance.exceptions import BinanceAPIException
import math
import time
import logging as logger
import json
import copy
import signal

class MemCache:
    def __init__(self):
        self.content = {}
        
    def get_local_cache(self):
        return self.content

    def save_local_cache(self, content):
        self.content = copy.deepcopy(content)
        
