# ec2-scheduler

The [EC2 Scheduler](https://aws.amazon.com/answers/ec2-scheduler) is a simple AWS-provided solution that enables customers to easily configure custom start and stop schedules for their Amazon EC2 instances. The solution is easy to deploy and can help reduce operational costs for both development and production environments. 

Source code for the AWS solution "EC2 Scheduler". 

## New Features
- Start/Stop RDS instance (http://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html)
- Customzied Timezone support (pytz)
- Customzied AWS Region(s)
- Support start/stop EC2/RDS based on month day, nth weekdays, weekdays
- Default setting specified in AWS CloudWatch Rule input instead of DynamoDB table 
- Support EC2 instance with encrypted EBS volumes

## Cloudformation templates

- cform/ec2-scheduler.template

## Lambda source code

- code/ec2-scheduler.py

## Notes
### Dependency 

- boto3
- pytz : https://pypi.python.org/pypi/pytz

    Please install boto3 and pytz locally if you experience blow error message which is caused by the outdated boto3 library provided by AWS lambda.
     
    cd code
    
    pip install boto3 -t .
    
    pip install pytz -t .
    

### Customzied TimeZone Support

- Please refer to https://pypi.python.org/pypi/pytz for valid timezone (same as timezone supported by Amazon Linux)
- The easiest way is to check folder /usr/share/zoneinfo of Amazon Linux, for example

    cd /usr/share/zoneinfo
    
    find . -type f |sed s'/^\.\///'|grep Australia
    
    ....
    
    Australia/Melbourne
    ...
    
    "Australia/Melbourne" is a valid timezone .


### IAM Role RDS Permissions 

    AWS accounced RDS instance stop/stop support in June 1, 2017, as this file is wriiten, IAM role allow unstricted RDS API access "rds:*" because no AWS document states which RDS api applies to rds instance stop and start operations.
    
    URL: 
    
    - http://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAM.ResourcePermissions.html
    - https://aws.amazon.com/about-aws/whats-new/2017/06/amazon-rds-supports-stopping-and-starting-of-database-instances/

## Author
- Initial version: AWS provided
- Updated by: 

    Eric Ho (eric.ho@datacom.com.au, hbwork@gmail.com, https://www.linkedin.com/in/hbwork/)
    
   Last update: July 20, 2017

***

Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/asl/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.
