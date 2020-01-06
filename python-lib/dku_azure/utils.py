import requests
import json
import logging

from msrestazure.azure_exceptions import CloudError
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient

AZURE_METADATA_SERVICE="http://169.254.169.254"

def run_and_process_cloud_error(fn):
    try:
        return fn()
    except CloudError as e:
        raise Exception('%s : %s' % (str(e), e.response.content))
    except Exception as e:
        raise e
        

def get_instance_metadata(api_version="2019-04-30"):
    """
    Return VM metadata.
    """
    metadata_svc_endpoint = "{}/metadata/instance?api-version={}".format(AZURE_METADATA_SERVICE, api_version)
    req = requests.get(metadata_svc_endpoint, headers={"metadata": "true"})
    resp = json.loads(req.text)
    return resp


def get_vm_resource_id(subscription_id=None,
                       resource_group=None,
                       vm_name=None):
    """
    Return full resource ID given a VM's name.
    """
    
    return "/subscriptions/{}/resourceGroups/{}/providers/Microsoft.Compute/virtualMachines/{}".format(subscription_id, resource_group, vm_name)


def get_subnet_id(connection_info, resource_group, vnet, subnet):
    """
    """
    logging.info("Mapping subnet {} to its full resource ID...".format(subnet))
    subscription_id = connection_info.get("subscriptionId", None)
    subnet_id = "/subscriptions/{}/resourceGroups/{}/providers/Microsoft.Network/virtualNetworks/{}/subnets/{}".format(subscription_id,
                                                                                                                       resource_group,
                                                                                                                       vnet,
                                                                                                                       subnet)
    logging.info("Subnet {} linked to the resource {}".format(subnet, subnet_id))
    return "/subscriptions/{}/resourceGroups/{}/providers/Microsoft.Network/virtualNetworks/{}/subnets/{}".format(subscription_id,
                                                                                                                  resource_group,
                                                                                                                  vnet,
                                                                                                                  subnet)


def get_host_network(credentials=None, resource_group=None, connection_info=None, api_version="2019-07-01"):
    """
    Return the VNET and subnet id of the DSS host.
    """
    
    logging.info("Getting instance metadata...")
    vm_name = get_instance_metadata()["compute"]["name"]
    logging.info("DSS host is on VNET {}".format(vm_name))
    subscription_id = connection_info.get("subscriptionId", None)
    vm_resource_id = get_vm_resource_id(subscription_id, resource_group, vm_name)
    resource_mgmt_client = ResourceManagementClient(credentials=credentials, subscription_id=subscription_id, api_version=api_version)
    vm_properties = resource_mgmt_client.resources.get_by_id(vm_resource_id, api_version=api_version).properties
    vm_network_interfaces = vm_properties["networkProfile"]["networkInterfaces"]
    if len(vm_network_interfaces) > 1:
        print("WARNING: more than 1 network interface detected, will use 1st one on list to retrieve IP configuration info")
    network_interface_id = vm_network_interfaces[0]["id"]
    network_interface_properties = resource_mgmt_client.resources.get_by_id(network_interface_id, api_version=api_version).properties
    ip_configs = network_interface_properties["ipConfigurations"]
    if len(ip_configs) > 1:
        print("WARNING: more than 1 IP config detected for this interface, will use 1st one on the list to retrieve VNET/subnet info")
    subnet_id = ip_configs[0]["properties"]["subnet"]["id"]
    vnet = subnet_id.split("virtualNetworks")[1].split('/')[1]
    logging.info("VNET: {}".format(vnet))
    logging.info("SUBNET ID: {}".format(subnet_id))
    return vnet, subnet_id
        

    

