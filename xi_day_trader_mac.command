#!/bin/sh
# resize -s 58
# stty cols 58
DIRECTORY=`dirname $0`
python $DIRECTORY/script/xi_day_trader.py
