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
                                      3. clone_policies
                                      4. hcl_inventory
                                      5. hcl_status
                                      6. server_inventory
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
    from json_ref_dict import materialize, RefDict
    from pathlib import Path
    import argparse, codecs, json, logging, os, platform, re, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

#=================================================================
# Parse Arguments
#=================================================================
def cli_arguments():
    Parser = argparse.ArgumentParser(description = 'Intersight Converged Infrastructure Deployment Module')
    Parser.add_argument(
        '-a', '--intersight-api-key-id', default = os.getenv('intersight_api_key_id'),
        help='The Intersight API key id for HTTP signature scheme.')
    Parser.add_argument(
        '-d', '--dir', default = 'Intersight',
        help = 'The Directory to use for the Creation of the Terraform Files.')
    Parser.add_argument(
        '-dl', '--debug-level', default = 0,
        help    = 'The Amount of Debug output to Show:'\
            '1. Shows the api request response status code'
            '5. Show URL String + Lower Options'\
            '6. Adds Results + Lower Options'\
            '7. Adds json payload + Lower Options'\
            'Note: payload shows as pretty and straight to check for stray object types like Dotmap and numpy')
    Parser.add_argument(
        '-f', '--intersight-fqdn', default = 'intersight.com',
        help = 'The Intersight hostname for the API endpoint. The default is intersight.com.')
    Parser.add_argument(
        '-fi', '--full-inventory', action = 'store_true',
        help = 'Used in conjunction with srv-inventory to pull more indepth inventory.')
    Parser.add_argument(
        '-i', '--ignore-tls', action = 'store_false',
        help = 'Ignore TLS server-side certificate verification.  Default is False.')
    Parser.add_argument(
        '-j', '--json-file', default = None,
        help = 'Input JSON File for HCL Inventory.')
    Parser.add_argument(
        '-k', '--intersight-secret-key', default = os.getenv('intersight_secret_key'),
        help = 'Name of the file containing The Intersight secret key or contents of the secret key in environment.')
    Parser.add_argument(
        '-p', '--process', default = 'EMPTY',
        help = 'Which Process to run with the Script.  Options are:  '\
            '1. add_policies '\
            '2. add_vlan '\
            '3. clone_policies '\
            '4. hcl_inventory '\
            '5. server_inventory.')
    Parser.add_argument(
        '-v', '--api-key-v3', action = 'store_true', help = 'Flag for API Key Version 3.')
    Parser.add_argument(
        '-wb', '--workbook', default = 'Settings.xlsx', help = 'The source Workbook.')
    Parser.add_argument(
        '-y', '--yaml-file', default = None,  help = 'The input YAML File.')
    kwargs = DotMap()
    kwargs.args = Parser.parse_args()
    return kwargs

def main():
    #==============================================
    # Configure logger
    #==============================================
    script_name = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    dest_dir = f"{Path.home()}{os.sep}Logs"
    dest_file = script_name + '.log'
    if not os.path.exists(dest_dir): os.mkdir(dest_dir)
    if not os.path.exists(os.path.join(dest_dir, dest_file)): os.system(f'type nul >> {os.path.join(dest_dir, dest_file)}')
    FORMAT = '%(asctime)-15s [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
    logging.basicConfig(
        filename=f"{dest_dir}{os.sep}{script_name}.log",
        filemode='a', format=FORMAT, level=logging.DEBUG)
    logger = logging.getLogger('openapi')
    #==============================================
    # Build kwargs
    #==============================================
    kwargs = cli_arguments()
    #==============================================
    # Determine the Script Path
    #==============================================
    kwargs.script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
    script_path        = kwargs.script_path
    args_dict          = vars(kwargs.args)
    for k,v in args_dict.items():
        if type(v) == str: os.environ[k] = v
    if kwargs.args.intersight_secret_key:
        if '~' in kwargs.args.intersight_secret_key:
            kwargs.args.intersight_secret_key = os.path.expanduser(kwargs.args.intersight_secret_key)
    kwargs.home          = Path.home()
    kwargs.logger        = logger
    kwargs.op_system     = platform.system()
    kwargs.imm_dict.orgs = DotMap()

    #================================================
    # Import Stored Parameters
    #================================================
    ezdata          = DotMap(materialize(RefDict(f'{script_path}{os.sep}variables{os.sep}easy-imm.json')))
    kwargs.ezdata   = DotMap(ezdata['components']['schemas'])
    kwargs.ezwizard = DotMap(ezdata['components']['wizard'])
    #==============================================
    # Get Intersight Configuration
    # - intersight_api_key_id
    # - intersight_fqdn
    # - intersight_secret_key
    #==============================================
    kwargs         = ezfunctions.intersight_config(kwargs)
    kwargs.args.url= 'https://%s' % (kwargs.args.intersight_fqdn)
    #==============================================
    # Build Deployment Library
    #==============================================
    if not re.search('^add_polices|add_vlans|clone_policies|hcl_inventory|server_inventory$', kwargs.args.process):
        kwargs.jdata = DotMap(
            default = 'server_inventory',
            description = f'Select the Process to run:\n  * add_policies: Function to add policies to profiles.\n'\
                  '  * add_vlans: Function to add a VLAN to existing VLAN and Ethernet Network Group Policies and Create LAN Connectivity Policy.\n'\
                  '  * clone_policies: Function to clone policies from one Organization to another.\n'\
                  '  * hcl_inventory: Function to clone policies from one Organization to another.\n'\
                  '  * server_inventory: Function to clone policies from one Organization to another.\n',
            enum = ['add_policies', 'add_vlans', 'clone_policies', 'hcl_inventory', 'server_inventory'],
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
