# Intersight Tools to Deploy and Manage Intersight Managed Environments
Converged - HyperConverged - Traditional Domains and Standalone

[![published](https://static.production.devnetcloud.com/codeexchange/assets/images/devnet-published.svg)](https://developer.cisco.com/codeexchange/github/repo/scotttyso/intersight_iac)

## Disclaimer

This code is provided as is.  No warranty, support, or guarantee is provided with this.  But in typical github fashion there is the opportunity to collaborate and share Bug's/Feedback/PR Requests.

## Updates

* 2024-05-18: Changing version numbering to match the `Intersight API` release version that was tested.  This is going back from `4.X` to `1.X` to perform this match.  This is so it is easier for a user to identify which `Intersight API` release the `intersight-tools` release was tested against.

## ezci.py

### General Use Cases
* Deploy Azure Stack HCI Using Cisco Intersight Cloud Orchestrator
* Deploy FlashStack Using Cisco Intersight Cloud Orchestrator
* Deploy FlexPod Using Cisco Intersight Cloud Orchestrator

[README - *ezci*](https://github.com/scotttyso/intersight-tools/blob/master/README.ezci.md)

## ezimm.py

### General Use Cases
* `OS Installation`: Use existing profiles or create new profiles and install an operating system to a list of servers.
* `Build IaC (Infrastructure as Code)` YAML Configuration files from an export of Cisco Intersight Transition Tool JSON from UCSM/UCS Central environments to be consumed with Terraform or this Python library.
* `Build IaC` YAML Configuration files using a guided Wizard to be consumed with Terraform or this Python library.
* `Deploy` Cisco Intersight Policies, Pools, and Profiles/Templates using Python

[README - *ezimm*](https://github.com/scotttyso/intersight-tools/blob/master/README.ezimm.md)

## ezclaim.py

### General Use Case
   * Claim C-Series with Intersight.

[README - *ezclaim*](https://github.com/scotttyso/intersight-tools/blob/master/README.ezclaim.md)

## ezday2tools.py

### General Use Cases
   * `add_policies`: Update Policies attached to chassis, domain, server profiles/templates within the same organization or from a shared organization.
   * `add_vlans`: Function to add a VLAN to existing VLAN Poilcy and Ethernet Network Group Policies.  Optionally can also create LAN Connectivity Policies.
   * `audit_logs`: Function to Get List of Users that have logged into the Account and performed actions/changes.
   * `clone_policies`: Function to clone policies from one Organization to another.
   * `hcl_status`: Function to take UCS inventory from vCenter and validate the status of the HCL VIB.
   * `inventory`: Function to Create a Spreadsheet with inventory for Domains, Chassis, Servers.
   * `server_identities`: Function to get WWNN/WWPN and MAC identities.  By default it only gathers the fibre-channel identities. To get full identities list add the `-fi` option at the CLI.,

[README - *ezday2tools*](https://github.com/scotttyso/intersight-tools/blob/master/README.ezday2tools.md)

## Updates/News

2023-11-18
* Added New README's for Each Use Case, see above.
* Archived intersight_iac.  See: [*Old - README*](https://github.com/scotttyso/intersight-tools/blob/master/archive/README.md)

## Getting Started - Environment Preparation

## Install Visual Studio Code

- Download Here: [*Visual Studio Code*](https://code.visualstudio.com/Download)

- Recommended Extensions: 
  - GitHub Pull Requests and Issues - Author GitHub
  - HashiCorp HCL - Author HashiCorp
  - HashiCorp Terraform - Author HashiCorp
  - Pylance - Author Microsoft
  - Python - Author Microsoft
  - PowerShell (Windows) - Author Microsoft
  - YAML - Author Red Hat

- Authorize Visual Studio Code to GitHub via the GitHub Extension

## Install git

- Linux - Use the System Package Manager - apt/yum etc.

```bash
sudo apt update
sudo apt install git
```

- Windows Download Here: [*Git*](https://git-scm.com/download/win)

configure Git Credentials

```bash
git config --global user.name "<username>"   
git config --global user.email "<email>"
```

## Python Requirements

- Python 3.9 or Greater
- Linux - Use the System Package Manager - apt/yum etc.
- Windows Download Here: [*Python*](https://www.python.org/downloads/) 
  Note: Make sure to select the `Add To System Path Option` during the installation for Windows

### Clone this Repository

#### Linux/Windows

```bash
git clone https://github.com/scotttyso/intersight-tools
cd intersight-tools
```

### Install the Requirements File

#### Linux/Windows

```bash
pip install -r requirements.txt
```

### For Linux Environments - Create Symbolic Links for Simplicity

```bash
sudo ln -s $(readlink -f ezazure.ps1) /usr/bin/ezazure.ps1
sudo ln -s $(readlink -f ezci.py) /usr/bin/ezci.py
sudo ln -s $(readlink -f ezclaim.py) /usr/bin/ezclaim.py
sudo ln -s $(readlink -f ezday2tools.py) /usr/bin/ezday2tools.py
sudo ln -s $(readlink -f ezimm.py) /usr/bin/ezimm.py
sudo ln -s $(readlink -f ezpure_login.ps1) /usr/bin/ezpure_login.ps1
sudo ln -s $(readlink -f ezvcenter.ps1) /usr/bin/ezvcenter.ps1
```

## PowerShell Requirements

- Many Features in the Modules use PowerShell 7.X Features.  Make sure you are running PowerShell 7.X

#### Linux

```bash
sudo snap install powershell --classic
```

#### Windows

[Download PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-windows)

## YAML Schema Notes for auto-completion, Help, and Error Validation:

If you would like to utilize Autocompletion, Help Context, and Error Validation, `(HIGHLY RECOMMENDED)` make sure the files all utilize the `.ezi.yaml` file extension.

And Add the Following to `YAML: Schemas` in Visual Studio Code: Settings > Search for `YAML: Schema`: Click edit in `settings.json`.  In the `yaml.schemas` section:

```bash
"https://raw.githubusercontent.com/terraform-cisco-modules/easy-imm/main/yaml_schema/easy-imm.json": "*.ezi.yaml"
```

Soon the Schema for these YAML Files will be registered with [*SchemaStore*](https://github.com/SchemaStore/schemastore/blob/master/src/api/json/catalog.json) via utilizing this `.ezi.yaml` file extension.  But until then, you will need to still add this to `settings.json`.

