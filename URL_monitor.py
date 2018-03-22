#!/usr/bin/env python

'''
URL_monitor.py

Python3 program to monitor web site for availability and changes

If URL returns and error, takes to long to respond or has changed then
either bail out or print error with a timestamp

@author: Michael O'Connor <gmikeoc@gmail.com>

@copywrite: 2018

'''

import requests
import time
from datetime import datetime, date
from hashlib import sha256
from timeit import default_timer as timer

# Name of URL we want to monitor
target_URL = 'http://www.oracle.com'

# SHA256 hash of URL
target_Hash = '3e9503004cea57daf3bd19fa372e6b225f84c16dfa69d94fe96941b678802752'

# Where to store file locally for additional processing
target_file = '/tmp/pymonitor.html'

# Acceptable amount of time for URL get before we raise an exception
target_timeout = 0.9

# How often to test, or sleep between tests, of URL
test_interval = 300

def main():

    print ("Monitoring web site: {}".format(target_URL))

    while True:

        # start of loop, initialize to normal

        happy = True
        err_msg = "No Trouble Found"

        # Send get request to specified URL and test for errors

        try:

            start = timer()
            resp_URL = requests.get(target_URL, timeout=target_timeout)
            resp_URL.raise_for_status()
            latency = timer() - start

        except requests.exceptions.HTTPError as e1:
            err_msg = "HTTP Error: " + e1
            happy = False
        except requests.exceptions.ConnectionError as e2:
            err_msg = "Connection Error: " + e2
            happy = False
        except requests.exceptions.Timeout as e3:
            err_msg = "Timeout Error: " + e3
            happy = False
        except requests.exceptions.RequestException as e4:
            err_msg = "Unknown Error: " + e4
            happy = False

        # if we're not happy at this point, no point in continuing

        if not happy:
            print(err_msg)
            quit()

        # Check for total latency on URL get request. Complain if too long

        if latency >= target_timeout:
            err_msg = "Elapsed time is: {}, maximum is: {}".format(latency, target_timeout)
            happy = False

        # Compute SHA256 hash of the URL contents so we can compare against expected

        hash_URL = sha256(resp_URL.content).hexdigest()

        if hash_URL != target_Hash:
            err_msg = "Hash is: {}, expected: {}".format(hash_URL, target_Hash)
            happy = False

        # Save URL contents to a file in case we want to examine further

        file = open(target_file, "w+")
        file.write(resp_URL.text)
        file.close()

        if not happy:
            print('{:%Y-%m-%d %H:%M:%S}: {}'.format(datetime.now(), err_msg))

        time.sleep(test_interval)


# If called from shell as script

if __name__ == '__main__':

    main()
