#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, isight, pcolor
    from dotmap import DotMap
    from stringcase import snakecase
    import argparse, json, os, re, urllib3, yaml
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=================================================================
# Function: Parse Arguments
#=================================================================
def cli_arguments():
    parser = argparse.ArgumentParser(description ='Intersight BIOS Key Check Module')
    parser = ezfunctions.base_arguments(parser)
    return DotMap(args = parser.parse_args())
#=================================================================
# Function: Main Script
#=================================================================
def main():
    #=============================================================
    # Configure Base Module Setup
    #=============================================================
    kwargs = cli_arguments()
    kwargs = ezfunctions.base_script_settings(kwargs)
    kwargs = isight.api('organization').all_organizations(kwargs)
    #=============================================================
    # Sorting BIOS Tokens from easy-imm.json
    #=============================================================
    keys      = list(kwargs.ezdata.bios.allOf[1].properties.keys())
    bios_keys = []
    for e in keys: bios_keys.append(kwargs.ezdata.bios.allOf[1].properties[e].intersight_api)
    bios_keys.extend([
        'AccountMoid', 'Ancestors', 'ClassId', 'CreateTime', 'Description', 'DomainGroupMoid', 'ModTime', 'Moid', 'Name', 'ObjectType',
        'Organization', 'Owners', 'PermissionResources', 'Profiles', 'SharedScope', 'Tags'])
    kwargs.method   = 'get'
    kwargs.names    = list(kwargs.org_names.keys())
    kwargs.org      = 'default'
    kwargs.uri      = kwargs.ezdata.bios.intersight_uri
    kwargs          = isight.api('multi_org').calls(kwargs)
    api_docs        = json.load(open(os.path.join(kwargs.script_path, 'variables', 'intersight-openapi.json'), 'r'))
    intersight_bios = DotMap(api_docs['components']['schemas'])['bios.Policy'].allOf[1].properties
    bios            = DotMap()
    defaults        = DotMap()
    for k in list(kwargs.results[0].keys()):
        if not k in bios_keys:
            bios[snakecase(k)] = DotMap(
                type = 'string', default = intersight_bios[k].default, description = f'Default is `platform-default`.  {intersight_bios[k].description}',
                intersight_api = k, enum = intersight_bios[k].enum, title = snakecase(k))
            defaults[snakecase(k)] = intersight_bios[k].default
    pcolor.LightGray(f'{"-"*54}')
    pcolor.Yellow('New Keys:\n')
    if len(bios) > 0:
        pcolor.Yellow(json.dumps(bios, indent=4))
        pcolor.Yellow(yaml.dump(defaults.toDict(), Dumper=ezfunctions.yaml_dumper, default_flow_style=False))
    else: pcolor.Yellow('None')
    bkeys = list(kwargs.results[0].keys())
    pcolor.LightGray(f'\n{"-"*54}')
    pcolor.Yellow('Removed Keys:\n')
    rcount = 0
    for k in bios_keys:
        if not k in bkeys and k != 'bios_template': pcolor.Yellow(k); rcount += 1
    if rcount == 0: pcolor.Yellow('None')
    pcolor.LightGray(f'\n{"-"*54}')
    pcolor.Yellow('Description Keys:\n')
    descr = kwargs.ezdata.bios.allOf[1].description
    dsplit = descr.split('\n')
    dkeys = []
    for e in dsplit:
        if re.search(r'\* ([a-zA-Z0-9\_]+)$', e): dkeys.append(re.search(r'\* ([a-zA-Z0-9\_]+)$', e).group(1))
    keys.remove('bios_template')
    for e in keys:
        if not e in dkeys: pcolor.Yellow(e)
    for k,v in kwargs.ezdata.bios.allOf[1].properties.items():
        vkeys = list(v.keys())
        if 'enum' in vkeys and k != 'bios_template':
            for e in intersight_bios[v.intersight_api].enum:
                if not e in v.enum:
                    pcolor.LightGray(f'{"-"*54}')
                    pcolor.Yellow(''); pcolor.Yellow(k); pcolor.Yellow('')
                    pcolor.Yellow(f'intersight enum is:')
                    pcolor.Yellow(json.dumps(intersight_bios[v.intersight_api].enum, indent=4))
                    pcolor.Yellow(f'easy-imm enum is:')
                    pcolor.Yellow(json.dumps(v.enum, indent=4))
            if not intersight_bios[v.intersight_api].default == v.default:
                pcolor.LightGray(f'{"-"*54}')
                pcolor.Yellow(''); pcolor.Yellow(k); pcolor.Yellow('')
                pcolor.Yellow(f'intersight default is:')
                pcolor.Yellow(intersight_bios[v.intersight_api].default)
                pcolor.Yellow(f'easy-imm default is:')
                pcolor.Yellow(v.default)

if __name__ == '__main__':
    main()
