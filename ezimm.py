#!/usr/bin/env python3
"""EZIMM - 
Use This Wizard to Create Terraform HCL configuration from Question and Answer or the IMM Transition Tool.
It uses argparse to take in the following CLI arguments:
    -a   or --intersight-api-key-id: The Intersight API key id for HTTP signature scheme.
    -d   or --dir:                   Base Directory to use for creation of the YAML Configuration Files.
    -dl  or --debug-level:           The Debug Level to Run for Script Output
                                       1. Shows the api request response status code
                                       5. Shows URL String + Lower Options
                                       6. Adds Results + Lower Options
                                       7. Adds json payload + Lower Options
                                     Note: payload shows as pretty and straight to check for stray object types like Dotmap and numpy
    -f  or --intersight-fqdn:        The Intersight hostname for the API endpoint. The default is intersight.com.
    -i  or --ignore-tls:             Ignore TLS server-side certificate verification.  Default is False.
    -j  or --json_file:              IMM Transition JSON export to convert to HCL.
    -l  or --load-config             Flag to Load Previously Saved YAML Configuration Files.
    -k  or --intersight-secret-key:  Name of the file containing The Intersight secret key for the HTTP signature scheme.
    -t  or --deployment-method:      Deployment Method.  Values are: Intersight or Terraform
    -v  or --api-key-v3:             Flag for API Key Version 3.
"""
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import build, ezfunctions, isight, lansan, pcolor, policies, pools, profiles, questions, quick_start, tf, transition, validating
    from copy import deepcopy
    from dotmap import DotMap
    from json_ref_dict import materialize, RefDict
    from pathlib import Path
    import argparse, json, os, logging, platform, re, requests, urllib3, yaml
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=================================================================
# Function: Parse Arguments
#=================================================================
def cli_arguments():
    Parser = argparse.ArgumentParser(description ='Intersight Easy IMM Deployment Module')
    Parser.add_argument(
        '-a', '--intersight-api-key-id', default = os.getenv('intersight_api_key_id'),
        help='The Intersight API key id for HTTP signature scheme.')
    Parser.add_argument( '-ccp', '--cco-password',   help = 'Cisco Connection Online Password to Authorize Firmware Downloads.' )
    Parser.add_argument( '-ccu', '--cco-user',   help = 'Cisco Connection Online Username to Authorize Firmware Downloads.' )
    Parser.add_argument(
        '-d', '--dir', default = 'Intersight',
        help = 'The Directory to use for the Creation of the YAML Configuration Files.')
    Parser.add_argument(
        '-dl', '--debug-level', default = 0,
        help ='Used for troubleshooting.  The Amount of Debug output to Show: '\
            '1. Shows the api request response status code '\
            '5. Show URL String + Lower Options '\
            '6. Adds Results + Lower Options '\
            '7. Adds json payload + Lower Options '\
            'Note: payload shows as pretty and straight to check for stray object types like Dotmap and numpy')
    Parser.add_argument(
        '-dm', '--deployment-method', default ='',
        help = 'Deployment Method values are: \
            1.  Python \
            2.  Terraform')
    Parser.add_argument(
        '-dt', '--deployment-type', default ='',
        help = 'Deployment Type values are: \
            1.  Convert \
            2.  Deploy \
            3.  Domain \
            4.  Individual \
            5.  OSInstall \
            6.  Server \
            7.  Exit')
    Parser.add_argument(
        '-f', '--intersight-fqdn', default ='intersight.com',
        help = 'The Directory to use for the Creation of the YAML Configuration Files.')
    Parser.add_argument(
        '-i', '--ignore-tls', action = 'store_false',
        help = 'Ignore TLS server-side certificate verification.  Default is False.')
    Parser.add_argument(
        '-j', '--json-file', default = None,
        help = 'The IMM Transition Tool JSON Dump File to Convert to HCL.')
    Parser.add_argument(
        '-k', '--intersight-secret-key', default = '~/Downloads/SecretKey.txt',
        help='Name of the file containing The Intersight secret key or contents of the secret key in environment.')
    Parser.add_argument(
        '-l', '--load-config', action = 'store_true',
        help = 'Skip Wizard and Just Load Configuration Files.')
    Parser.add_argument( '-v', '--api-key-v3', action = 'store_true', help = 'Flag for API Key Version 3.' )
    kwargs = DotMap()
    kwargs.args = Parser.parse_args()
    return kwargs

#=================================================================
# Function: Create Terraform Workspaces
#=================================================================
def create_terraform_workspaces(orgs, kwargs):
    jsonData = kwargs.jsonData
    opSystem = kwargs.opSystem
    org = kwargs.org
    tfcb_config = []
    polVars = DotMap()
    kwargs.jdata = DotMap()
    kwargs.jdata.default     = True
    kwargs.jdata.description = f'Terraform Cloud Workspaces'
    kwargs.jdata.varInput    = f'Do you want to Proceed with creating Workspaces in Terraform Cloud or Enterprise?'
    kwargs.jdata.varName     = 'Terraform Cloud Workspaces'
    runTFCB = ezfunctions.varBoolLoop(kwargs)
    if runTFCB == True:
        polVars = {}
        kwargs.multi_select = False
        kwargs.jdata = DotMap()
        kwargs.jdata.default     = 'Terraform Cloud'
        kwargs.jdata.description = 'Select the Terraform Target.'
        kwargs.jdata.enum        = ['Terraform Cloud', 'Terraform Enterprise']
        kwargs.jdata.varType     = 'Target'
        terraform_target = ezfunctions.variablesFromAPI(kwargs)

        if terraform_target[0] == 'Terraform Enterprise':
            kwargs.jdata = DotMap()
            kwargs.jdata.default     = f'app.terraform.io'
            kwargs.jdata.description = f'Hostname of the Terraform Enterprise Instance'
            kwargs.jdata.pattern     = '^[a-zA-Z0-9\\-\\.\\:]+$'
            kwargs.jdata.minimum     = 1
            kwargs.jdata.maximum     = 90
            kwargs.jdata.varInput    = f'What is the Hostname of the TFE Instance?'
            kwargs.jdata.varName     = f'Terraform Target Name'
            polVars.tfc_host = ezfunctions.varStringLoop(kwargs)
            if re.search(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", polVars.tfc_host):
                validating.ip_address('Terraform Target', polVars.tfc_host)
            elif ':' in polVars.tfc_host:
                validating.ip_address('Terraform Target', polVars.tfc_host)
            else: validating.dns_name('Terraform Target', polVars.tfc_host)
        else:
            polVars.tfc_host = 'app.terraform.io'
        #polVars = {}
        polVars.terraform_cloud_token = tf.terraform_cloud().terraform_token()
        #==============================================
        # Obtain Terraform Cloud Organization
        #==============================================
        if os.environ.get('tfc_organization') is None:
            polVars.tfc_organization = tf.terraform_cloud().tfc_organization(polVars, kwargs)
            os.environ.tfc_organization = polVars.tfc_organization
        else: polVars.tfc_organization = os.environ.get('tfc_organization')
        tfcb_config.append({'tfc_organization':polVars.tfc_organization})
        #==============================================
        # Obtain Version Control Provider
        #==============================================
        if os.environ.get('tfc_vcs_provider') is None:
            tfc_vcs_provider,polVars.tfc_oath_token = tf.terraform_cloud().tfc_vcs_providers(polVars, kwargs)
            polVars.tfc_vcs_provider = tfc_vcs_provider
            os.environ.tfc_vcs_provider = tfc_vcs_provider
            os.environ.tfc_oath_token = polVars.tfc_oath_token
        else:
            polVars.tfc_vcs_provider = os.environ.get('tfc_vcs_provider')
            polVars.tfc_oath_token = os.environ.tfc_oath_token
        #==============================================
        # Obtain Version Control Base Repo
        #==============================================
        if os.environ.get('vcsBaseRepo') is None:
            polVars.vcsBaseRepo = tf.terraform_cloud().tfc_vcs_repository(polVars, kwargs)
            os.environ.vcsBaseRepo = polVars.vcsBaseRepo
        else: polVars.vcsBaseRepo = os.environ.get('vcsBaseRepo')
        
        polVars.agentPoolId = ''
        polVars.allowDestroyPlan = False
        polVars.executionMode = 'remote'
        polVars.queueAllRuns = False
        polVars.speculativeEnabled = True
        polVars.triggerPrefixes = []
        #==============================================
        # Obtain Terraform Versions from GitHub
        #==============================================
        terraform_versions = []
        # Get the Latest Release Tag for Terraform
        url = f'https://github.com/hashicorp/terraform/tags'
        r = requests.get(url, stream=True)
        for line in r.iter_lines():
            toString = line.decode("utf-8")
            if re.search(r'/releases/tag/v(\d+\.\d+\.\d+)\"', toString):
                terraform_versions.append(re.search('/releases/tag/v(\d+\.\d+\.\d+)', toString).group(1))
        #==============================================
        # Removing Deprecated Versions from the List
        #==============================================
        deprecatedVersions = ['1.1.0", "1.1.1']
        for depver in deprecatedVersions:
            for Version in terraform_versions:
                if str(depver) == str(Version):
                    terraform_versions.remove(depver)
        terraform_versions = list(set(terraform_versions))
        terraform_versions.sort(reverse=True)
        #==============================================
        # Assign the Terraform Version
        #==============================================
        kwargs.jdata = DotMap()
        kwargs.jdata.default     = terraform_versions[0]
        kwargs.jdata.description = "Terraform Version for Workspaces:"
        kwargs.jdata.dontsort    = True
        kwargs.jdata.enum        = terraform_versions
        kwargs.jdata.varType     = 'Terraform Version'
        polVars.terraformVersion = ezfunctions.variablesFromAPI(kwargs)
        #==============================================
        # Begin Creating Workspaces
        #==============================================
        for org in orgs:
            kwargs.org = org
            kwargs.jdata = DotMap()
            kwargs.jdata.default     = f'{org}'
            kwargs.jdata.description = f'Name of the {org} Workspace to Create in Terraform Cloud'
            kwargs.jdata.pattern     = '^[a-zA-Z0-9\\-\\_]+$'
            kwargs.jdata.minimum     = 1
            kwargs.jdata.maximum     = 90
            kwargs.jdata.varInput    = f'Terraform Cloud Workspace Name.'
            kwargs.jdata.varName     = f'Workspace Name'
            polVars.workspaceName = ezfunctions.varStringLoop(kwargs)
            polVars.workspace_id = tf.terraform_cloud().tfcWorkspace(polVars, kwargs)
            vars = ['apikey.Intersight API Key', 'secretkey.Intersight Secret Key' ]
            for var in vars:
                pcolor.Green(f"* Adding {var.split('.')[1]} to {polVars.workspaceName}")
                kwargs['Variable'] = var.split('.')[0]
                if 'secret' in var:
                    kwargs['Multi_Line_Input'] = True
                polVars.description = var.split('.')[1]
                polVars['varId'] = var.split('.')[0]
                polVars['varKey'] = var.split('.')[0]
                kwargs = ezfunctions.sensitive_var_value(kwargs)
                polVars['varValue'] = kwargs['var_value']
                polVars['Sensitive'] = True
                if 'secret' in var and opSystem == 'Windows':
                    if os.path.isfile(polVars['varValue']):
                        f = open(polVars['varValue'])
                        polVars['varValue'] = f.read().replace('\n', '\\n')
                tf.terraform_cloud().tfcVariables(polVars, kwargs)
                kwargs['Multi_Line_Input'] = False
            vars = [
                'ipmi_over_lan.ipmi_key',
                'iscsi_boot.iscsi_boot_password',
                'ldap.binding_parameters_password',
                'local_user.local_user_password',
                'persistent_memory.secure_passphrase',
                'snmp.sensitive_vars',
                'virtual_media.vmedia_password'
            ]
            for var in vars:
                policy = '%s' % (var.split('.')[0])
                kwargs = ezfunctions.policies_parse('policies', policy, policy)
                policies = deepcopy(kwargs['policies'][policy])
                y = var.split('.')[0]
                z = var.split('.')[1]
                if len(policies) > 0:
                    if y == 'persistent_memory':
                        varValue = z
                        polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, **polVars)
                        tf.terraform_cloud().tfcVariables(**polVars)
                    else:
                        for item in policies:
                            if y == 'ipmi_over_lan' and item.get('enabled'):
                                varValue = z
                                polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                tf.terraform_cloud().tfcVariables(**polVars)
                            elif y == 'iscsi_boot' and item.get('authentication'):
                                if re.search('chap', item['authentication']):
                                    varValue = z
                                    polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                    tf.terraform_cloud().tfcVariables(**polVars)
                            elif y == 'ldap' and item.get('binding_parameters'):
                                if item['binding_parameters'].get('bind_method'):
                                    if item['binding_parameters']['bind_method'] == 'ConfiguredCredentials':
                                        varValue = z
                                        polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                        tf.terraform_cloud().tfcVariables(**polVars)
                            elif y == 'local_user':
                                if item.get('enforce_strong_password'):
                                    polVars['enforce_strong_password'] = item['enforce_strong_password']
                                else: polVars['enforce_strong_password'] = True
                                for i in item['users']:
                                    varValue = '%s_%s' % (z, i['password'])
                                    polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                    tf.terraform_cloud().tfcVariables(**polVars)
                            elif y == 'snmp':
                                if item.get('access_community_string'):
                                    varValue = 'access_community_string_%s' % (i['access_community_string'])
                                    polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                    tf.terraform_cloud().tfcVariables(**polVars)
                                if item.get('snmp_users'):
                                    for i in item['snmp_users']:
                                        varValue = 'snmp_auth_password_%s' % (i['auth_password'])
                                        polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                        tf.terraform_cloud().tfcVariables(**polVars)
                                        if i.get('privacy_password'):
                                            varValue = 'snmp_privacy_password_%s' % (i['privacy_password'])
                                            polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                            tf.terraform_cloud().tfcVariables(**polVars)
                                if item.get('snmp_traps'):
                                    for i in item['snmp_traps']:
                                        if i.get('community_string'):
                                            varValue = 'snmp_trap_community_%s' % (i['community_string'])
                                            polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                            tf.terraform_cloud().tfcVariables(**polVars)
                                if item.get('trap_community_string'):
                                    varValue = 'trap_community_string'
                                    polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                    tf.terraform_cloud().tfcVariables(**polVars)
                            elif y == 'virtual_media' and item.get('add_virtual_media'):
                                for i in item['add_virtual_media']:
                                    if i.get('password'):
                                        varValue = '%s_%s' % (z, i['password'])
                                        polVars = ezfunctions.tfc_sensitive_variables(varValue, jsonData, polVars)
                                        tf.terraform_cloud().tfcVariables(**polVars)
    else:
        pcolor.Cyan(f'\n-------------------------------------------------------------------------------------------\n')
        pcolor.Cyan(f'  Skipping Step to Create Terraform Cloud Workspaces.')
        pcolor.Cyan(f'  Moving to last step to Confirm the Intersight Organization Exists.')
        pcolor.Cyan(f'\n-------------------------------------------------------------------------------------------\n')
    # Configure the provider.tf and variables.auto.tfvars
    name_prefix = 'dummy'
    type = 'policies'
    policies.policies(name_prefix, org, type).variables(kwargs)
    # Return kwargs
    return kwargs
     
#=================================================================
# Function: Deploy Configuration to Intersight
#=================================================================
def deploy(kwargs):
    kwargs.orgs = list(kwargs.imm_dict.orgs.keys())
    #==============================================
    # Create YAML Files
    #==============================================
    orgs = kwargs.orgs
    ezfunctions.create_yaml(orgs, kwargs)
    #==============================================
    # Pools
    #==============================================
    pool_list = []
    for k, v in kwargs.ezdata.items():
        if v.intersight_type == 'pool' and not '.' in k: pool_list.append(k)
    for ptype in pool_list:
        for org in orgs:
            kwargs.org = org
            if kwargs.imm_dict.orgs[org].get('pools'):
                if ptype in kwargs.imm_dict.orgs[org]['pools']:  kwargs = eval(f"isight.imm(ptype).pools(kwargs)")
    #==============================================
    # Policies
    #==============================================
    policy_list = []
    for k, v in kwargs.ezdata.items():
        if v.intersight_type == 'policy' and not '.' in k: policy_list.append(k)
    for ptype in policy_list:
        for org in orgs:
            kwargs.org = org
            if kwargs.imm_dict.orgs[org].get('policies'):
                if ptype in kwargs.imm_dict.orgs[org]['policies']:  kwargs = eval(f"isight.imm(ptype).policies(kwargs)")
    #==============================================
    # Profiles
    #==============================================
    for org in orgs:
        kwargs.org = org
        if kwargs.imm_dict.orgs[org].get('templates'):
            if kwargs.imm_dict.orgs[org]['templates'].get('server'): kwargs = eval(f"isight.imm('server_template').profiles(kwargs)")
    for org in orgs:
        kwargs.org = org
        if kwargs.imm_dict.orgs[org].get('profiles'):
            profile_list = ['domain', 'chassis', 'server']
            for i in profile_list:
                if kwargs.imm_dict.orgs[org]['profiles'].get(i): kwargs = eval(f"isight.imm(i).profiles(kwargs)")
    # return kwargs
    return kwargs

#=================================================================
# Function: Intersight Transition Tool Configuration Conversion
#=================================================================
def imm_transition(kwargs):
    #==============================================
    # Obtain JSON File
    #==============================================
    json_check = False
    json_file  = kwargs.args.json_file
    if json_file == None: json_file = 'none'
    while json_check == False:
        if not os.path.isfile(json_file):
            pcolor.Yellow(f'\n{"-"*108}\n\n  !!ERROR!!\n  Did not find the file `{json_file}`.')
            pcolor.Yellow(f'  Please Validate that you have specified the correct file and path.')
            kwargs.jdata = kwargs.ezwizard.setup.properties.json_file
            json_file    = ezfunctions.variable_prompt(kwargs)
        else: json_check = True
    kwargs.json_data = DotMap(json.load(open(json_file, 'r')))
    device_type = kwargs.json_data.easyucs.metadata[0].device_type
    #==============================================
    # Validate the device_type in json file
    #==============================================
    if not device_type == 'intersight':
        pcolor.Red(f'\n{"-"*108}\n\n  !!ERROR!!\n  The File `{json_file}` device_type is `{device_type}`.')
        pcolor.Red(f'  This file is either the UCSM Configuration converted from XML to JSON or invalid.'\
                   f'  The device_type is found on line 10 of the json configuration file.'\
                   f'  The Script is looking for the file that has been converted to Intersight Managed Mode.'\
                   f'  The JSON file should be downloaded at the last step of the IMM Transition tool where the'\
                   f'  API Key and Secret would be entered to upload to Intersight.'\
                   f'  Exiting Wizard...  (ezimm.py Line 402)')
        pcolor.Red(f'\n{"-"*108}\n')
        len(False); sys.exit(1)
    #==============================================
    # Run through the IMM Transition Wizard
    #==============================================
    kwargs = transition.intersight('transition').policy_loop(kwargs)
    #==============================================
    # Create YAML Files and return kwargs
    #==============================================
    kwargs.orgs = list(kwargs.imm_dict.orgs.keys())
    orgs = kwargs.orgs
    ezfunctions.create_yaml(orgs, kwargs)
    return kwargs

#=================================================================
# Function: Main Menu
#=================================================================
def menu(kwargs):
    #=================================================================
    # Prompt User for Deployment Type and Loading Configurations
    #=================================================================
    pcolor.Cyan(f'\n{"-"*108}\n\n  Starting the Easy IMM Wizard!\n\n{"-"*108}\n')
    kwargs = questions.main_menu.deployment_type(kwargs)
    if   kwargs.deployment_type == 'Exit': return kwargs
    elif kwargs.deployment_type == 'Convert': kwargs = imm_transition(kwargs); return kwargs
    kwargs = questions.main_menu.previous_configuration(kwargs)
    if kwargs.deployment_type == 'Deploy': kwargs = deploy(kwargs); return kwargs
    kwargs.main_menu_list = []
    #=================================================================
    # Prompt User with Questions
    #=================================================================
    kwargs = questions.orgs.organization(kwargs)
    if not kwargs.get('profile_option') and kwargs.deployment_type == 'OSInstall':
        kwargs.jdata          = kwargs.ezwizard.setup.properties.profile_option
        kwargs.profile_option = ezfunctions.variable_prompt(kwargs)
    else: kwargs.profile_option = 'new'
    if not re.search('Individual', kwargs.deployment_type):
        if (re.search('OSInstall', kwargs.deployment_type) and kwargs.profile_option == 'existing'): pass
        elif type(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.shared_org) == str: kwargs.use_shared_org = True
        else: questions.orgs.organization_shared(kwargs)
    if len(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.toDict()) == 0:
        kwargs = build.intersight('setup').setup(kwargs)
    else:
        orgs = list(kwargs.imm_dict.orgs.keys())
        if kwargs.org in orgs:
            for org in orgs:
                if kwargs.imm_dict.orgs[org].get('wizard') and kwargs.imm_dict.orgs[org].wizard.get('setup'):
                    kwargs.org = org
                    for k,v in kwargs.imm_dict.orgs[kwargs.org].wizard.setup.items(): kwargs[k] = v
                    kwargs = build.intersight('setup').setup(kwargs)
    return kwargs


#=================================================================
# Function: Wizard
#=================================================================
def process_wizard(kwargs):
    #==============================================
    # Process List from Main Menu
    #==============================================
    profile_list = ['chassis', 'domain', 'server', 'server_template']
    if kwargs.deployment_type == 'OSInstall':
        kwargs = build.intersight(kwargs.target_platform).operating_system_installation(kwargs)
        return kwargs
    elif kwargs.build_type == 'Interactive':
        for p in kwargs.main_menu_list:
            #==============================================
            # Intersight Pools/Policies/Profiles
            #==============================================
            if p in kwargs.pool_list or p in kwargs.policy_list or p in profile_list:
                kwargs = build.intersight(p).ezimm(kwargs)
    elif kwargs.build_type == 'Machine' and kwargs.deployment_type == 'Domain':
        if kwargs.discovery == True:
            kwargs = build.intersight('domain').domain_setup(kwargs)
        kwargs = build.intersight('quick_start').quick_start_domain(kwargs)
    #==============================================
    # Create YAML Files
    #==============================================
    kwargs.orgs = list(kwargs.imm_dict.orgs.keys())
    orgs = kwargs.orgs
    ezfunctions.create_yaml(orgs, kwargs)
    if len(kwargs.imm_dict.orgs.keys()) > 0: kwargs = isight.api('organization').organizations(kwargs)
    if kwargs.deployment_method == 'Terraform':
        #==============================================
        # Create Terraform Config and Workspaces
        #==============================================
        ezfunctions.merge_easy_imm_repository(kwargs)
        kwargs = ezfunctions.terraform_provider_config(kwargs)
        kwargs = create_terraform_workspaces(orgs, kwargs)
    elif re.search('Domain|Individual|Server', kwargs.deployment_type): kwargs = deploy(kwargs)
    return kwargs

#=================================================================
# Function: Main Script
#=================================================================
def main():
    #==============================================
    # Configure logger and Build kwargs
    #==============================================
    script_name = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    dest_dir = f"{Path.home()}{os.sep}Logs"
    dest_file = script_name + '.log'
    if not os.path.exists(dest_dir): os.mkdir(dest_dir)
    if not os.path.exists(os.path.join(dest_dir, dest_file)): 
        create_file = f'type nul >> {os.path.join(dest_dir, dest_file)}'; os.system(create_file)
    FORMAT = '%(asctime)-15s [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
    logging.basicConfig( filename=f"{dest_dir}{os.sep}{script_name}.log", filemode='a', format=FORMAT, level=logging.DEBUG )
    logger = logging.getLogger('openapi')
    kwargs = cli_arguments()
    if os.getenv('intersight_fqdn'): kwargs.args.intersight_fqdn = os.getenv('intersight_fqdn')
    if os.getenv('intersight_secret_key'): kwargs.args.intersight_secret_key = os.getenv('intersight_secret_key')
    #==============================================
    # Determine the Script Path
    #==============================================
    kwargs.script_path= script_path
    args_dict = vars(kwargs.args)
    for k,v in args_dict.items():
        if type(v) == str:
            if v: os.environ[k] = v
    if kwargs.args.intersight_secret_key:
        if '~' in kwargs.args.intersight_secret_key:
            kwargs.args.intersight_secret_key = os.path.expanduser(kwargs.args.intersight_secret_key)
    kwargs.args.dir  = os.path.abspath(kwargs.args.dir)
    kwargs.home      = Path.home()
    kwargs.logger    = logger
    kwargs.op_system = platform.system()
    #================================================
    # Import Stored Parameters and Add to kwargs
    #================================================
    ezdata = materialize(RefDict(f'{script_path}{os.sep}variables{os.sep}easy-imm.json', 'r', encoding="utf8"))
    kwargs.ez_tags  = {'Key':'ezimm','Value':ezdata['info']['version']}
    kwargs.ezdata   = DotMap(ezdata['components']['schemas'])
    kwargs.ezwizard = DotMap(ezdata['components']['wizard'])
    #==============================================
    # Get Intersight Configuration
    # - apikey
    # - endpoint
    # - keyfile
    #==============================================
    kwargs = ezfunctions.intersight_config(kwargs)
    kwargs.args.url = 'https://%s' % (kwargs.args.intersight_fqdn)
    #==============================================
    # Check Folder Structure for Illegal Characters
    #==============================================
    for folder in kwargs.args.dir.split(os.sep):
        if folder == '': pass
        elif not re.search(r'^[\w\-\.\:\/\\]+$', folder):
            pcolor.Red(f'\n{"-"*108}\n\n  !!ERROR!!')
            pcolor.Red(f'  The Directory structure can only contain the following characters:')
            pcolor.Red(f'  letters(a-z, A-Z), numbers(0-9), hyphen(-), period(.), colon(:), and underscore(-).')
            pcolor.Red(f'  It can be a short path or a fully qualified path.  "{folder}" does not qualify.')
            pcolor.Red(f'  Exiting...\n\n{"-"*108}\n')
            len(False); sys.exit(1)
    #==============================================
    # Prompt User for Main Menu
    #==============================================
    kwargs = menu(kwargs)
    if re.search('Domain|Individual|OSInstall|Server', kwargs.deployment_type): kwargs = process_wizard(kwargs)
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...\n\n{"-"*108}\n')
    sys.exit(0)

if __name__ == '__main__':
    main()
