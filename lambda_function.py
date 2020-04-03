#To execute the function in Lambda, the latest version of Boto3, botocore and urllib3 would be required. 
#A suggestion would be to create a Lambda Layer using these three Packages and refer it in the Lambda functions.

# DESCRIPTION : Custom Resource function to create a Target Group with Target Type as Lambda.

import json
import time
import random
from botocore.vendored import requests
import boto3

client = boto3.client('elbv2')

def lambda_handler(event, context):
    print('REQUEST BODY:n' + str(event))
    client = boto3.client('elbv2') 
    healthcheck=False     # Default set to false for parameter HealthCheckEnabled
    count = 1
    existencecheck = 0
    responseData= {}
    physical_id = 'Resource_not_created'
    #count = int(event['ResourceProperties']['count'])    #Uncomment this line if you are configuring the number of retries through the CFN template
    attempts = 0
    if count <= 3:
        count = 3
        
    #Check if the provided Lambda Target ARN is provided and the validity of it.
    if event['RequestType'] != 'Delete' :
        if 'TargetLambdaArn' not in event['ResourceProperties'] :
            responseStatus = 'FAILED'
            responseData = {'Failure': 'ARN for the Target Lambda Function missing. Provide the Target Lambda ARN in the property - TargetLambdaArn'}
            print("*************** Important : ARN for the Target Lambda Function missing. Provide the Target Lambda ARN in the property - TargetLambdaArn. ***************")
            print('Create failed. Sending response...')
            sendResponse(event, context, responseStatus, responseData, reason='ARN for the Target Lambda Function missing. Provide the Target Lambda ARN in the property - TargetLambdaArn', physical_resource_id=physical_id)
            return

        try :
            lambda_check = boto3.client('lambda').get_function(
                FunctionName = event['ResourceProperties']['TargetLambdaArn']
            )
        except :
            responseStatus = 'FAILED'
            responseData = {'Failure': 'ARN for the Target Lambda Function is not valid. Please check validity and Region and try again.'}
            print("*************** Important : ARN for the Target Lambda Function is not valid. Please check validity and Region and try again. ***************")
            print('Create failed. Sending response...')
            sendResponse(event, context, responseStatus, responseData, reason='ARN for the Target Lambda Function is not valid. Please check validity and Region and try again.', physical_resource_id=physical_id)
            return
    

    #Check and populate default Property Values
    if 'Name' in event['ResourceProperties'] :
        Name = event['ResourceProperties']['Name']
    else :
        Name = 'TG' + str(int(time.time()))

    if 'HealthCheckEnabled' in event['ResourceProperties'] :
        HealthCheckEnabled = event['ResourceProperties']['HealthCheckEnabled']
    else :
        HealthCheckEnabled = 'false'

    if 'HealthCheckPath' in event['ResourceProperties'] :
        HealthCheckPath = event['ResourceProperties']['HealthCheckPath']
    else :
        HealthCheckPath = '/'

    if 'HealthCheckIntervalSeconds' in event['ResourceProperties'] :
        HealthCheckIntervalSeconds = int(event['ResourceProperties']['HealthCheckIntervalSeconds'])
    else :
        HealthCheckIntervalSeconds = 35

    if 'HealthCheckTimeoutSeconds' in event['ResourceProperties'] :
        HealthCheckTimeoutSeconds = int(event['ResourceProperties']['HealthCheckTimeoutSeconds'])
    else :
        HealthCheckTimeoutSeconds = 30

    if 'HealthyThresholdCount' in event['ResourceProperties'] :
        HealthyThresholdCount = int(event['ResourceProperties']['HealthyThresholdCount'])
    else :
        HealthyThresholdCount = 5

    if 'UnhealthyThresholdCount' in event['ResourceProperties'] :
        UnhealthyThresholdCount = int(event['ResourceProperties']['UnhealthyThresholdCount'])
    else :
        UnhealthyThresholdCount = 2

    if 'MatcherHttpCode' in event['ResourceProperties'] :
        MatcherHttpCode = event['ResourceProperties']['MatcherHttpCode']
    else :
        MatcherHttpCode = '200'
                    
    while attempts < count:
        try:
            
            #Delete
            if event['RequestType'] == 'Delete':
                print ("delete")
                if (event['PhysicalResourceId'] != 'Resource_not_created'):
                    responseData = client.delete_target_group(
                        TargetGroupArn=event['PhysicalResourceId']
                        )
                print("Response:" + str(responseData))
            
            #Create
            elif event['RequestType'] == 'Create':
                print ("create")
                if(HealthCheckEnabled.lower() == 'true'):
                    healthcheck = True
                
                #Check if the resource already exists
                try:
                    existencecheck = 1
                    response = client.describe_target_groups(
                        Names=[
                            Name
                        ]
                    )
                    responseStatus = 'FAILED'
                    responseData = {'Failure': 'Resource already exists.'}
                    print(response)
                    print("*************** Resource already exists ***************")
                    print('Create failed. Sending response...')
                    sendResponse(event, context, responseStatus, responseData, reason='Resource already exists', physical_resource_id=physical_id)
                    break
                except Exception as e:
                    print('Creating new Target Group')
                    responseData = client.create_target_group(
                        Name = Name,
                        HealthCheckEnabled = healthcheck, 
                        HealthCheckPath = HealthCheckPath,
                        HealthCheckIntervalSeconds = HealthCheckIntervalSeconds,
                        HealthCheckTimeoutSeconds = HealthCheckTimeoutSeconds,
                        HealthyThresholdCount = HealthyThresholdCount,
                        UnhealthyThresholdCount = UnhealthyThresholdCount,
                        Matcher={
                            'HttpCode': MatcherHttpCode
                        },
                        TargetType='lambda'
                    )


                    #Target Registration
                    
                    try:
                        tgarn = responseData['TargetGroups'][0]['TargetGroupArn']

                        #addPolicy for TG to invoke Lambda
                        try :
                            addPolicyResponse = boto3.client('lambda').add_permission(
                                FunctionName=str(event['ResourceProperties']['TargetLambdaArn']).split(':')[6],
                                StatementId= ('AWS-ALB_Invoke-' + tgarn.split('/')[1] + '-' + tgarn.split('/')[2]),
                                Action='lambda:InvokeFunction',
                                Principal="elasticloadbalancing.amazonaws.com",
                                SourceArn=tgarn,
                            )
                            print('Policy Addition Response : \n' + str(addPolicyResponse))
                        except Exception as e:
                            print ('Error adding policy : \n' + str(e))
                            if ('ResourceConflictException' not in str(e)):
                                raise RuntimeError('Error registering target : ' + str(e))
                            else:
                                pass

                        #Register Lambda in TG
                        targetRegisterResponse = client.register_targets(
                            TargetGroupArn = responseData['TargetGroups'][0]['TargetGroupArn'],
                            Targets=[
                                {
                                    'Id': event['ResourceProperties']['TargetLambdaArn']
                                }
                            ]
                        )
                        print ('Register Lambda tarets to Target Group : \n' + str(targetRegisterResponse))
                            
                    except Exception as e :
                        print ('Error registering target : ' + str(e))
                        raise RuntimeError('Error registering target : ' + str(e))

                print("Response:" + str(responseData))
                physical_id = responseData['TargetGroups'][0]['TargetGroupArn']
            
            #Update
            elif event['RequestType'] == 'Update':
                print ("update")
                if(HealthCheckEnabled.lower() == 'true'):
                    healthcheck = True
                
                Oldname= ((event['PhysicalResourceId']).split('/'))[1]

                if (Name != Oldname):
                    if ('Name' not in  event['ResourceProperties'] and 'Name' not in  event['OldResourceProperties']) :
                        responseData = client.modify_target_group(
                            TargetGroupArn=event['PhysicalResourceId'],
                            HealthCheckEnabled = healthcheck, 
                            HealthCheckPath = HealthCheckPath,
                            HealthCheckIntervalSeconds = HealthCheckIntervalSeconds,
                            HealthCheckTimeoutSeconds = HealthCheckTimeoutSeconds,
                            HealthyThresholdCount = HealthyThresholdCount,
                            UnhealthyThresholdCount = UnhealthyThresholdCount,
                            Matcher={
                                'HttpCode': MatcherHttpCode
                            }
                        )
                    else :
                        print('Resource name changed. Thus creating new resource and deleting the old one.')
                        #Check if the resource already exists
                        try:
                            existencecheck = 1
                            response = client.describe_target_groups(
                                Names=[
                                    Name
                                ]
                            )
                            responseStatus = 'FAILED'
                            responseData = {'Failure': 'Resource already exists.'}
                            print(response)
                            print("*************** Resource already exists ***************")
                            print('Create failed. Sending response...')
                            sendResponse(event, context, responseStatus, responseData, reason='Resource already exists.', physical_resource_id=physical_id)
                            break
                        except Exception as e:
                            print('Creating new Target Group')
                            responseData = client.create_target_group(
                                Name = Name,
                                HealthCheckEnabled = healthcheck, 
                                HealthCheckPath = HealthCheckPath,
                                HealthCheckIntervalSeconds = HealthCheckIntervalSeconds,
                                HealthCheckTimeoutSeconds = HealthCheckTimeoutSeconds,
                                HealthyThresholdCount = HealthyThresholdCount,
                                UnhealthyThresholdCount = UnhealthyThresholdCount,
                                Matcher={
                                    'HttpCode': MatcherHttpCode
                                },
                                TargetType='lambda'
                            )

                else : 
                    responseData = client.modify_target_group(
                        TargetGroupArn=event['PhysicalResourceId'],
                        HealthCheckEnabled = healthcheck, 
                        HealthCheckPath = HealthCheckPath,
                        HealthCheckIntervalSeconds = HealthCheckIntervalSeconds,
                        HealthCheckTimeoutSeconds = HealthCheckTimeoutSeconds,
                        HealthyThresholdCount = HealthyThresholdCount,
                        UnhealthyThresholdCount = UnhealthyThresholdCount,
                        Matcher={
                            'HttpCode': MatcherHttpCode
                        }
                    )
                
                try:
                    tgarn = responseData['TargetGroups'][0]['TargetGroupArn']

                    #addPolicy for TG to invoke Lambda
                    try :
                        addPolicyResponse = boto3.client('lambda').add_permission(
                            FunctionName=str(event['ResourceProperties']['TargetLambdaArn']).split(':')[6],
                            StatementId= ('AWS-ALB_Invoke-' + tgarn.split('/')[1] + '-' + tgarn.split('/')[2]),
                            Action='lambda:InvokeFunction',
                            Principal="elasticloadbalancing.amazonaws.com",
                            SourceArn=tgarn,
                        )
                        print('Policy Addition Response : \n' + str(addPolicyResponse))
                    except Exception as e:
                        if ('ResourceConflictException' not in str(e)):
                            raise RuntimeError('Error registering target : ' + str(e))
                        else:
                            pass
                    
                    #De-register old targets first. Since, there can be one Lambda type target per TG.
                    if event['ResourceProperties']['TargetLambdaArn'] != event['OldResourceProperties']['TargetLambdaArn'] :
                        targetDeregisterResponse = client.deregister_targets(
                            TargetGroupArn = responseData['TargetGroups'][0]['TargetGroupArn'],
                            Targets=[
                                {
                                    'Id':event['OldResourceProperties']['TargetLambdaArn']
                                },
                            ]
                        )
                        print ('De-register Lambda taret from Target Group : \n' + str(targetDeregisterResponse))

                    #Register Lambda in TG
                    targetRegisterResponse = client.register_targets(
                        TargetGroupArn = responseData['TargetGroups'][0]['TargetGroupArn'],
                        Targets=[
                            {
                                'Id': event['ResourceProperties']['TargetLambdaArn']
                            }
                        ]
                    )
                    print ('Register Lambda tarets to Target Group : \n' + str(targetRegisterResponse))
                        
                except Exception as e :
                    print ('Error registering target : ' + str(e))
                    raise RuntimeError('Error registering target : ' + str(e))

                print("Response:" + str(responseData))
                physical_id = responseData['TargetGroups'][0]['TargetGroupArn']
            responseStatus = 'SUCCESS'
            break
        except Exception as e:
            print('Error : ' + str(e))
            responseStatus = 'FAILED'
            responseData = {'Failure': str(e)}
            attempts += 1
            time.sleep(3)
            if(attempts == 3):
                print('Create failed. Sending response...')
                sendResponse(event, context, responseStatus, responseData, reason=str(e), physical_resource_id=physical_id)
                return
    print('Sending response...')
    if existencecheck == 1 : 
        sendResponse(event, context, responseStatus, responseData, reason='Resource already exists.', physical_resource_id=physical_id)
    else :
        sendResponse(event, context, responseStatus, responseData, physical_resource_id=physical_id)
    
def sendResponse(event, context, responseStatus, responseData, reason='', physical_resource_id=None):
    try:
        responseBody = {'Status': responseStatus,
                        'Reason': reason + '   | See the details in CloudWatch Log Stream: ' + context.log_stream_name,
                        'PhysicalResourceId': physical_resource_id,
                        'StackId': event['StackId'],
                        'RequestId': event['RequestId'],
                        'LogicalResourceId': event['LogicalResourceId'],
                        'Data': responseData}
        print ('RESPONSE BODY: ' + json.dumps(responseBody))
        responseUrl = event['ResponseURL']
        json_responseBody = json.dumps(responseBody)
        headers = {
            'content-type' : '',
            'content-length' : str(len(json_responseBody))
        }
    except Exception as e:
        print('Error : ' + str(e))
    try:
        response = requests.put(responseUrl,
                                data=json_responseBody,
                                headers=headers)
        print ("Status code: " + response.reason)
    except Exception as e:
        print ("send(..) failed executing requests.put(..): " + str(e))

