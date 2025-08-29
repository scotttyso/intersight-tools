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
script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, pcolor
    from copy import deepcopy
    from dotmap import DotMap
    from pathlib import Path
    import argparse, jinja2, json, logging, os, platform, re, requests, urllib3, yaml
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'EZIMM - !!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=============================================================================
# Function: Parse Arguments
#=============================================================================
def cli_arguments():
    parser = argparse.ArgumentParser(description ='Intersight Easy IMM Deployment Module')
    parser = ezfunctions.base_arguments(parser)
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
    return DotMap(args = parser.parse_args())

#=============================================================================
# Function: Main Script
#=============================================================================
def menu(kwargs):
    yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
    kwargs.ezdata = DotMap(yaml.safe_load(yfile))
    yfile.close()
    #=========================================================================
    # Setup jinja2 Environment
    #=========================================================================
    template_dir    = os.path.join(kwargs.script_path, 'templates', 'openshift', 'deploy_cluster')
    template_loader = jinja2.FileSystemLoader(template_dir)
    template_env    = jinja2.Environment(loader=template_loader)
    #=========================================================================
    # Define the Template Source
    #=========================================================================
    template_list = [
        # '00-cilium-namespace.j2',
        # '00-cluster-namespace.j2',
        # '01-agent-cluster-install.j2',
        # '02-assisted-deployment-pull-secret.j2',
        # '02-cluster-deployment.j2',
        # '03-cilium-custom-resource-definition.j2',
        # '04-cilium-deployment.j2',
        # '05-cilium-config.j2',
        # '06-cilium-operator-group.j2',
        # '07-cilium-rbac-cluster-roles.j2',
        # '08-cilium-subscription.j2',
        # '09-cilium-service-account.j2',
        # '09-cilium-service.j2',
        '10-nmstate-config.j2',
        # '12-spoke-infraenv.j2',
        # '13-baremetal-cluster.j2',
        # '14-machine-config.j2',
        # '15-portworx-machine-config.j2'
    ]
    for template_file in template_list:
        template = template_env.get_template(template_file)
        #print(template); exit()
        payload  = template.render(kwargs.ezdata.toDict())
        print(json.dumps(payload, indent=4))
    exit()
#=============================================================================
# Function: Main Script
#=============================================================================
def main():
    #=========================================================================
    # Configure Base Module Setup
    #=========================================================================
    kwargs = cli_arguments()
    script_name = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    dest_dir    = f'{Path.home()}{os.sep}Logs'
    dest_file   = script_name + '.log'
    if not os.path.exists(dest_dir): os.mkdir(dest_dir)
    if not os.path.exists(os.path.join(dest_dir, dest_file)): 
        create_file = f'type nul >> {os.path.join(dest_dir, dest_file)}'; os.system(create_file)
    FORMAT = '%(asctime)-15s [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
    logging.basicConfig(filename=f'{dest_dir}{os.sep}{script_name}.log', filemode='a', format=FORMAT, level=logging.DEBUG )
    logger = logging.getLogger('openapi')
    #=========================================================================
    # Determine the Script Path
    #=========================================================================
    args_dict = vars(kwargs.args)
    for k,v in args_dict.items():
        if type(v) == str and v != None: os.environ[k] = v
    kwargs.script_name   = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    kwargs.script_path   = os.path.dirname(os.path.realpath(sys.argv[0]))
    kwargs.args.dir      = os.path.abspath(kwargs.args.dir)
    kwargs.home          = Path.home()
    kwargs.logger        = logger
    kwargs.op_system     = platform.system()
    kwargs.type_dotmap   = type(DotMap())
    kwargs.type_none     = type(None)

    # kwargs = ezfunctions.base_script_settings(kwargs)
    #=========================================================================
    # Prompt User for Main Menu
    #=========================================================================
    kwargs = menu(kwargs)
    #if re.search('Domain|Individual|OSInstall|Server', kwargs.deployment_type): kwargs = process_wizard(kwargs)
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...\n\n{"-"*108}\n')
    sys.exit(0)

if __name__ == '__main__':
    main()
