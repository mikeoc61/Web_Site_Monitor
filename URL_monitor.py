#!/usr/bin/env python3

'''
+-------------------------------------------------------------------------------
+
+ URL_monitor.py - Watch specific URL for changes or access issues
+
+ See README.md for more detail
+
+ Last update: 10/30/18
+
+-------------------------------------------------------------------------------
'''

__author__      = "Michael E. O'Connor"
__copyright__   = "Copyright 2018"

import sys
import time
import boto3
import signal
import requests
from os import environ
from hashlib import sha1
from timeit import default_timer as timer
from botocore.exceptions import ProfileNotFound, ClientError

# Name of URL we want to monitor

target_URL = "http://www.mikeoc.me"

# Local file to store URL contents for additional processing
# Note this format is not portable across platforms

target_file = '/tmp/pymonitor.html'

# Acceptable amount of time for URL get before we raise an exception
# Need to give web site a reasonable amount of time to respond to request
# Note this is used by both the requests() call as well as the latency calculation
# which is dependent on client host performance, network and workload.
# In most cases, suggest this be set between 3.0 and 5.0 seconds

target_timeout = 5.0

# Delay between health checks (in seconds). 5 min (300s) seems reasonable

test_interval = 300

# Global variable used to determine if we should alert using AWS SMS.
# Initially set to False, toggled in check_authorization() as appropriate

AWS_Valid = False

#---------------------------------------------------
# Return current date and time with local TZ
#---------------------------------------------------

def t_stamp():
    t = time.time()
    time_msg = time.strftime('%Y-%m-%d %H:%M:%S %Z: ', time.localtime(t))
    return (time_msg)

#--------------------------------------------------------------
# Check environment for variables CELL_PHONE and AWS_PROFILE.
# Prompt to confirm or change if needed. Both need to be set
# and valid in order for AWS SNS service to work correctly.
# Note we don't attempt to validate AWS_Profile at this stage.
#--------------------------------------------------------------

def validate_environment():
    try:
        aws_profile = environ["AWS_PROFILE"]
        #resp = input ("AWS_PROFILE = [{}]. Press enter to confirm or specify new: ".format(aws_profile))
        resp = input (f'AWS_PROFILE = [{aws_profile}]. Press enter to confirm or specify new: ')

        # If response if not NULL, change profile value to new

        if bool(resp.strip()):
            print (f'AWS Profile changed to [{resp}]')
            aws_profile = resp

    except KeyError:
        aws_profile = input ("AWS_PROFILE not set. Please enter a valid AWS_PROFILE: ")

    environ["AWS_PROFILE"] = aws_profile

    while True:             # Allow user multiple attempts to get it right
        try:
            target_phone = environ["CELL_PHONE"]
            resp = input (f'CELL_PHONE = [{target_phone}]. Press enter to confirm or specify new: ')

            # If response if not NULL, change phone number to new number provided

            if bool(resp.strip()):
                print (f'Mobile changed to [{resp}]')
                target_phone = resp

        except KeyError:
            target_phone = input ("CELL_PHONE not set. Enter a valid Mobile # [+12345679999]: ")

        # Validate phone number format, break if correct, warn and loop if not

        if (len(target_phone) == 12) and (target_phone[0:2] == '+1'):
            environ["CELL_PHONE"] = target_phone
            break
        else:
            print ("Error: phone # must start with +1 followed by 10 digits")

    return

#----------------------------------------------------------------------------
# Confirm user is known to AWS and that user has required SNS authorization
# Assumes that environment variables have been previously set. If attempt to
# send initial SMS message via SNS succeeds, set global AWS_Valid to True
# ---------------------------------------------------------------------------

def check_authorization(service):

    mobile = environ["CELL_PHONE"]
    user = environ["AWS_PROFILE"]
    test_msg = "Begin Monitoring: " + target_URL

    global AWS_Valid                       # Make global so we can toggle

    try:
        client = boto3.client(service)
        client.publish(PhoneNumber=mobile, Message=test_msg)
        AWS_Valid = True

    except ProfileNotFound:
        print ("Error: AWS credentials not found for [{}]".format(user))
        print ("To configure, run: aws configure --profile " + user)
        client = False

    except ClientError:
        print ("Error: User [{}] has inadequate AWS permissions".format(user))
        client = False

    return client

#-------------------------------------------------------------------------
# Routine to send SMS message utilizing AWS Simple Notification service
# Assumes CELL_PHONE enviroment variable is set correctly. send_sms() typically
# only called when there is something urgent vs. informational to report
#-------------------------------------------------------------------------

def send_sms(client, message):

    mobile_num = environ["CELL_PHONE"]

    message += ": " + target_URL

    send_console ("Msg= {}, num= {}".format(message, mobile_num), "Sending SMS")

    try:
        client.publish(PhoneNumber=mobile_num, Message=message)
    except ClientError:
        print ("Error: Unable to send SMS message via AWS")

#-------------------------------------------------------------
# Print output to console with time stamp. Output consists of
# message detail (raw_msg) and summary info (short_msg)
#-------------------------------------------------------------

def send_console(raw_msg, short_msg):
    print("{} {}: {}".format(t_stamp(), short_msg, raw_msg))
    return

#--------------------------------------------------------
# Display alternating characters on console to mark time
#--------------------------------------------------------

last_char = 'x'

def show_progress(char_a, char_b):
    global last_char

    if last_char == char_a:
        last_char = char_b
    else:
        last_char = char_a

    print(last_char, end='', flush=True)

#------------------------------------------------------------
# Main body of program
#------------------------------------------------------------

def main():

    # Parse input looking for argument to specify AWS SMS integration

    arg_cnt = len(sys.argv)

    if arg_cnt > 2:
        print("Usage: {} <-sns>".format(sys.argv[0]))
        raise SystemExit()
    elif arg_cnt == 2 and sys.argv[1] != "-sns":
        print("Usage: {} <-sns>".format(sys.argv[0]))
        raise SystemExit()
    elif arg_cnt == 2 and sys.argv[1] == "-sns":
        print("Configuring for AWS SNS notification")
        validate_environment()
        client = check_authorization('sns')
        if client == False:
             raise SystemExit()

    # Initialize variables for good measure. All will be reset in main loop

    previous_Hash = ""
    first_Pass = True

    # Main loop. Stay in loop unless unrecoverable error detected or sighup

    while True:

        # Sleep for specified time interval, if not first time through loop

        if first_Pass == True:
            send_console(target_URL, "Begin monitoring URL")
            send_console("", "Monitoring interval [{}s], response threshold [{}s]".format(test_interval, target_timeout))
            if AWS_Valid:
                send_console(target_URL, "AWS SNS Notification is active for")
            else:
                send_console(target_URL, "AWS SNS messaging not configured for")
            first_Pass = False
        else:
            show_progress('+', '|')
            time.sleep(test_interval)

        # Send get request to specified URL and trap errors

        try:
            start = timer()
            resp_URL = requests.get(target_URL, timeout=target_timeout)
            latency = timer() - start

            # Check for problems with HTTP response and parse errors

            resp_URL.raise_for_status()

        except requests.exceptions.Timeout as e1:
            send_console(e1, "\nTimeout Error")
            if AWS_Valid: send_sms(client, "Timeout error")
            continue

        except requests.exceptions.ConnectionError as e2:
            send_console(e2, "\nConnection Error")
            if AWS_Valid: send_sms(client, "Connection Error")
            continue

        # For HTTP or Unknown errors, log error and leave loop

        except requests.exceptions.HTTPError as e3:
            send_console(e3, "\nHTTP Error")
            if AWS_Valid: send_sms(client, "HTTP Error")
            break

        except requests.exceptions.RequestException as e4:
            send_console(e4, "\nUnknown Error")
            if AWS_Valid: send_sms(client, "Unknown Error")
            break

        # Calculate latency on URL get request. Complain if too slow

        if latency >= target_timeout:
            print ('\n')                          # To left align console output
            err_msg = "{:4.2f}s, threshold: {}s".format(latency, target_timeout)
            send_console(err_msg, "Slow response")
            if AWS_Valid: send_sms(client, "Slow response")

        # Compute SHA1 hash of the URL contents so we can compare against previous.
        # If changed, report and then reset target hash to current hash value

        current_Hash = sha1(resp_URL.content).hexdigest()

        if current_Hash != previous_Hash:
            if previous_Hash == "":
                send_console(current_Hash, "Initial hash")
            else:
                send_console(current_Hash, "\nHash changed to")
                if AWS_Valid: send_sms(client, "Contents changed")

            previous_Hash = current_Hash

        # Save URL contents to local filesystem. May examine further

        file = open(target_file, "w+")
        file.write(resp_URL.text)
        file.close()

    # If reaching this point, something unexpected has happened

    send_console("Program experienced unexpected problem", "Abort")
    if AWS_Valid: send_sms(client, "Monitoring terminated due to unexpected problem")
    raise SystemExit()

# Signal handler for CTRL-C manual termination

def signal_handler(signal, frame):
    print("\nProgram terminated manually")
    raise SystemExit()

# If called from shell as script

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
