#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import build, ezfunctions, isight, pcolor, questions, tf, terraform, transition, validating
    from copy import deepcopy
    from dotmap import DotMap
    from pathlib import Path
    import argparse, json, logging, os, platform, re, requests, urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

#=============================================================================
# Function: Parse Arguments
#=============================================================================
def cli_arguments():
    parser = argparse.ArgumentParser(description ='Intersight Easy IMM Deployment Module')
    parser = ezfunctions.base_arguments(parser)
    parser = ezfunctions.base_arguments_ezimm_sensitive_variables(parser)
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
def main():
    #=========================================================================
    # Configure Base Module Setup
    #=========================================================================
    kwargs = cli_arguments()
    #=========================================================================
    # Configure logger and Build kwargs
    #=========================================================================
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
    kwargs.imm_dict.orgs = DotMap()
    kwargs.type_dotmap   = type(DotMap())
    kwargs.type_none     = type(None)
    #=========================================================================
    # Import Stored Parameters and Add to kwargs
    #=========================================================================
    ezdata = DotMap(json.load(open(os.path.join(kwargs.script_path, 'variables', 'easy-imm.json'), 'r', encoding='utf8')))
    # print(json.dumps(ezdata.components.schemas['ip.ipv4_blocks'], indent=4))
    for key, value in ezdata.components.schemas.items():
        value_keys = list(value.keys())
        if 'type' in value_keys and 'properties' in value_keys and value.type == 'object':
            descr = value.description
            req   = value.required
            title = value.title
            for k, v in v.properties.items():
                vkeys = list()

if __name__ == '__main__':
    main()
