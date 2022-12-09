import requests
import yaml
import logging

from msrestazure.azure_exceptions import CloudError
from azure.mgmt.resource import ResourceManagementClient
from dku_utils.access import _is_none_or_blank

AZURE_METADATA_SERVICE="http://169.254.169.254"
INSTANCE_API_VERSION = "2019-04-30"

def run_and_process_cloud_error(fn):
    try:
        return fn()
    except CloudError as e:
        raise Exception('%s : %s' % (str(e), e.response.content))
    except Exception as e:
        raise e
        

def get_instance_metadata(api_version=INSTANCE_API_VERSION):
    """
    Return VM metadata.
    """
    metadata_svc_endpoint = "{}/metadata/instance?api-version={}".format(AZURE_METADATA_SERVICE, api_version)
    req = requests.get(metadata_svc_endpoint, headers={"metadata": "true"}, proxies={"http":None, "http":None})
    resp = req.json()
    return resp

def get_subscription_id(connection_info):
    identity_type = connection_info.get('identityType', None)
    subscription_id = connection_info.get('subscriptionId', None)
    if (identity_type == 'default' or identity_type == 'service-principal') and not _is_none_or_blank(subscription_id):
        return subscription_id
    else:
        return get_instance_metadata()["compute"]["subscriptionId"]

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

    if vnet.startswith("/subscriptions/"):
        logging.info("Vnet is specified by its full resource ID: {}".format(vnet))
        subnet_id = "{}/subnets/{}".format(vnet, subnet)
    else:
        logging.info("Vnet is specified by its name: {}".format(vnet))
        subscription_id = get_subscription_id(connection_info)
        subnet_id = "/subscriptions/{}/resourceGroups/{}/providers/Microsoft.Network/virtualNetworks/{}/subnets/{}".format(subscription_id,
                                                                                                                           resource_group,
                                                                                                                           vnet,
                                                                                                                           subnet)
    logging.info("Subnet {} linked to the resource {}".format(subnet, subnet_id))
    return subnet_id


def get_host_network(credentials=None, resource_group=None, connection_info=None, api_version="2019-07-01"):
    """
    Return the VNET and subnet id of the DSS host.
    """
    
    logging.info("Getting instance metadata...")
    vm_name = get_instance_metadata()["compute"]["name"]
    logging.info("DSS host is on VNET {}".format(vm_name))
    subscription_id = get_subscription_id(connection_info)
    vm_resource_id = get_vm_resource_id(subscription_id, resource_group, vm_name)
    resource_mgmt_client = ResourceManagementClient(credential=credentials, subscription_id=subscription_id, api_version=api_version)
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

def patch_kube_config_with_aad(kube_config_string, authentication_mode, identity_label):
    kube_config = yaml.safe_load(kube_config_string)

    kubelogin_command_options = ['get-token', '--login', 'msi', '--server-id', '6dae42f8-4368-4678-94ff-3960e28e3630']

    additional_options = []
    if authentication_mode == 'service-principal':
        additional_options = ['--identity-resource-id', identity_label]
    elif authentication_mode == 'user-assigned':
        if identity_label.startswith("/"):
            additional_options = ['--identity-resource-id', identity_label]
        else:
            additional_options = ['--client-id', identity_label]
    
    kubelogin_command_options = kubelogin_command_options + additional_options

    kube_config_user = {
        'name': kube_config['contexts'][0]['context']['user'],
        'user': {
            'exec': {
                'apiVersion': 'client.authentication.k8s.io/v1beta1',
                'command': 'kubelogin',
                'args': kubelogin_command_options
            }
        }
    }
    
    kube_config['users'] = [kube_config_user]

    return kube_config

    # determine which is the authentication mode
    # depending on the authentication mode, the derivation command kubelogin options will be different
    # 
    # SERVICE-PRINCIPAL
    # kubelogin get-token -l msi --server-id 6dae42f8-4368-4678-94ff-3960e28e3630 --identity-resource-id /subscriptions/8c59bf15-b4a9-4398-a354-d2a4e7d60e2a/resourcegroups/jcasoli-fm/providers/Microsoft.ManagedIdentity/userAssignedIdentities/dss-id-jcasoli
    # USER-ASSIGNED
    # kubelogin get-token -l msi --server-id 6dae42f8-4368-4678-94ff-3960e28e3630 --client-id de4cab2c-359c-4970-8032-89bee12a7d31
    # DEFAULT
    # kubelogin get-token -l msi --server-id 6dae42f8-4368-4678-94ff-3960e28e3630

