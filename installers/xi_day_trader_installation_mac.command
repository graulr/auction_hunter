#!/bin/sh
resize -s 50 100
stty columns 100
stty rows 50
sudo easy_install pip
pip install requests --user
pip install beautifulsoup4 --user
pip install lxml --user
pip install colorama --user
pip install crayons --user
pip install sendgrid --user
echo XI Day Trader Installation Complete!
