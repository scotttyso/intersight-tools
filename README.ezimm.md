## EZIMM Synopsis

The purpose of `ezimm.py` is to manage Server Environments in Intersight using Infastructure as Code with `Python`.  It provides a number a wizards to build YAML data models and push these definitions to the Intersight API.  This may also include 3rd party calls for integrations with Hypervisors and Storage partners.

### Running the Wizard(s)

It is recommend to add the following secure variables to your environment before running the script at a minimum.

#### Linux

```bash
## Bash Intersight Variables
export intersight_api_key_id="<your_intersight_api_key>"
export intersight_secret_key="~/Downloads/SecretKey.txt"
```

#### Windows

```powershell
## Powershell Intersight Variables
$env:intersight_api_key_id="<your_intersight_api_key>"
$env:intersight_secret_key="$HOME\Downloads\SecretKey.txt"
```

Note: The above example is based on the key being in your Downloads folder.  Set according to your environment.


There may be additional variables to define in the environment based on the deployment type, but the API key and Secret File are the bare minimum requirements.

## Wizard Options

  * Convert:    Convert a configuration export from Intersight Transition Tool to the YAML data model for the easy-imm repository.
  * Deploy:     Deploy pools, policies, profiles, and templates defined in YAML using the JSON schema with the easy-imm repository.
  * Domain:     Deploy a domain via cloning an existing profile or creating net new.
  * Individual: Select individual pools, policies, profiles, or templates to build.
  * OSInstall:  Install an Operating System with either new or existing profiles.
  * Server:     Build server profiles/templates for Intersight Managed Servers.

  The wizard selection can be chosen through a prompt or passed as a variable with `-dt {option above}` as an example.

### Convert: Brownfield Migration with [Cisco Intersight Transition Tool](https://www.cisco.com/c/en/us/td/docs/unified_computing/Intersight/IMM-Transition-Tool/User-Guide-4-0/b_imm_transition_tool_user_guide_4_0.html)

Convert a migrated configuration from UCS Central or UCS Manager using the Cisco Intersight Managed Mode Transition Tool to work with the easy-imm repository.

Example:

```bash
./ezimm.py -d {export-destination-directory} -dt Convert -j {json_export_file_from_imm_tool.json}
```

Once the configuration has been converted to the YAML Data model it can be managed with [easy-imm](https://github.com/terraform-cisco-modules/easy-imm) or the `Deploy` option described below.

### Deploy: Use Cases

  - Create/Manage Pools
  - Create/Manage Policies
  - Create/Manage UCS Domain Profiles
  - Create/Manage Service Profiles and Templates

#### Deploy: Push configuration defined using [easy-imm](https://github.com/terraform-cisco-modules/easy-imm) data model

The easy-imm repository provides a YAML data model to manage Intersight configuration (pools/policies/profiles/templates) as Infrasctructure as Code (IaC).

The easy-imm repo includes the ability to push this data model using Terraform.  The `Deploy` option allows to manage/push the data model to Intersight using this Python library.  Following are reasons that I added this as an option.

  * API Optimization: Terraform makes an individual API call for each object it manages.  Intersight supports API optimization with Bulk API calls.  This libary uses the Bulk API's to reduce the number of API calls speeding up the code deployments.
  * Server Profile/Template challenges:  Intersight uses the bulk/Merger api for adding the server profile template to server profiles.  This is transient, the record does not remain after the initial API call.  Because Terraform wants to be the source of truth and the record is transient, there is no good way to support template updates with Terraform.
  * Order Creation: Terraform creates 10 threads of API calls when communicating to Intersight.  Because of this multi-threading it has been observed that server profiles get created in random orders.  Many customers that want to gaurantee that identities are assigned in the order they have defined have complained about this.  This library is written to address the order of creation.

What the library doesn't address is deleting objects.  Because the library doesn't maintain a state file in the same way Terraform does, this library does not delete objects created in Intersight.  That was a decision I made as my intention is not to duplicate what Terraform does.  If full scrum management is desired, it would be recommended to use the Terraform modules in the easy-imm repository, instead of this Python library.

#### Example for Deploy option:

```bash
./ezimm.py -d {easy-imm-directory} -dt Deploy -l
```

The `-l` option will load the YAML from the directory without prompting you to load/import the data.

### Domain/Server: Use Cases

  - Create/Manage Domain Profiles via a wizard based setup
  - Create/Manage Server Profiles/Templates via a wizard based setup

#### Domain/Server: Build/Push configuration defined using [easy-imm](https://github.com/terraform-cisco-modules/easy-imm) data model

The easy-imm repository provides a YAML data model to manage Intersight configuration (pools/policies/profiles/templates) as Infrasctructure as Code (IaC).

The `Domain` and `Server` options allow you to walk thru a wizard based configuration to build the YAML files through a wizard based approach.  If Python is chosen to push the configuration to Intersight, it will deploy the configuration when complete just like the `Deploy` option.

#### Examples for Domain/Server options:

```bash
./ezimm.py -d {easy-imm-directory} -dt Domain
```

```bash
./ezimm.py -d {easy-imm-directory} -dt Server
```

## Wizard Help Menu

```bash
./ezimm.py -h

usage: ezimm.py [-h] [-a INTERSIGHT_API_KEY_ID] [-ccp CCO_PASSWORD] [-ccu CCO_USER] [-d DIR] [-dl DEBUG_LEVEL] [-dm DEPLOYMENT_METHOD] [-dt DEPLOYMENT_TYPE]
                [-f INTERSIGHT_FQDN] [-i] [-j JSON_FILE] [-k INTERSIGHT_SECRET_KEY] [-l] [-v]

Intersight Easy IMM Deployment Module

options:
  -h, --help            show this help message and exit
  -a INTERSIGHT_API_KEY_ID, --intersight-api-key-id INTERSIGHT_API_KEY_ID
                        The Intersight API key id for HTTP signature scheme.
  -ccp CCO_PASSWORD, --cco-password CCO_PASSWORD
                        Cisco Connection Online Password to Authorize Firmware Downloads.
  -ccu CCO_USER, --cco-user CCO_USER
                        Cisco Connection Online Username to Authorize Firmware Downloads.
  -d DIR, --dir DIR     The Directory to use for the Creation of the YAML Configuration Files.
  -dl DEBUG_LEVEL, --debug-level DEBUG_LEVEL
                        Used for troubleshooting. The Amount of Debug output to Show: 1. Shows the api request response status code 5. Show URL String + Lower
                        Options 6. Adds Results + Lower Options 7. Adds json payload + Lower Options Note: payload shows as pretty and straight to check for
                        stray object types like Dotmap and numpy
  -dm DEPLOYMENT_METHOD, --deployment-method DEPLOYMENT_METHOD
                        Deployment Method values are: 1. Python 2. Terraform
  -dt DEPLOYMENT_TYPE, --deployment-type DEPLOYMENT_TYPE
                        Deployment Type values are: 1. Domain 2. FIAttached 3. Individual 4. OSInstall 5. Standalone 6. Deploy 7. Exit
  -f INTERSIGHT_FQDN, --intersight-fqdn INTERSIGHT_FQDN
                        The Directory to use for the Creation of the YAML Configuration Files.
  -i, --ignore-tls      Ignore TLS server-side certificate verification. Default is False.
  -j JSON_FILE, --json-file JSON_FILE
                        The IMM Transition Tool JSON Dump File to Convert to HCL.
  -k INTERSIGHT_SECRET_KEY, --intersight-secret-key INTERSIGHT_SECRET_KEY
                        Name of the file containing The Intersight secret key or contents of the secret key in environment.
  -l, --load-config     Skip Wizard and Just Load Configuration Files.
  -v, --api-key-v3      Flag for API Key Version 3.
```

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
