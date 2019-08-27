import os, json, logging, yaml, time
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
        
        # credit this cluster to Dataiku
        clusters_client.config.add_user_agent('pid-fd3813c7-273c-5eec-9221-77323f62a148')
        
        resource_group_name = self.config.get('resourceGroup', None)
        if _is_none_or_blank(resource_group_name):
            resource_group_name = vm_infos.get('resource_group_name', None)
        if _is_none_or_blank(resource_group_name):
            raise Exception("A resource group to put the cluster in is required")
        location = self.config.get('location', None)
        if _is_none_or_blank(location):
            location = vm_infos.get('location', None)
        if _is_none_or_blank(location):
            raise Exception("A location to put the cluster in is required")
            
        linux_profile = None # ContainerServiceLinuxProfile()
        network_profile = ContainerServiceNetworkProfile(service_cidr=self.config.get("serviceCIDR", '10.10.10.0/24'), dns_service_ip=self.config.get('dnsServiceIP', '10.10.10.10'))

        cluster_service_principal = self.config.get("clusterServicePrincipal", connection_info)
        cluster_service_principal_secret = self.plugin_config.get("clusterServicePrincipal", connection_info_secret)
        if not 'clientId' in cluster_service_principal:
            cluster_service_principal = connection_info
            cluster_service_principal_secret = connection_info_secret
        service_principal_profile = ContainerServiceServicePrincipalProfile(client_id=cluster_service_principal["clientId"], secret=cluster_service_principal_secret["password"], key_vault_secret_ref=None)
        
        agent_pool_profiles = []
        for conf in self.config.get('nodePools', []):
            idx = len(agent_pool_profiles)
            vm_size = conf.get('vmSize', None)
            
            subnet = conf.get('subnet', None)
            vnet = conf.get('vnet', None)
            vnet_subnet_id = None
            if not _is_none_or_blank(subnet):
                if subnet.startswith('/subscriptions'):
                    vnet_subnet_id = subnet
                else:
                    vnet_subnet_id = "/subscriptions/%s/resourceGroups/%s/providers/Microsoft.Network/virtualNetworks/%s/subnets/%s" % (subscription_id, resource_group_name, vnet, subnet)
            num_nodes = conf.get('numNodes', 3)
            auto_scaling = conf.get('autoScaling', False)
            min_num_nodes = conf.get('minNumNodes', num_nodes)
            max_num_nodes = conf.get('maxNumNodes', num_nodes)
            
            os_disk_size_gb = conf.get('osDiskSizeGb', 0)
            if _is_none_or_blank(vm_size):
                raise Exception("Node pool %s has no vm size" % idx)
            if os_disk_size_gb == 0:
                os_disk_size_gb = None
                
            agent_pool_type = "VirtualMachineScaleSets" if auto_scaling else None
            agent_pool_profile = ManagedClusterAgentPoolProfile(name="nodepool%s" % idx, type=agent_pool_type, vm_size=vm_size, count=num_nodes, os_disk_size_gb=os_disk_size_gb, vnet_subnet_id=vnet_subnet_id, enable_auto_scaling=auto_scaling, min_count=min_num_nodes, max_count=max_num_nodes)
            agent_pool_profiles.append(agent_pool_profile)
            
        cluster_config = ManagedCluster(location=location
                                        , dns_prefix='%s-dns' % self.cluster_name
                                        , linux_profile=linux_profile
                                        , network_profile=network_profile
                                        , service_principal_profile=service_principal_profile
                                        , agent_pool_profiles=agent_pool_profiles)
        logging.info("Creating cluster %s in %s" % (self.cluster_name, resource_group_name))
        def do_creation():
            cluster_create_op = clusters_client.managed_clusters.create_or_update(resource_group_name, self.cluster_name, cluster_config)
            return cluster_create_op.result()
        try:
            create_result = run_and_process_cloud_error(do_creation)
        except Exception as e:
            perm_error_needle = "does not have authorization to perform action 'Microsoft.ContainerService/managedClusters/write'"
            if perm_error_needle in str(e):
                # check that the resource group exists, because the permission error is misleading
                logging.info("Check that the resource group %s exists... " % resource_group_name)
                if not check_resource_group_exists(resource_group_name, credentials, subscription_id):
                    raise Exception("Resource group %s doesn't exist" % resource_group_name)
            raise e
            
        logging.info("Fetching kubeconfig for cluster %s in %s" % (self.cluster_name, resource_group_name))
        def do_fetch():
            return clusters_client.managed_clusters.list_cluster_admin_credentials(resource_group_name, self.cluster_name)
        get_credentials_result = run_and_process_cloud_error(do_fetch)
        
        kube_config_content = get_credentials_result.kubeconfigs[0].value.decode('utf8')
        
        kube_config_path = os.path.join(os.getcwd(), 'kube_config')
        with open(kube_config_path, 'w') as f:
            f.write(kube_config_content)

        overrides = make_overrides(self.config, yaml.safe_load(kube_config_content), kube_config_path)
        
        return [overrides, {'kube_config_path':kube_config_path, 'cluster':create_result.as_dict()}]

    def stop(self, data):
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
        