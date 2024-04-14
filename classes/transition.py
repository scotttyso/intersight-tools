#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions
    from copy import deepcopy
    from dotmap import DotMap
    import json, re
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

#=============================================================================
# Class - Intersight Transition Tool
#=============================================================================
class intersight(object):
    def __init__(self, type):
        self.type = type

    #=============================================================================
    # Function - Modify Boot Order Policies
    #=============================================================================
    def modify_boot_order(pvars):
        odict = DotMap(
            local_cdd = 'boot.LocalCdd',
            local_disk = 'boot.LocalDisk',
            pxe_boot = 'boot.Pxe')
        pkeys = list(pvars.keys())
        if 'boot_devices' in pkeys:
            key_list = ['name,device_name', 'object_type,device_type']
            temp_dict = deepcopy(pvars.boot_devices)
            pvars.boot_devices = []
            for e in temp_dict:
                edict = deepcopy(e)
                edict = intersight.replace_keys(key_list, edict)
                edict.object_type = odict[edict.object_type]
                pvars.boot_devices.append(edict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Ethernet Adapter Policies
    #=============================================================================
    def modify_ethernet_adapter(pvars):
        key_list = [
            'completion.queue_count,completion_queue_count',
            'completion.ring_size,completion_ring_size',
            'receive.queue_count,receive_queue_count',
            'receive.ring_size,receive_ring_size',
            'receive_side_scaling,rss_settings',
            'tcp_offload,tcp_offload_settings',
            'transmit.queue_count,transmit_queue_count',
            'transmit.ring_size,transmit_ring_size']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        if 'interrupt_settings' in pkeys:
            for k in list(pvars.interrupt_settings.keys()):
                if 'interrupt_' in k:
                    pvars.interrupt_settings[k.replace('interrupt_', '')] = pvars.interrupt_settings[k]
                    pvars.interrupt_settings.pop(k)
                ikeys = list(pvars.interrupt_settings.keys())
                if 'coalescing_type' in ikeys:
                    pvars.interrupt_settings.coalescing_type = pvars.interrupt_settings.coalescing_type.upper()
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Ethernet Network Control Policies
    #=============================================================================
    def modify_ethernet_network_control(pvars):
        key_list = [
            'lldp_enable_receive,lldp_receive_enable',
            'lldp_enable_transmit,lldp_transmit_enable']
        pvars = intersight.replace_keys(key_list, pvars)
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Ethernet Network Group Policies
    #=============================================================================
    def modify_ethernet_network_group(pvars):
        vlans      = sorted(pvars.allowed_vlans.split(','))
        vlans      = [int(e) for e in vlans]
        vlan_list  = ezfunctions.vlan_list_format(vlans)
        if type(vlan_list) == int: vlan_list = str(vlan_list)
        pvars.allowed_vlans = vlan_list
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Fibre-Channel Adapter Policies
    #=============================================================================
    def modify_fibre_channel_adapter(pvars):
        key_list = [
            'error_recovery_settings,error_recovery_settings',
            'flogi.retries,flogi_retries',
            'flogi.timeout,flogi_timeout',
            'maximum_luns_per_target,max_luns_per_target',
            'plogi.retries,plogi_retries',
            'plogi.timeout,plogi_timeout',
            'receive.ring_size,receive_ring_size',
            'scsi_io.queue_count,scsi_io_queue_count',
            'scsi_io.ring_size,scsi_io_ring_size',
            'transmit.ring_size,transmit_ring_size']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        if 'interrupt_settings' in pkeys:
            pvars.interrupt.mode = pvars.interrupt_settings.interrupt_mode
            pvars.pop('interrupt_settings')
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify IMC Access Policies
    #=============================================================================
    def modify_imc_access(pvars):
        pkeys = list(pvars.keys())
        if 'inband_configuration' in pkeys: pvars.pop('inband_configuration')
        if 'out_of_band_configuration' in pkeys: pvars.pop('out_of_band_configuration')
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Pools
    #=============================================================================
    def modify_pools(pvars):
        pkeys = list(pvars.keys())
        if 'reservations' in pkeys: pvars.pop('reservations')
        if 'wwnn_blocks' in pkeys:
            pvars.id_blocks = pvars.wwnn_blocks
            pvars.pop('wwnn_blocks')
        if 'wwpn_blocks' in pkeys:
            pvars.id_blocks = pvars.wwpn_blocks
            pvars.pop('wwpn_blocks')
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify LAN Connectivity Policies
    #=============================================================================
    def modify_lan_connectivity(pvars):
        pkeys = list(pvars.keys())
        if 'target_platform' in pkeys: pvars.target_platform = pvars.target_platform.replace('-', '')
        if 'vnics' in pkeys:
            key_list = [
                'ethernet_network_group_policies,ethernet_network_group_policy',
                'mac_address_pools,mac_address_pool',
                'names,name',
                'placement.pci_links,pci_link',
                'placement.pci_order,pci_order',
                'placement.slot_ids,slot_id',
                'placement.switch_ids,switch_id',
                'placement.uplink_ports,uplink_port']
            temp_dict = deepcopy(pvars.vnics)
            pvars.vnics = []
            for e in temp_dict:
                idict = deepcopy(e)
                idict = intersight.replace_key_list(key_list, idict)
                vkeys = list(idict.keys())
                if 'mac_address_allocation_type' in vkeys:
                    idict.mac_address_allocation_type = (idict.mac_address_allocation_type).upper()
                pvars.vnics.append(idict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Port Policies
    #=============================================================================
    def modify_port(pvars):
        pvars.names = [pvars.name]
        pvars.pop('name')
        port_type_list = [
            'port_channel_appliances,appliance_port_channels',
            'port_channel_ethernet_uplinks,lan_port_channels',
            'port_channel_fc_uplinks,san_port_channels' ,
            'port_channel_fcoe_uplinks,fcoe_port_channels',
            'port_modes,san_unified_ports',
            'port_role_appliances,appliance_ports',
            'port_role_ethernet_uplinks,lan_uplink_ports',
            'port_role_fc_storage,storage_ports',
            'port_role_fc_uplinks,san_uplink_ports',
            'port_role_fcoe_uplinks,fcoe_ports',
            'port_role_servers,server_ports'
        ]
        pkeys = list(pvars.keys())
        for e in port_type_list:
            easy_imm = e.split(',')[0]
            imm_transition = e.split(',')[1]
            if imm_transition in pkeys:
                pvars[easy_imm] = pvars[imm_transition]
                pvars.pop(imm_transition)
        pkeys = list(pvars.keys())
        for item in port_type_list:
            port_type = item.split(',')[0]
            if port_type in pkeys:
                if re.search('_port_channels', port_type):
                    for x in(0, len(pvars[port_type])):
                        pvars[port_type][x].pc_ids = [pvars[port_type][x].pc_id]
                        pvars[port_type][x].pop('pc_id')
                if re.search('port_modes', port_type):
                    pvars[port_type].port_list = [pvars[port_type].port_id_start, pvars[port_type].port_id_end]
                    pvars[port_type].pop('port_id_start')
                    pvars[port_type].pop('port_id_end')
                    if pvars[port_type].slot_id == 1:
                        pvars[port_type].pop('slot_id')
                    if re.search('UCS-FI-6536', pvars.device_model):
                        pvars[port_type].custom_mode = 'BreakoutFibreChannel32G'
                    else: pvars[port_type].custom_mode = 'FibreChannel'
                if re.search('port_role', port_type):
                    for x in range(0, len(pvars[port_type])):
                        pvars[port_type][x].port_list = pvars[port_type][x].port_id
                        pvars[port_type][x].pop('port_id')
                        if pvars[port_type][x].slot_id == 1: pvars[port_type][x].pop('slot_id')
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify SAN Connectivity Policies
    #=============================================================================
    def modify_san_connectivity(pvars):
        pkeys = list(pvars.keys())
        if 'target_platform' in pkeys: pvars.target_platform = pvars.target_platform.replace('-', '')
        if 'wwnn_allocation_type' in pkeys: pvars.wwnn_allocation_type = pvars.wwnn_allocation_type.upper()
        if 'vhbas' in pkeys:
            key_list = [
                'fibre_channel_network_policies,fibre_channel_network_policy',
                'names,name',
                'placement.pci_links,pci_link',
                'placement.pci_order,pci_order',
                'placement.slot_ids,slot_id',
                'placement.switch_ids,switch_id',
                'placement.uplink_ports,uplink_port',
                'wwpn_pools,wwpn_pool']
            temp_dict = deepcopy(pvars.vhbas)
            pvars.vhbas = []
            for e in temp_dict:
                idict = deepcopy(e)
                idict = intersight.replace_key_list(key_list, idict)
                vkeys = list(idict.keys())
                if 'wwpn_allocation_type' in vkeys:
                    idict.wwpn_allocation_type = idict.wwpn_allocation_type.upper()
                pvars.vhbas.append(idict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Server Profiles
    #=============================================================================
    def modify_server(pvars, kwargs):
        key_list = ['boot_order_policy,boot_policy']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        if 'uuid_allocation_type' in pkeys: pvars.pop('uuid_allocation_type')
        for e in ['action', 'attach_template', 'target_platform', 'targets']:
            if not e in pkeys:
                if e == 'targets': pvars[e] = []
                else: pvars[e] = kwargs.ezdata.server.allOf[0].properties[e].default
        pkeys = list(pvars.keys())
        if 'target_platform' in pkeys: pvars.target_platform = pvars.target_platform.replace('-', '')
        tdict = DotMap()
        for e in ['description', 'name', 'reservations', 'static_uuid_address', 'serial_number']:
            if e in pkeys: tdict[e] = pvars[e]; pvars.pop(e)
        pvars.targets.append(tdict)
        for x in range(0,len(pvars.targets)):
            tkeys = list(pvars.targets[x].keys())
            if not 'serial_number' in tkeys: pvars.targets[x].serial_number = 'unknown'
            if 'reservations' in tkeys:
                key_list = ['identity_type,reservation_type','interface,vhba_name','interface,vnic_name']
                temp_dict = deepcopy(pvars.targets[x].reservations)
                pvars.targets[x].reservations = []
                for e in temp_dict:
                    edict = deepcopy(e)
                    edict = intersight.replace_keys(key_list, edict)
                    pvars.targets[x].reservations.append(edict)
        pvars = DotMap(sorted(pvars.items()))
        ## Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Storage Policies
    #=============================================================================
    def modify_storage(pvars):
        pkeys = list(pvars.keys())
        if 'drive_group' in pkeys:
            pvars.drive_groups = pvars.drive_group
            pvars.pop('drive_group')
            key_list = ['manual_drive_group,manual_drive_selection', 'name,drive_group_name']
            temp_dict = deepcopy(pvars.drive_groups)
            pvars.drive_groups = []
            for e in temp_dict:
                edict = deepcopy(e)
                edict = intersight.replace_keys(key_list, edict)
                ekeys = list(edict.keys())
                if 'raid_level' in ekeys: edict.raid_level = edict.raid_level.capitalize()
                if 'virtual_drives' in ekeys:
                    item_list = ['name,vd_name']
                    temp_dicti = deepcopy(edict.virtual_drives)
                    edict.virtual_drives = []
                    for i in temp_dicti:
                        idict = deepcopy(i)
                        idict = intersight.replace_keys(item_list, idict)
                        edict.virtual_drives.append(idict)
                pvars.drive_groups.append(edict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Thermal Policies
    #=============================================================================
    def modify_thermal(pvars):
        pkeys = list(pvars.keys())
        if 'fan_control_mode' in pkeys: pvars.fan_control_mode = pvars.fan_control_mode.replace(' ', '')
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify System QoS Policies
    #=============================================================================
    def modify_system_qos(pvars):
        pkeys = list(pvars.keys())
        if 'classes' in pkeys:
            for r in range(0,len(pvars.classes)):
                ckeys = pvars.classes[r]
                if 'mtu' in ckeys:
                    if pvars.classes[r].mtu > 3000: pvars.jumbo_mtu = True
                    pvars.classes[r].pop('mtu')
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Loop Through Organization - Pool, Policies, Profiles/Templates
    #=============================================================================
    def policy_loop(self, kwargs):
        # Set the org_count to 0 for the First Organization
        # Loop through the orgs discovered by the Class
        for e in kwargs.json_data.config.orgs:
            kwargs.org = e.name
            kwargs.imm_dict.orgs[e.name] = DotMap()
            for key, value in e.items():
                if re.search('_(policies|pools|profiles)', key):
                    p1 = re.search('_(policies|pools|profiles)', key).group(1)
                    p2 = ((key.replace('_policies', '')).replace('_pools', '')).replace('_profiles', '')
                    if p2 == 'boot': p2 = 'boot_order'
                    elif p2 == 'ucs_server': p2 = 'server'
                    elif p2 == 'ucs_server_template': p2 = 'server_template'
                    for item in value:
                        pvars = deepcopy(item)
                        if pvars.get('descr'):
                            pvars.description = pvars.descr
                            pvars.pop('descr')
                        if pvars.get('tags'): pvars.pop('tags')
                        if   p2 == 'boot_order':               pvars = intersight.modify_boot_order(pvars)
                        elif p2 == 'ethernet_adapter':         pvars = intersight.modify_ethernet_adapter(pvars)
                        elif p2 == 'ethernet_network_control': pvars = intersight.modify_ethernet_network_control(pvars)
                        elif p2 == 'ethernet_network_group':   pvars = intersight.modify_ethernet_network_group(pvars)
                        elif p2 == 'fibre_channel_adapter':    pvars = intersight.modify_fibre_channel_adapter(pvars)
                        elif p2 == 'imc_access':               pvars = intersight.modify_imc_access(pvars)
                        elif p2 == 'lan_connectivity':         pvars = intersight.modify_lan_connectivity(pvars)
                        elif p2 == 'port':                     pvars = intersight.modify_port(pvars)
                        elif p2 == 'san_connectivity':         pvars = intersight.modify_san_connectivity(pvars)
                        elif p2 == 'server':                   pvars = intersight.modify_server(pvars, kwargs)
                        elif p2 == 'storage':                  pvars = intersight.modify_storage(pvars)
                        elif p2 == 'system_qos':               pvars = intersight.modify_system_qos(pvars)
                        elif p2 == 'thermal':                  pvars = intersight.modify_thermal(pvars)
                        elif re.search('ip|iqn|mac|uuid|wwnn|wwpn', p2): pvars = intersight.modify_pools(pvars)
                        #else:
                        #    print(json.dumps(pvars, indent=4))
                        #    print(key,p1,p2)
                        kwargs.class_path = f'{p1},{p2}'
                        kwargs = ezfunctions.ez_append(pvars, kwargs)
        # Return kwargs
        return kwargs

    #=============================================================================
    # Function - Replace Keys
    #=============================================================================
    def replace_keys(key_list, pvars):
        pkeys = list(pvars.keys())
        for e in key_list:
            easy_imm,imm_transition = e.split(',')
            if imm_transition in pkeys:
                if '.' in easy_imm:
                    key1,key2 = easy_imm.split('.')
                    pvars[key1][key2] = pvars[imm_transition]
                else: pvars[easy_imm] = pvars[imm_transition]
                pvars.pop(imm_transition)
        pvars = DotMap(sorted(pvars.items()))
        return pvars

    #=============================================================================
    # Function - Replace Key List
    #=============================================================================
    def replace_key_list(key_list, pvars):
        pkeys = list(pvars.keys())
        for e in key_list:
            easy_imm,imm_transition = e.split(',')
            if imm_transition in pkeys:
                if '.' in easy_imm:
                    key1,key2 = easy_imm.split('.')
                    pvars[key1][key2] = [pvars[imm_transition]]
                else: pvars[easy_imm] = [pvars[imm_transition]]
                pvars.pop(imm_transition)
        pvars = DotMap(sorted(pvars.items()))
        return pvars
