from dataiku.runnables import Runnable
import json, logging
from dku_utils.cluster import get_cluster_from_dss_cluster
from dku_utils.access import _is_none_or_blank
from dku_azure.utils import run_and_process_cloud_error

class MyRunnable(Runnable):
    def __init__(self, project_key, config, plugin_config):
        self.project_key = project_key
        self.config = config
        self.plugin_config = plugin_config
        
    def get_progress_target(self):
        return None

    def run(self, progress_callback):
        cluster_data, clusters, dss_cluster_settings, dss_cluster_config, _, _ = get_cluster_from_dss_cluster(self.config['clusterId'])

        # retrieve the actual name in the cluster's data
        if cluster_data is None:
            raise Exception("No cluster data (not started?)")
        cluster_def = cluster_data.get("cluster", None)
        if cluster_def is None:
            raise Exception("No cluster definition (starting failed?)")
        cluster_id = cluster_def["id"]
        _,_,subscription_id,_,resource_group,_,_,_,cluster_name = cluster_id.split("/")
        cluster = clusters.managed_clusters.get(resource_group, cluster_name)
        
        # get the object for the cluster, AKS side
        cluster = clusters.managed_clusters.get(resource_group, cluster_name)
        
        node_pool_id = self.config.get('nodePoolId', None)
        node_pool = None
        node_pools = [node_pool for node_pool in clusters.agent_pools.list(resource_group, cluster_name)]
        if _is_none_or_blank(node_pool_id) and len(node_pools) > 1:
            raise Exception("Cluster has %s node pools, you need to specify the node pool id" % len(node_pools))
        for profile in node_pools:
            if profile.name == node_pool_id or (_is_none_or_blank(node_pool_id) and len(node_pools) == 1):
                node_pool = profile
        if node_pool is None:
            raise Exception("Unable to find node pool '%s'" % (node_pool_id))
        node_pool_id = node_pool.name
        logging.info("Node pool selected is %s " % node_pool_id)

        autoscaling_enabled = self.config['autoScaling']
        if autoscaling_enabled:
            min_nodes = self.config['minNumNodes']
            max_nodes = self.config['maxNumNodes']
            if min_nodes is None:
                raise Exception("Cannot make auto scalable cluster with no minimum number of nodes.")
            elif max_nodes is None:
                raise Exception("Cannot make auto scalable cluster with no maximum number of nodes.")
            elif min_nodes > max_nodes:
                raise Exception("Cannot make auto scalable cluster with a maximum number of nodes less than its "
                                "minimum number of nodes.")
            else:
                logging.info("Resizing cluster to auto scale with %s min nodes and %s max nodes"
                             % (min_nodes, max_nodes))
                node_pool.enable_cluster_autoscaling = autoscaling_enabled
                node_pool.min_count = min_nodes
                node_pool.max_count = max_nodes
        else:
            desired_count = self.config['numNodes']
            logging.info("Resize to %s" % desired_count)
            if desired_count == 0:
                if len(node_pools) == 1:
                    raise Exception("Can't delete node pool, a cluster needs at least one running node pool")
                def do_delete():
                    cluster_update_op = clusters.agent_pools.begin_delete(resource_group, cluster_name, node_pool_id)
                    return cluster_update_op.result()
                delete_result = run_and_process_cloud_error(do_delete)
                logging.info("Cluster updated")
                return '<pre class="debug">Node pool %s deleted</pre>' % node_pool_id
            else:
                node_pool.count = desired_count
                logging.info("Waiting for cluster resize")

        def do_update():
            cluster_update_op = clusters.agent_pools.begin_create_or_update(resource_group, cluster_name, node_pool_id, node_pool)
            return cluster_update_op.result()
        update_result = run_and_process_cloud_error(do_update)
        logging.info("Cluster updated")
        return '<pre class="debug">%s</pre>' % json.dumps(update_result.as_dict(), indent=2)
        
