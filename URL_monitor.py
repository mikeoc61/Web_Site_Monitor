#!/usr/bin/env python

'''
+-------------------------------------------------------------------------------
+
+ URL_monitor.py - Watch specific URL for changes or access issues
+
+ See README.md for more detail
+
+ Last update: 11/15/18
+
+-------------------------------------------------------------------------------
'''

__author__      = 'Michael E. OConnor'
__copyright__   = 'Copyright 2018'

import os
import sys
import time
import signal
import requests
from hashlib import sha1
from timeit import default_timer as timer

# AWS Boto3 and botocore only needed when using AWS SNS notification service option

try:
    import boto3
    from botocore.exceptions import ProfileNotFound, ClientError
except ImportError:
    print('Unable to load Boto3 or botocore modules')

# Name of URL we want to monitor

target_URL = 'http://www.mikeoc.me'

# Acceptable amount of time for URL get before we raise an exception
# Need to give web site a reasonable amount of time to respond to request
# Note this is used by both the requests() call as well as the latency calculation
# which is dependent on client host performance, network and workload.
# In most cases, suggest this be set between 3.0 and 5.0 seconds

target_timeout = 5.0

# Delay between health checks (in seconds). 5 min (300s) seems reasonable

test_interval = 300

#-------------------------------------------------------------------------
# Global variable used to control use AWS SMS to alert about problems
# If Sns_client is successfully set it will contain the botocore object and
# no longer be == to False
#-------------------------------------------------------------------------

Sns_client = False

#-----------------------------------------------------
# Return current date and time configured for local TZ
#-----------------------------------------------------

def t_stamp():
    t=time.time()
    time_msg=time.strftime('%Y-%m-%d %H:%M:%S %Z: ', time.localtime(t))
    return (time_msg)

#--------------------------------------------------------------
# Check environment for variables CELL_PHONE and AWS_PROFILE.
# Prompt to confirm or change if needed. Both need to be set
# and valid in order for AWS SNS service to work correctly.
# Note we don't attempt to validate AWS_Profile at this stage.
#--------------------------------------------------------------

def validate_aws_env():
    try:
        aws_profile=os.environ['AWS_PROFILE']
        resp = input('AWS_PROFILE = [{}]. Press enter to confirm '
                     'or specify new: '.format(aws_profile))

        if bool(resp.strip()):
            print('AWS Profile changed to [{}]'.format(resp))
            aws_profile = resp

    except KeyError:
        aws_profile=input('AWS_PROFILE not set. Enter a valid AWS_PROFILE: ')

    os.environ['AWS_PROFILE'] = aws_profile

    while True:             # Allow user multiple attempts to get it right
        try:
            target_phone = os.environ['CELL_PHONE']
            resp = input('CELL_PHONE = [{target_phone}]. Press enter to confirm '
                         'or specify new: ')

            if bool(resp.strip()):
                print('Mobile changed to [{resp}]')
                target_phone = resp

        except KeyError:
            target_phone=input ('CELL_PHONE not set. Enter a valid Mobile '
                                '[+12345679999]: ')

        # Validate phone number format, break if correct, warn and loop if not

        if (len(target_phone) == 12) and (target_phone[0:2] == '+1'):
            os.environ['CELL_PHONE'] = target_phone
            break
        else:
            print ('Error: phone # must start with +1 followed by 10 digits')

    return

#----------------------------------------------------------------------------
# Confirm user is known to AWS and that user has required SNS authorization
# ---------------------------------------------------------------------------

def validate_aws_auth(service):

    mobile=os.environ['CELL_PHONE']
    user=os.environ['AWS_PROFILE']
    message='Begin Monitoring: ' + target_URL
    client=False

    try:
        client=boto3.client(service)
        client.publish(PhoneNumber=mobile, Message=message)

    except ProfileNotFound:
        print ('Error: AWS credentials not found for [{}]'.format(user))
        print ('To configure, run: aws configure --profile ' + user)

    except ClientError:
        print ('Error: User [{}] has inadequate AWS permissions'.format(user))

    return client

#-------------------------------------------------------------------------
# Routine to send SMS message utilizing AWS Simple Notification service
# Assumes CELL_PHONE enviroment variable is set correctly. send_sms() typically
# only called when there is something urgent vs. informational to report
#-------------------------------------------------------------------------

def send_sms(client, message):

    mobile_num=os.environ['CELL_PHONE']

    send_console('Sending SMS', 'Msg= {}, num= {}'.format(message, mobile_num))

    try:
        client.publish(PhoneNumber=mobile_num, Message=message)
    except ClientError:
        send_console ('Error:', 'Unable to send SMS message via AWS', '\n')

#-------------------------------------------------------------
# Print output to console with time stamp. Output consists of
# message detail (raw_msg) and summary info (short_msg)
#-------------------------------------------------------------

def send_console(short_msg, raw_msg = '', cr = ''):
    print(cr + '{} {}: {}'.format(t_stamp(), short_msg, raw_msg))
    return

#--------------------------------------------------------
# Generator to return alternating characters to mark time
#--------------------------------------------------------

def gen_progress(*chars):
    i=0
    while True:
        yield chars[i]
        i=0 if i == (len(chars) - 1) else (i + 1)

#------------------------------------------------------------
# Main body of program
#------------------------------------------------------------

def main():


    global Sns_client             # If AWS Monitoring, contains botocore object

    # Parse input looking for argument to specify AWS SMS integration

    arg_cnt = len(sys.argv)

    if arg_cnt > 2:
        print('Usage: {} <-sns>'.format(sys.argv[0]))
        raise SystemExit()
    elif arg_cnt == 2 and sys.argv[1] != '-sns':
        print('Usage: {} <-sns>'.format(sys.argv[0]))
        raise SystemExit()
    elif arg_cnt == 2 and sys.argv[1] == '-sns':
        print('Configuring for AWS SNS notification')
        validate_aws_env()
        Sns_client = validate_aws_auth('sns')
        if Sns_client == False:
            raise SystemExit()

    # Initialize variables for good measure. All will be reset in main loop

    previous_Hash = None
    first_Pass = True

    # Main loop. Stay in loop unless unrecoverable error detected or sighup

    while True:

        # Sleep for specified time interval, if not first time through loop

        if first_Pass == True:
            send_console('Operating Systems Type is', os.name)
            send_console('Begin monitoring URL', target_URL)
            send_console('Monitoring interval [{}s], response threshold [{}s]'.format(test_interval, target_timeout))
            if Sns_client: send_console('AWS SNS Notification is active for', target_URL)
            prog_char = gen_progress('/', '-', '\\', '-')
            first_Pass = False
        else:
            print(next(prog_char), end='\b', flush=True)
            time.sleep(test_interval)

        # Send get request to specified URL and trap errors

        try:
            start=timer()
            resp_URL=requests.get(target_URL, timeout=target_timeout)
            latency=timer() - start

            # Check for problems with HTTP response and parse errors

            resp_URL.raise_for_status()

        except requests.exceptions.Timeout as e1:
            send_console('Timeout Error', e1, '\n')
            if Sns_client: send_sms(Sns_client, 'Timeout error')
            continue

        except requests.exceptions.ConnectionError as e2:
            send_console('Connection Error', e2, '\n')
            if Sns_client: send_sms(Sns_client, 'Connection Error')
            continue

        # For HTTP or Unknown errors, log error and leave loop

        except requests.exceptions.HTTPError as e3:
            send_console('HTTP Error', e3, '\n')
            if Sns_client: send_sms(Sns_client, 'HTTP Error')
            break

        except requests.exceptions.RequestException as e4:
            send_console('Unknown Error', e4, '\n')
            if Sns_client: send_sms(Sns_client, 'Unknown Error')
            break

        # Calculate latency on URL get request. Complain if too slow

        if latency >= target_timeout:
            err_msg = '{:4.2f}s, threshold: {}s'.format(latency, target_timeout)
            send_console('Slow response', err_msg, '\n')
            if Sns_client: send_sms(Sns_client, 'Slow response: ' + err_msg)

        # Compute SHA1 hash of the URL contents so we can compare against previous.

        current_Hash = sha1(resp_URL.content).hexdigest()

        if current_Hash != previous_Hash:
            if previous_Hash == None:
                send_console('Initial URL hash', current_Hash)
            else:
                send_console('URL Hash changed to', current_Hash, '\n')
                if Sns_client: send_sms(Sns_client, 'Web Site Contents changed')

            previous_Hash = current_Hash

    # If reaching this point, something unexpected has happened

    send_console('Abort', 'Program experienced unexpected problem', '\n')
    if Sns_client: send_sms(Sns_client, 'Monitoring terminated due to unexpected problem')
    raise SystemExit()

# Signal handler for CTRL-C manual termination

def signal_handler(signal, frame):
    send_console('Program terminated manually', '', '\n')
    raise SystemExit()

# If called from shell as script

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
