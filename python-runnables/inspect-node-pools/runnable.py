from dataiku.runnables import Runnable
import json
from dku_utils.cluster import get_cluster_from_dss_cluster

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
        node_pools = clusters.agent_pools.list(resource_group, cluster_name)
        node_pools = [node_pool for node_pool in node_pools]
        return '<pre class="debug">%s</pre>' % json.dumps([node_pool.as_dict() for node_pool in node_pools], indent=2)
