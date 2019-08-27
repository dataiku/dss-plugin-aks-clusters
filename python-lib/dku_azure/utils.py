from msrestazure.azure_exceptions import CloudError
from azure.mgmt.resource import ResourceManagementClient
import logging

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
        logging.error("Unable to check resource group existence")
        return True # non conclusive, can't say for sure it doesn't exist