#! /usr/bin/python3
import os
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
import math
import time
import logging as logger
import json
import signal


class GridRun:
    def __init__(self, client, config):
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
        cache_dir = os.path.abspath(os.path.join(os.path.dirname(
                    os.path.realpath(__file__)), '../data'))
        if not os.path.exists(cache_dir):
            os.mkdir(cache_dir)
        self.cache_file_name = os.path.join(cache_dir, self.strategy_id + '.data')
        
        if self.run_target == "quit":
            logger.info("quit strategy of %s", self.strategy_id)
            self.quit_all()
            return
        if self.grid_mode == 'equal_percent':
            pper = math.pow(self.up_bound / self.low_bound, 1.0 / self.grid_num)
            if pper - 0.0015 <= 1.001:
                raise Exception("grid too crowd")
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
            if pdel / self.up_bound - 0.0015 <= 0.001:
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
                r = self.client.cancel_order(symbol = self.trade_symbol, order_id = od['clientOrderId'])
                if r and 'symbol' in r:
                    break
                time.sleep(0.1)
            time.sleep(0.01)
            logger.info('cancel order %s', r)
        self.last_open_orders = []
        self.save_last_open_orders()
        
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
        #logger.info("all open orders:%s", orders)
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
        oid = '%s_%s_%s_%s_%s_%s' % (self.strategy_id, str(flag_id), qstr[0], qstr[1], str(int(time.time())), str(side))
        logger.info('try to order %s %s %s %s %s', side, quantity, price, flag_id, oid)
        rtc = 10
        last_exp = None
        while rtc > 0:
            try:
                r = self.client.create_limit_order(
                    symbol = self.trade_symbol,
                    side = side, quantity = quantity, price = price, client_order_id = oid)
                time.sleep(0.1)
                crtc = 10
                logger.info(r)
                while crtc > 0:
                    ro = self.client.get_order(symbol = self.trade_symbol, order_id = oid)
                    if ro is not None and ro.get('clientOrderId') == oid:
                        logger.info('suc to order %s %s %s %s', side, quantity, price, flag_id)
                        return r
                    crtc -= 1
                    time.sleep(0.1)
                raise Exception("create order check failed")
            except Exception as e:
                last_exp = e
                time.sleep(0.1)
            rtc -= 1
        logger.error(str(last_exp))
        rep = {
            "od_error":str(last_exp),
            "side": side,
            "quantity": quantity,
            "price": price,
            "clientOrderId": oid}
        return rep
        
    def init_order(self):
        for fid in range(self.grid_num):
            fp = round(self.flags[fid] * self.buy_greedy_x, self.price_round_num)
            logger.info('init order of %s', self.flags[fid])
            qua = round(self.cash_per_flag / fp, self.quantity_round_num)
            ret = self.create_order(Client.SIDE_BUY, qua, fp, fid)
            self.last_open_orders.append(ret)
            if 'od_error' in ret:
                logger.error('flag %s order failed %s', fp, ret['od_error'])
        self.save_last_open_orders()
# {
#             "symbol": "ATAUSDT",
#             "orderId": 28174988,
#             "orderListId": -1,
#             "clientOrderId": "test01_9_268_0_1624501260",
#             "transactTime": 1624501260660,
#             "price": "0.18661000",
#             "origQty": "268.00000000",
#             "executedQty": "0.00000000",
#             "cummulativeQuoteQty": "0.00000000",
#             "status": "NEW",
#             "timeInForce": "GTC",
#             "type": "LIMIT",
#             "side": "BUY",
#             "fills": []
#         }
    def check_and_commit(self):
        self.last_open_orders = self.load_orders()
        self.remote_open_orders = self.get_open_orders()        
        rid = set([s['clientOrderId'] for s in self.remote_open_orders])
        lid = set([s['clientOrderId'] for s in self.last_open_orders])
        logger.info("l-r:%s",set(lid) - set(rid))
        logger.info("r-l:%s",set(rid) - set(lid))
        lmap = {}
        for s in self.last_open_orders:
            lmap[s['clientOrderId']] = s
        new_last_open_orders = []
        for cid in lid:
            if cid in rid:
                #logger.info('pass %s', cid)
                new_last_open_orders.append(lmap[cid])
                continue
            od = lmap[cid]
            content = cid.split('_')
            qty = float(content[2] + '.' + content[3])
            flag_id = int(content[1])
            logger.info('lost order cid %s qty:%s flag_id:%s', cid, qty, flag_id)
            if 'od_error' in od:
                ret = self.create_order(od['side'], od['quantity'], od['price'], flag_id)
                new_last_open_orders.append(ret)
            elif od['side'] == Client.SIDE_BUY:
                sell_flag_id = flag_id + 1
                fp = round(self.flags[sell_flag_id] * self.sell_greedy_x, self.price_round_num)
                ret = self.create_order(Client.SIDE_SELL, qty, fp, sell_flag_id)
                new_last_open_orders.append(ret)
            elif od['side'] == Client.SIDE_SELL:
                buy_flag_id = flag_id - 1
                fp = round(self.flags[buy_flag_id] * self.buy_greedy_x, self.price_round_num)
                qua = round(self.cash_per_flag / fp, self.quantity_round_num)
                ret = self.create_order(Client.SIDE_BUY, qua, fp, buy_flag_id)
                new_last_open_orders.append(ret)
                op = float(od['price'])
                cur_gain = (op - fp) * qty - (op + fp) * qty * 0.00075
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
            logger.info('reorder missing order of %s', self.flags[i])
            qua = round(self.cash_per_flag / fp, self.quantity_round_num)
            ret = self.create_order(Client.SIDE_BUY, qua, fp, i)
            self.last_open_orders.append(ret)
            time.sleep(0.1)
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

