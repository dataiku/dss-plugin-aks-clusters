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
        cluster_data, clusters, dss_cluster_settings, dss_cluster_config = get_cluster_from_dss_cluster(self.config['clusterId'])

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
        for profile in node_pools:
            if profile.name == node_pool_id or (_is_none_or_blank(node_pool_id) and len(node_pools) == 1):
                node_pool = profile
        if node_pool is None:
            raise Exception("Unable to find node pool '%s'" % (node_pool_id))

        desired_count = self.config['numNodes']
        logging.info("Resize to %s" % desired_count)
        if desired_count == 0:
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
        
