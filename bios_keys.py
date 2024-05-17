#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, isight
    from dotmap import DotMap
    from stringcase import snakecase
    import argparse, json, os, urllib3, yaml
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
    kwargs      = DotMap()
    parser      = argparse.ArgumentParser(description ='Intersight BIOS Key Check Module')
    parser      = ezfunctions.base_arguments(parser)
    kwargs.args = parser.parse_args()
    return kwargs
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
    # bios_output = DotMap(sorted(kwargs.ezdata.bios.allOf[1].properties.items()))
    # print(json.dumps(bios_output, indent=4))
    # exit()
    keys      = list(kwargs.ezdata.bios.allOf[1].properties.keys())
    bios_keys = []
    for e in keys: bios_keys.append(kwargs.ezdata.bios.allOf[1].properties[e].intersight_api)
    bios_keys.extend([
        'AccountMoid', 'Ancestors', 'ClassId', 'CreateTime', 'Description', 'DomainGroupMoid', 'ModTime', 'Moid', 'Name', 'ObjectType', 'Organization',
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
    print(json.dumps(bios, indent=4))
    print(yaml.dump(defaults.toDict(), Dumper=ezfunctions.yaml_dumper, default_flow_style=False))

if __name__ == '__main__':
    main()
