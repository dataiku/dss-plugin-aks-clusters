# Managed AKS clusters plugin

This plugin allows to dynamically create, manage and scale AKS clusters in DSS.

Requires DSS 6.0 or above.

For more details, please see [the DSS reference documentation](https://doc.dataiku.com/dss/latest/containers/aks/index.html).

## Release notes

### v1.0.6
- Allow nodepools with a minimum of 0 nodes (allowed for user node pools)
- Users can now create node pools with specific [modes](https://docs.microsoft.com/en-us/azure/aks/use-system-pools#system-and-user-node-pools).

### v1.0.5
- Add node labels and node taints to AKS nodepools

### v1.0.4
- Fix `Test network connectivity` macro when the hostname is already an IP.

### v1.0.3

- Minor fix on cluster autoscaler
- Explicit definition of the code-env package versions

### v1.0.2

- Minor fix on Azure API calls.

## License
Copyright (C) 2019-2021 Dataiku

Licensed under the Apache License, version 2.0
