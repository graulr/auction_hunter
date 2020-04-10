import colorama
import crayons
import logging
import os
import requests
import time
import sys
import enum

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
    FAILURE = 3


class Colors(enum.Enum):
    RED = 1
    YELLOW = 2
    GREEN = 3


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
    cookies = {'sid': get_server_id()}

    # Set the global_sleep_time
    set_sleep_time()

    # Get the hunt mode
    hunt_mode = get_hunt_mode()

    # Get the ffxi url and item to check
    url, item_name = get_ffxiah_url_and_item()

    # Setup a logging file for the item
    setup_logging(item_name)

    continue_options = {'should_restart': True}
    while continue_options.get('should_restart', False):

        # Get the config options from the user
        config_options = get_config_options(item_name)

        continue_options['should_retry'] = True
        while continue_options.get('should_retry', False):

            # Start checking ffxiah and get any restart options afterwards
            continue_options = check_ffxiah(cookies, url, item_name, hunt_mode, config_options)


def check_ffxiah(cookies, url, item_name, hunt_mode, config_options):
    print_and_log('\n-----=============== Checking FFXIAH ===============-----', Colors.GREEN)

    # Process url parameters for the request
    base_url, url_params = parse_url(url)

    attempt = 0  # A count of attempts for logging
    consecutive_failures = 0  # A count of consecutive failures

    log('url: %s' % base_url)
    log('params: %s' % url_params)
    log('cookies: %s' % cookies)

    while True:

        attempt += 1

        # Fetch the page
        try:
            response = requests.get(base_url, headers=HEADERS, cookies=cookies, params=url_params)
        except requests.ConnectionError as e:
            handle_and_log_error(consecutive_failures,
                                 'An exception was encountered requesting FFXIAH: \n%s' % e,
                                 'Failed to request FFXIAH %s consecutive times.' % redify(MAX_RETRIES))
            if consecutive_failures == MAX_RETRIES:
                return get_should_retry()
            consecutive_failures += 1
            continue

        # Parse the page
        soup = BeautifulSoup(response.text, 'lxml')

        # Inventory mode
        if hunt_mode == Modes.INVENTORY:
            result = check_inventory(soup, item_name, url, config_options, consecutive_failures, attempt)

        # Price mode
        elif hunt_mode == Modes.PRICE:
            result = check_price(soup, item_name, url, config_options, consecutive_failures, attempt)

        # Player mode
        elif hunt_mode == Modes.PLAYER:
            result = check_player(soup, item_name, url, config_options, consecutive_failures, attempt)

        # Handle result
        if result:
            if result == Results.FAILURE:
                consecutive_failures += 1
                if consecutive_failures == MAX_RETRIES:
                    return get_retry_options()

            elif result == Results.CONTINUE_SEARCHING:
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
def check_inventory(soup, item_name, url, config_options, consecutive_failures, attempt):
    # Find the item count element
    current_stock = soup.findAll('span', {'class': 'stock'})

    # Parse the string found into an integer
    total_in_stock = get_total_in_stock(current_stock, consecutive_failures)

    # Looking for 0 items
    if config_options['is_count_down']:
        return check_inventory_empty(total_in_stock, url, item_name, attempt)

    # Looking for a range
    if config_options['is_range']:
        return check_inventory_range(total_in_stock, url, item_name, attempt, config_options)

    # Looking for at least 1
    return check_inventory_stocked(total_in_stock, url, item_name, attempt)


def check_inventory_empty(total_in_stock, url, item_name, attempt):
    print_and_log('#%s check for %s %s:' % (greenify(attempt), greenify('empty'), item_name))

    # No items found
    if total_in_stock == 0:
        print_and_log('Found 0 %s!' % item_name, color=Colors.GREEN, indent=True)
        send_email(item_name, url, 'There are 0 %s up for sale' % item_name)
        return Results.COMPLETED

    # Items in stock
    else:
        print_and_log('Found %s %s' % (redify(total_in_stock), item_name), indent=True)

        # Sleep before attempting to try again
        sleep(global_sleep_time)
        return Results.CONTINUE_SEARCHING


def check_inventory_range(total_in_stock, url, item_name, attempt, config_options):
    lower_bound = config_options['lower_bound']
    upper_bound = config_options['upper_bound']
    print_and_log('#%s check for %s within %s (%s - %s):' %
                  (greenify(attempt), item_name, greenify('range'), lower_bound, upper_bound))

    # Within range
    if is_stock_within_range(total_in_stock, lower_bound, upper_bound):
        print_and_log('Found %s %s! (range %s - %s)' % (total_in_stock, item_name,
                                                        lower_bound, upper_bound), color=Colors.GREEN, indent=True)
        send_email(item_name, url, 'There %s %s %s up for sale' % (get_is_or_are(total_in_stock),
                                                                   total_in_stock, item_name))
        return Results.COMPLETED

    # Out of range
    else:
        print_and_log('Found %s %s' % (redify(total_in_stock), item_name), indent=True)

        # Sleep before attempting to try again
        sleep(global_sleep_time)
        return Results.CONTINUE_SEARCHING


def check_inventory_stocked(total_in_stock, url, item_name, attempt):
    print_and_log('#%s check for %s %s:' % (greenify(attempt), greenify('stocked'), item_name))

    # If there are 0 in stock:
    if is_stock_empty(total_in_stock):
        print_and_log('Found %s %s' % (redify(0), item_name), indent=True)

        # Sleep before attempting to try again
        sleep(global_sleep_time)
        return Results.CONTINUE_SEARCHING

    # The item is in stock
    else:
        print_and_log('Found %s %s!' % (total_in_stock, item_name), color=Colors.GREEN, indent=True)
        send_email(item_name, url, 'There %s %s %s up for sale' % (get_is_or_are(total_in_stock),
                                                                   total_in_stock, item_name))
    return Results.COMPLETED


#######################################################################################################################
#                                                      User Input                                                     #
#######################################################################################################################
def get_int_user_input(message):
    answer = None
    while not isinstance(answer, int):
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


def get_ffxiah_url_and_item():
    item_name = ''
    while not item_name:
        url = get_string_user_input('Paste the %s for the item and press enter.' % greenify('ffixah url'))
        try:
            # Parse the item_name out of the url, accounting for stack pages
            # Ex: https://www.ffxiah.com/item_name/4752/fire-crystal
            #     https://www.ffxiah.com/item_name/4096/fire-crystal/?stack=1
            base_url, query_params = parse_url(url)
            item_name_split_list = base_url.rsplit('/', 1)
            if len(item_name_split_list) < 2:
                raise ValueError('Must supply an entire ffxiah url')
            item_name = item_name_split_list[1]

            # The url was for a stack so add the suffix
            if query_params:
                item_name += '-stack'
        except ValueError as e:
            print_and_log(e, Colors.YELLOW)
    return url, item_name


def get_config_options(item_name):
    message = line_breakify_message(('Would you like to be notified when %s is ' % item_name) +
                                    'empty, stocked, or a specific range is on the AH?',
                                    green_words=[item_name])
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


def get_hunt_mode():
    message = line_breakify_message('Would you like this script to hunt based on inventory, price, or player?')
    print_and_log(message)
    hunt_mode = get_option_user_input({Modes.INVENTORY.value, Modes.PRICE.value, Modes.PLAYER.value},
                                      'Type %s, %s, or %s and press enter.' % (greenify('inventory'),
                                                                               greenify('price'),
                                                                               greenify('player')))
    return Modes[hunt_mode.upper()]


def set_sleep_time():
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


def print_failure_and_sleep(consecutive_failures):
    print_and_log('Re-attempting %s out of %s times after sleeping' %
                  (consecutive_failures, MAX_RETRIES), Colors.YELLOW)
    sleep(5)


def handle_and_log_error(consecutive_failures, attempt_message, final_failure_message):
    print_and_log(attempt_message, Colors.RED)
    if consecutive_failures == MAX_RETRIES:
        print_and_log(final_failure_message)
        print_and_log('---------------------------------------------------------', Colors.RED)
    if consecutive_failures != MAX_RETRIES:
        print_failure_and_sleep(consecutive_failures + 1)


def send_email(item_name, url, message):
    notification_address = get_email_notification_address()
    mail = Mail(
        from_email='auction_hunter <notifications@auction_hunter>',
        to_emails=notification_address,
        subject='%s notification' % item_name,
        html_content='<h2>auction_hunter is notifying you: <br/> <a href="%s">%s</a>.</h2>' % (url, message))

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


def parse_url(url):
    stack_split_list = url.rsplit('/?stack=1', 1)
    if len(stack_split_list) == 2:
        return stack_split_list[0], {'stack': 1}
    return stack_split_list[0], {}


def is_stock_empty(total_in_stock):
    return total_in_stock == 0


def is_stock_within_range(total_in_stock, lower_bound, upper_bound):
    return total_in_stock >= lower_bound and total_in_stock <= upper_bound


def get_total_in_stock(current_stock, consecutive_failures):
    if not len(current_stock):
        handle_and_log_error(consecutive_failures,
                             'Current stock was not found on the page',
                             'Failed to find current stock %s consecutive times.' % redify(MAX_RETRIES))
        return FAILUIRE

    # Attempt to parse the current item count to an integer
    total_in_stock = 0
    try:
        total_in_stock = int(current_stock[0].text)
    except Exception as e:
        handle_and_log_error(consecutive_failures,
                             'Could not parse stock count: \n%s' % e,
                             'Failed to parse stock count %s consecutive times.' % redify(MAX_RETRIES))
        return FAILUIRE

    return total_in_stock


# Run the script
main()
