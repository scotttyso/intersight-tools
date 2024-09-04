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
        key_list = [
            'bootloader.description,bootloader_description',
            'bootloader.name,bootloader_name',
            'bootloader.path,bootloader_path']
        pkeys = list(pvars.keys())
        if 'boot_devices' in pkeys:
            temp_dict = deepcopy(pvars.boot_devices)
            pvars.boot_devices = []
            for e in temp_dict:
                idict = deepcopy(e)
                ikeys = list(idict.keys())
                if 'bootloader_path' in ikeys:
                    if '|' in idict.bootloader_path: idict.bootloader_path = idict.bootloader_path.replace('|', '')
                idict = intersight.replace_keys(key_list, idict)
                ikeys = list(idict.keys())
                if 'slot' in ikeys:
                    if idict.device_type == 'san_boot': idict.slot = 'MLOM'
                pvars.boot_devices.append(idict)
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
        pkeys = list(pvars.keys())
        vlans     = ezfunctions.vlan_list_full(pvars.allowed_vlans)
        vlan_list = ezfunctions.vlan_list_format(vlans)
        if type(vlan_list) == int: vlan_list = str(vlan_list)
        pvars.allowed_vlans = vlan_list
        if 'enable_q_in_q_tunneling' in pkeys: pvars.pop('enable_q_in_q_tunneling')
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
    # Function - Modify Firmware Policies
    #=============================================================================
    def modify_firmware(pvars):
        key_list = ['model_bundle_version,models']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        if 'excluded_components' in pkeys:
            for e in pvars.excluded_components:
                if   e == None:   pass
                elif e == 'none': pass
                elif e == 'drives-except-boot-drives': pvars.advanced_mode.exclude_drives_except_boot_drives = True
                elif e == 'local-disk':                pvars.advanced_mode.exclude_drives = True
                elif e == 'storage-controller':        pvars.advanced_mode.exclude_storage_controllers = True
                elif e == 'storage-sasexpander':       pvars.advanced_mode.exclude_storage_sasexpander = True
                elif e == 'storage-u2':                pvars.advanced_mode.exclude_storage_u2 = True
            pvars.pop('excluded_components')
        if 'target_platform' in pkeys: pvars.target_platform = pvars.target_platform.replace('-', '')
        if 'model_bundle_version' in pkeys:
            temp_dict = deepcopy(pvars.model_bundle_version)
            pvars.model_bundle_version = []
            for e in temp_dict:
                idict = deepcopy(e)
                ikeys = list(idict.keys())
                if 'server_model' in ikeys: idict.server_models = [idict.server_model]; idict.pop('server_model')
                pvars.model_bundle_version.append(idict)
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
    # Function - Modify IMC Access Policies
    #=============================================================================
    def modify_imc_access(pvars):
        pkeys = list(pvars.keys())
        if 'inband_configuration' in pkeys: pvars.pop('inband_configuration')
        if 'out_of_band_configuration' in pkeys: pvars.pop('out_of_band_configuration')
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify IPMI over LAN Policies
    #=============================================================================
    def modify_ipmi_over_lan(pvars):
        key_list = ['privilege,privilege_level']
        pvars = intersight.replace_keys(key_list, pvars)
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify iSCSI Boot Policies
    #=============================================================================
    def modify_iscsi_boot(pvars):
        key_list = ['initiator_ip_pool,ip_pool']
        pvars = intersight.replace_keys(key_list, pvars)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify iSCSI Static Target Policies
    #=============================================================================
    def modify_iscsi_static_target(pvars):
        pkeys = list(pvars.keys())
        if 'lun' in pkeys: pvars.lun_id = deepcopy(pvars.lun.lun_id); pvars.pop('lun')
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Pools
    #=============================================================================
    def modify_pools(ptype, pvars):
        pkeys = list(pvars.keys())
        if 'reservations' in pkeys: pvars.pop('reservations')
        if 'wwnn_blocks' in pkeys:
            pvars.id_blocks = pvars.wwnn_blocks
            pvars.pop('wwnn_blocks')
        if 'wwpn_blocks' in pkeys:
            pvars.id_blocks = pvars.wwpn_blocks
            pvars.pop('wwpn_blocks')
        if not 'mac_blocks' in pkeys and ptype == 'mac':
            pvars.mac_blocks = [DotMap({'from':'00:25:B5:0A:00:00','size':255})]
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify LAN Connectivity Policies
    #=============================================================================
    def modify_lan_connectivity(pvars):
        pkeys = list(pvars.keys())
        if 'iqn_allocation_type' in pkeys: pvars.iqn_allocation_type = (pvars.iqn_allocation_type).capitalize()
        if 'target_platform' in pkeys: pvars.target_platform = pvars.target_platform.replace('-', '')
        if 'vnics' in pkeys:
            key_list1 = [
                'ethernet_network_group_policies,ethernet_network_group_policy',
                'iscsi_boot_policies,iscsi_boot_policy',
                'mac_address_pools,mac_address_pool',
                'names,name',
                'placement.pci_links,pci_link',
                'placement.pci_order,pci_order',
                'placement.slot_ids,slot_id',
                'placement.switch_ids,switch_id',
                'placement.uplink_ports,uplink_port']
            key_list2 = [
                'placement.automatic_pci_link_assignment,automatic_pci_link_assignment',
                'placement.automatic_slot_id_assignment,automatic_slot_id_assignment']
            temp_dict = deepcopy(pvars.vnics)
            pvars.vnics = []
            for e in temp_dict:
                edict = intersight.replace_key_list(key_list1, deepcopy(e))
                edict = intersight.replace_keys(key_list2, edict)
                ekeys = list(edict.keys())
                if 'pci_link_assignment_mode' in ekeys: edict.pop('pci_link_assignment_mode')
                if 'mac_address_allocation_type' in ekeys: edict.pop('mac_address_allocation_type')
                pvars.vnics.append(edict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Local User Policies
    #=============================================================================
    def modify_local_user(pvars):
        key_list = [
            'password_properties.always_send_user_password,always_send_user_password',
            'password_properties.enable_password_expiry,enable_password_expiry',
            'password_properties.enforce_strong_password,enforce_strong_password',
            'password_properties.grace_period,grace_period',
            'password_properties.notification_period,notification_period',
            'password_properties.password_expiry_duration,password_expiry_duration',
            'password_properties.password_history,password_history',
            'users,local_users']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        if 'users' in pkeys:
            temp_dict = deepcopy(pvars.users)
            pvars.users = []
            key_list = ['enabled,enable']
            for e in temp_dict:
                idict = intersight.replace_keys(key_list, deepcopy(e))
                ikeys = list(idict.keys())
                if not 'password' in ikeys: idict.password = 1
                idict = DotMap(sorted(idict.items()))
                pvars.users.append(idict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Multicast Policies
    #=============================================================================
    def modify_multicast(pvars):
        key_list = [
            'querier_state,igmp_snooping_querier_state',
            'snooping_state,igmp_snooping_state']
        pvars = intersight.replace_keys(key_list, pvars)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Switch Control Policies
    #=============================================================================
    def modify_network_connectivity(pvars):
        pkeys = list(pvars.keys())
        if 'enable_ipv6' in pkeys: pvars.pop('enable_ipv6')
        pvars.dns_servers_v4 = []
        pvars.dns_servers_v6 = []
        if 'preferred_ipv4_dns_server' in pkeys:
            pvars.dns_servers_v4.append(pvars.preferred_ipv4_dns_server)
            pvars.pop('preferred_ipv4_dns_server')
        if 'alternate_ipv4_dns_server' in pkeys:
            pvars.dns_servers_v4.append(pvars.alternate_ipv4_dns_server)
            pvars.pop('alternate_ipv4_dns_server')
        if 'preferred_ipv6_dns_server' in pkeys:
            pvars.dns_servers_v6.append(pvars.preferred_ipv6_dns_server)
            pvars.pop('preferred_ipv6_dns_server')
        if 'alternate_ipv6_dns_server' in pkeys:
            pvars.dns_servers_v6.append(pvars.alternate_ipv6_dns_server)
            pvars.pop('alternate_ipv6_dns_server')
        if len(pvars.dns_servers_v4) == 0: pvars.pop('dns_servers_v4')
        if len(pvars.dns_servers_v6) == 0: pvars.pop('dns_servers_v6')
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Port Policies
    #=============================================================================
    def modify_port(pvars):
        pvars.names = [pvars.name]
        pvars.pop('name')
        key_list = [
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
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        for e in key_list:
            port_type = e.split(',')[0]
            if port_type in pkeys:
                if re.search('port_channel_', port_type):
                    for x in range(0, len(pvars[port_type])):
                        xkeys = pvars[port_type][x]
                        if 'pc_id' in xkeys:
                            pvars[port_type][x].pc_ids = [pvars[port_type][x].pc_id]
                            pvars[port_type][x].pop('pc_id')
                        if 'vsan_id' in xkeys:
                            pvars[port_type][x].vsan_ids = [pvars[port_type][x].vsan_id]
                            pvars[port_type][x].pop('vsan_id')
                        if 'fill_pattern' in xkeys: pvars[port_type][x].pop('fill_pattern')
                if re.search('port_modes', port_type):
                    pvars[port_type].port_list = [pvars[port_type].port_id_start, pvars[port_type].port_id_end]
                    pvars[port_type].pop('port_id_start')
                    pvars[port_type].pop('port_id_end')
                    if pvars[port_type].slot_id == 1:
                        pvars[port_type].pop('slot_id')
                    if re.search('UCS-FI-6536', pvars.device_model):
                        pvars[port_type].custom_mode = 'BreakoutFibreChannel32G'
                    else: pvars[port_type].custom_mode = 'FibreChannel'
                    pvars[port_type] = [pvars[port_type]]
                if re.search('port_role', port_type):
                    for x in range(0, len(pvars[port_type])):
                        pvars[port_type][x].port_list = str(pvars[port_type][x].port_id)
                        pvars[port_type][x].pop('port_id')
                        if pvars[port_type][x].slot_id == 1: pvars[port_type][x].pop('slot_id')
                        xkeys = pvars[port_type][x]
                        if 'connected_device_id' in xkeys:
                            pvars[port_type][x].device_number = pvars[port_type][x].connected_device_id
                            pvars[port_type][x].pop('connected_device_id')
                        if 'fill_pattern' in xkeys: pvars[port_type][x].pop('fill_pattern')
                        if 'vsan_id' in xkeys:
                            pvars[port_type][x].vsan_ids = [pvars[port_type][x].vsan_id]
                            pvars[port_type][x].pop('vsan_id')
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Power Policies
    #=============================================================================
    def modify_power(pvars):
        pkeys = list(pvars.keys())
        if not 'power_redundancy' in pkeys: pvars.power_redundancy = 'Grid'
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify SAN Connectivity Policies
    #=============================================================================
    def modify_san_connectivity(pvars):
        pkeys = list(pvars.keys())
        if 'target_platform' in pkeys: pvars.target_platform = pvars.target_platform.replace('-', '')
        if 'wwnn_allocation_type' in pkeys: pvars.pop('wwnn_allocation_type')
        if 'vhbas' in pkeys:
            key_list1 = [
                'fibre_channel_network_policies,fibre_channel_network_policy',
                'names,name',
                'placement.pci_links,pci_link',
                'placement.pci_order,pci_order',
                'placement.slot_ids,slot_id',
                'placement.switch_ids,switch_id',
                'placement.uplink_ports,uplink_port',
                'wwpn_pools,wwpn_pool']
            key_list2 = [
                'placement.automatic_pci_link_assignment,automatic_pci_link_assignment',
                'placement.automatic_slot_id_assignment,automatic_slot_id_assignment']
            temp_dict = deepcopy(pvars.vhbas)
            pvars.vhbas = []
            for e in temp_dict:
                edict = intersight.replace_key_list(key_list1, deepcopy(e))
                edict = intersight.replace_keys(key_list2, edict)
                ekeys = list(edict.keys())
                if 'pci_link_assignment_mode' in ekeys: edict.pop('pci_link_assignment_mode')
                if 'wwpn_allocation_type' in ekeys: edict.pop('wwpn_allocation_type')
                pvars.vhbas.append(edict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify SD Card Policies
    #=============================================================================
    def modify_sd_card(pvars):
        pkeys = list(pvars.keys())
        pvars.enable_diagnostics = False
        pvars.enable_drivers     = False
        pvars.enable_huu         = False
        pvars.enable_os          = False
        pvars.enable_scu         = False
        if 'partitions' in pkeys:
            for e in pvars.partitions:
                if   e.type == 'OS':          pvars.enable_os          = True
                elif e.type == 'Diagnostics': pvars.enable_diagnostics = True
                elif e.type == 'Drivers':     pvars.enable_drivers     = True
                elif e.type == 'HUU':         pvars.enable_huu         = True
                elif e.type == 'SCU':         pvars.enable_scu         = True
            pvars.pop('partitions')
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
        if 'assigned_server' in pkeys: pvars.pop('assigned_server')
        if 'operational_state' in pkeys:
            pvars.reservations = pvars.operational_state.identities; pvars.pop('operational_state')
        if 'uuid_allocation_type' in pkeys: pvars.pop('uuid_allocation_type')
        for e in ['action', 'attach_template', 'target_platform', 'targets']:
            if not e in pkeys:
                if e == 'targets': pvars[e] = []
                else: pvars[e] = kwargs.ezdata['profiles.server'].allOf[0].properties[e].default
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
                    edict = intersight.replace_keys(key_list, deepcopy(e))
                    pvars.targets[x].reservations.append(edict)
        pvars = DotMap(sorted(pvars.items()))
        ## Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Server Templates
    #=============================================================================
    def modify_server_template(pvars, kwargs):
        key_list = ['boot_order_policy,boot_policy']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        if 'uuid_allocation_type' in pkeys: pvars.pop('uuid_allocation_type')
        pvars.create_template = True
        for e in ['target_platform']:
            if not e in pkeys: pvars[e] = kwargs.ezdata['templates.server'].allOf[0].properties[e].default
        pkeys = list(pvars.keys())
        if 'target_platform' in pkeys: pvars.target_platform = pvars.target_platform.replace('-', '')
        pvars = DotMap(sorted(pvars.items()))
        ## Return pvars
        return pvars

    #=============================================================================
    # Function - Modify SNMP Policies
    #=============================================================================
    def modify_snmp(pvars):
        key_list = ['enable_snmp,enabled','snmp_community_access,community_access','snmp_port,port',
                    'snmp_trap_destinations,trap_destinations', 'snmp_users,users']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys    = list(pvars.keys())
        if 'snmp_trap_destinations' in pkeys:
            temp_dict = deepcopy(pvars.snmp_trap_destinations)
            pvars.snmp_trap_destinations = []
            for e in temp_dict:
                ilist = ['community_string,community','enable,enabled']
                idict = intersight.replace_keys(ilist, deepcopy(e))
                ikeys = list(idict.keys())
                if 'community_string' in ikeys: idict.community_string = 1
                if 'version' in ikeys: idict.pop('version')
                if 'user' in ikeys and len(idict.user) == 0: idict.pop('user')
                pvars.snmp_trap_destinations.append(idict)
        if 'snmp_users' in pkeys:
            temp_dict = deepcopy(pvars.snmp_users)
            pvars.snmp_users = []
            for e in temp_dict:
                idict = deepcopy(e)
                ikeys = list(idict.keys())
                if 'auth_password' in ikeys: idict.auth_password = 1
                if 'privacy_password' in ikeys: idict.privacy_password = 1
                if 'auth_password' in ikeys and 'privacy_password' in ikeys: idict.security_level = 'AuthPriv'
                elif 'auth_password' in ikeys: idict.security_level = 'AuthNoPriv'
                else: idict.security_level = 'NoAuthNoPriv'
                pvars.snmp_users.append(idict)
        if 'trap_community_string' in pkeys: pvars.trap_community_string = 1
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
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
                        ikeys = list(idict.keys())
                        idict.virtual_drive_policy = DotMap()
                        for vp in ['access_policy', 'disk_cache', 'read_policy', 'strip_size', 'write_policy']:
                            if vp in ikeys:
                                if vp == 'strip_size' and 'strip_size' in ikeys:
                                    idict.virtual_drive_policy[vp] = int((idict[vp].replace('KiB', '')).replace('MiB', ''))
                                    idict.pop(vp)
                                elif vp == 'disk_cache' and vp in ikeys: idict.virtual_drive_policy.drive_cache = idict[vp]; idict.pop(vp)
                                else: idict.virtual_drive_policy[vp] = idict[vp]; idict.pop(vp)
                        if len(idict.virtual_drive_policy) == 0: idict.pop('virtual_drive_policy')
                        edict.virtual_drives.append(idict)
                pvars.drive_groups.append(edict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Switch Control Policies
    #=============================================================================
    def modify_switch_control(pvars):
        key_list = ['udld_global_settings,link_control_global_settings']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        if 'fabric_port_channel_vhba_reset' in pkeys:
            if pvars.fabric_port_channel_vhba_reset == True:
                pvars.fabric_port_channel_vhba_reset = 'Enabled'
            else: pvars.fabric_port_channel_vhba_reset = 'Disabled'
        if 'switching_mode' in pkeys:
            skeys = list(pvars.switching_mode.keys())
            if 'ethernet' in skeys:  pvars.switching_mode_ethernet = pvars.switching_mode.ethernet
            if 'fc' in skeys:  pvars.switching_mode_fc = pvars.switching_mode.fc
            pvars.pop('switching_mode')
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Syslog Policies
    #=============================================================================
    def modify_syslog(pvars):
        pkeys = list(pvars.keys())
        if 'local_logging' in pkeys:
            skeys = list(pvars.local_logging.keys())
            if 'file' in skeys:
                pvars.local_logging.minimum_severity = pvars.local_logging.file.min_severity
                pvars.local_logging.pop('file')
        if 'remote_logging' in pkeys:
            rlogging = []
            rkeys = list(pvars.remote_logging.keys())
            if 'server1' in rkeys: rlogging.append(pvars.remote_logging.server1)
            if 'server2' in rkeys: rlogging.append(pvars.remote_logging.server2)
            key_list = ['minimum_severity,min_severity']
            pvars.remote_logging = []
            for e in rlogging:
                idict = deepcopy(e)
                idict = intersight.replace_keys(key_list, idict)
                pvars.remote_logging.append(idict)
        pvars = DotMap(sorted(pvars.items()))
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
                if 'multicast_optimized' in ckeys: pvars.classes[r].pop('multicast_optimized')
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
    # Function - Modify Virtual KVM Policies
    #=============================================================================
    def modify_virtual_kvm(pvars):
        key_list = ['maximum_sessions,max_sessions']
        pvars = intersight.replace_keys(key_list, pvars)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify Virtual Media Policies
    #=============================================================================
    def modify_virtual_media(pvars):
        key_list = ['add_virtual_media,vmedia_mounts']
        pvars = intersight.replace_keys(key_list, pvars)
        pkeys = list(pvars.keys())
        if 'add_virtual_media' in pkeys:
            temp_list = deepcopy(pvars.add_virtual_media)
            pvars.add_virtual_media = []
            for e in temp_list:
                edict = deepcopy(e)
                if edict.protocol == 'nfs': edict.file_location = 'nfs://' + e.file_location
                elif edict.protocol == 'cifs': edict.file_location = 'cifs://' + e.file_location
                pvars.add_virtual_media.append(edict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify VLAN Policies
    #=============================================================================
    def modify_vlan(pvars):
        key_list = ['vlan_list,id']
        pkeys    = list(pvars.keys())
        if 'vlans' in pkeys:
            temp_dict = deepcopy(pvars.vlans)
            pvars.vlans = []
            for e in temp_dict:
                idict = deepcopy(e)
                idict = intersight.replace_keys(key_list, idict)
                ikeys = list(idict.keys())
                idict.vlan_list = str(idict.vlan_list)
                if 'native_vlan' in ikeys:
                    if idict.native_vlan == False: idict.pop('native_vlan')
                pvars.vlans.append(idict)
        pvars = DotMap(sorted(pvars.items()))
        # Return pvars
        return pvars

    #=============================================================================
    # Function - Modify VSAN Policies
    #=============================================================================
    def modify_vsan(pvars):
        key_list = ['vsan_scope,scope','vsan_id,id']
        pkeys    = list(pvars.keys())
        if 'vsans' in pkeys:
            temp_dict = deepcopy(pvars.vsans)
            pvars.vsans = []
            for e in temp_dict:
                idict = deepcopy(e)
                idict = intersight.replace_keys(key_list, idict)
                ikeys = list(idict.keys())
                if 'zoning' in ikeys: idict.pop('zoning')
                pvars.vsans.append(idict)
        pvars = DotMap(sorted(pvars.items()))
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
                if re.search('_(policies|pools|profiles|templates)', key):
                    p1 = re.search('_(policies|pools|profiles|templates)', key).group(1)
                    p2 = ((key.replace('_policies', '')).replace('_pools', '')).replace('_profiles', '')
                    if p2 == 'boot': p2 = 'boot_order'
                    elif p2 == 'ucs_server_templates': p2 = 'server_template'
                    elif p2 == 'ucs_server_profile_templates': p2 = 'server_template'
                    elif p2 == 'ucs_server': p2 = 'server'
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
                        elif p2 == 'firmware':                 pvars = intersight.modify_firmware(pvars)
                        elif p2 == 'imc_access':               pvars = intersight.modify_imc_access(pvars)
                        elif p2 == 'ipmi_over_lan':            pvars = intersight.modify_ipmi_over_lan(pvars)
                        elif p2 == 'iscsi_boot':               pvars = intersight.modify_iscsi_boot(pvars)
                        elif p2 == 'iscsi_static_target':      pvars = intersight.modify_iscsi_static_target(pvars)
                        elif p2 == 'lan_connectivity':         pvars = intersight.modify_lan_connectivity(pvars)
                        elif p2 == 'local_user':               pvars = intersight.modify_local_user(pvars)
                        elif p2 == 'multicast':                pvars = intersight.modify_multicast(pvars)
                        elif p2 == 'network_connectivity':     pvars = intersight.modify_network_connectivity(pvars)
                        elif p2 == 'port':                     pvars = intersight.modify_port(pvars)
                        elif p2 == 'power':                    pvars = intersight.modify_power(pvars)
                        elif p2 == 'san_connectivity':         pvars = intersight.modify_san_connectivity(pvars)
                        elif p2 == 'sd_card':                  pvars = intersight.modify_sd_card(pvars)
                        elif p2 == 'server':                   pvars = intersight.modify_server(pvars, kwargs)
                        elif p2 == 'server_template':          pvars = intersight.modify_server_template(pvars, kwargs)
                        elif p2 == 'snmp':                     pvars = intersight.modify_snmp(pvars)
                        elif p2 == 'storage':                  pvars = intersight.modify_storage(pvars)
                        elif p2 == 'switch_control':           pvars = intersight.modify_switch_control(pvars)
                        elif p2 == 'syslog':                   pvars = intersight.modify_syslog(pvars)
                        elif p2 == 'system_qos':               pvars = intersight.modify_system_qos(pvars)
                        elif p2 == 'thermal':                  pvars = intersight.modify_thermal(pvars)
                        elif p2 == 'virtual_kvm':              pvars = intersight.modify_virtual_kvm(pvars)
                        elif p2 == 'virtual_media':            pvars = intersight.modify_virtual_media(pvars)
                        elif p2 == 'vlan':                     pvars = intersight.modify_vlan(pvars)
                        elif p2 == 'vsan':                     pvars = intersight.modify_vsan(pvars)
                        elif re.search('ip|iqn|mac|uuid|wwnn|wwpn', p2): pvars = intersight.modify_pools(p2, pvars)
                        if p2 == 'server_template': kwargs.class_path = f'{p1},server'
                        else: kwargs.class_path = f'{p1},{p2}'
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
                    pvars[key1][key2] = deepcopy(pvars[imm_transition])
                else: pvars[easy_imm] = deepcopy(pvars[imm_transition])
                pvars.pop(imm_transition)
        pvars = DotMap(sorted(pvars.items()))
        # return pvars
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
        # return pvars
        return pvars
