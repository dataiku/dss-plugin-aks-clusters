# Changelog

## Version 3.0.0 - Feature release

 - Add more supported Python versions. This plugin can now 3.10 and 3.11
 - Drop of support for python 2.7

## Version 2.3.0 - Feature release

 - The default node type is no longer a burstable one but a D8s_v5 (32 GB RAM, 8vCPU) 
 - Add support of cluster and node OS upgrade policy at cluster creation (Supported only with python 37+ codeenv)

## Version 2.2.1 - Feature release

 - Feature: new action to add a node pool to a cluster
 - Allow forcing a different subscription when using user assigned managed identities for credentials
 - Improve error display for cluster starts in regions without availability zones
 - Fix deleting of node pools by resizing them to 0 nodes

## Version 2.2.0 - Feature release

 - Add more supported Python versions. This plugin can now use 2.7 (deprecated), 3.6, 3.7, 3.8, 3.9
 - Fix vnet auto-attach managed identity when let AKS provision the control plane identity

## Version 2.1.0 - Feature release

- Support GPU out-of-the-box
- Add ability to manually set additional cluster settings

## Version 2.0.3 - Bugfix release

- Explicit dependency on `<0.7 mssrest`

## Version 2.0.2 - Bugfix release

- Fix node taints

## Version 2.0.1 - Bugfix release

- Fix resource group mixup when specifying custom resource group and reuse of host's network settings

## Version 2.0.0 - Feature release

This release brings a whole new system to manage identities and credentials

- Feature: Add support for Python 3.6 and Python 3.7.
- Feature: Support for 3 new auth modes:  default env, managed identity (with client id), managed identity (with resource id)
- Feature: Support for AKS user assigned identities, defaults to inherit DSS identity
- Feature: Support for AKS managed identities, with ACR auto-attach (and auto-detach at stop), VNet auto-attach (and detach at stop)
- Feature: Tag support
- Feature: Auto-detect resource group and location, defaults to same as DSS Node
- Feature: Auto detect subscription id for all auth modes
- Feature: multi-AZ deployment option for node groups
- Feature: Custom node resource group
- Bugfix: Stop/Detach not longer relies on current parameters set but on actual deployed cluster values.

## Version 1.0.6

- Allow nodepools with a minimum of 0 nodes (allowed for user node pools)
- Users can now create node pools with specific [modes](https://docs.microsoft.com/en-us/azure/aks/use-system-pools#system-and-user-node-pools).

## Version 1.0.5
- Add node labels and node taints to AKS nodepools

## Version 1.0.4
- Fix `Test network connectivity` macro when the hostname is already an IP.

## Version 1.0.3

- Minor fix on cluster autoscaler
- Explicit definition of the code-env package versions

## Version 1.0.2

- Minor fix on Azure API calls.
