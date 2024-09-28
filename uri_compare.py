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
    kwargs.policies_list  = []
    kwargs.pools_list     = []
    kwargs.templates_list = kwargs.profiles_list
    for k, v in kwargs.ezdata.items():
        if v.intersight_type == 'policies' and not '.' in k: kwargs.policies_list.append(k)
        elif v.intersight_type == 'pools' and not '.' in k: kwargs.pools_list.append(k)
    kwargs.org = 'default'
    plist = kwargs.pools_list + kwargs.policies_list + ['profiles.domain', 'profiles.chassis', 'profiles.server']
    pcolor.Yellow('')
    plist.remove('firmware_authenticate')
    for e in plist:
        title = ezfunctions.mod_pol_description((e.replace('_', ' ')).title())
        kwargs.api_filter = 'ignore'
        kwargs.uri        = kwargs.ezdata[e].intersight_uri
        kwargs            = isight.api(e).calls(kwargs)
        pcolor.Yellow(f'result_length={len(kwargs.results)}, Checking {title}, uri: {kwargs.uri}')
        uri_dict          = DotMap()
        uri_moids         = sorted([d.Moid for d in kwargs.results])
        for d in kwargs.results: uri_dict[d.Moid] = d
        kwargs.api_filter = f"ObjectType eq '{kwargs.ezdata[e].object_type}'"
        kwargs.uri        = 'search/SearchItems'
        kwargs            = isight.api(e).calls(kwargs)
        pcolor.Yellow(f'result_length={len(kwargs.results)}, Checking {title}, uri: {kwargs.uri}')
        search_dict       = DotMap()
        search_moids      = sorted([d.Moid for d in kwargs.results])
        for d in kwargs.results: search_dict[d.Moid] = d
        difference = set(uri_moids).symmetric_difference(set(search_moids))
        if len(difference) > 0:
            pcolor.LightGray(f'\n{"-"*108}\n')
            pcolor.LightGray(f'Differences between the Results\n')
            for d in difference:
                if d in uri_moids:
                    pcolor.Yellow(f'uri_result: name: {uri_dict[d].Name}, org: {kwargs.org_names[uri_dict[d].Organization.Moid]}, moid: {d}')
                elif d in search_dict:
                    pcolor.Yellow(f'search_result: name: {search_dict[d].Name}, org: {kwargs.org_names[search_dict[d].Organization.Moid]}, moid: {d}')
            pcolor.LightGray(f'\n{"-"*108}\n')

if __name__ == '__main__':
    main()
