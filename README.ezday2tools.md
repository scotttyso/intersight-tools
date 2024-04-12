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

## EZDAY2TOOLS - `hcl_inventory`: Use Cases

  - Collect UCS Inventory from list of vCenters and compare HCL inventory results in Intersight.

### EZDAY2TOOLS - `hcl_inventory`: Obtain vCenter Inventory with `vcenter-hcl-inventory.ps1`

#### Install PowerShell

  - macOS: [PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-macos)
  - Ubuntu: [Powershell](https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu)

#### Install VMware PowerCLI

```bash
pwsh
Install-Module -Name VMware.PowerCLI
```

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
