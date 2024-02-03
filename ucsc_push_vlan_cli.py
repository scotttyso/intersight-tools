#!/usr/bin/env python3
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions
    from dotmap import DotMap
    from json_ref_dict import materialize, RefDict
    from ucscsdk import ucschandle
    from ucscsdk.utils.ucscdomain import get_domain
    import argparse, json, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

def cli_arguments():
    Parser = argparse.ArgumentParser(description='UCS Central VLAN Push Module')
    Parser.add_argument( '-y', '--yaml-file', help = 'The input YAML File.', required=True )
    kwargs = DotMap()
    kwargs.args = Parser.parse_args()
    return kwargs

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
    # Login to UCS Central CLI
    #================================
    kwargs.hostname    = ydict.hostname
    kwargs.host_prompt = r'[\w\-]{3,64}(\([\w\-]+\))?( /[/\w\-]+)?( )?#'
    kwargs.password    = 'ucs_central_password'
    kwargs.username    = ydict.username
    child, kwargs      = ezfunctions.child_login(kwargs)
    #================================
    # Connect to Resource Manager
    #================================
    cmds = ['connect resource-mgr', 'scope domain-mgmt']
    for cmd in cmds:
        child.sendline(cmd)
        child.expect(cmd)
        child.expect(kwargs.host_prompt)
    #================================
    # Login to UCS Central API
    #================================
    handle = ucschandle.UcscHandle(ip=kwargs.hostname, username=kwargs.username, password=kwargs.password)
    handle.login()
    #================================
    # Loop Through List of Domains
    #================================
    for e in ydict.domains:
        domain = get_domain(handle, domain_ip=e)
        child.sendline(f'scope ucs-domain {domain.id}')
        child.expect(kwargs.host_prompt)
        for v in ydict.vlans:
            child.sendline(f'publish vlan {v.name}')
            child.expect(f'publish vlan {v.name}')
            cmd_check = False
            while cmd_check == False:
                i = child.expect(['Do you want to continue?', kwargs.host_prompt])
                if   i == 0: child.sendline('yes'); child.expect('yes')
                elif i == 1: cmd_check = True
        child.sendline('exit')
        child.expect(kwargs.host_prompt)
    cmds = ['exit', 'exit']
    for cmd in cmds:
        child.sendline(cmd)
        child.expect(kwargs.host_prompt)
    #================================
    # Close CLI and API Sessions
    #================================
    child.sendline('exit')
    child.close()
    handle.logout()

if __name__ == '__main__':
    main()
