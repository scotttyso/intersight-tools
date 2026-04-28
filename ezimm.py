#!/usr/bin/env python3
"""EZIMM - 
Use This Wizard to Create Terraform HCL configuration from Question and Answer or the IMM Transition Tool.
It uses argparse to take in the following CLI arguments:
        Base arguments:
            -a   or --intersight-api-key-id: The Intersight API key id for HTTP signature scheme.
            -d   or --dir:                   Base directory used for YAML configuration files.
            -dl  or --debug-level:           Debug output level.
            -f   or --intersight-fqdn:       Intersight hostname. Default is intersight.com.
            -i   or --ignore-tls:            Ignore TLS server-side certificate verification.
            -j   or --json-file:             IMM Transition Tool JSON dump file to convert to HCL.
            -k   or --intersight-secret-key: Intersight secret key file path or key content.
            -l   or --load-config:           Skip wizard and load existing configuration files.
            -ni  or --non-interactive:       Run in non-interactive mode with defaults.
            -rc  or --repository-check-skip: Skip repository URL checks for OS install.
            -y   or --yaml-file:             Input YAML file.

        EZIMM-sensitive-variable arguments:
            -alp  or --azure-stack-lcm-password
            -ccp  or --cco-password
            -ccu  or --cco-user
            -dap  or --domain-administrator-password
            -ilp  or --local-user-password-1
            -ilp2 or --local-user-password-2
            -imm  or --imm-transition-password
            -isa  or --snmp-auth-password-1
            -isp  or --snmp-privacy-password-1
            -lap  or --local-administrator-password
            -np   or --netapp-password
            -nsa  or --netapp-snmp-auth
            -nsp  or --netapp-snmp-priv
            -nxp  or --nexus-password
            -p    or --pure-storage-password
            -psa  or --pure-storage-snmp-auth
            -psp  or --pure-storage-snmp-priv
            -pxp  or --proxy-password
            -vep  or --vmware-esxi-password
            -vvp  or --vmware-vcenter-password

        EZIMM-specific arguments:
            -check or --check:               Run in check mode.  The Model definitions will only be compared to the Intersight API.
            -dm    or --deployment-method:   Deployment method values: Python or Terraform.
            -dt    or --deployment-type:     Deployment type values: Convert, Deploy, Domain,
                                                                             Individual, OSInstall, Server, StateUpdate, Exit.
"""
#=============================================================================
# Source Modules
#=============================================================================
import os
import sys
from pathlib import Path
from typing import Any, Tuple


def prRed(message: str) -> None:
    """Print a red terminal message."""
    print("\033[91m {}\033[00m".format(message))


SCRIPT_PATH = Path(__file__).resolve().parent
CLASSES_PATH = SCRIPT_PATH / 'classes'
if str(CLASSES_PATH) not in sys.path:
    sys.path.insert(0, str(CLASSES_PATH))


def _load_dependencies() -> Tuple[Any, ...]:
    """Import runtime dependencies and return them as module-level bindings."""
    try:
        import argparse
        import importlib
        import json
        import re

        import requests
        import urllib3
        from copy import deepcopy
        from dotmap import DotMap

        from classes import build, ezfunctions, isight, pcolor, policies, questions, tf, terraform, transition, validating
    except ImportError as error:
        prRed(f'EZIMM - !!! ERROR !!!\n{error.__class__.__name__}')
        prRed(f" Module {error.name} is required to run this script")
        prRed(f" Install the module using the following: `pip install {error.name}`")
        raise SystemExit(1) from error

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return argparse, json, re, requests, deepcopy, DotMap, build, ezfunctions, isight, pcolor, policies, questions, tf, terraform, transition, validating


(
    argparse,
    json,
    re,
    requests,
    deepcopy,
    DotMap,
    build,
    ezfunctions,
    isight,
    pcolor,
    policies,
    questions,
    tf,
    terraform,
    transition,
    validating,
) = _load_dependencies()
#=============================================================================
# Function: Parse Arguments
#=============================================================================
def cli_arguments() -> Any:
    """Parse CLI arguments for EZIMM and return them as a DotMap."""
    parser = argparse.ArgumentParser(description ='Intersight Easy IMM Deployment Module')
    parser = ezfunctions.base_arguments(parser)
    parser = ezfunctions.base_arguments_ezimm_sensitive_variables(parser)
    parser.add_argument(
        '-check', '--check', action='store_true',
        help='Boolean flag to enable check mode')
    parser.add_argument(
        '-dm', '--deployment-method', default ='',
        help = 'Deployment Method values are: \
            1.  Python \
            2.  Terraform')
    parser.add_argument(
        '-dt', '--deployment-type', default ='',
        help = 'Deployment Type values are: \
            1.  Convert \
            2.  Deploy \
            3.  Domain \
            4.  Individual \
            5.  OSInstall \
            6.  Server \
            7.  StateUpdate \
            8.  Exit')
    return DotMap(args=parser.parse_args())


def _validate_terraform_target(terraform_target: str) -> None:
    """Validate Terraform target as IPv4, IPv6, or DNS name."""
    if re.search(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", terraform_target):
        validating.ip_address('Terraform Target', terraform_target)
    elif ':' in terraform_target:
        validating.ip_address('Terraform Target', terraform_target)
    else:
        validating.dns_name('Terraform Target', terraform_target)


def _prompt_terraform_target(kwargs: Any) -> Any:
    """Prompt for Terraform target type and hostname details."""
    polVars = DotMap()
    kwargs.multi_select = False
    kwargs.jdata = DotMap()
    kwargs.jdata.default = 'Terraform Cloud'
    kwargs.jdata.description = 'Select the Terraform Target.'
    kwargs.jdata.enum = ['Terraform Cloud', 'Terraform Enterprise']
    kwargs.jdata.varType = 'Target'
    terraform_target = ezfunctions.variablesFromAPI(kwargs)

    if terraform_target[0] == 'Terraform Enterprise':
        kwargs.jdata = DotMap()
        kwargs.jdata.default = 'app.terraform.io'
        kwargs.jdata.description = 'Hostname of the Terraform Enterprise Instance'
        kwargs.jdata.pattern = '^[a-zA-Z0-9\\-\\.\\:]+$'
        kwargs.jdata.minimum = 1
        kwargs.jdata.maximum = 90
        kwargs.jdata.varInput = 'What is the Hostname of the TFE Instance?'
        kwargs.jdata.varName = 'Terraform Target Name'
        polVars.tfc_host = ezfunctions.varStringLoop(kwargs)
        _validate_terraform_target(polVars.tfc_host)
    else:
        polVars.tfc_host = 'app.terraform.io'

    return polVars


def _load_terraform_cloud_context(polVars: Any, kwargs: Any) -> Any:
    """Populate Terraform Cloud context in polVars and cache values in env vars."""
    terraform_cloud = tf.terraform_cloud()
    polVars.terraform_cloud_token = terraform_cloud.terraform_token()

    if os.environ.get('tfc_organization') is None:
        polVars.tfc_organization = terraform_cloud.tfc_organization(polVars, kwargs)
        os.environ['tfc_organization'] = polVars.tfc_organization
    else:
        polVars.tfc_organization = os.environ.get('tfc_organization')

    if os.environ.get('tfc_vcs_provider') is None:
        tfc_vcs_provider, polVars.tfc_oath_token = terraform_cloud.tfc_vcs_providers(polVars, kwargs)
        polVars.tfc_vcs_provider = tfc_vcs_provider
        os.environ['tfc_vcs_provider'] = tfc_vcs_provider
        os.environ['tfc_oath_token'] = polVars.tfc_oath_token
    else:
        polVars.tfc_vcs_provider = os.environ.get('tfc_vcs_provider')
        polVars.tfc_oath_token = os.environ.get('tfc_oath_token')

    if os.environ.get('vcsBaseRepo') is None:
        polVars.vcsBaseRepo = terraform_cloud.tfc_vcs_repository(polVars, kwargs)
        os.environ['vcsBaseRepo'] = polVars.vcsBaseRepo
    else:
        polVars.vcsBaseRepo = os.environ.get('vcsBaseRepo')

    polVars.agentPoolId = ''
    polVars.allowDestroyPlan = False
    polVars.executionMode = 'remote'
    polVars.queueAllRuns = False
    polVars.speculativeEnabled = True
    polVars.triggerPrefixes = []
    return polVars


def _terraform_versions_from_github() -> list[str]:
    """Fetch available Terraform versions from GitHub tags page."""
    terraform_versions = []
    response = requests.get('https://github.com/hashicorp/terraform/tags', stream=True)
    for line in response.iter_lines():
        line_text = line.decode('utf-8')
        if re.search(r'/releases/tag/v(\d+\.\d+\.\d+)\"', line_text):
            terraform_versions.append(re.search('/releases/tag/v(\d+\.\d+\.\d+)', line_text).group(1))

    deprecated_versions = ['1.1.0", "1.1.1']
    terraform_versions = sorted(
        {version for version in terraform_versions if version not in deprecated_versions},
        reverse=True,
    )
    return terraform_versions


def _prompt_terraform_version(kwargs: Any, terraform_versions: list[str]) -> Any:
    """Prompt for the Terraform version to use for workspace creation."""
    kwargs.jdata = DotMap()
    kwargs.jdata.default = terraform_versions[0]
    kwargs.jdata.description = 'Terraform Version for Workspaces:'
    kwargs.jdata.dontsort = True
    kwargs.jdata.enum = terraform_versions
    kwargs.jdata.varType = 'Terraform Version'
    return ezfunctions.variablesFromAPI(kwargs)


def _prompt_workspace_name(org: str, kwargs: Any) -> str:
    """Prompt for a Terraform workspace name for the given organization."""
    kwargs.jdata = DotMap()
    kwargs.jdata.default = f'{org}'
    kwargs.jdata.description = f'Name of the {org} Workspace to Create in Terraform Cloud'
    kwargs.jdata.pattern = '^[a-zA-Z0-9\\-\\_]+$'
    kwargs.jdata.minimum = 1
    kwargs.jdata.maximum = 90
    kwargs.jdata.varInput = 'Terraform Cloud Workspace Name.'
    kwargs.jdata.varName = 'Workspace Name'
    return ezfunctions.varStringLoop(kwargs)


def _add_workspace_credentials(polVars: Any, kwargs: Any, op_system: str, terraform_cloud: Any) -> Any:
    """Attach API key and secret variables to a Terraform workspace."""
    credential_vars = ['apikey.Intersight API Key', 'secretkey.Intersight Secret Key']

    for credential_var in credential_vars:
        var_id, description = credential_var.split('.')
        pcolor.Green(f'* Adding {description} to {polVars.workspaceName}')
        kwargs['Variable'] = var_id
        if 'secret' in credential_var:
            kwargs['Multi_Line_Input'] = True
        polVars.description = description
        polVars['varId'] = var_id
        polVars['varKey'] = var_id
        kwargs = ezfunctions.sensitive_var_value(kwargs)
        polVars['varValue'] = kwargs['var_value']
        polVars['Sensitive'] = True
        if 'secret' in credential_var and op_system == 'Windows' and os.path.isfile(polVars['varValue']):
            with open(polVars['varValue']) as secret_handle:
                polVars['varValue'] = secret_handle.read().replace('\n', '\\n')
        terraform_cloud.tfcVariables(polVars, kwargs)
        kwargs['Multi_Line_Input'] = False

    return kwargs


def _push_tfc_sensitive_var(
    var_value: str,
    json_data: Any,
    polVars: Any,
    terraform_cloud: Any,
    use_kwargs_expand: bool = False,
) -> Any:
    """Transform and push a sensitive variable to Terraform Cloud."""
    if use_kwargs_expand:
        updated_vars = ezfunctions.tfc_sensitive_variables(var_value, json_data, **polVars)
    else:
        updated_vars = ezfunctions.tfc_sensitive_variables(var_value, json_data, polVars)
    terraform_cloud.tfcVariables(**updated_vars)
    return updated_vars


def _process_policy_sensitive_vars(
    policy_name: str,
    variable_suffix: str,
    policy_items: list[Any],
    json_data: Any,
    polVars: Any,
    terraform_cloud: Any,
) -> Any:
    """Process policy-specific sensitive values and push them to Terraform Cloud."""
    if not policy_items:
        return polVars

    if policy_name == 'persistent_memory':
        return _push_tfc_sensitive_var(
            variable_suffix,
            json_data,
            polVars,
            terraform_cloud,
            use_kwargs_expand=True,
        )

    for item in policy_items:
        if policy_name == 'ipmi_over_lan' and item.get('enabled'):
            polVars = _push_tfc_sensitive_var(variable_suffix, json_data, polVars, terraform_cloud)

        elif policy_name == 'iscsi_boot' and item.get('authentication'):
            if re.search('chap', item['authentication']):
                polVars = _push_tfc_sensitive_var(variable_suffix, json_data, polVars, terraform_cloud)

        elif policy_name == 'ldap' and item.get('binding_parameters'):
            bind_parameters = item['binding_parameters']
            if bind_parameters.get('bind_method') == 'ConfiguredCredentials':
                polVars = _push_tfc_sensitive_var(variable_suffix, json_data, polVars, terraform_cloud)

        elif policy_name == 'local_user':
            polVars['enforce_strong_password'] = item.get('enforce_strong_password', True)
            for user in item['users']:
                polVars = _push_tfc_sensitive_var(
                    f'{variable_suffix}_{user["password"]}',
                    json_data,
                    polVars,
                    terraform_cloud,
                )

        elif policy_name == 'snmp':
            if item.get('access_community_string'):
                access_community = item['access_community_string']
                polVars = _push_tfc_sensitive_var(
                    f'access_community_string_{access_community}',
                    json_data,
                    polVars,
                    terraform_cloud,
                )

            if item.get('snmp_users'):
                for snmp_user in item['snmp_users']:
                    polVars = _push_tfc_sensitive_var(
                        f'snmp_auth_password_{snmp_user["auth_password"]}',
                        json_data,
                        polVars,
                        terraform_cloud,
                    )
                    if snmp_user.get('privacy_password'):
                        polVars = _push_tfc_sensitive_var(
                            f'snmp_privacy_password_{snmp_user["privacy_password"]}',
                            json_data,
                            polVars,
                            terraform_cloud,
                        )

            if item.get('snmp_traps'):
                for snmp_trap in item['snmp_traps']:
                    if snmp_trap.get('community_string'):
                        polVars = _push_tfc_sensitive_var(
                            f'snmp_trap_community_{snmp_trap["community_string"]}',
                            json_data,
                            polVars,
                            terraform_cloud,
                        )

            if item.get('trap_community_string'):
                polVars = _push_tfc_sensitive_var('trap_community_string', json_data, polVars, terraform_cloud)

        elif policy_name == 'virtual_media' and item.get('add_virtual_media'):
            for media_entry in item['add_virtual_media']:
                if media_entry.get('password'):
                    polVars = _push_tfc_sensitive_var(
                        f'{variable_suffix}_{media_entry["password"]}',
                        json_data,
                        polVars,
                        terraform_cloud,
                    )

    return polVars

#=============================================================================
# Function: Create Terraform Workspaces
#=============================================================================
def create_terraform_workspaces(orgs: list[str], kwargs: Any) -> Any:
    """Create and configure Terraform workspaces for selected organizations."""
    json_data = kwargs.jsonData
    op_system = kwargs.opSystem
    org = kwargs.org
    polVars = DotMap()
    terraform_cloud = tf.terraform_cloud()
    kwargs.jdata = DotMap()
    kwargs.jdata.default = True
    kwargs.jdata.description = f'Terraform Cloud Workspaces'
    kwargs.jdata.varInput = f'Do you want to Proceed with creating Workspaces in Terraform Cloud or Enterprise?'
    kwargs.jdata.varName = 'Terraform Cloud Workspaces'
    run_tfcb = ezfunctions.varBoolLoop(kwargs)
    if run_tfcb is True:
        polVars = _prompt_terraform_target(kwargs)
        polVars = _load_terraform_cloud_context(polVars, kwargs)
        polVars.terraformVersion = _prompt_terraform_version(kwargs, _terraform_versions_from_github())
        #=====================================================================
        # Begin Creating Workspaces
        #=====================================================================
        for org in orgs:
            kwargs.org = org
            polVars.workspaceName = _prompt_workspace_name(org, kwargs)
            polVars.workspace_id = terraform_cloud.tfcWorkspace(polVars, kwargs)
            kwargs = _add_workspace_credentials(polVars, kwargs, op_system, terraform_cloud)
            sensitive_policy_vars = [
                'ipmi_over_lan.ipmi_key',
                'iscsi_boot.iscsi_boot_password',
                'ldap.binding_parameters_password',
                'local_user.local_user_password',
                'persistent_memory.secure_passphrase',
                'snmp.sensitive_vars',
                'virtual_media.vmedia_password'
            ]
            for var in sensitive_policy_vars:
                policy_name, variable_suffix = var.split('.')
                kwargs = ezfunctions.policies_parse('policies', policy_name, policy_name)
                policy_items = deepcopy(kwargs['policies'][policy_name])
                polVars = _process_policy_sensitive_vars(
                    policy_name,
                    variable_suffix,
                    policy_items,
                    json_data,
                    polVars,
                    terraform_cloud,
                )
    else:
        pcolor.Cyan(f'\n-------------------------------------------------------------------------------------------\n')
        pcolor.Cyan(f'  Skipping Step to Create Terraform Cloud Workspaces.')
        pcolor.Cyan(f'  Moving to last step to Confirm the Intersight Organization Exists.')
        pcolor.Cyan(f'\n-------------------------------------------------------------------------------------------\n')
    # Configure the provider.tf and variables.auto.tfvars
    name_prefix = 'dummy'
    policy_type = 'policies'
    policies.policies(name_prefix, org, policy_type).variables(kwargs)
    # Return kwargs
    return kwargs
     
#=============================================================================
# Function: Intersight Transition Tool Configuration Conversion
#=============================================================================
def _prompt_existing_json_path(kwargs: Any, json_file: str) -> str:
    """Prompt until a valid JSON file path is provided."""
    while not os.path.isfile(json_file):
        pcolor.Yellow(f'\n{"-"*108}\n\n  !!ERROR!!\n  Did not find the file `{json_file}`.')
        pcolor.Yellow('  Please Validate that you have specified the correct file and path.')
        kwargs.jdata = kwargs.ezwizard.setup.properties.json_file
        json_file = ezfunctions.variable_prompt(kwargs)
    return json_file


def _validate_transition_device_type(json_file: str, device_type: str) -> None:
    """Validate that transition JSON device_type is supported."""
    if device_type == 'intersight':
        return

    pcolor.Red(f'\n{"-"*108}\n\n  !!ERROR!!\n  The File `{json_file}` device_type is `{device_type}`.')
    pcolor.Red(
        f'  This file is either the UCSM Configuration converted from XML to JSON or invalid.'
        f'  The device_type is found on line 10 of the json configuration file.'
        f'  The Script is looking for the file that has been converted to Intersight Managed Mode.'
        f'  The JSON file should be downloaded at the last step of the IMM Transition tool where the'
        f'  API Key and Secret would be entered to upload to Intersight.'
        f'  Exiting Wizard...  (ezimm.py Line 402)'
    )
    pcolor.Red(f'\n{"-"*108}\n')
    raise SystemExit(1)


def imm_transition(kwargs: Any) -> Any:
    """Run the IMM transition conversion flow and write resulting YAML."""
    #=========================================================================
    # Obtain JSON File
    #=========================================================================
    json_file = kwargs.args.json_file or 'none'
    json_file = _prompt_existing_json_path(kwargs, json_file)

    with open(json_file, 'r', encoding='utf8') as json_handle:
        kwargs.json_data = DotMap(json.load(json_handle))

    device_type = kwargs.json_data.easyucs.metadata[0].device_type
    _validate_transition_device_type(json_file, device_type)

    #=========================================================================
    # Run through the IMM Transition Wizard
    #=========================================================================
    kwargs = transition.intersight('transition').modify_keys_loop(kwargs)
    #=========================================================================
    # Create YAML Files and return kwargs
    #=========================================================================
    build.intersight.create_yaml_files(kwargs)
    return kwargs

#=============================================================================
# Function: Main Menu
#=============================================================================
def _should_run_wizard(deployment_type: str) -> bool:
    """Return whether deployment type requires running the interactive wizard."""
    return bool(re.search('Domain|Individual|OSInstall|Server', deployment_type))


def _apply_shared_org_selection(kwargs: Any) -> Any:
    """Resolve whether to use a shared organization setting in wizard flow."""
    if re.search('Individual', kwargs.deployment_type):
        return kwargs

    if re.search('OSInstall', kwargs.deployment_type) and kwargs.profile_option == 'existing':
        return kwargs

    shared_org = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.shared_org
    if isinstance(shared_org, str):
        kwargs.use_shared_org = True
    else:
        questions.orgs.organization_shared(kwargs)

    return kwargs


def _finalize_menu_setup(kwargs: Any) -> Any:
    """Finalize menu-driven setup selections before build/setup execution."""
    kwargs.main_menu_list = []
    kwargs = questions.orgs.organization(kwargs)

    if not kwargs.get('profile_option') and kwargs.deployment_type == 'OSInstall':
        kwargs.jdata = kwargs.ezwizard.setup.properties.profile_option
        kwargs.profile_option = ezfunctions.variable_prompt(kwargs)
    else:
        kwargs.profile_option = 'new'

    kwargs = _apply_shared_org_selection(kwargs)
    for key, value in kwargs.imm_dict.orgs[kwargs.org].wizard.setup.items():
        kwargs[key] = value
    kwargs = build.intersight('setup').setup(kwargs)
    return kwargs


def _handle_menu_shortcuts(kwargs: Any) -> tuple[bool, Any]:
    """Handle shortcut deployment paths and indicate whether flow is complete."""
    if kwargs.deployment_type == 'Exit':
        return True, kwargs

    if kwargs.deployment_type == 'Convert':
        kwargs = imm_transition(kwargs)
        build.intersight.create_yaml_files(kwargs)
        return True, kwargs

    kwargs = questions.main_menu.previous_configuration(kwargs)
    if kwargs.deployment_type == 'StateUpdate':
        return True, terraform.state('state_update').state_import(kwargs)

    if kwargs.deployment_type == 'Deploy':
        kwargs.orgs = list(kwargs.imm_dict.orgs.keys())
        kwargs = isight.api('organization').organizations(kwargs)
        return True, isight.imm('deployment').define_imm_functions_to_run(kwargs)

    return False, kwargs


def menu(kwargs: Any) -> Any:
    """Drive top-level menu flow and return updated wizard context."""
    #=========================================================================
    # Prompt User for Deployment Type and Loading Configurations
    #=========================================================================
    pcolor.Cyan(f'\n{"-"*108}\n\n  Starting the Easy IMM Wizard!\n\n{"-"*108}\n')
    kwargs = questions.main_menu.deployment_type(kwargs)
    handled, kwargs = _handle_menu_shortcuts(kwargs)
    if handled:
        return kwargs

    kwargs = isight.api('organization').all_organizations(kwargs)
    return _finalize_menu_setup(kwargs)

#=============================================================================
# Function: Wizard
#=============================================================================
def process_wizard(kwargs: Any) -> Any:
    """Execute selected wizard actions and deployment steps."""
    #=========================================================================
    # Process List from Main Menu
    #=========================================================================
    profile_list = ['chassis', 'domain', 'server', 'server_template']
    if kwargs.deployment_type == 'OSInstall':
        kwargs = build.intersight(kwargs.target_platform).operating_system_installation(kwargs)
        return kwargs

    if kwargs.build_type == 'Interactive':
        for p in kwargs.main_menu_list:
            #=================================================================
            # Intersight Pools/Policies/Profiles
            #=================================================================
            if p in kwargs.pool_list or p in kwargs.policy_list or p in profile_list:
                kwargs = build.intersight(p).ezimm(kwargs)

    elif kwargs.build_type == 'Machine' and kwargs.deployment_type == 'Domain':
        if kwargs.discovery:
            kwargs = build.intersight('domain').domain_setup(kwargs)
        kwargs = build.intersight('quick_start').quick_start_domain(kwargs)
    #=========================================================================
    # Create YAML Files
    #=========================================================================
    build.intersight.create_yaml_files(kwargs)
    if len(kwargs.imm_dict.orgs.keys()) > 0:
        kwargs = isight.api('organization').organizations(kwargs)
    if kwargs.deployment_method == 'Terraform':
        #=====================================================================
        # Create Terraform Config and Workspaces
        #=====================================================================
        ezfunctions.merge_easy_imm_repository(kwargs)
        kwargs = ezfunctions.terraform_provider_config(kwargs)
        kwargs = create_terraform_workspaces(kwargs.orgs, kwargs)
    elif re.search('Individual|Server', kwargs.deployment_type):
        kwargs = isight.imm('deployment').define_imm_functions_to_run(kwargs)
    return kwargs

#=============================================================================
# Function: Main Script
#=============================================================================
def main() -> int:
    """Program entrypoint for EZIMM CLI."""
    #=========================================================================
    # Configure Base Module Setup
    #=========================================================================
    kwargs = cli_arguments()
    kwargs = ezfunctions.base_script_settings(kwargs)
    #=========================================================================
    # Prompt User for Main Menu
    #=========================================================================
    kwargs = menu(kwargs)
    if _should_run_wizard(kwargs.deployment_type):
        kwargs = process_wizard(kwargs)
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...\n\n{"-"*108}\n')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
