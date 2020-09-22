from azure.common.credentials import ServicePrincipalCredentials
from msrestazure.azure_active_directory import MSIAuthentication

from dku_utils.access import _is_none_or_blank

def get_credentials_from_connection_info(connection_info, connection_info_secret):
    user_managed_identity = connection_info.get('userManagedIdentity', None)
    client_id = connection_info.get('clientId', None)
    password = connection_info.get('password', None)
    tenant_id = connection_info.get('tenantId', None)
    if not _is_none_or_blank(user_managed_identity) and not _is_none_or_blank(client_id) and not _is_none_or_blank(password):
        credentials = MSIAuthentication(msi_res_id = user_managed_identity)
    elif not _is_none_or_blank(client_id) and not _is_none_or_blank(tenant_id) and not _is_none_or_blank(password):
        credentials = ServicePrincipalCredentials(client_id = client_id, secret = password, tenant = tenant_id)
    else:
        raise Exception('You must defined User-assigned managed identity or Tenant with Client and Password')
    return credentials
