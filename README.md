# xi_day_trader
A script for monitoring inventory on FFXIAH
- Windows & Mac compatible

# Setup
Requires you have: 
- python 2.7.xx [installed](https://www.python.org/downloads/release/python-2716/)
- Created a free [send grid account](https://signup.sendgrid.com/)

### Installation:
1. [Download the latest release](https://github.com/graulr/xi_day_trader/releases) and unzip
2. Run the installer for your respective operating system

### One time setup:

#### The first time you run xi_day_trader you will have to enter some setup info.  The setup info is saved in the `xi_day_trader/data` folder on your machine and will not be asked on future runs.

#### 1. Open the unzipped xi_day_trader folder and double click `xi_day_trader_win` or `xi_day_trader_mac` depending on your operating system
![](http://g.recordit.co/AqOwMIky9S.gif)

#### 2. While logged into send grid, navigate to account management and then to the api keys section.  Create a new full access key, copy it, and paste it into the console.
![](https://i.imgur.com/nugO3BD.gif)

#### 3. Follow the prompts and enter the information requested to complete the setup.
![](https://i.imgur.com/WrP9HsZ.gif)

# Usage:

#### 1. Once prompted to enter the ffxiah url, choose an item that you would like to monitor, copy the url, and paste the url into the console.
![](https://i.imgur.com/pYREYJI.gif)

#### 2. Once the criteria you setup for the item has been met, a modal will display on the screen and a notification will be emailed to the address you setup earlier.
![](https://i.imgur.com/Ipq9kiE.gif)
