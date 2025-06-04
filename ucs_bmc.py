#!/usr/bin/env python3
""" Infrastructure Deployment - 
This Script is built to Deploy Infrastructure from a YAML Configuration File.
The Script uses argparse to take in the following CLI arguments:
    -a  or -intersight-api-key-id: The Intersight API key id for HTTP signature scheme.
    -d  or -dir:                   Base Directory to use for creation of the YAML Configuration Files.
    -dl or -debug-level:          The Debug Level to Run for Script Output
    -e  or -intersight-fqdn:       The Intersight hostname for the API endpoint. The default is intersight.com.
    -i  or -ignore-tls:            Ignore TLS server-side certificate verification.  Default is False.
    -k  or -intersight-secret-key: Name of the file containing The Intersight secret key for the HTTP signature scheme.
    -s  or -deployment-step:       The steps in the proceedure to run. Options Are: 
                                     1. initial
                                     2. servers
                                     3. luns
                                     4. operating_system
                                     5. os_configuration
    -t  or -deployment-type:       Infrastructure Deployment Type. Options Are: 
                                     1. azure_stack
                                     2. flashstack
                                     3. flexpod
                                     4. imm_domain
                                     5. imm_standalone
    -v  or -api-key-v3:            Flag for API Key Version 3.
    -y  or -yaml-file:             The input YAML File.
"""
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import bmc, ezfunctions, pcolor
    from copy import deepcopy
    from dotmap import DotMap
    from pathlib import Path
    import argparse, json, os, re, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

#=============================================================================
# Function: Parse Arguments
#=============================================================================
def cli_arguments():
    parser = argparse.ArgumentParser(description ='Intersight Easy IMM Deployment Module', conflict_handler='resolve')
    parser = ezfunctions.base_arguments(parser)
    parser.add_argument('-y', '--yaml-file', default = None, required=True,  help = 'The input YAML File.')
    return DotMap(args = parser.parse_args())

#=============================================================================
# Function: Main Script
#=============================================================================
def main():
    #=========================================================================
    # Configure Base Module Setup
    #=========================================================================
    kwargs = cli_arguments()
    kwargs = ezfunctions.base_script_settings(kwargs)
    #=========================================================================
    # Send Notification Message
    #=========================================================================
    if os.path.isfile(kwargs.args.yaml_file): pass
    else: pcolor.Yellow(f'`{kwargs.args.yaml_file}` is not valid')
    kwargs.args.dir        = os.path.dirname(os.path.abspath(kwargs.args.yaml_file))

    pcolor.Green(f'\n{"-"*108}\n\n  Begin Deployment for hosts.')
    pcolor.Green(f'\n{"-"*108}\n')
    #=========================================================================
    # Process the YAML input File
    #=========================================================================
    if (kwargs.args.yaml_file):
        yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
        kwargs.ucs_dict = DotMap(yaml.safe_load(yfile))
        yfile.close()
    else:
        pcolor.Red(f'!!! ERROR !!!\n  The YAML file `{kwargs.args.yaml_file}` is not valid.')
        sys.exit(1)
    kwargs = bmc.build('ucs').hosts(kwargs)
    #=========================================================================


    pcolor.Green(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...')
    pcolor.Green(f'\n{"-"*108}\n')
    sys.exit(0)

if __name__ == '__main__':
    main()
