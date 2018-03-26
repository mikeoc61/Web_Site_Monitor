#!/usr/bin/env python3

'''
+-------------------------------------------------------------------------------
+
+ URL_monitor.py
+
+ Python3 program to monitor a specific URL for availability and changes
+
+ If URL returns an error, takes too long to respond or has changed then
+ either bail out or print error with a timestamp.
+
+ Program also uses AWS SNS service to send text message to phone number in
+ form of +12345679999 and at this time only works for US country code '+1'
+
+ Tested on:
+
+  MacOS 10.13.3 with Python 3.6.2
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

target_URL = 'https://www.rubrik.com/'
# target_URL = 'http://google.com/'

# Where to store file locally for additional processing
# Note this format is not portable across platforms

target_file = '/tmp/pymonitor.html'

# Acceptable amount of time for URL get before we raise an exception
# Need to give web site a reasonable amount of time to respond to request
# Note this is used by both the requests() call as well as the latency calculation
# which is dependent on client host performance and workload

target_timeout = 2.0

# How often to test, or sleep between tests (in seconds)

test_interval = 300

# Return current date and time with local TZ

def t_stamp():

    t = time.time()

    time_msg = time.strftime('\n%Y-%m-%d %H:%M:%S %Z: ', time.localtime(t))

    return (time_msg)

# Routine to send SMS message utilizing AWS Simple Notification service
# Assumes CELL_PHONE enviroment variable is set correctly

def send_sms(client, sms_msg):

    mobile_num = environ["CELL_PHONE"]

    client.publish(PhoneNumber=str(mobile_num), Message=str(sms_msg))

    return

#------------------------------------------------------------
# Check environment for variables CELL_PHONE and AWS_PROFILE.
# Prompt to confirm or change if needed. Both need to be set
# in order for AWS SNS service to work correctly.
#------------------------------------------------------------

def validate_environment():

    try:
        aws_profile = environ["AWS_PROFILE"]
        resp = input ("AWS_PROFILE set to [{0}]. Press enter to confirm or specify new: ".format(aws_profile))

        # If response if not NULL, change profile value to new

        if bool(resp.strip()):
            print ("Profile changed to [{0}]".format(resp))
            aws_profile = resp

    except KeyError:
        aws_profile = input ("AWS_PROFILE not set. Please enter a valid AWS_Profle: ")

    environ["AWS_PROFILE"] = aws_profile

    while True:

        try:
            target_phone = environ["CELL_PHONE"]
            resp = input ("CELL_PHONE set to [{0}]. Press enter to confirm or specify new: ".format(target_phone))

            # If response if not NULL, change phone number to new number provided

            if bool(resp.strip()):
                print ("Mobile changed to [{0}]".format(resp))
                target_phone = resp

        except KeyError:
            target_phone = input ("CELL_PHONE not set. Please enter a valid Mobile # [+12345679999]: ")

        # Validate phone number format, break if correct, warn and loop if not

        if (len(target_phone) == 12) and (target_phone[0:2] == '+1'):
            environ["CELL_PHONE"] = target_phone
            break
        else:
            print ("Error: phone # must start with +1 followed by 10 digits")

    return

#----------------------------------------------------------------------------
# Confirm user is known to AWS and that user has required SNS authorization
# Assumes that environment variables have been previously set
# ---------------------------------------------------------------------------

def check_authorization(service):

    mobile = environ["CELL_PHONE"]
    user = environ["AWS_PROFILE"]
    test_msg = "Begin Monitoring " + target_URL

    try:
        client = boto3.client(service)
        client.publish(PhoneNumber=mobile, Message=test_msg)

    except ProfileNotFound:
        print ("Error: AWS credentials not found for [{}]".format(user))
        print ("To configure, run: aws configure --profile " + user)
        return False

    except ClientError:
        print ("Error: User [{}] has inadequate AWS permissions".format(user))
        return False

    return client

#------------------------------------------------------------
# Main body of program
#------------------------------------------------------------

def main():

    # Make sure environment variables are set up prior to Monitoring

    validate_environment()

    # Confim that we're able to establish an AWS client session and have
    # adequate permission to send SMS messages via AWS SNS

    client = check_authorization('sns')

    # If client was not successfully set in previous step, abort

    if client == False:
        quit()

    # Initialize variables for good measure. All will be reset in main loop

    err_msg = "**This should never happen**"

    previous_Hash = ""

    first_Pass = True

    while True:

        # Sleep for specified time interval, if not first time through loop

        if first_Pass == True:
            print ("\nBegin monitoring web site: {}".format(target_URL))
            first_Pass = False
        else:
            time.sleep(test_interval)

        # Send get request to specified URL and test for errors

        try:

            start = timer()
            resp_URL = requests.get(target_URL, timeout=target_timeout)
            latency = timer() - start

            # Check for problems with HTTP response and parse errors

            resp_URL.raise_for_status()

        # For Timeout or Connection errors, alert and loop back to top

        except requests.exceptions.Timeout as e1:
            err_msg = "Timeout Error: " + str(e1)
            print(t_stamp() + err_msg)
            send_sms(client, target_URL + '\n' + "Timeout error")
            continue

        except requests.exceptions.ConnectionError as e2:
            err_msg = "Connection Error: " + str(e2)
            print(t_stamp() + err_msg)
            send_sms(client, target_URL + '\n' + "Connection error")
            continue

        # For HTTP or Unknown errors, exit program immediately by leaving loop

        except requests.exceptions.HTTPError as e3:
            err_msg = "HTTP Error: " + str(e3)
            print(t_stamp() + err_msg)
            send_sms(client, target_URL + '\n' + err_msg)
            break

        except requests.exceptions.RequestException as e4:
            err_msg = "Unknown Error: " + str(e4)
            print(t_stamp() + err_msg)
            send_sms(client, target_URL + '\n' + "Abort Monitoring")
            break

        # Calculate latency on URL get request. Complain if too long

        if latency >= target_timeout:
            err_msg = " Response took: {0:4.2f}s, threshold: {1}s".format(latency, target_timeout)
            print(t_stamp() + err_msg)
            send_sms(client, target_URL + '\n' + "Slow response")

        # Compute SHA1 hash of the URL contents so we can compare against previous.
        # If changed, report and then reset target hash to current hash value

        current_Hash = sha1(resp_URL.content).hexdigest()

        if current_Hash != previous_Hash:
            if previous_Hash == "":
                err_msg = "Hash set to: {}".format(current_Hash)
            else:
                err_msg = "Hash changed to: {}".format(current_Hash)
                send_sms(client, target_URL + '\n' + "Web site content changed")

            print(t_stamp() + err_msg)
            previous_Hash = current_Hash

        # Save URL contents to local filesystem in case we want to examine further

        file = open(target_file, "w+")
        file.write(resp_URL.text)
        file.close()

        print('.', end='', flush=True)    # Output stream of dots to represent progress

    # If reaching this point, something has gone wrong

    print(t_stamp() + "Program terminated due to serious problem")

    sys.exit(1)

# Signal handler for CTRL-C manual termination

def signal_handler(signal, frame):
    print("\nProgram terminated manually")
    sys.exit(0)

# If called from shell as script

if __name__ == '__main__':

    signal.signal(signal.SIGINT, signal_handler)

    main()
