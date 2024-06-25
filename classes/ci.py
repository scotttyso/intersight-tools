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
        self.type = type

    #=========================================================================
    # Function - Build Policies - BIOS
    #=========================================================================
    def bios(self, kwargs):
        # Build Dictionary
        descr     = (self.type.replace('_', ' ')).upper()
        btemplates= []
        dataset   = []
        for k, v in kwargs.servers.items():
            dataset.append(f"{v.gen}-{v.cpu}-{v.tpm}")
        models = list(numpy.unique(numpy.array(dataset)))
        for i in models:
            gen, cpu, tpm = i.split('-')
            if kwargs.args.deployment_type == 'azure_stack':
                if len(tpm) > 0: btemplates.append(f'{gen}-{cpu}-azure-tpm')
                else: btemplates.append(f'{gen}-{cpu}-azure')
            else:
                if len(tpm) > 0: btemplates.append(f'{gen}-{cpu}-virtual-tpm')
                else: btemplates.append(f'{gen}-{cpu}-virtual')
        btemplates = list(numpy.unique(numpy.array(btemplates)))
        for i in btemplates:
            pvars = dict(
                baud_rate           = '115200',
                bios_template       = str(i),
                console_redirection = f'com-0',
                description         = f'{i} {descr} Policy',
                name                = i,
                serial_port_aenable = f'enabled',
                terminal_type       = f'vt100',
            )
            # Add Policy Variables to imm_dict
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
        # Build Dictionary
        if kwargs.imm.policies.boot_volume == 'iscsi': boot_type = 'iscsi'
        elif kwargs.imm.policies.boot_volume == 'm2':  boot_type = 'm2'
        elif kwargs.imm.policies.boot_volume == 'san': boot_type = 'fcp'
        vics = []
        for k,v in kwargs.servers.items():
            if len(v.vics) > 0: vics.append(f'{v.vics[0].vic_gen}:{v.vics[0].vic_slot}')
        vics = list(numpy.unique(numpy.array(vics)))
        for vic in vics:
            pvars = {
                'boot_devices': [{
                    'device_name': 'kvm',
                    'device_type': 'virtual_media',
                    'enabled': True,
                    'subtype': 'kvm-mapped-dvd'
                }],
                'boot_mode': 'Uefi',
                'description': f'{boot_type} Boot Policy',
                'enable_secure_boot': True,
                'name': f'{boot_type}-{vic.split(":")[1]}-boot',
            }
            if 'fcp' in boot_type and kwargs.deployment_type == 'flexpod':
                fabrics = ['a', 'b']
                for x in range(0,len(fabrics)):
                    for k,v in kwargs.imm_dict.orgs[kwargs.org].storage.items():
                        for e in v:
                            for s in e['wwpns'][chr(ord('@')+x+1).lower()]:
                                pvars['boot_devices'].append({
                                    'device_name':  e.svm + '-' + s.interface,
                                    'device_type': 'san_boot',
                                    'enabled': True,
                                    'interface_name': f'vhba{x+1}',
                                    'slot': vic.split(":")[1],
                                    'wwpn': s.wwpn
                                })
            elif 'iscsi' in boot_type:
                fabrics = ['a', 'b']
                for fab in fabrics:
                        pvars['boot_devices'].append({
                            'device_name': f'storage-{fab}',
                            'device_type': 'iscsi_boot',
                            'enabled': True,
                            'interface_name': f'storage-{fab}',
                            'slot': vic.split(":")[1]
                        })
            elif 'm2' in boot_type:
                pvars['boot_devices'].extend([{
                    'device_name': f'm2',
                    'device_type': 'local_disk',
                    'enabled': True,
                    'slot':'MSTOR-RAID'
                },{
                    'device_name': f'network_pxe',
                    'device_type': 'pxe_boot',
                    'enabled': True,
                    'interface_name': '',
                    'interface_source': 'name',
                    'port': 1,
                    'slot': vic.split(":")[1]
                }])
            if 'azure_stack' in kwargs.args.deployment_type:
                indx = next((index for (index, d) in enumerate(pvars['boot_devices']) if d['device_type'] == 'pxe_boot'), None)
                pvars['boot_devices'][indx]['interface_source'] = 'port'
                pvars['boot_devices'][indx].pop('interface_name')
            if 'gen' in vic:
                indx = next((index for (index, d) in enumerate(pvars['boot_devices']) if d['device_type'] == 'pxe_boot'), None)
                pvars['boot_devices'][indx].pop('port')
                if len(kwargs.virtualization) > 0 and len(kwargs.virtualization[0].virtual_switches) > 0:
                    if re.search('vswitch0', kwargs.virtualization[0].virtual_switches[0].name, re.IGNORECASE):
                        if len(kwargs.virtualization[0].virtual_switches[0].alternate_name) > 0:
                            name = kwargs.virtualization[0].virtual_switches[0].alternate_name
                        else: name = kwargs.virtualization[0].virtual_switches[0].name
                    else: name = kwargs.virtualization[0].virtual_switches[0].name
                    pvars['boot_devices'][indx]['interface_name'] = name
            pvars['boot_devices'].append({
                'enabled': True,
                'device_name': 'cimc',
                'device_type': 'virtual_media',
                'subtype': 'cimc-mapped-dvd'
            })
            pvars['boot_devices'].append({
                'enabled': True,
                'device_name': 'uefishell',
                'device_type': 'uefi_shell'
            })
            # Add Policy Variables to imm_dict
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
        # Build Dictionary
        for k, v in kwargs.chassis.items():
            pvars = dict(
                action = 'Deploy', imc_access_policy = 'kvm', power_policy = k, snmp_policy = 'snmp', thermal_policy = k, targets = [])
            for i in v:
                pvars['targets'].append(dict(
                    description   = f'{i.domain}-{i.identity} Chassis Profile',
                    name          = f'{i.domain}-{i.identity}',
                    serial_number = i.serial
                ))
            # If using Shared Org update Policy Names
            if kwargs.use_shared_org == True and kwargs.org != 'default':
                org = kwargs.shared_org; pkeys = list(pvars.keys())
                for e in pkeys:
                    if re.search('policy|policies$', e): pvars[e] = f'{org}/{pvars[e]}'
            # Add Policy Variables to imm_dict
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
        kwargs.servers  = DotMap([])
        #=====================================================================
        # Build Domain Dictionaries
        #=====================================================================
        kwargs.boot_volume = kwargs.imm.policies.boot_volume
        if len(kwargs.domain) > 0:
            #=================================================================
            # Domain Inventory
            #=================================================================
            kwargs.api_filter = f"PlatformType in ('UCSFI', 'UCSFIISM')"
            kwargs = isight.api('domains').domain_device_registrations(kwargs)
            kwargs.api_filter = f"SwitchType eq 'FabricInterconnect'"
            kwargs = isight.api('domains').domain_network_elements(kwargs)
            #=================================================================
            # Chassis Inventory
            #=================================================================
            kwargs = isight.api('chassis').chassis_equipment(kwargs)
            #=================================================================
            # Server Inventory
            #=================================================================
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
                for e in dlist: kwargs.servers[kwargs.server_ips[k]][e] = v[e]
                indx = next((index for (index, d) in enumerate(kwargs.imm.profiles) if d.cimc == k), None)
                kwargs.servers[kwargs.server_ips[k]].active_directory = kwargs.imm.profiles[indx].active_directory
                kwargs.servers[kwargs.server_ips[k]].azure_stack = kwargs.imm.profiles[indx].azure_stack
                #kwargs.servers[kwargs.server_ips[k]] = DotMap(sorted(kwargs.servers[kwargs.server_ips[k]].items()))
            #kwargs.servers = DotMap(sorted(kwargs.servers.items(), key=lambda ele: ele[1].name))
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Profiles - Domain
    #=========================================================================
    def domain(self, kwargs):
        # Build Dictionary
        pvars = dict(
            action                     = 'Deploy',
            description                = f'{kwargs.domain.name} Domain Profile',
            name                       = kwargs.domain.name,
            network_connectivity_policy= 'dns',
            ntp_policy                 = 'ntp',
            port_policies              = [f'{kwargs.domain.name}-A', f'{kwargs.domain.name}-B'],
            serial_numbers             = kwargs.domain.serial_numbers,
            snmp_policy                = 'snmp',
            switch_control_policy      = 'sw-ctrl',
            syslog_policy              = 'syslog',
            system_qos_policy          = 'qos',
            vlan_policies              = ['vlans'])
        if kwargs.domain.get('vsans'):
            pvars['vsan_policies'] = []
            for i in kwargs.domain.vsans: pvars['vsan_policies'].append(f'vsan-{i}')
        # If using Shared Org update Policy Names
        if kwargs.use_shared_org == True and kwargs.org != 'default':
            org = kwargs.shared_org; pkeys = list(pvars.keys())
            for e in pkeys:
                if re.search('policy|policies$', e):
                    if type(pvars[e]) == list:
                        temp = pvars[e]; pvars[e] = []
                        for d in temp: pvars[e].append(f'{org}/{d}')
                    else: pvars[e] = f'{org}/{pvars[e]}'
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'profiles,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Ethernet Adapter
    #=========================================================================
    def ethernet_adapter(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        plist = ['16RxQs-4G', '16RxQs-5G']
        for item in kwargs.virtualization:
            if item.type == 'vmware': plist.extend(['VMware', 'VMware-High-Trf'])
        for i in plist:
            pvars = dict(
                adapter_template = i,
                description      = f'{i} {descr} Policy',
                name             = i,
            )
            # Add Policy Variables to imm_dict
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        name = kwargs.domain.discovery_protocol
        if 'cdp' in name: cdpe = True
        else: cdpe = False
        if 'lldp' in name: lldpe = True
        else: lldpe = False
        pvars = dict(
            cdp_enable           = cdpe,
            description          = f'{name} {descr} Policy',
            name                 = name,
            lldp_enable_receive  = lldpe,
            lldp_enable_transmit = lldpe,
            mac_register_mode    = 'nativeVlanOnly',
            mac_security_forge   = 'allow',
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Ethernet Network Group
    #=========================================================================
    def ethernet_network_group(self, kwargs):
        kwargs.descr = (self.type.replace('_', ' ')).title()
        #=====================================================================
        # Assign Configuration to Policy
        #=====================================================================
        def create_eth_groups(kwargs):
            pvars = dict(
                allowed_vlans = kwargs.allowed,
                description   = f'{kwargs.name} {kwargs.descr} Policy',
                name          = kwargs.name,
                native_vlan   = kwargs.native,
            )
            # Add Policy Variables to imm_dict
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
            return kwargs
        #=====================================================================
        # Add All VLANs for Guest vSwitch
        #=====================================================================
        vlans = []
        for i in kwargs.vlans: vlans.append(i.vlan_id)
        for i in kwargs.ranges:
            vrange = ezfunctions.vlan_list_full(i.vlan_list); vlans.extend(vrange)
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
            disjoint_vlans = []
            disjoint_native= 1
            native         = 1
            for i in kwargs.vlans:
                if i.disjoint == True:
                    disjoint_vlans.append(i.vlan_id)
                    if i.native_vlan == True: disjoint_native = i.vlan_id
                elif i.native_vlan == True: native = i.vlan_id

            for i in kwargs.ranges:
                if i.disjoint == True: disjoint_vlans.extend(ezfunctions.vlan_list_full(i.vlan_list))
            disjoint_vlans = list(numpy.unique(numpy.array(disjoint_vlans)))
            disjoint_vlans.sort()
            uplink1 = vlans
            for i in disjoint_vlans: uplink1.remove(i)
            kwargs.uplink1= ezfunctions.vlan_list_format(uplink1)
            kwargs.uplink2= ezfunctions.vlan_list_format(disjoint_vlans)
            kwargs.name   = 'uplink1'
            kwargs.allowed= kwargs.uplink1
            kwargs.native = native
            kwargs = create_eth_groups(kwargs)
            kwargs.name   = 'uplink2'
            kwargs.allowed= kwargs.uplink2
            kwargs.native = disjoint_native
            kwargs = create_eth_groups(kwargs)

        #=====================================================================
        # Create Eth NetworkGroups for Virtual Switches
        #=====================================================================
        for item in kwargs.virtualization:
            for i in item.virtual_switches:
                if re.search('vswitch0', i.name, re.IGNORECASE):
                    kwargs.name = i.alternate_name
                else: kwargs.name = i.name
                kwargs.native= 1
                if 'guests' in i.data_types:
                    kwargs.name = 'all_vlans'
                    kwargs.allowed= kwargs.vlan.all_vlans
                    if 'management' in i.data_types:
                        kwargs.native= kwargs.inband.vlan_id
                        kwargs       = create_eth_groups(kwargs)
                    elif 'storage' in i.data_types:
                        if kwargs.iscsi == 2:
                            for x in range(0,2):
                                if re.search('[A-Z]', i.name): suffix = chr(ord('@')+x+1)
                                else: suffix = chr(ord('@')+x+1).lower()
                                kwargs.name  = f"{i.name}-{suffix}"
                                kwargs.native= kwargs.iscsi_vlans[x]
                                kwargs       = create_eth_groups(kwargs)
                        elif 'migration' in i.data_types:
                            kwargs.native= kwargs.migration.vlan_id
                            kwargs       = create_eth_groups(kwargs)
                        else: kwargs = create_eth_groups(kwargs)
                    elif 'migration' in i.data_types:
                            kwargs.native= kwargs.migration.vlan_id
                            kwargs       = create_eth_groups(kwargs)
                    else: kwargs = create_eth_groups(kwargs)
                elif 'management' in i.data_types:
                    kwargs.native= kwargs.inband.vlan_id
                    mvlans       = [kwargs.inband.vlan_id]
                    if 'migration' in i.data_types: mvlans.append(kwargs.migration.vlan_id)
                    if 'storage' in i.data_types:
                        for v in kwargs.vlans:
                            if re.search('(iscsi|nfs|nvme)', v.vlan_type): mvlans.append(v.vlan_id)
                    mvlans.sort()
                    kwargs.allowed= ezfunctions.vlan_list_format(mvlans)
                    kwargs        = create_eth_groups(kwargs)
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
                            else: suffix = chr(ord('@')+x+1).lower()
                            kwargs.native= kwargs.iscsi_vlans[x]
                            kwargs.name  = f"{i.name}-{suffix}"
                            svlans       = [kwargs.iscsi_vlans[x]]
                            for v in kwargs.vlans:
                                if re.search('(nfs|nvme)', v.vlan_type): svlans.append(v.vlan_id)
                            kwargs.allowed= ezfunctions.vlan_list_format(svlans)
                            kwargs        = create_eth_groups(kwargs)
                    else:
                        mvlans       = [kwargs.migration.vlan_id]
                        for v in kwargs.vlans:
                            if re.search('(iscsi|nfs|nvme)', v.vlan_type): mvlans.append(v.vlan_id)
                        mvlans.sort()
                        kwargs.allowed= ezfunctions.vlan_list_format(mvlans)
                        kwargs        = create_eth_groups(kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Ethernet QoS
    #=========================================================================
    def ethernet_qos(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        plist = ['Best Effort']
        if kwargs.domain.cfg_qos_priorities == True:
            plist = plist.extend(['Bronze', 'Gold', 'Platinum', 'Silver'])
        for i in plist:
            name = i.replace(' ', '-')
            pvars = dict(
                enable_trust_host_cos= False,
                burst        = 10240,
                description  = f'{name} {descr} Policy',
                name         = name,
                mtu          = 9000,
                priority     = i,
                rate_limit   = 0,
            )
            # Add Policy Variables to imm_dict
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
        descr = (self.type.replace('_', ' ')).title()
        fabrics = ['a', 'b']
        kwargs.fc_zone = []
        for x in range(0,len(fabrics)):
            if len(kwargs.domain.vsans) == 2: vsan = kwargs.domain.vsans[x]
            else: vsan = kwargs.domain.vsans[0]
            name = f'fabric-{fabrics[x]}-vsan-{vsan}'
            # Build Dictionary
            pvars = dict(
                description           = f'{name} {descr} Policy',
                fc_target_zoning_type = 'SIMT',
                name                  = name,
                targets               = [],
            )
            kwargs.storage = kwargs.imm_dict.orgs[kwargs.org].storage
            for k, v in kwargs.storage.items():
                for e in v:
                    for i in e.wwpns[fabrics[x]]:
                        pvars['targets'].append(dict(
                            name      = e.svm + '-' + i.interface,
                            switch_id = (fabrics[x]).upper(),
                            vsan_id   = vsan,
                            wwpn      = i.wwpn
                        ))
                    kwargs.fc_zone.append(pvars['name'])
            # Add Policy Variables to imm_dict
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        plist = ['VMware', 'FCNVMeInitiator']
        for i in plist:
            pvars = dict(
                adapter_template = i,
                description      = f'{i} {descr} Policy',
                name             = i,
            )
            # Add Policy Variables to imm_dict
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Fibre-Channel Network
    #=========================================================================
    def fibre_channel_network(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        for i in kwargs.domain.vsans:
            pvars = dict(
                description = f'vsan-{i} {descr} Policy',
                name        = f'vsan-{i}',
                vsan_id     = i,
            )
            # Add Policy Variables to imm_dict
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Fibre-Channel QoS
    #=========================================================================
    def fibre_channel_qos(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        plist = ['fc-qos']
        for i in plist:
            pvars = dict(
                max_data_field_size = 2112,
                burst               = 10240,
                description         = f'{i} {descr} Policy',
                name                = i,
                rate_limit          = 0,
            )
            # Add Policy Variables to imm_dict
            kwargs.class_path = f'policies,{self.type}'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policies - Firmware
    #=========================================================================
    def firmware(self, kwargs):
        # Build Dictionary
        descr   = (self.type.replace('_', ' ')).capitalize()
        dataset = []
        #fw_name = (fw.replace(')', '')).replace('(', '-')
        for k, v in kwargs.servers.items():
            m = re.search('(M[\\d]{1,2}[A-Z]?[A-Z]?)', v.model).group(1)
            g = re.search('(M[\\d]{1,2})', v.model).group(1)
            v.model = v.model.replace(m, g)
            dataset.append(v.model)
        models = list(numpy.unique(numpy.array(dataset)))
        if len(kwargs.domain) > 0: fw_name = kwargs.domain.name
        else: fw_name = 'fw'
        kwargs.firmware_policy_name = fw_name
        pvars = dict(
            description          = f'{fw_name} {descr} Policy',
            model_bundle_version = [],
            name                 = fw_name,
            target_platform      = 'FIAttached'
        )
        if len(kwargs.domain) > 0:
            stypes = ['blades', 'rackmount']
            for s in stypes: pvars['model_bundle_version'].append(
                dict(firmware_version= kwargs.domain.firmware[s], server_models = []))
            for i in models:
                if 'UCSC' in i: pvars['model_bundle_version'][1]['server_models'].append(i)
                else: pvars['model_bundle_version'][0]['server_models'].append(i)
        else:
            pvars['target_platform'] = 'Standalone'
            pvars['model_bundle_version'].append(dict(firmware_version= kwargs.imm.firmware, server_models = []))
            for i in models: pvars['model_bundle_version'][0]['server_models'].append(i)
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        pvars = dict(cco_password = 1, cco_user = 1)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policies - Firmware
    #=========================================================================
    def firmware_authenticate(self, kwargs):
        pvars = dict(cco_password = 1, cco_user = 1)
        # Add Policy for Firmware Authentication
        kwargs.class_path = f'policies,firmware_authenticate'
        kwargs.append_type = 'map'
        kwargs = ezfunctions.ez_append(pvars, kwargs)

        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Flow Control
    #=========================================================================
    def flow_control(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description = f'flow-ctrl {descr} Policy',
            name        = 'flow-ctrl',
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - IMC Access
    #=========================================================================
    def imc_access(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description         = f'kvm {descr} Policy',
            inband_ip_pool      = f'kvm-inband',
            inband_vlan_id      = kwargs.inband.vlan_id,
            out_of_band_ip_pool = 'kvm-ooband',
            name                = 'kvm',
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Pools - IP
    #=========================================================================
    def ip(self, kwargs):
        pdns = kwargs.dns_servers[0]
        sdns = ''
        if len(kwargs.dns_servers) >= 2: sdns = kwargs.dns_servers[1]
        # Build Dictionary
        for i in kwargs.vlans:
            if re.search('(inband|iscsi|ooband)', i.vlan_type):
                if not kwargs.pools.ip.get(i.vlan_type):
                    kwargs.pools.ip[i.vlan_type] = []
                if re.search('inband|ooband', i.vlan_type):
                    name = f'kvm-{i.vlan_type}'
                    pool_from = i.pool[0]
                    pool_to   = i.pool[-1]
                else:
                    name = f'iscsi-vlan{i.vlan_id}'
                    pool_from = i.server[0]
                    pool_to   = i.server[-1]
                kwargs['defaultGateway'] = i.gateway
                kwargs['subnetMask']     = i.netmask
                kwargs['ip_version']     = 'v4'
                kwargs['pool_from']      = pool_from
                kwargs['pool_to']        = pool_to
                validating.error_subnet_check(kwargs)
                size = int(ipaddress.IPv4Address(pool_to)) - int(ipaddress.IPv4Address(pool_from)) + 1
                pvars = dict(
                    assignment_order = 'sequential',
                    description      = f'{name} IP Pool',
                    name             = f'{name}',
                    ipv4_blocks      = [{
                        'from':pool_from,
                        'size':size
                    }],
                    ipv4_configuration = dict(
                        gateway       = i.gateway,
                        netmask       = i.netmask,
                        primary_dns   = pdns,
                        secondary_dns = sdns
                    ),
                )
                kwargs.pools.ip[i.vlan_type].append(pvars['name'])
                # Add Policy Variables to imm_dict
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
        # Build Dictionary
        pvars = dict(
            assignment_order = 'sequential',
            description      = f'iscsi IQN Pool',
            name             = 'iscsi',
            prefix           = f'iqn.1984-12.com.cisco',
            iqn_blocks       = [{
                'from': 0,
                'size': 255,
                'suffix': 'ucs-host'
            }],
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'pools,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - IPMI over LAN
    #=========================================================================
    def ipmi_over_lan(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description = f'ipmi {descr} Policy',
            name        = 'ipmi',
            privilege   = 'read-only'
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - iSCSI Adapter
    #=========================================================================
    def iscsi_adapter(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description            = f'iadapter {descr} Policy',
            dhcp_timeout           = 60,
            name                   = 'iadapter',
            lun_busy_retry_count   = 15,
            tcp_connection_timeout = 15,
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - iSCSI Boot
    #=========================================================================
    def iscsi_boot(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        fabrics = ['a', 'b']
        list_of_list = []
        for i in range(0, len(kwargs.iscsi.targets), 2): list_of_list.append(kwargs.iscsi.targets[i:i+2])
        #half = kwargs.iscsi.targets // 2
        kwargs.a.targets  = list_of_list[0]
        kwargs.b.targets  = list_of_list[1]
        kwargs.iscsi.boot = []
        for x in range(0,len(fabrics)):
            pool = kwargs.pools.ip.iscsi[x]
            pvars = dict(
                description             = f'{pool} {descr} Policy',
                initiator_ip_source     = 'Pool',
                initiator_ip_pool       = kwargs.pools.ip.iscsi[x], 
                iscsi_adapter_policy    = f'iadapter',
                name                    = pool,
                primary_target_policy   = kwargs[fabrics[x]].targets[0],
                secondary_target_policy = kwargs[fabrics[x]].targets[1],
                target_source_type      = f'Static',
            )
            kwargs.iscsi.boot.append(pvars['name'])
            # Add Policy Variables to imm_dict
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        kwargs.iscsi.targets = []
        for k, v in kwargs.imm_dict.orgs[kwargs.org].storage.items():
            for e in v:
                for i in e.iscsi.interfaces:
                    name = e.svm + ':' + i.interface
                    pvars = dict(
                        description = f'{name} {descr} Policy',
                        ip_address  = i.ip_address,
                        lun_id      = 0,
                        name        = f'{name}',
                        port        = 3260,
                        target_name = v[0].iscsi.iqn,
                    )
                    kwargs.iscsi.targets.append(name)
                    # Add Policy Variables to imm_dict
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
        descr= (self.type.replace('_', ' ')).title()
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description = f'link-agg {descr} Policy',
            name        = 'link-agg',
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Link Control
    #=========================================================================
    def link_control(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description = f'link-ctrl {descr} Policy',
            name        = 'link-ctrl',
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
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
            description = f'users {descr} Policy',
            name        = 'users',
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description = f'mcast {descr} Policy',
            name        = 'mcast',
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Network Connectivity
    #=========================================================================
    def network_connectivity(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        if len(kwargs.dhcp_servers) > 0 and kwargs.deployment_type == 'azure_stack':
            enable_dhcp = True; enable_dhcp_dns = True; enable_ipv6 = False; enable_ipv6_dhcp = False
            e = kwargs.servers[list(kwargs.servers.keys())[0]]
            if (e.get('enable_dhcp') is not None) and (e.enable_dhcp == 'no'): enable_dhcp = False
            if (e.get('enable_dhcp_dns') is not None) and (e.enable_dhcp_dns == 'no'): enable_dhcp_dns = False
            if (e.get('enable_ipv6') is not None) and (e.enable_ipv6 == 'yes'): enable_ipv6 = True
            if (e.get('enable_ipv6_dhcp') is not None) and (e.enable_ipv6_dhcp == 'yes'): enable_ipv6_dhcp = True
            pvars = dict(
                description              = f'dns {descr} Policy',
                dns_servers_v4           = kwargs.dns_servers,
                enable_dynamic_dns       = True,
                enable_ipv6              = False,
                name                     = 'dns',
                obtain_ipv4_dns_from_dhcp= True,
                obtain_ipv6_dns_from_dhcp= False,
            )
            pop_list = []
            if enable_dhcp == False: pop_list.extend(['enable_dynamic_dns', 'obtain_ipv4_dns_from_dhcp'])
            elif enable_dhcp_dns == False: pop_list.append('obtain_ipv4_dns_from_dhcp')
            elif enable_dhcp_dns == True: pop_list.append('dns_servers_v4')
            if enable_ipv6 == True:
                pvars['enable_ipv6'] = True
                if enable_ipv6_dhcp == True and enable_dhcp_dns == True: pvars['obtain_ipv6_dns_from_dhcp'] = True
            else: pop_list.extend(['enable_ipv6', 'obtain_ipv6_dns_from_dhcp'])
            for i in pop_list: pvars.pop(i)
        else:
            pvars = dict(description    = f'dns {descr} Policy',
                           dns_servers_v4 = kwargs.dns_servers,
                           name           = 'dns')
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,network_connectivity'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - NTP
    #=========================================================================
    def ntp(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description = f'ntp {descr} Policy',
            name        = 'ntp',
            ntp_servers = kwargs.ntp_servers,
            timezone    = kwargs.timezone,
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,ntp'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        power_list = []
        for i in kwargs.chassis: power_list.append(i)
        power_list.append('server')
        for i in power_list:
            pvars = dict(
                description      = f'{i} {descr} Policy',
                name             = i,
                power_allocation = 0,
                power_redundancy = 'Grid',
            )
            if i == 'server': pvars.update({'power_restore':'LastState'})
            if '9508' in i: pvars['power_allocation'] = 8400
            else: pvars.pop('power_allocation')

            # Add Policy Variables to imm_dict
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description = f'sol {descr} Policy',
            name        = 'sol',
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            description             = f'ssh {descr} Policy',
            name                    = 'ssh',
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        if kwargs.domain.switch_mode: switch_mode = kwargs.domain.switch_mode
        else: switch_mode = 'end-host'
        pvars = dict(
            description       = f'sw-ctrl {descr} Policy',
            switching_mode_fc = switch_mode,
            name              = 'sw-ctrl',
            vlan_port_count_optimization = True,
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,switch_control'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
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
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).title()
        pvars = dict(
            configure_default_classes = True,
            description = f'qos {descr} Policy',
            jumbo_mtu   = True,
            name        = 'qos')
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Templates - Server
    #=========================================================================
    def templates(self, kwargs):
        # Build Dictionary
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
                imc_access_policy       = f'kvm',
                lan_connectivity_policy = lcp,
                local_user_policy       = 'users',
                name                    = p,
                power_policy            = 'server',
                san_connectivity_policy = '',
                serial_over_lan_policy  = 'sol',
                snmp_policy             = 'snmp',
                syslog_policy           = 'syslog',
                target_platform         = 'FIAttached',
                thermal_policy          = 'server',
                uuid_pool               = 'uuid',
                virtual_kvm_policy      = 'vkvm',
                virtual_media_policy    = 'vmedia',
            )
            if 'rack' in p: pvars.pop('power_policy')
            if 'fcp' in p: pvars.update({'san_connectivity_policy': scp})
            else: pvars.pop('san_connectivity_policy')
            if len(kwargs.domain) == 0:
                pvars['target_platform'] = 'Standalone'
                pop_list = ['imc_access_policy', 'lan_connectivity_policy', 'uuid_pool']
                for e in pop_list: pvars.pop(e)
                pvars = dict(pvars, **dict(
                    network_connectivity_policy= 'dns',
                    ntp_policy                 = 'ntp',
                    ssh_policy                 = 'ssh',
                    storage_policy             = 'M2-raid'
                ))
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
        # Build Dictionary
        policies = []
        if len(kwargs.chassis) > 0: policies.extend(kwargs.chassis)
        policies.append('server')
        descr = (self.type.replace('_', ' ')).title()
        for i in policies:
            pvars = dict(
                fan_control_mode = 'Balanced',
                description      = f'{i} {descr} Policy',
                name             = i,
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
    def uuid(self, kwargs):
        # Build Dictionary
        pvars = dict(
            assignment_order = 'sequential',
            description      = f'uuid Pool',
            name             = 'uuid',
            prefix           = '000025B5-0000-0000',
            uuid_blocks      = [{
                'from':f'{kwargs.domain.pools.prefix}00-000000000000',
                'size':255
            }],
        )
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'pools,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Virtual KVM
    #=========================================================================
    def virtual_kvm(self, kwargs):
        # Build Dictionary
        pvars = dict(
            allow_tunneled_vkvm = True,
            description         = 'vkvm Virtual KVM Policy',
            name                = 'vkvm',
        )

        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - Virtual Media
    #=========================================================================
    def virtual_media(self, kwargs):
        descr = (self.type.replace('_', ' ')).title()
        # Build Dictionary
        pvars = dict(
            description = f'vmedia {descr} Policy',
            name        = 'vmedia',
        )

        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - VLAN
    #=========================================================================
    def vlan(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).upper()
        pvars = dict(
            description = f'vlans {descr} Policy',
            name        = 'vlans',
            vlans       = [dict(
                auto_allow_on_uplinks = True,
                multicast_policy      = 'mcast',
                name                  = 'default',
                native_vlan           = True,
                vlan_list             = str(1)
            )]
        )
        for i in kwargs.vlans:
            if not int(i.vlan_id) == 1:
                pvars['vlans'].append(dict(
                    multicast_policy = 'mcast',
                    name             = i['name'],
                    vlan_list        = str(i.vlan_id)
                ))
        for i in kwargs.ranges:
            vfull = ezfunctions.vlan_list_full(i.vlan_list)
            if 1 in vfull: vfull.remove(1)
            vlan_list = ezfunctions.vlan_list_format(vfull)
            pvars['vlans'].append(dict(
                multicast_policy = 'mcast',
                name             = i['name'],
                vlan_list        = vlan_list
            ))
        # Add Policy Variables to imm_dict
        kwargs.class_path = f'policies,{self.type}'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Policy - VSAN
    #=========================================================================
    def vsan(self, kwargs):
        # Build Dictionary
        descr = (self.type.replace('_', ' ')).upper()
        if kwargs.swmode == 'end-host': vsan_scope = 'Uplink'
        else: vsan_scope = 'Storage'
        for i in kwargs.domain.vsans:
            pvars = dict(
                description = f'vsan-{i} {descr} Policy',
                name        = f'vsan-{i}',
                vsans       = [dict(
                    fcoe_vlan_id = i,
                    name         = f'vsan-{i}',
                    vsan_id      = i,
                    vsan_scope   = vsan_scope
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
        # Build Dictionary
        # Loop through WWPN Pools
        flist = ['A', 'B']
        pfx = kwargs.domain.pools.prefix
        for i in flist:
            pvars = dict(
                assignment_order = 'sequential',
                description      = f'wwpn-{i.lower()} Pool',
                name             = f'wwpn-{i.lower()}',
                id_blocks        = [{ 'from':f'20:00:00:25:B5:{pfx}:{i}0:00', 'size':255 }])
            kwargs.class_path = f'pools,wwpn'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

#=============================================================================
# Wizard Class
#=============================================================================
class wizard(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function - Build Intersight Managed Mode Domain Dictionaries
    #=========================================================================
    def build_imm_domain(self, kwargs):
        #==================================
        # Configure Domain Policies
        #==================================
        policy_list = []
        for k, v in kwargs.ezdata.items():
            if v.intersight_type == 'policies' and 'domain' in v.target_platforms: policy_list.append(k)
        for k, v in kwargs.imm.domain.items():
            dom_policy_list = deepcopy(policy_list)
            if not kwargs.imm.domain[k].get('vsans'): dom_policy_list.pop('vsan')
            for i in dom_policy_list:
                kwargs.domain = v; kwargs.domain.name = k
                kwargs = eval(f'imm(i).{i}(kwargs)')
        #==================================
        # Configure Domain Profiles
        #==================================
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
            #==================================
            # Configure IMM Pools
            #==================================
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
            pop_list = kwargs.ezdata.converged_pop_list.properties.azure_stack.enum
            print(pop_list)
            exit()
            for i in pop_list:
                if i in policy_list: policy_list.remove(i)
            kwargs = imm('compute_environment').compute_environment(kwargs)
            for i in policy_list: kwargs = eval(f'imm(i).{i}(kwargs)')
        else:
            for k, v in kwargs.ezdata.items():
                if v.intersight_type == 'policies' and (
                    'chassis' in v.target_platforms or 'FIAttached' in v.target_platforms) and not '.' in k:  policy_list.append(k)
            policy_list.remove('iscsi_static_target')
            policy_list.insert((policy_list.index('iscsi_boot')), 'iscsi_static_target')
            pop_list = kwargs.ezdata.converged_pop_list.properties.domain.enum
            for i in pop_list: policy_list.remove(i)
            if kwargs.sw_mode == 'end-host': policy_list.remove('fc_zone')
            iscsi_type = False
            for i in kwargs.vlans:
                if i.vlan_type == 'iscsi': iscsi_type = True
            if iscsi_type == False:
                pop_list = kwargs.ezdata.converged_pop_list.properties.iscsi.enum
                for i in pop_list: policy_list.remove(i)
            #==================================
            # Configure IMM Policies
            #==================================
            domain_pop_list = True
            for k, v in kwargs.imm.domain.items():
                kwargs.domain = v
                kwargs = imm('compute_environment').compute_environment(kwargs)
                if v.get('vsans'): domain_pop_list = False
            if domain_pop_list == True:
                pop_list = kwargs.ezdata.converged_pop_list.properties.fc.enum
                for i in pop_list: policy_list.remove(i)
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
            kwargs.org            = item.organization
            if re.search('azure_stack|standalone', kwargs.args.deployment_type):
                kwargs.imm.cimc_default  = item.cimc_default
                kwargs.imm.firmware      = item.firmware
                kwargs.imm.policies      = item.policies
                kwargs.imm.tags          = kwargs.ezdata.tags
                kwargs.imm.username      = item.policies.local_user
                if re.search('azure_stack', kwargs.args.deployment_type):
                    kwargs.imm.profiles = []
                    for item in kwargs.imm_dict.wizard.azure_stack:
                        icount = 0
                        for i in item.clusters:
                            for e in i.members:
                                kwargs.imm.profiles.append(DotMap(
                                    active_directory  = item.active_directory,
                                    azure_stack_admin = item.azure_stack_admin,
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
                    #==================================
                    # Get Moids for Fabric Switches
                    #==================================
                    kwargs.method    = 'get'
                    kwargs.uri       = 'network/Elements'
                    kwargs.names     = i.serial_numbers
                    kwargs           = isight.api('serial_number').calls(kwargs)
                    serial_moids     = kwargs.pmoids
                    serial           = i.serial_numbers[0]
                    serial_moids     = {k: v for k, v in sorted(serial_moids.items(), key=lambda ele: ele[1].switch_id)}
                    kwargs.api_filter= f"RegisteredDevice.Moid eq '{serial_moids[serial]['registered_device']}'"
                    kwargs.uri       = 'asset/Targets'
                    kwargs           = isight.api('asset_target').calls(kwargs)
                    names = list(kwargs.pmoids.keys())
                    i.name= names[0]
                    #==================================
                    # Build Domain Dictionary
                    #==================================
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
                    #==================================
                    # Build Domain Network Dictionary
                    #==================================
                    fabrics = ['A', 'B']
                    for x in range(0,2):
                        kwargs.network.imm[f'{i.name}-{fabrics[x]}'] = DotMap(
                            data_ports  = i.eth_uplink_ports,
                            data_speed  = i.eth_uplink_speed,
                            mgmt_port   = i.network.management,
                            network_port= i.network.data[x],
                            port_channel=True)
                    #=================================================================
                    # Confirm if Fibre-Channel is in Use
                    #=================================================================
                    fcp_count = 0
                    if i.get('fcp_uplink_ports'):
                        if len(i.fcp_uplink_ports) >= 2: fcp_count += 1
                    if i.get('fcp_uplink_speed'): fcp_count += 1
                    if i.get('switch_mode'): fcp_count += 1
                    if i.get('vsans'):
                        if len(i.vsans) >= 2: fcp_count += 1
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
                #==================================
                # Build Cluster Network Dictionary
                #==================================
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
    # Function - Build Policies - BIOS
    #=========================================================================
    def os_install(self, kwargs):
        #=====================================================================
        # Load Variables and Send Begin Notification
        #=====================================================================
        validating.begin_section(self.type, 'Install')
        kwargs.org_moid= kwargs.org_moids[kwargs.org].moid
        kwargs.models  = []
        os_install_fail_count = 0
        for k in list(kwargs.server_profiles.keys()): kwargs.models.append(kwargs.server_profiles[k].model)
        kwargs.models   = list(numpy.unique(numpy.array(kwargs.models)))
        #==========================================
        # Get Physical Server Tags to Check for
        # Existing OS Install
        #==========================================
        os_install= False
        kwargs.method   = 'get'
        kwargs.names    = [kwargs.server_profiles[k].serial for k in list(kwargs.server_profiles.keys())]
        kwargs.uri      = 'compute/PhysicalSummaries'
        kwargs          = isight.api('serial_number').calls(kwargs)
        server_profiles = deepcopy(kwargs.server_profiles)
        compute_moids   = kwargs.pmoids
        os_vendors = []
        for k in list(server_profiles.keys()):
            kwargs.server_profiles[k].hardware_moid = compute_moids[kwargs.server_profiles[k].serial].moid
            kwargs.server_profiles[k].os_installed  = False
            kwargs.server_profiles[k].tags          = compute_moids[kwargs.server_profiles[k].serial].tags
            os_vendors.append(v.os_vendor)
            for e in compute_moids[kwargs.server_profiles[k].serial].tags:
                if e.Key == 'os_installed' and e.Value == kwargs.server_profiles[k].os_vendor:
                    kwargs.server_profiles[k].os_installed = True
                else:  os_install = True
            if kwargs.server_profiles[k].boot_volume == 'm2':
                if not kwargs.server_profiles[k].storage_controllers.get('UCS-M2-HWRAID'):
                    pcolor.Red(f"!!! ERROR !!!\n  Could not determine the Controller Slot for:")
                    pcolor.Red(f"  * Profile: {kwargs.server_profiles[k].name}")
                    pcolor.Red(f"  * Serial:  {kwargs.server_profiles[k].serial}\n")
                    sys.exit(1)
        #=================================================================
        # Check for Sensitive Variables and 
        #=================================================================
        os_vendors = list(numpy.unique(numpy.array(os_vendors))); sensitive_list = []
        if 'Microsoft' in os_vendors:
            windows_language = DotMap(language_pack  = kwargs.imm_dict.wizard.windows_install.language_pack,
                                      layered_driver = kwargs.imm_dict.wizard.windows_install.layered_driver)
            kwargs = ezfunctions.windows_languages(windows_language, kwargs)
            kwargs = ezfunctions.windows_timezones(kwargs)
            sensitive_list.extend(['windows_admin_password', 'windows_domain_password'])
        if 'VMware' in os_vendors: sensitive_list.append('vmware_esxi_password')
        for e in sensitive_list:
            kwargs.sensitive_var = e
            kwargs = ezfunctions.sensitive_var_value(kwargs)
            kwargs[e] = kwargs.var_value
        #==========================================
        # Cfg Repositories if os_install is True
        #==========================================
        if os_install == True:
            #==================================
            # Get OS Config Files
            #==================================
            kwargs = isight.software_repository('os_cfg').os_configuration(kwargs)
            #==================================
            # Get SCU Repositories
            #==================================
            kwargs = isight.software_repository('scu').scu(kwargs)
            # Get User Input Software Configuration Utility
            kwargs.method     = 'get_by_moid'
            kwargs.pmoid      = kwargs.imm_dict.wizard.server_configuration_utility
            kwargs.uri        = 'firmware/ServerConfigurationUtilityDistributables'
            kwargs            = isight.api('server_configuration_utility').calls(kwargs)
            scu_source_link   = kwargs.results.Source.LocationLink
            # Get Organization Software Configuration Utility Repository that Matches User Input
            for e in kwargs.scu_moids:
                if e.Source.LocationLink == scu_source_link:
                    kwargs.scu_moid = e.Moid; url = e.Source.LocationLink; break
            ezfunctions.test_repository_url(url)
            repo_url = f"https://{url.split('/')[2]}/repo/"
            kwargs.imm_dict.orgs[kwargs.org].wizard.repository_server = repo_url
            #=======================================
            # Get Operating System Image Repositories
            #=======================================
            kwargs = isight.software_repository('scu').os_images(kwargs)
            kwargs.method     = 'get_by_moid'
            kwargs.pmoid      = kwargs.imm_dict.wizard.os_install_image
            kwargs.uri        = 'softwarerepository/OperatingSystemFiles'
            kwargs            = isight.api('operating_system').calls(kwargs)
            osi_source_link   = kwargs.results.Source.LocationLink
            for e in kwargs.osi_moids:
                if e.Source.LocationLink == osi_source_link:
                    kwargs.os_sw_moid = e.Moid; os_sw = e; break
            version = ''
            x = (os_sw.Version).split(' ')
            if v.os_vendor == 'Microsoft':
                version = f'{x[0]}{x[2]}'
                ctemplate = 'AzureStackHCIIntersight.xml'
                template_name = version + '-' + ctemplate.split('_')[0]
                kwargs.os_config_template = template_name
                if not kwargs.distributions.get(version):
                    kwargs.api_filter = f"Version eq '{e.Version}'"
                    kwargs.build_skip = True
                    kwargs.method     = 'get'
                    kwargs.uri        = 'hcl/OperatingSystems'
                    kwargs            = isight.api('hcl_operating_system').calls(kwargs)
                    kwargs.distributions[version] = DotMap(moid = kwargs.results[0].Moid)
                kwargs.distribution_moid = kwargs.distributions[version].moid
                file_content = (open(os.path.join(kwargs.script_path, 'examples', 'azure_stack_hci', '22H3', ctemplate), 'r')).read()
                for e in ['LayeredDriver:layeredDriver', 'UILanguageFallback:secondaryLanguage']:
                    elist = e.split(':')
                    rstring = '            <%s>{{ .%s }}</%s>\n' % (elist[0], elist[1], elist[0])
                    if kwargs.language[snakecase(elist[1])] == '': file_content = file_content.replace(rstring, '')
                kwargs.file_content = file_content
                kwargs.api_body     = ezfunctions.os_configuration_file(kwargs)
                kwargs.method       = 'post'
                kwargs.uri          = 'os/ConfigurationFiles'
                kwargs              = isight.api('os_configuration').calls(kwargs)
                kwargs.os_cfg_moids[template_name] = DotMap(moid = kwargs.pmoid)
                kwargs.os_cfg_moid = kwargs.os_cfg_moids[template_name].moid
            elif e.Vendor == v.os_vendor:
                template_name = f'{x[0]}{x[1]}ConfigFile'
                kwargs.os_cfg_moid = kwargs.os_cfg_moids[template_name].moid
            else:
                pcolor.Cyan(f'\n{"*" * 108}')
                pcolor.Red(f'Unsure which OS this is:\n  * Vendor: {e.Vendor}\n  * OS Type: {v.os_vendor}.\n\nExiting... (cy.py Line 2670)')
                pcolor.Cyan(f'\n{"*" * 108}')
                sys.exit(1)
        #==========================================
        # Install Operating System on Servers
        #==========================================
        count = 1
        for k,v in kwargs.server_profiles.items():
            if v.boot_volume == 'san':
                if count % 2 == 0: kwargs.wwpn = 0; kwargs.san_target = kwargs.imm_dict.orgs[kwargs.org].storage.appliances[0].wwpns.a[0].wwpn
                else: kwargs.wwpn = 1; kwargs.san_target = kwargs.imm_dict.orgs[kwargs.org].storage.appliances[0].wwpns.b[0].wwpn
            if v.os_installed == False:
                kwargs.mac_a = v.macs[0].mac
                kwargs.mac_b = v.macs[1].mac
                if v.os_vendor   == 'VMware':    kwargs.api_body = ezfunctions.installation_body_vmware(v, kwargs)
                elif v.os_vendor == 'Microsoft': kwargs.api_body = ezfunctions.installation_body_windows(v, kwargs)
                kwargs.method = 'post'
                kwargs.uri    = 'os/Installs'
                if v.boot_volume == 'san':
                    pcolor.Green(f"\n{'-'*108}\n\n{' '*6}* host {k}\n{' '*8}initiator: {v.wwpns[kwargs.wwpn].wwpn}"\
                                 f"\n{' '*8}target: {kwargs.san_target}\n{' '*8}mac: {kwargs.mac_a}")
                    pcolor.Green(f"\n{'-'*108}\n")
                else:
                    pcolor.Green(f"\n{'-'*108}\n\n{' '*6}* host {k}:\n{' '*8}target: {v.boot_volume}\n{' '*8}mac: {kwargs.mac_a}")
                    pcolor.Green(f"\n{'-'*108}\n")
                kwargs = isight.api(self.type).calls(kwargs)
                kwargs.server_profiles[k].os_install = DotMap(moid=kwargs.pmoid,workflow='')
        pcolor.Cyan(f'\n{"*" * 108}\n\nSleeping for 20 Minutes to pause for Workflow/Infos Lookup.')
        pcolor.Cyan(f'\n{"*" * 108}\n')
        time.sleep(1200)
        #=================================================
        # Monitor OS Installation until Complete
        #=================================================
        kwargs.names = []
        for k,v in kwargs.server_profiles.items():
            if v.os_installed == False:
                if len(v.os_install.moid) > 0: kwargs.names.append(v.os_install.moid)
        #from datetime import datetime
        #tdate = datetime.today().strftime('%Y-%m-%d')
        #kwargs.api_filter = f'CreateTime gt {tdate}T00:00:00.000Z and CreateTime lt {tdate}T23:59:00.000Z'
        kwargs.method = 'get'
        kwargs.uri    = 'os/Installs'
        kwargs = isight.api('workflow_os_install').calls(kwargs)
        install_workflows = kwargs.pmoids
        install_workflow_results = kwargs.results
        for k,v in kwargs.server_profiles.items():
            indx = next((index for (index, d) in enumerate(install_workflow_results) if d['Moid'] == v.os_install.moid), None)
            v.install_success = False
            if indx != None:
                v.os_install.workflow = install_workflow_results[indx].WorkflowInfo.Moid
                install_complete = False
                while install_complete == False:
                    kwargs.method = 'get_by_moid'
                    kwargs.pmoid  = v.os_install.workflow
                    kwargs.uri    = 'workflow/WorkflowInfos'
                    kwargs = isight.api('workflow_info').calls(kwargs)
                    if kwargs.results.WorkflowStatus == 'Completed':
                        install_complete = True; v.install_success  = True
                        pcolor.Green(f'    - Completed Operating System Installation for {k}.')
                    elif re.search('(Failed|Terminated)', kwargs.results.WorkflowStatus):
                        kwargs.upgrade.failed.update({k:v.moid})
                        pcolor.Red(f'!!! FAILED !!! Operating System Installation for Server Profile {k} failed.')
                        install_complete = True; os_install_fail_count += 1
                    else:
                        progress= kwargs.results.Progress
                        status  = kwargs.results.WorkflowStatus
                        pcolor.Cyan(f'      * Operating System Installation for {k}.')
                        pcolor.Cyan(f'        Status is {status} Progress is {progress}, Waiting 120 seconds.')
                        time.sleep(120)
                #=================================================
                # Add os_installed Tag to Physical Server
                #=================================================
                if v.install_success == True:
                    tags = deepcopy(v.tags)
                    tag_body = []
                    os_installed = False
                    for e in tags:
                        if e.Key == 'os_installed':
                            os_installed = True
                            tag_body.append({'Key':e.Key,'Value':v.os_vendor})
                        else: tag_body.append(e.toDict())
                    if os_installed == False:
                        tag_body.append({'Key':'os_installed','Value':v.os_vendor})
                    tags = list({v['Key']:v for v in tags}.values())
                    kwargs.api_body = {'Tags':tag_body}
                    kwargs.method   = 'patch'
                    kwargs.pmoid    = v.hardware_moid
                    kwargs.tag_server_profile = k
                    if v.object_type == 'compute.Blade': kwargs.uri = 'compute/Blades'
                    else: kwargs.uri = 'compute/RackUnits'
                    kwargs        = isight.api('update_tags').calls(kwargs)
            elif v.os_installed == False:
                os_install_fail_count += 1
                pcolor.Red(f'      * Something went wrong with the OS Install Request for {k}. Please Validate the Server.')
            else: pcolor.Cyan(f'      * Skipping Operating System Install for {k}.')
        #=====================================================================
        # Send End Notification and return kwargs
        #=====================================================================
        validating.end_section(self.type, 'Install')
        if os_install_fail_count > 0:
            pcolor.Yellow(kwargs.names)
            pcolor.Yellow(install_workflows)
            pcolor.Yellow(json.dumps(install_workflow_results, indent=4))
            for k,v in kwargs.server_profiles.items():
                if not v.install_success == True: pcolor.Red(f'      * OS Install Failed for `{k}`.  Please Validate the Logs.')
            sys.exit(1)
        return kwargs

    #=========================================================================
    # Function - Converged Stack - VLAN Attributes
    #=========================================================================
    def vlans(self, kwargs):
        kwargs.vlans = []
        for i in kwargs.imm_dict.wizard.vlans:
            #==================================
            # Build VLAN Dictionary
            #==================================
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

    #=========================================================================
    # Function - Build Policies - BIOS
    #=========================================================================
    def windows_prep(self, kwargs):
        #=====================================================================
        # Load Variables and Send Begin Notification
        #=====================================================================
        validating.begin_section(self.type, 'preparation')
        kwargs.org_moid = kwargs.org_moids[kwargs.org].moid
        kwargs.windows_languages = json.load(open(os.path.join(kwargs.script_path, 'variables', 'windowsTimeZones.json'), 'r'))
        kwargs.windows_languages = json.load(open(os.path.join(kwargs.script_path, 'variables', 'windowsLocals.json'), 'r'))
        kwargs = ezfunctions.windows_languages(kwargs.imm_dict.wizard.windows_install, kwargs)
        kwargs = ezfunctions.windows_timezones(kwargs)
        #=====================================================================
        # Get Physical Server Tags to Check for
        # Existing OS Install
        #=====================================================================
        kwargs.repo_server = kwargs.imm_dict.wizard.imm_transition
        for v in ['imm_transition_password', 'windows_admin_password', 'windows_domain_password']:
            kwargs.sensitive_var = v
            kwargs  = ezfunctions.sensitive_var_value(kwargs)
            kwargs[v]=kwargs.var_value
        tloader  = jinja2.FileSystemLoader(searchpath = os.path.join(kwargs.script_path, 'examples', 'azure_stack_hci', '22H3'))
        tenviro  = jinja2.Environment(loader=tloader, autoescape=True)
        if kwargs.imm_dict.wizard.install_source == 'wds':
            template = tenviro.get_template('AzureStackHCI.xml')
            ou       = kwargs.imm_dict.wizard.azure_stack[0].active_directory.azure_stack_ou
            org_unit = f'OU=Computers,OU={ou},DC=' + kwargs.imm_dict.wizard.azure_stack[0].active_directory.domain.replace('.', ',DC=')
            install_server = kwargs.imm_dict.wizard.install_server.hostname
            share_path     = kwargs.imm_dict.wizard.install_server.reminst_share
            jargs = dict(
                administratorPassword  = kwargs['windows_admin_password'],
                domain                 = kwargs.imm_dict.wizard.azure_stack[0].active_directory.domain,
                domainAdministrator    = kwargs.imm_dict.wizard.azure_stack[0].active_directory.administrator,
                domainPassword         = kwargs['windows_domain_password'],
                organization           = kwargs.imm_dict.wizard.azure_stack[0].organization,
                organizationalUnit     = org_unit,
                sharePath              = f'\\\\{install_server}\\{share_path}',
                # Language
                inputLocale           = kwargs.language.input_local,
                languagePack          = kwargs.language.ui_language,
                layeredDriver         = kwargs.language.layered_driver,
                secondaryLanguage     = kwargs.language.secondary_language,
                # Timezone
                disableAutoDaylightTimeSet = kwargs.disable_daylight,
                timeZone                   = kwargs.windows_timezone,
            )
            jtemplate = template.render(jargs)
            for x in ['LayeredDriver', 'UILanguageFallback']:
                if f'            <{x}></{x}>' in jtemplate: jtemplate = jtemplate.replace(f'            <{x}></{x}>\n', '')
            cwd = os.getcwd()
            new_dir = 'AzureStack'
            if not os.path.exists(os.path.join(cwd, new_dir)):
                os.makedirs(os.path.join(cwd, new_dir))
            file  = open(os.path.join(cwd, new_dir, 'AzureStackHCI.xml'), 'w')
            file.write(jtemplate)
            file.close()
        models = []
        for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            if e.get('model'): models.append(e.model)
        models = list(numpy.unique(numpy.array(models)))
        for e in models:
            if re.search('UCSC.*M7', e): server_model = 'CxxxM7'; break
            elif re.search('UCSC.*M6', e): server_model = 'CxxxM6'; break
        template = tenviro.get_template('azs-template.jinja2')
        jargs = dict(
            administrator        = kwargs.imm_dict.wizard.azure_stack[0].active_directory.azure_stack_admin,
            azure_stack_ou       = kwargs.imm_dict.wizard.azure_stack[0].active_directory.azure_stack_ou,
            azure_stack_prefix   = kwargs.imm_dict.wizard.azure_stack[0].active_directory.azure_stack_prefix,
            domain               = kwargs.imm_dict.wizard.azure_stack[0].active_directory.domain,
            domainAdministrator  = kwargs.imm_dict.wizard.azure_stack[0].active_directory.administrator,
            clusters             = kwargs.imm_dict.wizard.azure_stack[0].clusters,
            file_share_witness   = {},
            install_server       = kwargs.imm_dict.wizard.install_server.toDict(),
            operating_system     = 'W2K22',
            proxy                = {},
            server_model         = server_model
        )
        if kwargs.imm_dict.wizard.get('proxy'): jargs['proxy'] = kwargs.imm_dict.wizard.proxy.toDict()
        else: jargs.pop('proxy')
        if kwargs.imm_dict.wizard.get('file_share_witness'):
            jargs['file_share_witness'] = kwargs.imm_dict.wizard.file_share_witness
        else: jargs.pop('file_share_witness')
        jtemplate = template.render(jargs)
        file = open(os.path.join(cwd, new_dir, 'azs-answers.yaml'), 'w')
        file.write(jtemplate)
        file.close()
        hostnames = {}
        for k, v in kwargs.server_profiles.items():
            hostnames.update({v.serial:k})
        file = open(os.path.join(cwd, new_dir, 'hostnames.json'), 'w')
        file.write(json.dumps(hostnames, indent=4))
        file.close()
        fpath = os.path.join(kwargs.script_path, 'examples', 'azure_stack_hci', '22H3')
        win_files = ['azs-hci-adprep.ps1', 'azs-hci-drivers.ps1', 'azs-hci-hostprep.ps1', 'azs-hci-witness.ps1']
        for file in win_files:
            shutil.copyfile(os.path.join(fpath, file), os.path.join(cwd, new_dir, file))
        azs_file_name = 'azure_stack_hci_files'
        shutil.make_archive(os.path.join(cwd, azs_file_name), 'zip', os.path.join(cwd, new_dir))
        azs_file_name = 'azure_stack_hci_files.zip'
        #=====================================================================
        # LOGIN TO IMM TRANSITION API
        #=====================================================================
        s = requests.Session()
        data = json.dumps({'username':'admin','password':kwargs['imm_transition_password']})
        url = f'https://{kwargs.imm_dict.wizard.imm_transition}'
        try: r = s.post(data = data, headers= {'Content-Type': 'application/json'}, url = f'{url}/api/v1/login', verify = False)
        except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}\n'); sys.exit(1)
        if not r.status_code == 200: pcolor.Red(r.text); sys.exit(1)
        jdata = json.loads(r.text)
        token = jdata['token']
        #=====================================================================
        # GET EXISTING FILES FROM THE SOFTWARE REPOSITORY
        #=====================================================================
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
        #=====================================================================
        # CREATE ZIP FILE IN THE SOFTWARE REPOSITORY
        #=====================================================================
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
        #=====================================================================
        # LOGOUT OF THE API
        #=====================================================================
        for uri in ['logout']:
            try: r = s.get(url = f'{url}/api/v1/{uri}', headers={'x-access-token': token}, verify=False)
            except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
            if 'repo' in uri: jdata = json.loads(r.text)
            if not r.status_code == 200: pcolor.Red(r.text); sys.exit(1)
        #=====================================================================
        # REMOVE FOLDER and ZIP FILE
        #=====================================================================
        try: shutil.rmtree(new_dir)
        except OSError as e: print("Error: %s - %s." % (e.filename, e.strerror))
        os.remove(os.path.join(cwd, azs_file_name))
        #=====================================================================
        # END SECTION
        #=====================================================================
        validating.end_section(self.type, 'preparation')
        return kwargs
