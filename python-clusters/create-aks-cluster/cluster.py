import os, json, logging, yaml, time
from dataiku.cluster import Cluster

from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.containerservice.models import ManagedCluster, ManagedClusterServicePrincipalProfile
from azure.mgmt.containerservice.models import ContainerServiceLinuxProfile, ContainerServiceNetworkProfile, ContainerServiceServicePrincipalProfile
from azure.mgmt.containerservice.models import ManagedClusterAgentPoolProfile
from azure.mgmt.containerservice.models import ContainerServiceVMSizeTypes
from msrestazure.azure_exceptions import CloudError

from dku_utils.access import _is_none_or_blank
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
        clusters_client.config.add_user_agent('pid-fd3813c7-273c-5eec-9221-77323f62a148')
        
        resource_group_name = self.config.get('resourceGroup', None)
        #if _is_none_or_blank(resource_group_name):
        #    resource_group_name = vm_infos.get('resource_group_name', None)
        if _is_none_or_blank(resource_group_name):
            raise Exception("A resource group to put the cluster in is required")
        
        location = self.config.get('location', None)
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
        
        #linux_profile = None # ContainerServiceLinuxProfile()
        #network_profile = ContainerServiceNetworkProfile(service_cidr=self.config.get("serviceCIDR", '10.10.10.0/24'), dns_service_ip=self.config.get('dnsServiceIP', '10.10.10.10'))

#        cluster_service_principal = self.config.get("clusterServicePrincipal", connection_info)
#        cluster_service_principal_secret = self.plugin_config.get("clusterServicePrincipal", connection_info_secret)
#        if not 'clientId' in cluster_service_principal:
#            cluster_service_principal = connection_info
#            cluster_service_principal_secret = connection_info_secret
#        service_principal_profile = ContainerServiceServicePrincipalProfile(client_id=cluster_service_principal["clientId"], secret=cluster_service_principal["password"], key_vault_secret_ref=None)
        
#         agent_pool_profiles = []
#         for conf in self.config.get('nodePools', []):
#             idx = len(agent_pool_profiles)
#             vm_size = conf.get('vmSize', None)
            
#             subnet = conf.get('subnet', None)
#             vnet = conf.get('vnet', None)
#             vnet_subnet_id = None
#             if not _is_none_or_blank(subnet):
#                 if subnet.startswith('/subscriptions'):
#                     vnet_subnet_id = subnet
#                 else:
#                     vnet_subnet_id = "/subscriptions/%s/resourceGroups/%s/providers/Microsoft.Network/virtualNetworks/%s/subnets/%s" % (subscription_id, resource_group_name, vnet, subnet)
#             num_nodes = conf.get('numNodes', 3)
#             auto_scaling = conf.get('autoScaling', False)
#             min_num_nodes = conf.get('minNumNodes', num_nodes) if auto_scaling else None 
#             max_num_nodes = conf.get('maxNumNodes', num_nodes) if auto_scaling else None
            
#             os_disk_size_gb = conf.get('osDiskSizeGb', 0)
#             if _is_none_or_blank(vm_size):
#                 raise Exception("Node pool %s has no vm size" % idx)
#             if os_disk_size_gb == 0:
#                 os_disk_size_gb = None
                
#             agent_pool_type = "VirtualMachineScaleSets" if auto_scaling else None
#             agent_pool_profile = ManagedClusterAgentPoolProfile(name="nodepool%s" % idx, type=agent_pool_type, vm_size=vm_size, count=num_nodes, os_disk_size_gb=os_disk_size_gb, vnet_subnet_id=vnet_subnet_id, enable_auto_scaling=auto_scaling, min_count=min_num_nodes, max_count=max_num_nodes)
#             agent_pool_profiles.append(agent_pool_profile)
            
#         kubernetes_version = self.config.get('kubernetesVersion', None)
#         if _is_none_or_blank(kubernetes_version):
#             kubernetes_version = None # don't pass empty strings
            
#         cluster_config = ManagedCluster(location=location
#                                         , dns_prefix='%s-dns' % self.cluster_name
#                                         , kubernetes_version=kubernetes_version
#                                         , linux_profile=linux_profile
#                                         , network_profile=network_profile
#                                         , service_principal_profile=service_principal_profile
#                                         , agent_pool_profiles=agent_pool_profiles)
#         logging.info("Creating cluster %s in %s" % (self.cluster_name, resource_group_name))
# =======

        cluster_builder = ClusterBuilder(clusters_client)
        cluster_builder.with_name(self.cluster_name)
        cluster_builder.with_dns_prefix("{}-dns".format(self.cluster_name))
        cluster_builder.with_resource_group(resource_group)
        cluster_builder.with_location(self.config.get("location", None))
        cluster_builder.with_linux_profile() # default is None
        cluster_builder.with_network_profile(service_cidr=self.config.get("serviceCIDR", None),
                                             dns_service_ip=self.config.get("dnsServiceIP", None))
        cluster_builder.with_cluster_sp(cluster_service_principal=self.config.get("clusterServicePrincipal",
                                                                                  connection_info),
                                        cluster_service_principal_secret=self.plugin_config.get("clusterServicePrincipalSecret",
                                                                                                 connection_info_secret))
        cluster_builder.with_cluster_version(self.config.get("clusterVersion", None))
        
        for idx, node_pool_conf in enumerate(self.config.get("nodePools", [])):
            node_pool_builder = cluster_builder.get_node_pool_builder()
            node_pool_builder.with_idx(idx)
            node_pool_builder.with_vm_size(node_pool_conf.get("vmSize", None))
            vnet = node_pool_conf.get("vnet", None)
            subnet = node_pool_conf.get("subnet", None)
            subnet_id = get_subnet_id(connection_info=connection_info,
                                      resource_group=resource_group,
                                      vnet=vnet,
                                      subnet=subnet)
            node_pool_builder.with_network(inherit_from_host=node_pool_conf.get("useSameNetworkAsDSSHost"),
                                           cluster_vnet=vnet,
                                           cluster_subnet_id=subnet_id,
                                           connection_info=connection_info,
                                           credentials=credentials,
                                           resource_group=resource_group)

            num_nodes = node_pool_conf.get("numNodes", None)
            auto_scaling = node_pool_conf.get("autoScaling", False),
            node_pool_builder.with_node_count(enable_autoscaling=auto_scaling,
                                              num_nodes=num_nodes,
                                              min_num_nodes=node_pool_conf.get("minNumNodes", num_nodes) if auto_scaling else None,
                                              max_num_nodes=node_pool_conf.get("maxNumNodes", num_nodes) if auto_scaling else None)

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
        