import os, json, logging, yaml
from dataiku.cluster import Cluster

from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.containerservice.models import ManagedCluster, ManagedClusterServicePrincipalProfile
from azure.mgmt.containerservice.models import ContainerServiceLinuxProfile, ContainerServiceNetworkProfile, ContainerServiceServicePrincipalProfile
from azure.mgmt.containerservice.models import ManagedClusterAgentPoolProfile
from azure.mgmt.containerservice.models import ContainerServiceVMSizeTypes

from dku_utils.access import _is_none_or_blank
from dku_utils.cluster import make_overrides
from dku_azure.auth import get_credentials_from_connection_info
from dku_azure.utils import run_and_process_cloud_error, check_resource_group_exists, grab_vm_infos

class MyCluster(Cluster):
    def __init__(self, cluster_id, cluster_name, config, plugin_config):
        self.cluster_id = cluster_id
        self.cluster_name = cluster_name
        self.config = config
        self.plugin_config = plugin_config
        
    def start(self):
        vm_infos = grab_vm_infos()
        logging.info("Current VM is in %s" % json.dumps(vm_infos))

        connection_info = self.config.get("connectionInfo", {})
        connection_info_secret = self.plugin_config.get("connectionInfo", {})
        subscription_id = connection_info.get('subscriptionId', None)
        if _is_none_or_blank(subscription_id):
            subscription_id = vm_infos.get('subscription_id', None)
        if _is_none_or_blank(subscription_id):
            raise Exception('Subscription must be defined')

        credentials = get_credentials_from_connection_info(connection_info, connection_info_secret)
        clusters_client = ContainerServiceClient(credentials, subscription_id)
        
        resource_group_name = self.config.get('resourceGroup', None)
        if _is_none_or_blank(resource_group_name):
            resource_group_name = vm_infos.get('resource_group_name', None)
        if _is_none_or_blank(resource_group_name):
            raise Exception("A resource group to put the cluster in is required")

        cluster_name = self.config.get('cluster', self.cluster_name)
        
        logging.info("Fetching kubeconfig for cluster %s in %s" % (cluster_name, resource_group_name))
        def do_fetch():
            return clusters_client.managed_clusters.list_cluster_admin_credentials(resource_group_name, cluster_name)
        try:
            get_credentials_result = run_and_process_cloud_error(do_fetch)
        except Exception as e:
            perm_error_needle = "does not have authorization to perform action 'Microsoft.ContainerService/managedClusters/listClusterAdminCredential/action'"
            if perm_error_needle in str(e):
                # check that the resource group exists, because the permission error is misleading
                logging.info("Check that the resource group %s exists... " % resource_group_name)
                if not check_resource_group_exists(resource_group_name, credentials, subscription_id):
                    raise Exception("Resource group %s doesn't exist" % resource_group_name)
            raise e

        kube_config_content = get_credentials_result.kubeconfigs[0].value.decode('utf8')
        
        kube_config_path = os.path.join(os.getcwd(), 'kube_config')
        with open(kube_config_path, 'w') as f:
            f.write(kube_config_content)

        overrides = make_overrides(self.config, yaml.safe_load(kube_config_content), kube_config_path)
        
        def do_inspect():
            return clusters_client.managed_clusters.get(resource_group_name, cluster_name)
        get_cluster_result = run_and_process_cloud_error(do_inspect)

        return [overrides, {'kube_config_path':kube_config_path, 'cluster':get_cluster_result.as_dict()}]

    def stop(self, data):
        pass

