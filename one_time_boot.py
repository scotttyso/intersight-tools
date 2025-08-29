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
    from classes import ezfunctions, isight, pcolor
    from copy import deepcopy
    from dotmap import DotMap
    import argparse, json, os, re, requests, time, urllib3, yaml
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
    parser = ezfunctions.base_arguments_ezimm_sensitive_variables(parser)
    parser.add_argument(
        '-iso', '--mapping-iso', default ='',
        help = 'Name of the ISO file to mapping:')
    return DotMap(args = parser.parse_args())
#=============================================================================
# Function: Parse Arguments
#=============================================================================
def hosts(kwargs):
    #=========================================================================
    # Setup Variables
    #=========================================================================
    boot_device = 'kvm'
    kwargs.org  = 'common'
    kwargs.org1 = 'RICH'
    name        = 'vmedia1'
    profiles = [
        DotMap(action = 'Deploy', name = 'r142c-2-8', serial_number = 'FCH243974V2'),
        # DotMap(action = 'Deploy', name = 'r142c-2-8', serial_number = 'FCH243974V2'),
        # DotMap(action = 'Deploy', name = 'r142c-2-8', serial_number = 'FCH243974V2'),
        # DotMap(action = 'Deploy', name = 'r142c-2-8', serial_number = 'FCH243974V2'),
        # DotMap(action = 'Deploy', name = 'r142c-2-8', serial_number = 'FCH243974V2'),
        # DotMap(action = 'Deploy', name = 'r142c-2-8', serial_number = 'FCH243974V2')
    ]
    #=========================================================================
    # Patch Virtual Media
    #=========================================================================
    kwargs = isight.api('organization').all_organizations(kwargs)
    kwargs = kwargs | DotMap(method = 'get', names = [name], uri = 'vmedia/Policies')
    kwargs = isight.api('virtual_media').calls(kwargs)
    api_body = {
        "Mappings": [{
            'AuthenticationProtocol': 'none', 'DeviceType': 'cdd',
            'FileLocation': f'https://10.247.2.11/{kwargs.args.mapping_iso}', 'MountOptions': 'noauto', 'MountProtocol': 'https'
        }]
    }
    kwargs = kwargs | DotMap(api_body = api_body, method = 'patch', pmoid = kwargs.pmoids[name].moid, uri = 'vmedia/Policies')
    kwargs = isight.api('virtual_media').calls(kwargs)
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Virtual Media Patch Complete.  Sleeping for Profile Validation !!!\n\n{"-"*108}\n')
    time.sleep(30)
    #=========================================================================
    # Deploy Domain Profiles
    #=========================================================================
    kwargs.org = kwargs.org1
    kwargs = isight.imm('profiles.server').profiles_chassis_server_deploy(profiles, kwargs)
    #=========================================================================
    # Set One Time Boot and Reboot
    #=========================================================================
    physical_servers = DotMap()
    kwargs = kwargs | DotMap(method = 'get', names = [e.name for e in profiles], uri = 'server/Profiles')
    kwargs = isight.api('server').calls(kwargs)
    for e in kwargs.results: physical_servers[e.AssignedServer.Moid] = DotMap(name = e.Name, object_type = e.AssignedServer.ObjectType)
    kwargs = kwargs | DotMap(method = 'get', names = [k for k,v in physical_servers.items()], uri = 'compute/ServerSettings')
    kwargs = isight.api('ancestors').calls(kwargs)
    for e in kwargs.results: physical_servers[e.Ancestors[0].Moid].server_settings_moid = e.Moid
    pcolor.Cyan(f'\n{"-"*108}\n')
    for k, v in physical_servers.items():
        api_body = {'AdminPowerState': "PowerCycle", 'OneTimeBootDevice': boot_device}
        kwargs   = kwargs | DotMap(api_body = api_body, method = 'post_by_moid', pmoid = v.server_settings_moid)
        kwargs   = isight.api('servers').calls(kwargs)
        pcolor.Cyan(f'    * One Time Boot Set for Server: {v.name} - Moid: {k}')
    pcolor.Cyan(f'\n{"-"*108}\n')

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
    # Set Virtual Media and Reboot
    #=========================================================================
    kwargs = hosts(kwargs)
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...\n\n{"-"*108}\n')
    sys.exit(0)

if __name__ == '__main__':
    main()
