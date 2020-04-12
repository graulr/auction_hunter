import colorama
import crayons
import enum
import logging
import json
import os
import re
import requests
import time
import sys

from bs4 import BeautifulSoup
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class Modes(enum.Enum):
    INVENTORY = 'inventory'
    PRICE = 'price'
    PLAYER = 'player'


class Results(enum.Enum):
    CONTINUE_SEARCHING = 1
    COMPLETED = 2


class Colors(enum.Enum):
    RED = 1
    YELLOW = 2
    GREEN = 3


class AHUrl(object):
    def __init__(self, **kwargs):
        self.url = kwargs.get('url')
        self.base = kwargs.get('base')
        self.params = kwargs.get('params')
        self.url_type = kwargs.get('url_type')
        self.tail = kwargs.get('tail')


class HandledException(Exception):
    pass


ERROR_SLEEP_TIME = 5
MAX_RETRIES = 5
MAX_LINE_LENGTH = 57

SERVER_NAME_TO_SID = {
    'asura': '28',
    'bahamut': '1',
    'bismark': '25',
    'carbuncle': '6',
    'cerberus': '23',
    'fenrir': '7',
    'lakshmi': '27',
    'leviathan': '11',
    'odin': '12',
    'phoenix': '5',
    'quetzalcoatl': '16',
    'ragnarok': '20',
    'shiva': '2',
    'siren': '17',
    'slyph': '8',
    'valefor': '9',
}

PATH_TO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
AUCTION_HUNTER_DIRECTORY_PATH = PATH_TO_SCRIPT[0:len(PATH_TO_SCRIPT)-6]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) ' +
                         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

global_sleep_time = 5
global_cookies = {'sid': 28}
global_last_sale = None

# This script fetches the supplied ffxiah url, checks the item value, & repeats util
# the item value matches the users specification.  The user is then notified via email.


def main():
    colorama.init()
    print_and_log('\n-----================ auction_hunter ================-----', Colors.GREEN)
    print_and_log('Type ctrl + c at any time to quit (cmd + c for mac).', Colors.YELLOW)

    # Create the data folder if it does not exist
    create_folder('data')

    # Get the stored api key or solicit one and store it
    get_send_grid_key()

    # Get the stored notification address or solicit one and store it
    get_email_notification_address()

    # Get the stored server id or solicit one and store it
    global global_cookies
    global_cookies = {'sid': get_server_id()}

    # Set the global_sleep_time
    set_global_sleep_time()

    # Get the ffxi url and parse
    ah_url = get_ahurl()

    # Get the hunt_mode
    hunt_mode = get_hunt_mode(ah_url.url_type)

    # Setup a logging file for the tail
    setup_logging(ah_url.tail)

    continue_options = {'should_restart': True}
    while continue_options.get('should_restart', False):

        # Get the config options from the user
        config = get_config(hunt_mode, ah_url)

        continue_options['should_retry'] = True
        while continue_options.get('should_retry', False):

            # Start checking ffxiah and get any restart options afterwards
            continue_options = check_ffxiah(ah_url, hunt_mode, config)


def check_ffxiah(ah_url, hunt_mode, config):
    print_and_log('\n-----=============== Checking FFXIAH ===============-----', Colors.GREEN)
    attempt = 0  # A count of attempts for logging
    consecutive_failures = 0  # A count of consecutive failures

    # Log some basic debugging information
    log('base_url: %s' % ah_url.base)
    log('params: %s' % ah_url.params)
    log('cookies: %s' % global_cookies)

    while True:
        # Increment the attempt counter
        attempt += 1

        try:
            # Inventory mode
            if hunt_mode == Modes.INVENTORY:
                result = check_inventory(ah_url, attempt, config)

            # Price mode
            elif hunt_mode == Modes.PRICE:
                result = check_price(ah_url, attempt, config)

            # Player mode
            elif hunt_mode == Modes.PLAYER:
                result = check_player(ah_url, attempt, config)

        except HandledException as e:
            print_and_log(e, Colors.RED)
            consecutive_failures += 1

            if consecutive_failures == MAX_RETRIES:
                print_and_log('Failed %s consecutive times. Stopping for user input' % MAX_RETRIES, Colors.RED)
                print_and_log('---------------------------------------------------------', Colors.RED)
                return get_retry_options()

            else:
                print_and_log('Re-attempting %s out of %s times after sleeping' % (
                    consecutive_failures, MAX_RETRIES), Colors.YELLOW)
                sleep(ERROR_SLEEP_TIME)
                continue

        # Handle result
        if result:
            if result == Results.CONTINUE_SEARCHING:
                # Sleep before attempting to try again
                sleep(global_sleep_time)
                consecutive_failures = 0
                continue

            elif result == Results.COMPLETED:
                return get_restart_options()

        # We have no result, kill the loop
        print_and_log('An error has occured, halting execution', Colors.RED)
        log(result)
        return {}


#######################################################################################################################
#                                                      Inventory                                                      #
#######################################################################################################################
def check_inventory(ah_url, attempt, config):
    soup = fetch_page_and_soupify(ah_url)

    # Find the item count element
    total_in_stock = soup.findAll('span', {'class': 'stock'})

    # Parse the soup found into an integer
    total_in_stock = parse_integer_from_soup(total_in_stock, 'current stock')

    # Looking for 0 items
    if config['is_count_down']:
        return check_inventory_empty(total_in_stock, ah_url, attempt)

    # Looking for a range
    if config['is_range']:
        return check_inventory_range(total_in_stock, ah_url, attempt, config)

    # Looking for at least 1
    return check_inventory_stocked(total_in_stock, ah_url, attempt)


def check_inventory_empty(total_in_stock, ah_url, attempt):
    print_and_log('#%s check for %s %s:' % (greenify(attempt), greenify('empty'), ah_url.tail))

    # If there are 0 in stock:
    if total_in_stock == 0:
        return handle_inventory_at_target(total_in_stock, ah_url)

    # The item is in stock
    return handle_inventory_target_not_reached(total_in_stock, ah_url)


def check_inventory_stocked(total_in_stock, ah_url, attempt):
    print_and_log('#%s check for %s %s:' % (greenify(attempt), greenify('stocked'), ah_url.tail))

    # If there are 0 in stock:
    if total_in_stock != 0:
        return handle_inventory_at_target(total_in_stock, ah_url)

    # The item is in stock
    return handle_inventory_target_not_reached(total_in_stock, ah_url)


def check_inventory_range(total_in_stock, ah_url, attempt, config):
    lower_bound = config['lower_bound']
    upper_bound = config['upper_bound']
    print_and_log('#%s check for %s within %s (%s - %s):' %
                  (greenify(attempt), ah_url.tail, greenify('range'), lower_bound, upper_bound))

    # Within range
    if is_within_range(total_in_stock, lower_bound, upper_bound):
        return handle_inventory_at_target(total_in_stock, ah_url,
                                          suffix='(range %s - %s)' % (lower_bound, upper_bound))

    # Out of range
    return handle_inventory_target_not_reached(total_in_stock, ah_url)


def handle_inventory_at_target(total_in_stock, ah_url, suffix=''):
    item_name = ah_url.tail
    print_and_log('Found %s %s! %s' % (total_in_stock, item_name, suffix), color=Colors.GREEN, indent=True)
    send_email(ah_url, 'There %s %s %s up for sale' % (get_is_or_are(total_in_stock),
                                                       total_in_stock, item_name))
    return Results.COMPLETED


def handle_inventory_target_not_reached(total_in_stock, ah_url):
    print_and_log('Found %s %s' % (redify(total_in_stock), ah_url.tail), indent=True)
    return Results.CONTINUE_SEARCHING


def get_inventory_config(item_name):
    message = line_breakify_message(('Would you like to be notified when %s is ' % item_name) +
                                    'empty, stocked, or a specific range is on the AH?')
    print_and_log(message)
    script_type = get_option_user_input({'empty', 'stocked', 'range'},
                                        'Type %s, %s, or %s and press enter.' % (greenify('empty'),
                                                                                 greenify('stocked'),
                                                                                 greenify('range')))
    is_count_down = script_type == 'empty'
    is_range = script_type == 'range'

    # Determine the lower and upper ranges if the script type is range
    lower_bound = 0
    upper_bound = 0
    if is_range:
        lower_message = line_breakify_message('Type the lowest number in the range (inclusive) and press enter.',
                                              green_words=['lowest number'])
        lower_bound = get_int_user_input(lower_message)

        upper_message = line_breakify_message('Type the highest number in the range (inclusive) and press enter.',
                                              green_words=['highest number'])
        upper_bound = get_int_user_input(upper_message)

    return {
        'is_count_down': is_count_down,
        'is_range': is_range,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
    }
#######################################################################################################################
#                                                        Price                                                        #
#######################################################################################################################


def check_price(ah_url, attempt, config):
    soup = fetch_page_and_soupify(ah_url)

    # Get the script tags on the page
    scripts = soup.findAll('script')

    # Parse the soup found into an integer
    last_sale_price = parse_last_sale_price_from_scripts(scripts)

    # Check greater than
    if config['is_greater']:
        return check_price_greater(last_sale_price, ah_url, attempt, config['target_price'])

    # Check less than
    return check_price_less(last_sale_price, ah_url, attempt, config['target_price'])


def check_price_greater(last_sale_price, ah_url, attempt, target_price):
    print_and_log('#%s check for %s price at or above %s:' % (greenify(attempt), ah_url.tail, greenify(target_price)))

    # Greater or equal to
    if last_sale_price >= target_price:
        return handle_price_at_target(last_sale_price, ah_url)

    # Below target price
    return handle_price_target_not_reached(last_sale_price, ah_url)


def check_price_less(last_sale_price, ah_url, attempt, target_price):
    print_and_log('#%s check for %s price at or below %s:' % (greenify(attempt), ah_url.tail, greenify(target_price)))

    # Less than or equal to
    if last_sale_price <= target_price:
        return handle_price_at_target(last_sale_price, ah_url)

    # Above target price
    return handle_price_target_not_reached(last_sale_price, ah_url)


def handle_price_at_target(last_sale_price, ah_url, suffix=''):
    item_name = ah_url.tail
    print_and_log('Last %s sale was %s! %s' % (item_name, last_sale_price, suffix), color=Colors.GREEN, indent=True)
    send_email(ah_url, 'Last %s sale was %s' % (item_name, last_sale_price))
    return Results.COMPLETED


def handle_price_target_not_reached(last_sale_price, ah_url):
    print_and_log('Last %s sale was %s' % (ah_url.tail, redify(last_sale_price)), indent=True)
    return Results.CONTINUE_SEARCHING


def parse_last_sale_price_from_scripts(scripts):
    last_sale = parse_transactions(scripts, 'Item.sales')[0]
    last_sale_price = last_sale.get('price')

    if not last_sale_price:
        raise HandledException('Last sale has not price data')

    return parse_integer_from_string(last_sale_price, 'last sale')


def get_price_config(item_name):
    target_price = get_int_user_input('\nType the %s you would like to target and press enter' % greenify('price'))

    message = line_breakify_message(('Would you like to be notified when the price of %s is ' % item_name) +
                                    'above or below %s? (inclusive)' % target_price)
    print_and_log(message)
    script_type = get_option_user_input({'above', 'below', },
                                        'Type %s or %s and press enter.' % (greenify('above'),
                                                                            greenify('below')))
    is_greater = script_type == 'above'

    return {
        'target_price': target_price,
        'is_greater': is_greater
    }


#######################################################################################################################
#                                                       Player                                                        #
#######################################################################################################################
def check_player(ah_url, attempt, config):
    soup = fetch_page_and_soupify(ah_url)

    # Get the script tags on the page
    scripts = soup.findAll('script')

    # Find the last sale element
    transaction = parse_latest_player_sale(scripts, ah_url.tail)

    # Check for a specific sale
    if config['specific_item_name']:
        return check_player_sold_specific_item(transaction, ah_url, attempt, config['specific_item_name'])

    # Check for any sale
    return check_player_any_sale(transaction, ah_url, attempt)


def check_player_any_sale(transaction, ah_url, attempt):
    print_and_log('#%s check for %s sales:' % (greenify(attempt), greenify(ah_url.tail)))

    # New sale
    if transaction.get('saleon') > global_last_sale.get('saleon'):
        return handle_player_sale_complete(transaction.get('en_name'), ah_url)

    # Nothing sold
    return handle_no_player_sale(ah_url)


def check_player_sold_specific_item(transaction, ah_url, attempt, search_item_name):
    print_and_log('#%s check for %s %s sales:' % (
        greenify(attempt), ah_url.tail, greenify(search_item_name)))

    # New sale
    if transaction.get('saleon') > global_last_sale.get('saleon') and transaction.get('en_name') == search_item_name:
        return handle_player_sale_complete(transaction.get('en_name'), ah_url)

    # Nothing sold
    return handle_no_player_sale(ah_url)


def parse_latest_player_sale(scripts, player_name):
    transactions = parse_transactions(scripts, 'Player.sales')

    for transaction in transactions:
        item_name = transaction.get('en_name')
        seller_name = transaction.get('seller_name')

        if not item_name:
            raise HandledException('Transaction has no item name')

        if not seller_name:
            raise HandledException('Transaction has no seller name')

        if seller_name.lower() == player_name.lower():

            # Set the global last on the first run
            global global_last_sale
            if global_last_sale is None:
                global_last_sale = transaction

            return transaction
    return None


def handle_player_sale_complete(item_name, ah_url):
    player_name = ah_url.tail
    print_and_log('%s sold a %s' % (player_name.capitalize(), item_name), color=Colors.GREEN, indent=True)
    send_email(ah_url, '%s sold a %s' % (player_name.capitalize(), item_name))
    return Results.COMPLETED


def handle_no_player_sale(ah_url):
    print_and_log('%s for %s' % (redify('No new sales'), ah_url.tail), indent=True)
    return Results.CONTINUE_SEARCHING


def get_player_config(player_name):
    message = line_breakify_message(('Would you like to be notified when any sale is made or when ') +
                                    'a specific item is sold?')
    print_and_log(message)
    script_type = get_option_user_input({'any', 'specific', },
                                        'Type %s or %s and press enter.' % (greenify('any'),
                                                                            greenify('specific')))

    specific_item_name = None
    if script_type == 'specific':
        specific_item_name = get_string_user_input(
            '\nType the %s you would like to target and press enter' % greenify('item'))

    return {'specific_item_name': specific_item_name}


#######################################################################################################################
#                                                      User Input                                                     #
#######################################################################################################################
def get_int_user_input(message):
    answer = None
    while not isinstance(answer, int) or answer < 0:
        print_and_log(message)
        answer = input()
        try:
            answer = int(answer)
        except:
            print_and_log('Expected an integer, received %s' % type(answer), Colors.YELLOW)
    return answer


def get_string_user_input(message, lower=True):
    user_input = ''
    while not user_input:
        print_and_log('\n%s' % message)
        user_input = input().strip()
        if lower:
            user_input = user_input.lower()
    return user_input


def get_option_user_input(options, message):
    answer = None
    while answer not in options:
        print_and_log(message)
        answer = input()
        answer = answer.lower().strip()
    return answer


def get_ahurl():
    tail = ''
    while not tail:
        url = get_string_user_input('Paste the %s for the item and press enter.' % greenify('ffixah url'))
        try:
            # Parse the item_name out of the url, accounting for stack pages
            # Ex: https://www.ffxiah.com/item_name/4752/fire-crystal
            #     https://www.ffxiah.com/item_name/4096/fire-crystal/?stack=1
            stack_split_list = url.rsplit('/?stack=1', 1)
            base_url = stack_split_list[0]
            query_params = {}
            if len(stack_split_list) == 2:
                query_params['stack'] = 1

            segments = base_url.rsplit('/', 3)
            if len(segments) < 4:
                raise ValueError('Must supply an entire ffxiah url')

            url_type = segments[1]
            tail = segments[3]

            # The url was for a stack so add the suffix
            if query_params:
                tail += '-stack'
        except ValueError as e:
            print_and_log(e, Colors.YELLOW)

    return AHUrl(url=url, base=base_url, params=query_params, url_type=url_type, tail=tail)


def get_config(hunt_mode, ah_url):
    if hunt_mode == Modes.INVENTORY:
        return get_inventory_config(ah_url.tail)

    elif hunt_mode == Modes.PRICE:
        return get_price_config(ah_url.tail)

    elif hunt_mode == Modes.PLAYER:
        return get_player_config(ah_url.tail)


def get_boolean_input():
    answer = get_option_user_input({'y', 'n'},
                                   'Type "%s" or "%s" and press enter.' % (greenify('y'),
                                                                           greenify('n')))
    return answer == 'y'


def get_restart_options():
    print_and_log('\nWould you like to run the script again?')
    restart_options = {'should_restart': get_boolean_input()}
    return restart_options


def get_retry_options():
    print_and_log('\nWould you like to resume the script and keep trying?', Colors.YELLOW)
    retry_options = {'should_retry': get_boolean_input()}
    return retry_options


def get_send_grid_key():
    file_path = 'data/send_grid_key.txt'
    send_grid_key = get_file_data(file_path)
    if send_grid_key is None:
        send_grid_key = get_string_user_input('Paste your %s and press enter.' % (greenify('Send Grid API key')),
                                              lower=False)
        store_data(file_path, send_grid_key)
    return send_grid_key


def get_email_notification_address():
    file_path = 'data/notification_address.txt'
    notification_address = get_file_data(file_path)
    if notification_address is None:
        notification_address = get_string_user_input('Type the email address to notify and press enter')
        store_data(file_path, notification_address)
    return notification_address


def get_server_id():
    file_path = 'data/server_id.txt'
    server_id = get_file_data(file_path)
    if server_id is None:
        server_name = get_option_user_input(list(SERVER_NAME_TO_SID.keys()),
                                            '\nType the %s and press enter.' % (greenify('FFXI server name')))
        server_id = SERVER_NAME_TO_SID[server_name]
        store_data(file_path, server_id)
    return server_id


def get_hunt_mode(url_type):
    if url_type.lower() == 'player':
        return Modes.PLAYER

    else:
        print_and_log(line_breakify_message('Would you like this script to hunt based on inventory or price?'))
        hunt_mode = get_option_user_input({Modes.INVENTORY.value, Modes.PRICE.value},
                                          'Type %s or %s and press enter.' % (greenify('inventory'),
                                                                              greenify('price')))
        return Modes[hunt_mode.upper()]


def set_global_sleep_time():
    file_path = 'data/sleep_time.txt'
    sleep_time = get_file_data(file_path)
    if sleep_time is None:
        sleep_time = 0
        message = line_breakify_message('Type the number of minutes to wait between requests and press enter.',
                                        green_words=['number of minutes'])
        while sleep_time < 1:
            sleep_time = get_int_user_input(message)
            if sleep_time < 1:
                print_and_log('Must supply an integer greater than 0.', Colors.YELLOW)

        store_data(file_path, str(sleep_time))
    global global_sleep_time
    global_sleep_time = int(sleep_time)


#######################################################################################################################
#                                                    Notifications                                                    #
#######################################################################################################################
def setup_logging(item_name):
    create_folder('logs')

    # Kill any previously existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Setup logging
    filename = get_combined_path('logs/%s.log' % (item_name))
    logging.basicConfig(filename=filename, filemode='w', level=logging.DEBUG)


def log(message):
    logging.debug(message)


def print_and_log(message, color=None, indent=False):
    log(message)

    message = format_message(message, color, indent)
    print(message)

    # In order to ensure the terminal renders the print
    sys.stdout.flush()


def send_email(ah_url, message):
    notification_address = get_email_notification_address()
    mail = Mail(
        from_email='auction_hunter <notifications@auction_hunter>',
        to_emails=notification_address,
        subject='%s notification' % ah_url.tail,
        html_content='<h2>auction_hunter is notifying you: <br/> <a href="%s">%s</a>.</h2>' % (ah_url.url, message))

    api_key = get_send_grid_key()
    try:
        sg = SendGridAPIClient(api_key=api_key)
        response = sg.send(mail)
        log(response.status_code)
        log(response.body)
        log(response.headers)
    except Exception as e:
        print_and_log('\n%s %s' % (redify('Failed to notify'), notification_address))
        print_and_log(e)
    else:
        print_and_log('\n%s %s' % (greenify('Successfully notified'), notification_address))


#######################################################################################################################
#                                                   Text Utilities                                                    #
#######################################################################################################################
def greenify(message):
    return crayons.green(message, bold=True)


def redify(message):
    return crayons.red(message, bold=True)


def line_breakify_message(message, green_words=None):
    length = len(message)
    if length <= MAX_LINE_LENGTH:
        return message

    # Convert the message into a 2D list where each row represents
    # a line of text fitting under MAX_LINE_LENGTH
    words = message.split()
    word_matrix = [[]]
    row = 0
    characters_in_line = 0
    for word in words:
        characters_in_line += len(word) + 1
        if characters_in_line >= MAX_LINE_LENGTH:
            # Start a new line
            row += 1
            word_matrix.append([])
            characters_in_line = len(word) + 1
        word_matrix[row].append(word)

    # Convert the 2D list into a single string with line breaks
    updated_message = '\n'
    for i in range(0, row + 1):
        newline = '\n'
        if i == row:
            newline = ''
        updated_message += '%s%s' % ((' '.join(word_matrix[i]).strip()), newline)

    # Apply optional styling
    if isinstance(green_words, list):
        for word in green_words:
            updated_message = updated_message.replace(word, str(greenify(word)))

    return updated_message


def format_message(message, color, indent):
    if indent:
        message = '   %s' % message
    if color == Colors.RED:
        message = redify(message)
    elif color == Colors.YELLOW:
        message = crayons.yellow(message)
    elif color == Colors.GREEN:
        message = greenify(message)
    return message


def get_is_or_are(number):
    if number == 1:
        return 'is'
    return 'are'


#######################################################################################################################
#                                                    Misc Utilities                                                   #
#######################################################################################################################
def fetch_page_and_soupify(ah_url):
    try:
        response = requests.get(ah_url.base, headers=HEADERS, cookies=global_cookies, params=ah_url.params)
    except requests.ConnectionError as e:
        raise HandledException('An exception was encountered requesting FFXIAH: \n%s' % e)

    return BeautifulSoup(response.text, 'lxml')


def sleep(sleep_time):
    plural = ''
    if sleep_time > 1:
        plural = 's'
    print_and_log('Sleeping for %s minute%s \n' % (sleep_time, plural), indent=True)
    time.sleep(sleep_time * 60)


def get_combined_path(path):
    return '%s/%s' % (AUCTION_HUNTER_DIRECTORY_PATH, path)


def create_folder(folder_name):
    has_folder = False

    # Check if a folder exists
    files = [f for f in os.listdir(AUCTION_HUNTER_DIRECTORY_PATH)]
    for f in files:
        if f == folder_name:
            has_folder = True
            break

    # Create a folder if none exists
    if not has_folder:
        try:
            os.mkdir(get_combined_path(folder_name))
        except OSError:
            log('\nCreation of the %s directory failed' % folder_name)
        else:
            log('\nSuccessfully created the %s directory' % folder_name)


def get_file_data(file_path):
    try:
        f = open(get_combined_path(file_path), 'r')
    except IOError:
        return None
    fl = f.readlines()
    f.close()
    if fl:
        return fl[0].strip()
    return None


def store_data(file_path, data):
    f = open(get_combined_path(file_path), 'w+')
    f.write(data)
    f.close()
    log('Successfully saved to %s' % file_path)


def is_within_range(number_to_check, lower_bound, upper_bound):
    return number_to_check >= lower_bound and number_to_check <= upper_bound


def parse_transactions(scripts, script_index):
    if len(scripts) < 8:
        raise HandledException('Script was not found on the page')

    try:
        item_script_tag = scripts[7].contents[0]
    except Exception as e:
        raise HandledException('Script contents were not found')

    try:
        transactions = item_script_tag.split('%s = ' % script_index)[1]
    except Exception as e:
        raise HandledException('%s were not found' % script_index)

    try:
        transactions = re.search("\[\{.*?\}\]", transactions).group()
    except Exception as e:
        raise HandledException('Regular expression matching failed')

    try:
        transactions = json.loads(transactions)
    except Exception as e:
        raise HandledException('Json failed to load')

    if len(transactions) < 1:
        raise HandledException('Sales data contains less than 1 entry')

    return transactions


def parse_integer_from_soup(soup, parse_name):
    if not len(soup):
        raise HandledException('%s was not found on the page' % parse_name.capitalize())

    try:
        text = soup[0].text
    except Exception as e:
        raise HandledException('Could not get text from soup %s: \n%s' % (parse_name, e))

    return parse_integer_from_string(text, parse_name)


def parse_integer_from_string(int_str, parse_name):
    parsed_int = 0
    try:
        parsed_int = int(int_str)
    except Exception as e:
        raise HandledException('Could not parse %s: \n%s' % (parse_name, e))

    return parsed_int


# Run the script
main()
