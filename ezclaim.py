#!/usr/bin/env python3
"""Intersight Device Connector API configuration and device claim via the Intersight API."""

#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import claim_device, ezfunctions, isight, pcolor
    from dotmap import DotMap
    from pathlib import Path
    import argparse, os, traceback, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")

#=============================================================================
# Parse Arguments
#=============================================================================
def cli_arguments():
    kwargs = DotMap()
    parser = argparse.ArgumentParser(description ='Intersight Easy IMM Deployment Module')
    parser = ezfunctions.base_arguments(parser)
    parser.add_argument( '-ilp', '--local-user-password-1',   help='Password used to login to the device for claiming.' )
    parser.add_argument( '-pxp', '--proxy-password',   help='Proxy password when using proxy and authentication is required.' )
    kwargs.args = parser.parse_args()
    return kwargs

#=============================================================================
# Function: Main Script
#=============================================================================
def main():
    #=========================================================================
    # Configure Base Module Setup
    #=========================================================================
    kwargs = cli_arguments()
    kwargs = ezfunctions.base_script_settings(kwargs)
    kwargs = isight.api('organization').all_organizations(kwargs)
    #=========================================================================
    # EZCLAIM Setup
    #=========================================================================
    return_code = 0
    kwargs.args.dir    = os.path.join(Path.home(), kwargs.args.yaml_file.split('/')[0])
    kwargs.deployment_type ='claim_devices'
    #=========================================================================
    # Send Notification Message
    #=========================================================================
    pcolor.LightGray(f'\n{"-"*91}\n')
    pcolor.LightGray(f'  * Begin Device Claims.')
    pcolor.LightGray(f'\n{"-"*91}\n')
    yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
    kwargs.yaml = DotMap(yaml.safe_load(yfile))
    try:
        kwargs.sensitive_var  = 'local_user_password_1'
        kwargs                = ezfunctions.sensitive_var_value(kwargs)
        kwargs.password       = kwargs.var_value
        kwargs.yaml.password  = kwargs.password
        kwargs = claim_device.claim_targets(kwargs)
    except Exception as err:
        print("Exception:", str(err))
        print('-' * 60)
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)
        if kwargs.return_code:
            sys.exit(kwargs.return_code)
        else: sys.exit(return_code)
    #=========================================================================
    # Send Notification Message and Exit
    #=========================================================================
    pcolor.LightGray(f'\n{"-"*91}\n')
    pcolor.LightGray(f'  * Completed Device Claims.')
    pcolor.LightGray(f'\n{"-"*91}\n')
    sys.exit(1)
if __name__ == '__main__':
    main()
