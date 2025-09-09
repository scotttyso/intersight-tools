#!/usr/bin/env python3
"""Deploy OCP - 
Use This Wizard to Create Terraform HCL configuration from Question and Answer or the IMM Transition Tool.
It uses argparse to take in the following CLI arguments:
    -d   or --dir:                   Base Directory to use for creation of the YAML Configuration Files.
    -dt  or --deployment-type:       The Deployment Type to use for the script.
                                       1. argocd-gitops:      Create YAML Files for ArgoCD application deployment.
                                       2. cluster-deployment: Create YAML Files for RHACM agent assist cluster deployment.
                                       3. openshift-ai:       Create YAML Files for RedHat Openshift AI ArgoCD.
                                       4. Exit:               Cancel the Wizard.
    -y  or --yaml-file:              The input YAML File.
Example:
    python deploy_ocp.py -d <directory> -dt <deployment_type> -y <yaml_file>
"""
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, os.path.join(script_path, 'classes'))
try:
    from classes import ezfunctions, pcolor
    from dotmap  import DotMap
    from pathlib import Path
    import argparse, base64, jinja2, logging, re, yaml
except ImportError as e:
    prRed(f'deploy_ocp.py - !!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=============================================================================
# Function: Parse Arguments
#=============================================================================
def cli_arguments():
    parser = argparse.ArgumentParser(description ='OpenShift Container Platform Deployment Module')
    parser.add_argument(
        '-d', '--dir', default = f'{Path.home()}{os.sep}install',
        help   = 'The Directory to use for the Creation of the YAML Configuration Files.')
    parser.add_argument(
        '-dt', '--deployment-type', default ='',
        help = 'Deployment Type values are: \
            1.  argocd-gitops \
            2.  cluster-deployment \
            3.  openshift-ai \
            4.  Exit')
    parser.add_argument('-y', '--yaml-file', default = None,  help = 'The input YAML File.')
    return DotMap(args = parser.parse_args())

#=============================================================================
# Function: Write File
#=============================================================================
def write_file(dest_dir, dest_file, ydata):
    if not os.path.isdir(dest_dir): os.makedirs(dest_dir)
    if not os.path.exists(os.path.join(dest_dir, dest_file)):
        Path(os.path.join(dest_dir, dest_file)).touch()
    with open(os.path.join(dest_dir, dest_file), 'w') as wr_file:
        wr_file.write(ydata)

#=============================================================================
# Function: RedHat OpenShift Cluster
#=============================================================================
def cluster_deployment(kwargs):
    #=========================================================================
    # Import YAML Data
    #=========================================================================
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
    template_list = [item for item in os.listdir(template_dir) if os.path.isfile(os.path.join(template_dir, item))]
    for template_file in template_list:
        template = template_env.get_template(template_file)
        ydata    = template.render(kwargs.ydata.toDict())
        write_file(dest_dir=os.path.join(kwargs.args.dir, kwargs.args.deployment_type), dest_file=f'{template_file.replace('j2', 'yaml')}', ydata=ydata)
    
#=============================================================================
# Function: RedHat OpenShift ArgoCD Applications for OpenShift AI
#=============================================================================
def gitops(kwargs):
    #=========================================================================
    # Import YAML Data
    #=========================================================================
    yaml_file    = open(os.path.join(kwargs.args.yaml_file), 'r')
    kwargs.ydata = DotMap(yaml.safe_load(yaml_file))
    yaml_file.close()
    #=========================================================================
    # Loop Through Templates
    #=========================================================================
    start_directory = os.path.join(kwargs.script_path, 'classes', 'templates', 'openshift', kwargs.args.deployment_type)
    for root, _, files in os.walk(start_directory):
        for file_name in files:
            full_path = os.path.join(root, file_name)
            if re.search('j2', full_path):
                sub_dir      = root.split(kwargs.args.deployment_type)[1]
                template_dir = os.path.join(root)
                template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
                template     = template_env.get_template(file_name)
                ydata        = template.render(kwargs.ydata.toDict())
                write_file(dest_dir=f'{kwargs.args.dir}{os.sep}{kwargs.args.deployment_type}{sub_dir}', dest_file=f'{file_name.replace('j2', 'yaml')}', ydata=ydata)

#=============================================================================
# Function: Argument Validation
#=============================================================================
def argument_validation(kwargs):
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
    if not kwargs.args.deployment_type: kwargs.args.deployment_type = 'empty'
    if not re.search('^(argocd-gitops|cluster-deployment|openshift-ai)$', kwargs.args.deployment_type):
        kwargs.jdata = DotMap(
            type = "string",
            default = "cluster-deployment",
            description = 'Select the Option to Perform:'\
                '\n  * argocd-gitops:      Create YAML Files for ArgoCD application deployment.' \
                '\n  * cluster-deployment: Create YAML Files for RHACM agent assist cluster deployment.'\
                '\n  * openshift-ai:       Create YAML Files for RedHat Openshift AI ArgoCD.' \
                '\n  * Exit:               Cancel the Wizard',
            enum = [
                "argocd-gitops",
                "cluster-deployment",
                "openshift-ai",
                "Exit"
            ],
            sort = False,
            title = "Deployment Type"
        )
        kwargs.args.deployment_type = ezfunctions.variable_prompt(kwargs)
        if kwargs.args.deployment_type == 'Exit':
            pcolor.Cyan(f'\n{"-"*108}\n\n  Exiting Script...\n\n{"-"*108}\n')
            sys.exit(0)
    return kwargs

#=============================================================================
# Function: Main Script
#=============================================================================
def main():
    #=========================================================================
    # Configure Base Module Setup
    #=========================================================================
    kwargs = cli_arguments()
    log_dir     = f'{Path.home()}{os.sep}Logs'
    dest_file   = (sys.argv[0].split(os.sep)[-1]).split('.')[0] + '.log'
    if not os.path.isdir(log_dir): os.makedirs(log_dir)
    if not os.path.exists(os.path.join(log_dir, dest_file)):
        Path(os.path.join(log_dir, dest_file)).touch()
    FORMAT = '%(asctime)-15s [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
    logging.basicConfig(filename=os.path.join(log_dir, dest_file), filemode='a', format=FORMAT, level=logging.DEBUG )
    kwargs.logger = logging.getLogger('openapi')
    #=========================================================================
    # Determine the Script Path
    #=========================================================================
    args_dict = vars(kwargs.args)
    for k,v in args_dict.items():
        if type(v) == str and v != None: os.environ[k] = v
    kwargs.script_name = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    kwargs.script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
    kwargs.args.dir    = os.path.abspath(kwargs.args.dir)
    if not os.path.isdir(kwargs.args.dir): os.mkdir(kwargs.args.dir)
    #=========================================================================
    # Run Deployment Type
    #=========================================================================
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Begin Procedures !!!\n\n{"-"*108}\n')
    kwargs = argument_validation(kwargs)
    if kwargs.args.deployment_type == 'cluster-deployment': kwargs = cluster_deployment(kwargs)
    elif re.search('argocd-gitops|openshift-ai', kwargs.args.deployment_type): kwargs = gitops(kwargs)
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...\n\n{"-"*108}\n')
    sys.exit(0)

if __name__ == '__main__':
    main()
