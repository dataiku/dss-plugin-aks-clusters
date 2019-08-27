from msrestazure.azure_exceptions import CloudError
from azure.mgmt.resource import ResourceManagementClient
import logging
import requests
import json

def run_and_process_cloud_error(fn):
    try:
        return fn()
    except CloudError as e:
        raise Exception('%s : %s' % (str(e), e.response.content))
    except Exception as e:
        raise e
        
def check_resource_group_exists(resource_group, credentials, subscription_id):
    client = ResourceManagementClient(credentials = credentials, subscription_id = subscription_id)
    try:
        for g in client.resource_groups.list():
            if g.name == resource_group:
                return True
        return False
    except:
        logging.warning("Unable to check resource group existence")
        return True # non conclusive, can't say for sure it doesn't exist
    
def grab_vm_infos():
    try:
        r = requests.get('http://169.254.169.254/metadata/instance/compute?api-version=2017-08-01', headers={'Metadata': 'true'})
        data = json.loads(r.text)
        return {'location':data.get('location', None), 'resource_group_name':data.get('resourceGroupName', None), 'subscription_id':data.get('subscriptionId', None)}
    except:
        logging.warning("Unable to get location and resource group from current VM (maybe not running in Azure)")
        return {}