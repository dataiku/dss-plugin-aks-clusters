from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, ClientSecretCredential

from dku_utils.access import _is_none_or_blank

def get_credentials_from_connection_info(connection_info, connection_info_secret):
    client_id = connection_info.get('clientId', None)
    tenant_id = connection_info.get('tenantId', None)
    password = connection_info.get('password', None)
    if _is_none_or_blank(client_id) or _is_none_or_blank(password) or _is_none_or_blank(tenant_id):
        raise Exception('Client, password and tenant must all be defined')

    credentials = ClientSecretCredential(tenant_id, client_id, password)
    return credentials


def get_credentials_from_connection_infoV2(connection_infos):
    infos = connection_infos
    identity_type = infos.get('identityType','default')
    managed_identity_id = None
    if identity_type == 'default':
        credentials = DefaultAzureCredential()
    elif identity_type == 'user-assigned':
        managed_identity_id = infos.get('userManagedIdentityId')
        if managed_identity_id.startswith("/"):
            credentials = ManagedIdentityCredential(identity_config={'msi_res_id': managed_identity_id})
        else:
            credentials = ManagedIdentityCredential(client_id=managed_identity_id)
    elif identity_type == 'service-principal':
        client_id = infos.get('clientId', None)
        password = infos.get('password', None)
        tenant_id = infos.get('tenantId', None)
        credentials = ClientSecretCredential(tenant_id, client_id, password)
    else:
        raise Exception("Identity type {} is unknown and cannot be used".format(identity_type))

    return credentials, managed_identity_id
