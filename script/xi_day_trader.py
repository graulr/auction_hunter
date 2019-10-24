import colorama
import crayons
import logging
import os
import requests
import time
import tkMessageBox
import sys

from bs4 import BeautifulSoup
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Print color constants
RED = 'red'
YELLOW = 'yellow'
GREEN = 'green'

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

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) ' +
                         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}


# This script fetches the supplied ffxiah url, checks the item value, & repeats util
# the item value matches the users specification.  The user is then notified via modal & email.
def main():
    colorama.init()
    print_and_log('\n-----================= xi_day_trader =================-----', GREEN)
    print_and_log('Type ctrl + c at any time to quit (cmd + c for mac).', YELLOW)

    # Create the data folder if it does not exist
    create_folder('data')

    # Get the stored api key or get one from the user and store it
    setup_send_grid()

    # Get the stored server id or get one from the user and store it
    cookies = {'sid': get_server_id()}

    # Get the ffxi url to check
    url = get_string_user_input('Paste the ffxiah url for the item and press enter.')

    # Process the item_name name from the url
    try:
        item_name = get_item_name(url)
    except ValueError, e:
        print_and_log(e, RED)
        return

    # Get the stored sleep time or get one from the user and store it
    sleep_time = get_sleep_time()

    # Create the logging folder and configure the logger
    setup_logging(item_name)

    # Get the config options from the user
    config_options = get_config_options(item_name)

    # Begin checking:
    check_ffxiah(cookies, url, item_name, sleep_time, config_options)


def check_ffxiah(cookies, url, item_name, sleep_time, config_options):
    print_and_log('\n-----================ Checking FFXIAH ================-----', GREEN)

    # Process url parameters for the request
    base_url, url_params = parse_url(url)

    attempt = 0  # A count of attempts for logging
    consecutive_failures = 0  # A count of consecutive failures
    while True:

        # Fetch the page
        try:
            log('url: %s' % base_url)
            log('params: %s' % url_params)
            log('cookies: %s' % cookies)
            response = requests.get(base_url, headers=HEADERS, cookies=cookies, params=url_params)
        except requests.ConnectionError, e:
            handle_and_log_error(consecutive_failures,
                                 'Exception encountered attempting to request FFXIAH: \n%s' % e,
                                 'Failed to request FFXIAH 5 consecutive times, exiting')
            if consecutive_failures == 5:
                break
            consecutive_failures += 1
            continue

        # Parse the page
        soup = BeautifulSoup(response.text, 'lxml')

        # Find the item count element
        current_stock = soup.findAll('span', {'class': 'stock'})
        if not len(current_stock):
            handle_and_log_error(consecutive_failures,
                                 'Current stock was not found on the page',
                                 'Failed to find current stock 5 consecutive times, exiting')
            if consecutive_failures == 5:
                break
            consecutive_failures += 1
            continue

        # Attempt to parse the current item count to an integer
        total_count_in_stock = 0
        try:
            total_count_in_stock = int(current_stock[0].text)
        except Exception, e:
            handle_and_log_error(consecutive_failures,
                                 'Could not parse stock count: \n%s' % e,
                                 'Failed to parse stock count 5 consecutive times, exiting')
            if consecutive_failures == 5:
                break
            consecutive_failures += 1
            continue

        # Reset failure count since we've made it this far
        consecutive_failures = 0

        # Increment the attempts
        attempt += 1

        # Looking for 0 items on the AH
        if config_options['is_count_down']:
            print_and_log('#%s check for %s %s:' % (greenify(attempt), greenify('empty'), item_name))

            # No items found
            if is_stock_empty(total_count_in_stock):
                print_and_log('Found 0 %s!' % item_name, color=GREEN, indent=True, flush=True)
                notify_success(item_name, 'Item Vacant', 'There are 0 %s up for sale' % item_name, url)
                break

            # Items in stock
            else:
                print_and_log('Found %s %s' % (redify(total_count_in_stock), item_name), indent=True)

                # Sleep before attempting to try again
                sleep(sleep_time)
                continue

        # Looking for a range on the AH
        elif config_options['is_range']:
            lower_bound = config_options['lower_bound']
            upper_bound = config_options['upper_bound']
            print_and_log('#%s check for %s within %s (%s - %s):' %
                          (greenify(attempt), item_name, greenify('range'), lower_bound, upper_bound))

            # Within range
            if is_stock_within_range(total_count_in_stock, lower_bound, upper_bound):
                print_and_log('Found %s %s! (range %s - %s)' % (total_count_in_stock, item_name,
                                                                lower_bound, upper_bound), color=GREEN, indent=True, flush=True)
                notify_success(item_name, 'Item Within Range', 'There %s %s %s up for sale' %
                               (get_is_or_are(total_count_in_stock), total_count_in_stock, item_name), url)
                break

            # Out of range
            else:
                print_and_log('Found %s %s' % (redify(total_count_in_stock), item_name), indent=True)

                # Sleep before attempting to try again
                sleep(sleep_time)
                continue

        # Looking for at least 1 item on the AH
        else:
            print_and_log('#%s check for %s %s:' % (greenify(attempt), greenify('stocked'), item_name))

            # If there are 0 in stock:
            if is_stock_empty(total_count_in_stock):
                # Sleep before attempting to try again
                print_and_log('Found %s %s' % (redify(0), item_name), indent=True)
                sleep(sleep_time)
                continue

            # The item is in stock
            else:
                print_and_log('Found %s %s!' % (total_count_in_stock, item_name), color=GREEN, indent=True, flush=True)
                notify_success(item_name, 'Item Found', 'There %s %s %s up for sale' % (
                    get_is_or_are(total_count_in_stock), total_count_in_stock, item_name), url)
                break


def is_stock_empty(total_count_in_stock):
    return total_count_in_stock == 0


def is_stock_within_range(total_count_in_stock, lower_bound, upper_bound):
    return total_count_in_stock >= lower_bound and total_count_in_stock <= upper_bound


def get_is_or_are(number):
    if number == 1:
        return 'is'
    return 'are'


def create_folder(folder_name):
    has_folder = False

    # Check if a folder exists
    files = [f for f in os.listdir('../')]
    for f in files:
        if f == folder_name:
            has_folder = True
            break

    # Create a folder if none exists
    if not has_folder:
        try:
            os.mkdir(folder_name)
        except OSError:
            log('\nCreation of the %s directory failed' % folder_name)
        else:
            log('\nSuccessfully created the %s directory' % folder_name)


def get_file_data(file_path):
    try:
        f = open(file_path, 'r')
    except IOError:
        return None
    fl = f.readlines()
    f.close()
    if fl:
        return fl[0].strip()
    return None


def store_data(file_path, data):
    f = open(file_path, 'w+')
    f.write(data)
    f.close()
    log('Successfully saved to %s' % file_path)


def parse_url(url):
    stack_split_list = url.rsplit('/?stack=1', 1)
    if len(stack_split_list) == 2:
        return stack_split_list[0], {'stack': 1}
    return stack_split_list[0], {}


def get_item_name(url):
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

    return item_name


def get_user_sript_type_input():
    answer = None
    acceptable_answers = {'empty', 'stocked', 'range'}
    while answer not in acceptable_answers:
        answer = raw_input('Type "empty", "stocked", or "range" and press enter. \n').lower().strip()
    return answer


def get_int_input(message):
    answer = None
    while not isinstance(answer, int):
        answer = raw_input(message)
        try:
            answer = int(answer)
        except:
            print_and_log('Expected an integer, received %s' % type(answer), YELLOW)
    return answer


def get_string_user_input(message, lower=True):
    user_input = ''
    while not user_input:
        user_input = raw_input('\n%s \n' % message).strip()
        if lower:
            user_input = user_input.lower()
    return user_input


def get_sleep_time_user_input():
    sleep_time = 59
    while sleep_time < 59:
        sleep_time = get_int_input('\nType the number of seconds to wait between requests and press enter. \n')
        if sleep_time < 59:
            print_and_log('Must supply an integer greater than 59.', YELLOW)
    return sleep_time


def get_server_id_user_input():
    server_name = ''
    while not server_name in SERVER_NAME_TO_SID.keys():
        server_name = raw_input('\nType the FFXI server name and press enter. \n').lower().strip()
    return SERVER_NAME_TO_SID[server_name]


def get_send_grid_key():
    file_path = 'data/send_grid_key.txt'
    send_grid_key = get_file_data(file_path)
    if send_grid_key is None:
        send_grid_key = get_string_user_input('Paste your Send Grid API key and press enter.', lower=False)
        store_data(file_path, send_grid_key)
    return send_grid_key


def get_config_options(item_name):
    print_and_log(('\nWould you like this script to alert when %s is empty, stocked, ' % item_name) +
                  '\nor a specific range is on the AH?', GREEN)
    answer = get_user_sript_type_input()
    is_count_down = answer == 'empty'
    is_range = answer == 'range'

    # Determine the lower and upper ranges if the script type is range
    lower_bound = 0
    upper_bound = 0
    if is_range:
        lower_bound = get_int_input('\nType the *lowest* number in the range (inclusive) and press enter. \n')
        upper_bound = get_int_input('\nType the *highest* number in the range (inclusive) and press enter. \n')

    return {
        'is_count_down': is_count_down,
        'is_range': is_range,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
    }


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
        server_id = get_server_id_user_input()
        store_data(file_path, server_id)
    return server_id


def get_sleep_time():
    file_path = 'data/sleep_time.txt'
    sleep_time = get_file_data(file_path)
    if sleep_time is None:
        sleep_time = get_sleep_time_user_input()
        store_data(file_path, str(sleep_time))
    return int(sleep_time)


def setup_send_grid():
    get_send_grid_key()
    get_email_notification_address()


def setup_logging(item_name):
    create_folder('logs')

    # Kill any previously existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Setup logging
    filename = 'logs/%s.log' % (item_name)
    logging.basicConfig(filename=filename, filemode='w', level=logging.DEBUG)


def send_email(message, item_name, url):
    notification_address = get_email_notification_address()
    mail = Mail(
        from_email='xi_day_trader <notifications@graulr.xi>',
        to_emails=notification_address,
        subject='%s notification' % item_name,
        html_content='<h2>xi_day_trader is notifying you that <a href="%s">%s</a>.</h2>' % (url, message.lower()))

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


def notify_success(item_name, title, message, url):
    send_email(message, item_name, url)
    tkMessageBox.showinfo(title, message)


def handle_and_log_error(consecutive_failures, attempt_message, final_failure_message):
    print_and_log(attempt_message, RED)
    if consecutive_failures == 5:
        print_and_log(final_failure_message, RED, flush=True)
    if consecutive_failures != 5:
        print_failure_and_sleep(consecutive_failures + 1)


def greenify(message):
    return crayons.green(message, bold=True)


def redify(message):
    return crayons.red(message, bold=True)


def format_message(message, color, indent):
    if indent:
        message = '   %s' % message
    if color == RED:
        message = redify(message)
    elif color == YELLOW:
        message = crayons.yellow(message)
    elif color == GREEN:
        message = greenify(message)
    return message


def log(message):
    logging.debug(message)


def print_and_log(message, color=None, indent=False, flush=False):
    log(message)

    message = format_message(message, color, indent)
    print message

    # In order to ensure the terminal renders the print
    # flush the stdout when supplied
    if flush:
        sys.stdout.flush()


def sleep(sleep_time):
    print_and_log('Sleeping for %s seconds \n' % sleep_time, indent=True, flush=True)
    time.sleep(sleep_time)


def print_failure_and_sleep(consecutive_failures):
    print_and_log('Re-attempting %s out of 5 times after sleeping' % consecutive_failures, YELLOW)
    sleep(60)


# Run the script
main()
