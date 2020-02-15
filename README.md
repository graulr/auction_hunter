# auction_hunter
### Have you ever:
- Struggled to get items that are rarely on the auction house?
- Wished you knew the perfect time to **buy** at the **low**?
- Wished you knew the perfect time to **sell** at the **high**?
- Wanted to spend less time checking ffxiah?

### auction_hunter is a script that can do all of these things!
##### Simply supply a ffxiah url and specify when you want to be notified.

# Setup
This script works on Windows & Mac and requires you have:
- python 2.7.xx [installed](https://www.python.org/downloads/release/python-2716/)
- Created a free [send grid account](https://signup.sendgrid.com/)

### Installation:
1. [Download the latest release](https://github.com/graulr/auction_hunter/releases) and unzip
![](https://i.imgur.com/Lvr8U4C.gif)

2. Run the installer for your respective operating system
![](https://i.imgur.com/T3IFkXm.gif)


### One time setup:

#### 1. Open the unzipped auction_hunter folder, click `auction_hunter_win` or `auction_hunter_mac` depending on your operating system and create a shortcut to your desktop.  Then double click the shortcut to start the script.
![](https://i.imgur.com/gwgT0po.gif)

#### 2. While logged into send grid, navigate to account management and then to the api keys section.  Create a new full access key, copy it, and paste it into the console.
![](https://i.imgur.com/nugO3BD.gif)

#### 3. Follow the prompts entering additional information required to complete the one time setup.
##### Setup data is saved in the `auction_hunter/data` folder and will not be requested on future runs.

# Usage:

#### 1. Once prompted to enter the ffxiah url, copy the url of an item you want to monitor and paste the url into the console.  Then enter your search conditions.
![](https://i.imgur.com/KCvRQdd.gif)

#### 2. When the conditions for your search are met, a notification will be emailed to the address you setup earlier.
![](https://i.imgur.com/dbqbdMo.gif)
##### ^ In order to demonstrate the success case, I set the script to check for stocked fire crystal stacks.
