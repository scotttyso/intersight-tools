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

class yaml_dumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(yaml_dumper, self).increase_indent(flow, False)

class tools(object):
    def __init__(self, type):
        self.type = type

    #======================================================
    # Function - Add Policies
    #======================================================
    def add_policies(self, kwargs):
        #======================================================
        # Check for YAML File Definition
        #======================================================
        pcolor.Cyan(f'\n{"-"*108}\n\n  Beginning Policy Append to Profiles...')
        pcolor.Cyan(f'\n{"-"*108}\n')
        if kwargs.args.yaml_file != None:
            yaml_arg = True
            ydata = DotMap(yaml.safe_load(open(kwargs.args.yaml_file, 'r')))
        else: yaml_arg = False; ydata = DotMap()
        #======================================================
        # Build Platform Data
        #======================================================
        target_platforms = ['chassis', 'domain', 'FIAttached', 'Standalone']
        target = DotMap()
        for e in target_platforms:
            target[e].policies = []
        for k, v in kwargs.ezdata.items():
            if v.get('target_platforms') and v.get('intersight_type') == 'policy':
                for e in v.target_platforms:
                    target[e].policies.append(k)
        #======================================================
        # Determine if the Profiles are FIAttached or Standalone
        #======================================================
        target_platforms = ['chassis', 'domain', 'server', 'server_template']
        kwargs.jdata = DotMap()
        if yaml_arg == False:
            kwargs.jdata = DotMap(
                default = 'server', description  = 'Select the Intersight Profile Type.',
                enum = target_platforms,  multi_select = True, title = 'Profile Type(s)', type = 'string')
            profile_types = ezfunctions.variable_prompt(kwargs)
        else: profile_types = [e.type for e in ydata.profile_types]
        kwargs.sub_type = DotMap()
        if yaml_arg == False:
            for e in profile_types:
                if re.search('^server(_template)?$', e):
                    kwargs.jdata = DotMap(
                        default = 'FIAttached', description  = f'Select the {e} Profile Sub-Type.',
                        enum = ['FIAttached', 'Standalone'], title = 'Profile Sub-Type', type = 'string')
                    kwargs.sub_type[e] = ezfunctions.variable_prompt(kwargs)
        else:
            for e in ydata.profile_types:
                if re.search('server|server_template'): kwargs.sub_type[e.type] = e.sub_type
        #======================================================
        # Prompt User for Policies to Attach
        #======================================================
        for e in profile_types:
            if yaml_arg == False:
                if re.search('server(_template)?', e): policies = target[kwargs.sub_type[e]].policies
                else: policies = target[e].policies
                kwargs.jdata = DotMap(
                    default      = policies[0],
                    description  = f'Select the `{", ".join(profile_types)}` Policy Type(s) (can be multiple).',
                    enum = policies, multi_select = True, title = 'Policy Type(s)', type = 'string')
                target[e].update_policies = ezfunctions.variable_prompt(kwargs)
            else: target[e].update_policies = ydata.policy_types
        #======================================================
        # Prompt for Organizations and Loop Through Target Platforms
        #======================================================
        if yaml_arg == False:  kwargs = tools(self.type).select_organizations(kwargs)
        else: kwargs.organizations = ydata.organizations
        for target_platform in profile_types:
            for org in kwargs.organizations:
                pcolor.Cyan(f'\n{"-"*108}\n\n  Starting `{target_platform}` Loop in Organization `{org}`.')
                pcolor.Cyan(f'\n{"-"*108}\n')
                tools(target_platform).update_profile(org, target, yaml_arg, ydata, kwargs)
                pcolor.Cyan(f'\n{"-"*108}\n\n  Finished `{target_platform}` Loop in Organization `{org}`.')
                pcolor.Cyan(f'\n{"-"*108}\n')
            pcolor.Purple(f'\n{"-"*108}\n\n  Finished Updating `{target_platform}` Profiles...')
            pcolor.Purple(f'\n{"-"*108}\n')

    #======================================================
    # Function - Add Vlans
    #======================================================
    def add_vlans(self, kwargs):
        #======================================================
        # Function - Add Vlans
        #======================================================
        # Validate YAML configuration file is defined.
        if kwargs.args.yaml_file != None:
            ydata = DotMap(yaml.safe_load(open(kwargs.args.yaml_file, 'r'))).add_vlans
        else:
            prRed(f'\n{"-"*108}\n\n  Missing Required YAML File Argument `-y`.  Exiting Process.')
            prRed(f'\n{"-"*108}\n')
            len(False); sys.exit(1)
        #======================================================
        # Get VLAN List and Organizations from YAML configuration file.
        #======================================================
        tags  = [{'key': 'Module','value': 'day2tools'}]
        kwargs.organizations = ydata.organizations
        for org in kwargs.organizations:
            kwargs.org = org
            vpolicy    = ydata.vlan_policy.name
            vlans      = ydata.vlan_policy.vlans
            pcolor.Cyan(f'\n{"-"*108}\n\n  Starting Loop on Organization {org}.')
            pcolor.Cyan(f'\n{"-"*108}\n')
            #======================================================
            # Query the API for the VLAN Policies
            #======================================================
            kwargs = isight.api_get(False, [vpolicy], 'vlan', kwargs)
            vlan_moid = kwargs.pmoids[vpolicy].moid
            #======================================================
            # Query the API for the VLANs Attached to the VLAN Policy
            #======================================================
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
                #======================================================
                # Query the API for the Ethernet Network Group Policies
                #======================================================
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
            #======================================================
            # Loop through Policy Creation
            #======================================================
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
                #======================================================
                # Query the API for the Ethernet Network Group Policies
                #======================================================
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
                #======================================================
                # Query the API for Policies
                #======================================================
                pdata = DotMap()
                ilist = ['ethernet_adapter', 'ethernet_network_control', 'ethernet_qos', 'mac']
                for e in ilist:
                    kwargs   = isight.api_get(True, idata[e], e, kwargs)
                    pdata[e] = kwargs.pmoids
                #======================================================
                # Query the API for the LAN Connectivity Policies
                #======================================================
                kwargs       = isight.api_get(True, [e.name for e in idata.lan_connectivity], 'lan_connectivity', kwargs)
                lan_policies = kwargs.pmoids
                #======================================================
                # Configure LAN Connectivity Policies
                #======================================================
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
                    #======================================================
                    # Configure vNIC Policies
                    #======================================================
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
        
    #======================================================
    # Function - Add Policies
    #======================================================
    def clone_policies(self, kwargs):
        #======================================================
        # Determine Policies to Clone
        #======================================================
        pcolor.Cyan(f'\n{"-"*108}\n\n  Beginning Policy Clone Process...')
        pcolor.Cyan(f'\n{"-"*108}\n')
        kwargs = questions.target_platform(kwargs)
        kwargs = questions.build_policy_list(kwargs)
        kwargs.jdata = DotMap(
            default      = '',
            description  = f'Select the policy types you would like to clone in the environment:',
            enum         = kwargs.policy_list,
            multi_select = True,
            title        = 'Policies',
            type         = 'string')
        policy_types = ezfunctions.variable_prompt(kwargs)
        #======================================================
        # Prompt User for Source and Destination Organization
        #======================================================
        orgs = list(kwargs.org_moids.keys())
        kwargs.jdata = DotMap(
            default     = orgs[0],
            description = 'Select the Source Organization to clone the policies from.',
            enum        = orgs, title = 'Organization', type = 'string')
        source_org               = ezfunctions.variable_prompt(kwargs)
        kwargs.jdata.description = 'Select the Destination Organization to clone the policies to.'
        destination_org          = ezfunctions.variable_prompt(kwargs)
        #======================================================
        # Prompt User for Policies to Clone
        #======================================================
        kwargs.org = source_org
        for e in policy_types:
            kwargs.api_filter = f"Organization.Moid eq '{kwargs.org_moids[source_org].moid}'"
            kwargs.method     = 'get'
            kwargs.uri        = kwargs.ezdata[e].intersight_uri
            kwargs            = isight.api(e).calls(kwargs)
            kwargs[f'{e}_results'] = kwargs.results
            for d in kwargs[f'{e}_results']: kwargs[e][d.Name] = d
            policies = sorted([d.Name for d in kwargs[f'{e}_results']])
            kwargs.jdata  = DotMap(
            default       = '',
            description   = f'Select the `{e}` policies to clone from source org: `{source_org}` to destination org: `{destination_org}`.',
            multi_select  = True,
            enum          = policies, title = f'{e} Policies', type = 'string')
            clone_poicies = ezfunctions.variable_prompt(kwargs)
            key_list = ['Description', 'Name', 'Tags']
            for k,v in kwargs.ezdata[e].allOf[1].properties.items():
                if v.type == 'array':
                    key_list.append(v['items'].intersight_api)
                elif v.type == 'object':
                    key_list.append(v.intersight_api)
                elif re.search('boolean|integer|string', v.type):
                    if re.search(r'\$ref\:', v.intersight_api): key_list.append(v.intersight_api.split(':')[1])
                    else: key_list.append(v.intersight_api)
                else: pcolor.Yellow(json.dumps(v, indent=4)); sys.exit(1)
            kwargs.bulk_list = []
            key_list = list(numpy.unique(numpy.array(key_list)))
            for d in clone_poicies:
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

    #======================================================
    # Function - HCL Inventory
    #======================================================
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
            kwargs.timezone = questions.prompt_user_for_timezone(kwargs)
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

    #======================================================
    # Function - Prompt for Organizations
    #======================================================
    def select_organizations(self, kwargs):
        kwargs.jdata              = kwargs.ezdata.organization.allOf[1].properties.name
        kwargs.jdata.description  = 'Select the Organization(s) to Apply the changes to.'
        kwargs.jdata.enum         = list(kwargs.org_moids.keys())
        kwargs.jdata.multi_select = True
        kwargs.jdata.title        = 'Intersight Organization(s)'
        kwargs.organizations      = ezfunctions.variable_prompt(kwargs)
        return kwargs

    #======================================================
    # Function - Setup Local Time
    #======================================================
    def setup_local_time(self, kwargs):
        kwargs.datetime   = datetime.now(pytz.timezone(kwargs.timezone))
        kwargs.time_short = kwargs.datetime.strftime('%Y-%m-%d-%H-%M')
        kwargs.time_long  = kwargs.datetime.strftime('%Y-%m-%d %H:%M:%S %Z %z')
        return kwargs

    #======================================================
    # Function - Server Inventory
    #======================================================
    def server_inventory(self, kwargs):
        #======================================================
        # Get Device Registrations and build domains/servers
        #======================================================
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
        #======================================================
        # Get Physical Summaries and extend servers dict
        #======================================================
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
        #======================================================
        # Get Intersight Server Profiles
        #======================================================
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
            #======================================================
            # Get WWPN Leases, vHBAs, vNICs, and QoS Policies
            #======================================================
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
            #======================================================
            # Add vHBAs/vNICs to servers dict
            #======================================================
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
        #======================================================
        # BUILD Workbooks
        #======================================================
        if len(kwargs.servers) > 0:
            #======================================================
            # Sort server dictionary
            #======================================================
            kwargs.servers = DotMap(dict(sorted(kwargs.servers.items(), key=lambda ele: ele[1].server_profile)))
            for k, v in kwargs.servers.items():
                kwargs.servers[k].vnics = sorted(v.vnics, key=lambda ele: ele.order)
                kwargs.servers[k].vhbas = sorted(v.vhbas, key=lambda ele: ele.order)
                if v.platform_type == 'UCSFI': kwargs.servers[k].domain = kwargs.domains[v.registration].name
                elif v.mgmt_mode != 'IntersightStandalone': kwargs.servers[k].domain = kwargs.domains[v.parent].name
            #kwargs.timezone = questions.prompt_user_for_timezone(kwargs)
            kwargs.timezone = 'America/New_York'
            kwargs  = tools(self.type).setup_local_time(kwargs)
            #======================================================
            # Build Workbooks and Style Sheets
            #======================================================
            workbook   = f'UCS-Inventory-Collector-{kwargs.time_short}.xlsx'
            kwargs = tools(self.type).workbook_styles(kwargs)
            wb = kwargs.wb; ws = wb.active; ws.title = 'Inventory List'
            #======================================================
            # Full Inventory Workbook
            #======================================================
            if kwargs.args.full_inventory:
                #==================================================
                # Create Column Headers - Extend with server dict
                #==================================================
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
                #==================================================
                # Populate the Worksheet with Server Inventory
                #==================================================
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
            #======================================================
            # WWPN Inventory Workbook
            #======================================================
            else:
                #==================================================
                # Create Column Headers - Extend with server dict
                #==================================================
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
                #==================================================
                # Populate the Worksheet with Server Inventory
                #==================================================
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
            #======================================================
            # Save the Workbook
            #======================================================
            wb.save(filename=workbook)

    #======================================================
    # Function - Update Profile
    #======================================================
    def update_profile(self, org, target, yaml_arg, ydata, kwargs):
        kwargs.org = org
        policies = DotMap()
        for policy in target[self.type].update_policies:
            #======================================================
            # Query API for List of Policies.
            #======================================================
            kwargs.api_filter = f"Organization.Moid eq '{kwargs.org_moids[org].moid}'"
            kwargs.method     = 'get'
            kwargs.uri        = kwargs.ezdata[policy].intersight_uri
            kwargs            = isight.api(policy).calls(kwargs)
            if kwargs.results == None: isight.empty_results(kwargs)
            policies[policy] = kwargs.pmoids
            #======================================================
            # Prompt User for Policy to Attach.
            #======================================================
            kwargs.jdata = DotMap(
                default      = list(policies[policy].keys())[0],
                description  = f'Select the {policy} Policy to attach to the Profile(s).',
                enum         = list(policies[policy].keys()),
                title        = f'{policy} Policy Name')
            policies[policy].name = ezfunctions.variable_prompt(kwargs)
        #======================================================
        # Obtain Profile Data.
        #======================================================
        kwargs.method  = 'get'
        kwargs.top1000 = True
        org_moid       = kwargs.org_moids[org].moid
        if re.search('^server(_template)?$', self.type):
            target_type = kwargs.sub_type[self.type]
            kwargs.api_filter= f"Organization.Moid eq '{org_moid}' and TargetPlatform eq '{target_type}'"
        else: kwargs.api_filter = f"Organization.Moid eq '{org_moid}'"
        kwargs.uri = kwargs.ezdata[self.type].intersight_uri
        kwargs     = isight.api(self.type).calls(kwargs)
        profiles   = kwargs.pmoids
        for k,v in profiles.items(): profiles[k].name = k
        if profiles == None: isight.empty_results(kwargs)
        #======================================================
        # Request from User Which Profiles to Apply this to.
        #======================================================
        if yaml_arg == False:
            kwargs.jdata = DotMap(
                default      = sorted(list(profiles.keys()))[0],
                description  = f'Select the {self.type} Profiles to Apply the {policy} to.',
                enum         = sorted(list(profiles.keys())),
                multi_select = True,
                title        = f'{self.type} Profiles')
            profile_names = ezfunctions.variable_prompt(kwargs)
        else: profile_names = ydata.profiles
        #======================================================
        # Attach the Policy to the Selected Server Profiles.
        #======================================================
        for i in profile_names:
            pcolor.Purple(f'\n{"-"*108}\n  Starting on Server Profile `{i}`.\n{"-"*108}\n')
            policy_bucket = profiles[i].policy_bucket
            object_index  = dict((d.ObjectType, s) for s, d in enumerate(policy_bucket))
            for e in policies.keys():
                policy_moid = policies[e][policies[e].name].moid
                object_type = kwargs.ezdata[e].ObjectType
                policy_uri  = kwargs.ezdata[e].intersight_uri
                #======================================================
                # Index the Server List to find the Server Profile and 
                # pull the Policy BucketSee if the Policy Type is 
                # Already Attached.  If attached, Update to the new.
                # Moid, else attach the Policy.
                #======================================================
                if object_index.get(object_type):
                    type_index = object_index.get(object_type, -1)
                    policy_link = f"https://www.intersight.com/api/v1/{policy_uri}/{policy_moid}"
                    policy_bucket[type_index].update({'Moid':policy_moid, 'link': policy_link})
                else:
                    policy_bucket.append({'Moid': policy_moid, 'ObjectType': object_type})
            pbucket = []
            for x in policy_bucket: pbucket.append(x.toDict())
            policy_bucket = sorted(pbucket, key=lambda ele: ele.ObjectType)
            #======================================================
            # Patch the Profile with new Policy Bucket.
            #======================================================
            kwargs.api_body = {"Name":profiles[i].name,"PolicyBucket":pbucket}
            kwargs.method = 'patch'
            kwargs.pmoid  = profiles[i].moid
            if re.search('FIAttached|Standalone', self.type):
                kwargs.uri   = kwargs.ezdata['server'].intersight_uri
            else: kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs = isight.api(self.type).calls(kwargs)

    #======================================================
    # Function - Workbook Styles
    #======================================================
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
