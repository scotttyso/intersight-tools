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

Note: The above examples are based on the key being in your Downloads folder.  Set according to your environment.


There may be additional variables to define in the environment based on the deployment type, but the API key and Secret File are the bare minimum requirements.

## Wizard Options

  * `Convert`: Convert a configuration export from Intersight Transition Tool to the YAML data model for the easy-imm repository.
  * `Deploy`: Deploy pools, policies, profiles, and templates defined in YAML using the JSON schema with the easy-imm repository.
  * `Domain`: Deploy a domain via cloning an existing profile or creating net new.
  * `Individual`: Select individual pools, policies, profiles, or templates to build.
  * `OSInstall`: Install an Operating System with either new or existing profiles.
  * `Server`: Build server profiles/templates for Intersight Managed Servers.

  The wizard selection can be chosen through a prompt or passed as a variable with `-dt {option above}` as an example.

### Wizard - `Convert`: Brownfield Migration with [Cisco Intersight Transition Tool](https://www.cisco.com/c/en/us/td/docs/unified_computing/Intersight/IMM-Transition-Tool/User-Guide-4-0/b_imm_transition_tool_user_guide_4_0.html)

Convert a migrated configuration from UCS Central or UCS Manager using the Cisco Intersight Managed Mode Transition Tool to work with the easy-imm repository.

Examples:

#### Linux

```bash
./ezimm.py -d {export_destination_directory} -dt Convert -j {json_export_file_from_imm_tool.json}
```

#### Windows

```powershell
.\ezimm.py -d {export_destination_directory} -dt Convert -j {json_export_file_from_imm_tool.json}
```

Once the configuration has been converted to the YAML Data model it can be managed with [easy-imm](https://github.com/terraform-cisco-modules/easy-imm) or the `Deploy` option described below.

### Wizard - `Deploy`: Use Cases

  - Create/Manage Pools
  - Create/Manage Policies
  - Create/Manage UCS Domain Profiles
  - Create/Manage Service Profiles and Templates

#### Wizard - `Deploy`: Push configuration defined using [easy-imm](https://github.com/terraform-cisco-modules/easy-imm) data model

The easy-imm repository provides a YAML data model to manage Intersight configuration (pools/policies/profiles/templates) as Infrasctructure as Code (IaC).

The easy-imm repo includes the ability to push this data model using Terraform.  The `Deploy` option allows to manage/push the data model to Intersight using this Python library.  Following are reasons that I added this as an option.

  * API Optimization: Terraform makes an individual API call for each object it manages.  Intersight supports API optimization with Bulk API calls.  This libary uses the Bulk API's to reduce the number of API calls speeding up the code deployments.
  * Server Profile/Template challenges:  Intersight uses the bulk/Merger api for adding the server profile template to server profiles.  This is transient, the record does not remain after the initial API call.  Because Terraform wants to be the source of truth and the record is transient, there is no good way to support template updates with Terraform.
  * Order Creation: Terraform creates 10 threads of API calls when communicating to Intersight.  Because of this multi-threading it has been observed that server profiles get created in random orders.  Many customers that want to gaurantee that identities are assigned in the order they have defined have complained about this.  This library is written to address the order of creation.

What the library doesn't address is deleting objects.  Because the library doesn't maintain a state file in the same way Terraform does, this library does not delete objects created in Intersight.  That was a decision I made as my intention is not to duplicate what Terraform does.  If full scrum management is desired, it would be recommended to use the Terraform modules in the easy-imm repository, instead of this Python library.

#### Example for `Deploy` option:

#### Linux

```bash
./ezimm.py -d {easy-imm-directory} -dt Deploy -l
```

The `-l` option will load the YAML from the directory without prompting you to load/import the data.

### IMPORTANT NOTES

Take notice of the `ezi.yaml` extension on the files.  This is how the  YAML schema will recognize the files as part of the library.

The Structure of the YAML files is very flexible.  You can have all the YAML Data in a single file or you can have it in multiple individual folders like is shown in the easy-imm repository.

## YAML Schema Notes for auto-completion, Help, and Error Validation:

If you would like to utilize Autocompletion, Help Context, and Error Validation, `(HIGHLY RECOMMENDED)` make sure the files all utilize the `.ezi.yaml` file extension.

And Add the Following to `YAML: Schemas`.  In Visual Studio Code: Settings > Settings > Search for `YAML: Schema`: Click edit in `settings.json`.  In the `yaml.schemas` section:

```bash
"https://raw.githubusercontent.com/terraform-cisco-modules/easy-imm/main/yaml_schema/easy-imm.json": "*.ezi.yaml"
```

Soon the Schema for these YAML Files have been registered with [*SchemaStore*](https://github.com/SchemaStore/schemastore/blob/master/src/api/json/catalog.json) via utilizing this `.ezi.yaml` file extension.  But until that is complete, need to still add to settings.

### Wizard - `Domain/Server`: Use Cases

  - Create/Manage Domain Profiles via a wizard based setup
  - Create/Manage Server Profiles/Templates via a wizard based setup

#### Wizard - `Domain/Server`: Build/Push configuration defined using [easy-imm](https://github.com/terraform-cisco-modules/easy-imm) data model

The easy-imm repository provides a YAML data model to manage Intersight configuration (pools/policies/profiles/templates) as Infrasctructure as Code (IaC).

The `Domain` and `Server` options allow you to walk thru a wizard based configuration to build the YAML files through a wizard based approach.  If Python is chosen to push the configuration to Intersight, it will deploy the configuration when complete just like the `Deploy` option.

#### Examples for `Domain/Server` options:

```bash
./ezimm.py -d {easy-imm-directory} -dt Domain
```

```bash
./ezimm.py -d {easy-imm-directory} -dt Server
```

### Wizard - `OSInstall`: Use Cases

  - Install the Operating System on either existing or new server profiles

#### Wizard - `OSInstall`: Supported Operating Systems

  * CentOS
  * Citrix
  * Microsoft
  * Nutanix
  * Oracle
  * Red Hat
  * Rocky Linux
  * SuSE
  * Ubuntu
  * VMware

Note: This is dependent on what is supported by Intersight OS Install.  As new operating systems or new versions are supported, this will support the new versions.

#### Wizard - `OSInstall`: Prerequisites

  * [Cisco Intersight Transition Tool](https://www.cisco.com/c/en/us/td/docs/unified_computing/Intersight/IMM-Transition-Tool/User-Guide-4-0/b_imm_transition_tool_user_guide_4_0.html).
  * `Server Configuration Utility for OS Version`: Assigned to the Organization that supports the OS Image Version
  * `OS Install Image`: Assigned to the Organization
  * `OS Configuration File`: This can be the default files in Intersight or a custom User uploaded OS Configuration `AutoInstall` file.

Note: We recommend that the SCU and OS Image be hosted on the Intersight Transition Tool.  It supports the ability to auto-sync the files with Intersight in the Software Repository.  See [install instructions](https://www.cisco.com/c/en/us/td/docs/unified_computing/Intersight/IMM-Transition-Tool/User-Guide-4-0/b_imm_transition_tool_user_guide_4_0.html)

The easy-imm repository provides a YAML data model to manage Intersight configuration (pools/policies/profiles/templates) as Infrasctructure as Code (IaC).

The `Domain` and `Server` options allow you to walk thru a wizard based configuration to build the YAML files through a wizard based approach.  If Python is chosen to push the configuration to Intersight, it will deploy the configuration when complete just like the `Deploy` option.

#### Examples for `OSInstall`:

#### Linux

```bash
export root_password="<your_root_password>"
```

#### Windows

```powershell
$env:root_password="<your_root_password>"
```

See examples under `examples/os_install/`

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
                        Deployment Type values are: 1. Convert 2. Deploy 3. Domain 4. Individual 5. OSInstall 6. Server 7. Exit
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

## Sensitive Environment Variables

Note All the variables discussed below are considered sensitive.  Meaning these are variables that shouldn't be exposed due to the sensitive nature of them.

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
