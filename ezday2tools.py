#!/usr/bin/env python3
"""Day 2 Tools - 
This Script is built to Perform Day 2 Configuration Tasks.
The Script uses argparse to take in the following CLI arguments:
    -a  or --intersight-api-key-id: The Intersight API key id for HTTP signature scheme.
    -d  or --dir:                   Base Directory to use for creation of the YAML Configuration Files.
    -dl or --debug-level:           The Debug Level to Run for Script Output
                                      1. Shows the api request response status code
                                      5. Shows URL String + Lower Options
                                      6. Adds Results + Lower Options
                                      7. Adds json payload + Lower Options
                                    Note: payload shows as pretty and straight to check for stray object types like Dotmap and numpy
    -f  or --intersight-fqdn:       The Intersight hostname for the API endpoint. The default is intersight.com.
    -fi or --full-inventory:        Used in conjunction with srv-inventory to pull more indepth inventory.
    -i  or --ignore-tls:            Ignore TLS server-side certificate verification.  Default is False.
    -k  or --intersight-secret-key: Name of the file containing The Intersight secret key for the HTTP signature scheme.
    -p  or --process:               Which Process to run with the Script.  Options are:  
                                      1. add_policies
                                      2. add_vlans
                                      3. audit_logs
                                      4. clone_policies
                                      5. hcl_inventory
                                      6. inventory
                                      7. server_identities
    -v or --api-key-v3:             Flag for API Key Version 3.
    -wb or --workbook:              The Source Workbook for hcl_inventory
    -y or --yaml-file:              The input YAML File.
"""
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
excel_workbook = None
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import day2tools, ezfunctions, isight, pcolor
    from dotmap import DotMap
    import argparse, codecs, json, os, re
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

#=============================================================================
# Parse Arguments
#=============================================================================
def cli_arguments():
    parser = argparse.ArgumentParser(description ='Intersight Easy IMM Deployment Module')
    parser = ezfunctions.base_arguments(parser)
    parser.add_argument(
        '-fi', '--full-identities', action = 'store_true',
        help = 'Used in conjunction with server_identities to pull more indepth Identity inventory.')
    parser.add_argument(
        '-p', '--process', default = 'EMPTY',
        help = 'Which Process to run with the Script.  Options are:  '\
            '1. add_policies '\
            '2. add_vlan '\
            '3. audit_logs '\
            '4. clone_policies '\
            '5. hcl_inventory '\
            '6. inventory '\
            '7. server_identities.')
    parser.add_argument('-wb', '--workbook', default = 'Settings.xlsx', help = 'The source Workbook.')
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
    kwargs = isight.api('organization').all_organizations(kwargs)
    #==============================================
    # Build Deployment Library
    #==============================================
    if not re.search('^add_policies|add_vlans|audit_logs|clone_policies|hcl_status|inventory|server_identities$', kwargs.args.process):
        kwargs.jdata = DotMap(
            default = 'server_identities',
            description = f'Select the Process to run:\n'\
                '  * add_policies: Update Policies attached to chassis, domain, server profiles/templates within the same organization or from a shared organization.\n'\
                '  * add_vlans: Function to add a VLAN to existing VLAN Poilcy and Ethernet Network Group Policies.  Optionally can also create LAN Connectivity Policies.\n'\
                '  * audit_logs: Function to Get List of Users that have logged into the Account and performed actions/changes.\n'\
                '  * clone_policies: Function to clone policies from one Organization to another.\n'\
                '  * hcl_status: Function to take UCS inventory from vCenter and validate the status of the HCL VIB.\n'\
                '  * inventory: Function to Create a Spreadsheet with inventory for Domains, Chassis, Servers.\n'\
                '  * server_identities: Function to get WWNN/WWPN and MAC identities.  By default it only gathers the fibre-channel identities. To get full identities list add the `-fi` option at the CLI.\n',
            enum = ['add_policies', 'add_vlans', 'audit_logs', 'clone_policies', 'hcl_status', 'inventory', 'server_identities'],
            title = 'Day2Tools Process', type = 'string')
        kwargs.args.process = ezfunctions.variable_prompt(kwargs)
    kwargs = isight.api('organization').all_organizations(kwargs)
    #==============================================
    # Send Notification Message
    #==============================================
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.LightGray(f'  Begin Function: {kwargs.args.process}.')
    pcolor.LightGray(f'\n{"-"*108}\n')
    if not kwargs.args.json_file == None:
        if not os.path.isfile(kwargs.args.json_file):
            pcolor.Red(f'\n{"-"*108}\n')
            pcolor.Red(f'  !!!ERROR!!!\n  Did not find the file {kwargs.args.json_file}.')
            pcolor.Red(f'  Please Validate that you have specified the correct file and path.')
            pcolor.Red(f'\n{"-"*108}\n')
            len(False); sys.exit(1)
        else:
            def try_utf8(json_file):
                try:
                    f = codecs.open(json_file, encoding='utf-8', errors='strict')
                    for line in f: line = line
                    pcolor.Green("Valid utf-8"); return 'Good'
                except UnicodeDecodeError:
                    pcolor.Green("invalid utf-8"); return None
            if 'hcl_inventory' in kwargs.args.process:
                if try_utf8(kwargs.args.json_file) is None:
                    json_file   = open(kwargs.args.json_file, 'r', encoding='utf-16')
                else: json_file = open(kwargs.args.json_file, 'r')
            else: json_file = open(kwargs.args.json_file, 'r')
            kwargs.json_data = json.load(json_file)
        if kwargs.args.process == 'hcl_inventory':
            json_data = []
            for e in kwargs.json_data:
                if 'Cisco' in e['Hostname']['Manufacturer']: json_data.append(DotMap(e))
            kwargs.json_data = json_data
    process = kwargs.args.process
    eval(f'day2tools.tools(process).{process}(kwargs)')
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.LightGray(f'  End Function: {kwargs.args.process}.')
    pcolor.LightGray(f'\n{"-"*108}\n')

if __name__ == '__main__':
    main()
