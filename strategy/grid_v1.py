#! /usr/bin/python3
import os
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from binance.exceptions import BinanceAPIException
import math
import time
import logging as logger
import json
import signal
from strategy.file_cache import FileCache
from strategy.mem_cache import MemCache

class GridRun:
    def __init__(self, client, config, verbose = True):
        self.order_sleep = 0.01
        self.unique_order_id = 0
        self.verbose = verbose
        self.client = client
        self.low_bound = config.get('low_bound')
        self.up_bound = config.get('up_bound')
        self.total_cash = config.get('total_cash')
        self.grid_num = config.get('grid_num')
        self.target_symbol = config.get('target_symbol')
        self.base_symbol = config.get('base_symbol')
        self.strategy_id = config.get('strategy_id')
        self.price_round_num = config.get('price_round_num')
        self.quantity_round_num = config.get('quantity_round_num')
        self.sell_greedy_x = config.get('sell_greedy_x', 1.0)
        self.buy_greedy_x = config.get('buy_greedy_x', 1.0)
        self.grid_mode = config.get('grid_mode', 'equal_percent')
        self.run_target = config.get('run_target', 'join')
        self.trade_symbol = self.target_symbol + self.base_symbol
        self.cache_type = config.get('cache_type', 'file')
        if self.cache_type == 'file':
            self.cache_client = FileCache(self.strategy_id)
        elif self.cache_type == 'mem':
            self.cache_client = MemCache()
        else:
            raise Exception('unsupport cache type')
            
        if self.run_target == "quit":
            logger.info("quit strategy of %s", self.strategy_id)
            self.quit_all()
            return
        if self.grid_mode == 'equal_percent':
            pper = math.pow(self.up_bound / self.low_bound, 1.0 / self.grid_num)
            if pper - 2. * self.client.trade_fee() <= 1.001:
                raise Exception("grid too crowd")
            if self.verbose:
                logger.info("gain per grid without trade fee: %s", pper)
            fp = self.low_bound
            self.flags = [round(fp, self.price_round_num)]
            for i in range(self.grid_num):
                fp = fp * pper
                clp = round(fp, self.price_round_num)
                if clp == self.flags[-1]:
                    raise Exception("too close")
                self.flags.append(clp)
        elif self.grid_mode == 'equal_delta':
            pdel = (self.up_bound - self.low_bound) * 1.0 / self.grid_num
            if pdel / self.up_bound - 2. * self.client.trade_fee() <= 0.001:
                raise Exception("grid too crowd")
            fp = self.low_bound
            self.flags = [round(fp, self.price_round_num)]
            for i in range(self.grid_num):
                fp = fp + self.pdel
                clp = round(fp, self.price_round_num)
                if clp == self.flags[-1]:
                    raise Exception("too close")
                self.flags.append(clp)
        else:
            raise Exception("unsupport grid mode %s" % (self.grid_mode))
        if self.verbose:        
            logger.info('all flag:%s grid_num %s', self.flags, self.grid_num)
        self.cash_per_flag = self.total_cash / self.grid_num
        self.last_open_orders = self.load_orders()
        self.remote_open_orders = self.get_open_orders()
        rid = set([s['clientOrderId'] for s in self.remote_open_orders])
        lid = set([s['clientOrderId'] for s in self.last_open_orders])
        rdl = set(rid) - set(lid)
        if len(rdl) > 0:
            logger.error("error remote order, delta: %s", rdl)
            raise Exception('error remote order')
        self.total_gain = self.load_total_gain()

    def get_total_gain(self):
        return self.total_gain

    def quit_all(self):
        self.last_open_orders = self.load_orders()
        self.remote_open_orders = self.get_open_orders()
        for od in self.remote_open_orders:
            while True:
                try:
                    r = self.client.cancel_order(symbol = self.trade_symbol, order_id = od['clientOrderId'])
                    if r and 'symbol' in r:
                        break
                except BinanceAPIException as e:
                    if e.code == -2013:
                        break
                except Exception as e:
                    logger.error(r)
                time.sleep(self.order_sleep * 10)
            time.sleep(self.order_sleep)
            if self.verbose:            
                logger.info('cancel order %s', r)
        self.last_open_orders = []
        self.save_last_open_orders()
        
    def get_local_cache(self):
        return self.cache_client.get_local_cache()

    def save_local_cache(self, content):
        self.cache_client.save_local_cache(content)

    def load_total_gain(self):
        cr = self.get_local_cache()
        return cr.get('total_gain', 0.)

    def save_total_gain(self):
        cr = self.get_local_cache()
        cr['total_gain'] = self.total_gain
        self.save_local_cache(cr)
        
    def load_orders(self):
        cr = self.get_local_cache()
        return cr.get('open_orders', [])

    def save_last_open_orders(self):
        cr = self.get_local_cache()
        cr['open_orders'] = self.last_open_orders
        self.save_local_cache(cr)

    def get_open_orders(self):
        orders = self.client.get_all_open_orders(self.trade_symbol)
        ret = [ord for ord in orders if ord['clientOrderId'].startswith(self.strategy_id)]
        return ret
    
    def get_cur_balance(self):
        asset = self.client.get_asset_balance(self.symbol)
        return float(asset['free']) + float(asset['locked'])

    def get_cur_buy(self):
        mk = self.client.get_cur_buy(self.trade_symbol)
        return float(mk[0])

    def get_cur_sell(self):
        mk = self.client.get_cur_sell(self.trade_symbol)
        return float(mk[0])

    #    def create_limit_order(self, symbol, side, quantity, price, client_order_id, time_in_force = 'GTC'):
    def create_order(self, side, quantity, price, flag_id):
        qstr = str(quantity).split('.')
        oid = '%s_%s_%s_%s_%s_%s' % (self.strategy_id, str(flag_id), qstr[0], qstr[1], str(int(time.time())) + str(self.unique_order_id), str(side))
        self.unique_order_id += 1
        if self.verbose:
            logger.info('try to order %s %s %s %s %s', side, quantity, price, flag_id, oid)
        rtc = 10
        last_exp = None
        while rtc > 0:
            try:
                r = self.client.create_limit_order(
                    symbol = self.trade_symbol,
                    side = side, quantity = quantity, price = price, client_order_id = oid)
                time.sleep(self.order_sleep * 10)
                crtc = 10
                if self.verbose:
                    logger.info(r)
                while crtc > 0:
                    ro = self.client.get_order(symbol = self.trade_symbol, order_id = oid)
                    if ro is not None and ro.get('clientOrderId') == oid:
                        if self.verbose:                        
                            logger.info('suc to order %s %s %s %s', side, quantity, price, flag_id)
                        return r
                    crtc -= 1
                    time.sleep(self.order_sleep * 10)
                raise Exception("create order check failed")
            except Exception as e:
                logger.exception(e)
                last_exp = e
                time.sleep(self.order_sleep * 10)
            rtc -= 1
        logger.exception(last_exp)
        rep = {
            "od_error":str(last_exp),
            "side": side,
            "origQty": quantity,
            "price": price,
            "clientOrderId": oid}
        return rep
        
    def init_order(self):
        for fid in range(self.grid_num):
            fp = round(self.flags[fid] * self.buy_greedy_x, self.price_round_num)
            if self.verbose:            
                logger.info('init order of %s', self.flags[fid])
            qua = round(self.cash_per_flag / fp, self.quantity_round_num)
            ret = self.create_order(Client.SIDE_BUY, qua, fp, fid)
            self.last_open_orders.append(ret)
            if 'od_error' in ret:
                logger.error('flag %s order failed %s', fp, ret['od_error'])
        self.save_last_open_orders()

    def check_order_dealed(self, cid):
        # until success
        while True:
            try:
                r = self.client.get_order(self.trade_symbol, cid)
                if 'symbol' not in r:
                    return False
                if float(r.get('executedQty', -1.0)) >= float(r.get('origQty', 0.0)) - 1e-8 and r.get('status', '') == 'FILLED':
                    return True
                if r.get('status', '') == 'CANCELED':
                    return False
            except BinanceAPIException as e:
                if e.code == -2013:
                    return False
                logger.error(e)
                time.sleep(self.order_sleep)                
            except Exception as e:
                logger.error(e)
                time.sleep(self.order_sleep)
        return False

    def get_sell_price(self, flag_id):
        fp = round(self.flags[flag_id] * self.sell_greedy_x, self.price_round_num)
        return fp

    def get_buy_price(self, flag_id):
        fp = round(self.flags[flag_id] * self.buy_greedy_x, self.price_round_num)
        return fp

    def check_and_commit(self):
        self.last_open_orders = self.load_orders()
        self.remote_open_orders = self.get_open_orders()        
        rid = set([s['clientOrderId'] for s in self.remote_open_orders])
        lid = set([s['clientOrderId'] for s in self.last_open_orders])
        if self.verbose:        
            logger.info("l-r:%s",set(lid) - set(rid))
            logger.info("r-l:%s",set(rid) - set(lid))
        lmap = {}
        for s in self.last_open_orders:
            lmap[s['clientOrderId']] = s
        new_last_open_orders = []
        for cid in lid:
            if cid in rid:
                new_last_open_orders.append(lmap[cid])
                continue
            od = lmap[cid]
            content = cid.split('_')
            qty = float(content[2] + '.' + content[3])
            flag_id = int(content[1])
            if self.verbose:            
                logger.info('lost order cid %s order:%s', cid, od)
            if 'od_error' in od or not self.check_order_dealed(cid):
                fp = od['price']
                if od['side'] == Client.SIDE_BUY:
                    fp = self.get_buy_price(flag_id)
                else:
                    fp = self.get_sell_price(flag_id)
                rqty = round(float(od['origQty']), self.quantity_round_num)
                ret = self.create_order(od['side'], rqty, fp, flag_id)
                new_last_open_orders.append(ret)
            elif od['side'] == Client.SIDE_BUY:
                sell_flag_id = flag_id + 1
                fp = self.get_sell_price(sell_flag_id)
                ret = self.create_order(Client.SIDE_SELL, qty, fp, sell_flag_id)
                new_last_open_orders.append(ret)
            elif od['side'] == Client.SIDE_SELL:
                buy_flag_id = flag_id - 1
                fp = self.get_buy_price(buy_flag_id)                
                qua = round(self.cash_per_flag / fp, self.quantity_round_num)
                ret = self.create_order(Client.SIDE_BUY, qua, fp, buy_flag_id)
                new_last_open_orders.append(ret)
                op = float(od['price'])
                cur_gain = (op - fp) * qty - (op + fp) * qty * self.client.trade_fee()
                self.total_gain += cur_gain
                self.save_total_gain()
        self.last_open_orders = new_last_open_orders
        self.save_last_open_orders()
        if len(self.load_orders()) == self.grid_num:
            return
        self.last_open_orders = self.load_orders()
        id_orders = {}
        for od in self.last_open_orders:
            if 'od_error' in od:
                pass
            i = int(od['clientOrderId'].split('_')[1])
            if i not in id_orders:
                id_orders[i] = [od]
            else:
                id_orders[i].append(od)
        for i in range(self.grid_num):
            if i in id_orders:
                has_buy = False
                for od in id_orders[i]:
                    if od['side'] == Client.SIDE_BUY:
                        has_buy = True
                if has_buy:
                    continue
                continue
            if i + 1 in id_orders:
                has_sell = False
                for od in id_orders[i + 1]:
                    if od['side'] == Client.SIDE_SELL:
                        has_sell = True
                if has_sell:
                    continue
            fp = round(self.flags[i] * self.buy_greedy_x, self.price_round_num)
            if self.verbose:            
                logger.info('reorder missing order of %s', self.flags[i])
            qua = round(self.cash_per_flag / fp, self.quantity_round_num)
            ret = self.create_order(Client.SIDE_BUY, qua, fp, i)
            self.last_open_orders.append(ret)
            time.sleep(self.order_sleep * 10)
        self.save_last_open_orders()
    
    def work_loop(self):
        if self.run_target == 'quit':
            return
        try:
            self.last_open_orders = self.load_orders()
            self.remote_open_orders = self.get_open_orders()
            if len(self.last_open_orders) == 0:
                ## firstly commit all buy order
                self.init_order()
            rid = set([s['clientOrderId'] for s in self.remote_open_orders])
            lid = set([s['clientOrderId'] for s in self.last_open_orders])
            rdl = set(rid) - set(lid)
            if len(rdl) > 0:
                logger.error("error remote order, delta: %s", rdl)
                raise Exception('error remote order')
            ldl = set(lid) - set(rid)
            if len(ldl) > 0:
                # check dealed order and commit
                self.check_and_commit()

        except Exception as e:
            logger.exception(e)

