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
    from classes import claim_device, ezfunctions, pcolor
    from dotmap import DotMap
    from json_ref_dict import materialize, RefDict
    from pathlib import Path
    import argparse, json, logging, os, re, traceback, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")

class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)

#=================================================================
# Parse Arguments
#=================================================================
def cli_arguments():
    Parser = argparse.ArgumentParser(description='Intersight Converged Infrastructure Deployment Module')
    Parser.add_argument(
        '-a', '--intersight-api-key-id', default=os.getenv('intersight_api_key_id'),
        help='The Intersight API key id for HTTP signature scheme.')
    Parser.add_argument(
        '-f', '--intersight-fqdn', default='intersight.com',
        help='The Intersight hostname for the API endpoint. The default is intersight.com.')
    Parser.add_argument(
        '-i', '--ignore-tls', action='store_false',
        help='Ignore TLS server-side certificate verification.  Default is False.')
    Parser.add_argument( '-ilp', '--local-user-password-1',   help='Intersight Managed Mode Local User Password 1.' )
    Parser.add_argument(
        '-k', '--intersight-secret-key', default='~/Downloads/SecretKey.txt',
        help='Name of the file containing The Intersight secret key or contents of the secret key in environment.')
    Parser.add_argument('-y', '--yaml-file', help = 'The input YAML File.', required= True)
    kwargs = DotMap()
    kwargs.args = Parser.parse_args()
    return kwargs

#=================================================================
# The Main Module
#=================================================================
def main():
    return_code = 0
    #==============================================
    # Configure logger and Build kwargs
    #==============================================
    script_name = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    dest_dir = f"{Path.home()}{os.sep}Logs"
    dest_file = script_name + '.log'
    if not os.path.exists(dest_dir): os.mkdir(dest_dir)
    if not os.path.exists(os.path.join(dest_dir, dest_file)): 
        create_file = f'type nul >> {os.path.join(dest_dir, dest_file)}'; os.system(create_file)
    FORMAT = '%(asctime)-15s [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
    logging.basicConfig( filename=f"{dest_dir}{os.sep}{script_name}.log", filemode='a', format=FORMAT, level=logging.DEBUG )
    logger = logging.getLogger('openapi')
    kwargs = cli_arguments()

    #==============================================
    # Determine the Script Path
    #==============================================
    kwargs.script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
    kwargs.args.dir    = os.path.join(Path.home(), kwargs.args.yaml_file.split('/')[0])
    args_dict          = vars(kwargs.args)
    for k,v in args_dict.items():
        if type(v) == str:
            if v: os.environ[k] = v
    if kwargs.args.intersight_secret_key:
        if '~' in kwargs.args.intersight_secret_key:
            kwargs.args.intersight_secret_key = os.path.expanduser(kwargs.args.intersight_secret_key)
    kwargs.deployment_type ='claim_devices'
    kwargs.home            = Path.home()
    kwargs.logger          = logger

    #================================================
    # Import Stored Parameters
    #================================================
    ezdata         = materialize(RefDict(f'{script_path}{os.sep}variables{os.sep}easy-imm.json', 'r', encoding="utf8"))
    kwargs.ez_tags = {'Key':'ezci','Value':ezdata['info']['version']}
    kwargs.ezdata  = DotMap(ezdata['components']['schemas'])
    #==============================================
    # Add Sensitive Variables to Environment
    #==============================================
    arg_dict = vars(kwargs.args)
    for e in list(arg_dict.keys()):
        if re.search('cco|password|intersight', e):
            if not arg_dict[e] == None: os.environ[e] = arg_dict[e]
    #==============================================
    # Send Notification Message
    #==============================================
    pcolor.LightGray(f'\n{"-"*91}\n')
    pcolor.LightGray(f'  * Begin Device Claims.')
    pcolor.LightGray(f'\n{"-"*91}\n')
    yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
    kwargs.yaml = DotMap(yaml.safe_load(yfile))
    #==============================================
    # Get Intersight Configuration
    # - intersight_api_key_id
    # - intersight_fqdn
    # - intersight_secret_key
    #==============================================
    kwargs         = ezfunctions.intersight_config(kwargs)
    kwargs.args.url= 'https://%s' % (kwargs.args.intersight_fqdn)

    try:
        kwargs.sensitive_var  = 'local_user_password_1'
        kwargs                = ezfunctions.sensitive_var_value(kwargs)
        kwargs.yaml.password  = kwargs.var_value
        kwargs = claim_device.claim_targets(kwargs)
    except Exception as err:
        print("Exception:", str(err))
        print('-' * 60)
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)
        if kwargs.return_code:
            sys.exit(kwargs.return_code)
        else: sys.exit(return_code)

    pcolor.LightGray(f'\n{"-"*91}\n')
    pcolor.LightGray(f'  * Completed Device Claims.')
    pcolor.LightGray(f'\n{"-"*91}\n')
    sys.exit(1)
if __name__ == '__main__':
    main()
