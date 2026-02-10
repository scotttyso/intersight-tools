#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, isight, pcolor
    from dotmap import DotMap
    import argparse, json, os, re, urllib3
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
    parser = argparse.ArgumentParser(description ='Intersight Server Pool Qualification Lists')
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
    kwargs.org = 'default'
    for e in ['ChassisDescriptors', 'CpuEndpointDescriptors', 'GpuEndpointDescriptors', 'SwitchDescriptors']:
        pcolor.LightGray(f'\n{"="*20} {e} {"="*20}\n')
        kwargs = kwargs | DotMap(api_filter = 'ignore', method = 'get', uri = f'capability/{e}')
        kwargs = isight.api('capability').calls(kwargs)
        if re.search('(CpuEndpointDescriptors|GpuEndpointDescriptors)', e):
            models = sorted([e.Pid for e in kwargs.results])
        else:
            models = sorted([e.Model for e in kwargs.results])
        json.dumps(print(json.dumps(models, indent=4)))
    for e in ['blade', 'rack']:
        pcolor.LightGray(f'\n{"="*20} {e.capitalize()} Descriptors {"="*20}\n')
        kwargs = kwargs | DotMap(api_filter = f"ServerFormFactor eq '{e}'", method = 'get', uri = 'capability/ServerDescriptors')
        kwargs = isight.api('capability').calls(kwargs)
        models = sorted([e.Model for e in kwargs.results])
        json.dumps(print(json.dumps(models, indent=4)))

if __name__ == '__main__':
    main()
