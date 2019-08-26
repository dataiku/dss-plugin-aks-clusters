from dataiku.runnables import Runnable
import dataiku
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
        cluster_name = cluster_def["name"]
        
        resource_group_name = dss_cluster_config['config']['resourceGroup']
        # get the object for the cluster, AKS side
        cluster = clusters.managed_clusters.get(resource_group_name, cluster_name)

        return '<pre class="debug">%s</pre>' % json.dumps(cluster.as_dict()['agent_pool_profiles'], indent=2)