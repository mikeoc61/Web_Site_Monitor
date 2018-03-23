#!/usr/bin/env python

'''
URL_monitor.py

Python3 program to monitor web site for availability and changes

If URL returns an error, takes to long to respond or has changed then
either bail out or print error with a timestamp.

Note originally used sha256 but changed to sha1 for better cross platform
     consistency and performance

@author: Michael O'Connor <gmikeoc@gmail.com>

@copywrite: 2018

'''

import requests
import time
from datetime import datetime, date
from hashlib import sha1
from timeit import default_timer as timer

# Name of URL we want to monitor
target_URL = 'http://www.oracle.com'

# SHA1 hash of URL
target_Hash = '606de0df954a8d7c46a66fdf6686a91d7ef985ff'

# Where to store file locally for additional processing
# Note this format is not portable across platforms
target_file = '/tmp/pymonitor.html'

# Acceptable amount of time for URL get before we raise an exception
# Need to give web site a reasonable amount of time to respond to request
# Note this is used by both the requests() call as well as the latency calculation
# which is dependent on client host performance and workload
target_timeout = 1.0

# How often to test, or sleep between tests, of URL
test_interval = 60

# Take error message passed as an arguement, return with prepended date and time

def timestamp(err_msg):

    timestamp = "\n{:%Y-%m-%d %H:%M:%S}: {}".format(datetime.now(), err_msg)

    return (timestamp)

# Main body of program

def main():

    print ("\nMonitoring web site: {}".format(target_URL))

    while True:

        # start of loop, initialize to normal

        err_msg = "No Trouble Found"

        # Send get request to specified URL and test for errors

        try:

            start = timer()
            resp_URL = requests.get(target_URL, timeout=target_timeout)
            resp_URL.raise_for_status()
            latency = timer() - start

        # For HTTP or Timeout errors, sleep for awhile and loop back to top

        except requests.exceptions.HTTPError as e1:
            err_msg = "HTTP Error: " + str(e1)
            print (timestamp(err_msg))
            time.sleep(test_interval)
            continue
        except requests.exceptions.Timeout as e2:
            err_msg = "Timeout Error: " + str(e2)
            print (timestamp(err_msg))
            time.sleep(test_interval)
            continue

        # For Connection or Unknown errors, exit program immediately

        except requests.exceptions.ConnectionError as e3:
            err_msg = "Connection Error: " + str(e3)
            print (timestamp(err_msg))
            quit()
        except requests.exceptions.RequestException as e4:
            err_msg = "Unknown Error: " + str(e4)
            print (timestamp(err_msg))
            quit()

        # Calculate latency on URL get request. Complain if too long

        if latency >= target_timeout:
            err_msg = "Latency is: {0:4.2f}, threshold: {1}".format(latency, target_timeout)
            print (timestamp(err_msg))

        # Compute SHA1 hash of the URL contents so we can compare against expected

        hash_URL = sha1(resp_URL.content).hexdigest()

        if hash_URL != target_Hash:
            err_msg = "Hash is: {}, expected: {}".format(hash_URL, target_Hash)
            print (timestamp(err_msg))

        # Save URL contents to a file in case we want to examine further
        # Note this section may not be portable and does not work on IOS

##        file = open(target_file, "w+")
##        file.write(resp_URL.text)
##        file.close()

        print('.', end='', flush=True)    # Output dots to represent progress

        time.sleep(test_interval)


# If called from shell as script

if __name__ == '__main__':

    main()
