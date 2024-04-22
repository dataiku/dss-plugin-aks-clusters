# Changelog

## Version 2.1.1 - Bugfix release
- Update Nvidia driver location

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
