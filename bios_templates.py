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
class yaml_dumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(yaml_dumper, self).increase_indent(flow, False)
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
    keys      = list(kwargs.ezdata.bios.allOf[1].properties.keys())
    bios_keys = DotMap()
    bios_json = DotMap()
    bios_yaml = DotMap()
    for e in keys: bios_keys[kwargs.ezdata.bios.allOf[1].properties[e].intersight_api] = e
    bkeys         = list(bios_keys.keys())
    kwargs.method = 'get'
    kwargs.names  = list(kwargs.org_names.keys()) + ['5ddfd9ff6972652d31ee6582']
    kwargs.org    = 'default'
    kwargs.uri    = kwargs.ezdata.bios.intersight_uri
    kwargs        = isight.api('multi_org').calls(kwargs)
    for e in list(kwargs.results):
        if e.Organization.Moid == '5ddfd9ff6972652d31ee6582':
            jdict = DotMap(); ydict = DotMap()
            for k,v in e.items():
               if k in bkeys and v != 'platform-default':
                   jdict[k] = v
                   ydict[bios_keys[k]] = v
            bios_json[e.Name] = jdict
            bios_yaml[e.Name] = ydict
    bios_json = DotMap(sorted(bios_json.items()))
    bios_yaml = DotMap(sorted(bios_yaml.items()))
    print(json.dumps(bios_json, indent=4))
    print(yaml.dump(bios_yaml.toDict(), Dumper = yaml_dumper, default_flow_style=False))
if __name__ == '__main__':
    main()
