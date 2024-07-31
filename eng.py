#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import build, ezfunctions, isight, questions
    from copy import deepcopy
    from dotmap import DotMap
    import argparse, json, os, re
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

#=============================================================================
# Function: Parse Arguments
#=============================================================================
def cli_arguments():
    kwargs = DotMap()
    parser = argparse.ArgumentParser(description ='Ethernet Network Group Module', conflict_handler='resolve')
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
    #=========================================================================
    # Send Notification Message
    #=========================================================================
    kwargs.args.dir        = os.path.abspath(kwargs.args.dir)
    kwargs.deployment_type = 'Convert'
    kwargs                 = questions.main_menu.previous_configuration(kwargs)
    #kwargs.imm_dict.orgs['PVU-DC'].policies.ethernet_network_group = []
    #kwargs.imm_dict.orgs['ROB-DC'].policies.ethernet_network_group = []
    #for f in ['pvu.json', 'rob.json']:
    #    jdata = json.load(open(os.path.join(kwargs.args.dir, f), 'r'))
    #    for e in jdata:
    #        e = DotMap(e)
    #        edict = DotMap(allowed_vlans = str(e.ID), name = e.VLANName, native_vlan = e.ID)
    #        if 'Riverton_DC' in e.DomainGroup: org = 'ROB-DC'
    #        else: org = 'PVU-DC'
    #        npfx = org.split('-')[0] + '-'
    #        if not re.search(f'^{npfx}', edict.name): edict.name = npfx + edict.name
    #        edict.name = edict.name.replace('_', '-')
    #        edict = edict.toDict()
    #        kwargs.imm_dict.orgs[org].policies.ethernet_network_group.append(edict)
    #print(json.dumps(kwargs.imm_dict.orgs, indent=4))
    #print(yaml.dump(kwargs.imm_dict.orgs.toDict()))
    #sys.exit(1)
    #
    # VLAN SECTION
    for org in ['PVU-DC', 'ROB-DC']:
        pkeys = list(kwargs.imm_dict.orgs[org].policies.keys())
        if not 'vlan' in pkeys: kwargs.imm_dict.orgs[org].policies.vlan = []
        vlans = []
        for e in kwargs.imm_dict.orgs[org].policies.ethernet_network_group:
            ekeys = list(e.keys())
            if 'native_vlan' in ekeys:
                edict = DotMap(auto_allow_on_uplinks = True, multicast_policy = 'Global/Global-Multicast-Disabled',
                               name = e.name, vlan_list = e.allowed_vlans)
                vlans.append(edict)
        name  = org.split('-')[0] + '-VLANS'
        vdict = DotMap(name = name, vlans = vlans)
        indx = next((index for (index, d) in enumerate(kwargs.imm_dict.orgs[org].policies.vlan) if d.name == name), None)
        if not indx == None:
            kwargs.imm_dict.orgs[org].policies.vlan[indx] = vdict
        else: kwargs.imm_dict.orgs[org].policies.vlan.append(vdict)
    #
    # LAN CONNECTIVITY SECTION
    #eng    = deepcopy(kwargs.imm_dict.orgs['PVU-DC'].policies.ethernet_network_group)
    #lcp    = deepcopy(kwargs.imm_dict.orgs['PVU-DC'].policies.lan_connectivity)
    #neweng = DotMap(yaml.safe_load(open(os.path.join('/home/tyscott/terraform-cisco-modules/church/policies/ethernet.ezi.yaml'))))
    #pvu    = neweng['PVU-DC'].policies.ethernet_network_group
    #rob    = neweng['ROB-DC'].policies.ethernet_network_group
    #kwargs.imm_dict.orgs['PVU-DC'].policies.lan_connectivity = []
    #kwargs.imm_dict.orgs['ROB-DC'].policies.lan_connectivity = []
    #for e in lcp:
    #    if '2NIC' in e.name: kwargs.imm_dict.orgs['PVU-DC'].policies.lan_connectivity.append(e)
    #    else:
    #        vnics = DotMap(enable_failover = True, ethernet_adapter_policy = e.vnics[0].ethernet_adapter_policy,
    #                    ethernet_network_control_policy = 'Global/Global-BOTH', ethernet_network_group_policies = [],
    #                    ethernet_qos_policy = 'Global/Global-Best-Effort', mac_address_pools = ['Global/Global-MAC'],
    #                    names = [e.vnics[0].names[0], e.vnics[1].names[0]], placement = DotMap(pci_order = [0, 1]))
    #        if vnics.ethernet_adapter_policy == 'G_8Core_CPU': vnics.ethernet_adapter_policy = 'Global/Global-8Core-CPU'
    #        for x in range(0,2):
    #            ethg = e.vnics[x].ethernet_network_group_policies[0]
    #            indx = next((index for (index, d) in enumerate(eng) if d.name == ethg), None)
    #            vlan = eng[indx].native_vlan
    #            indx = next((index for (index, d) in enumerate(pvu) if d.native_vlan == vlan), None)
    #            if indx == None:
    #                indx  = next((index for (index, d) in enumerate(rob) if d.native_vlan == vlan), None)
    #                if indx == None:
    #                    print(json.dumps(e, indent=4))
    #                    print(vlan)
    #                vname = rob[indx].name
    #            else: vname = pvu[indx].name
    #            vnics.ethernet_network_group_policies.append(vname)
    #        nlcp = DotMap(name = vnics.ethernet_network_group_policies[0] + '-LCP', target_platform = 'FIAttached', vnics = [vnics])
    #        if 'ROB-' in nlcp.name:
    #            indx = next((index for (index, d) in enumerate(kwargs.imm_dict.orgs['ROB-DC'].policies.lan_connectivity) if d.name == nlcp.name), None)
    #            if indx == None: kwargs.imm_dict.orgs['ROB-DC'].policies.lan_connectivity.append(nlcp)
    #        else:
    #            indx = next((index for (index, d) in enumerate(kwargs.imm_dict.orgs['PVU-DC'].policies.lan_connectivity) if d.name == nlcp.name), None)
    #            if indx == None: kwargs.imm_dict.orgs['PVU-DC'].policies.lan_connectivity.append(nlcp)
    #lcp = sorted(kwargs.imm_dict.orgs['PVU-DC'].policies.lan_connectivity, key=lambda ele: ele.name)
    #kwargs.imm_dict.orgs['PVU-DC'].policies.lan_connectivity = lcp
    #lcp = sorted(kwargs.imm_dict.orgs['ROB-DC'].policies.lan_connectivity, key=lambda ele: ele.name)
    #kwargs.imm_dict.orgs['ROB-DC'].policies.lan_connectivity = lcp
    # print(json.dumps(lcp, indent=4))
    build.intersight.create_yaml_files(kwargs)    

if __name__ == '__main__':
    main()
