#!/usr/bin/env python3
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import build, ezfunctions, imm, isight, lansan, pcolor, policies, pools, profiles, questions, quick_start, tf, validating
    from collections import OrderedDict
    from copy import deepcopy
    from dotmap import DotMap
    from json_ref_dict import materialize, RefDict
    from pathlib import Path
    import argparse, base64, jinja2, json, os, logging, platform, re, requests, urllib3, uuid, lxml, yaml
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")

#=================================================================
# Function: Parse Arguments
#=================================================================
def cli_arguments():
    Parser = argparse.ArgumentParser(description='Intersight Converged Infrastructure Deployment Module')
    Parser.add_argument(
        '-a', '--intersight-api-key-id', default=os.getenv('intersight_api_key_id'),
        help='The Intersight API key id for HTTP signature scheme.')
    Parser.add_argument(
        '-d', '--dir', default = 'Intersight',
        help = 'The Directory to use for the Creation of the YAML Configuration Files.')
    Parser.add_argument(
        '-dl', '--debug-level', default =0,
        help ='The Amount of Debug output to Show: '\
            '1. Shows the api request response status code '\
            '5. Show URL String + Lower Options '\
            '6. Adds Results + Lower Options '\
            '7. Adds json payload + Lower Options '\
            'Note: payload shows as pretty and straight to check for stray object types like Dotmap and numpy')
    Parser.add_argument(
        '-f', '--intersight-fqdn', default='intersight.com',
        help='The Intersight hostname for the API endpoint. The default is intersight.com.')
    Parser.add_argument(
        '-i', '--ignore-tls', action='store_false',
        help='Ignore TLS server-side certificate verification.  Default is False.')
    Parser.add_argument( '-ilp', '--local-user-password-1',   help='Intersight Managed Mode Local User Password 1.' )
    Parser.add_argument( '-ilp2','--local-user-password-2',   help='Intersight Managed Mode Local User Password 2.' )
    Parser.add_argument( '-imm', '--imm-transition-password', help='IMM Transition Tool Password.' )
    Parser.add_argument( '-isa', '--snmp-auth-password-1',    help='Intersight Managed Mode SNMP Auth Password.' )
    Parser.add_argument( '-isp', '--snmp-privacy-password-1', help='Intersight Managed Mode SNMP Privilege Password.' )
    Parser.add_argument(
        '-k', '--intersight-secret-key', default='~/Downloads/SecretKey.txt',
        help='Name of the file containing The Intersight secret key or contents of the secret key in environment.')
    Parser.add_argument( '-np',  '--netapp-password',  help='NetApp Login Password.' )
    Parser.add_argument( '-nsa', '--netapp-snmp-auth', help='NetApp SNMP Auth Password.' )
    Parser.add_argument( '-nsp', '--netapp-snmp-priv', help='NetApp SNMP Privilege Password.' )
    Parser.add_argument( '-nxp', '--nexus-password',   help='Nexus Login Password.' )
    Parser.add_argument( '-p', '--pure-storage-password',   help='Pure Storage Login Password.' )
    Parser.add_argument( '-psa', '--pure-storage-snmp-auth', help='Pure Storage SNMP Auth Password.' )
    Parser.add_argument( '-psp', '--pure-storage-snmp-priv', help='Pure Storage SNMP Privilege Password.' )
    Parser.add_argument( '-pxp', '--proxy-password',   help='Proxy Password.' )
    Parser.add_argument(
        '-s', '--deployment-step', default ='initial', required=True,
        help ='The steps in the proceedure to run. Options Are: '\
            '1. initial '
            '2. servers '\
            '3. luns '\
            '4. operating_system '\
            '5. os_configuration ')
    Parser.add_argument(
        '-t', '--deployment-type', default ='imm_domain', required=True,
        help ='Infrastructure Deployment Type. Options Are: '\
            '1. azurestack '
            '2. flashstack '\
            '3. flexpod '\
            '3. imm_domain '\
            '4. imm_standalone ')
    Parser.add_argument( '-v', '--api-key-v3', action='store_true', help='Flag for API Key Version 3.' )
    Parser.add_argument( '-vep', '--vmware-esxi-password',          help='VMware ESXi Root Login Password.' )
    Parser.add_argument( '-vvp', '--vmware-vcenter-password',       help='VMware vCenter Admin Login Password.' )
    Parser.add_argument( '-wap', '--windows-admin-password',        help='Windows Administrator Login Password.' )
    Parser.add_argument( '-wdp', '--windows-domain-password',       help='Windows Domain Registration Login Password.' )
    Parser.add_argument( '-y', '--yaml-file',                       help = 'The input YAML File.' )
    kwargs = DotMap()
    kwargs.args = Parser.parse_args()
    return kwargs


def main():
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
    kwargs.script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
    kwargs.args.dir   = os.path.join(Path.home(), kwargs.args.yaml_file.split('/')[0])
    args_dict = vars(kwargs.args)
    for k,v in args_dict.items():
        if type(v) == str:
            if v: os.environ[k] = v
    if kwargs.args.intersight_secret_key:
        if '~' in kwargs.args.intersight_secret_key:
            kwargs.args.intersight_secret_key = os.path.expanduser(kwargs.args.intersight_secret_key)
    kwargs.deployment_type= kwargs.args.deployment_type
    kwargs.home           = Path.home()
    kwargs.logger         = logger
    kwargs.op_system      = platform.system()
    kwargs.imm_dict.orgs  = DotMap()
    #=====================================================
    # Test Repo URL for NetAppNasPlugin
    #=====================================================
    kwargs.repo_server = 'imm-transition.rich.ciscolabs.com'
    for v in ['imm_transition_password', 'windows_admin_password', 'windows_domain_password']:
        kwargs.sensitive_var = v
        kwargs  = ezfunctions.sensitive_var_value(kwargs)
        kwargs[v]=kwargs.var_value
    #windows_admin_password = base64.b64encode(bytes(kwargs['windows_admin_password'], 'utf-8'))
    windows_admin_password = kwargs['windows_admin_password'].encode('utf-8').hex()
    print(windows_admin_password)
    exit()
    templateLoader = jinja2.FileSystemLoader(searchpath='./')
    templateEnv    = jinja2.Environment(loader=templateLoader, autoescape=True)
    template       = templateEnv.get_template('AzureStackHCI.xml')
    jargs = DotMap(
        administratorPassword = windows_admin_password,
        domain                = 'ucs-spaces.lab',
        domainAdministrator   = 'hciadmin@ucs-spaces.lab',
        domainPassword        = kwargs['windows_domain_password'],
        ouArgument            = '',
        organization          = 'Cisco Systems',
        organizationalUnit    = 'CN=Computers,DC=ucs-spaces,DC=lab',
        sharePath             = '\\\\win22-jump.ucs-spaces.lab\\reminst',
        # Language
        inputLocale           = '',
        languagePack          = 'en-Us',
        layeredDriver         = '',
        secondaryLanguage     = ''
    )
    print(json.dumps(jargs.toDict(), indent=4))
    exit()
    jargs = jargs.toDict()
    jtemplate = template.render(kwargs=jargs)
    for x in ['LayeredDriver', 'UILanguageFallback']:
        if f'            <{x}></{x}>' in jtemplate: jtemplate = jtemplate.replace(f'            <{x}></{x}>\n', '')
    file  = open('./AzureStackHCI2.xml', 'w')
    file.write(jtemplate)
    file.close()
    s = requests.Session()
    data = json.dumps({'username':'admin','password':kwargs['imm_transition_password']})
    url = f'https://{kwargs.repo_server}'
    try: r = s.post(data = data, headers= {'Content-Type': 'application/json'}, url = f'{url}/api/v1/login', verify = False)
    except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}\n'); sys.exit(1)
    if not r.status_code == 200: prRed(r.text); sys.exit(1)
    jdata = json.loads(r.text)
    token = jdata['token']
    file = open('./AzureStackHCI2.xml', 'rb')
    files = {'file': file}
    values = {'uuid':str(uuid.uuid4())}
    try: r = s.post(
        url = f'{url}/api/v1/repo/actions/upload?use_chunks=false', headers={'x-access-token': token}, verify=False, data=values, files=files)
    except requests.exceptions.ConnectionError as e:
        pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
    if not r.ok: prRed(r.text); sys.exit(1)
    for uri in ['logout']:
        try: r = s.get(url = f'{url}/api/v1/{uri}', headers={'x-access-token': token}, verify=False)
        except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
        if 'repo' in uri: jdata = json.loads(r.text)
        if not r.status_code == 200: prRed(r.text); sys.exit(1)
    file.close()
    os.remove('./AzureStackHCI2.xml')

if __name__ == '__main__':
    main()
