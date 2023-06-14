from dataiku.runnables import Runnable
import json, logging
from dku_utils.cluster import get_cluster_from_dss_cluster
from dku_utils.access import _is_none_or_blank
from dku_azure.clusters import NodePoolBuilder
from dku_azure.utils import run_and_process_cloud_error, get_instance_metadata, get_subscription_id
from dku_kube.nvidia_utils import add_gpu_driver_if_needed

class MyRunnable(Runnable):
    def __init__(self, project_key, config, plugin_config):
        self.project_key = project_key
        self.config = config
        self.plugin_config = plugin_config
        
    def get_progress_target(self):
        return None

    def run(self, progress_callback):
        cluster_data, clusters, dss_cluster_settings, dss_cluster_config, connection_info, credentials = get_cluster_from_dss_cluster(self.config['clusterId'])
        
        # Fetch metadata about the instance
        metadata = get_instance_metadata()
        dss_host_resource_group = metadata["compute"]["resourceGroupName"]

        # retrieve the actual name in the cluster's data
        if cluster_data is None:
            raise Exception("No cluster data (not started?)")
        cluster_def = cluster_data.get("cluster", None)
        if cluster_def is None:
            raise Exception("No cluster definition (starting failed?)")
        cluster_id = cluster_def["id"]
        _,_,subscription_id,_,resource_group,_,_,_,cluster_name = cluster_id.split("/") # resource_group here will be the same as in the cluster.py
        
        # get the object for the cluster, AKS side
        cluster = clusters.managed_clusters.get(resource_group, cluster_name)
        
        # get existing, to ensure uniqueness
        node_pools = [node_pool for node_pool in clusters.agent_pools.list(resource_group, cluster_name)]
        node_pool_ids = [node_pool.name for node_pool in node_pools]

        node_pool_id = self.config.get('nodePoolId', None)
        if node_pool_id is None or len(node_pool_id) == 0:
            cnt = 0
            while ('nodepool%s' % cnt) in node_pool_ids:
                cnt += 1
            node_pool_id = 'nodepool%s' % cnt
        elif node_pool_id in node_pool_ids:
            raise Exception("Node pool '%s' already exists" % node_pool_id)
        logging.info("Using name %s for node pool" % node_pool_id)
            
        node_pool_config = self.config.get("nodePoolConfig", {})
        
        node_pool_builder = NodePoolBuilder(None)

        # Sanity check for node pools
        node_pool_vnets = set()
        for node_pool in node_pools:
            nodepool_vnet = node_pool.vnet_subnet_id.split("/")[-3]
            node_pool_vnets.add(nodepool_vnet)
        if len(node_pool_vnets) > 0:
            node_pool_vnet = node_pool_config.get("vnet", None)
            node_pool_subnet = node_pool_config.get("subnet", None)
            node_pool_vnet, _ = node_pool_builder.resolve_network(inherit_from_host=node_pool_config.get("useSameNetworkAsDSSHost"),
                                           cluster_vnet=node_pool_vnet,
                                           cluster_subnet=node_pool_subnet,
                                           connection_info=connection_info,
                                           credentials=credentials,
                                           resource_group=resource_group,
                                           dss_host_resource_group=dss_host_resource_group)
            if not node_pool_vnet in node_pool_vnets:
                node_pool_vnets.add(node_pool_vnet)
                raise Exception("Node pools must all share the same vnet. Current node pools configuration yields vnets {}.".format(",".join(node_pool_vnets)))

        
        
        node_pool_builder.with_name(node_pool_id)
        node_pool_builder.with_vm_size(node_pool_config.get("vmSize", None))
        vnet = node_pool_config.get("vnet", None)
        subnet = node_pool_config.get("subnet", None)
        node_pool_builder.with_network(inherit_from_host=node_pool_config.get("useSameNetworkAsDSSHost"),
                                       cluster_vnet=vnet,
                                       cluster_subnet=subnet,
                                       connection_info=connection_info,
                                       credentials=credentials,
                                       resource_group=resource_group,
                                       dss_host_resource_group=dss_host_resource_group)

        node_pool_builder.with_availability_zones(
            use_availability_zones=node_pool_config.get("useAvailabilityZones", True))

        node_pool_builder.with_node_count(enable_autoscaling=node_pool_config.get("autoScaling", False),
                                          num_nodes=node_pool_config.get("numNodes", None),
                                          min_num_nodes=node_pool_config.get("minNumNodes", None),
                                          max_num_nodes=node_pool_config.get("maxNumNodes", None))

        node_pool_builder.with_mode(mode=node_pool_config.get("mode", "Automatic"),
                                    system_pods_only=node_pool_config.get("systemPodsOnly", True))

        node_pool_builder.with_disk_size_gb(disk_size_gb=node_pool_config.get("osDiskSizeGb", 0))
        node_pool_builder.with_node_labels(node_pool_config.get("labels", None))
        node_pool_builder.with_node_taints(node_pool_config.get("taints", None))
        node_pool_builder.with_gpu(node_pool_config.get("enableGPU", False))

        node_pool_builder.add_tags(dss_cluster_config.get("tags", None))
        node_pool_builder.add_tags(node_pool_config.get("tags", None))
        node_pool_builder.build()
        
        agent_pool = node_pool_builder.agent_pool
        # force the name
        agent_pool.name = node_pool_id
        
        logging.info("Will create pool %s" % json.dumps(agent_pool.as_dict(), indent=2))
        
        def do_create():
            cluster_create_op = clusters.agent_pools.begin_create_or_update(resource_group, cluster_name, node_pool_id, agent_pool)
            return cluster_create_op.result()
        create_result = run_and_process_cloud_error(do_create)
        logging.info("Cluster updated")
        
        if node_pool_builder.gpu:
            kube_config_path = cluster_data["kube_config_path"]
            add_gpu_driver_if_needed(kube_config_path)

        return '<pre class="debug">%s</pre>' % json.dumps(create_result.as_dict(), indent=2)
        
