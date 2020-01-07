import os, json, logging, yaml, time
from dataiku.cluster import Cluster

from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.containerservice.models import ManagedCluster, ManagedClusterServicePrincipalProfile
from azure.mgmt.containerservice.models import ContainerServiceLinuxProfile, ContainerServiceNetworkProfile, ContainerServiceServicePrincipalProfile
from azure.mgmt.containerservice.models import ManagedClusterAgentPoolProfile
from azure.mgmt.containerservice.models import ContainerServiceVMSizeTypes
from msrestazure.azure_exceptions import CloudError

from dku_utils.access import _is_none_or_blank, _has_not_blank_property
from dku_utils.cluster import make_overrides, get_cluster_from_connection_info
from dku_azure.auth import get_credentials_from_connection_info
from dku_azure.clusters import ClusterBuilder
from dku_azure.utils import run_and_process_cloud_error, get_subnet_id

class MyCluster(Cluster):
    def __init__(self, cluster_id, cluster_name, config, plugin_config):
        self.cluster_id = cluster_id
        self.cluster_name = cluster_name
        self.config = config
        self.plugin_config = plugin_config

    def start(self):
        """
        Build the create cluster request.
        """

        connection_info = self.config.get("connectionInfo", {})
        connection_info_secret = self.plugin_config.get("connectionInfo", {})
        credentials = get_credentials_from_connection_info(connection_info, connection_info_secret)
        subscription_id = connection_info.get('subscriptionId', None)
        resource_group = self.config.get('resourceGroup', None)

        clusters_client = ContainerServiceClient(credentials, subscription_id)
        
        # Credit the cluster to DATAIKU
        if os.environ.get("DISABLE_AZURE_USAGE_ATTRIBUTION", "0") == "1":
            logging.info("Azure usage attribution is disabled")
        else:
            clusters_client.config.add_user_agent('pid-fd3813c7-273c-5eec-9221-77323f62a148')
        
        resource_group_name = self.config.get('resourceGroup', None)
        # TODO: Auto detection
        #if _is_none_or_blank(resource_group_name):
        #    resource_group_name = vm_infos.get('resource_group_name', None)
        if _is_none_or_blank(resource_group_name):
            raise Exception("A resource group to put the cluster in is required")
        
        location = self.config.get('location', None)
        # TODO: Auto detection
        #if _is_none_or_blank(location):
        #    location = vm_infos.get('location', None)
        if _is_none_or_blank(location):
            raise Exception("A location to put the cluster in is required")
            
        # check that the cluster doesn't exist yet, otherwise azure will try to update it
        # and will almost always fail
        try:
            existing = clusters_client.managed_clusters.get(resource_group_name, self.cluster_name)
            if existing is not None:
                raise Exception("A cluster with name %s in resource group %s already exists" % (self.cluster_name, resource_group_name))
        except CloudError as e:
            logging.info("Cluster doesn't seem to exist yet")

        cluster_builder = ClusterBuilder(clusters_client)
        cluster_builder.with_name(self.cluster_name)
        cluster_builder.with_dns_prefix("{}-dns".format(self.cluster_name))
        cluster_builder.with_resource_group(resource_group)
        cluster_builder.with_location(self.config.get("location", None))
        cluster_builder.with_linux_profile() # default is None
        cluster_builder.with_network_profile(service_cidr=self.config.get("serviceCIDR", None),
                                             dns_service_ip=self.config.get("dnsServiceIP", None),
                                             load_balancer_sku=self.config.get("loadBalancerSku", None))

        if self.config.get("useDistinctSPForCluster", False):
            cluster_sp = self.config.get("clusterServicePrincipal")
        else:
            cluster_sp = connection_info
        cluster_builder.with_cluster_sp(cluster_service_principal_connection_info=cluster_sp)

        cluster_builder.with_cluster_version(self.config.get("clusterVersion", None))
        
        for idx, node_pool_conf in enumerate(self.config.get("nodePools", [])):
            node_pool_builder = cluster_builder.get_node_pool_builder()
            node_pool_builder.with_idx(idx)
            node_pool_builder.with_vm_size(node_pool_conf.get("vmSize", None))
            vnet = node_pool_conf.get("vnet", None)
            subnet = node_pool_conf.get("subnet", None)
            node_pool_builder.with_network(inherit_from_host=node_pool_conf.get("useSameNetworkAsDSSHost"),
                                           cluster_vnet=vnet,
                                           cluster_subnet=subnet,
                                           connection_info=connection_info,
                                           credentials=credentials,
                                           resource_group=resource_group)

            node_pool_builder.with_node_count(enable_autoscaling=node_pool_conf.get("autoScaling", False),
                                              num_nodes=node_pool_conf.get("numNodes", None),
                                              min_num_nodes=node_pool_conf.get("minNumNodes", None),
                                              max_num_nodes=node_pool_conf.get("maxNumNodes", None))

            node_pool_builder.with_disk_size_gb(disk_size_gb=node_pool_conf.get("osDiskSizeGb", 0))
            node_pool_builder.build()
            cluster_builder.with_node_pool(node_pool=node_pool_builder.agent_pool_profile)
        

        def do_creation():
            cluster_create_op = cluster_builder.build()
            return cluster_create_op.result()
        create_result = run_and_process_cloud_error(do_creation)

        logging.info("Fetching kubeconfig for cluster {} in {}...".format(self.cluster_name, resource_group))
        def do_fetch():
            return clusters_client.managed_clusters.list_cluster_admin_credentials(resource_group, self.cluster_name)
        get_credentials_result = run_and_process_cloud_error(do_fetch)
        kube_config_content = get_credentials_result.kubeconfigs[0].value.decode("utf8")
        logging.info("Writing kubeconfig file...")
        kube_config_path = os.path.join(os.getcwd(), "kube_config")
        with open(kube_config_path, 'w') as f:
            f.write(kube_config_content)
        
        overrides = make_overrides(self.config, yaml.safe_load(kube_config_content), kube_config_path)

        return [overrides, {"kube_config_path": kube_config_path, "cluster": create_result.as_dict()}]


    def stop(self, data):
        connection_info = self.config.get("connectionInfo", {})
        connection_info_secret = self.plugin_config.get("connectionInfo", {})
        subscription_id = connection_info.get('subscriptionId', None)
        if _is_none_or_blank(subscription_id):
            raise Exception('Subscription must be defined')

        credentials = get_credentials_from_connection_info(connection_info, connection_info_secret)
        clusters_client = ContainerServiceClient(credentials, subscription_id)
        
        resource_group_name = self.config.get('resourceGroup', None)
        if _is_none_or_blank(resource_group_name):
            raise Exception("A resource group to put the cluster in is required")

        logging.info("Fetching kubeconfig for cluster %s in %s" % (self.cluster_name, resource_group_name))
        def do_delete():
            return clusters_client.managed_clusters.delete(resource_group_name, self.cluster_name)
        delete_result = run_and_process_cloud_error(do_delete)
        
        # delete returns void, so we poll until the cluster is really gone
        gone = False
        while not gone:
            time.sleep(5)
            try:
                cluster = clusters_client.managed_clusters.get(resource_group_name, self.cluster_name)
                if cluster.provisioning_state.lower() != 'deleting':
                    logging.info("Cluster is not deleting anymore, must be deleted now (state = %s)" % cluster.provisioning_state)
            except Exception as e:
                logging.info("Could not get cluster, should be gone (%s)" % str(e))
                gone = True
        
