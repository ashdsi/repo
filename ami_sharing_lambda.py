import boto3
import time

accountID = ('359763635961','891414916041')
region_list = ['eu-central-1','ap-southeast-2']
AMI_list = []

def lambda_handler(event, context):
    print("Giving the AMI 60 seconds to be finished")
    print("Copying new AMI " + event['ami'] +  " to ", *region_list)
    Copy_AMI(event['ami'])
    time.sleep(120)
    print("Sharing the AMI in respective regions")
    Share_AMI(AMI_list)
    
    ###It gets all region names - we need only 2 now - set below manually###
    ##If you want to copy to all, comment region_list above and uncomment this part
    #Get list of regions and endpoints
    #regions = client.describe_regions()
    #extract region list from response
    # region_count = range(len(regions['Regions']))
    # x = 0
    # for x in region_count:
    #     region_list.append(regions['Regions'][x]['RegionName'])
    #     x = x+1
    
def Copy_AMI(AMI_ID):
    y = 0
    for region in region_list:
        client = boto3.client('ec2',region_name=region_list[y])
        copiedAMIID = client.copy_image(
            Name='CopiedAMIfrom ' + AMI_ID,
            SourceImageId=AMI_ID,
            SourceRegion='eu-west-1'
        )
        print("Copied AMI " + AMI_ID + " in " + region_list[y])
        y = y+1
        AMI_list.append(copiedAMIID['ImageId'])
        
    return AMI_list
        
def Share_AMI(AMI_list):
    print("Waiting 30 seconds for the AMI to be copied")
    time.sleep(30)
    for (region, AMI) in zip(region_list, AMI_list):
        while True:
            try:
                client = boto3.client('ec2',region_name=region)
                response_shareimage = client.modify_image_attribute(
                    Attribute = 'launchPermission',
                    ImageId = AMI,
                    LaunchPermission = {
                        'Add' : [{ 'UserId': accountID[0] }, { 'UserId': accountID[1] }]
                    }
                )
                print ("Image "+ AMI + " shared")
                break
            except:
              print ("Image " + AMI + " in region " + region + " not ready yet")
              print("Waiting 30 seconds for next attempt")
              time.sleep(30)
              continue
    # print("Getting current launchPermissions to verify")   
    # response_launchpermissions = client.describe_image_attribute(
    #     Attribute='launchPermission',
    #     ImageId=AMI_ID
    #     )
        
    # shared_with_acc1=(response_launchpermissions['LaunchPermissions'][0].get('UserId'))
    # shared_with_acc2=(response_launchpermissions['LaunchPermissions'][1].get('UserId'))
    
    # if (shared_with_acc1 == accountID[0]) and (shared_with_acc2 == accountID[1]):
    #     print("Successfully shared")
    # else:
    #     print ("AMI not shared")
       
