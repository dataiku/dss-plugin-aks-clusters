AKS_ACCESS_MODE_CLUSTER_ADMIN = "cluster-admin"
AKS_ACCESS_MODE_CLUSTER_USER = "cluster-user"

DEFAULT_AKS_ACCESS_MODE = AKS_ACCESS_MODE_CLUSTER_ADMIN
AKS_ACCESS_MODE_CHOICES = [
    {"value": AKS_ACCESS_MODE_CLUSTER_ADMIN, "label": "Cluster Admin"},
    {"value": AKS_ACCESS_MODE_CLUSTER_USER, "label": "Cluster User"},
]
AKS_ACCESS_MODES = {
    choice["value"] for choice in AKS_ACCESS_MODE_CHOICES
}
