from dku_azure.utils import get_instance_metadata, get_vm_resource_id, get_host_network, get_subnet_id
from azure.mgmt.containerservice.models import ManagedClusterAgentPoolProfile
from azure.mgmt.containerservice.models import ContainerServiceNetworkProfile, ContainerServiceServicePrincipalProfile, ManagedCluster
from dku_utils.access import _default_if_blank

import logging


class ClusterBuilder(object):
    """
    """
    
    def __init__(self, clusters_client):
        self.clusters_client = clusters_client
        self.name = None
        self.dns_prefix = None
        self.resource_group = None
        self.location = None
        self.linux_profile = None
        self.network_profile = None
        self.cluster_sp = None
        self.node_pools = []
        self.cluster_version = None


    def with_name(self, name):
        self.name = name
        return self

    def with_dns_prefix(self, dns_prefix):
        self.dns_prefix = dns_prefix
        return self

    def with_resource_group(self, resource_group):
        self.resource_group = _default_if_blank(resource_group, None)
        return self

    def with_location(self, location):
        self.location = _default_if_blank(location, None)
        return self

    def with_linux_profile(self, linux_profile=None):
        self.linux_profile = linux_profile
        return self

    def with_network_profile(self, service_cidr, dns_service_ip, load_balancer_sku):
        self.network_profile = ContainerServiceNetworkProfile(service_cidr=service_cidr, dns_service_ip=dns_service_ip, load_balancer_sku=load_balancer_sku)
        return self

    def with_cluster_sp(self, cluster_service_principal_connection_info):
        client_id = cluster_service_principal_connection_info["clientId"]
        client_secret = cluster_service_principal_connection_info["password"]
        service_principal_profile = ContainerServiceServicePrincipalProfile(client_id=client_id,
                                                                            secret=client_secret,
                                                                            key_vault_secret_ref=None)
        self.cluster_sp = service_principal_profile
        return self

    def get_node_pool_builder(self):
        nb_node_pools = len(self.node_pools)
        return NodePoolBuilder(self).with_name("node-pool-{}".format(nb_node_pools))
    
        
    def with_cluster_version(self, cluster_version):
        if cluster_version != "latest":
            self.cluster_version = cluster_version
        return self

    def with_node_pool(self, node_pool):
        self.node_pools.append(node_pool)
        return self

    def build(self):
        cluster_params = {}
        cluster_params["location"] = self.location
        cluster_params["dns_prefix"] = self.dns_prefix
        cluster_params["linux_profile"] = self.linux_profile
        cluster_params["network_profile"] = self.network_profile
        cluster_params["service_principal_profile"] = self.cluster_sp
        cluster_params["kubernetes_version"] = self.cluster_version
        cluster_params["agent_pool_profiles"] = self.node_pools

        self.cluster_config = ManagedCluster(**cluster_params)
        return self.clusters_client.managed_clusters.create_or_update(self.resource_group, self.name, self.cluster_config)


class NodePoolBuilder(object):
    """
    """

    def __init__(self, cluster_builder):
        self.cluster_builder = cluster_builder
        self.name = None
        self.vm_size = None
        self.vnet = None
        self.subnet_id = None # Full resource id (!)
        self.enable_autoscaling = None
        self.num_nodes = None
        self.min_num_nodes = None
        self.max_num_nodes = None
        self.disk_size_gb = None
        self.agent_pool_type = None
        self.idx = None
        self.agent_pool_profile = None
        self.gpu = None


    def with_name(self, name):
        self.name = name
        return self

    def with_idx(self, idx):
        self.idx = idx
        return self
    
    def with_vm_size(self, vm_size):
        self.vm_size = vm_size
        return self

    def with_gpu(self, vm_size):
        if "Standard_N" in vm_size:
            self.gpu = True
        else:
            self.gpu = False
        return self

    def with_network(self, inherit_from_host, cluster_vnet, cluster_subnet, connection_info, credentials, resource_group):
        if inherit_from_host:
            logging.info("Inheriting VNET/subnet from DSS host")
            self.vnet, self.subnet_id = get_host_network(credentials=credentials,
                                                         resource_group=resource_group,
                                                         connection_info=connection_info)
        else:
            logging.info("Using custom VNET ({}) and subnet ({}) for cluster".format(cluster_vnet, cluster_subnet))
            self.vnet = cluster_vnet
            self.subnet_id = get_subnet_id(resource_group=resource_group, connection_info=connection_info, vnet=cluster_vnet, subnet=cluster_subnet)
        return self

    def with_node_count(self, enable_autoscaling, num_nodes, min_num_nodes, max_num_nodes):
        logging.info("Setting node count autoscale=%s num=%s min=%s max=%s" % (enable_autoscaling, num_nodes, min_num_nodes, max_num_nodes))
        self.enable_autoscaling = enable_autoscaling
        if enable_autoscaling:
            self.agent_pool_type = "VirtualMachineScaleSets"
            self.min_num_nodes = min_num_nodes
            self.max_num_nodes = max_num_nodes
            self.num_nodes = min_num_nodes
        else:
            self.num_nodes = num_nodes
        return self

    def with_disk_size_gb(self, disk_size_gb):
        if disk_size_gb == 0:
            self.disk_size_gb = None
        else:
            self.disk_size_gb = disk_size_gb
        return self

    def build(self):
        agent_pool_profile_params = {}
        if self.idx == 0:
            agent_pool_profile_params["mode"] = "System"
        agent_pool_profile_params["name"] = "nodepool{}".format(self.idx)
        agent_pool_profile_params["type"] = self.agent_pool_type
        agent_pool_profile_params["vm_size"] = self.vm_size
        agent_pool_profile_params["count"] = self.num_nodes
        agent_pool_profile_params["os_disk_size_gb"] = self.disk_size_gb
        agent_pool_profile_params["vnet_subnet_id"] = self.subnet_id
        agent_pool_profile_params["enable_auto_scaling"] = self.enable_autoscaling
        if self.min_num_nodes:
            agent_pool_profile_params["min_count"] = self.min_num_nodes
        if self.max_num_nodes:
            agent_pool_profile_params["max_count"] = self.max_num_nodes

        logging.info("Adding agent pool profile: %s" % agent_pool_profile_params)

        self.agent_pool_profile = ManagedClusterAgentPoolProfile(**agent_pool_profile_params)
        return self


