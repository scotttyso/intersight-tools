#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import claim_device, ezfunctions, isight, netapp, pcolor, pure_storage, validating
    from copy import deepcopy
    from dotmap import DotMap
    from operator import itemgetter
    from stringcase import snakecase
    import ipaddress, jinja2, json, numpy, os, re, requests, shutil, time, urllib3, uuid
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#=============================================================================
# Intersight Managed Mode Class
#=============================================================================
class imm(object):
    def __init__(self, type):
        self.type  = type
        self.descr = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).title())

    #=========================================================================
    # Function - Build Policies - BIOS
    #=========================================================================
    def bios(self, kwargs):
        btemplates = []
        for i in list(kwargs.server_serials.keys()):
            cpu      = 'Intel' if 'Intel' in kwargs.servers[kwargs.server_serials[i]].processors['1'] else 'AMD'
            gen      = re.search('-(M[0-9]{1,2})', kwargs.servers[kwargs.server_serials[i]].model).group(1)
            template = f"{gen}-{cpu}-Tpm" if kwargs.servers[kwargs.server_serials[i]].tpm.present == True else f"{gen}-{cpu}"
            if kwargs.args.deployment_type == 'azure_stack':
                kwargs.servers[kwargs.server_serials[i]].bios_policy = f'AzureStack-{template}'; btemplates.append(f'AzureStack-{template}')
            else: kwargs.servers[kwargs.server_serials[i]].bios_policy = f'Virtualization-{template}'; btemplates.append(f'Virtualization-{template}')
        btemplates = sorted(list(numpy.unique(numpy.array(btemplates))))
        #=====================================================================
        # Build Dictionary and Add Policy Variables to imm_dict
        #=====================================================================
        for i in btemplates:
            pvars = dict(baud_rate = '115200', bios_template = str(i), boot_performance_mode = 'Max Performance', console_redirection = f'com-0',
                         description = f'{i} {self.descr} Policy', name = i, serial_port_aenable = f'enabled', terminal_type = f'vt100', txt_support = f'enabled')
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policies - Boot Order
    #=========================================================================
    def boot_order(self, kwargs):
        if kwargs.imm.policies.boot_volume == 'iscsi': boot_type = 'iscsi'
        elif kwargs.imm.policies.boot_volume == 'm2':  boot_type = 'm2'
        elif kwargs.imm.policies.boot_volume == 'san': boot_type = 'fcp'
        def boot_policy(boot_type, vic):
            if boot_type == 'iscsi': boot_order_policy = f'Boot-iSCSI-Pxe-{vic.split(":")[0]}-{vic.split(":")[1]}'
            elif boot_type == 'm2':  boot_order_policy = f'Boot-M2-Pxe-{vic.split(":")[0]}-{vic.split(":")[1]}'
            elif boot_type == 'fcp': boot_order_policy = f'Boot-SAN-Pxe-{vic.split(":")[0]}-{vic.split(":")[1]}'
            return boot_order_policy
        boot_order = []
        for i in list(kwargs.server_serials.keys()):
            vdict = DotMap()
            for k,v in kwargs.servers[kwargs.server_serials[i]].adapters.items():
                append = False
                if re.search('V[5-9]', v.model): vic_generation = f'CISCO-G{re.search("V[5-9]", v.model).group(1)}'
                elif 'INTEL' in v.model: vic_generation = 'INTEL'
                elif 'MLNX' in v.model: vic_generation = 'MLNX'
                else: vic_generation = 'CISCO-G4'
                if 'MLOM' in v.pci_slot: vic_slot = 'MLOM'; append = True
                elif not 'MEZZ' in v.pci_slot and 'SlotID' in v.pci_slot: vic_slot = re.search("SlotID:(\\d+)", v.pci_slot).group(1); append = True
                elif re.search("\\d", str(v.pci_slot)): vic_slot = int(v.pci_slot); append = True
                if append == True: vdict[vic_slot] = vic_generation
            vkeys = list(vdict.keys())
            if 'MLOM' in vkeys: kwargs.servers[kwargs.server_serials[i]].boot_order_policy = boot_policy(boot_type, f'{vdict["MLOM"]}:MLOM')
            else:
                for x in range(0,10):
                    if x in vkeys: kwargs.servers[kwargs.server_serials[i]].boot_order_policy = boot_policy(boot_type, f'{vdict[x]}:{x}'); break
        boot_order = list(numpy.unique(numpy.array(boot_order)))
        if len(boot_order) > 0:
            if re.search('Pxe-[a-zA-Z0-9]+-(\\d+)$', b): slot = int(re.search('Pxe-[a-zA-Z0-9]+-(\\d+)$', b).group(1))
            else: slot = re.search('Pxe-[a-zA-Z0-9]+-(.*)$').group(1)
            for b in boot_order:
                pvars = {
                    'boot_devices': [{'device_name': 'kvm', 'device_type': 'virtual_media', 'subtype': 'kvm-mapped-dvd'}],
                    'boot_mode': 'Uefi',
                    'description': f'{b} {self.descr} Policy',
                    'enable_secure_boot': True,
                    'name': b,
                }
                if 'fcp' in boot_type and kwargs.deployment_type == 'flexpod':
                    fabrics = ['a', 'b']
                    for x in range(0,len(fabrics)):
                        for k,v in kwargs.imm_dict.orgs[kwargs.org].storage.items():
                            for e in v:
                                for s in e['wwpns'][chr(ord('@')+x+1).lower()]:
                                    pvars['boot_devices'].append({
                                        'device_name':  e.svm + '-' + s.interface, 'device_type': 'san_boot',
                                        'interface_name': f'vhba{x+1}', 'slot': slot, 'wwpn': s.wwpn})
                elif 'iscsi' in boot_type:
                    fabrics = ['a', 'b']
                    for fab in fabrics:
                            pvars['boot_devices'].append({
                                'device_name': f'storage-{fab}', 'device_type': 'iscsi_boot', 'interface_name': f'storage-{fab}', 'slot': slot})
                elif 'm2' in boot_type:
                    pvars['boot_devices'].extend([{
                        'device_name': f'm2', 'device_type': 'local_disk', 'slot':'MSTOR-RAID'
                    },{
                        'device_name': f'network_pxe', 'device_type': 'pxe_boot', 'interface_name': '', 'interface_source': 'name', 'port': 1, 'slot': slot
                    }])
                if re.search('INTEL|MLNX', b):
                    indx = next((index for (index, d) in enumerate(pvars['boot_devices']) if d['device_type'] == 'pxe_boot'), None)
                    pvars['boot_devices'][indx]['interface_source'] = 'port'
                    pvars['boot_devices'][indx].pop('interface_name')
                else:
                    indx = next((index for (index, d) in enumerate(pvars['boot_devices']) if d['device_type'] == 'pxe_boot'), None)
                    pvars['boot_devices'][indx].pop('port')
                    if len(kwargs.virtualization) > 0 and len(kwargs.virtualization[0].virtual_switches) > 0:
                        if re.search('vswitch0', kwargs.virtualization[0].virtual_switches[0].name, re.IGNORECASE):
                            if len(kwargs.virtualization[0].virtual_switches[0].alternate_name) > 0:
                                name = kwargs.virtualization[0].virtual_switches[0].alternate_name
                            else: name = kwargs.virtualization[0].virtual_switches[0].name
                        else: name = kwargs.virtualization[0].virtual_switches[0].name
                        pvars['boot_devices'][indx]['interface_name'] = name
                pvars['boot_devices'].append({'device_name': 'cimc', 'device_type': 'virtual_media', 'subtype': 'cimc-mapped-dvd'})
                pvars['boot_devices'].append({'device_name': 'uefishell', 'device_type': 'uefi_shell'})
                #=============================================================
                # Add Policy Variables to imm_dict
                #=============================================================
                kwargs.class_path = f'policies,{self.type}'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Profiles - Chassis
    #=========================================================================
    def chassis(self, kwargs):
        #=====================================================================
        # Build Dictionary
        #=====================================================================
        for k, v in kwargs.chassis.items():
            pvars = dict(action = 'Deploy', imc_access_policy = 'KVM', power_policy = k, snmp_policy = 'SNMP', thermal_policy = k, targets = [])
            for i in v:
                pvars['targets'].append(dict(description = f'{i.domain}-{i.identity} {self.descr} Profile',
                                             name = f'{i.domain}-{i.identity}', serial_number = i.serial))
            #=================================================================
            # If using Shared Org update Policy Names
            #=================================================================
            if kwargs.use_shared_org == True and kwargs.org != 'default':
                org = kwargs.shared_org; pkeys = list(pvars.keys())
                for e in pkeys:
                    if re.search('policy|policies$', e): pvars[e] = f'{org}/{pvars[e]}'
            #=================================================================
            # Add Policy Variables to imm_dict
            #=================================================================
            kwargs.class_path = f'profiles,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Compute Dictionary
    #=========================================================================
    def compute_environment(self, kwargs):
        kwargs.servers     = DotMap([])
        kwargs.boot_volume = kwargs.imm.policies.boot_volume
        #=====================================================================
        # Build Domain Dictionaries
        #=====================================================================
        if len(kwargs.domain) > 0:
            #=================================================================
            # Domain/Chassis/Server Inventory
            #=================================================================
            kwargs.api_filter = f"PlatformType in ('UCSFI', 'UCSFIISM')"
            kwargs = isight.api('domains').domain_device_registrations(kwargs)
            kwargs.api_filter = f"SwitchType eq 'FabricInterconnect'"
            kwargs = isight.api('domains').domain_network_elements(kwargs)
            kwargs = isight.api('chassis').chassis_equipment(kwargs)
            for e in ['compute', 'children_equipment']:
                kwargs.api_filter = 'ignore'
                kwargs = eval(f"isight.api('server').server_{e}(kwargs)")
        else:
            #=================================================================
            # Intersight Target(s) - Registration/Validation
            #=================================================================
            org = kwargs.org
            if kwargs.imm.cimc_default == False:
                kwargs.sensitive_var = 'local_user_password_1'
                kwargs  = ezfunctions.sensitive_var_value(kwargs)
                password = kwargs.var_value
            else: password ='Password'
            devices = [e.cimc for e in kwargs.imm.profiles]
            if kwargs.imm_dict.wizard.get('proxy'):
                kwargs.proxy = kwargs.imm_dict.wizard.proxy
                proxy_data = re.search('^http(s)?://(.*):([0-9]+)$', kwargs.proxy.host)
                kwargs.proxy.host = proxy_data.group(2)
                kwargs.proxy.port = proxy_data.group(3)
            else: kwargs.proxy = DotMap(host = '', password = '', port = '', username = '')
            kwargs.yaml.device_list = [DotMap(
                device_type    = 'imc',
                devices        = devices,
                dns_servers    = kwargs.dns_servers,
                password       = password,
                proxy          = kwargs.proxy,
                organization   = kwargs.org,
                resource_group = kwargs.org,
                username       = kwargs.imm.username)]
            kwargs.username = kwargs.imm.username
            kwargs.password = password
            kwargs          = claim_device.claim_targets(kwargs)
            #=================================================================
            # Server Inventory
            #=================================================================
            kwargs.org = org
            for e in ['compute', 'children_equipment']:
                kwargs.api_filter = 'ignore'; kwargs = eval(f"isight.api('server').server_{e}(kwargs)")
            for k,v in kwargs.servers.items():
                if len(v.kvm_ip_addresses) > 0:
                    for i in v.kvm_ip_addresses: kwargs.server_ips[i] = k
            dlist = ['enable_dhcp', 'enable_dhcp_dns', 'enable_ipv6', 'enable_ipv6_dhcp']
            for k, v in kwargs.result.items():
                kwargs.server_serials[v.serial] = kwargs.server_ips[k]
                for e in dlist: kwargs.servers[kwargs.server_ips[k]][e] = v[e]
                indx = next((index for (index, d) in enumerate(kwargs.imm.profiles) if d.cimc == k), None)
                kwargs.servers[kwargs.server_ips[k]].active_directory = kwargs.imm.profiles[indx].active_directory
                kwargs.servers[kwargs.server_ips[k]].azure_stack = kwargs.imm.profiles[indx].azure_stack
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Profiles - Domain
    #=========================================================================
    def domain(self, kwargs):
        #=====================================================================
        # Build Dictionary
        #=====================================================================
        name = kwargs.domain.name
        pvars = dict(
            action = 'Deploy', description = f'{name} {self.descr} Profile', name = name, network_connectivity_policy = 'DNS',
            ntp_policy = 'NTP', port_policies = [f'{name}-{l}' for l in ['A', 'B']], serial_numbers = kwargs.domain.serial_numbers,
            snmp_policy = 'SNMP', switch_control_policy = 'Sw-Ctrl', syslog_policy = 'Syslog', system_qos_policy = 'QoS', vlan_policies = ['VLANs'])
        if kwargs.domain.get('vsans'):
            pvars['vsan_policies'] = []
            for i in kwargs.domain.vsans: pvars['vsan_policies'].append(f'VSAN-{i}')
        #=====================================================================
        # If using Shared Org update Policy Names
        #=====================================================================
        if kwargs.use_shared_org == True and kwargs.org != 'default':
            org = kwargs.shared_org; pkeys = list(pvars.keys())
            for e in pkeys:
                if re.search('policy|policies$', e):
                    if type(pvars[e]) == list:
                        pvars[e] = [f'{org}/{d}' for d in pvars[e]]
                        #temp = pvars[e]; pvars[e] = []
                        #for d in temp: pvars[e].append(f'{org}/{d}')
                    else: pvars[e] = f'{org}/{pvars[e]}'
        #=====================================================================
        # Add Policy Variables to imm_dict and return kwargs
        #=====================================================================
        kwargs.class_path = f'profiles,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Ethernet Adapter
    #=========================================================================
    def ethernet_adapter(self, kwargs):
        plist = ['16RxQs-4G', '16RxQs-5G']
        for item in kwargs.virtualization:
            if item.type == 'vmware': plist.extend(['VMware', 'VMware-High-Trf'])
        #=====================================================================
        # Build Dictionary and Add Policy Variables to imm_dict
        #=====================================================================
        for i in plist:
            pvars = dict(adapter_template = i, description = f'{i} {self.descr} Policy', name = i)
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Ethernet Network Control
    #=========================================================================
    def ethernet_network_control(self, kwargs):
        name  = (kwargs.domain.discovery_protocol).upper()
        cdpe  = True if 'CDP' in name else False
        lldpe = True if 'LLDP' in name else False
        #=====================================================================
        # Build Dictionary, Add Policy Variables to imm_dict and return kwargs
        #=====================================================================
        pvars = dict(cdp_enable = cdpe, description = f'{name} {self.descr} Policy', name = name, lldp_enable_receive = lldpe, lldp_enable_transmit = lldpe)
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Ethernet Network Group
    #=========================================================================
    def ethernet_network_group(self, kwargs):
        #=====================================================================
        # Function - Assign Configuration to Policy and return kwargs
        #=====================================================================
        def create_eth_groups(kwargs):
            pvars = dict(
                allowed_vlans = kwargs.allowed, description = f'{kwargs.name} {self.descr} Policy',
                name = kwargs.name, native_vlan = kwargs.native,)
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
            return kwargs
        #=====================================================================
        # Add All VLANs for Guest vSwitch
        #=====================================================================
        vlans = []
        for i in kwargs.vlans: vlans.append(i.vlan_id)
        for i in kwargs.ranges: vrange = ezfunctions.vlan_list_full(i.vlan_list); vlans.extend(vrange)
        vlans = list(numpy.unique(numpy.array(vlans))); vlans.sort()
        kwargs.vlan.all_vlans = ezfunctions.vlan_list_format(vlans)
        kwargs.disjoint= False
        kwargs.iscsi = 0;  kwargs.iscsi_vlans= []; kwargs.nvme = 0; kwargs.nvme_vlans = []
        for i in kwargs.vlans:
            if i.disjoint == True: kwargs.disjoint = True
            if i.vlan_type == 'iscsi': kwargs.iscsi+=1; kwargs.iscsi_vlans.append(i.vlan_id)
            elif i.vlan_type == 'nvme': kwargs.nvme+=1; kwargs.nvme_vlans.append(i.vlan_id)
        #=====================================================================
        # Create Uplink Groups if Disjoint is Present
        #=====================================================================
        if kwargs.disjoint == True:
            disjoint_vlans = []; disjoint_native = 1; native = 1
            for i in kwargs.vlans:
                if i.disjoint == True:
                    disjoint_vlans.append(i.vlan_id)
                    if i.native_vlan == True: disjoint_native = i.vlan_id
                elif i.native_vlan == True: native = i.vlan_id

            for i in kwargs.ranges:
                if i.disjoint == True: disjoint_vlans.extend(ezfunctions.vlan_list_full(i.vlan_list))
            disjoint_vlans = sorted(list(numpy.unique(numpy.array(disjoint_vlans))))
            uplink1        = vlans
            for i in disjoint_vlans: uplink1.remove(i)
            kwargs.uplink1 = ezfunctions.vlan_list_format(uplink1)
            kwargs.uplink2 = ezfunctions.vlan_list_format(disjoint_vlans)
            kwargs.name    = 'Uplink1'
            kwargs.allowed = kwargs.uplink1
            kwargs.native  = native
            kwargs         = create_eth_groups(kwargs)
            kwargs.name    = 'Uplink2'
            kwargs.allowed = kwargs.uplink2
            kwargs.native  = disjoint_native
            kwargs         = create_eth_groups(kwargs)
        #=====================================================================
        # Create Eth NetworkGroups for Virtual Switches
        #=====================================================================
        for item in kwargs.virtualization:
            for i in item.virtual_switches:
                if re.search('vswitch0', i.name, re.IGNORECASE): kwargs.name = i.alternate_name
                else: kwargs.name = i.name
                kwargs.native= 1
                if 'guests' in i.data_types:
                    kwargs.name = 'all_vlans'
                    kwargs.allowed= kwargs.vlan.all_vlans
                    if 'management' in i.data_types:
                        kwargs.native = kwargs.inband.vlan_id
                        kwargs        = create_eth_groups(kwargs)
                    elif 'storage' in i.data_types:
                        if kwargs.iscsi == 2:
                            for x in range(0,2):
                                if re.search('[A-Z]', i.name): suffix = chr(ord('@')+x+1)
                                else: suffix = chr(ord('@')+x+1).lower()
                                kwargs.name  = f"{i.name}-{suffix}"
                                kwargs.native= kwargs.iscsi_vlans[x]
                                kwargs       = create_eth_groups(kwargs)
                        elif 'migration' in i.data_types:
                            kwargs.native = kwargs.migration.vlan_id
                            kwargs        = create_eth_groups(kwargs)
                        else: kwargs = create_eth_groups(kwargs)
                    elif 'migration' in i.data_types:
                            kwargs.native = kwargs.migration.vlan_id
                            kwargs        = create_eth_groups(kwargs)
                    else: kwargs = create_eth_groups(kwargs)
                elif 'management' in i.data_types:
                    kwargs.native = kwargs.inband.vlan_id
                    mvlans        = [kwargs.inband.vlan_id]
                    if 'migration' in i.data_types: mvlans.append(kwargs.migration.vlan_id)
                    if 'storage' in i.data_types:
                        for v in kwargs.vlans:
                            if re.search('(iscsi|nfs|nvme)', v.vlan_type): mvlans.append(v.vlan_id)
                    mvlans.sort()
                    kwargs.allowed = ezfunctions.vlan_list_format(mvlans)
                    kwargs         = create_eth_groups(kwargs)
                elif 'migration' in i.data_types:
                    kwargs.native= kwargs.migration.vlan_id
                    mvlans       = [kwargs.migration.vlan_id]
                    if 'storage' in i.data_types:
                        for v in kwargs.vlans:
                            if re.search('(iscsi|nfs|nvme)', v.vlan_type): mvlans.append(v.vlan_id)
                    mvlans.sort()
                    kwargs.allowed= ezfunctions.vlan_list_format(mvlans)
                    kwargs        = create_eth_groups(kwargs)
                elif 'storage' in i.data_types:
                    if kwargs.iscsi == 2:
                        for x in range(0,2):
                            if re.search('[A-Z]', i.name): suffix = chr(ord('@')+x+1)
                            else: suffix  = chr(ord('@')+x+1).lower()
                            kwargs.native = kwargs.iscsi_vlans[x]
                            kwargs.name   = f"{i.name}-{suffix}"
                            svlans        = [kwargs.iscsi_vlans[x]]
                            for v in kwargs.vlans:
                                if re.search('(nfs|nvme)', v.vlan_type): svlans.append(v.vlan_id)
                            kwargs.allowed = ezfunctions.vlan_list_format(svlans)
                            kwargs         = create_eth_groups(kwargs)
                    else:
                        mvlans = [kwargs.migration.vlan_id]
                        for v in kwargs.vlans:
                            if re.search('(iscsi|nfs|nvme)', v.vlan_type): mvlans.append(v.vlan_id)
                        mvlans.sort()
                        kwargs.allowed = ezfunctions.vlan_list_format(mvlans)
                        kwargs         = create_eth_groups(kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Ethernet QoS
    #=========================================================================
    def ethernet_qos(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        plist = ['Best Effort', 'Bronze', 'Gold', 'Platinum', 'Silver'] if kwargs.domain.cfg_qos_priorities == True else ['Best Effort']
        for i in plist:
            pvars = dict(
                enable_trust_host_cos = False, burst = 10240,
                description  = f'{i.replace(" ", "-")} {self.descr} Policy',
                name = i.replace(' ', '-'), mtu = 9000, priority = i, rate_limit = 0)
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - FC Zone
    #=========================================================================
    def fc_zone(self, kwargs):
        fabrics = ['A', 'B']
        kwargs.fc_zone = []
        #=====================================================================
        # Build Dictionary and add to `imm_dict`
        #=====================================================================
        for x in range(0,len(fabrics)):
            if len(kwargs.domain.vsans) == 2: vsan = kwargs.domain.vsans[x]
            else: vsan = kwargs.domain.vsans[0]
            name = f'Fabric-{fabrics[x]}-VSAN-{vsan}'
            pvars = dict(description = f'{name} {self.descr} Policy',
                         fc_target_zoning_type = 'SIMT', name = name, targets = [])
            kwargs.storage = kwargs.imm_dict.orgs[kwargs.org].storage
            for k, v in kwargs.storage.items():
                for e in v:
                    for i in e.wwpns[fabrics[x].lower()]:
                        pvars['targets'].append(dict(
                            name = e.svm + '-' + i.interface, switch_id = fabrics[x], vsan_id = vsan, wwpn = i.wwpn))
            kwargs.fc_zone.append(pvars['name'])
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Fibre-Channel Adapter
    #=========================================================================
    def fibre_channel_adapter(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        for i in ['VMware', 'FCNVMeInitiator']:
            pvars = dict(adapter_template = i, description = f'{i} {self.descr} Policy', name = i,)
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Fibre-Channel Network
    #=========================================================================
    def fibre_channel_network(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        for i in kwargs.domain.vsans:
            pvars  = dict(description = f'VSAN-{i} {self.descr} Policy', name = f'VSAN-{i}', vsan_id = i)
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Fibre-Channel QoS
    #=========================================================================
    def fibre_channel_qos(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars  = dict( max_data_field_size = 2112, burst = 10240, description = f'FC-QoS {self.descr} Policy', name = 'FC-QoS', rate_limit = 0)
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policies - Firmware
    #=========================================================================
    def firmware(self, kwargs):
        #=====================================================================
        # Build Dictionary
        #=====================================================================
        fw       = kwargs.imm.firmware
        fw_name = (fw.replace(')', '')).replace('(', '-')
        models   = []
        for k in list(kwargs.servers.keys()):
            m = re.search('(M[\\d]{1,2}[A-Z]?[A-Z]?)', kwargs.servers[k].model).group(1)
            g = re.search('(M[\\d]{1,2})', kwargs.servers[k].model).group(1)
            model = kwargs.servers[k].model.replace(m, g)
            if not model in models: models.append(model)
            kwargs.servers[k].firmware_policy = fw_name
        models.sort()
        kwargs.firmware_policy_name = fw_name
        pvars = dict(description = f'{fw_name} {self.descr} Policy', model_bundle_version = [], name = fw_name, target_platform = 'FIAttached')
        if len(kwargs.domain) > 0:
            stypes = ['blades', 'rackmount']
            for s in stypes: pvars['model_bundle_version'].append(dict(firmware_version= kwargs.domain.firmware[s], server_models = []))
            for i in models:
                if 'UCSC' in i: pvars['model_bundle_version'][1]['server_models'].append(i)
                else: pvars['model_bundle_version'][0]['server_models'].append(i)
        else:
            pvars['target_platform'] = 'Standalone'
            pvars['model_bundle_version'].append(dict(firmware_version= kwargs.imm.firmware, server_models = []))
            for i in models: pvars['model_bundle_version'][0]['server_models'].append(i)
        #=====================================================================
        # Add to `imm_dict` and return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        pvars = dict(cco_password = 1, cco_user = 1)
        return kwargs

    #=========================================================================
    # Function - Build Policies - Firmware
    #=========================================================================
    def firmware_authenticate(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        kwargs.class_path  = f'policies,firmware_authenticate'
        kwargs.append_type = 'map'
        kwargs = ezfunctions.ez_append(dict(cco_password = 1, cco_user = 1), kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Flow Control
    #=========================================================================
    def flow_control(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(dict(description = f'{self.descr} Policy', name = 'FlowCtrl'), kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - IMC Access
    #=========================================================================
    def imc_access(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(description = f'KVM {self.descr} Policy', inband_ip_pool = f'KVM-InBand', inband_vlan_id = kwargs.inband.vlan_id,
                     out_of_band_ip_pool = 'KVM-OoBand', name = 'KVM')
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Pools - IP
    #=========================================================================
    def ip(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`
        #=====================================================================
        pdns = kwargs.dns_servers[0]
        sdns = kwargs.dns_servers[1] if len(kwargs.dns_servers) >= 2 else ''
        for i in kwargs.vlans:
            if re.search('(inband|iscsi|ooband)', i.vlan_type):
                if not kwargs.pools.ip.get(i.vlan_type): kwargs.pools.ip[i.vlan_type] = []
                if re.search('inband|ooband', i.vlan_type):
                    name = 'KVM-InBand' if 'inband' in i.vlan_type else 'KVM-OoBand'; ips = i.pool
                else: name = f'iSCSI-VLAN{i.vlan_id}'; ips = i.server
                kwargs.pools.ip[i.vlan_type].append(name)
                args = DotMap(defaultGateway = i.gateway, subnetMask = i.netmask, ip_version = 'v4', pool_from = ips[0], pools_to = ips[-1])
                validating.error_subnet_check(args)
                size = int(ipaddress.IPv4Address(ips[-1])) - int(ipaddress.IPv4Address(ips[0])) + 1
                pvars = dict(
                    assignment_order = 'sequential', description = f'{name} {self.descr} Pool', name = f'{name}',
                    ipv4_blocks = [{'from':ips[0], 'gateway':i.gateway, 'netmask':i.netmask, 'primary_dns':pdns, 'secondary_dns':sdns, 'size':size}])
                kwargs.class_path = f'pools,{self.type}'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Pools - IQN
    #=========================================================================
    def iqn(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(
            assignment_order = 'sequential', description = f'iSCSI {self.descr} Pool',
            iqn_blocks = [{'from': 0, 'size': 255, 'suffix': 'ucs-host'}], name = 'iSCSI', prefix = f'iqn.1984-12.com.cisco',)
        kwargs.class_path = f'pools,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - IPMI over LAN
    #=========================================================================
    def ipmi_over_lan(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(description = f'{self.descr} Policy', name = 'IPMI', privilege = 'read-only')
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - iSCSI Adapter
    #=========================================================================
    def iscsi_adapter(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(description = f'{self.descr} Policy', dhcp_timeout = 60, name = 'Adapter', lun_busy_retry_count = 15, tcp_connection_timeout = 15,)
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - iSCSI Boot
    #=========================================================================
    def iscsi_boot(self, kwargs):
        fabrics = ['a', 'b']
        targets = []
        for i in range(0, len(kwargs.iscsi.targets), 2): targets.append(kwargs.iscsi.targets[i:i+2])
        kwargs.a.targets  = targets[0]
        kwargs.b.targets  = targets[1]
        kwargs.iscsi.boot = []
        #=====================================================================
        # Build Dictionaries and add to `imm_dict`
        #=====================================================================
        for x in range(0,2):
            pool = kwargs.pools.ip.iscsi[x]
            pvars = dict(
                description = f'{pool} {self.descr} Policy', initiator_ip_source = 'Pool',
                initiator_ip_pool = kwargs.pools.ip.iscsi[x],  iscsi_adapter_policy    = 'Adapter',
                name = pool, primary_target_policy = kwargs[fabrics[x]].targets[0],
                secondary_target_policy = kwargs[fabrics[x]].targets[1], target_source_type = f'Static')
            kwargs.iscsi.boot.append(pvars['name'])
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - iSCSI Target
    #=========================================================================
    def iscsi_static_target(self, kwargs):
        #=====================================================================
        # Build Dictionaries and add to `imm_dict`
        #=====================================================================
        kwargs.iscsi.targets = []
        for k, v in kwargs.imm_dict.orgs[kwargs.org].storage.items():
            for e in v:
                for i in e.iscsi.interfaces:
                    name = e.svm + ':' + i.interface
                    pvars = dict(
                        description = f'{name} {self.descr} Policy', ip_address  = i.ip_address,
                        lun_id = 0, name = name, port = 3260, target_name = v[0].iscsi.iqn)
                    kwargs.iscsi.targets.append(name)
                    kwargs.class_path = f'policies,{self.type}'
                    kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - LAN Connectivity
    #=========================================================================
    def lan_connectivity(self, kwargs):
        # Build Dictionary
        descr= ezfunctions.mod_pol_description((self.type.replace('_', ' ')).title())
        vics = []
        for k, v in kwargs.servers.items():
            if len(v.vics) == 2: vics = f'{v.vics[0].vic_gen}:{v.vics[0].vic_slot}-{v.vics[1].vic_slot}'
            else: vics = f'{v.vics[0].vic_gen}:{v.vics[0].vic_slot}'
        kwargs.vic_details= list(numpy.unique(numpy.array(vics)))
        lan_policies = ['lcp']
        iscsi_vlan = False
        for i in kwargs.vlans:
            if i.vlan_type == 'iscsi': iscsi_vlan = True
        if iscsi_vlan == True: lan_policies.append('lcp-iscsi')
        for g in kwargs.vic_details:
            for lcp in lan_policies:
                ga       = g.split(':')
                gen      = ga[0]
                name     = (f'{lcp}-vic-{g}').lower()
                pci_order= kwargs.pci_order
                slots    = (ga[1]).split('-')
                pvars  = dict(
                    description          = f'{name} {descr} Policy',
                    iqn_pool             = '',
                    name                 = name,
                    target_platform      = 'FIAttached',
                    vnics                = [],
                )
                if re.search('iscsi', lcp):
                    pvars['iqn_pool'] = f'iscsi'
                else: pvars.pop('iqn_pool')
                iscsi = 0
                for v in kwargs.vlans:
                    if 'iscsi' in v.vlan_type: iscsi+=1
                vnic_count = 0
                for e in kwargs.virtualization:
                    for i in e.virtual_switches:
                        if re.search('vswitch0', i.name, re.IGNORECASE):
                            name = i.alternate_name
                        else: name = i.name
                        if re.search('[A-Z]', name): a = 'A'; b = 'B'
                        else: a = 'a'; b = 'b'
                        if 'guests' in i.data_types:
                            if iscsi==2 and 'storage' in i.data_types: network_groups = [
                                    f'{name}-{a}',
                                    f'{name}-{b}']
                            else: network_groups = ['all_vlans']
                        elif 'storage' in i.data_types:
                            if iscsi==2: network_groups = [
                                    f'{name}-{a}',
                                    f'{name}-{b}']
                            else: network_groups = [name]
                        else: network_groups = [name]
                        if   'storage' in i.data_types:
                            if gen == 'gen5': adapter_policy= '16RxQs-5G'
                            else: adapter_policy= '16RxQs-4G'
                            if kwargs.domain.cfg_qos_priorities == True: qos_policy = 'Platinum'
                            else: qos_policy = 'Best-Effort'
                        elif 'guests' in i.data_types:
                            if e.type == 'vmware': adapter_policy= 'VMware-High-Trf'
                            if kwargs.domain.cfg_qos_priorities == True: qos_policy = 'Gold'
                            else: qos_policy = 'Best-Effort'
                        elif 'migration' in i.data_types:
                            if e.type == 'vmware': adapter_policy= 'VMware-High-Trf'
                            if kwargs.domain.cfg_qos_priorities == True: qos_policy = 'Bronze'
                            else: qos_policy = 'Best-Effort'
                        else:
                            if e.type == 'vmware': adapter_policy = 'VMware'
                            if kwargs.domain.cfg_qos_priorities == True: qos_policy = 'Silver'
                            else: qos_policy = 'Best-Effort'
                        qos_policy = 'Best-Effort'
                        if len(slots) == 1: placement_order = pci_order, pci_order + 1,
                        else: placement_order = pci_order, pci_order
                        pvars['vnics'].append(dict(
                            ethernet_adapter_policy        = adapter_policy,
                            ethernet_network_control_policy= kwargs.domain.discovery_protocol,
                            ethernet_network_group_policies= network_groups,
                            ethernet_qos_policy            = qos_policy,
                            iscsi_boot_policies            = [],
                            names                          = [f'{name}-{a}', f'{name}-{b}'],
                            mac_address_pools              = [f'{name}-{a}', f'{name}-{b}'],
                            placement = dict(
                                pci_order = placement_order,
                                slot_ids  = slots
                            )
                        ))
                        if 'storage' in i.data_type and 'iscsi' in lcp:
                            pvars['vnics'][vnic_count].update({'iscsi_boot_policies': kwargs.iscsi.boot})
                        else: pvars['vnics'][vnic_count].pop('iscsi_boot_policies')
                        if len(slots) == 1: pci_order += 2
                        else: pci_order += 1
                        vnic_count += 1
                # Add Policy Variables to imm_dict
                kwargs.class_path = f'policies,{self.type}'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        kwargs.pci_order = pci_order
        return kwargs

    #=========================================================================
    # Function - Build Policy - Link Aggregation
    #=========================================================================
    def link_aggregation(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(dict(description = f'LinkAgg {self.descr} Policy', name = 'LinkAgg'), kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Link Control
    #=========================================================================
    def link_control(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(dict(description = f'LinkCtrl {self.descr} Policy', name = 'LinkCtrl'), kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Local User
    #=========================================================================
    def local_user(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        if len(kwargs.domain) > 0: username = kwargs.domain.policies.local_user
        else: username = kwargs.imm.policies.local_user
        pvars = dict(
            description = f'Users {descr} Policy',
            name        = 'Users',
            users       = [dict(
                enabled  = True,
                password = 1,
                role     = 'admin',
                username = username
            )]
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Pools - MAC
    #=========================================================================
    def mac(self, kwargs):
        # Build Dictionary
        mcount = 1
        for e in kwargs.virtualization:
            for i in e.virtual_switches:
                for x in range(0,2):
                    if re.search('vswitch0', i.name, re.IGNORECASE):
                        name = i.alternate_name
                    else: name = i.name
                    if re.search('[A-Z]', name): pool= name + '-' + chr(ord('@')+x+1)
                    else: pool= name + '-' + chr(ord('@')+x+1).lower()
                    pid = mcount + x
                    if pid > 8: pid=chr(ord('@')+pid-8)
                    pvars = dict(
                        assignment_order = 'sequential',
                        description      = f'{pool} Pool',
                        name             = pool,
                        mac_blocks       = [{
                            'from':f'00:25:B5:{kwargs.domain.pools.prefix}:{pid}0:00',
                            'size':255
                        }],
                    )
                    # Add Policy Variables to imm_dict
                    kwargs.class_path = f'pools,{self.type}'
                    kwargs = ezfunctions.ez_append(pvars, kwargs)
                # Increment MAC Count
                mcount = mcount + 2
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Multicast
    #=========================================================================
    def multicast(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(dict(description = f'Mcast {self.descr} Policy', name = 'Mcast'), kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Network Connectivity
    #=========================================================================
    def network_connectivity(self, kwargs):
        #=====================================================================
        # Build Dictionary
        #=====================================================================
        if len(kwargs.dhcp_servers) > 0 and kwargs.deployment_type == 'azure_stack':
            enable_dhcp = True; enable_dhcp_dns = True; enable_ipv6 = False; enable_ipv6_dhcp = False
            e = kwargs.servers[list(kwargs.servers.keys())[0]]
            if (e.get('enable_dhcp') is not None) and (e.enable_dhcp == 'no'): enable_dhcp = False
            if (e.get('enable_dhcp_dns') is not None) and (e.enable_dhcp_dns == 'no'): enable_dhcp_dns = False
            if (e.get('enable_ipv6') is not None) and (e.enable_ipv6 == 'yes'): enable_ipv6 = True
            if (e.get('enable_ipv6_dhcp') is not None) and (e.enable_ipv6_dhcp == 'yes'): enable_ipv6_dhcp = True
            pvars = dict(
                description = f'DNS {self.descr} Policy', dns_servers_v4 = kwargs.dns_servers,
                enable_dynamic_dns = True, enable_ipv6 = False, name = 'DNS',
                obtain_ipv4_dns_from_dhcp= True, obtain_ipv6_dns_from_dhcp= False)
            pop_list = []
            if enable_dhcp == False: pop_list.extend(['enable_dynamic_dns', 'obtain_ipv4_dns_from_dhcp'])
            elif enable_dhcp_dns == False: pop_list.append('obtain_ipv4_dns_from_dhcp')
            elif enable_dhcp_dns == True: pop_list.append('dns_servers_v4')
            if enable_ipv6 == True:
                pvars['enable_ipv6'] = True
                if enable_ipv6_dhcp == True and enable_dhcp_dns == True: pvars['obtain_ipv6_dns_from_dhcp'] = True
            else: pop_list.extend(['enable_ipv6', 'obtain_ipv6_dns_from_dhcp'])
            for i in pop_list: pvars.pop(i)
        else: pvars = dict(description = f'DNS {self.descr} Policy', dns_servers_v4 = kwargs.dns_servers, name = 'DNS')
        #=====================================================================
        # Add Policy Variables to imm_dict and return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,network_connectivity'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - NTP
    #=========================================================================
    def ntp(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(description = f'NTP {self.descr} Policy', name = 'NTP', ntp_servers = kwargs.ntp_servers, timezone = kwargs.timezone)
        kwargs.class_path = f'policies,ntp'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Port
    #=========================================================================
    def port(self, kwargs):
        def ethernet_pc_uplinks(kwargs):
            idict = dict(
                admin_speed                  = 'Auto',
                ethernet_network_group_policy= kwargs.vlan_group,
                flow_control_policy          = 'flow-ctrl',
                interfaces                   = kwargs.ports,
                link_aggregation_policy      = 'link-agg',
                link_control_policy          = 'link-ctrl',
                pc_ids                       = [kwargs.pc_id, kwargs.pc_id],
            )
            return idict
        eth_breakout_ports = []
        #=====================================================================
        # Base Dictionary
        #=====================================================================
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description  = f'{kwargs.domain.name} {descr} Policy',
            device_model = kwargs.domain.device_model,
            names        = [f'{kwargs.domain.name}-A', f'{kwargs.domain.name}-B'],
            port_channel_ethernet_uplinks = []
        )
        #=====================================================================
        # Uplink Port-Channels
        #=====================================================================
        x = str(kwargs.domain.eth_uplinks[0]).split('/')
        if len(x) == 3: eth_breakout_ports.extend(kwargs.domain.eth_uplinks)
        if kwargs.disjoint == True:
            # First Uplink
            plength = len(kwargs.domain.eth_uplinks) // 2
            kwargs.ports = []
            for i in kwargs.domain.eth_uplinks[:plength]:
                kwargs.ports.append({'port_id':int(i.split('/')[-1])})
            if len(x) == 3: pc_id = '1' + x[1] + x[2]
            else: pc_id = x[-1]
            kwargs.pc_id     = int(pc_id)
            kwargs.vlan_group= 'uplink1'
            pvars['port_channel_ethernet_uplinks'].append(ethernet_pc_uplinks(kwargs))
            # Second Uplink
            kwargs.ports = []
            for i in kwargs.domain.eth_uplinks[plength:]:
                kwargs.ports.append({'port_id':int(i.split('/')[-1])})
            x = str(kwargs.domain.eth_uplinks[plength:][0]).split('/')
            if len(x) == 3: pc_id = '1' + x[1] + x[2]
            else: pc_id = x[-1]
            kwargs.pc_id     = int(pc_id)
            kwargs.vlan_group= 'uplink2'
            pvars['port_channel_ethernet_uplinks'].append(ethernet_pc_uplinks(kwargs))
        else:
            kwargs.ports = []
            for i in kwargs.domain.eth_uplinks:
                kwargs.ports.append({'port_id':int(i.split('/')[-1])})
            if len(x) == 3: pc_id = '1' + x[1] + x[2]
            else: pc_id = x[-1]
            kwargs.pc_id     = int(pc_id)
            kwargs.vlan_group= 'all_vlans'
            pvars['port_channel_ethernet_uplinks'].append(ethernet_pc_uplinks(kwargs))
        #=====================================================================
        # Fibre-Channel Uplinks/Port-Channels
        #=====================================================================
        if kwargs.domain.get('vsans'):
            ports= []
            x    = kwargs.domain.fcp_uplink_ports[0].split('/')
            if kwargs.swmode == 'end-host':
                if len(x) == 3: pc_id = '1' + x[1] + x[2]
                else: pc_id = x[-1]
                pvars.update(dict(
                    port_channel_fc_uplinks = [dict(
                        admin_speed  = kwargs.domain.fcp_uplink_speed,
                        fill_pattern = 'Idle',
                        interfaces   = [],
                        pc_ids       = [pc_id, pc_id],
                        vsan_ids     = kwargs.domain.vsans
                    )]
                ))
                for i in kwargs.domain.fcp_uplink_ports:
                    idict = {}
                    if len(x) == 3: idict.append({'breakout_port_id':int(i.split('/')[-2])})
                    idict.append({'port_id':int(i.split('/')[-1])})
                    pvars['port_channel_fc_uplinks']['interfaces'].append(idict)
            else:
                pvars['port_role_fc_storage'] = []
                if x == 3:
                    breakout = []
                    for i in kwargs.domain.fcp_uplink_ports:
                        breakout.append(int(i.split('/')[-2]))
                    breakout = list(numpy.unique(numpy.array(breakout)))
                    for item in breakout:
                        port_list = []
                        for i in kwargs.domain.fcp_uplink_ports:
                            if int(item) == int(i.split('/')[-2]):
                                port_list.append(int(i.split('/')[-1]))
                        port_list = ezfunctions.vlan_list_format(port_list)
                        idict = dict(
                            breakout_port_id = item,
                            admin_speed      = kwargs.domain.fcp_uplink_speed,
                            port_list        = port_list,
                            vsan_ids         = kwargs.domain.vsans
                        )
                        pvars['port_role_fc_storage'].append(idict)
                else:
                    port_list = []
                    for i in kwargs.domain.fcp_uplink_ports:
                        port_list.append(int(i.split('/')[-1]))
                    port_list = ezfunctions.vlan_list_format(port_list)
                    idict = dict(
                        admin_speed  = kwargs.domain.fcp_uplink_speed,
                        port_list    = port_list,
                        vsan_ids     = kwargs.domain.vsans
                    )
                    pvars['port_role_fc_storage'].append(idict)
            #=================================================================
            # Configure Fibre Channel Unified Port Mode
            #=================================================================
            if len(x) == 3:
                port_start = int(kwargs.domain.fcp_uplink_ports[0].split('/')[-2])
                port_end   = int(kwargs.domain.fcp_uplink_ports[-1].split('/')[-2])
                pvars.update(dict(
                    port_modes = [dict(
                        custom_mode = f'BreakoutFibreChannel{kwargs.domain.fcp_uplink_speed}',
                        port_list   = [port_start, port_end]
                    )]
                ))
            else:
                port_start = int(kwargs.domain.fcp_uplink_ports[0].split('/')[-1])
                port_end   = int(kwargs.domain.fcp_uplink_ports[-1].split('/')[-1])
                if port_start < 15: port_start = 1
                if port_end > 12: port_end = 16
                elif port_end > 8: port_end = 12
                elif port_end > 4: port_end = 8
                else: port_end = 4
                pvars.update(dict(
                    port_modes = [dict(
                        custom_mode = 'FibreChannel',
                        port_list   = [port_start, port_end]
                    )]
                ))
        #=====================================================================
        # Ethernet Uplink Breakout Ports if present
        #=====================================================================
        if len(eth_breakout_ports) > 0:
            port_start= int(eth_breakout_ports[0].split('/'))[2]
            port_end  = int(eth_breakout_ports[-1].split('/'))[2]
            pvars['port_modes'].append(dict(
                custom_mode = f'BreakoutEthernet{kwargs.domain.eth_breakout_speed}',
                port_list   = [port_start, port_end]
            ))
        #=====================================================================
        # Server Ports
        #=====================================================================
        pvars.update({'port_role_servers':[]})
        for i in kwargs.domain.profiles:
            if len(i.domain_ports[0].split('/')) == 3:
                port_start= int(i.domain_ports[0].split('/'))[2]
                port_end  = int(i.domain_ports[-1].split('/'))[2]
                pvars['port_modes'].append(dict(
                    custom_mode = f'BreakoutEthernet{kwargs.domain.eth_breakout_speed}',
                    port_list   = [port_start, port_end]
                ))
                for e in i.domain_ports:
                    pvars['port_role_servers'].append(dict(
                        breakout_port_id      = e.split('/')[-2],
                        connected_device_type = i.equipment_type,
                        device_number         = i.identifier,
                        port_list             = e.split('/')[-1]
                    ))
            else:
                ports = []
                for e in i.domain_ports: ports.append(int(e.split('/')[-1]))
                port_list = ezfunctions.vlan_list_format(ports)
                pvars['port_role_servers'].append(dict(
                    connected_device_type = i.equipment_type,
                    device_number         = i.identifier,
                    port_list             = port_list
                ))
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Power
    #=========================================================================
    def power(self, kwargs):
        #=====================================================================
        # Build Dictionaries and add to `imm_dict`
        #=====================================================================
        power_list = [i for i in kwargs.chassis] + ['Server']
        for i in power_list:
            pvars = dict(description = f'{i} {self.descr} Policy', name = i, power_allocation = 0, power_redundancy = 'Grid')
            if i == 'Server': pvars.update({'power_restore':'LastState'})
            if '9508' in i: pvars['power_allocation'] = 8400
            else: pvars.pop('power_allocation')
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - SAN Connectivity
    #=========================================================================
    def san_connectivity(self, kwargs):
        # Build Dictionary
        descr     = (self.type.replace('_', ' ')).title()
        pci_order = kwargs.pci_order
        for g in kwargs.vic_details:
            gen      = g.split(':')[0]
            name     = (f'scp-vic-{g}').lower()
            slots    = (g.split(':')[1]).split('-')
            pvars = dict(
                description          = f'{name} {descr} Policy',
                name                 = name,
                target_platform      = 'FIAttached',
                vhbas                = [],
                wwnn_allocation_type = 'POOL',
                wwnn_pool            = f'wwnn',
            )
            ncount = 1
            if 'nvme-fc' in kwargs.protocols: adapter_list = ['VMware', 'FCNVMeInitiator']
            else: adapter_list = ['VMware']
            vcount = 0
            network_policies = []
            for v in kwargs.domain.vsans: network_policies.append(f'vsan-{v}')
            if len(slots) == 1: placement_order = pci_order, pci_order + 1,
            else: placement_order = pci_order, pci_order,
            for x in range(0,len(adapter_list)):
                pvars['vhbas'].append(dict(
                    fc_zone_policies              = [],
                    fibre_channel_adapter_policy  = adapter_list[x],
                    fibre_channel_network_policies= network_policies,
                    fibre_channel_qos_policy      = 'fc-qos',
                    names                         = [f'vhba{ncount}', f'vhba{ncount + 1}'],
                    placement = dict(
                        pci_order = placement_order,
                        slot_ids  = slots
                    ),
                    wwpn_allocation_type = 'POOL',
                    wwpn_pools           = [f'wwpn-a', f'wwpn-b']
                ))
                if 'switch' in kwargs.domain.switch_mode:
                    pvars['vhbas'][vcount].update({'fc_zone_policies': kwargs.fc_zone})
                else: pvars['vhbas'][vcount].pop('fc_zone_policies')
                ncount += 2
                vcount += 1
                if len(slots) == 1: pci_order += 2
                else: pci_order += 1
                
                # Add Policy Variables to imm_dict
                kwargs.class_path = f'policies,{self.type}'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
        
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Serial over LAN
    #=========================================================================
    def serial_over_lan(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(dict(description = f'SoL {self.descr} Policy', name = 'SoL'), kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Profiles - Server
    #=========================================================================
    def server(self, kwargs):
        #=====================================================================
        # Server Profile IP settings Function
        #=====================================================================
        def server_profile_networks(name, p, kwargs):
            #=================================================================
            # Send Error Message if IP Range isn't long enough
            #=================================================================
            def error_ip_range(i):
                pcolor.Red(f'!!! ERROR !!!\nNot Enough IPs in Range {i.server} for {name}')
                sys.exit(1)
            #=================================================================
            # Send Error Message if Server Range is missing
            #=================================================================
            def error_server_range(i):
                pcolor.Red(f'!!! ERROR !!!\nDid Not Find Server IP Range defined for {i.vlan_type}:{i.name}:{i.vlan_id}')
                sys.exit(1)
            #=================================================================
            # Dictionary of IP Settings for Server
            #=================================================================
            def ipdict(i, ipindex):
                idict = dict(
                    gateway  = i.gateway,
                    ip       = i.server[ipindex],
                    netmask  = i.netmask,
                    prefix   = i.prefix,
                    vlan     = i.vlan_id,
                    vlan_name= i.name,
                )
                return idict
            #=================================================================
            # Obtain the Index of the Starting IP Address
            #=================================================================
            ipindex = kwargs.inband.server.index(p.inband_start)
            if 'compute.Blade' in kwargs.server_profiles[name].object_type:
                ipindex = ipindex + int(kwargs.server_profiles[name].slot) - 1
            #=================================================================
            # Loop thru the VLANs
            #=================================================================
            for i in kwargs.vlans:
                if re.search('(inband|iscsi|migration|nfs|nvme|storage|tenant)', i.vlan_type):
                    if not i.server: error_server_range(i)
                    if not len(i.server) >= ipindex: error_ip_range(i)
                if re.search('(iscsi|nvme|storage)', i.vlan_type):
                    if not kwargs.server_profiles[name].get(i.vlan_type):
                        kwargs.server_profiles[name].update({i.vlan_type:[]})
                    idict = ipdict(i, ipindex)
                    kwargs.server_profiles[name][i.vlan_type].append(idict)
                if re.search('(inband|migration|nfs|tenant)', i.vlan_type):
                    idict = ipdict(i, ipindex)
                    kwargs.server_profiles[name][i.vlan_type] = idict
            return kwargs
        
        #=====================================================================
        # Build Server Profiles
        #=====================================================================
        templates = []
        for k, v in kwargs.servers.items(): templates.append(v.template)
        templates = list(numpy.unique(numpy.array(templates)))
        for template in templates:
            pvars = dict(
                action                       = 'Deploy',
                attach_template              = True,
                target_platform              = 'FIAttached',
                targets                      = [],
                ucs_server_profile_template  = str(template)
            )
            if len(kwargs.domain) > 0: idict = kwargs.domain
            else: idict = kwargs.imm; pvars['target_platform'] = 'Standalone'
            for k,v in kwargs.servers.items():
                if template == v.template:
                    if v.object_type == 'compute.Blade':
                        equipment_type= 'Chassis'
                        identifier    = v.chassis_id
                    else:
                        equipment_type= 'RackServer'
                        identifier    = v.server_id
                    match_profile = False
                    for p in idict.profiles:
                        if equipment_type == p.equipment_type and int(identifier) == int(p.identifier) and len(kwargs.domain) > 0:
                            os_vendor = p.os_vendor
                            if equipment_type == 'RackServer':
                                pstart = p.profile_start
                                match_profile = True
                            else:
                                suffix = int(p.suffix_digits)
                                pprefix= p.profile_start[:-(suffix)]
                                pstart = int(p.profile_start[-(suffix):])
                                match_profile = True
                            break
                        elif p.cimc == v.management_ip_address:
                            os_vendor = p.os_vendor
                            pstart  = p.profile_start
                            match_profile = True
                            break
                    if match_profile == False:
                        pcolor.Red('!!! ERROR !!!')
                        pcolor.Red(f'Did not Find Profile Definition for {k}')
                        pcolor.Red(f'Profiles:\n')
                        pcolor.Red(json.dumps(idict.profiles, indent=4))
                        pcolor.Red(f'Server Settings:\n')
                        pcolor.Red(json.dumps(v, indent=4))
                        pcolor.Red('!!! ERROR !!!\n Exiting...')
                        sys.exit(1)
                    if equipment_type == 'RackServer': name = pstart
                    else: name = f"{pprefix}{str(pstart+v.slot-1).zfill(suffix)}"
                    pvars['targets'].append(dict(
                        description  = f"{name} Server Profile.",
                        name         = name,
                        serial_number= k
                    ))
                    kwargs.server_profiles[name] = v
                    kwargs.server_profiles[name].boot_volume = kwargs.imm.policies.boot_volume
                    kwargs.server_profiles[name].os_vendor = os_vendor
                    #if not os_vendor == 'Windows':
                    kwargs = server_profile_networks(name, p, kwargs)
            pvars['targets']  = sorted(pvars['targets'], key=lambda ele: ele.name)
            kwargs.class_path= f'profiles,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        kwargs.server_profiles = dict(sorted(kwargs.server_profiles.items()))
        for k, v in kwargs.server_profiles.items():
            pvars = {}
            for a, b in v.items(): pvars[a] = b
            pvars = deepcopy(v)
            pvars.update(deepcopy({'name':k}))
            kwargs.class_path= f'wizard,server_profiles'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - SNMP
    #=========================================================================
    def snmp(self, kwargs):
        # Build Dictionary
        if len(kwargs.domain) > 0: idict = kwargs.domain.policies
        else: idict = kwargs.imm.policies
        pvars = dict(
            description           = 'snmp Policy',
            enable_snmp           = True,
            name                  = 'snmp',
            snmp_trap_destinations= [],
            snmp_users            = [dict(
                auth_password    = 1,
                auth_type        = 'SHA',
                name             = idict.snmp.username,
                privacy_password = 1,
                privacy_type     = 'AES',
                security_level   = 'AuthPriv'
            )],
            system_contact  = idict.snmp.contact,
            system_location = idict.snmp.location,
        )
        for i in idict.snmp.servers:
            pvars['snmp_trap_destinations'].append(dict(
                destination_address = i,
                port                = 162,
                user                = idict.snmp.username
            ))
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,snmp'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Storage
    #=========================================================================
    def ssh(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(dict(description = f'SSH {self.descr} Policy', name = 'SSH'), kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Storage
    #=========================================================================
    def storage(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description             = f'M2-raid {descr} Policy',
            name                    = 'M2-raid',
            m2_raid_configuration   = {'slot':'MSTOR-RAID-1'},
            use_jbod_for_vd_creation= True,
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Switch Control
    #=========================================================================
    def switch_control(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        switch_mode = kwargs.domain.switch_mode if kwargs.domain.switch_mode else 'end-host'
        pvars = dict(description = f'SwCtrl {self.descr} Policy', switching_mode_fc = switch_mode, name = 'SwCtrl', vlan_port_count_optimization = True)
        kwargs.class_path = f'policies,switch_control'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Syslog
    #=========================================================================
    def syslog(self, kwargs):
        # Build Dictionary
        if len(kwargs.domain) > 0: idict = kwargs.domain.policies
        else: idict = kwargs.imm.policies
        pvars = dict(
            description    = f'syslog Policy',
            local_logging  = dict( minimum_severity = 'warning' ),
            name           = 'syslog',
            remote_logging = []
        )
        for i in idict.syslog.servers:
            pvars['remote_logging'].append(dict(
                enable           = True,
                hostname         = i,
                minimum_severity = 'informational',
            ))
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,syslog'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - System QoS
    #=========================================================================
    def system_qos(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(
            configure_default_classes = True, configure_recommended_classes = True,
            description = f'qos {self.descr} Policy', jumbo_mtu = True, name = 'qos')
        if kwargs.domain.cfg_qos_priorities == True: pvars.pop('configure_default_classes')
        else: pvars.pop('configure_recommended_classes')
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Templates - Server
    #=========================================================================
    def templates(self, kwargs):
        #=====================================================================
        # Templates and Types
        #=====================================================================
        server_profiles = []
        for k, v in kwargs.servers.items(): server_profiles.append(v.template)
        server_profiles = list(numpy.unique(numpy.array(server_profiles)))
        for p in server_profiles:
            p = str(p)
            boot_type = re.search('-(iscsi|fcp|m2|raid)-', p).group(1)
            if 'vic' in p:
                bios_policy = p.split('-vic')[0] + '-virtual'
                bios_policy = bios_policy.replace('-tpm', '')
                if 'tpm' in p: bios_policy = bios_policy + '-tpm'
                if 'iscsi' in p: lcp = 'lcp-iscsi-vic-' + p.split('vic-')[1].replace('-', ':')
                else: lcp = 'lcp-vic-' + p.split('vic-')[1].replace('-', ':')
                scp = 'scp-vic-' + p.split('vic-')[1].replace('-', ':')
            else: lcp = 'none'; scp = 'none'; bios_policy = p
            bios_policy = re.sub('(fcp|iscsi|m2)-', '', bios_policy)
            bios_policy = re.sub('(blade|rack)-', '', bios_policy)
            pvars = dict(
                bios_policy             = bios_policy,
                boot_order_policy       = f'{boot_type}-boot',
                create_template         = True,
                description             = f'{p} Server Template',
                firmware_policy         = kwargs.firmware_policy_name,
                imc_access_policy       = f'KVM',
                lan_connectivity_policy = lcp,
                local_user_policy       = 'Users',
                name                    = p,
                power_policy            = 'Server',
                san_connectivity_policy = '',
                serial_over_lan_policy  = 'SoL',
                snmp_policy             = 'SNMP',
                syslog_policy           = 'Syslog',
                target_platform         = 'FIAttached',
                thermal_policy          = 'Server',
                uuid_pool               = 'UUID',
                virtual_kvm_policy      = 'vKVM',
                virtual_media_policy    = 'vMedia',
            )
            if 'rack' in p: pvars.pop('power_policy')
            if 'fcp' in p: pvars.update({'san_connectivity_policy': scp})
            else: pvars.pop('san_connectivity_policy')
            if len(kwargs.domain) == 0:
                pvars['target_platform'] = 'Standalone'
                for e in ['imc_access_policy', 'lan_connectivity_policy', 'uuid_pool']: pvars.pop(e)
                pvars = dict(pvars, **dict(network_connectivity_policy = 'DNS', ntp_policy = 'NTP', ssh_policy = 'SSH', storage_policy = 'M2-RAID'))
            pvars = dict(sorted(pvars.items()))
            # If using Shared Org update Policy Names
            if kwargs.use_shared_org == True and kwargs.org != 'default':
                org = kwargs.shared_org; pkeys = list(pvars.keys())
                for e in pkeys:
                    if re.search('policy|policies$', e): pvars[e] = f'{org}/{pvars[e]}'
            # Add Policy Variables to imm_dict
            kwargs.class_path = f'{self.type},server'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Thermal
    #=========================================================================
    def thermal(self, kwargs):
        #=====================================================================
        # Build Dictionaries and add to `imm_dict`, return kwargs
        #=====================================================================
        policies = kwargs.chassis + ['Server'] if len(kwargs.chassis) > 0 else ['Server']
        for i in policies:
            pvars = dict(fan_control_mode = 'Balanced', description = f'{i} {self.descr} Policy', name = i)
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Pools - MAC
    #=========================================================================
    def uuid(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(
            assignment_order = 'sequential', description = f'{self.descr} Pool', name = 'UUID', prefix = '000025B5-0000-0000',
            uuid_blocks = [{'from':f'{kwargs.domain.pools.prefix}00-000000000000', 'size':255}])
        kwargs.class_path = f'pools,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Virtual KVM
    #=========================================================================
    def virtual_kvm(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(allow_tunneled_vkvm = True, description = f'vKVM {self.descr} Policy', name = 'vKVM')
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - Virtual Media
    #=========================================================================
    def virtual_media(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(dict(description = f'vMedia {self.descr} Policy', name = 'vMedia'), kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - VLAN
    #=========================================================================
    def vlan(self, kwargs):
        #=====================================================================
        # Build Dictionary and add to `imm_dict`, return kwargs
        #=====================================================================
        pvars = dict(description = f'VLANs {self.descr} Policy', name = 'VLANs', vlans = [])
        for i in kwargs.vlans:
            if not int(i.vlan_id) == 1:
                pvars['vlans'].append(dict(multicast_policy = 'Mcast', name = i.name, vlan_list = str(i.vlan_id)))
        for i in kwargs.ranges:
            vfull = ezfunctions.vlan_list_full(i.vlan_list)
            if 1 in vfull: vfull.remove(1)
            vlan_list = ezfunctions.vlan_list_format(vfull)
            pvars['vlans'].append(dict(multicast_policy = 'Mcast', name = i.name, vlan_list = vlan_list))
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Policy - VSAN
    #=========================================================================
    def vsan(self, kwargs):
        #=====================================================================
        # Build Dictionaries and add to `imm_dict`, return kwargs
        #=====================================================================
        vsan_scope = 'Uplink' if kwargs.swmode == 'end-host' else 'Storage'
        for i in kwargs.domain.vsans:
            pvars = dict(
                description = f'VSAN-{i} {self.descr} Policy', name = f'VSAN-{i}',
                vsans = [dict(fcoe_vlan_id = i, name = f'VSAN-{i}', vsan_id = i, vsan_scope = vsan_scope)])
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Pools - WWNN/WWPN
    #=========================================================================
    def wwnn(self, kwargs):
        # Build Dictionary
        pfx = kwargs.domain.pools.prefix
        pvars = dict(
            assignment_order = 'sequential',
            description      = 'wwnn Pool',
            name             = 'wwnn',
            id_blocks        = [{ 'from':f'20:00:00:25:B5:{pfx}:00:00', 'size':255 }])
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'pools,wwnn'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Pools - WWNN/WWPN
    #=========================================================================
    def wwpn(self, kwargs):
        #=====================================================================
        # Build Dictionaries and add to `imm_dict`, return kwargs
        #=====================================================================
        flist = ['A', 'B']; pfx = kwargs.domain.pools.prefix
        for i in flist:
            pvars = dict(
                assignment_order = 'sequential', description = f'WWPN-{i} Pool', name = f'WWPN-{i}',
                id_blocks = [{ 'from':f'20:00:00:25:B5:{pfx}:{i}0:00', 'size':255 }])
            kwargs.class_path = f'pools,wwpn'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        return kwargs

#=============================================================================
# Wizard Class
#=============================================================================
class wizard(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function - Build Azure Stack Files for PowerShell Scripts
    #=========================================================================
    def azure_stack_prep(self, kwargs):
        #=====================================================================
        # Load Variables and Send Begin Notification
        #=====================================================================
        validating.begin_section(self.type, 'preparation')
        kwargs.org_moid = kwargs.org_moids[kwargs.org].moid
        kwargs.windows_timezones = json.load(open(os.path.join(kwargs.script_path, 'variables', 'windowsTimeZones.json'), 'r'))
        kwargs.windows_languages = json.load(open(os.path.join(kwargs.script_path, 'variables', 'windowsLocals.json'), 'r'))
        kwargs = ezfunctions.windows_languages(kwargs.imm_dict.wizard.windows_install, kwargs)
        kwargs = ezfunctions.windows_timezones(kwargs)
        #=====================================================================
        # Build the AzureStackHCI.xml Unnattend Answer File
        #=====================================================================
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, azs_file_name)): os.remove(os.path.join(cwd, azs_file_name))
        if not os.path.exists(os.path.join(cwd, 'AzureStack')): os.makedirs(os.path.join(cwd, 'AzureStack'))
        tloader  = jinja2.FileSystemLoader(searchpath = os.path.join(kwargs.script_path, 'examples', 'azure_stack_hci', '22H3'))
        tenviro  = jinja2.Environment(loader=tloader, autoescape=True)
        if kwargs.imm_dict.wizard.install_source == 'wds':
            for e in ['azure_stack_lcm_password', 'local_administrator_password', 'windows_domain_password']:
                kwargs.sensitive_var = e
                kwargs  = ezfunctions.sensitive_var_value(kwargs)
                kwargs[e]=kwargs.var_value
            install_server = kwargs.imm_dict.wizard.install_server.hostname
            ou             = kwargs.imm_dict.wizard.azure_stack[0].active_directory.azure_stack_ou
            org_unit       = f'OU=Computers,OU={ou},DC=' + kwargs.imm_dict.wizard.azure_stack[0].active_directory.domain.replace('.', ',DC=')
            jargs = dict(
                azure_stack_lcm_password     = kwargs.azure_stack_lcm_password,
                azure_stack_lcm_user         = kwargs.imm_dict.wizard.azure_stack[0].active_directory.azure_stack_lcm_user,
                azure_stack_ou               = org_unit,
                domain                       = kwargs.imm_dict.wizard.azure_stack[0].active_directory.domain,
                domain_administrator         = kwargs.imm_dict.wizard.azure_stack[0].active_directory.domain_administrator,
                domain_password              = kwargs.windows_domain_password,
                local_administrator_password = kwargs.local_administrator_password,
                organization                 = kwargs.imm_dict.wizard.azure_stack[0].organization,
                share_path                   = f'\\\\{install_server}\\{kwargs.imm_dict.wizard.install_server.reminst_share}',
                # Language
                input_locale       = kwargs.language.input_locale,
                languagePack       = kwargs.language.ui_language,
                layered_driver     = kwargs.language.layered_driver,
                secondary_language = kwargs.language.secondary_language,
                # Timezone
                disable_daylight_savings = kwargs.disable_daylight,
                timezone                 = kwargs.windows_timezone,
            )
            template  = tenviro.get_template('AzureStackHCI.xml')
            jtemplate = template.render(jargs)
            for x in ['layered_driver', 'secondary_language']:
                if f'{" "*12}<{x}></{x}>' in jtemplate: jtemplate = jtemplate.replace(f'{" "*12}<{x}></{x}>\n', '')
            file  = open(os.path.join(cwd, 'AzureStack', 'AzureStackHCI.xml'), 'w')
            file.write(jtemplate)
            file.close()
        #=====================================================================
        # Build the azs-answers.yaml and hostnames.json files
        #=====================================================================
        models = list(numpy.unique(numpy.array([e.model for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles])))
        for e in models:
            if re.search('UCSC.*M7', e): server_model = 'CxxxM7'; break
            elif re.search('UCSC.*M6', e): server_model = 'CxxxM6'; break
        template = tenviro.get_template('azs-template.jinja2')
        jargs = dict(
            active_directory = dict(
                azure_stack_lcm_user = kwargs.imm_dict.wizard.azure_stack[0].active_directory.azure_stack_lcm_user,
                azure_stack_ou       = kwargs.imm_dict.wizard.azure_stack[0].active_directory.azure_stack_ou,
                domain               = kwargs.imm_dict.wizard.azure_stack[0].active_directory.domain,
                domain_administrator = kwargs.imm_dict.wizard.azure_stack[0].active_directory.domain_administrator
            ),
            clusters             = [e.toDict() for e in kwargs.imm_dict.wizard.azure_stack[0].clusters],
            file_share_witness   = {},
            install_server       = kwargs.imm_dict.wizard.install_server.toDict(),
            operating_system     = 'W2K22',
            proxy                = {},
            server_model         = server_model
        )
        wkeys = list(kwargs.imm_dict.wizard.keys())
        for e in ['file_share_witness', 'install_server', 'proxy']:
            if e in wkeys: jargs[e] = kwargs.imm_dict.wizard[e].toDict()
            else: jargs.pop(e)
        jtemplate = template.render(jargs)
        file = open(os.path.join(cwd, 'AzureStack', 'azs-answers.yaml'), 'w')
        file.write(jtemplate)
        file.close()
        file = open(os.path.join(cwd, 'AzureStack', 'hostnames.json'), 'w')
        file.write(json.dumps({e.serial:e.name for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles}, indent=4))
        file.close()
        #=====================================================================
        # Add PowerShell scripts to the AzureStack directory and create zip
        #=====================================================================
        fpath = os.path.join(kwargs.script_path, 'examples', 'azure_stack_hci', '22H3')
        win_files = ['azs-hci-adprep.ps1', 'azs-hci-arcprep.ps1', 'azs-hci-hostprep.ps1', 'azs-hci-witness.ps1']
        for file in win_files: shutil.copyfile(os.path.join(fpath, file), os.path.join(cwd, 'AzureStack', file))
        azs_file_name = 'azure_stack_hci_files'
        shutil.make_archive(os.path.join(cwd, azs_file_name), 'zip', os.path.join(cwd, 'AzureStack'))
        azs_file_name = 'azure_stack_hci_files.zip'
        if kwargs.args.repository_check_skip == False:
            kwargs.sensitive_var = 'imm_transition_password'
            kwargs  = ezfunctions.sensitive_var_value(kwargs)
            kwargs['imm_transition_password']=kwargs.var_value
            #=================================================================
            # LOGIN TO IMM TRANSITION API
            #=================================================================
            s = requests.Session()
            data = json.dumps({'username':'admin','password':kwargs['imm_transition_password']})
            url = f'https://{kwargs.imm_dict.wizard.imm_transition}'
            try: r = s.post(data = data, headers= {'Content-Type': 'application/json'}, url = f'{url}/api/v1/login', verify = False)
            except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}\n'); sys.exit(1)
            if not r.status_code == 200: pcolor.Red(r.text); sys.exit(1)
            jdata = json.loads(r.text)
            token = jdata['token']
            #=================================================================
            # GET EXISTING FILES FROM THE SOFTWARE REPOSITORY
            #=================================================================
            try: r = s.get(url = f'{url}/api/v1/repo/files', headers={'x-access-token': token}, verify=False)
            except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
            if not r.ok: pcolor.Red(r.text); sys.exit(1)
            repository_files = (r.json())['repofiles']
            indx = next((index for (index, d) in enumerate(repository_files) if d['name'] == azs_file_name), None)
            if not indx == None:
                pcolor.Cyan(f'  * Deleting Existing Copy of `{azs_file_name}` on `{url}/api/v1/repo/files`')
                try: r = s.delete(url = f'{url}/api/v1/repo/files/{azs_file_name}', headers={'x-access-token': token}, verify=False)
                except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
                if not r.ok: pcolor.Red(r.text); sys.exit(1)
            #=================================================================
            # CREATE ZIP FILE IN THE SOFTWARE REPOSITORY
            #=================================================================
            file  = open(os.path.join(cwd, azs_file_name), 'rb')
            files = {'file': file}
            values = {'uuid':str(uuid.uuid4())}
            pcolor.Green(f'  * Uploading `{azs_file_name}` to `{url}/api/v1/repo/files`')
            try: r = s.post(
                url = f'{url}/api/v1/repo/actions/upload?use_chunks=false', headers={'x-access-token': token}, verify=False, data=values, files=files)
            except requests.exceptions.ConnectionError as e:
                pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
            if not r.ok: pcolor.Red(r.text); sys.exit(1)
            file.close()
            #=================================================================
            # LOGOUT OF THE API
            #=================================================================
            for uri in ['logout']:
                try: r = s.get(url = f'{url}/api/v1/{uri}', headers={'x-access-token': token}, verify=False)
                except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
                if 'repo' in uri: jdata = json.loads(r.text)
                if not r.status_code == 200: pcolor.Red(r.text); sys.exit(1)
        #=================================================================
        # REMOVE FOLDER and ZIP FILE - END SECTION
        #=================================================================
        try: shutil.rmtree('AzureStack')
        except OSError as e: print("Error: %s - %s." % (e.filename, e.strerror))
        if kwargs.args.repository_check_skip == False: os.remove(os.path.join(cwd, azs_file_name))
        validating.end_section(self.type, 'preparation')
        return kwargs

    #=========================================================================
    # Function - Build Intersight Managed Mode Domain Dictionaries
    #=========================================================================
    def build_imm_domain(self, kwargs):
        #=====================================================================
        # Configure Domain Policies
        #=====================================================================
        policy_list = []
        for k, v in kwargs.ezdata.items():
            if v.intersight_type == 'policies' and 'domain' in v.target_platforms: policy_list.append(k)
        for k, v in kwargs.imm.domain.items():
            dom_policy_list = deepcopy(policy_list)
            if not kwargs.imm.domain[k].get('vsans'): dom_policy_list.pop('vsan')
            for i in dom_policy_list:
                kwargs.domain = v; kwargs.domain.name = k
                kwargs = eval(f'imm(i).{i}(kwargs)')
        #=====================================================================
        # Configure Domain Profiles
        #=====================================================================
        kwargs = imm('domain').domain(kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        kwargs.policy_list = policy_list
        return kwargs

    #=========================================================================
    # Function - Build Intersight Managed Mode Server Dictionaries
    #=========================================================================
    def build_imm_servers(self, kwargs):
        pool_list = []; policy_list = []
        if not kwargs.args.deployment_type == 'azure_stack':
            #=================================================================
            # Configure IMM Pools
            #=================================================================
            for k, v in kwargs.ezdata.items():
                if v.intersight_type == 'pools' and not '.' in k: pool_list.append(k)
            pool_list.remove('resource')
            for k, v in kwargs.imm.domain.items():
                kwargs.domain = v; kwargs.domain.name = k
                for i in pool_list: kwargs = eval(f'isight.imm(i).pools(kwargs)')
        #==================================
        # Modify the Policy List
        #==================================
        if kwargs.args.deployment_type == 'azure_stack':
            for k, v in kwargs.ezdata.items():
                if v.intersight_type == 'policies' and 'Standalone' in v.target_platforms and not '.' in k:
                    policy_list.append(k)
            for i in kwargs.ezdata.converged_pop_list.properties.azure_stack.enum:
                if i in policy_list: policy_list.remove(i)
            kwargs = imm('compute_environment').compute_environment(kwargs)
            for i in policy_list: kwargs = eval(f'imm(i).{i}(kwargs)')
        else:
            for k, v in kwargs.ezdata.items():
                if v.intersight_type == 'policies' and (
                    'chassis' in v.target_platforms or 'FIAttached' in v.target_platforms) and not '.' in k:  policy_list.append(k)
            policy_list.remove('iscsi_static_target')
            policy_list.insert((policy_list.index('iscsi_boot')), 'iscsi_static_target')
            for i in kwargs.ezdata.converged_pop_list.properties.domain.enum: policy_list.remove(i)
            if kwargs.sw_mode == 'end-host': policy_list.remove('fc_zone')
            iscsi_type = False
            for i in kwargs.vlans:
                if i.vlan_type == 'iscsi': iscsi_type = True
            if iscsi_type == False:
                for i in kwargs.ezdata.converged_pop_list.properties.iscsi.enum: policy_list.remove(i)
            #=================================================================
            # Configure IMM Policies
            #=================================================================
            domain_pop_list = True
            for k, v in kwargs.imm.domain.items():
                kwargs.domain = v
                kwargs = imm('compute_environment').compute_environment(kwargs)
                if v.get('vsans'): domain_pop_list = False
            if domain_pop_list == True:
                for i in kwargs.ezdata.converged_pop_list.properties.fc.enum: policy_list.remove(i)
            kwargs.pci_order = 0
            for i in policy_list: kwargs = eval(f'imm(i).{i}(kwargs)')
        #=====================================================================
        # Configure Templates/Chassis/Server Profiles
        #=====================================================================
        kwargs.policy_list = policy_list
        profiles_list = ['templates', 'chassis', 'server']
        if kwargs.args.deployment_type == 'azure_stack': profiles_list.remove('chassis')
        for p in profiles_list: kwargs = eval(f'imm(p).{p}(kwargs)')
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - FlexPod Converged Stack - Build Storage Dictionaries
    #=========================================================================
    def build_netapp(self, kwargs):
        #=====================================================================
        # Build Dictionaries
        #=====================================================================
        for name,items in kwargs.netapp.cluster.items(): kwargs = netapp.build('cluster').cluster(items, name, kwargs)
        #==================================
        # Configure NetApp
        #==================================
        kwargs = netapp.api('cluster').cluster(kwargs)
        #==================================
        # Add Policy Variables to imm_dict
        #==================================
        idict = kwargs.storage.toDict()
        for k, v in idict.items():
            for a, b in v.items():
                kwargs.class_path = f'storage,appliances'
                kwargs = ezfunctions.ez_append(b, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - FlashStack Converged Stack - Build Storage Dictionaries
    #=========================================================================
    def build_pure_storage(self, kwargs):
        #=====================================================================
        # Build Pure Storage Dictionaries
        #=====================================================================
        for name,items in kwargs.pure_storage.items():
            kwargs = pure_storage.build('array').array(items, name, kwargs)
        #==================================
        # Configure Pure Storage
        #==================================
        kwargs = pure_storage.api('array').array(kwargs)
        #==================================
        # Add Policy Variables to imm_dict
        #==================================
        idict = kwargs.storage.toDict()
        for k, v in idict.items():
            for a, b in v.items():
                kwargs.class_path = f'storage,appliances'
                kwargs = ezfunctions.ez_append(b, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - DHCP - DNS - NTP Attributes
    #=========================================================================
    def dns_ntp(self, kwargs):
        i = kwargs.imm_dict.wizard.protocols
        kwargs.dhcp_servers = i.dhcp_servers
        kwargs.dns_servers  = i.dns_servers
        kwargs.dns_domains  = i.dns_domains
        kwargs.ntp_servers  = i.ntp_servers
        kwargs.timezone     = i.timezone
        return kwargs

    #=========================================================================
    # Function - Intersight Managed Mode Attributes
    #=========================================================================
    def imm(self, kwargs):
        kwargs.orgs = []
        for item in kwargs.imm_dict.wizard.intersight:
            item = DotMap(item)
            kwargs.orgs.append(item.organization)
            kwargs.org = item.organization
            if re.search('azure_stack|standalone', kwargs.args.deployment_type):
                kwargs.imm.cimc_default = item.cimc_default
                kwargs.imm.firmware     = item.firmware
                kwargs.imm.policies     = item.policies
                kwargs.imm.tags         = kwargs.ezdata.tags
                kwargs.imm.username     = item.policies.local_user
                if re.search('azure_stack', kwargs.args.deployment_type):
                    kwargs.imm.profiles = []
                    for item in kwargs.imm_dict.wizard.azure_stack:
                        icount = 0
                        for i in item.clusters:
                            for e in i.members:
                                kwargs.imm.profiles.append(DotMap(
                                    active_directory  = item.active_directory,
                                    cimc              = e.cimc,
                                    equipment_type    = 'RackServer',
                                    identifier        = 1,
                                    os_vendor           = 'Microsoft',
                                    profile_start     = e.hostname,
                                    suffix_digits     = 1,
                                    inband_start      = kwargs.inband.server[icount]))
                                icount += 1
                    kwargs.imm.policies.boot_volume = 'm2'
            else:
                kwargs.virtualization = item.virtualization
                for e in range(0,len(kwargs.virtualization)): kwargs.virtualization[e].syslog_server = item.policies.syslog.servers[0]
                if len(str(item.pools.prefix)) == 1: item.pools.prefix = f'0{item.pools.prefix}'
                for i in item.domains:
                    i = DotMap(i)
                    #=================================================================
                    # Get Moids for Fabric Switches
                    #=================================================================
                    kwargs.method     = 'get'
                    kwargs.uri        = 'network/Elements'
                    kwargs.names      = i.serial_numbers
                    kwargs            = isight.api('serial_number').calls(kwargs)
                    serial_moids      = kwargs.pmoids
                    serial            = i.serial_numbers[0]
                    serial_moids      = {k: v for k, v in sorted(serial_moids.items(), key=lambda ele: ele[1].switch_id)}
                    kwargs.api_filter = f"RegisteredDevice.Moid eq '{serial_moids[serial]['registered_device']}'"
                    kwargs.uri        = 'asset/Targets'
                    kwargs            = isight.api('asset_target').calls(kwargs)
                    names = list(kwargs.pmoids.keys())
                    i.name= names[0]
                    #=================================================================
                    # Build Domain Dictionary
                    #=================================================================
                    kwargs.imm.pool.prefix    = item.pools.prefix
                    kwargs.imm.policies       = item.policies
                    kwargs.imm.domain[i.name] = DotMap(
                        cfg_qos_priorities = item.cfg_qos_priorities,
                        device_model       = serial_moids[serial]['model'],
                        discovery_protocol = item.discovery_protocol,
                        eth_breakout_speed = i.eth_breakout_speed,
                        eth_uplinks        = i.eth_uplink_ports,
                        firmware           = item.firmware,
                        organization       = item.organization,
                        policies           = item.policies,
                        pools              = item.pools,
                        profiles           = i.profiles,
                        registered_device  = serial_moids[serial]['registered_device'],
                        serial_numbers     = list(serial_moids.keys()),
                        tags               = kwargs.ezdata.tags)
                    #=================================================================
                    # Build Domain Network Dictionary
                    #=================================================================
                    fabrics = ['A', 'B']
                    for x in range(0,2):
                        kwargs.network.imm[f'{i.name}-{fabrics[x]}'] = DotMap(
                            data_ports   = i.eth_uplink_ports,
                            data_speed   = i.eth_uplink_speed,
                            mgmt_port    = i.network.management,
                            network_port = i.network.data[x],
                            port_channel = True)
                    #=================================================================
                    # Confirm if Fibre-Channel is in Use
                    #=================================================================
                    fcp_count = 0
                    if i.get('fcp_uplink_ports') and len(i.fcp_uplink_ports) >= 2: fcp_count += 1
                    if i.get('fcp_uplink_speed'): fcp_count += 1
                    if i.get('switch_mode'): fcp_count += 1
                    if i.get('vsans') and len(i.vsans) >= 2: fcp_count += 1
                    if fcp_count == 4:
                        kwargs.imm.domain[i.name].fcp_uplink_ports= i.fcp_uplink_ports
                        kwargs.imm.domain[i.name].fcp_uplink_speed= i.fcp_uplink_speed
                        kwargs.imm.domain[i.name].switch_mode     = i.switch_mode
                        kwargs.imm.domain[i.name].vsans           = i.vsans
                    kwargs.imm.domain[i.name].virtualization = item.virtualization
                if len(kwargs.imm.domains) == 0: kwargs.imm.profiles = item.profiles
            if not kwargs.imm.policies.prefix == None and len(str(kwargs.imm.policies.prefix)) > 0:
                kwargs.imm_dict.orgs[kwargs.org].policies.name_prefix = DotMap(default = kwargs.imm.policies.prefix)
            else: kwargs.imm.policies.prefix = ''
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - FlexPod Converged Stack Attributes
    #=========================================================================
    def netapp(self, kwargs):
        #==================================
        # Build Cluster Dictionary
        #==================================
        kwargs.netapp.cluster = DotMap()
        kwargs.storage = DotMap()
        for item in kwargs.imm_dict.wizard.netapp:
            for i in item.clusters:
                protocols = []
                for e in i.svm.volumes: protocols.append(e.protocol)
                if 'local' in protocols: protocols.remove('local')
                if 'nvme-fc' in protocols or 'nvme-tcp' in protocols: protocols.append('nvme_of')
                protocols = list(numpy.unique(numpy.array(protocols)))
                kwargs.protocols = protocols
                kwargs.storage[i.name][i.svm.name] = DotMap(
                    cluster = i.name,
                    name    = f"{i.name}:{i.svm.name}",
                    svm     = i.svm.name,
                    vendor  = 'netapp')
                cname = i.name
                rootv = (i.svm.name).replace('-', '_').lower() + '_root'
                kwargs.netapp.cluster[cname] = DotMap(
                    autosupport = item.autosupport,
                    banner      = i.login_banner,
                    host_prompt = r'[\w]+::>',
                    nodes       = i.nodes,
                    protocols   = protocols,
                    snmp        = item.snmp,
                    svm         = DotMap(
                        agg1      = i.nodes.node01.replace('-', '_').lower() + '_1',
                        agg2      = i.nodes.node02.replace('-', '_').lower() + '_1',
                        banner    = i.svm.login_banner,
                        name      = i.svm.name,
                        m01       = rootv + '_m01',
                        m02       = rootv + '_m02',
                        protocols = protocols,
                        rootv     = rootv,
                        volumes   = i.svm.volumes),
                    username = item.username)
                kwargs.netapp.cluster[cname].nodes.node_list = [i.nodes.node01, i.nodes.node02]
                #=================================================================
                # Build Cluster Network Dictionary
                #=================================================================
                nodes = kwargs.netapp.cluster[cname].nodes.node_list
                for x in range(0,len(nodes)):
                    kwargs.network.storage[nodes[x]] = DotMap(
                        data_ports   = i.nodes.data_ports,
                        data_speed   = i.nodes.data_speed,
                        mgmt_port    = i.nodes.network.management,
                        network_port = i.nodes.network.data[x],
                        port_channel =True)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - FlexPod Converged Stack Attributes
    #=========================================================================
    def pure_storage(self, kwargs):
        #==================================
        # Build Cluster Dictionary
        #==================================
        kwargs.pure_storage = DotMap()
        kwargs.storage = DotMap()
        for i in kwargs.imm_dict.wizard.pure_storage:
            protocols = []
            for e in i.volumes: protocols.append(e.protocol)
            if 'local' in protocols: protocols.remove('local')
            if 'nvme-fcp' in protocols or 'nvme-roce' in protocols: protocols.append('nvme_of')
            protocols = list(numpy.unique(numpy.array(protocols)))
            kwargs.protocols = protocols
            kwargs.storage[i.name] = DotMap(
                name    = i.name,
                vendor  = 'pure_storage')
            kwargs.pure_storage[i.name] = DotMap(
                host_prompt= f'\\@[\\w-]+>',
                network    = i.network,
                system     = i.system,
                protocols  = protocols,
                volumes    = i.volumes,
                username   = i.username)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Converged Stack - VLAN Attributes
    #=========================================================================
    def vlans(self, kwargs):
        kwargs.vlans = []
        for i in kwargs.imm_dict.wizard.vlans:
            #=================================================================
            # Build VLAN Dictionary
            #=================================================================
            netwk = '%s' % ipaddress.IPv4Network(i.network, strict=False)
            vDict = DotMap(
                configure_l2 = i.configure_l2,
                configure_l3 = i.configure_l3,
                disjoint     = i.disjoint,
                gateway      = i.network.split('/')[0],
                name         = i.name,
                native_vlan  = i.native_vlan,
                netmask      = ((ipaddress.IPv4Network(netwk)).with_netmask).split('/')[1],
                network      = netwk,
                prefix       = i.network.split('/')[1],
                switch_type  = i.switch_type,
                vlan_id      = i.vlan_id,
                vlan_type    = i.vlan_type)
            def iprange(xrange):
                ipsplit = xrange.split('-')
                ip1 = ipsplit[0]
                ips = []
                a = ip1.split('.')
                for x in range(int(ip1.split('.')[-1]), int(ipsplit[1])+1):
                    ipaddress = f'{a[0]}.{a[1]}.{a[2]}.{x}'
                    ips.append(ipaddress)
                return ips
            if i.ranges.get('controller'): vDict.controller = iprange(i.ranges.controller)
            if i.ranges.get('pool') and re.search('(inband|ooband)', i.vlan_type): vDict.pool = iprange(i.ranges.pool)
            if i.ranges.get('server'): vDict.server = iprange(i.ranges.server)
            kwargs.vlans.append(vDict)
        #==================================
        # Build VLAN Ranges Dictionary
        #==================================
        kwargs.ranges = []
        for i in kwargs.imm_dict.wizard.vlan_ranges:
            kwargs.ranges.append(DotMap(
                configure_l2= i.configure_l2,
                disjoint    = i.disjoint,
                name        = i.name_prefix,
                vlan_list   = i.vlan_range))
        #==================================
        # Build inband|nfs|ooband Dict
        #==================================
        for i in kwargs.vlans:
            if re.search('(inband|nfs|ooband|migration)', i.vlan_type): kwargs[i.vlan_type] = i
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs
