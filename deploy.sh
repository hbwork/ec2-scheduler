#!/bin/bash
# 
# deploy.sh
#   Shell script to deploy Aws EC2/RDS Scheduer 
# Dependecy: 
#   - pip
#   - AWS CLI configured with credential and default AWS regions
# Reference: https://aws.amazon.com/answers/infrastructure-management/ec2-scheduler/
# Author: Eric Ho (eric.ho@datacom.com.au, hbwork@gmail.com, https://www.linkedin.com/in/hbwork/)
#

function assume_role {
    if [ $(date "+%s") -ge ${TokenExpiration} ]
    then
        unset AWS_ACCESS_KEY_ID
        unset AWS_SECRET_ACCESS_KEY
        unset AWS_SECURITY_TOKEN
        unset TokenExpiration

        echo "(Renew) Assuming role arn:aws:iam::${AccountId}:role/${RoleName}"

        #Default session expiration period is 1 hour
        aws sts assume-role --role-session-name JenkinCiSession \
            --role-arn arn:aws:iam::${AccountId}:role/${RoleName} \
            --external-id ${ExternalId}  \
            | grep -w 'AccessKeyId\|SecretAccessKey\|SessionToken' \
            | awk  '{print $2}' \
            | sed  's/"//g;s/,//'\
            > awscre

        export AWS_ACCESS_KEY_ID=`sed -n '3p' /tmp/awscre`
        export AWS_SECRET_ACCESS_KEY=`sed -n '1p' /tmp/awscre`;
        export AWS_SECURITY_TOKEN=`sed -n '2p' /tmp/awscre`

        # Sesson expiration time  (50 minutes)
        export TokenExpiration=$(expr $(date "+%s") + 3000)

        rm awscre
    fi
}

# assume_role - Deploy EC2 Scheduer by assuming IAM role in other AWS account

#if [ "$#" -ne 5 ] ; then
#  echo "Usage: ./deploy.sh s3_bucket_name AwsAccountId IamRoleNamee externalId"
#  exit 1
#fi

#export AccountId=${2}
#export RoleName=${3}
#export ExternalId=${4}
#export TokenExpiration=$(date "+%s")
#assume_role

# End of assume_role


if [ "$#" -lt 1 ] ; then
    echo "Usage: ./deploy.sh s3_bucket_name [profilename]"
    exit 1
fi

#S3 BucketName for zip file
S3BucketName=${1}

# AWS CLI default profile 
ProfileName=${2:-default}

#Stack Deploy Parameters
StackName="ec2-scheduler"
DefaultTimeZone="Australia/Melbourne"
RDSSupport="Yes"
Schedule="5minutes" 
#Regions='ap-southeast-2 ap-southeast-1'
Regions="ap-southeast-2"

# End of Customzation 

rm -f *.zip

cd code

# boto3 library provided in lambda does not support rds.start_db_instance and rds.stop_db_instance (in July 20, 2017)
pip install boto3 -t .
pip install pytz -t .

zip -r -9 ../ec2-scheduler.zip *

aws s3 cp ../ec2*.zip s3://${S3BucketName}

cd ..

aws cloudformation validate-template --template-body file://cform/ec2-scheduler.template

set +e

StackStatus=$(aws cloudformation describe-stacks --stack-name ${StackName} --query Stacks[0].StackStatus --output text)

set -e

if [ ${#StackStatus} -eq 0 ]
then
    echo "Please ignore the Validation Error messagege above. Create CloudFormation stack ${StackName} ..."

    aws cloudformation create-stack --stack-name ${StackName} \
		  --template-body file://cform/ec2-scheduler.template \
    	--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    	--profile ${ProfileName} \
    	--parameters \
    	  ParameterKey=DefaultTimeZone,ParameterValue=${DefaultTimeZone}  \
    	  ParameterKey=RDSSupport,ParameterValue=${RDSSupport} \
    	  ParameterKey=Schedule,ParameterValue=${Schedule} \
    	  ParameterKey=S3BucketName,ParameterValue=${S3BucketName} \
    	  ParameterKey=Regions,ParameterValue="${Regions}"

    sleep 30

elif [ ${StackStatus} == 'CREATE_COMPLETE' -o ${StackStatus} == 'UPDATE_COMPLETE' ]
then
    echo "Update stack ${StackName} ..."

    ChangeSetName="${StackName}-$(uuidgen)"

    aws cloudformation create-change-set --stack-name ${StackName} \
          --template-body file://cform/ec2-scheduler.template \
    	    --profile ${ProfileName} \
          --change-set-name ${ChangeSetName} \
          --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    	    --parameters \
    	      ParameterKey=DefaultTimeZone,ParameterValue=${DefaultTimeZone}  \
    	      ParameterKey=RDSSupport,ParameterValue=${RDSSupport} \
    	      ParameterKey=Schedule,ParameterValue=${Schedule} \
    	      ParameterKey=S3BucketName,ParameterValue=${S3BucketName} \
    	      ParameterKey=Regions,ParameterValue="${Regions}"
    sleep 10

    ChangeSetStatus=$(aws cloudformation describe-change-set  \
    	  --profile ${ProfileName} \
        --change-set-name ${ChangeSetName} \
        --stack-name ${StackName} \
        --query Status \
        --output text)

    #CREATE_IN_PROGRESS , CREATE_COMPLETE , or FAILED
    while [ ${ChangeSetStatus} == 'CREATE_IN_PROGRES' ]
    do
        sleep 30
        ChangeSetStatus=$(aws cloudformation describe-change-set \
            --change-set-name ${ChangeSetName} \
    	      --profile ${ProfileName} \
            --stack-name ${StackName} \
            --query Status \
            --output text)
    done

	  if [ ${ChangeSetStatus} == 'FAILED' ]
	  then
        echo "Update lambda code using zip file"
        FunctionName=$(aws lambda list-functions --query Functions[].FunctionName \
    	      --profile ${ProfileName} \
            | grep ec2SchedulerOptIn |sed s/\",*//g |tr -d '[:space:]')

        aws lambda update-function-code --profile ${ProfileName} --function-name ${FunctionName} --zip-file fileb://ec2-scheduler.zip
    else
        echo "Execute change set ${ChangeSetName}"
        aws cloudformation execute-change-set --change-set-name ${ChangeSetName} --stack-name ${StackName} --profile ${ProfileName}
        sleep 30
    fi
else
    echo "Failed to create or update stack ${StackName} (Unexpected stack status: ${StackStatus})"
    exit 1
fi

StackStatus=$(aws cloudformation describe-stacks \
    --stack-name ${StackName} \
    --query Stacks[0].StackStatus \
    --output text  \
    --profile ${ProfileName})

#CREATE_IN_PROGRESS
#UPDATE_IN_PROGRESS

while [ $StackStatus == "CREATE_IN_PROGRESS" -o $StackStatus == "UPDATE_IN_PROGRESS" ]
do
    sleep 30
    StackStatus=$(aws cloudformation describe-stacks \
      --stack-name ${StackName} \
      --query Stacks[0].StackStatus \
      --output text  \
      --profile ${ProfileName})
done

# CREATE_COMPLETE
# UPDATE_COMPLETE
# UPDATE_COMPLETE_CLEANUP_IN_PROGRESS
if [ $StackStatus != "CREATE_COMPLETE" -a $StackStatus != "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS" -a $StackStatus != "UPDATE_COMPLETE" ]
then
    echo "Create/Update stack failed - ${StackStatus}"
    exit 1
fi

echo "Create/Update stack succeeded"
# __EOF__
