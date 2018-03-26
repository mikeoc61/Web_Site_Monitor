# Web_Site_Monitor

Simple Python program which opens a target URL and then loops at a specified interval checking

1. Accessibility

2. Latency

3. Changes based on a hash of contents

If there are problems with these, the program either terminates or reports the problem with a timestamp

Program also utilizes AWS SNS service to alert a mobile number of problems.
As such, AWS SDK with Boto3 need to be installed and configured. Program
requires that the following environment variables be set:

  AWS_PROFILE = profile defined in users ~/.aws/configure and credentials files

  CELL_PHONE = country code and 10-digit phone number. Currently only supports US '+1'

# Requirements

Python3

> $ brew install python3

AWS CLI to set up environment used to configure user profile and keys in ~/.aws
and for Boto3 python modules

> $ pip install awscli

# Tested with

- MacOS 10.13.3 and Python 3.6.4
