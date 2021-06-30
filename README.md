# binance_grid_trade
binance grid trade
## usage:
1. prepare your config by copy config.tmp
2. ./run.py ${your_config_path}

## config description
```
{
    "api_key": "${your api key}",
    "api_secret": "${your api secret}",
    "strategy": [{
        "strategy_id": "${your strategy unique id}",
        "low_bound": ${grid lower bound},
        "up_bound": ${grid upper bound},
        "total_cash": ${total base coin num},
        "grid_num": ${grid count},
        "target_symbol": "${target trade symbol, like 'ATA' for ATA/USDT pair}",
        "base_symbol": "${base trade symbol, like 'USDT' for ATA/USDT pair}",
        "price_round_num": ${price round num, like 5 for 0.00001, check by your trade pair},
        "quantity_round_num": ${price round num, like 1 for 0.1, check by your trade pair},
        "sell_greedy_x": ${default 1.0, means the sell price will multiple by it},
        "buy_greedy_x": ${default 1.0, means the buy price will multiple by it},
        "grid_mode": "${equal_percent or equal_delta}",
        "run_target": "${join or quit}",
        "client_type" : "${spot only support spot now}",
        "strategy_type" : "${grid_v1, only support this}"
    }]
}
```
