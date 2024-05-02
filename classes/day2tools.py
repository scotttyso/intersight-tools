#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes  import ezfunctions, isight, pcolor, questions
    from classes  import isight
    from copy import deepcopy
    from datetime import datetime
    from dotmap   import DotMap
    from openpyxl.styles import Alignment, Border, Font, NamedStyle, PatternFill, Side
    import json, numpy, pytz, openpyxl, re, urllib3, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class tools(object):
    def __init__(self, type):
        self.type = type

    #=============================================================================
    # Function - Add Policies
    #=============================================================================
    def add_policies(self, kwargs):
        #=============================================================================
        # Prompt User for Source and Destination Organization
        #=============================================================================
        orgs = list(kwargs.org_moids.keys())
        kwargs.jdata             = kwargs.ezwizard.setup.properties.organization
        kwargs.jdata.description = 'Select the Source Organization for the pools/policies:'
        kwargs.jdata.enum        = orgs
        source_org               = ezfunctions.variable_prompt(kwargs)
        kwargs.jdata.description = 'Select the Organization for the Profiles:'
        destination_org          = ezfunctions.variable_prompt(kwargs)
        #=============================================================================
        # Prompt for Profile Type and obtain Pools/Policies
        #=============================================================================
        kwargs     = questions.profiles.profile_type(kwargs)
        kwargs     = questions.policies.build_policy_list(kwargs)
        pool_types = []
        if kwargs.target_platform == 'FIAttached':
            kwargs.jdata       = kwargs.ezwizard.setup.properties.server_type
            kwargs.server_type = ezfunctions.variable_prompt(kwargs)
            print(kwargs.pool_list)
            for e in ['ip', 'iqn', 'mac', 'wwnn', 'wwpn']:
                if e in kwargs.pool_list: kwargs.pool_list.remove(e)
            kwargs.jdata      = kwargs.ezwizard.setup.properties.pool_types
            kwargs.jdata.enum = kwargs.pool_list
            pool_types        = ezfunctions.variable_prompt(kwargs)
        for e in ['ethernet_adapter', 'ethernet_network_control', 'ethernet_network_group', 'ethernet_qos', 'fc_zone', 'fibre_channel_adapter',
                  'fibre_channel_network', 'fibre_channel_qos', 'firmware_authenticate', 'iscsi_adapter', 'iscsi_boot', 'iscsi_static_target']:
            if e in kwargs.policy_list: kwargs.policy_list.remove(e)
        kwargs.jdata      = kwargs.ezwizard.setup.properties.policy_types
        kwargs.jdata.enum = kwargs.policy_list
        policy_types      = ezfunctions.variable_prompt(kwargs)
        #=============================================================================
        # Prompt User for Policies to Attach
        #=============================================================================
        pool_types.extend(policy_types)
        update_types = pool_types
        kwargs.org   = source_org
        kwargs.policy_bucket = []
        kwargs.pools         = []
        accept_policies = False
        while accept_policies == False:
            policy_names = DotMap()
            for e in update_types:
                kwargs.api_filter      = f"Organization.Moid eq '{kwargs.org_moids[source_org].moid}'"
                kwargs.method          = 'get'
                kwargs.uri             = kwargs.ezdata[e].intersight_uri
                kwargs                 = isight.api(e).calls(kwargs)
                kwargs[f'{e}_results'] = kwargs.results
                for d in kwargs[f'{e}_results']: kwargs[e][d.Name] = d
                policies = sorted([d.Name for d in kwargs[f'{e}_results']])
                kwargs.jdata  = DotMap(
                    default     = '',
                    description = f'Select the {e} policy from source org: `{source_org}` to attach to {kwargs.target_platform}(s) in org: `{destination_org}`.',
                    enum        = policies, title = f'{e} Policy', type = 'string')
                if type(kwargs.server_type) == str:
                    kwargs.jdata.description = kwargs.jdata.description.replace(kwargs.target_platform, kwargs.server_type)
                if re.search('^resource|uuid$', e):
                    kwargs.jdata.description.replace('policy', 'pool')
                    kwargs.jdata.title.replace('Policy', 'Pool')
                policy_name = ezfunctions.variable_prompt(kwargs)
                policy_names[e] = policy_name
                indx = next((index for (index, d) in enumerate(kwargs[f'{e}_results']) if d['Name'] == policy_name), None)
                if re.search('^resource|uuid$', e):
                    kwargs.pools.append(DotMap(Moid=kwargs[f'{e}_results'][indx].Moid,ObjectType=kwargs[f'{e}_results'][indx].ObjectType))
                else: kwargs.policy_bucket.append(DotMap(Moid=kwargs[f'{e}_results'][indx].Moid,ObjectType=kwargs[f'{e}_results'][indx].ObjectType))
            answer = questions.prompt_user.to_accept('the `policy bucket update`', policy_names, kwargs)
            if answer == True: accept_policies = True
        #=============================================================================
        # Update the Profiles
        #=============================================================================
        kwargs.org = destination_org
        if len(kwargs.policy_bucket) > 0: kwargs = tools(kwargs.target_platform).profiles_update(kwargs)

    #=============================================================================
    # Function - Add Vlans
    #=============================================================================
    def add_vlans(self, kwargs):
        #=============================================================================
        # Function - Add Vlans
        #=============================================================================
        # Validate YAML configuration file is defined.
        if kwargs.args.yaml_file != None:
            ydata = DotMap(yaml.safe_load(open(kwargs.args.yaml_file, 'r'))).add_vlans
        else:
            prRed(f'\n{"-"*108}\n\n  Missing Required YAML File Argument `-y`.  Exiting Process.')
            prRed(f'\n{"-"*108}\n')
            len(False); sys.exit(1)
        #=============================================================================
        # Get VLAN List and Organizations from YAML configuration file.
        #=============================================================================
        tags  = [{'key': 'Module','value': 'day2tools'}]
        kwargs.organizations = ydata.organizations
        for org in kwargs.organizations:
            kwargs.org = org
            vpolicy    = ydata.vlan_policy.name
            vlans      = ydata.vlan_policy.vlans
            pcolor.Cyan(f'\n{"-"*108}\n\n  Starting Loop on Organization {org}.')
            pcolor.Cyan(f'\n{"-"*108}\n')
            #=============================================================================
            # Query the API for the VLAN Policies
            #=============================================================================
            kwargs = isight.api_get(False, [vpolicy], 'vlan', kwargs)
            vlan_moid = kwargs.pmoids[vpolicy].moid
            #=============================================================================
            # Query the API for the VLANs Attached to the VLAN Policy
            #=============================================================================
            pcolor.Cyan(f'\n{"-"*108}\n\n  Checking VLAN Policy `{vpolicy}` for VLANs.')
            pcolor.Cyan(f'\n{"-"*108}\n')
            kwargs.api_filter = f"EthNetworkPolicy.Moid eq '{vlan_moid}'"
            kwargs.method     = 'get'
            kwargs.uri        = kwargs.ezdata['vlan.vlans'].intersight_uri
            kwargs            = isight.api('vlan.vlans').calls(kwargs)
            mcast_moid        = kwargs.results[-1].MulticastPolicy.Moid
            policy_vlans      = sorted([e.VlanId for e in kwargs.results])
            add_vlans = []
            pcolor.Cyan(f'\n{"-"*108}\n')
            for e in vlans:
                if not e.vlan_id in policy_vlans: add_vlans.append(e)
                else:
                    pcolor.Cyan(f'  VLAN `{e.vlan_id}` is already in VLAN Policy: `{vpolicy}` in Organization: `{org}`.')
            kwargs.bulk_list = []
            for e in add_vlans:
                pcolor.Green(f'  VLAN `{e.vlan_id}` is not in VLAN Policy: `{vpolicy}` in Organization: `{org}`.  Adding VLAN...')
                api_body = {
                    'EthNetworkPolicy':{'Moid':vlan_moid,'ObjectType':'fabric.EthNetworkPolicy'},
                    'MulticastPolicy':{'Moid':mcast_moid,'ObjectType':'fabric.MulticastPolicy'},
                    'Name':e.name, 'ObjectType': 'fabric.Vlan', 'VlanId':e.vlan_id}
                kwargs.bulk_list.append(api_body)
            pcolor.Cyan(f'\n{"-"*108}\n')
            #=============================================================================
            # POST Bulk Request if Post List > 0
            #=============================================================================
            if len(kwargs.bulk_list) > 0:
                kwargs.uri = kwargs.ezdata['vlan.vlans'].intersight_uri
                kwargs     = isight.imm('vlan.vlans').bulk_request(kwargs)
            if len(ydata.ethernet_network_groups) > 0:
                #=============================================================================
                # Query the API for the Ethernet Network Group Policies
                #=============================================================================
                kwargs = isight.api_get(False, ydata.ethernet_network_groups, 'ethernet_network_group', kwargs)
                eng_results  = kwargs.results
                vlan_ids = [v.vlan_id for v in add_vlans]
                kwargs.bulk_list = []
                for e in ydata.ethernet_network_groups:
                    indx            = next((index for (index, d) in enumerate(eng_results) if d['Name'] == e), None)
                    allowed_vlans   = ezfunctions.vlan_list_full(eng_results[indx].VlanSettings.AllowedVlans)
                    vlan_check = True
                    for v in vlan_ids:
                        if not int(v) in allowed_vlans: vlan_check = False
                    if vlan_check == False:
                        allowed_vlans   = ezfunctions.vlan_list_format(list(numpy.unique(numpy.array(allowed_vlans + vlan_ids))))
                        api_body = {'Name': e,'VlanSettings': {'AllowedVlans': allowed_vlans},'pmoid': eng_results[indx].Moid}
                        kwargs.bulk_list.append(api_body)
                #=============================================================================
                # PATCH Bulk Request if Bulk List > 0
                #=============================================================================
                if len(kwargs.bulk_list) > 0:
                    kwargs.uri = kwargs.ezdata['ethernet_network_group'].intersight_uri
                    kwargs     = isight.imm(e).bulk_request(kwargs)
            #=============================================================================
            # Loop through Policy Creation
            #=============================================================================
            add_vlans = [e for e in ydata.vlan_policy.vlans]
            if len(ydata.lan_connectivity) > 0:
                idata = DotMap(ethernet_adapter  = [], ethernet_network_control = [], ethernet_network_group = [],
                               ethernet_qos = [], lan_connectivity = [], mac = [])
                for e in add_vlans:
                    idata.lan_connectivity.append(DotMap(
                        name = ydata.lan_connectivity.name.replace('{{vlan_id}}', str(e.vlan_id)), vlan_id = e.vlan_id))
                    for i in ydata.lan_connectivity.vnics:
                        idata.ethernet_adapter.append(i.ethernet_adapter)
                        idata.ethernet_network_control.append(i.ethernet_network_control)
                        idata.ethernet_network_group.append(DotMap(
                            name = i.ethernet_network_group.replace('{{vlan_id}}', str(e.vlan_id)), vlan_id = e.vlan_id))
                        idata.ethernet_qos.append(i.ethernet_qos)
                        idata.mac.append(i.mac_pool)
                for k, v in idata.items():
                    if re.search('ethernet_network_group|lan_connectivity', k):
                        idata[k]   = sorted(v, key=lambda ele: ele.vlan_id)
                    else: idata[k] = sorted(list(numpy.unique(numpy.array(v))))
                #=============================================================================
                # Query the API for the Ethernet Network Group Policies
                #=============================================================================
                kwargs   = isight.api_get(True, [e.name for e in idata.ethernet_network_group], 'ethernet_network_group', kwargs)
                eth_eng  = kwargs.pmoids
                eng_keys = list(eth_eng.keys())
                kwargs.bulk_list = []
                pcolor.Cyan(f'\n{"-"*108}\n')
                for e in idata.ethernet_network_group:
                    if e.name in eng_keys:
                        pcolor.Cyan(f'  Ethernet Network Group `{e.name}` Exists.  Moid is: {eth_eng[e.name].moid}')
                    else:
                        pcolor.Green(f'  Ethernet Network Group `{e.name}` does not exist.  Creating...')
                        api_body = {
                            'Description': f'{e.name} Ethernet Network Group', 'Name': e.name,
                            'ObjectType': 'fabric.EthNetworkGroupPolicy', 'Tags': tags,
                            'Organization': {'Moid':kwargs.org_moids[org].moid, 'ObjectType':'organization.Organization'},
                            'VlanSettings': {'AllowedVlans': f'{e.vlan_id}', 'NativeVlan': e.vlan_id, 'ObjectType': 'fabric.VlanSettings'}}
                        kwargs.bulk_list.append(api_body)
                pcolor.Cyan(f'\n{"-"*108}\n')
                #=============================================================================
                # POST Bulk Request if Bulk List > 0
                #=============================================================================
                if len(kwargs.bulk_list) > 0:
                    kwargs.uri = kwargs.ezdata['ethernet_network_group'].intersight_uri
                    kwargs     = isight.imm('ethernet_network_group').bulk_request(kwargs)
                #=============================================================================
                # Query the API for Policies
                #=============================================================================
                pdata = DotMap()
                ilist = ['ethernet_adapter', 'ethernet_network_control', 'ethernet_qos', 'mac']
                for e in ilist:
                    kwargs   = isight.api_get(True, idata[e], e, kwargs)
                    pdata[e] = kwargs.pmoids
                #=============================================================================
                # Query the API for the LAN Connectivity Policies
                #=============================================================================
                kwargs       = isight.api_get(True, [e.name for e in idata.lan_connectivity], 'lan_connectivity', kwargs)
                lan_policies = kwargs.pmoids
                #=============================================================================
                # Configure LAN Connectivity Policies
                #=============================================================================
                pcolor.Cyan(f'\n{"-"*108}\n')
                for e in idata.lan_connectivity:
                    if e.name in list(lan_policies.keys()):
                        pcolor.Cyan(f'  LAN Connectivity Policy `{e.name}` exists.  Moid is: {lan_policies[e.name].moid}')
                        lan_moid = lan_policies[e.name].moid
                    else:
                        pcolor.Cyan(f'  LAN Connectivity Policy `{e.name}` does not exist.  Creating...')
                        kwargs.api_body = {
                            'Name': str(e.name),
                            'ObjectType': 'vnic.LanConnectivityPolicy',
                            'Organization': {'Moid': kwargs.org_moids[org].moid, 'ObjectType': 'organization.Organization'},
                            'Tags': tags, 'TargetPlatform': ydata.lan_connectivity.target_platform}
                        kwargs.method = 'post'
                        kwargs.uri    = kwargs.ezdata.lan_connectivity.intersight_uri
                        kwargs        = isight.api(self.type).calls(kwargs)
                        lan_moid      = kwargs.pmoid
                        kwargs.isight[kwargs.org].policy.lan_connectivity[e.name] = lan_moid
                    #=============================================================================
                    # Configure vNIC Policies
                    #=============================================================================
                    kwargs.pmoid = lan_moid
                    kwargs = isight.api_get(True, [i.name for i in ydata.lan_connectivity.vnics], 'lan_connectivity.vnics', kwargs)
                    vnic_results = kwargs.pmoids
                    kwargs.bulk_list = []
                    for i in ydata.lan_connectivity.vnics:
                        if i.name in list(vnic_results.keys()):
                            pcolor.Cyan(f'  LAN Connectivity `{e.name}` vNIC `{i.name}` exists.  Moid is: {vnic_results[i.name].moid}')
                        else:
                            pcolor.Cyan(f'  vNIC `{i.name}` was not attached to LAN Policy `{e.name}`.  Creating...')
                            if len(ydata.lan_connectivity.vnics) > 1: failover = False
                            else: failover = True
                            eng = i.ethernet_network_group.replace('{{vlan_id}}', str(e.vlan_id))
                            api_body = {
                                'Cdn': {'ObjectType': 'vnic.Cdn', 'Source': 'vnic', 'Value': i.name },
                                'EthAdapterPolicy': {'Moid': pdata['ethernet_adapter'][i.ethernet_adapter].moid, 'ObjectType': 'vnic.EthAdapterPolicy'},
                                'EthQosPolicy': {'Moid': pdata['ethernet_qos'][i.ethernet_qos].moid, 'ObjectType': 'vnic.EthQosPolicy'},
                                'FabricEthNetworkControlPolicy': {
                                    'Moid': pdata['ethernet_network_control'][i.ethernet_network_control].moid,
                                    'ObjectType': 'fabric.EthNetworkControlPolicy'},
                                'FabricEthNetworkGroupPolicy': [{'Moid': eth_eng[eng].moid, 'ObjectType': 'fabric.EthNetworkGroupPolicy'}],
                                'FailoverEnabled': failover,
                                'LanConnectivityPolicy': {'Moid': lan_moid, 'ObjectType': 'vnic.LanConnectivityPolicy'},
                                'MacAddressType': 'POOL',
                                'MacPool': {'Moid': pdata['mac'][i.mac_pool].moid, 'ObjectType': 'macpool.Pool'},
                                'Name': i.name,
                                'ObjectType': 'vnic.EthIf',
                                'Order': i.placement.order,
                                'Placement': {'Id': i.placement.slot, 'ObjectType': 'vnic.PlacementSettings', 'PciLink': 0,
                                            'SwitchId': i.placement.switch_id, 'Uplink': 0}}
                            kwargs.bulk_list.append(api_body)
                    #=============================================================================
                    # POST Bulk Request if Bulk List > 0
                    #=============================================================================
                    kwargs.parent_key = 'lan_connectivity'
                    if len(kwargs.bulk_list) > 0:
                        kwargs.uri = kwargs.ezdata['lan_connectivity.vnics'].intersight_uri
                        kwargs     = isight.imm('lan_connectivity.vnics').bulk_request(kwargs)
                pcolor.Cyan(f'\n{"-"*108}\n')
        pcolor.Cyan(f'\n{"-"*108}\n\n  Finished Loop on Organization `{org}`.')
        pcolor.Cyan(f'\n{"-"*108}\n')
        
    #=============================================================================
    # Function - Add Policies
    #=============================================================================
    def clone_policies(self, kwargs):
        #=============================================================================
        # Prompt User for Source and Destination Organization
        #=============================================================================
        orgs = list(kwargs.org_moids.keys())
        kwargs.jdata             = kwargs.ezwizard.setup.properties.organization
        kwargs.jdata.description = 'Select the Source Organization to clone the pools/policies from:'
        kwargs.jdata.enum        = orgs
        source_org               = ezfunctions.variable_prompt(kwargs)
        kwargs.jdata.description = 'Select the Destination Organization to clone the policies to:'
        destination_org          = ezfunctions.variable_prompt(kwargs)
        #=============================================================================
        # Prompt for Profile Type and obtain Pools/Policies
        #=============================================================================
        kwargs = questions.profiles.profile_type(kwargs)
        kwargs = questions.policies.build_policy_list(kwargs)
        for e in ['imc_access', 'iscsi_boot', 'firmware_authenticate', 'lan_connectivity', 'ldap', 'local_user', 'port', 'san_connectivity', 'storage', 'vlan', 'vsan']:
            if e in kwargs.policy_list: kwargs.policy_list.remove(e)
        kwargs.jdata      = kwargs.ezwizard.setup.properties.policy_types
        kwargs.jdata.enum = kwargs.policy_list,
        policy_types      = ezfunctions.variable_prompt(kwargs)
        pool_types        = []
        if kwargs.target_platform == 'FIAttached':
            kwargs.jdata      = kwargs.ezwizard.setup.properties.pool_types
            kwargs.jdata.enum = kwargs.pool_list,
            pool_types        = ezfunctions.variable_prompt(kwargs)
        #=============================================================================
        # Prompt User for Policies to Clone
        #=============================================================================
        pool_types.extend(policy_types)
        clone_types = pool_types
        kwargs.org  = source_org
        for e in clone_types:
            kwargs.api_filter      = f"Organization.Moid eq '{kwargs.org_moids[source_org].moid}'"
            kwargs.method          = 'get'
            kwargs.uri             = kwargs.ezdata[e].intersight_uri
            kwargs                 = isight.api(e).calls(kwargs)
            kwargs[f'{e}_results'] = kwargs.results
            for d in kwargs[f'{e}_results']: kwargs[e][d.Name] = d
            policies = sorted([d.Name for d in kwargs[f'{e}_results']])
            kwargs.jdata  = DotMap(
                default       = '',
                description   = f'Select the `{e}` policies to clone from source org: `{source_org}` to destination org: `{destination_org}`.',
                multi_select  = True,
                enum          = policies, title = f'{e} Policies', type = 'string')
            if re.search('^ip|iqn|mac|resource|uuid|wwnn|wwpn$', e):
                kwargs.jdata.description.replace('policies', 'pools')
                kwargs.jdata.title.replace('Policies', 'Pools')
            clone_policies = ezfunctions.variable_prompt(kwargs)
            key_list = ['Description', 'Name', 'Tags']
            for k,v in kwargs.ezdata[e].allOf[1].properties.items():
                if v.type == 'array': key_list.append(v['items'].intersight_api)
                elif v.type == 'object': key_list.append(v.intersight_api)
                elif re.search('boolean|integer|string', v.type):
                    if re.search(r'\$ref\:', v.intersight_api): key_list.append(v.intersight_api.split(':')[1])
                    else: key_list.append(v.intersight_api)
                else: pcolor.Yellow(json.dumps(v, indent=4)); sys.exit(1)
            kwargs.bulk_list = []
            key_list = list(numpy.unique(numpy.array(key_list)))
            for d in clone_policies:
                api_body = kwargs[e][d]
                for key in list(api_body.keys()):
                    if not key in key_list: api_body.pop(key)
                api_body.ObjectType = kwargs.ezdata[e].ObjectType
                api_body.Organization.Moid = kwargs.org_moids[destination_org].moid
                api_body.Organization.ObjectType = 'organization.Organization'
                kwargs.bulk_list.append(api_body.toDict())
            #=============================================================================
            # POST Bulk Request if Post List > 0
            #=============================================================================
            if len(kwargs.bulk_list) > 0:
                kwargs.uri = kwargs.ezdata[e].intersight_uri
                kwargs     = isight.imm(e).bulk_request(kwargs)

    #=============================================================================
    # Function - HCL Inventory
    #=============================================================================
    def hcl_inventory(self, kwargs):
        kwargs.org = 'default'
        pdict = DotMap()
        # Obtain Server Profile Data
        for e in kwargs.json_data:
            if 'Cisco' in e.Hostname.Manufacturer:
                pdict[e.Serial]     = DotMap(
                    domain          = 'Standalone',
                    model           = e.Hostname.Model,
                    serial          = e.Serial,
                    server_dn       = 'unknown',
                    server_profile  = 'unassigned',
                    firmware        = 'unknown',
                    vcenter         = e.vCenter,
                    cluster         = e.Cluster,
                    hostname        = e.Hostname.Name,
                    version         = e.Hostname.Version,
                    build           = e.Hostname.Build,
                    hcl_check       = 'unknown',
                    hcl_status      = 'unknown',
                    hcl_reason      = 'unknown',
                    toolName        = e.Name,
                    toolDate        = e.InstallDate,
                    toolVer         = e.Version,
                    moid            = 'unknown'
                )
        kwargs.names  = list(pdict.keys())
        kwargs.method = 'get'
        kwargs.uri    = 'compute/PhysicalSummaries'
        kwargs        = isight.api('serial_number').calls(kwargs)
        registered_devices  = []
        for e in kwargs.results:
            pdict[e.Serial].firmware = e.Firmware
            if 'sys/' in e.Dn: pdict[e.Serial].server_dn = (e.Dn).replace('sys/', '')
            elif e.ServerId == 0: pdict[e.Serial].server_dn = f'chassis-{e.ChassisId}-slot-{e.SlotId}'
            else: pdict[e.Serial].server_dn = f'rack-unit-{e.ServerId}'
            pdict[e.Serial].moid = e.Moid
            if e.get('ServiceProfile'): pdict[e.Serial].server_profile = e.ServiceProfile
            if not e.ManagementMode == 'IntersightStandalone':
                pdict[e.Serial].registered_moid = e.RegisteredDevice.Moid
                registered_devices.append(e.RegisteredDevice.Moid)
        if len(registered_devices) > 0:
            domain_map    = DotMap()
            parents       = []
            kwargs.method = 'get'
            kwargs.names  = list(numpy.unique(numpy.array(registered_devices)))
            kwargs.uri    = 'asset/DeviceRegistrations'
            kwargs        = isight.api('registered_device').calls(kwargs)
            for e in kwargs.results:
                if e.get('ParentConnection'):
                    domain_map[e.Moid].hostname = None
                    domain_map[e.Moid].parent = e.ParentConnection.Moid
                    parents.append(e.ParentConnection.Moid)
                else:
                    domain_map[e.Moid].hostname = e.DeviceHostname
                    domain_map[e.Moid].parent = None
            if len(parents) > 0:
                kwargs.names = list(numpy.unique(numpy.array(parents)))
                kwargs.uri   = 'asset/DeviceRegistrations'
                kwargs       = isight.api('registered_device').calls(kwargs)
                for e in kwargs.results:
                    for k, v in domain_map.items():
                        if v.get('parent'):
                            if v.parent == e.Moid: domain_map[k].hostname = e.DeviceHostname
            for k, v in pdict.items():
                if v.get('registered_moid'): pdict[k].domain = domain_map[v.registered_moid].hostname[0]
        hw_moids = DotMap()
        for k,v in pdict.items(): hw_moids[v.moid].serial = k
        kwargs.names      = list(hw_moids.keys())
        kwargs.uri        = 'cond/HclStatuses'
        kwargs            = isight.api('hcl_status').calls(kwargs)
        hcl_results       = kwargs.results
        names             = "', '".join(kwargs.names).strip("', '")
        kwargs.api_filter = f"AssociatedServer.Moid in ('{names}')"
        kwargs.uri        = kwargs.ezdata.server.intersight_uri
        kwargs            = isight.api('hcl_status').calls(kwargs)
        profile_results   = kwargs.results
        for k,v in pdict.items():
            indx = next((index for (index, d) in enumerate(hcl_results) if d['ManagedObject']['Moid'] == v.moid), None)
            if not indx == None:
                pdict[k].hcl_check  = hcl_results[indx].SoftwareStatus
                pdict[k].hcl_status = hcl_results[indx].Status
                pdict[k].hcl_reason = hcl_results[indx].ServerReason
            indx = next((index for (index, d) in enumerate(profile_results) if d['AssociatedServer']['Moid'] == v.moid), None)
            if not indx == None: pdict[k].server_profile = profile_results[indx].Name

        if len(pdict) > 0:
            kwargs.timezone = questions.prompt_user.for_timezone(kwargs)
            kwargs = tools(self.type).setup_local_time(kwargs)
            # Build Named Style Sheets for Workbook
            kwargs = tools(self.type).workbook_styles(kwargs)
            workbook = f'HCL-Inventory-{kwargs.time_short}.xlsx'
            wb = kwargs.wb
            ws = wb.active
            ws.title = 'Inventory List'
            column_headers = [
                'Domain','Model','Serial','Server','Profile','Firmware','vCenter','Cluster','Hostname', 'ESX Version', 'ESX Build',
                'HCL Component Status', 'HCL Status', 'HCL Reason', 'UCS Tools Name', 'UCS Tools Install Date', 'UCS Tools Version']
            for i in range(len(column_headers)): ws.column_dimensions[chr(ord('@')+i+1)].width = 30
            cLength = len(column_headers)
            ws_header = f'Collected UCS Data on {kwargs.time_long}'
            data = [ws_header]
            ws.append(data)
            ws.merge_cells(f'A1:{chr(ord("@")+cLength)}1')
            for cell in ws['1:1']: cell.style = 'heading_1'
            ws.append(column_headers)
            for cell in ws['2:2']: cell.style = 'heading_2'
            ws_row_count = 3
            # Populate the Columns with Server Inventory
            for key, value in pdict.items():
                # Add the Columns to the Spreadsheet
                data = []
                for k,v in value.items():
                    if not re.search('moid|registered_moid', k): data.append(v)
                ws.append(data)
                for cell in ws[ws_row_count:ws_row_count]:
                    if ws_row_count % 2 == 0: cell.style = 'odd'
                    else: cell.style = 'even'
                ws_row_count += 1
            # Save the Workbook
            wb.save(filename=workbook)

    #=============================================================================
    # Function - Profiles Update
    #=============================================================================
    def profiles_deploy(self, kwargs):
        #=============================================================================
        # Get Physical Devices
        #=============================================================================
        kwargs.names = []
        for e in kwargs.profile_results:
            if   e.get('AssignedServer'):  kwargs.names.append(e.AssignedServer.Moid)
            elif e.get('AssignedChassis'): kwargs.names.append(e.AssignedChassis.Moid)
            elif e.get('AssignedSwitch'):  kwargs.names.append(e.AssignedSwitch.Moid)
        kwargs.method = 'get'
        kwargs.uri    = kwargs.ezdata[self.type].intersight_uri_serial
        kwargs        = isight.api('moid_filter').calls(kwargs)
        phys_devices  = kwargs.results
        profiles      = []
        #=============================================================================
        # Build Dictionary and Deploy Profiles
        #=============================================================================
        if re.search('chassis|server', self.type):
            for e in kwargs.profile_names:
                indx = next((index for (index, d) in enumerate(kwargs.profile_results) if d['Name'] == e), None)
                kwargs.isight[kwargs.org].profile[self.type][e] = kwargs.profile_results[indx].Moid
                if self.type == 'server': sname = 'AssignedServer'
                if self.type == 'chassis': sname = 'AssignedChassis'
                sindx = next((index for (index, d) in enumerate(phys_devices) if d['Moid'] == kwargs.profile_results[indx][sname].Moid), None)
                profiles.append(DotMap(action='Deploy',name=e,serial_number=phys_devices[sindx].Serial))
            if len(profiles) > 0: kwargs = isight.imm(self.type).profile_chassis_server_deploy(profiles, kwargs)
        else:
            for dp in kwargs.domain_names:
                indx = next((index for (index, d) in enumerate(kwargs.domain_results) if d['Name'] == dp), None)
                kwargs.isight[kwargs.org].profile[self.type][dp] = kwargs.domain_results[indx].Moid
                switch_profiles = [e for e in kwargs.profile_results if e.SwitchClusterProfile.Moid == kwargs.domain_results[indx].Moid]
                serials         = []
                for e in switch_profiles:
                    kwargs.isight[kwargs.org].profile['switch'][e.Name] = e.Moid
                    sname = 'AssignedSwitch'
                    sindx = next((index for (index, d) in enumerate(phys_devices) if d['Moid'] == e[sname].Moid), None)
                    serials.append(phys_devices[sindx])
                serials = sorted(serials, key=lambda ele: ele.SwitchId)
                profiles.append(DotMap(action='Deploy',name=dp,serial_numbers=[e.Serial for e in serials]))
            if len(profiles) > 0: kwargs = isight.imm(self.type).profile_domain_deploy(profiles, kwargs)
        #=============================================================================
        # Return kwargs
        #=============================================================================
        return kwargs

    #=============================================================================
    # Function - Profiles Update
    #=============================================================================
    def profiles_update(self, kwargs):
        #=============================================================================
        # Obtain Profile Data.
        #=============================================================================
        org_moid = kwargs.org_moids[kwargs.org].moid
        if kwargs.get('server_type') and type(kwargs.server_type) == str: utype = kwargs.server_type
        else: utype = self.type
        if re.search('^server(_template)?$', utype):
            kwargs.api_filter   = f"Organization.Moid eq '{org_moid}' and TargetPlatform eq '{kwargs.target_platform}'"
        else: kwargs.api_filter = f"Organization.Moid eq '{org_moid}'"
        kwargs.method = 'get'
        kwargs.uri    = kwargs.ezdata[utype].intersight_uri
        kwargs        = isight.api(utype).calls(kwargs)
        profiles      = kwargs.pmoids
        if len(profiles.toDict()) == 0: isight.empty_results(kwargs)
        kwargs.profile_results = kwargs.results
        #=============================================================================
        # Request from User Which Profiles to Apply this to.
        #=============================================================================
        kwargs.profile_names = sorted(list(profiles.keys()))
        kwargs.jdata = DotMap(
            default      = kwargs.profile_names[0],
            description  = f'Select the `{utype}` Profiles to update.',
            enum         = kwargs.profile_names,
            multi_select = True,
            title        = f'{self.type} Profiles')
        kwargs.profile_names = ezfunctions.variable_prompt(kwargs)
        if kwargs.target_platform == 'domain':
            kwargs.domain_names    = kwargs.profile_names
            kwargs.domain_results  = kwargs.profile_results
            kwargs.names           = [profiles[e].moid for e in kwargs.profile_names]
            kwargs.uri             = kwargs.ezdata[utype].intersight_uri_switch
            kwargs                 = isight.api('switch_profiles').calls(kwargs)
            profiles               = kwargs.pmoids
            kwargs.profile_names   = list(profiles.keys())
            kwargs.profile_results = kwargs.results
        #=============================================================================
        # Attach the Policies to the Profiles.
        #=============================================================================
        kwargs.bulk_list = []
        for i in kwargs.profile_names:
            original_bucket = profiles[i].policy_bucket
            new_bucket = []
            for e in original_bucket:
                e.pop('ClassId'); e.pop('link')
                indx = next((index for (index, d) in enumerate(kwargs.policy_bucket) if d['ObjectType'] == e['ObjectType']), None)
                if indx == None: new_bucket.append(e.toDict())
                else: new_bucket.append(kwargs.policy_bucket[indx].toDict())
            policy_bucket = sorted(new_bucket, key=lambda ele: ele['ObjectType'])
            api_body = {"Name":i,"PolicyBucket":policy_bucket,'pmoid':profiles[i].moid}
            if len(kwargs.pools) > 0:
                for e in kwargs.pools:
                    if e.ObjectType == 'resourcepool.Pool': api_body.update({'ServerAssignmentMode':'Pool','ServerPool':e.toDict()})
                    elif e.ObjectType == 'uuidpool.Pool':   api_body.update({'UuidAddressType':'Pool','UuidPool':e.toDict()})
            kwargs.bulk_list.append(api_body)
        #=============================================================================
        # Send the Bulk Request
        #=============================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[utype].intersight_uri
            kwargs     = isight.imm(utype).bulk_request(kwargs)
        #=============================================================================
        # Prompt User to Deploy Profile(s)
        #=============================================================================
        if len(kwargs.bulk_list) > 0 and re.search('^chassis|domain|server$', utype):
            kwargs.jdata             = kwargs.ezwizard.setup.properties.deploy_profiles
            kwargs.jdata.description = kwargs.jdata.description.replace('server', utype)
            deploy_profiles          = ezfunctions.variable_prompt(kwargs)
            if deploy_profiles == True: tools(utype).profiles_deploy(kwargs)
        return kwargs

    #=============================================================================
    # Function - Setup Local Time
    #=============================================================================
    def setup_local_time(self, kwargs):
        kwargs.datetime   = datetime.now(pytz.timezone(kwargs.timezone))
        kwargs.time_short = kwargs.datetime.strftime('%Y-%m-%d-%H-%M')
        kwargs.time_long  = kwargs.datetime.strftime('%Y-%m-%d %H:%M:%S %Z %z')
        return kwargs

    #=============================================================================
    # Function - Server Inventory
    #=============================================================================
    def server_inventory(self, kwargs):
        #=============================================================================
        # Get Device Registrations and build domains/servers
        #=============================================================================
        kwargs.org = 'default'
        kwargs.api_filter = f"PlatformType in ('IMCBlade', 'IMCM4', 'IMCM5', 'IMCM6', 'IMCM7', 'IMCM8', 'IMCM9', 'UCSFI', 'UCSFIISM')"
        kwargs.method     = 'get'
        kwargs.uri        = 'asset/DeviceRegistrations'
        kwargs            = isight.api('device_registration').calls(kwargs)
        for e in kwargs.results:
            if re.search('UCSFI(ISM)?', e.PlatformType):
                kwargs.domains[e.Moid] = DotMap(name = e.DeviceHostname[0], serials = e.Serial, servers = DotMap(), type = e.PlatformType)
            elif re.search('IMC', e.PlatformType):
                parent = 'none'
                if e.get('ParentConnection'): parent = e.ParentConnection.Moid
                kwargs.servers[e.Serial[0]] = DotMap(dict(parent = parent, server_name = e.DeviceHostname[0]))
        #=============================================================================
        # Get Physical Summaries and extend servers dict
        #=============================================================================
        kwargs.api_filter = 'ignore'
        kwargs.uri        = 'compute/PhysicalSummaries'
        kwargs            = isight.api('physical_summaries').calls(kwargs)
        for e in kwargs.results:
            kwargs.servers[e.Serial] = DotMap(dict(kwargs.servers[e.Serial].toDict(), **dict(
                chassis_id      = e.ChassisId,
                domain          = 'Standalone',
                hw_moid         = e.Moid,
                mgmt_ip_address = e.MgmtIpAddress,
                mgmt_mode       = e.ManagementMode,
                model           = e.Model,
                moid            = '',
                name            = e.Name,
                object_type     = e.SourceObjectType,
                organization    = 'none',
                platform_type   = e.PlatformType,
                power_state     = e.OperPowerState,
                registration    = e.RegisteredDevice.Moid,
                server_dn       = e.Dn,
                server_id       = e.ServerId,
                server_profile  = 'unassigned',
                slot            = e.SlotId,
                wwnn            = 'unassigned')))
            if len(e.ServiceProfile) > 0: kwargs.servers[e.Serial].server_profile = e.ServiceProfile
        for k in list(kwargs.servers.keys()):
            if not kwargs.servers[k].get('hw_moid'): kwargs.servers.pop(k)
            else: kwargs.hw_moids[kwargs.servers[k].hw_moid] = k
        #=============================================================================
        # Get Intersight Server Profiles
        #=============================================================================
        kwargs.api_filter = 'ignore'
        kwargs.uri        = 'server/Profiles'
        kwargs            = isight.api('server').calls(kwargs)
        if kwargs.results == None: prRed('empty results.  Exiting script...')
        profile_moids = []
        for e in kwargs.results:
            if e.AssociatedServer != None:
                serial = kwargs.hw_moids[e.AssignedServer.Moid]
                kwargs.servers[serial].moid           = e.Moid
                kwargs.servers[serial].organization   = dict(name = kwargs.org_names[e.Organization.Moid], moid = e.Organization.Moid)
                kwargs.servers[serial].server_profile = e.Name
                profile_moids.append(e.Moid)
        if len(profile_moids) > 0:
            #=============================================================================
            # Get WWPN Leases, vHBAs, vNICs, and QoS Policies
            #=============================================================================
            kwargs.names = profile_moids
            kwargs.uri   = 'fcpool/Leases'
            kwargs       = isight.api('wwnn_pool_leases').calls(kwargs)
            wwnn_leases  = kwargs.results
            kwargs.uri   = kwargs.ezdata['san_connectivity.vhbas'].intersight_uri
            kwargs       = isight.api('profile_moid').calls(kwargs)
            vhbas        = kwargs.results
            kwargs.uri   = kwargs.ezdata['lan_connectivity.vnics'].intersight_uri
            kwargs       = isight.api('profile_moid').calls(kwargs)
            vnics        = kwargs.results
            kwargs.names = list(numpy.unique(numpy.array([e.EthQosPolicy.Moid for e in vnics])))
            kwargs.uri   = kwargs.ezdata.ethernet_qos.intersight_uri
            kwargs       = isight.api('moid_filter').calls(kwargs)
            qos_policies = DotMap()
            for e in kwargs.results: qos_policies[e.Moid] = DotMap(mtu = e.Mtu, name = e.Name)
            #=============================================================================
            # Add vHBAs/vNICs to servers dict
            #=============================================================================
            for k in list(kwargs.servers.keys()):
                kwargs.servers[k].vhbas = []
                kwargs.servers[k].vnics = []
                indx = next((index for (index, d) in enumerate(wwnn_leases) if d.AssignedToEntity.Moid == kwargs.servers[k].moid), None)
                if indx != None: kwargs.servers[k].wwnn = wwnn_leases[indx].WwnId
                for e in vhbas:
                    if e.Profile.Moid == kwargs.servers[k].moid:
                        if e.WwpnAddressType == 'STATIC':
                            kwargs.servers[k].vhbas.append({'name': e.Name, 'order': e.Order, 'switch_id':e.Placement.SwitchId,'wwpn_address':e.StaticWwpnAddress})
                        else: kwargs.servers[k].vhbas.append({'name': e.Name, 'order': e.Order, 'switch_id':e.Placement.SwitchId,'wwpn_address':e.Wwpn})
                for e in vnics:
                    if e.Profile.Moid == kwargs.servers[k].moid:
                        if e.MacAddressType == 'STATIC':
                            kwargs.servers[k].vnics.append({'name': e.Name, 'mac_address':e.StaticMacAddress,'mtu':qos_policies[e.EthQosPolicy.Moid].mtu, 'order': e.Order})
                        else: kwargs.servers[k].vnics.append({'name': e.Name, 'mac_address':e.MacAddress,'mtu':qos_policies[e.EthQosPolicy.Moid].mtu, 'order': e.Order})
        #=============================================================================
        # BUILD Workbooks
        #=============================================================================
        if len(kwargs.servers) > 0:
            #=============================================================================
            # Sort server dictionary
            #=============================================================================
            kwargs.servers = DotMap(dict(sorted(kwargs.servers.items(), key=lambda ele: ele[1].server_profile)))
            for k, v in kwargs.servers.items():
                kwargs.servers[k].vnics = sorted(v.vnics, key=lambda ele: ele.order)
                kwargs.servers[k].vhbas = sorted(v.vhbas, key=lambda ele: ele.order)
                if v.platform_type == 'UCSFI': kwargs.servers[k].domain = kwargs.domains[v.registration].name
                elif v.mgmt_mode != 'IntersightStandalone': kwargs.servers[k].domain = kwargs.domains[v.parent].name
            kwargs.timezone = questions.prompt_user.for_timezone(kwargs)
            kwargs.timezone = 'America/New_York'
            kwargs  = tools(self.type).setup_local_time(kwargs)
            #=============================================================================
            # Build Workbooks and Style Sheets
            #=============================================================================
            workbook   = f'UCS-Inventory-Collector-{kwargs.time_short}.xlsx'
            kwargs = tools(self.type).workbook_styles(kwargs)
            wb = kwargs.wb; ws = wb.active; ws.title = 'Inventory List'
            #=============================================================================
            # Full Inventory Workbook
            #=============================================================================
            if kwargs.args.full_inventory:
                #=============================================================================
                # Create Column Headers - Extend with server dict
                #=============================================================================
                column_headers = ['Domain','Profile','Server','Serial','WWNN']
                vhba_list = []; vnic_list = []
                for i in list(kwargs.servers.keys()):
                    for e in kwargs.servers[i].vhbas:
                        if not e.name in vhba_list: vhba_list.append(e.name)
                    for e in kwargs.servers[i].vnics:
                        if not e.name in vnic_list: vnic_list.append(e.name)
                column_headers = column_headers + vhba_list + vnic_list
                for i in range(len(column_headers)): ws.column_dimensions[chr(ord('@')+i+1)].width = 30
                cLength = len(column_headers)
                ws_header = f'Collected UCS Data on {kwargs.time_long}'
                data = [ws_header]
                ws.append(data)
                ws.merge_cells(f'A1:{chr(ord("@")+cLength)}1')
                for cell in ws['1:1']: cell.style = 'heading_1'
                ws.append(column_headers)
                for cell in ws['2:2']: cell.style = 'heading_2'
                ws_row_count = 3
                #=============================================================================
                # Populate the Worksheet with Server Inventory
                #=============================================================================
                for k, v in kwargs.servers.items():
                    data = []
                    for i in column_headers:
                        column_count = 0
                        if   i == 'Domain':  data.append(v.domain); column_count += 1
                        elif i == 'Profile': data.append(v.server_profile); column_count += 1
                        elif i == 'Serial':  data.append(k); column_count += 1
                        elif i == 'WWNN':    data.append(v.wwnn); column_count += 1
                        elif i == 'Server':
                            if not 'sys' in v.server_dn:
                                if len(v.chassis_id) > 0: server_dn = f'sys/chassis-{v.chassis_id}/blade-{v.slot}'
                                else: server_dn = f'sys/rack-unit-{v.server_id}'
                            else: server_dn = v.server_dn
                            if len(server_dn) == 0: data.append(''); column_count += 1
                            else: data.append(server_dn); column_count += 1
                        else:
                            for e in v.vhbas:
                                if i == e.name: data.append(e.wwpn_address); column_count += 1
                            for e in v.vnics:
                                if i == e.name: data.append(e.mac_address); column_count += 1
                        if column_count == 0: data.append('Not Configured')
                    ws.append(data)
                    for cell in ws[ws_row_count:ws_row_count]:
                        if ws_row_count % 2 == 0: cell.style = 'odd'
                        else: cell.style = 'even'
                    ws_row_count += 1
            #=============================================================================
            # WWPN Inventory Workbook
            #=============================================================================
            else:
                #=============================================================================
                # Create Column Headers - Extend with server dict
                #=============================================================================
                column_headers = ['Profile','Serial']
                vhba_list = []
                for k,v in kwargs.servers.items():
                    if v.wwnn != 'unassigned':
                        if not 'WWNN' in column_headers: column_headers.append('WWNN')
                    if v.get('vhbas'):
                        for e in v.vhbas:
                            if not e.name in vhba_list: vhba_list.append(e.name)
                column_headers= column_headers + vhba_list
                for x in range(len(column_headers)): ws.column_dimensions[chr(ord('@')+x+1)].width = 30
                cLength = len(column_headers)
                ws_header = f'Collected UCS Data on {kwargs.time_long}'
                data = [ws_header]
                ws.append(data)
                ws.merge_cells(f'A1:{chr(ord("@")+cLength)}1')
                for cell in ws['1:1']: cell.style = 'heading_1'
                ws.append(column_headers)
                for cell in ws['2:2']: cell.style = 'heading_2'
                ws_row_count = 3
                #=============================================================================
                # Populate the Worksheet with Server Inventory
                #=============================================================================
                for k, v in kwargs.servers.items():
                    data = []
                    for i in column_headers:
                        column_count = 0
                        if   i == 'Profile': data.append(v.server_profile); column_count += 1
                        elif i == 'Serial':  data.append(k); column_count += 1
                        elif i == 'WWNN':    data.append(v.wwnn); column_count += 1
                        else:
                            if v.get('vhbas'):
                                for e in v.vhbas:
                                    if i == e.name: data.append(e.wwpn_address); column_count += 1
                        if column_count == 0: data.append('Not Configured')
                    ws.append(data)
                    for cell in ws[ws_row_count:ws_row_count]:
                        if ws_row_count % 2 == 0: cell.style = 'odd'
                        else: cell.style = 'even'
                    ws_row_count += 1
            #=============================================================================
            # Save the Workbook
            #=============================================================================
            wb.save(filename=workbook)

    #=============================================================================
    # Function - Workbook Styles
    #=============================================================================
    def workbook_styles(self, kwargs):
        wb = openpyxl.Workbook()
        # Build Named Style Sheets for Workbook
        bd1 = Side(style="thick", color="0070C0")
        bd2 = Side(style="medium", color="0070C0")
        heading_1 = NamedStyle(name="heading_1")
        heading_1.alignment = Alignment(horizontal="center", vertical="center", wrap_text="True")
        heading_1.border = Border(left=bd1, top=bd1, right=bd1, bottom=bd1)
        heading_1.fill = PatternFill("solid", fgColor="305496")
        heading_1.font = Font(bold=True, size=15, color="FFFFFF")
        heading_2 = NamedStyle(name="heading_2")
        heading_2.alignment = Alignment(horizontal="center", vertical="center", wrap_text="True")
        heading_2.border = Border(left=bd2, top=bd2, right=bd2, bottom=bd2)
        heading_2.font = Font(bold=True, size=15, color="44546A")
        even = NamedStyle(name="even")
        even.alignment = Alignment(horizontal="center", vertical="center", wrap_text="True")
        even.border = Border(left=bd1, top=bd1, right=bd1, bottom=bd1)
        even.font = Font(bold=False, size=12, color="44546A")
        odd = NamedStyle(name="odd")
        odd.alignment = Alignment(horizontal="center", vertical="center", wrap_text="True")
        odd.border = Border(left=bd2, top=bd2, right=bd2, bottom=bd2)
        odd.fill = PatternFill("solid", fgColor="D9E1F2")
        odd.font = Font(bold=False, size=12, color="44546A")
        wb.add_named_style(heading_1)
        wb.add_named_style(heading_2)
        wb.add_named_style(even)
        wb.add_named_style(odd)
        kwargs.wb = wb
        return kwargs
