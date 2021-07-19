import os, json, logging, yaml, time, uuid
from dataiku.cluster import Cluster

from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.msi import ManagedServiceIdentityClient
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.core.pipeline.policies import UserAgentPolicy
from azure.core.exceptions import ResourceNotFoundError
from msrestazure.azure_exceptions import CloudError

from dku_utils.access import _is_none_or_blank, _has_not_blank_property
from dku_utils.cluster import make_overrides, get_cluster_from_connection_info
from dku_azure.auth import get_credentials_from_connection_info, get_credentials_from_connection_infoV2
from dku_azure.clusters import ClusterBuilder
from dku_azure.utils import run_and_process_cloud_error, get_subnet_id, get_instance_metadata, get_subscription_id
from dku_azure.auth import AzureIdentityCredentialAdapter

class MyCluster(Cluster):
    def __init__(self, cluster_id, cluster_name, config, plugin_config):
        self.cluster_id = cluster_id
        self.cluster_name = cluster_name
        self.config = config
        self.plugin_config = plugin_config

    def _get_credentials(self):
        connection_info = self.config.get("connectionInfo", None)
        connection_info_secret = self.plugin_config.get("connectionInfo", None)
        if not _is_none_or_blank(connection_info) or not _is_none_or_blank(connection_info_secret):
            logging.warn("Using legacy authentication fields. Clear them to use the new ones.")
            credentials = get_credentials_from_connection_info(connection_info, connection_info_secret)
            subscription_id = connection_info.get('subscriptionId', None)
        else:
            connection_info_v2 = self.config.get("connectionInfoV2",{"identityType":"default"})
            credentials = get_credentials_from_connection_infoV2(connection_info_v2)
            subscription_id = get_subscription_id(connection_info_v2)
        return credentials, subscription_id

    def start(self):
        """
        Build the create cluster request.
        """
        credentials, subscription_id = self._get_credentials()

        # Fetch metadata should we need them
        if self.config.get("useSameResourceGroupAsDSSHost",True) or self.config.get("useSameLocationAsDSSHost",True):
            metadata = get_instance_metadata()

        # Resource group
        resource_group = self.config.get('resourceGroup', None)
        if _is_none_or_blank(resource_group):
            if self.config.get("useSameResourceGroupAsDSSHost",True):
                resource_group = metadata["compute"]["resourceGroupName"]
                logging.info("Using same resource group as DSS: {}".format(resource_group))
            else:
                resource_group = self.config.get("resourceGroupV2",None)
        else: 
            logging.warn("Fetching resource group \"{}\" from legacy setting. Clear it to use the new one.".format(resource_group))

        # Location
        location = self.config.get('location', None)
        if _is_none_or_blank(location):
            if self.config.get("useSameLocationAsDSSHost",True):
                location = metadata["compute"]["location"]
                logging.info("Using same location as DSS: {}".format(location))
            else:
                location = self.config.get("locationV2",None)
        else:
            logging.warn("Fetching location \"{}\" from legacy setting. Clear it to use the new one.".format(location))

        # Consistency checks
        if _is_none_or_blank(resource_group):
            raise Exception("A resource group to put the cluster in is required")
        if _is_none_or_blank(location):
            raise Exception("A location to put the cluster in is required")

        # AKS Client
        clusters_client = None

        # Credit the cluster to DATAIKU
        if os.environ.get("DISABLE_AZURE_USAGE_ATTRIBUTION", "0") == "1":
            logging.info("Azure usage attribution is disabled")
            clusters_client = ContainerServiceClient(credentials, subscription_id)
        else:
            policy = UserAgentPolicy()
            policy.add_user_agent('pid-fd3813c7-273c-5eec-9221-77323f62a148')
            clusters_client = ContainerServiceClient(credentials, subscription_id, user_agent_policy=policy)

        # check that the cluster doesn't exist yet, otherwise azure will try to update it
        # and will almost always fail
        try:
            existing = clusters_client.managed_clusters.get(resource_group, self.cluster_name)
            if existing is not None:
                raise Exception("A cluster with name %s in resource group %s already exists" % (self.cluster_name, resource_group))
        except CloudError as e:
            logging.info("Cluster doesn't seem to exist yet")
        except ResourceNotFoundError as e:
            logging.info("Cluster doesn't seem to exist yet")

        cluster_builder = ClusterBuilder(clusters_client)
        cluster_builder.with_name(self.cluster_name)
        cluster_builder.with_dns_prefix("{}-dns".format(self.cluster_name))
        cluster_builder.with_resource_group(resource_group)
        cluster_builder.with_location(location)
        cluster_builder.add_tags(self.config.get("tags", None))
        cluster_builder.with_linux_profile() # default is None
        cluster_builder.with_network_profile(service_cidr=self.config.get("serviceCIDR", None),
                                         dns_service_ip=self.config.get("dnsServiceIP", None),
                                         load_balancer_sku=self.config.get("loadBalancerSku", None),
                                         outbound_type=self.config.get("outboundType", None),
                                         network_plugin=self.config.get("networkPlugin"),
                                         docker_bridge_cidr=self.config.get("dockerBridgeCidr"))

        if self.config.get("useCustomNodeResourceGroup", False):
            cluster_builder.with_node_resource_group(self.config.get("nodeResourceGroup"))

        # Cluster identity
        connection_info = self.config.get("connectionInfo", None)
        cluster_idendity_legacy_use_distinct_sp = self.config.get("useDistinctSPForCluster", False)
        cluster_idendity_legacy_sp = self.config.get("clusterServicePrincipal",None)
        cluster_identity_type = None
        cluster_identity = None
        if not _is_none_or_blank(connection_info) or not _is_none_or_blank(cluster_idendity_legacy_sp):
            logging.warn("Using legacy options to configure cluster identity. Clear them to use the new ones.")
            if not cluster_idendity_legacy_use_distinct_sp and not _is_none_or_blank(connection_info):
                cluster_sp = connection_info
            elif cluster_idendity_legacy_use_distinct_sp and not _is_none_or_blank(cluster_idendity_legacy_sp):
                cluster_sp = self.config.get("clusterServicePrincipal")
            else:
                raise Exception("Legacy options are not complete enough to determine cluster identity settings")
            cluster_builder.with_cluster_sp_legacy(cluster_service_principal_connection_info=cluster_sp)
        else:
            cluster_identity = self.config.get("clusterIdentity",{"identityType":"managed-identity"})  
            cluster_identity_type = cluster_identity.get("identityType", "managed-identity")
            if cluster_identity_type == "managed-identity":
                control_plane_mi = None if cluster_identity.get("useAKSManagedIdentity",True) else cluster_identity["controlPlaneUserAssignedIdentity"]
                cluster_builder.with_managed_identity(control_plane_mi)
                if control_plane_mi is None:
                    logging.info("Configure cluster with system managed identity.")
                else:
                    logging.info("Configure cluster with user assigned identity: {}".format(control_plane_mi))
                if not cluster_identity.get("useAKSManagedKubeletIdentity",True):
                    kubelet_mi = cluster_identity["kubeletUserAssignedIdentity"]
                    _,_,mi_subscription_id,_,mi_resource_group,_,_,_,mi_name = kubelet_mi.split("/")
                    msiclient = ManagedServiceIdentityClient(AzureIdentityCredentialAdapter(credentials), mi_subscription_id)
                    mi = msiclient.user_assigned_identities.get(mi_resource_group, mi_name)
                    cluster_builder.with_kubelet_identity(kubelet_mi, mi.client_id, mi.principal_id)
                    logging.info("Configure kubelet identity with user assigned identity resourceId=\"{}\", clientId=\"{}\", objectId=\"{}\"".format(kubelet_mi, mi.client_id, mi.principal_id))
            elif cluster_identity_type == "service-principal":
                cluster_builder.with_cluster_sp(cluster_identity["clientId"], cluster_identity["password"])
                logging.info("Configure cluster with service principal")
            else:
                raise Exception("Cluster identity type \"{}\" is unknown".format(cluster_identity_type))


        # Fail fast for non existing ACRs to avoid drama in case of failure AFTER cluster is created
        if cluster_identity_type is not None and cluster_identity is not None:
            if cluster_identity_type == "managed-identity" and cluster_identity.get("useAKSManagedKubeletIdentity",True):
                acr_name = cluster_identity.get("attachToACRName", None)
                if not _is_none_or_blank(acr_name):
                    # build acr scope
                    acr_identifier_splitted = acr_name.split('/')
                    acr_subscription_id = subscription_id
                    acr_resource_group = resource_group
                    if 9 == len(acr_identifier_splitted):
                        _,_,acr_subscription_id,_,acr_resource_group,_,_,_,acr_name = acr_identifier_splitted
                    elif 2 == len(acr_identifier_splitted):
                        acr_resource_group, acr_name = acr_identifier_splitted
                        
                    authorization_client = AuthorizationManagementClient(credentials, acr_subscription_id)
                    acr_scope = "/subscriptions/{acr_subscription_id}/resourceGroups/{acr_resource_group}/providers/Microsoft.ContainerRegistry/registries/{acr_name}".format(**locals())
                    try:
                        acr_roles = list(authorization_client.role_definitions.list(acr_scope,"roleName eq 'AcrPull'"))
                    except ResourceNotFoundError as e:
                        raise Exception("ACR {} not found. Check it exists and you are Owner of it.".format(acr_scope))
                    if 0 == len(acr_roles):
                        raise Exception("Exception could not find the AcrPull role on the ACR {}. Check you are Owner of it.".format(acr_scope))
                    else:
                        acr_role_id = acr_roles[0].id
                        logging.info("ACR pull role id: %s", acr_role_id)


        # Access level
        if self.config.get("privateAccess"):
            cluster_builder.with_private_access(self.config.get("privateAccess"))

        cluster_builder.with_cluster_version(self.config.get("clusterVersion", None))

        # Node pools
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

            node_pool_builder.with_mode(mode=node_pool_conf.get("mode", "Automatic"),
                                        system_pods_only=node_pool_conf.get("systemPodsOnly", True))

            node_pool_builder.with_disk_size_gb(disk_size_gb=node_pool_conf.get("osDiskSizeGb", 0))
            node_pool_builder.with_node_labels(node_pool_conf.get("labels", None))
            node_pool_builder.with_node_taints(node_pool_conf.get("taints", None))
            node_pool_builder.add_tags(self.config.get("tags", None))
            node_pool_builder.add_tags(node_pool_conf.get("tags", None))
            node_pool_builder.build()
            cluster_builder.with_node_pool(node_pool=node_pool_builder.agent_pool_profile)


        # Run creation
        logging.info("Start creation of cluster")
        def do_creation():
            cluster_create_op = cluster_builder.build()
            return cluster_create_op.result()
        create_result = run_and_process_cloud_error(do_creation)
        logging.info("Cluster creation finished")


        # Attach to ACR
        acr_attachment = {}
        if cluster_identity_type is not None and cluster_identity is not None:
            if cluster_identity_type == "managed-identity" and cluster_identity.get("useAKSManagedKubeletIdentity",True):
                kubelet_mi_object_id = create_result.identity_profile.get("kubeletidentity").object_id
                logging.info("Kubelet Managed Identity object id: %s", kubelet_mi_object_id)
                if not _is_none_or_blank(acr_name):
                    logging.info("Assign ACR pull role id %s to %s", acr_role_id, kubelet_mi_object_id)
                    role_assignment = authorization_client.role_assignments.create(
                        scope=acr_scope,
                        role_assignment_name=str(uuid.uuid4()),
                        parameters= {
                            "properties": {
                                "role_definition_id": acr_role_id,
                                "principal_id": kubelet_mi_object_id,
                            },
                        },
                    )
                    acr_attachment.update({
                        "name": acr_name,
                        "resource_group": acr_resource_group,
                        "subscription_id": acr_subscription_id,
                        "resource_id": acr_scope,
                        "role_assignment": role_assignment.as_dict(),
                    })

        logging.info("Fetching kubeconfig for cluster {} in {}...".format(self.cluster_name, resource_group))
        def do_fetch():
            return clusters_client.managed_clusters.list_cluster_admin_credentials(resource_group, self.cluster_name)
        get_credentials_result = run_and_process_cloud_error(do_fetch)
        kube_config_content = get_credentials_result.kubeconfigs[0].value.decode("utf8")
        logging.info("Writing kubeconfig file...")
        kube_config_path = os.path.join(os.getcwd(), "kube_config")
        with open(kube_config_path, 'w') as f:
            f.write(kube_config_content)

        overrides = make_overrides(
                self.config,
                yaml.safe_load(kube_config_content),
                kube_config_path,
                acr_name = None if _is_none_or_blank(acr_attachment) else acr_attachment["name"],
        )

        return [overrides, {"kube_config_path": kube_config_path, "cluster": create_result.as_dict(), "acr_attachment": acr_attachment}]


    def stop(self, data):
        credentials, _ = self._get_credentials()

        # Do NOT use the conf but the actual values from the cluster here
        cluster_resource_id = data["cluster"]["id"]
        _,_,subscription_id,_,resource_group,_,_,_,cluster_name = cluster_resource_id.split("/")
        clusters_client = ContainerServiceClient(credentials, subscription_id)

        # Try to detach from ACR if required. It is not mandatory but if not done, it would pollute
        # the ACR with multiple invalid role attachments and consume attachment quotas
        node_resource_group = data["cluster"]["node_resource_group"]
        acr_attachment = data.get("acr_attachment", None)
        if not _is_none_or_blank(acr_attachment):
            logging.info("Cluster has an ACR attachment, check managed identity")
            cluster_identity_profile = data["cluster"]["identity_profile"]
            kubelet_mi_resource_id = cluster_identity_profile["kubeletidentity"].get("resource_id", None)
            if  kubelet_mi_resource_id is not None:
                _,_,mi_subscription_id,_,mi_resource_group,_,_,_,mi_name = kubelet_mi_resource_id.split("/")
                if mi_resource_group == node_resource_group:
                    logging.info("Cluster has an AKS managed kubelet identity, try to detach")
                    authorization_client = AuthorizationManagementClient(credentials, acr_attachment["subscription_id"])
                    try:
                        authorization_client.role_assignments.delete_by_id(acr_attachment["role_assignment"]["id"])
                    except ResourceNotFoundError as e:
                        logging.warn("It looks that the ACR role assignment doesnt exist. Ignore this step")


        def do_delete():
            future = clusters_client.managed_clusters.begin_delete(resource_group, cluster_name)
            return future.result()
        delete_result = run_and_process_cloud_error(do_delete)

        # delete returns void, so we poll until the cluster is really gone
        gone = False
        while not gone:
            time.sleep(5)
            try:
                cluster = clusters_client.managed_clusters.get(resource_group, cluster_name)
                if cluster.provisioning_state.lower() != 'deleting':
                    logging.info("Cluster is not deleting anymore, must be deleted now (state = %s)" % cluster.provisioning_state)
            # other exceptions should not be ignored
            except ResourceNotFoundError as e:
                logging.info("Cluster doesn't seem to exist anymore, considering it deleted")
                gone = True
