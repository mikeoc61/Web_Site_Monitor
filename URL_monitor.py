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
+ form of +12345679999
+
+ Tested on:
+
+  MacOS 10.13.3 with Python 3.6.2
+
+-------------------------------------------------------------------------------
'''

__author__      = "Michael E. O'Connor"
__copyright__   = "Copyright 2018"

import time
import boto3
import requests
from os import environ
from datetime import datetime, date
from hashlib import sha1
from timeit import default_timer as timer
from botocore.exceptions import ProfileNotFound, ClientError

# Name of URL we want to monitor

target_URL = 'http://www.rubrik.com/'

# SHA1 hash of Target URL. If you don't have the sha1 hash of the target URL_monitor
# put in any string you like. After reporting the error, target will be reset to
# current hash value

target_Hash = '827fdbfa884e4e6562b28f7394a92e2de5d90610'

# Where to store file locally for additional processing
# Note this format is not portable across platforms

target_file = '/tmp/pymonitor.html'

# Acceptable amount of time for URL get before we raise an exception
# Need to give web site a reasonable amount of time to respond to request
# Note this is used by both the requests() call as well as the latency calculation
# which is dependent on client host performance and workload

target_timeout = 1.5

# How often to test, or sleep between tests, in seconds

test_interval = 300

# Take error message passed as an arguement, return with prepended date and time

def timestamp(err_msg):

    time_msg = "\n{:%Y-%m-%d %H:%M:%S}: {}".format(datetime.now(), err_msg)

    return (time_msg)

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
        if bool(resp.strip()):
            print ("Profile changed to [{0}]".format(resp))
            aws_profile = resp

    except KeyError:
        aws_profile = input ("AWS_PROFILE not set. Please enter a valid AWS_Profle: ")

    environ["AWS_PROFILE"] = aws_profile

    try:
        target_phone = environ["CELL_PHONE"]
        resp = input ("CELL_PHONE set to [{0}]. Press enter to confirm or specify new: ".format(target_phone))
        if bool(resp.strip()):
            print ("Mobile changed to [{0}]".format(resp))
            target_phone = resp

    except KeyError:
        target_phone = input ("CELL_PHONE not set. Please enter a valid Mobile # [+12345679999]: ")

    environ["CELL_PHONE"] = target_phone

    return

#----------------------------------------------------------------------------
# Confirm user is known to AWS and that use has required SNS authorization
# ---------------------------------------------------------------------------

def check_authorization(service):

    try:
        client = boto3.client(service)
        client.publish(PhoneNumber=environ["CELL_PHONE"], Message="Begin Monitoring")

    except ProfileNotFound:
        print ("Error: No AWS credentials found for [" + environ["AWS_PROFILE"] + "]")
        print ("To configure, run: aws configure --profile " + environ["AWS_PROFILE"])
        return False

    except ClientError:
        print ("Error: AWS User doesn't have adequate permissions")
        return False

    return client

#------------------------------------------------------------
# Main body of program
#------------------------------------------------------------

def main():

    # Make sure environment variables are set up prior to Monitoring

    validate_environment()

    # Confim that we're able to establish an AWS client sessions and have
    # adequate permission to send SMS messages

    client = check_authorization('sns')

    # If client was not successfully set in previous step, abort

    if client == False:
        quit()

    print ("\nMonitoring web site: {}".format(target_URL))

    while True:

        # start of loop, initialize to normal

        err_msg = "No Trouble Found"

        # Send get request to specified URL and test for errors

        try:

            start = timer()
            resp_URL = requests.get(target_URL, timeout=target_timeout)
            latency = timer() - start

            resp_URL.raise_for_status()

        # For HTTP or Timeout errors, alert, sleep for awhile and loop back to top

        except requests.exceptions.HTTPError as e1:
            err_msg = "HTTP Error: " + str(e1)
            print(timestamp(err_msg))
            send_sms(client, target_URL + '\n' + err_msg)
            time.sleep(test_interval)
            continue
        except requests.exceptions.Timeout as e2:
            err_msg = "Timeout Error: " + str(e2)
            print(timestamp(err_msg))
            send_sms(client, target_URL + '\n' + err_msg)
            time.sleep(test_interval)
            continue

        # For Connection or Unknown errors, exit program immediately

        except requests.exceptions.ConnectionError as e3:
            err_msg = "Connection Error: " + str(e3)
            print(timestamp(err_msg))
            send_sms(client, target_URL + "Abort Monitoring")
            quit()
        except requests.exceptions.RequestException as e4:
            err_msg = "Unknown Error: " + str(e4)
            print(timestamp(err_msg))
            send_sms(client, target_URL + "Abort Monitoring")
            quit()

        # Calculate latency on URL get request. Complain if too long

        if latency >= target_timeout:
            err_msg = "Latency is: {0:4.2f}, threshold: {1}".format(latency, target_timeout)
            print(timestamp(err_msg))
            send_sms(client, target_URL + '\n' + err_msg)

        # Compute SHA1 hash of the URL contents so we can compare against previous.
        # If changed, report then reset target to current

        current_Hash = sha1(resp_URL.content).hexdigest()

        if current_Hash != target_Hash:
            err_msg = "Hash is: {}, was: {}".format(hash_URL, target_Hash)
            print(timestamp(err_msg))
            send_sms(client, target_URL + '\n' + err_msg)
            target_hash = current_Hash

        # Save URL contents to a file in case we want to examine further

##        file = open(target_file, "w+")
##        file.write(resp_URL.text)
##        file.close()

        print('.', end='', flush=True)    # Output stream of dots to represent progress

        time.sleep(test_interval)

# If called from shell as script

if __name__ == '__main__':

    main()
