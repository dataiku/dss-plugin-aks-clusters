## Release 2.0.0

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
