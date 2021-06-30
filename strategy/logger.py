#! /usr/bin/python3
import os
import logging as logger
from logging import handlers

def init_logger(filename,
                level = logger.INFO,
    		fmt = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                when = 'D',
                backup_count = 5):
    mlogger = logger.getLogger()
    format_str = logger.Formatter(fmt)
    mlogger.setLevel(level)
    sh = logger.StreamHandler()
    sh.setFormatter(format_str)
    th = handlers.TimedRotatingFileHandler(
        filename = filename,
        when = when,
        backupCount = backup_count,
	encoding = 'utf-8')
    th.setFormatter(format_str)
    mlogger.addHandler(sh)
    mlogger.addHandler(th)
