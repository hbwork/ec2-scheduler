######################################################################################################################
#  Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           #
#                                                                                                                    #
#  Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance        #
#  with the License. A copy of the License is located at                                                             #
#                                                                                                                    #
#      http://aws.amazon.com/asl/                                                                                    #
#                                                                                                                    #   
#  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    #
#  and limitations under the License.                                                                                #
######################################################################################################################


import boto3
import datetime
import json
from urllib2 import Request
from urllib2 import urlopen
from collections import Counter

# Import re to analyse month day
import re

# Import pytz to support local timezone
import pytz


#Default startTime, stopTime, TimeZone
defaultStartTime = 'none'
defaultStopTime = 'none'
defaultTimeZone = 'utc'
defaultDaysActive = 'all'

def putCloudWatchMetric(region, instance_id, instance_state):
    
    cw = boto3.client('cloudwatch')

    cw.put_metric_data(
        Namespace='EC2Scheduler',
        MetricData=[{
            'MetricName': instance_id,
            'Value': instance_state,

            'Unit': 'Count',
            'Dimensions': [
                {
                    'Name': 'Region',
                    'Value': region
                }
            ]
        }]
        
    )

def scheduler_action(tagValue):
    # Weekdays Interpreter
    weekdays = ['mon', 'tue', 'wed', 'thu', 'fri']

    # Monthdays Interpreter (1..31)
    monthdays = re.compile(r'^(0?[1-9]|[12]\d|3[01])$')

    # nth weekdays Interpreter
    nthweekdays=re.compile('\w{3}/\d{1}')

    # Split out Tag & Set Variables to default
    default1 = 'default'
    default2 = 'true'

    #Default scheduler action
    Action = 'None'

    ptag = tagValue.replace(':',';').split(";")

    startTime = defaultStartTime
    stopTime = defaultStopTime
    timeZone = defaultTimeZone
    daysActive = defaultDaysActive

    # Default Timzone
    tz = pytz.timezone(defaultTimeZone)

    # Valid timezone
    isValidTimeZone = True

    # Parse tag-value
    if len(ptag) >= 1:
        if ptag[0].lower() in (default1, default2):
            startTime = defaultStartTime
        else:
            startTime = ptag[0]
            stopTime = ptag[0]

    # Support 24x7
    if startTime  == '24x7':
        return "START"

    if len(ptag) >= 2:
        stopTime = ptag[1]
    if len(ptag) >= 3:
        #Timezone is case senstive
        timeZone = ptag[2]

        # timeZone is not empty and not DefaultTimeZone
        if timeZone != defaultTimeZone and timeZone != '':
            # utc is not included in pytz.all_timezones
            if timeZone != 'utc':
                if timeZone in pytz.all_timezones:
                    tz = pytz.timezone(timeZone)
                # No action if timeZone is not supported
                else:
                    print "Invalid time zone :", timeZone
                    isValidTimeZone = False
            # utc timezone
            else:
                tz = pytz.timezone('utc')

    if len(ptag) >= 4:
        daysActive = ptag[3].lower()

    now = datetime.datetime.now(tz).strftime("%H%M")

    if  datetime.datetime.now(tz).strftime("%H") != '00':
        nowMax = datetime.datetime.now(tz) - datetime.timedelta(minutes=59)
        nowMax = nowMax.strftime("%H%M")
    else:
        nowMax = "0000"

    nowDay = datetime.datetime.now(tz).strftime("%a").lower()
    nowDate = int(datetime.datetime.now(tz).strftime("%d"))

    isActiveDay = False

    # 24x5 support 
    if startTime  == '24x5':
       if nowDay == 'mon':
           startTime = defaultStartTime
           stopTime = 'none'
           isActiveDay = True
       elif nowDay == 'fri':
           isActiveDay = True
           startTime = 'none'
           stopTime = defaultStopTime

    elif daysActive == "all":
        isActiveDay = True
    elif daysActive == "weekdays":
        if (nowDay in weekdays):
            isActiveDay = True
    else:
        for d in daysActive.split(","):
            # mon, tue,wed,thu,fri,sat,sun ?
            if d.lower() == nowDay:
                    isActiveDay = True
            # Month days?
            elif monthdays.match(d):
                if int(d) == nowDate:
                     isActiveDay = True
            # mon/1 first Monday of the month
            # tue/2 second Tuesday of the month
            # Fri/3 third Friday of the month
            # sat/4 forth Saturday of the month
            elif nthweekdays.match(d):
                (weekday,nthweek) = d.split("/")

                if (weekday.lower() == nowDay) and ( nowDate >= (int(nthweek) * 7 - 6)) and (nowDate <= (int(nthweek) * 7)):
                   isActiveDay = True

    if startTime >= str(nowMax) and startTime <= str(now) and isActiveDay == True and isValidTimeZone == True:
        Action = "START"

    if stopTime >= str(nowMax) and stopTime <= str(now) and isActiveDay == True and isValidTimeZone == True:
        Action = "STOP"

    return Action

def lambda_handler(event, context):
    global defaultStartTime
    global defaultStopTime
    global defaultTimeZone
    global defaultDaysActive

    print "Running EC2 and RDS Scheduler"

    ec2 = boto3.client('ec2')

    if event['Regions'] == 'all':
        AwsRegionNames = []
        for r in ec2.describe_regions()['Regions']:
            AwsRegionNames.append(r['RegionName'])
    else:
        AwsRegionNames = event['Regions'].split()

    print "Operate in regions: ", " ".join(AwsRegionNames)

    # Reading Default Values from CloudWatch Rule Input event
    customTagName = event['CustomTagName']
    customTagLen = len(customTagName)
    sendData = event['SendAnonymousData'].lower()
    createMetrics = event['CloudWatchMetrics'].lower()
    UUID = event['UUID']

    # Set global default value
    defaultStartTime = event['DefaultStartTime']
    defaultStopTime = event['DefaultStopTime']
    defaultTimeZone = event['DefaultTimeZone']
    defaultDaysActive = event['DefaultDaysActive']

    #Customized RDS Tag Name
    RDSSupport = event['RDSSupport']
    customRDSTagName = event['CustomRDSTagName']
    customRDSTagLen = len(customRDSTagName)

    TimeNow = datetime.datetime.utcnow().isoformat()
    TimeStamp = str(TimeNow)

    # Declare Dicts
    regionDict = {}
    allRegionDict = {}
    regionsLabelDict = {}
    postDict = {}

    for region_name in AwsRegionNames:
        try:
            # Create connection to the EC2 using Boto3 resources interface
            ec2 = boto3.resource('ec2', region_name = region_name)

            # Declare Lists
            startList = []
            stopList = []
            runningStateList = []
            stoppedStateList = []

            # List all instances
            instances = ec2.instances.all()

            print "Creating ", region_name, " EC2 instance lists..."

            for i in instances:
                if i.tags != None:
                    for t in i.tags:
                        if t['Key'][:customTagLen] == customTagName:

                            state = i.state['Name']
                            itype = i.instance_type

                            # Post current state of the instances
                            if createMetrics == 'enabled':
                                if state == "running":
                                    putCloudWatchMetric(region_name, i.instance_id, 1)
                                if state == "stopped":
                                    putCloudWatchMetric(region_name, i.instance_id, 0)

                            action = scheduler_action(tagValue = t['Value'])

                            # Append to start list
                            if action == "START" and state == "stopped":
                                if i.instance_id not in startList:
                                    startList.append(i.instance_id)
                                    print i.instance_id, " added to START list"
                                    if createMetrics == 'enabled':
                                        putCloudWatchMetric(region_name, i.instance_id, 1)
                                # Instance Id already in startList

                            # Append to stop list
                            if action == "STOP" and state == "running":
                                if i.instance_id not in stopList:
                                    stopList.append(i.instance_id)
                                    print i.instance_id, " added to STOP list"
                                    if createMetrics == 'enabled':
                                        putCloudWatchMetric(region_name, i.instance_id, 0)
                                # Instance Id already in stopList

                            if state == 'running':
                                runningStateList.append(itype)
                            if state == 'stopped':
                                stoppedStateList.append(itype)

            # Execute Start and Stop Commands
            if startList:
                print "Starting", len(startList), "instances", startList
                ec2.instances.filter(InstanceIds=startList).start()
            else:
                print "No Instances to Start in region ",  region_name

            if stopList:
                print "Stopping", len(stopList) ,"instances", stopList
                ec2.instances.filter(InstanceIds=stopList).stop()
            else:
                print "No Instances to Stop in region ", region_name

            # Built payload for each region
            if sendData == "yes":
                countRunDict = {}
                typeRunDict = {}
                countStopDict = {}
                typeStopDict = {}
                runDictType = {}
                stopDictType = {}
                runDict = dict(Counter(runningStateList))
                for k, v in runDict.iteritems():
                    countRunDict['Count'] = v
                    typeRunDict[k] = countRunDict['Count']

                stopDict = dict(Counter(stoppedStateList))
                for k, v in stopDict.iteritems():
                    countStopDict['Count'] = v
                    typeStopDict[k] = countStopDict['Count']

                runDictType['instance_type'] = typeRunDict
                stopDictType['instance_type'] = typeStopDict

                typeStateSum = {}
                typeStateSum['running'] = runDictType
                typeStateSum['stopped'] = stopDictType
                StateSum = {}
                StateSum['instance_state'] = typeStateSum
                regionDict[region_name] = StateSum
                allRegionDict.update(regionDict)
            
        except Exception as e:
            print ("Exception: "+str(e))
            continue

        if RDSSupport == "Yes":
            # Declare Lists
            rdsStartList = []
            rdsStopList = []
            rdsRunningStateList = []
            rdsStoppedStateList = []

            print "Creating ", region_name, " RDS instance lists..."
            try:
                rds = boto3.client('rds', region_name =  region_name)
                rds_instances = rds.describe_db_instances()

                for rds_instance in rds_instances['DBInstances']:

                    if len(rds_instance['ReadReplicaDBInstanceIdentifiers']):
                        print "----- No action against RDS instance (with read replica): ", rds_instance['DBInstanceIdentifier']
                        continue

                    if "ReadReplicaSourceDBInstanceIdentifier" in rds_instance.keys():
                        print "----- No action against RDS instance (replication): ", rds_instance['DBInstanceIdentifier']
                        continue

                    if rds_instance['MultiAZ']:
                        print "----- No action against RDS instance (Multiple AZ): ", rds_instance['DBInstanceIdentifier']
                        continue

                    if rds_instance['DBInstanceStatus'] not in ["available","stopped"]:
                        print "----- No action against RDS instance (unsupported status):", rds_instance['DBInstanceIdentifier']
                        continue

                    # Query RDS instance tags 
                    response = rds.list_tags_for_resource( ResourceName = rds_instance['DBInstanceArn'])
                    tags = response['TagList']

                    for t in tags:
                        if t['Key'][:customRDSTagLen] == customRDSTagName:

                            action = scheduler_action(tagValue = t['Value'])
                            state = rds_instance['DBInstanceStatus'] 

                            # Append to start list
                            if action == "START" and state == "stopped":
                                if rds_instance['DBInstanceIdentifier'] not in rdsStartList:
                                    rdsStartList.append(rds_instance['DBInstanceIdentifier'])
                                    print rds_instance['DBInstanceIdentifier'], " added to RDS START list"
                                # Instance Id already in rdsStartList

                            # Append to stop list
                            if action == "STOP" and state == "available":
                                if rds_instance['DBInstanceIdentifier'] not in rdsStopList:
                                    rdsStopList.append(rds_instance['DBInstanceIdentifier'])
                                    print rds_instance['DBInstanceIdentifier'], " added to RDS STOP list"
                                # Instance Id already in rdsStopList

                # Execute Start and Stop Commands
                if rdsStartList:
                    print "Starting", len(rdsStartList), "RDS instances", rdsStartList
                    for DBInstanceIdentifier in rdsStartList:
                        rds.start_db_instance(DBInstanceIdentifier = DBInstanceIdentifier)
                else:
                    print "No RDS Instances to Start in region ",  region_name

                if rdsStopList:
                    print "Stopping", len(rdsStopList) ,"RDS instances", rdsStopList
                    for DBInstanceIdentifier in rdsStopList:
                        rds.stop_db_instance(DBInstanceIdentifier = DBInstanceIdentifier)
                else:
                    print "No RDS Instances to Stop in region ", region_name

            except Exception as e:
                print ("Exception: "+str(e))
                continue

    # Build payload for the account
    if sendData == "yes":
        regionsLabelDict['regions'] = allRegionDict
        postDict['Data'] = regionsLabelDict
        postDict['TimeStamp'] = TimeStamp
        postDict['Solution'] = 'SO0002'
        postDict['UUID'] = UUID
        # API Gateway URL to make HTTP POST call
        url = 'https://metrics.awssolutionsbuilder.com/generic'
        data=json.dumps(postDict)
        headers = {'content-type': 'application/json'}
        req = Request(url, data, headers)
        rsp = urlopen(req)
        content = rsp.read()
        rsp_code = rsp.getcode()
        print ('Response Code: {}'.format(rsp_code))

# Local version
if  __name__ =='__main__':
    event = {
        "DefaultStartTime": "0800",
        "DefaultStopTime": "1800",
        "UUID": "27b0ceaa-2162-47d0-9ed1-e7e76f22cbba",
        "SolutionName": "EC2Scheduler",
        "DefaultDaysActive": "all",
        "Regions": "ap-southeast-2",
        "DefaultTimeZone": "Australia/Melbourne",
        "RDSSupport": "Yes",
        "SendAnonymousData": "No",
        "CustomTagName": "scheduler:ec2-startstop",
        "CustomRDSTagName": "scheduler:rds-startstop",
        "CloudWatchMetrics": "Enabled"
    }

    context = None

    lambda_handler(event = event, context = context)

#EOF
