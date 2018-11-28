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

__author__      = "Michael E. O'Connor"
__copyright__   = "Copyright 2018"

import os
import sys
import time
import signal
import requests
import threading
#from tkinter import *
from tkinter import Tk, Label, Button, Scrollbar, IntVar, StringVar, Text
from tkinter import BOTH, END, HORIZONTAL, VERTICAL, W, E, N, S, X, Y
from tkinter import ACTIVE, YES, RIGHT, LEFT, SUNKEN, DISABLED
from tkinter import ttk
from hashlib import sha1
from timeit import default_timer as timer

# AWS Boto3 and botocore only needed when using AWS SNS notification service option

try:
    import boto3
    from botocore.exceptions import ProfileNotFound, ClientError
except ImportError:
    print('Unable to load Boto3 or botocore modules')

#--------------------------------------------------------------------------
# Dictionary of Web URLs we want to monitor. Each will become a Radiobutton
# in the GUI. 'DEFAULT' entry is use to determine the pre-selected URL
#--------------------------------------------------------------------------

sites = {
    'Portfolio': 'https://www.mikeoc.me',
    'Keto Legal': 'https://www.ketolegal.com',
    'Google.com': 'https://www.google.com',
    'Amazon.com': 'https://www.amazon.com',
    '_DEFAULT_': 'https://www.mikeoc.me'
}

#-------------------------------------------------------------------------
# Global variables used to control use AWS SMS to alert about problems
# AWS_Valid used to control if AWS SNS will be used to notify User
# Sns_client used to store AWS botocore SNS object
#-------------------------------------------------------------------------

AWS_Valid = False
Sns_client = True

#-------------------------------------------------------------------------
# Global variable used as a flag to control termination of monitoring thread.
# Set to True initially, toggled in gui thread and checked in monitor thread.
#-------------------------------------------------------------------------

keep_monitoring = True

#-----------------------------------------------------
# Return current date and time configured for local TZ
#-----------------------------------------------------

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

def validate_aws_env():
    try:
        aws_profile = os.environ["AWS_PROFILE"]
        resp = input ('AWS_PROFILE = [{aws_profile}]. Press enter to confirm or specify new: ')

        if bool(resp.strip()):
            print ('AWS Profile changed to [{resp}]')
            aws_profile = resp

    except KeyError:
        aws_profile = input ("AWS_PROFILE not set. Please enter a valid AWS_PROFILE: ")

    os.environ["AWS_PROFILE"] = aws_profile

    while True:             # Allow user multiple attempts to get it right
        try:
            target_phone = os.environ["CELL_PHONE"]
            resp = input ('CELL_PHONE = [{target_phone}]. Press enter to confirm or specify new: ')

            if bool(resp.strip()):
                print ('Mobile changed to [{resp}]')
                target_phone = resp

        except KeyError:
            target_phone = input ("CELL_PHONE not set. Enter a valid Mobile # [+12345679999]: ")

        # Validate phone number format, break if correct, warn and loop if not

        if (len(target_phone) == 12) and (target_phone[0:2] == '+1'):
            os.environ["CELL_PHONE"] = target_phone
            break
        else:
            print ("Error: phone # must start with +1 followed by 10 digits")

    return

#----------------------------------------------------------------------------
# Confirm user is known to AWS and that user has required SNS authorization
# Assumes that environment variables have been previously set. If attempt to
# send initial SMS message via SNS succeeds, set global AWS_Valid to True
# ---------------------------------------------------------------------------

def validate_aws_auth(service):

    mobile = os.environ["CELL_PHONE"]
    user = os.environ["AWS_PROFILE"]
    message = "Begin Monitoring: "

    global AWS_Valid                       # Make global so we can toggle

    try:
        client = boto3.client(service)
        client.publish(PhoneNumber=mobile, Message=message)
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

    mobile_num = os.environ["CELL_PHONE"]

    send_console ("Sending SMS", "Msg= {}, num= {}".format(message, mobile_num))

    try:
        client.publish(PhoneNumber=mobile_num, Message=message)
    except ClientError:
        send_console ("Error:", "Unable to send SMS message via AWS", "\n")

#-------------------------------------------------------------
# Print output to console with time stamp. Output consists of
# message detail (raw_msg) and summary info (short_msg)
#-------------------------------------------------------------

def send_console(short_msg, raw_msg = "", cr = ""):
    print(cr + "{} {}: {}".format(t_stamp(), short_msg, raw_msg))
    return

class Monitor_Gui:
    '''Main GUI TKinter thread
    '''

    def __init__(self, master):
        self.master = master
        self.bstate = StringVar()
        self.bstate.set("Start Monitoring")

        self.s = ttk.Style()
        self.s.configure('.', font=('Arial', 14))
        self.s.configure('TButton', foreground='green', relief='sunken', padding=5)
        self.s.configure ('TLabel', background="yellow", foreground="white")

        master.title('Website Monitoring Tool')
        frame0 = ttk.Panedwindow(master, orient = HORIZONTAL)
        frame0.pack(fill = BOTH, expand = True)
        frame1 = ttk.Frame(frame0, width = 100, height = 300, relief = SUNKEN)
        frame2 = ttk.Frame(frame0, width = 1000, height = 300, relief = SUNKEN)
        frame0.add(frame1, weight = 1)
        frame0.add(frame2, weight = 10)

        # Build Radio Buttons used to select what and how we want to monitor

        Label(frame1, text = "Web Site", bg="black", fg="white", justify = LEFT).pack(fill=X)
        self.site = StringVar()
        for k,v in sites.items():
            if k != '_DEFAULT_':
                b = ttk.Radiobutton(frame1, text=k, variable=self.site, value=v).pack(anchor='w')
        self.site.set(sites['_DEFAULT_'])

        Label(frame1, text = "Sample period", bg="black", fg="white", justify = LEFT).pack(fill=X)
        self.period = IntVar()
        b = ttk.Radiobutton(frame1, text="5 seconds", variable=self.period, value=5).pack(anchor='w')
        b = ttk.Radiobutton(frame1, text="1 minute", variable=self.period, value=60).pack(anchor='w')
        b = ttk.Radiobutton(frame1, text="5 minutes", variable=self.period, value=300).pack(anchor='w')
        self.period.set(5)

        Label(frame1, text = "Timeout", bg="black", fg="white", justify = LEFT).pack(fill=X)
        self.timeout = IntVar()
        b = ttk.Radiobutton(frame1, text="1 seconds", variable=self.timeout, value=1).pack(anchor='w')
        b = ttk.Radiobutton(frame1, text="3 seconds", variable=self.timeout, value=3).pack(anchor='w')
        b = ttk.Radiobutton(frame1, text="5 seconds", variable=self.timeout, value=5).pack(anchor='w')
        self.timeout.set(1)

        # Build Button used to start monitoring

        self.start_button = ttk.Button(frame1)
        self.start_button.config(text=self.bstate.get(), command=self.submit)
        self.s.configure('TButton', foreground='green', relief='raised', padding=5, state=DISABLED)
        self.start_button.pack(anchor = 's')

        # Build Text Box with Scrollbar we will use to display Results

        self.result_box = Text(frame2, width=100, height=20)
        scrollbar = Scrollbar(frame2, orient=VERTICAL, command=self.result_box.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.result_box["yscrollcommand"]=scrollbar.set
        self.result_box.pack(side=LEFT, fill=BOTH, expand = YES)

    def submit(self):
        '''Sets monitoring flag to True, starts monitoring thread and
           toggles button state
        '''
        global keep_monitoring

        keep_monitoring = True
        monitor(tbox=self.result_box, url=self.site.get(), interval=self.period.get(), timeout=self.timeout.get())
        self.toggle_button()
        self.master.title("Monitoring: " + self.site.get())

    def clear(self):
        '''Clears output textbox, sets monitoring flag to False and
           toggles button state
        '''
        global keep_monitoring

        keep_monitoring = False
        self.toggle_button()
        self.master.title("Web Site Monitoring Tool")
        self.result_box.delete(1.0, 'end')

    def toggle_button(self):
        '''Toggle button callback function and display attributes
        '''
        if self.bstate.get() == "Start Monitoring":
            self.bstate.set("Stop Monitoring")
            self.start_button.config(text="Stop Monitoring", command=self.clear)
            self.s.configure('TButton', foreground='red', relief='raised', padding=5, state=ACTIVE)
        else:
            self.bstate.set("Start Monitoring")
            self.start_button.config(text="Start Monitoring", command=self.submit)
            self.s.configure('TButton', foreground='green', relief='sunken', padding=5, state=DISABLED)

class monitor(threading.Thread):
    '''Monitors a given web site for timeouts and content changes
    '''
    global keep_monitoring        # Controlled by main GUI thread button press

    def __init__(self, tbox, url, interval, timeout, *args, **kwargs):

        threading.Thread.__init__(self, *args, **kwargs)
        self.setName('URL Monitor Thread')
        self.tbox = tbox
        self.url = url
        self.interval = interval
        self.timeout = timeout
        self.daemon = True      # Stop all threads when program terminates

        _msg = "Watching: {}, with Interval: {} and Timeout: {}".format \
            (self.url, self.interval, self.timeout)
        self.output(_msg, cr='\n')
        if AWS_Valid: self.output("AWS SNS Notification is active for", self.url)

        self.start()

    def run(self):
        '''Primary worker function gets content of web site and checks for errors
        '''
        previous_Hash = None

        while keep_monitoring:
            start = timer()

            # Check for problems with HTTP response and parse errors
            try:
                resp_URL = requests.get(self.url, timeout=self.timeout)
                resp_URL.raise_for_status()

            except requests.exceptions.Timeout as e1:
                self.output("Timeout Error", e1, "\n")
                if AWS_Valid: send_sms(Sns_client, "Timeout error")
                continue

            except requests.exceptions.ConnectionError as e2:
                self.output("Connection Error", e2, "\n")
                if AWS_Valid: send_sms(Sns_client, "Connection Error")
                continue

            # For HTTP or Unknown errors, log error and leave loop

            except requests.exceptions.HTTPError as e3:
                self.output("HTTP Error", e3, "\n")
                if AWS_Valid: send_sms(Sns_client, "HTTP Error")
                break

            except requests.exceptions.RequestException as e4:
                self.output("Unknown Error", e4, "\n")
                if AWS_Valid: send_sms(Sns_client, "Unknown Error")
                break

            # Calculate latency on URL get request. Complain if too slow

            latency = timer() - start

            if latency >= self.timeout:
                err_msg = "{}:{:4.2f}s, threshold: {}s".format(self.url, latency, self.timeout)
                self.output("Slow response", err_msg, "\n")
                if AWS_Valid: send_sms(Sns_client, "Slow response: " + err_msg)

            # Compute SHA1 hash of the URL contents so we can compare against previous.

            current_Hash = sha1(resp_URL.content).hexdigest()

            if current_Hash != previous_Hash:
                if previous_Hash == None:
                    self.output(self.url + " Hash", current_Hash)
                else:
                    self.output(self.url + " Hash changed", current_Hash, "\n")
                    if AWS_Valid: send_sms(Sns_client, "Web Site Contents changed")

                previous_Hash = current_Hash

            # Loop interval seconds while checking for flag state each second

            for i in range(self.interval):
                if keep_monitoring == True:
                    self.tbox.insert(END, '.')
                    time.sleep(1)
                else:
                    break

            if keep_monitoring == True:
                self.tbox.insert(END, '|')

    def output(self, short_msg, raw_msg = "", cr = ""):
        _msg = '{}{} {}: {}\n'.format(cr, t_stamp(), short_msg, raw_msg)
        self.tbox.insert(END, _msg)

#------------------------------------------------------------
# Main body of program
#------------------------------------------------------------

def main():

    global Sns_client

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
        validate_aws_env()
        Sns_client = validate_aws_auth('sns')
        print(Sns_client)
        if Sns_client == False:
            raise SystemExit()

    root = Tk()
    Monitor_Gui(root)
    root.mainloop()

# Signal handler for CTRL-C manual termination

def signal_handler(signal, frame):
    send_console("Program terminated manually", "", "\n")
    raise SystemExit()

# If called from shell as script

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
