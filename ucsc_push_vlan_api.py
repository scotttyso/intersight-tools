#!/usr/bin/env python3
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, pcolor
    from dotmap import DotMap
    from json_ref_dict import materialize, RefDict
    from ucscsdk import ucschandle
    from ucscsdk import ucscmethodfactory
    from ucscsdk.utils.ucscdomain import get_domain
    import argparse, json, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

def cli_arguments():
    parser = argparse.ArgumentParser(description='UCS Central VLAN Push Module')
    parser.add_argument( '-y', '--yaml-file', help = 'The input YAML File.', required=True )
    return DotMap(args = parser.parse_args())

def main():
    kwargs = cli_arguments()
    #================================================
    # Import Stored Parameters and Add to kwargs
    #================================================
    ezdata = materialize(RefDict(f'{script_path}{os.sep}variables{os.sep}easy-imm.json', 'r', encoding="utf8"))
    kwargs.ez_tags = {'Key':'ezci','Value':ezdata['info']['version']}
    kwargs.ezdata  = DotMap(ezdata['components']['schemas'])
    #==============================================
    # Process the YAML input File
    #==============================================
    if (kwargs.args.yaml_file):
        yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
        ydict = DotMap(yaml.safe_load(yfile))
    #================================
    # Login to UCS Central API
    #================================
    kwargs.sensitive_var = 'ucs_central_password'
    kwargs               = ezfunctions.sensitive_var_value(kwargs)
    kwargs.password      = kwargs.var_value
    handle = ucschandle.UcscHandle(ip=ydict.hostname, username=ydict.username, password=kwargs.password)
    handle.login()
    #================================
    # Loop Through List of Domains
    #================================
    for e in ydict.domains:
        domain = get_domain(handle, domain_ip=e)
        for v in ydict.vlans:
            pcolor.Cyan(f'Pushing `{v.name}` to `{domain.name}`')
            r = ucscmethodfactory.config_publish_vlan(handle, in_domain=domain.id, in_vlan_name=v.name)

    #================================
    # Close API Session
    #================================
    handle.logout()

if __name__ == '__main__':
    main()
