import os, json, logging, yaml
from dataiku.cluster import Cluster

from azure.mgmt.containerservice import ContainerServiceClient
from dku_utils.access import _is_none_or_blank, _print_as_json
from dku_utils.cluster import make_overrides, get_subscription_id
from dku_azure.auth import get_credentials_from_connection_info, get_credentials_from_connection_infoV2
from dku_azure.utils import run_and_process_cloud_error, get_instance_metadata, get_subscription_id

class MyCluster(Cluster):
    def __init__(self, cluster_id, cluster_name, config, plugin_config):
        self.cluster_id = cluster_id
        self.cluster_name = cluster_name
        self.config = config
        self.plugin_config = plugin_config

    def _get_credentials(self):
        connection_info = self.config.get("connectionInfo", None)
        connection_info_secret = self.plugin_config.get("connectionInfo", None)
        if not _is_none_or_blank(connection_info) or not _is_none_or_blank(connection_info_secret):
            logging.warn("Using legacy authentication fields. Clear them to use the new ones.")
            credentials = get_credentials_from_connection_info(connection_info, connection_info_secret)
            subscription_id = connection_info.get('subscriptionId', None)
        else:
            connection_info_v2 = self.config.get("connectionInfoV2",{"identityType":"default"})
            credentials, _ = get_credentials_from_connection_infoV2(connection_info_v2)
            subscription_id = get_subscription_id(connection_info_v2)
        return credentials, subscription_id
        
    def start(self):
        credentials, subscription_id = self._get_credentials()

        # Cluster name
        cluster_name = self.config.get("cluster", None)
        if _is_none_or_blank(cluster_name):
            cluster_name = self.cluster_name
            logging.info("Using same cluster name as DSS: {}".format(cluster_name))

        # Resource group
        resource_group = self.config.get('resourceGroup', None)
        if _is_none_or_blank(resource_group):
            metadata = get_instance_metadata()
            resource_group = metadata["compute"]["resourceGroupName"]
            logging.info("Using same resource group as DSS: {}".format(resource_group))

        clusters_client = ContainerServiceClient(credentials, subscription_id)

        # Get kubeconfig 
        logging.info("Fetching kubeconfig for cluster %s in %s", cluster_name, resource_group)
        def do_fetch():
            return clusters_client.managed_clusters.list_cluster_admin_credentials(resource_group, cluster_name)
        get_credentials_result = run_and_process_cloud_error(do_fetch)
        logging.info("Kubeconfig retrieved for cluster")
        logging.info("Kubeconfig retrieved for cluster %s in %s: %s", cluster_name, resource_group, _print_as_json(get_credentials_result))
        kube_config_content = get_credentials_result.kubeconfigs[0].value.decode('utf8')
        kube_config_path = os.path.join(os.getcwd(), 'kube_config')
        with open(kube_config_path, 'w') as f:
            f.write(kube_config_content)
        overrides = make_overrides(self.config, yaml.safe_load(kube_config_content), kube_config_path)
        
        # Get other cluster infos
        logging.info("Retrieving cluster information for cluster %s in %s", cluster_name, resource_group)
        def do_inspect():
            return clusters_client.managed_clusters.get(resource_group, cluster_name)
        get_cluster_result = run_and_process_cloud_error(do_inspect)
        logging.info("Information retrieved for cluster")
        logging.info("Information retrieved for cluster %s in %s: %s", cluster_name, resource_group, _print_as_json(get_cluster_result))

        return [overrides, {'kube_config_path':kube_config_path, 'cluster':get_cluster_result.as_dict()}]

    def stop(self, data):
        pass

