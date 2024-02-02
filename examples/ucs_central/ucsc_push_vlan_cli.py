#!/usr/bin/env python3
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions
    from dotmap import DotMap
    import argparse, json, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

def cli_arguments():
    Parser = argparse.ArgumentParser(description='Intersight Converged Infrastructure Deployment Module')
    Parser.add_argument( '-y', '--yaml-file', help = 'The input YAML File.', required=True )
    kwargs = DotMap()
    kwargs.args = Parser.parse_args()
    return kwargs

def main():
    kwargs = cli_arguments()
    #==============================================
    # Process the YAML input File
    #==============================================
    if (kwargs.args.yaml_file):
        yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
        ydict = DotMap(yaml.safe_loadload(yfile))

    #================================
    # Login to UCS Central
    #================================
    kwargs.hostname   = ydict.hostname
    kwargs.host_prompt= r'[\w\-]{3,64}(\([\w\-]+\))?( /[/\w\-]+)?#'
    kwargs.password   = 'ucs_central_password'
    kwargs.username   = ydict.username
    child, kwargs     = ezfunctions.child_login(kwargs)

    cmds = ['connect resource-mgr', 'scope domain-mgmt']
    for cmd in cmds:
        child.sendline(cmd)
        child.expect(kwargs.host_prompt)
    child.sendline('show ucs domain')
    count = 0
    cmd_check = False
    while cmd_check == False:
        i = child.expect(['', kwargs.host_prompt], timeout=20)
        if i == 0:
            if (child.match).group(2) in ydict.domains: kwargs.domains[(child.match).group(2)] = (child.match).group(1)
        elif i == 1: cmd_check = True
    for k, v in kwargs.domains:
        cmds = [f'scope ucs-domain {v}', 'publish vlan', 'exit']
        for cmd in cmds:
            child.sendline(cmd)
            child.expect(kwargs.host_prompt)
    cmds = ['exit', 'exit']
    for cmd in cmds:
        child.sendline(cmd)
        child.expect(kwargs.host_prompt)
    child.sendline('exit')
    child.close()

if __name__ == '__main__':
    main()
