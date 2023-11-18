## Running the Wizard

- It is recommend to add the following secure variables to your environment before running the script

#### Linux

```bash
## Intersight Variables
export intersight_api_key_id="<your_intersight_api_key>"
export intersight_secret_key="~/Downloads/SecretKey.txt"
# The above example is based on the key being in your Downloads folder.  Correct for your environment.

## Terraform Cloud Variables
export terraform_cloud_token="<your_terraform_cloud_token>"
```

#### Windows

```powershell
## Powershell Intersight Variables
$env:intersight_api_key_id="<your_intersight_api_key>"
$env:intersight_secret_key="$HOME\Downloads\SecretKey.txt"
# The above example is based on the key being in your Downloads folder.  Correct for your environment.

## Powershell Terraform Cloud Variables
$env:terraform_cloud_token="<your_terraform_cloud_token>"
```

### Running the Wizard for Brownfield Migration with the Cisco Intersight Transition Tool
- Use a configuration migrated from UCS Central or Manager using the Intersight Transition Tool

```bash
./ezimm.py -j {json_file_name.json}
```

### Running the Wizard for Greenfield Deployment
- Running the Wizard to generate IaC YAML files through a Question and Answer Wizard

```bash
./ezimm.py
```

## Wizard Help Menu

```bash
./ezimm.py -h

Intersight Easy IMM Deployment Module

options:
  -h, --help            show this help message and exit
  -a INTERSIGHT_API_KEY_ID, --intersight-api-key-id INTERSIGHT_API_KEY_ID
                        The Intersight API key id for HTTP signature scheme.
  -d DIR, --dir DIR     The Directory to use for the Creation of the YAML Configuration Files.
  -dl DEBUG_LEVEL, --debug-level DEBUG_LEVEL
                        The Amount of Debug output to Show: 1. Shows the api request response status code 5. Show URL String + Lower Options 6. Adds Results + Lower Options 7.
                        Adds json payload + Lower Options Note: payload shows as pretty and straight to check for stray object types like Dotmap and numpy
  -f INTERSIGHT_FQDN, --intersight-fqdn INTERSIGHT_FQDN
                        The Directory to use for the Creation of the YAML Configuration Files.
  -i, --ignore-tls      Ignore TLS server-side certificate verification. Default is False.
  -j JSON_FILE, --json-file JSON_FILE
                        The IMM Transition Tool JSON Dump File to Convert to HCL.
  -k INTERSIGHT_SECRET_KEY, --intersight-secret-key INTERSIGHT_SECRET_KEY
                        Name of the file containing The Intersight secret key or contents of the secret key in environment.
  -l, --load-config     Skip Wizard and Just Load Configuration Files.
  -t DEPLOYMENT_METHOD, --deployment-method DEPLOYMENT_METHOD
                        Deployment Method values are: 1. Python 2. Terraform
  -v, --api-key-v3      Flag for API Key Version 3.
```

## Terraform Plan and Apply

After the Script has generated the Repository and downloaded the resources from the Easy IMM Repository, the data will need to be pushed to Intersight using Terraform Cloud or a local instance of Terraform.

## Synopsis

The purpose of this Python Tool is to deploy Policies/Pools/Profiles to Intersight using Infastructure as Code with `Python` or `Terraform`.  

When used in conjunction with Terraform; the goal of this module is to build the initial YAML Configuration files to:

1. Familiarize users with the layout of the YAML Configuration files used in conjunction with the `easy-imm` repository.  
2. Once a user feels conformatable with the auto generated files, Transition towards writing managing the code with `Git` and `Terraform`.
3. Lastly, build confidence to write your own code as well.  

The wizard will show after each section what the YAML Data being generated.  In the Heading for each section it will provide instructions and point you to the directly and file where the code will be created.  Be sure to read the information as it is meant to provide guidance through the wizard.

### Use Cases

- Create Pools
- Create Policies
- Create UCS Domain Profiles and attach Fabric Interconnects to the profiles
- Create Service Profiles and Templates

### Intersight Pools

This set of modules support creating the following Pool Types:

- IP Pools
- IQN Pools
- MAC Pools
- Resource Pools
- UUID Pools
- WWNN Pools
- WWPN Pools

### Intersight Policies

This set of modules support creating the following Policy Types:

- Adapter Configuration
- BIOS
- Boot Order
- Certificate Management
- Device Connector
- Drive Security
- Ethernet Adapter
- Ethernet Network
- Ethernet Network Control
- Ethernet Network Group
- Ethernet QoS
- FC Zone
- Fibre Channel Adapter
- Fibre Channel Network
- Fibre Channel QoS
- Firmware
- IMC Access
- Flow Control
- IPMI Over LAN
- iSCSI Adapter
- iSCSI Boot
- iSCSI Static Target
- LAN Connectivity
- LDAP
- Link Aggregation
- Link Control
- Local User
- Multicast
- Network Connectivity
- NTP
- Persistent Memory
- Port
- Power
- SAN Connectivity
- SD Card
- Serial over LAN
- SMTP
- SNMP
- SSH
- Storage
- Switch Control
- Syslog
- System QoS
- Thermal
- Virtual KVM
- Virtual Media
- VLAN
- VSAN

### Intersight Profiles and Templates

This set of modules support creating the following Profile Types:

- UCS Chassis Profile(s)
- UCS Domain Profile(s)
- UCS Server Profile(s)
- UCS Server Template(s) - Important Note: The Script can use the Template as a policy placeholder or to create profiles from the template.

To sum this up... the goal is to deploy the infrastructure using Infrastructure as Code (YAML Configuration Files) to manage Cisco Intersight.

## Wizard for Terraform use Cases

If using the script with Terraform, there are features that require `1.3.0` or greater, Preferrably `>1.3.0`.

- Download Here [terraform](https://www.terraform.io/downloads.html) 
- For Windows Make sure it is in a Directory that is in the system path.

### Terraform Modules and Providers

This script will utilize the Intersight Terraform Provider and supports the easy-imm modules built off of the Intersight Provider.

- [Intersight Provider](https://registry.terraform.io/providers/CiscoDevNet/intersight/latest)
- [easy-imm](https://github.com/terraform-cisco-modules/easy-imm)

## [Cloud Posse `tfenv`](https://github.com/cloudposse/tfenv)

Command line utility to transform environment variables for use with Terraform. (e.g. HOSTNAME → TF_VAR_hostname)

Recently I adopted the `tfenv` runner to standardize environment variables with multiple orchestration tools.  tfenv makes it so you don't need to add TF_VAR_ to the variables when you add them to the environment.  But it doesn't work for windows would be the caveat.

In the export examples below, for the Linux Example, the 'TF_VAR_' is excluded because Cloud Posse tfenv is used to insert it during the run.

### Make sure you have already installed go - Add go/bin to PATH

```bash
GOPATH="$HOME/go"
PATH="$GOPATH/bin:$PATH"
```

## [go](https://go.dev/doc/install)

```bash
go install github.com/cloudposse/tfenv@latest
```

### Aliases for `.bashrc`

Additionally to Save time on typing commands I use the following aliases by editing the `.bashrc` for my environment.

```bash
alias tfa='tfenv terraform apply main.plan'
alias tfap='tfenv terraform apply -parallelism=1 main.plan'
alias tfd='terraform destroy'
alias tff='terraform fmt'
alias tfi='terraform init'
alias tfp='tfenv terraform plan -out=main.plan'
alias tfu='terraform init -upgrade'
alias tfv='terraform validate'
```

## Environment Variables

Note that all the variables in `variables.tf` are marked as sensitive.  Meaning these are variables that shouldn't be exposed due to the sensitive nature of them.

Take note of the `locals.tf` that currently has all the sensitive variables mapped:

* `certificate_management`
* `drive_security`
* `firmware`
* `ipmi_over_lan`
* `iscsi_boot`
* `ldap`
* `local_user`
* `persistent_memory`
* `snmp`
* `virtual_media`

The Reason to add these variables as maps of string is to allow the flexibility to add or remove iterations of these sensitive variables as needed.  Sensitive Variables cannot be iterated with a `for_each` loop.  Thus instead of adding these variables to the YAML schema, directly, they are added to these seperate maps to allow lookup of the variable index.

In example, if you needed to add 100 iterations of the `certificate_management` variables you can do that, and simply reference the index in the map of the iteration that will consume that instance.

### Terraform Cloud/Enterprise - Workspace Variables

- Add variable `intersight_api_key_id` with the value of <your-api-key>
- Add variable `intersight_secret_key` with the value of <your-secret-file-content>

#### Add Other Variables as discussed below based on use cases

## IMPORTANT:

ALL EXAMPLES BELOW ASSUME USING `tfenv` in LINUX

#### Linux

```bash
export intersight_api_key_id="<your-api-key>"
export intersight_secret_key="<secret-key-file-location>"
```

#### Windows

```powershell
$env:TF_VAR_intersight_api_key_id="<your-api-key>"
$env:TF_VAR_intersight_secret_key="<secret-key-file-location>"
```

## Sensitive Variables for the Policies Module:

Take note of the `locals.tf` that currently has all the sensitive variables mapped.

This is the default sensitive variable mappings.  You can add or remove to these according to the needs of your environment.

The important point is that if you need more than is added by default you can expand the locals.tf and variables.tf to accomodate your environment.

## To Assign any of these values for consumption you can define them as discussed below.

### Certificate Management

* `cert_mgmt_certificate`: Options are by default 1-5 for Up to 5 Certificates.  Variable Should Point to the File Location of the PEM Certificate or be the value of the PEM certificate.
* `cert_mgmt_private_key`: Options are by default 1-5 for Up to 5 Private Keys.  Variable Should Point to the File Location of the PEM Private Key or be the value of the PEM Private Key.

#### Linux

```bash
export cert_mgmt_certificate_1='<cert_mgmt_certificate_file_location>'
```
```bash
export cert_mgmt_private_key_1='<cert_mgmt_private_key_file_location>'
```

#### Windows

```powershell
$env:TF_VAR_cert_mgmt_certificate_1='<cert_mgmt_certificate_file_location>'
```
```powershell
$env:TF_VAR_cert_mgmt_private_key_1='<cert_mgmt_private_key_file_location>'
```

### Drive Security - KMIP Sensitive Variables

* `drive_security_password`: If Authentication is supported/used by the KMIP Server, This is the User Password to Configure.
* `drive_security_server_ca_certificate`: KMIP Server CA Certificate Contents.

#### Linux

```bash
export drive_security_password='<drive_security_password>'
```
```bash
export drive_security_server_ca_certificate='<drive_security_server_ca_certificate_file_location>'
```

#### Windows

```powershell
$env:TF_VAR_drive_security_password='<drive_security_password>'
```
```powershell
$env:TF_VAR_drive_security_server_ca_certificate='<drive_security_server_ca_certificate_file_location>'
```

### Firmware - CCO  Credentials

* `cco_user`: If Configuring Firmware Policies, the CCO User for Firmware Downloads.
* `cco_password`: If Configuring Firmware Policies, the CCO Password for Firmware Downloads.

#### Linux

```bash
export cco_user='<cco_user>'
```
```bash
export cco_password='<cco_password>'
```

#### Windows

```powershell
$env:TF_VAR_cco_user='<cco_user>'
```
```powershell
$env:TF_VAR_cco_password='<cco_password>'
```
