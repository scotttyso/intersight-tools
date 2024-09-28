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
    from classes import ci, ezfunctions, isight, netapp, network, pcolor, vsphere
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
    parser = ezfunctions.base_arguments_ezimm_sensitive_variables(parser)
    parser.add_argument(
        '-s', '--deployment-step', choices=['initial', 'luns', 'operating_system', 'os_configuration', 'servers', ], default ='initial', required=True,
        help ='The steps in the proceedure to run. Options Are: '\
            '1. initial '
            '2. servers '\
            '3. luns '\
            '4. operating_system '\
            '5. os_configuration ')
    parser.add_argument(
        '-t', '--deployment-type', choices=['azure_stack', 'flashstack', 'flexpod', 'imm_domain', 'imm_standalone', ], default ='imm_domain', required=True,
        help ='Infrastructure Deployment Type. Options Are: '\
            '1. azure_stack '
            '2. flashstack '\
            '3. flexpod '\
            '4. imm_domain '\
            '5. imm_standalone ')
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
    kwargs.deployment_type = kwargs.args.deployment_type
    pcolor.Green(f'\n{"-"*108}\n\n  Begin Deployment for {kwargs.deployment_type}.')
    pcolor.Green(f'  * Deployment Step is {kwargs.args.deployment_step}.')
    pcolor.Green(f'\n{"-"*108}\n')
    #=========================================================================
    # Load Previous Configurations
    #=========================================================================
    kwargs = DotMap(ezfunctions.load_previous_configurations(kwargs))
    #=========================================================================
    # Process the YAML input File
    #=========================================================================
    if (kwargs.args.yaml_file):
        yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
        kwargs.imm_dict.wizard = DotMap(yaml.safe_load(yfile))
    #=========================================================================
    # Build Deployment Library
    #=========================================================================
    kwargs = ci.wizard('dns_ntp').dns_ntp(kwargs)
    kwargs = ci.wizard('vlans').vlans(kwargs)
    kwargs = ci.wizard('imm').imm(kwargs)
    kwargs = isight.api('organization').all_organizations(kwargs)
    if re.search('(flashstack|flexpod)', kwargs.args.deployment_type):
        if kwargs.args.deployment_type == 'flexpod':  run_type = 'netapp'
        elif kwargs.args.deployment_type == 'flashstack': run_type = 'pure_storage'
        kwargs = eval(f"ci.wizard(run_type).{run_type}(kwargs)")
    #=========================================================================
    # When Deployment Step is initial - Deploy NXOS|Storage|Domain
    #=========================================================================
    if 'flashstack' in kwargs.args.deployment_type: kwargs.protocols = ['fcp', 'iscsi', 'nvme-roce']
    elif 'flexpod' in kwargs.args.deployment_type: kwargs.protocols = ['fcp', 'iscsi', 'nfs', 'nvme-tcp']
    if kwargs.args.deployment_step == 'initial':
        #=====================================================================
        # Configure Switches if configure Set to True
        #=====================================================================
        if kwargs.imm_dict.wizard.nxos_config == True:
            if kwargs.imm_dict.wizard.get('nxos'):
                network_config = DotMap(deepcopy(kwargs.imm_dict.wizard.nxos[0]))
                network_types = ['network', 'ooband']
                for network_type in network_types:
                    config_count = 0
                    for i in network_config.switches:
                        if i.switch_type == network_type: config_count += 1
                    if config_count == 2: kwargs = network.nxos('nxos').config(network_config, network_type, kwargs)
        #=====================================================================
        # Configure Storage Appliances
        #=====================================================================
        if kwargs.args.deployment_type == 'flashstack': kwargs = ci.wizard('build').build_pure_storage(kwargs)
        elif kwargs.args.deployment_type == 'flexpod':  kwargs = ci.wizard('build').build_netapp(kwargs)
        #=====================================================================
        # Configure Domain
        #=====================================================================
        if re.search('(fl(ashstack|expod)|imm_domain)', kwargs.args.deployment_type):
            kwargs = ci.wizard('build').build_imm_domain(kwargs)
        #=====================================================================
        # Create YAML Files
        #=====================================================================
        orgs = list(kwargs.imm_dict.orgs.keys())
        kwargs = ezfunctions.remove_duplicates(orgs, ['policies', 'profiles'], kwargs)
        if len(kwargs.imm_dict.orgs) > 0: ezfunctions.create_yaml(orgs, kwargs)
        #=====================================================================
        # Deploy Policies
        #=====================================================================
        for org in orgs:
            kwargs.org = org
            if kwargs.imm_dict.orgs[org].get('policies'):
                for ptype in kwargs.policy_list:
                    if kwargs.imm_dict.orgs[org]['policies'].get(ptype): kwargs = eval(f"isight.imm(ptype).policies(kwargs)")
        #=====================================================================
        # Deploy Domain
        #=====================================================================
        if re.search('(flashstack|flexpod|imm_domain)', kwargs.args.deployment_type):
            for org in orgs:
                kwargs.org = org
                kwargs = eval(f"isight.imm('domain').profiles(kwargs)")
    #=========================================================================
    # Dummy Step to Test Script
    #=========================================================================
    elif kwargs.args.deployment_step == 'dummy':
        arg_dict = vars(kwargs.args)
        for e in list(arg_dict.keys()):
            if re.search('intersight|password', e):
                if arg_dict[e] != None: pcolor.LightPurple(f'  * Sensitive Data Value Set.')
                else: pcolor.Cyan(f'  * {arg_dict[e]}')
            else: pcolor.Cyan(f'  * {arg_dict[e]}')
    #=========================================================================
    # Deploy Chassis/Server Pools/Policies/Profiles
    #=========================================================================
    elif kwargs.args.deployment_step == 'servers':
        kwargs.deployed = {}
        #=====================================================================
        # Configure IMM Pools/Policies/Profiles
        #=====================================================================
        kwargs = ci.wizard('build').build_imm_servers(kwargs)
        orgs   = list(kwargs.imm_dict.orgs.keys())
        #=====================================================================
        # Create YAML Files
        #=====================================================================
        kwargs = ezfunctions.remove_duplicates(orgs, ['pools', 'policies', 'profiles', 'templates', 'wizard'], kwargs)
        ezfunctions.create_yaml(orgs, kwargs)
        #=====================================================================
        # Pools
        #=====================================================================
        for org in orgs:
            kwargs.org = org
            for ptype in kwargs.imm_dict.orgs[org]['pools']:
                if kwargs.imm_dict.orgs[org].get('pools'): kwargs = eval(f"isight.imm(ptype).pools(kwargs)")
        #=====================================================================
        # Policies
        #=====================================================================
        for ptype in kwargs.policy_list:
            for org in orgs:
                kwargs.org = org
                if kwargs.imm_dict.orgs[org].get('policies'):  kwargs = eval(f"isight.imm(ptype).policies(kwargs)")
        for org in orgs:
            kwargs.org = org
            kwargs.isight[org].policy = DotMap(dict(sorted(kwargs.isight[org].policy.toDict().items())))
        #=====================================================================
        # Profiles and Server Identities
        #=====================================================================
        for org in orgs:
            kwargs.org = org
            if kwargs.imm_dict.orgs[org].get('templates'):
                if kwargs.imm_dict.orgs[org]['templates'].get('server'): kwargs = eval(f"isight.imm('server_template').profiles(kwargs)")
        for org in orgs:
            kwargs.org = org
            if kwargs.imm_dict.orgs[org].get('profiles'):
                profile_list = ['chassis', 'server']
                for i in profile_list:
                    if kwargs.imm_dict.orgs[org]['profiles'].get(i): kwargs = eval(f"isight.imm(i).profiles(kwargs)")
            kwargs = isight.api('wizard').build_server_identities(kwargs)
            #=================================================================
            # Run Lun Creation Class
            #=================================================================
            if kwargs.args.deployment_type == 'flexpod': kwargs = netapp.build('lun').lun(kwargs)
        if 'azure_stack' == kwargs.args.deployment_type:
            for org in orgs: kwargs = ci.wizard('wizard').windows_prep(kwargs)
        #=====================================================================
        # Create YAML Files
        #=====================================================================
        ezfunctions.create_yaml(orgs, kwargs)
    #=========================================================================
    # Install the Operating System
    #=========================================================================
    elif kwargs.args.deployment_step == 'operating_system':
        #=====================================================================
        # Load Server Profile Variables/Cleanup imm_dict
        #=====================================================================
        orgs   = list(kwargs.imm_dict.orgs.keys())
        kwargs = ezfunctions.remove_duplicates(orgs, ['wizard'], kwargs)
        ezfunctions.create_yaml(orgs, kwargs)
        #=====================================================================
        # Loop thru Orgs and Install OS
        #=====================================================================
        if kwargs.args.deployment_type == 'azure_stack': kwargs = ci.wizard('windows').azure_stack_prep(kwargs)
        for org in orgs:
            kwargs.org = org
            kwargs = isight.imm('os_install').os_install(kwargs)
        #=====================================================================
        # Create YAML Files
        #=====================================================================
        ezfunctions.create_yaml(orgs, kwargs)
    #=========================================================================
    # Configure the Operating System
    #=========================================================================
    elif kwargs.args.deployment_step == 'os_configuration':
        #=====================================================================
        # Loop Through the Orgs
        #=====================================================================
        orgs = list(kwargs.imm_dict.orgs.keys())
        for org in orgs:
            #=================================================================
            # merge os_configuration with server_profiles
            #=================================================================
            for i in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
                for k, v in i.items(): kwargs.server_profiles[i.name][k] = v
            kwargs.repo_server = kwargs.imm_dict.orgs[kwargs.org].wizard.repository_server
            #=================================================================
            # Configure Virtualization Environment
            #=================================================================
            kwargs = vsphere.api('esx').esx(kwargs)
            kwargs = vsphere.api('powercli').powercli(kwargs)
    pcolor.Green(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...')
    pcolor.Green(f'\n{"-"*108}\n')
    sys.exit(0)

if __name__ == '__main__':
    main()
