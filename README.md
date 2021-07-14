# binance_grid_trade
binance grid trade
## Update Record:
### v1.0.2 update
1. support binance future trade pair
2. aggregate the income by group
3. shrink the client order id to avoid length exception
### v1.0.1 update
1. support loopback testing
2. reorder the order cancel by accident
3. log the income for each strategy in log file
4. fix some bug
### v1.0.0 update
1. first commit

## usage:
### how to build your strategy:
1. install python-binance, git:https://github.com/sammchardy/python-binance
2. prepare your config by copy config.tmp
3. ./run.py ${your_config_path}

### how to exec your loopback testing:
1. modify ord_record.py in two block, coin_pain = xxx and fh = xxx
2. run "./ord_record.py ${your_config_path}" to record the market price
3. now you get your coin pair market price record file xxx.record
4. learn the usage of MockClient in mock_run.py and exec your loopback testing 

## config description
```
{
    "api_key": "${your api key}",
    "api_secret": "${your api secret}",
    "strategy": [{
        "strategy_id": "${your strategy unique id}",
        "group": "{the group this strategy belong to}",        
        "low_bound": ${grid lower bound},
        "up_bound": ${grid upper bound},
        "total_cash": ${total base coin num},
        "grid_num": ${grid count},
        "target_symbol": "${target trade symbol, like 'ATA' for ATA/USDT pair}",
        "base_symbol": "${base trade symbol, like 'USDT' for ATA/USDT pair}",
        "price_round_num": ${price round num, like 5 for 0.00001, check by your trade pair},
        "quantity_round_num": ${price round num, like 1 for 0.1, check by your trade pair},
        "sell_greedy_x": ${default 1.0, sell price will multiple by it},
        "buy_greedy_x": ${default 1.0, buy price will multiple by it},
        "grid_mode": "${equal_percent or equal_delta}",
        "run_target": "${join or quit}",
        "client_type" : "${spot or future}",
        "strategy_type" : "${grid_v1, only support this}"
        "cache_type" : "${mem or file, mem only use for loopback testing in mock_run}"
    }]
}
```
