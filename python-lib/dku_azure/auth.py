from azure.common.credentials import ServicePrincipalCredentials
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

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
        credentials = ManagedIdentityCredential(identity_config={'id': infos.get('userManagedIdentityResourceId',None)})
    elif identity_type == 'service-principal':
        client_id = infos.get('clientId', None)
        password = infos.get('password', None)
        tenant_id = infos.get('tenantId', None)
        credentials = ServicePrincipalCredentials(client_id = client_id, secret = password, tenant = tenant_id)
    else:
        raise "Identity type {} is unknown and cannot be used".format(identity_type)

    return credentials


