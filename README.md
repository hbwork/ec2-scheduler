# EC2/RDS Scheduler

An improved version of AWS EC2 Scheduler](https://aws.amazon.com/answers/ec2-scheduler) that enables customers to easily configure custom start and stop schedules for their Amazon EC2 and RDS dev/test instances. The solution is easy to deploy and can help reduce operational costs for both development and production environments.

# New Features!

  -  Start/Stop RDS instance (http://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html)
  -  Customzied Timezone support (pytz)
  -  Customzied AWS Region(s)
  -  Support start/stop EC2/RDS based on month day, nth weekdays, weekdays
  -  Default setting specified in AWS CloudWatch Event Target Input instead of DynamoDB table
  -  (bug fix) Support EC2 instance with encrypted EBS volumes

# Code 
## Cloudformation templates
- cform/ec2-scheduler.template

## Lambda source code
- code/ec2-scheduler.py

# Installation

You can deploy EC2/RDS scheduler either using AWS CLI (Linux) or from AWS Management Console:

## AWS CloudFormation Management Console
- CloudFormation Template:  cfrom/ec2-scheduler.template
- Paramters (please refer to https://aws.amazon.com/answers/infrastructure-management/ec2-scheduler/)

| Parameter | Default | Notes|
| ------ | ------ |------|
|DynamoDBTableName |  | Not Applicable, removed (default scheudler paramters are moved to CloudWatch Target Input)|
|ReadCapacityUnits |  | Same as above|
|WriteCapacityUnit |  | Same as above|
|Regions | all | AWS regions seperated by space(s) where EC2/RDS scheduler operates|
|DefaultTimeZone | utc | Default time zone for the scheduler|
|RDSSupport | Yes| Change to 'No' to disable RDS instance stop/start support|
|CustomRDSTagName | scheduler:rdcs-startstop| This tag identifies RDS instances to receive automated actions|
|S3BucketName | | S3 Bucket name where Lambda zipfile sits|

## AWS CLI

- Update stack parameters in deploy.sh

      #Stack Deploy Parameters
      StackName="ec2-scheduler"
      DefaultTimeZone="Australia/Melbourne"
      RDSSupport="Yes"
      Schedule="5minutes"
      #Regions='ap-southeast-2 ap-southeast-1'
      Regions="ap-southeast-2"
- Deploy the stack using Shell script
```sh
./deploy.sh s3_bucket_name [profilename]
````

# Notes
## Dependency
- pytz : https://pypi.python.org/pypi/pytz
    
## Exceptions
Please install boto3  locally if you experience blow error message which is caused by the outdated boto3 library provided by AWS lambda.
- 'RDS' object has no attribute 'start_db_instance'
-  'RDS' object has no attribute 'stop_db_instance'
```sh
    cd code
    pip install boto3 -t .
    pip install pytz -t .
    zip -r -9 ../ec2-scheduler.zip *
    aws s3 cp ../ec2-scheduler.zip s3bucket
````
## Customzied TimeZone Support
Please refer to https://pypi.python.org/pypi/pytz for valid timezone (same as timezone supported by Amazon Linux).
The easiest way is to check folder /usr/share/zoneinfo of Amazon Linux, for example:
```sh
    cd /usr/share/zoneinfo
    find . -type f |sed s'/^\.\///'|grep Australia
    ....
    Australia/Melbourne
    ...
````
"Australia/Melbourne" is a valid timezone .

## IAM Role RDS Permissions
AWS accounced RDS instance stop/stop support in June 1, 2017, as this file is wriiten, IAM role allow unstricted RDS API access "rds:*" because no AWS document states which RDS api applies to rds instance stop and start operations.
URL:

    - http://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAM.ResourcePermissions.html
    - https://aws.amazon.com/about-aws/whats-new/2017/06/amazon-rds-supports-stopping-and-starting-of-database-instances/

# Applying Custom Parameters
You can apply custom start and stop parameters to an EC2 or RDS instance which will orverwide the default values you set during initial deployment. To do this, mofidy the tag value to specify the alternative settings.

The EC2/RDS Scheduler will read tag values, looking for four possible custom parameters in foloowing order: 
<start time>; <stop time>; <time zone>; <active days(s)>

You can sepereate each values with a semicolon or colon. The following table gives acceptable input values for each field

|Tag Value Field|Acceptable input values|Scheduled Action/Note |
| ------ | ------ | ------ | 
|<start time> | none | No action|
|| 24x7| Start the instance at any time if it is stopped|
|| default| The instance will start and stop on the default schedule|
|| true| The instance will start and stop on the default schedule|
|| HHMM| Time in 24-hour format (Default time zone or timezone specified, with no colon)|
|<stop time> | none | No action|
|| HHMM| Time in 24-hour format (Default time zone or timezone specified, with no colon)|
|<time zone>| <empty>| Default scheduler time zone |
||utc| UTC time zone |
||Australia/Melbourne| Or any pytz library supported time zone value |
|<active day(s)|all| All days |
||weekdays| From Monday to Friday |
||sat,1,2| Saturday, 1st and 2nd in each month|
||sat/2, fri/4| The second Saturday and fourth Friday in each month|

# Example Tag Value

The following table gives examples of different tag values and the resulting Scheduler actions

|Example Tag Value|EC2 Scheduler Action|
|------ | ------|
|24x7 | start RDS/EC2 instance at any time if it is stopped|
|none | No action|
|default | The instance will start and stop on the default schedule|
|true | The instance will start and stop on the default schedule|
|0800;;;weekdays |Start the instance at 08:00 (Default Timezone) in weekdays if it is stopped|
|;1700;;weekdays |Stop the instance at 17:00 (Default Timezone) in weekdays if it is running.|
|0800;1800;utc;all|The instance will start at 0800 hours and stop at 1800 hours on all days|
|0001;1800;Etc/GMT+1;Mon/1| The instance will start at 0001 hour and stop at 1800 hour (first Monday of every month, Etc/GMT+1 timezone)|
|1000;1700;utc;weekdays | The instance will start at 1000 hours and stop at 1700 hours Monday through Friday.|
|1030;1700;utc;mon,tue,fri| The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday only.|
|1030;1700;utc;mon,tue,fri,1,3 |The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday or date 1,3 only.|
|1030;1700;utc;1 |The instance will start at 1030 hours and stop at 1700 hours on date 1 only.|
|1030;1700;utc;01,fri | The instance will start at 1030 hours and stop at 1700 hours on date 1 and Friday.|
|0815;1745;utc;wed,thu |The instance will start at 0815 hours and stop at 1745 hours on Wednesday and Thursday.|
|none;1800;utc;weekdays| The instance stop at 1800 hours Monday through Friday. |
|0800;none;utc;weekdays| The instance start at 0800 hours Monday through Friday. |
|1030;1700;utc;mon,tue,fri,1,3,sat/1|The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday ,date 1,3 or the first Saturday in every month (utc TimeZone)|
|1030;1700;;mon,tue,fri,1,3,sat/1|The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday ,date 1,3 or the first Saturday in every month (Default TimeZone)|
|1030;1700;Australia/Sydney;mon,tue,fri,1,3,sat/1 | The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday ,date 1,3 or the first Saturday in every month (Australia/Sydney TimeZone)|

# Author
- Initial version: AWS provided
- Updated by:
Eric Ho (eric.ho@datacom.com.au, hbwork@gmail.com, https://www.linkedin.com/in/hbwork/)
Last update: July 22, 2017

***

Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/asl/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.
