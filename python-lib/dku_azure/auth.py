from azure.common.credentials import ServicePrincipalCredentials
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.mgmt.msi import ManagedServiceIdentityClient
from msrest.authentication import BasicTokenAuthentication
from azure.core.pipeline.policies import BearerTokenCredentialPolicy
from azure.core.pipeline import PipelineRequest, PipelineContext
from azure.core.pipeline.transport import HttpRequest

from dku_utils.access import _is_none_or_blank


def get_credentials_from_connection_info(connection_info, connection_info_secret):
    infos = {}
    infos.update(connection_info_secret)
    infos.update(connection_info)

    user_managed_identity = infos.get('userManagedIdentity', None)
    identity_type = infos.get('identityType','default')
    if identity_type == 'default':
        credentials = DefaultAzureCredential()
    elif identity_type == 'user-assigned-client-id':
        credentials = ManagedIdentityCredential(client_id=infos.get('userManagedIdentityClientId',None))
    elif identity_type == 'user-assigned-resource-id':
        credentials = ManagedIdentityCredential(identity_config={'msi_res_id': infos.get('userManagedIdentityResourceId',None)})
    elif identity_type == 'service-principal':
        client_id = infos.get('clientId', None)
        password = infos.get('password', None)
        tenant_id = infos.get('tenantId', None)
        credentials = ServicePrincipalCredentials(client_id = client_id, secret = password, tenant = tenant_id)
    else:
        raise "Identity type {} is unknown and cannot be used".format(identity_type)

    return credentials



# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------
# Adapt credentials from azure-identity to be compatible with SDK that needs msrestazure or azure.common.credentials
# Need msrest >= 0.6.0
# See also https://pypi.org/project/azure-identity/
# See https://github.com/jongio/azidext/blob/master/python/azure_identity_credential_adapter.py
class AzureIdentityCredentialAdapter(BasicTokenAuthentication):
    def __init__(self, credential=None, resource_id="https://management.azure.com/.default", **kwargs):
        """Adapt any azure-identity credential to work with SDK that needs azure.common.credentials or msrestazure.
        Default resource is ARM (syntax of endpoint v2)
        :param credential: Any azure-identity credential (DefaultAzureCredential by default)
        :param str resource_id: The scope to use to get the token (default ARM)
        """
        super(AzureIdentityCredentialAdapter, self).__init__(None)
        if credential is None:
            credential = DefaultAzureCredential()
        self._policy = BearerTokenCredentialPolicy(credential, resource_id, **kwargs)

    def _make_request(self):
        return PipelineRequest(
            HttpRequest(
                "AzureIdentityCredentialAdapter",
                "https://fakeurl"
            ),
            PipelineContext(None)
        )

    def set_token(self):
        """Ask the azure-core BearerTokenCredentialPolicy policy to get a token.
        Using the policy gives us for free the caching system of azure-core.
        We could make this code simpler by using private method, but by definition
        I can't assure they will be there forever, so mocking a fake call to the policy
        to extract the token, using 100% public API."""
        request = self._make_request()
        self._policy.on_request(request)
        # Read Authorization, and get the second part after Bearer
        token = request.http_request.headers["Authorization"].split(" ", 1)[1]
        self.token = {"access_token": token}

    def signed_session(self, session=None):
        self.set_token()
        return super(AzureIdentityCredentialAdapter, self).signed_session(session)
