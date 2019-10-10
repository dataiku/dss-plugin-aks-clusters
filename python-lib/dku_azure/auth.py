from azure.common.credentials import ServicePrincipalCredentials

from dku_utils.access import _is_none_or_blank

def get_credentials_from_connection_info(connection_info, connection_info_secret):
    client_id = connection_info.get('clientId', None)
    tenant_id = connection_info.get('tenantId', None)
    password = connection_info.get('password', None)
    if _is_none_or_blank(client_id) or _is_none_or_blank(password) or _is_none_or_blank(tenant_id):
        raise Exception('Client, password and tenant must all be defined')

    credentials = ServicePrincipalCredentials(client_id = client_id, secret = password, tenant = tenant_id)
    return credentials