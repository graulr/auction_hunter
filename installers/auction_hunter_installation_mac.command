#!/bin/sh
resize -s 50 100
stty columns 100
stty rows 50
sudo easy_install pip
pip3 install requests --user
pip3 install beautifulsoup4 --user
pip3 install lxml --user
pip3 install colorama --user
pip3 install crayons --user
pip3 install sendgrid --user
echo auction_hunter Installation Complete!
