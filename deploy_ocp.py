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
    import argparse, base64, jinja2, json, logging, os, platform, re, requests, urllib3, yaml
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
    #parser = ezfunctions.base_arguments(parser)
    parser.add_argument(
        '-a', '--intersight-api-key-id', default = os.getenv('intersight_api_key_id'),
        help   = 'The Intersight API key id for HTTP signature scheme.')
    parser.add_argument(
        '-d', '--dir', default = f'{Path.home()}{os.sep}install',
        help   = 'The Directory to use for the Creation of the YAML Configuration Files.')
    parser.add_argument(
        '-dt', '--deployment-type', default ='',
        help = 'Deployment Type values are: \
            1.  cluster-deployment \
            2.  gitops \
            3.  openshift-ai \
            4.  Exit')
    parser.add_argument(
        '-i', '--ignore-tls', action = 'store_false',
        help   = 'Ignore TLS server-side certificate verification.  Default is False.')
    parser.add_argument(
        '-k', '--intersight-secret-key', default = os.getenv('intersight_secret_key'),
        help   = 'Name of the file containing The Intersight secret key or contents of the secret key in environment.')
    parser.add_argument('-y', '--yaml-file', default = None,  help = 'The input YAML File.')
    return DotMap(args = parser.parse_args())

#=============================================================================
# Function: Write File
#=============================================================================
def write_file(dest_dir, dest_file, ydata):
    if not os.path.isdir(dest_dir): os.makedirs(dest_dir)
    if not os.path.exists(os.path.join(dest_dir, dest_file)):
        create_file = f'type nul >> {os.path.join(dest_dir, dest_file)}'
        os.system(create_file)
    wr_file = open(os.path.join(dest_dir, dest_file), 'w')
    wr_file.write(ydata)
    wr_file.close()

#=============================================================================
# Function: RedHat OpenShift Cluster
#=============================================================================
def cluster_deployment(kwargs):
    #=========================================================================
    # Import YAML Data
    #=========================================================================
    if not os.path.isdir(kwargs.args.dir): os.mkdir(kwargs.args.dir)
    yaml_file    = open(os.path.join(kwargs.args.yaml_file), 'r')
    kwargs.ydata = DotMap(yaml.safe_load(yaml_file))
    yaml_file.close()
    #=========================================================================
    # Setup jinja2 Environment
    #=========================================================================
    def b64decode_filter(value):
        return base64.b64decode(value).decode('utf-8')
    def b64encode_filter(value):
        return base64.b64encode(value.encode('utf-8')).decode('utf-8')
    template_dir = os.path.join(kwargs.script_path, 'classes', 'templates', 'openshift', 'cluster-deployment')
    template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
    template_env.filters['b64decode'] = b64decode_filter
    template_env.filters['b64encode'] = b64encode_filter
    #=========================================================================
    # Loop Through Templates
    #=========================================================================
    dest_dir      = kwargs.args.dir
    template_list = [item for item in os.listdir(template_dir) if os.path.isfile(os.path.join(template_dir, item))]
    for template_file in template_list:
        template = template_env.get_template(template_file)
        ydata    = template.render(kwargs.ydata.toDict())
        write_file(dest_dir=dest_dir, dest_file=f'{template_file.replace('j2', 'yaml')}', ydata=ydata)
    
#=============================================================================
# Function: RedHat OpenShift ArgoCD Applications
#=============================================================================
def gitops(kwargs):
    #=========================================================================
    # Import YAML Data
    #=========================================================================
    if not os.path.isdir(kwargs.args.dir): os.mkdir(kwargs.args.dir)
    yaml_file    = open(os.path.join(kwargs.args.yaml_file), 'r')
    kwargs.ydata = DotMap(yaml.safe_load(yaml_file))
    yaml_file.close()
    #=========================================================================
    # Setup jinja2 Environment
    #=========================================================================
    template_dir    = os.path.join(kwargs.script_path, 'classes', 'templates', 'openshift', 'cluster-deployment')
    template_loader = jinja2.FileSystemLoader(template_dir)
    template_env    = jinja2.Environment(loader=template_loader)
    #=========================================================================
    # Loop Through Templates
    #=========================================================================
    start_directory = os.path.join(kwargs.script_path, 'classes', 'templates', 'openshift', 'gitops')
    print(f"All files (including subdirectories) in '{start_directory}':")
    for root, _, files in os.walk(start_directory):
        for file_name in files:
            full_path = os.path.join(root, file_name)
            if re.search('j2', full_path):
                print(full_path)
            # print(full_path)
    exit()
    #=========================================================================
    # Loop Through Templates
    #=========================================================================
    template_list = [item for item in os.listdir(template_dir) if os.path.isfile(os.path.join(template_dir, item))]
    for template_file in template_list:
        template = template_env.get_template(template_file)
        ydata    = template.render(kwargs.ydata.toDict())
        write_file(dest_dir=dest_dir, dest_file=f'{template_file.replace('j2', 'yaml')}', ydata=ydata)

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
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Begin Proceedures !!!\n\n{"-"*108}\n')
    #=========================================================================
    # Prompt User for YAML input file
    #=========================================================================
    if not kwargs.args.yaml_file:
        valid = False
        while valid == False:
            kwargs.jdata = DotMap(
                type = "string",
                default = "",
                description = "What is the path to the YAML Data File?",
                maxLength = 2048,
                minLength = 1,
                pattern = '.*',
                title = "YAML File"
            )
            kwargs.args.yaml_file = ezfunctions.variable_prompt(kwargs)
            if not os.path.isfile(kwargs.args.yaml_file):
                pcolor.Yellow(f'\n{"-"*108}\n')
                pcolor.Red(f' !!! ERROR !!! Invalid File\n  * `{kwargs.args.yaml_file}`')
                pcolor.Cyan(f'\n  Re-enter the File Path.')
                pcolor.Yellow(f'\n{"-"*108}\n')
            else: valid = True
    #=========================================================================
    # Prompt User for Deployment Type
    #=========================================================================
    if not kwargs.args.deployment_type:
        kwargs.jdata = DotMap(
            type = "string",
            default = "cluster-deployment",
            description = 'Select the Option to Perform:'\
                '\n  * cluster-deployment: Create YAML Files for RHACM agent assist cluster deployment.'\
                '\n  * gitops:             Create YAML Files for ArgoCD application deployment.' \
                '\n  * openshift-ai:       Create YAML Files for RedHat Openshift AI ArgoCD.' \
                '\n  * Exit:               Cancel the Wizard',
            enum = [
                "cluster-deployment",
                "gitops",
                "openshift-ai",
                "Exit"
            ],
            sort = False,
            title = "Deployment Type"
        )
        kwargs.args.deployment_type = ezfunctions.variable_prompt(kwargs)
    if kwargs.args.deployment_type == 'cluster-deployment': kwargs = cluster_deployment(kwargs)
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...\n\n{"-"*108}\n')
    sys.exit(0)

if __name__ == '__main__':
    main()
