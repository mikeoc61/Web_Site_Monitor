# Web_Site_Monitor

Simple Python program which opens a target URL and then loops at a specified interval checking

1. Accessibility

2. Latency

3. Changes based on a hash of contents

If there are problems with these, the program either terminates or reports the problem with a timestamp

Program optionally utilizes AWS SNS service to alert a mobile number of problems.
As such, AWS SDK with Boto3 needs to be installed and configured. Program
requires and promts for the following environment:

  AWS_PROFILE = profile defined in users ~/.aws/configure and credentials files

  CELL_PHONE = country code and 10-digit phone number. Currently only supports US '+1'

The following reddit post may be helpful in understanding some of the subtleties of the
AWS SNS service: https://www.reddit.com/r/aws/comments/63vldy/our_experience_using_aws_sns_for_sms/

# Requirements

Python3

> $ brew install python3 (recommended method for MacOS)

AWS CLI to set up environment used to configure user profile and keys in ~/.aws
and for Boto3 python modules

> $ brew install awscli (recommended method for MacOS)

# Tested with

- MacOS 10.13/14 and Python 3.6/7
