#!/usr/bin/env python3
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from dotmap import DotMap
    from ucscsdk.ucschandle import UcsHandle
    from ucscsdk.mometa.fabric.FabricNetGroup import FabricNetGroup
    from ucscsdk.mometa.fabric.FabricPoolableVlan import FabricPooledVlan
    from ucscsdk.mometa.fabric.FabricVlan import FabricVlan
    from ucscsdk.methodmeta import ConfigPublishVlanMeta
    from ucscsdk.utils.ucscdomain import get_domain
    import argparse, getpass, json, yaml
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

def create_vlan(handle, kwargs):
    dn = handle.query_dn("domaingroup-root/fabric/lan")
    mo = FabricVlan(parent_mo_or_dn="domaingroup-root/fabric/lan", name=kwargs.vlan_name)
    handle.add_mo(mo)
    handle.commit()
    obj = handle.query_dn("domaingroup-root/fabric/lan/net-" + kwargs.vlan_name)
    obj.id = kwargs.vlan_id
    handle.set_mo(obj)
    handle.commit()

def add_vlan_to_vlan_group(handle, kwargs):
    dn_base = 'domaingroup-root/domaingroup-Lab-RDU/fabric/lan'
    vlanGroup = FabricNetGroup(parent_mo_or_dn=dn_base, name=kwargs.vlan_group)
    vlanRef = FabricPooledVlan(parent_mo_or_dn=vlanGroup, name=kwargs.vlan_name)
    handle.add_mo(vlanRef, True)
    handle.commit()

def delete_vlan(handle, kwargs):
    obj = handle.query_dn("domaingroup-root/fabric/lan/net-" + kwargs.vlan_name)
    handle.remove_mo(obj)
    handle.commit()

def main():
    kwargs = cli_arguments()
    #==============================================
    # Process the YAML input File
    #==============================================
    if (kwargs.args.yaml_file):
        yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
        ydict = DotMap(yaml.safe_load(yfile))
    user_passwd = getpass.getpass("=> passowrd: ")
    handle=UcsHandle()
    handle.login(ip=ydict.hostname,username=ydict.username, password=user_passwd)
    print(handle)
    for e in ydict.domains:
        domain = get_domain(handle, domain_ip=e.domain_ip)
    print("=> logged into {}".format(handle.ip))
    print("=> logging out of {}".format(handle.ip))
    handle.logout()