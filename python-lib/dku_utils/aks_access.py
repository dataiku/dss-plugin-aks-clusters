AKS_ACCESS_MODE_ADMIN = "admin"
AKS_ACCESS_MODE_CLUSTER_USER = "cluster-user"

DEFAULT_AKS_ACCESS_MODE = AKS_ACCESS_MODE_ADMIN
AKS_ACCESS_MODE_CHOICES = [
    {"value": AKS_ACCESS_MODE_ADMIN, "label": "Admin"},
    {"value": AKS_ACCESS_MODE_CLUSTER_USER, "label": "Cluster user"},
]
AKS_ACCESS_MODES = {
    choice["value"] for choice in AKS_ACCESS_MODE_CHOICES
}
