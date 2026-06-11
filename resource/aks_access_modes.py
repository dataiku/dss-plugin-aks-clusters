from dku_utils.aks_access import AKS_ACCESS_MODE_CHOICES


def do(payload, config, plugin_config, inputs):
    return {"choices": AKS_ACCESS_MODE_CHOICES}
