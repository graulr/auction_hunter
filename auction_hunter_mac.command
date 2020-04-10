#!/bin/sh
resize -s 70 58
stty columns 58
stty rows 70
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
python3 "$DIR/script/xi_day_trader.py"
