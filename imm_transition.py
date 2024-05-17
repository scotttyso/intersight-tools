#!/usr/bin/env python3
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, isight, pcolor
    from dotmap import DotMap
    from pathlib import Path
    import argparse, jinja2, json, os, requests, urllib3, uuid
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")

#=================================================================
# Function: Parse Arguments
#=================================================================
def cli_arguments():
    kwargs = DotMap()
    parser = argparse.ArgumentParser(description ='Intersight Easy IMM Deployment Module')
    parser = ezfunctions.base_arguments(parser)
    parser = ezfunctions.base_arguments_ezimm_sensitive_variables(parser)
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
    #==============================================
    # Determine the Script Path
    #==============================================
    kwargs.args.dir        = os.path.join(Path.home(), kwargs.args.yaml_file.split('/')[0])
    kwargs.deployment_type = kwargs.args.deployment_type
    #=====================================================
    # Test Repo URL for NetAppNasPlugin
    #=====================================================
    kwargs.repo_server = 'imm-transition.rich.ciscolabs.com'
    for v in ['imm_transition_password', 'windows_admin_password', 'windows_domain_password']:
        kwargs.sensitive_var = v
        kwargs  = ezfunctions.sensitive_var_value(kwargs)
        kwargs[v]=kwargs.var_value
    tloader  = jinja2.FileSystemLoader(searchpath=f'{kwargs.script_path}{os.pathsep}examples{os.pathsep}azurestack_hci')
    tenviro  = jinja2.Environment(loader=tloader, autoescape=True)
    template = tenviro.get_template('AzureStackHCI.xml')
    jargs = DotMap(
        administratorPassword = kwargs['windows_admin_password'],
        domain                = kwargs.imm_dict.wizard.domain,
        domainAdministrator   = kwargs.imm_dict.wizard.administrator,
        domainPassword        = kwargs['windows_domain_password'],
        ouArgument            = '',
        organization          = 'Cisco Systems',
        organizationalUnit    = kwargs.imm_dict.wiard.organizational_unit,
        sharePath             = kwargs.imm_dict.wiard.share_path,
        # Language
        inputLocale           = '',
        languagePack          = 'en-Us',
        layeredDriver         = '',
        secondaryLanguage     = ''
    )
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
    if not r.status_code == 200: pcolor.Red(r.text); sys.exit(1)
    jdata = json.loads(r.text)
    token = jdata['token']
    file = open('./AzureStackHCI2.xml', 'rb')
    files = {'file': file}
    values = {'uuid':str(uuid.uuid4())}
    try: r = s.post(
        url = f'{url}/api/v1/repo/actions/upload?use_chunks=false', headers={'x-access-token': token}, verify=False, data=values, files=files)
    except requests.exceptions.ConnectionError as e:
        pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
    if not r.ok: pcolor.Red(r.text); sys.exit(1)
    for uri in ['logout']:
        try: r = s.get(url = f'{url}/api/v1/{uri}', headers={'x-access-token': token}, verify=False)
        except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
        if 'repo' in uri: jdata = json.loads(r.text)
        if not r.status_code == 200: pcolor.Red(r.text); sys.exit(1)
    file.close()
    os.remove('./AzureStackHCI2.xml')

if __name__ == '__main__':
    main()
