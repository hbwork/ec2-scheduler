#!/bin/bash

#if [ "$#" -ne 5 ] ; then
#  echo "Usage: ./deploy.sh s3_bucket_name accountId rolename externalId"
#  exit 1
#fi

#export AccountId=${2}
#export RoleName=${3}
#export ExternalId=${4}
#export TokenExpiration=$(date "+%s")

function assume_role {
  if [ $(date "+%s") -ge ${TokenExpiration} ]
  then
    unset AWS_ACCESS_KEY_ID
    unset AWS_SECRET_ACCESS_KEY
    unset AWS_SECURITY_TOKEN
    unset TokenExpiration

    echo "(Renew) Assuming role arn:aws:iam::${AccountId}:role/${RoleName}"

    #Default session expiration period is 1 hour
    aws sts assume-role --role-session-name JenkinCiSession --role-arn arn:aws:iam::${AccountId}:role/${RoleName} --external-id ${ExternalId}  \
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

# assume_role
rm -f *.zip

cd code

pip install pytz -t .

zip -r -9 ../ec2-scheduler.zip *

aws s3 cp ../ec2*.zip s3://dcp-install --profile dcp

cd ..

aws cloudformation validate-template --template-body file://cform/ec2-scheduler.template

set +e

StackStatus=$(aws cloudformation describe-stacks --stack-name ec2-scheduler --query Stacks[0].StackStatus --output text)

set -e

if [ ${#StackStatus} -eq 0 ]
then
    echo "Stack ec2-scheduler does not exist, create stack"
    Action="create-stack"

    aws cloudformation ${Action} --stack-name ec2-scheduler \
		--template-body file://cform/ec2-scheduler.template \
    	--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    	--parameters ParameterKey=DefaultTimeZone,ParameterValue='Australia/Melbourne' \
    	ParameterKey=RDSSupport,ParameterValue=Yes \
    	ParameterKey=Schedule,ParameterValue=1minute

    sleep 30

elif [ ${StackStatus} == 'CREATE_COMPLETE' -o ${StackStatus} == 'UPDATE_COMPLETE' ]
then
    echo "Update stack ec2-scheduler"

    ChangeSetName="jenkins-$(uuidgen)"

    aws cloudformation create-change-set --stack-name ec2-scheduler \
          --template-body file://cform/ec2-scheduler.template \
          --change-set-name ${ChangeSetName} \
          --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
          --parameters ParameterKey=DefaultTimeZone,ParameterValue='Australia/Melbourne' \
                    ParameterKey=RDSSupport,ParameterValue=Yes \
                    ParameterKey=Schedule,ParameterValue=1minute \

    sleep 10

	ChangeSetStatus=$(aws cloudformation describe-change-set --change-set-name ${ChangeSetName} --stack-name ec2-scheduler --query Status --output text)

    #CREATE_IN_PROGRESS , CREATE_COMPLETE , or FAILED
    while [ ${ChangeSetStatus} == 'CREATE_IN_PROGRES' ]
    do
    	sleep 30
    	ChangeSetStatus=$(aws cloudformation describe-change-set --change-set-name ${ChangeSetName} --stack-name ec2-scheduler --query Status --output text)
    done

	if [ ${ChangeSetStatus} == 'FAILED' ]
	then
    	echo "Update lambda code using zip file"
    	FunctionName=$(aws lambda list-functions --query Functions[].FunctionName |grep ec2SchedulerOptIn |sed s/\"//g |tr -d '[:space:]')

		aws lambda update-function-code --function-name ${FunctionName} --zip-file fileb://ec2-scheduler.zip
    else
    	echo "Execute change set ${ChangeSetName}"
		aws cloudformation execute-change-set --change-set-name ${ChangeSetName} --stack-name ec2-scheduler
    	sleep 30
    fi

else
    echo "Failed to create or update stack ec2-scheduler: expected stack status: ${StackStatus}"
    exit 1
fi


StackStatus=$(aws cloudformation describe-stacks --stack-name ec2-scheduler --query Stacks[0].StackStatus --output text)

#CREATE_IN_PROGRESS
#UPDATE_IN_PROGRESS

while [ $StackStatus == "CREATE_IN_PROGRESS" -o $StackStatus == "UPDATE_IN_PROGRESS" ]
do
	sleep 30
    StackStatus=$(aws cloudformation describe-stacks --stack-name ec2-scheduler --query Stacks[0].StackStatus --output text)
done

# CREATE_COMPLETE
# UPDATE_COMPLETE
# UPDATE_COMPLETE_CLEANUP_IN_PROGRESS
if [ $StackStatus != "CREATE_COMPLETE" -a $StackStatus != "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS" -a $StackStatus != "UPDATE_COMPLETE" ]
then
	echo "${Action} stack failed - ${StackStatus}"
    exit 1
fi
