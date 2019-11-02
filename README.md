# xi_day_trader
### Have you ever:
- Struggled to get items that are rarely on the auction house?
- Wished you knew the perfect time to **buy** at the **low**?
- Wished you knew the perfect time to **sell** at the **high**?
- Wanted to spend less time checking ffxiah?

### xi_day_trader is a script that monitors ffxiah.com for you and can do all of these things! 
- Windows & Mac compatible
- Multiple scripts can run at a time
- Double click to run

# Setup
Requires you have: 
- python 2.7.xx [installed](https://www.python.org/downloads/release/python-2716/)
- Created a free [send grid account](https://signup.sendgrid.com/)

### Installation:
1. [Download the latest release](https://github.com/graulr/xi_day_trader/releases) and unzip
![](https://i.imgur.com/Lvr8U4C.gif)

2. Run the installer for your respective operating system
![](https://i.imgur.com/T3IFkXm.gif)


### One time setup:

#### 1. Open the unzipped xi_day_trader folder, click `xi_day_trader_win` or `xi_day_trader_mac` depending on your operating system and create a shortcut to your desktop.
![](https://i.imgur.com/gwgT0po.gif)

#### 2. While logged into send grid, navigate to account management and then to the api keys section.  Create a new full access key, copy it, and paste it into the console.
![](https://i.imgur.com/nugO3BD.gif)

##### Setup data is saved in the `xi_day_trader/data` folder and will not be requested on future runs.

# Usage:

#### 1. Once prompted to enter the ffxiah url, copy the url of an item you want to monitor and paste the url into the console.  Then enter your search conditions.
![](https://i.imgur.com/KCvRQdd.gif)

#### 2. When the conditions for your search are met, a notification will be emailed to the address you setup earlier.
![](https://i.imgur.com/dbqbdMo.gif)
##### ^ In order to demonstrate the success case, I set the script to check for stocked fire crystal stacks.
