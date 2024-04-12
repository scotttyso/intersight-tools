## EZDAY2TOOLS Synopsis

The purpose of `ezday2tools.py` is to manage Server Environments in Intersight for day 2 management tasks.  It provides tools to help in obtaining reports on identities, adding new VLANs to policies for domain and server policies.

### Capabilities

   * `add_policies`: Add policies to profiles.  Can select policies/types accross orgs to attach to chassis, domain, and server profiles for new capabilities or to change an existing policy.
   * `add_vlans`: Add a new VLAN to existing VLAN and Ethernet Network Group Policies.  If desired Create a new LAN Connectivity Policy.
   * `clone_policies`: Clone policies from one Organization to another.  Currently only supports policies without child policies.
   * `hcl_inventory`: Use UCS server inventory injested from vCenter to to check Intersight HCL inventory.
   * `server_inventory`: Function to clone policies from one Organization to another.

## EZDAY2TOOLS - `add_vlans`: Use Cases

  - Add VLAN to VLAN Policy and Ethernet Network Groups to Organization List.  If desired also create a new LAN Connectivity Policy for the new VLAN.

### EZDAY2TOOLS - `add_vlans`: Build the YAML definition File

See example `examples/day2tools/add_vlans/add_vlans.json`.

  * The function will loop through all `organizations` listed for `ethernet_network_groups`, `vlan_policy`, and `lan_connectivity`.
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

#### Linux

```bash
tyscott@TYSCOTT-DESKTOP:~$ ezday2tools.py -p clone_policies

------------------------------------------------------------------------------------------------------------

   Begin Function: clone_policies.

------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------------------------------------------

 Select the Server Profile Target Platform.  Options are:
  * FIAttached: Build Pools/Policies/Profiles for a Domain.
  * Standalone: Build Pools/Policies/Profiles for Standalone Servers.
 
    Select an Option Below:
      1. FIAttached
      2. Standalone

Please Enter the Option Number to select for Target Platform.  [1]: 

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
     14. firmware_authenticate
     15. imc_access
     16. ipmi_over_lan
     17. iscsi_adapter
     18. iscsi_boot
     19. iscsi_static_target
     20. lan_connectivity
     21. local_user
     22. power
     23. san_connectivity
     24. sd_card
     25. serial_over_lan
     26. snmp
     27. storage
     28. syslog
     29. thermal
     30. virtual_kvm
     31. virtual_media

Please Enter the Option Number(s) to select for Policies: 1

------------------------------------------------------------------------------------------------------------

 Select the Source Organization to clone the policies from.
 
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

Please Enter the Option Number to select for Organization.  [3]: 3

------------------------------------------------------------------------------------------------------------

 Select the `bios` policies to clone from source org: `common` to destination org: `default`.
 
     Note: Answer can be:
       * Single: 1
       * Multiple: `1,2,3` or `1-3,5-6`
     Select Option(s) Below:
      1. M5-intel-virtual
      2. M5-intel-virtual-tpm
      3. M6-intel-virtual-tpm

Please Enter the Option Number(s) to select for bios Policies: 1
     - Completed POST for Org: common Name: M5-intel-virtual - Moid: 66196a876275723101f316ae

------------------------------------------------------------------------------------------------------------

   End Function: clone_policies.

------------------------------------------------------------------------------------------------------------

tyscott@TYSCOTT-DESKTOP:~$ 
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

Note: `-fi` pulls adds more details, without primarily focused on WWNN/WWPN for server profiles.

See example Excel output in `examples/day2tools/server_inventory`.
