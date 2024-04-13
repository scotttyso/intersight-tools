## EZDAY2TOOLS Synopsis

The purpose of `ezday2tools.py` is to manage Server Environments in Intersight for day 2 management tasks.  It provides tools to help in obtaining reports on identities, adding new VLANs to policies for domain and server policies.

### Capabilities

   * `add_policies`: Update Policies attached to chassis, domain, server profiles/templates within the same organization or from a shared organization.
   * `add_vlans`: Add a new VLAN to existing VLAN Policy and Ethernet Network Group Policies.  If desired Create a new LAN Connectivity Policy.
   * `clone_policies`: Clone policies from one Organization to another.  Currently only supports policies without child policies.
   * `hcl_inventory`: Use UCS server inventory injested from vCenter to to check Intersight HCL inventory.
   * `server_inventory`: Function to clone policies from one Organization to another.

## EZDAY2TOOLS - `add_policies`: Use Case

  - Update Policies attached to chassis, domain, server profiles/templates within the same organization or from a shared organization.

### EZDAY2TOOLS - `add_policies`: Run the wizard

#### Linux

```bash
ezday2tools.py -p add_policies

------------------------------------------------------------------------------------------------------------

   Begin Function: add_policies.

------------------------------------------------------------------------------------------------------------


------------------------------------------------------------------------------------------------------------

 Select the Source Organization for the pools/policies:
 
    Select an Option Below:
      1. Asgard
      2. common
      3. default
      4. RICH
      5. Wakanda

Please Enter the Option Number to select for Organization.  [3]: 2

------------------------------------------------------------------------------------------------------------

 Select the Organization for the Profiles:
 
    Select an Option Below:
      1. Asgard
      2. common
      3. default
      4. RICH
      5. Wakanda

Please Enter the Option Number to select for Organization.  [3]: 5

------------------------------------------------------------------------------------------------------------

 Select the Profile Type.  Options are:
   * chassis: Chassis Profiles.
   * domain: Domain Profiles.
   * FIAttached: Domain Attached Server Profiles/Templates.
   * Standalone: Standalone Server Profiles/Templates.
 
    Select an Option Below:
      1. chassis
      2. domain
      3. FIAttached
      4. Standalone

Please Enter the Option Number to select for Profile Type.  [3]: 1

------------------------------------------------------------------------------------------------------------

 Select the policy types you would like to clone in the environment:
 
     Note: Answer can be:
       * Single: 1
       * Multiple: `1,2,3` or `1-3,5-6`
     Select Option(s) Below:
      1. imc_access
      2. power
      3. snmp
      4. syslog
      5. thermal

Please Enter the Option Number(s) to select for Policy Types.  [press enter to skip]: 3

------------------------------------------------------------------------------------------------------------

 Select the snmp policy from source org: `common` to attach to chassis(s) in org: `Wakanda`.
 
    Select an Option Below:
      1. snmp

Please Enter the Option Number to select for snmp Policy: 1

------------------------------------------------------------------------------------------------------------

    snmp: snmp

------------------------------------------------------------------------------------------------------------


------------------------------------------------------------------------------------------------------------

 Do You want to accept the above configuration for the `policy bucket update`?


Enter `Y` for `True` or `N` for `False` for `Accept`. [Y]: 

------------------------------------------------------------------------------------------------------------

 Select the `chassis` Profiles to update.
 
     Note: Answer can be:
       * Single: 1
       * Multiple: `1,2,3` or `1-3,5-6`
     Select Option(s) Below:
      1. r143e-2-1

Please Enter the Option Number(s) to select for chassis Profiles.  [1]: 
     - Completed PATCH for Org: Wakanda > Name: r143e-2-1 - Moid: 6605c56077696e3201f34e73

------------------------------------------------------------------------------------------------------------

 Do you want to Deploy/Activate the `chassis` profiles?


Enter `Y` for `True` or `N` for `False` for `Deploy Profiles`. [N]: Y

------------------------------------------------------------------------------------------------------------

     - Beginning Profile Deployment for `r143e-2-1`.
     - Completed PATCH for Org: Wakanda > Name: r143e-2-1 - Moid: 6605c56077696e3201f34e73
       * Deploy Still Occuring on `r143e-2-1`.  Waiting 60 seconds.
     - Completed Profile Deployment for `r143e-2-1`.

------------------------------------------------------------------------------------------------------------


------------------------------------------------------------------------------------------------------------

   End Function: add_policies.

------------------------------------------------------------------------------------------------------------

```

## EZDAY2TOOLS - `add_vlans`: Use Cases

  - Add VLAN to VLAN Policy and Ethernet Network Groups to Organization List.  If desired also create a new LAN Connectivity Policy for the new VLAN.

### EZDAY2TOOLS - `add_vlans`: Build the YAML definition File

See example `examples/day2tools/add_vlans/add_vlans.json`.

  * The function will loop through all `organizations` listed.  To create `ethernet_network_groups`, a `vlan_policy`, and `lan_connectivity`.
  * `lan_connectivity` is optional.
  * If `lan_connectivity` is defined all attributes shown are required.  Can have one or more `vnics`.

#### Linux

```bash
ezday2tools.py -p add_vlans -y add_vlans.yaml
```

#### Windows

```powershell
python ezday2tools.py -p add_vlans -y add_vlans.yaml
```

## EZDAY2TOOLS - `clone_policies`: Use Cases

  - Clone policies from one org to another

### EZDAY2TOOLS - `clone_policies`: Run the wizard

  * supports cloning one or more policy types from source to destination organization.
  * supports cloning one or more policies of each policy type.
  * policies with child policies are not supported currently.  If desired please open an Issue.  It just needs some additional development and I didn't have the need.

Not supported:
  * IMC Access
  * iSCSI Boot
  * LAN Connectivity
  * LDAP
  * Local User
  * Port
  * Profiles (chassis/domain/server)
  * SAN Connectivity
  * Storage
  * VLAN
  * VSAN

#### Linux

```bash
ezday2tools.py -p clone_policies

------------------------------------------------------------------------------------------------------------

   Begin Function: clone_policies.

------------------------------------------------------------------------------------------------------------


------------------------------------------------------------------------------------------------------------

 Select the Source Organization to clone the pools/policies from.
 
    Select an Option Below:
      1. Asgard
      2. common
      3. default
      4. RICH
      5. Wakanda

Please Enter the Option Number to select for Organization.  [3]: 2

------------------------------------------------------------------------------------------------------------

 Select the Destination Organization to clone the policies to.
 
    Select an Option Below:
      1. Asgard
      2. common
      3. default
      4. RICH
      5. Wakanda

Please Enter the Option Number to select for Organization.  [3]: 

------------------------------------------------------------------------------------------------------------

   * chassis: Chassis Profiles.
   * domain: Domain Profiles.
   * FIAttached: Domain Attached Server Profiles/Templates.
   * Standalone: Standalone Server Profiles/Templates. 

    Select an Option Below:
      1. chassis
      2. domain
      3. FIAttached
      4. Standalone

Please Enter the Option Number to select for Target Platform.  [3]: 

------------------------------------------------------------------------------------------------------------

 Select the policy types you would like to clone in the environment:
 
     Note: Answer can be:
       * Single: 1
       * Multiple: `1,2,3` or `1-3,5-6`
     Select Option(s) Below:
      1. bios
      2. boot_order
      3. certificate_management
      4. drive_security
      5. ethernet_adapter
      6. ethernet_network_control
      7. ethernet_network_group
      8. ethernet_qos
      9. fc_zone
     10. fibre_channel_adapter
     11. fibre_channel_network
     12. fibre_channel_qos
     13. firmware
     14. ipmi_over_lan
     15. iscsi_adapter
     16. iscsi_static_target
     17. power
     18. sd_card
     19. serial_over_lan
     20. snmp
     21. syslog
     22. thermal
     23. virtual_kvm
     24. virtual_media

Please Enter the Option Number(s) to select for Policies.  [press enter to skip]: 1

------------------------------------------------------------------------------------------------------------

 Select the pool types you would like to clone in the environment:
 
     Note: Answer can be:
       * Single: 1
       * Multiple: `1,2,3` or `1-3,5-6`
     Select Option(s) Below:
      1. ip
      2. iqn
      3. mac
      4. resource
      5. uuid
      6. wwnn
      7. wwpn

Please Enter the Option Number(s) to select for Pools.  [press enter to skip]: 

------------------------------------------------------------------------------------------------------------

 Select the `bios` policies to clone from source org: `common` to destination org: `default`.
 
     Note: Answer can be:
       * Single: 1
       * Multiple: `1,2,3` or `1-3,5-6`
     Select Option(s) Below:
      1. M5-intel-virtual
      2. M5-intel-virtual-tpm
      3. M6-intel-virtual-tpm

Please Enter the Option Number(s) to select for bios Policies: 3
     - Completed POST for Org: common Name: M6-intel-virtual-tpm - Moid: 661980966275723101045b92

------------------------------------------------------------------------------------------------------------

   End Function: clone_policies.

------------------------------------------------------------------------------------------------------------
```

## EZDAY2TOOLS - `hcl_inventory`: Use Cases

  - Collect UCS Inventory from list of vCenters and compare HCL inventory results in Intersight.

### EZDAY2TOOLS - `hcl_inventory`: Obtain vCenter Inventory with `vcenter-hcl-inventory.ps1`

#### Install PowerShell - Mac/Linux

  - macOS: [PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-macos)
  - Ubuntu: [Powershell](https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu)

#### Run the PowerShell Script (Windows)
```powershell
.\vcenter-hcl-inventory.ps1 -j inventory.json
```

#### Run the PowerShell Script (Linux)
```bash
pwsh
./vcenter-hcl-inventory.ps1 -j inventory.json
```

See example `inventory.json` file in `examples/day2tools/hcl_inventory`.

### EZDAY2TOOLS - `hcl_inventory`: Compare Inventory to Intersight and Create Spreadsheet.

From the previous PowerShell module use the output file for input to `ezday2tools.py` in example `2024-04-10_09-49-27.json`.

#### Linux

```bash
ezday2tools.py -p hcl_inventory -j 2024-04-10_09-49-27.json
```

#### Windows

```powershell
python ezday2tools.py -p hcl_inventory -j 2024-04-10_09-49-27.json
```

See example Excel output in `examples/day2tools/hcl_inventory`.

## EZDAY2TOOLS - `server_inventory`: Use Cases

  - Collect UCS Inventory and export to Spreadsheet.

### EZDAY2TOOLS - `server_inventory`: Get Inventory from Intersight and Create Spreadsheet.

#### Linux

```bash
ezday2tools.py -p server_inventory -fi
```

#### Windows

```powershell
python ezday2tools.py -p server_inventory -fi
```

Note: `-fi` pulls adds more details; without, primarily focused of function is WWNN/WWPN identities for server profiles.

See example output in `examples/day2tools/server_inventory`.
