import json, logging
import dataiku
from azure.mgmt.containerservice import ContainerServiceClient
from dataiku.core.intercom import backend_json_call
from dku_azure.auth import get_credentials_from_connection_info, get_credentials_from_connection_infoV2
from dku_azure.utils import get_subscription_id
from dku_utils.access import _is_none_or_blank


def make_overrides(config, kube_config, kube_config_path, acr_name=None):
    # alter the spark configurations to put the cluster master and image repo in the properties
    container_settings = {
        'executionConfigsGenericOverrides': {
            'kubeCtlContext': kube_config["current-context"], # has to exist, it's a config file we just built
            'kubeConfigPath': kube_config_path # the config is not merged into the main config file, so we need to pass the config file pth
        }
    }
    if acr_name is not None:
        container_settings['executionConfigsGenericOverrides']['repositoryURL'] = "{}.azurecr.io".format(acr_name)
    return {'container':container_settings}


def get_cluster_from_connection_info(config, plugin_config):
    """
    Return a ContainerServiceClient after authenticating using the connection info.
    """
    connection_info = config.get("connectionInfo", None)
    connection_info_secret = plugin_config.get("connectionInfo", None)
    if not _is_none_or_blank(connection_info) or not _is_none_or_blank(connection_info_secret):
        logging.warn("Using legacy authentication fields. Clear them to use the new ones.")
        credentials = get_credentials_from_connection_info(connection_info, connection_info_secret)
        subscription_id = connection_info.get('subscriptionId', None)
    else:
        connection_info_v2 = config.get("connectionInfoV2",{"identityType":"default"})
        credentials, _ = get_credentials_from_connection_infoV2(connection_info_v2)
        subscription_id = get_subscription_id(connection_info_v2)
    clusters_client = ContainerServiceClient(credentials, subscription_id)
    return clusters_client, connection_info, credentials

def get_cluster_from_dss_cluster(dss_cluster_id):
    # get the public API client
    client = dataiku.api_client()

    # get the cluster object in DSS
    found = False
    for c in client.list_clusters():
        if c['name'] == dss_cluster_id:
            found = True
    if not found:
        raise Exception("DSS cluster %s doesn't exist" % dss_cluster_id)
    dss_cluster = client.get_cluster(dss_cluster_id)

    # get the settings in it
    dss_cluster_settings = dss_cluster.get_settings()
    dss_cluster_config = dss_cluster_settings.get_raw()['params']['config']
    # resolve since we get the config with the raw preset setup
    dss_cluster_config = backend_json_call('plugins/get-resolved-settings', data={'elementConfig':json.dumps(dss_cluster_config), 'elementType':dss_cluster_settings.get_raw()['type']})
    logging.info("Resolved cluster config : %s" % json.dumps(dss_cluster_config))
    # build the helper class from the cluster settings (the macro doesn't have the params)
    clusters, connection_info, credentials = get_cluster_from_connection_info(dss_cluster_config.get("config"), dss_cluster_config.get("pluginConfig"))

    cluster_data = dss_cluster_settings.get_plugin_data()

    return cluster_data, clusters, dss_cluster_settings, dss_cluster_config, connection_info, credentials
    
