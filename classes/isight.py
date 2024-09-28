#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, pcolor, validating
    from copy import deepcopy
    from datetime import datetime
    from dotmap import DotMap
    from intersight_auth import IntersightAuth, repair_pem
    from operator import itemgetter
    from stringcase import pascalcase, snakecase
    import base64, json, numpy, os, re, requests, time, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
serial_regex = re.compile('^[A-Z]{3}[2-3][\\d]([0][1-9]|[1-4][0-9]|[5][0-3])[\\dA-Z]{4}$')
part1 = 'adapter_configuration|bios|boot_order|(ethernet|fibre_channel)_adapter|drive_security|ethernet_network(_group)?|firmware|imc_access'
part2 = 'ipmi_over_lan|iscsi_(boot|static_target)|(l|s)an_connectivity|local_user|network_connectivity|snmp|storage|syslog|system_qos|(vhba|vnic)_template'
policy_specific_regex = re.compile(f'^{part1}|{part2}$')

#=============================================================================
# API Class
#=============================================================================
class api(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function - Get Organizations from Intersight
    #=========================================================================
    def all_organizations(self, kwargs):
        #=====================================================================
        # Get Organization List from the API
        #=====================================================================
        kwargs = kwargs | DotMap(api_filter = 'ignore', method = 'get', uri = 'organization/Organizations')
        kwargs = api(self.type).calls(kwargs)
        kwargs.org_moids  = kwargs.pmoids
        for k, v in kwargs.org_moids.items(): kwargs.org_names[v.moid] = k
        return kwargs

    #=========================================================================
    # Function - Build Compute Dictionary
    #=========================================================================
    def build_compute_dictionary(self, kwargs):
        server_results = kwargs.results
        pcolor.Cyan(f'\n   - Pulling Server Inventory for the following Physical Server(s):')
        for e in server_results: pcolor.Cyan(f'     * {e.Serial}')
        kwargs = kwargs | DotMap(method = 'get', names = [e.Moid for e in server_results])
        for e in ['adapter/Units', 'equipment/Tpms', 'processor/Units', 'storage/Controllers']:
            kwargs.uri = e
            kwargs     = api('ancestors').calls(kwargs)
            kwargs[e.split('/')[0]] = kwargs.results
        for i in server_results:
            for e in ['adapter', 'equipment', 'processor', 'storage']:
                kwargs[f'{e}_results'] = []
                for f in kwargs[e]:
                    check = False
                    for g in f.Ancestors:
                        if g.Moid == i.Moid: check = True
                    if check == True: kwargs[f'{e}_results'].append(f)
            vics = []
            for e in kwargs['adapter_results']:
                if re.search('(V5)', e.Model):    vic_generation = 'gen5'
                elif re.search('INTEL', e.Model): vic_generation = 'INTEL'
                elif re.search('MLNX', e.Model):  vic_generation = 'MLNX'
                else: vic_generation = 'gen4'
                if 'MLOM' in e.PciSlot:  vic_slot = 'MLOM'
                elif not 'MEZZ' in e.PciSlot and 'SlotID' in e.PciSlot:
                    vic_slot = re.search('SlotID:(\\d)', e.PciSlot).group(1)
                elif re.search("\\d", str(e.PciSlot)): vic_slot = int(e.PciSlot)
                vics.append(DotMap(vic_gen = vic_generation, vic_slot = vic_slot))
            if len(vics) > 0:
                vic_names = []
                for e in vics:
                    if type(vics[0].vic_slot) == str: vic_names.append((vics[0].vic_slot).lower())
                    else: vic_names.append(vics[0].vic_slot)
                vic_names = '-'.join(vic_names)
            else: vic_names = ''
            sg = re.search('-(M[\\d])', i.Model).group(1)
            storage_controllers = DotMap()
            for e in kwargs['storage_results']:
                if len(e.Model) > 0:
                    mstring = 'Cisco Boot optimized M.2 Raid controller'
                    if e.Model == mstring: storage_controllers['UCS-M2-HWRAID'] = e.ControllerId
                    else: storage_controllers[e.Model] = e.ControllerId
            if i.SourceObjectType == 'compute.RackUnit': ctype = 'rack'
            else: ctype = 'blade'
            if kwargs.boot_volume.lower() == 'san': boot_type = 'fcp'
            else: boot_type = kwargs.boot_volume.lower()
            if 'Intel' in kwargs['processor_results'][0].Vendor: cv = 'intel'
            else: cv = 'amd'
            if len(kwargs['equipment_results']) > 0: tpm = '-tpm'
            else: tpm = ''
            if self.type == 'azurestack':
                template    = f"{sg}-{cv}-azure-{ctype}-{boot_type}{tpm}"
            else:  template = f"{sg}-{cv}{tpm}-{ctype}-{boot_type}-vic-{vics[0].vic_gen}-{vic_names}"
            kwargs.servers[i.Serial] = DotMap(
                boot_volume           = kwargs.boot_volume.lower(),
                chassis_id            = i.ChassisId,
                chassis_moid          = i.Parent.Moid,
                cpu                   = cv,
                domain                = '',
                firmware              = i.Firmware,
                gen                   = sg,
                management_ip_address = i.MgmtIpAddress,
                model                 = i.Model,
                moid                  = i.Moid,
                object_type           = i.SourceObjectType,
                serial                = i.Serial,
                server_id             = i.ServerId,
                slot                  = i.SlotId,
                storage_controllers   = storage_controllers,
                template              = template,
                tpm                   = tpm,
                vics                  = vics)
            if type(kwargs.servers[i.Serial].chassis_id) == int:
                for e in ['chassis_id', 'chassis_moid', 'domain', 'slot']: kwargs.servers[i.Serial].pop(e)
        pcolor.Cyan(f'   - Completed Server Inventory.\n')
        # Return kwargs
        return kwargs

    #=========================================================================
    # Function - Process API Results
    #=========================================================================
    def build_pmoid_dictionary(self, api_results, kwargs):
        api_dict = DotMap()
        if not kwargs.build_skip == True and api_results.get('Results'):
            for i in api_results.Results:
                if i.get('Body'): i = i.Body
                ikeys = list(i.keys())
                if   'VlanId'  in ikeys: iname = str(i.VlanId)
                elif i.ObjectType == 'asset.DeviceRegistration': iname = i.Serial[0]
                elif 'PcId'    in ikeys: iname = str(i.PcId)
                elif 'PortId'  in ikeys: iname = str(i.PortId)
                elif 'Serial'  in ikeys: iname = i.Serial
                elif 'VsanId'  in ikeys: iname = str(i.VsanId)
                elif 'Answers' in ikeys: iname = i.Answers.Hostname
                elif 'Name'    in ikeys: iname = i.Name
                elif self.type == 'upgrade' and i.Status == 'IN_PROGRESS': iname = kwargs.srv_moid
                elif 'SocketDesignation' in ikeys: iname = i.Dn
                elif 'EndPointUser'      in ikeys: iname = i.EndPointUser.Moid
                elif 'PortIdStart'       in ikeys: iname = str(i.PortIdStart)
                elif 'Version'           in ikeys: iname = i.Version
                elif 'ControllerId'      in ikeys: iname = i.ControllerId
                elif 'Identity'          in ikeys: iname = i.Identity
                elif 'MacAddress'        in ikeys: iname = i.MacAddress
                elif 'WWnId'             in ikeys: iname = i.WWnId
                elif 'IpV4Address'       in ikeys: iname = i.IpV4Address
                elif 'IpV6Address'       in ikeys: iname = i.IpV6Address
                elif 'IqnAddress'        in ikeys: iname = i.IqnAddress
                elif 'Uuid'              in ikeys: iname = i.Uuid
                elif 'PciSlot'           in ikeys: iname = str(i.PciSlot)
                else: iname = i.Moid
                if i.get('PcId') or i.get('PortId') or i.get('PortIdStart'):
                    api_dict[i.PortPolicy.Moid][iname].moid = i.Moid
                else: api_dict[iname].moid = i.Moid
                if 'ConfiguredBootMode'    in ikeys: api_dict[iname].boot_mode = i.ConfiguredBootMode
                if 'EnforceUefiSecureBoot' in ikeys: api_dict[iname].enable_secure_boot = i.EnforceUefiSecureBoot
                if 'IpV4Config'            in ikeys: api_dict[iname].ipv4_config = i.IpV4Config
                if 'IpV6Config'            in ikeys: api_dict[iname].ipv6_config = i.IpV6Config
                if 'ManagementMode'        in ikeys: api_dict[iname].management_mode = i.ManagementMode
                if 'MgmtIpAddress'         in ikeys: api_dict[iname].management_ip_address = i.MgmtIpAddress
                if 'Model'                 in ikeys:
                    api_dict[iname].model = i.Model
                    api_dict[iname].name = i.Name
                    api_dict[iname].object_type = i.ObjectType
                    api_dict[iname].registered_device = i.RegisteredDevice.Moid
                    if 'ChassisId'        in ikeys: api_dict[iname].id = i.ChassisId
                    if 'SourceObjectType' in ikeys: api_dict[iname].object_type = i.SourceObjectType
                if 'Organization'  in ikeys: api_dict[iname].organization = kwargs.org_names[i.Organization.Moid]
                if 'PolicyBucket'  in ikeys: api_dict[iname].policy_bucket = i.PolicyBucket
                if 'Selectors'     in ikeys: api_dict[iname].selectors = i.Selectors
                if 'SwitchId'      in ikeys: api_dict[iname].switch_id = i.SwitchId
                if 'Tags'          in ikeys: api_dict[iname].tags = i.Tags
                if 'UpgradeStatus' in ikeys: api_dict[iname].upgrade_status = i.UpgradeStatus
                if 'WorkflowInfo'  in ikeys:
                    if type(i.WorkflowInfo) != kwargs.type_none: api_dict[iname].workflow_moid  = i.WorkflowInfo.Moid
                if 'Distributions' in ikeys: api_dict[iname].distributions  = [e.Moid for e in i.Distributions]
                if 'Source'   in ikeys and 'LocationLink' in ikeys: api_dict[iname].url = i.Source.LocationLink
                if 'Vendor'   in ikeys and   type(i.Vendor) != str: api_dict[iname].vendor_moid = i.Vendor.Moid
                if 'Profiles' in ikeys and i.Profiles != None:
                    api_dict[iname].profiles = []
                    for x in i.Profiles:
                        xdict = DotMap(Moid=x.Moid,ObjectType=x.ObjectType)
                        api_dict[iname].profiles.append(xdict)
        return api_dict

    #=========================================================================
    # Function - Perform API Calls to Intersight
    #=========================================================================
    def calls(self, kwargs):
        #=====================================================================
        # Global options for debugging
        # 1 - Shows the api request response status code
        # 5 - Show URL String + Lower Options
        # 6 - Adds Results + Lower Options
        # 7 - Adds json payload + Lower Options
        # Note: payload shows as pretty and straight to check
        #       for stray object types like Dotmap and numpy
        #=====================================================================
        debug_level   = kwargs.args.debug_level
        #=====================================================================
        # Authenticate to the API
        #=====================================================================
        if not re.search('^(organization|resource)/', kwargs.uri): org_moid = kwargs.org_moids[kwargs.org].moid
        #=====================================================================
        # Authenticate to the API
        #=====================================================================
        def api_auth_function(kwargs):
            api_key_id      = kwargs.args.intersight_api_key_id
            secret_key      = kwargs.args.intersight_secret_key
            if os.path.isfile(secret_key):
                kwargs.api_auth = IntersightAuth(api_key_id=api_key_id, secret_key_filename=secret_key)
            elif re.search(r'\n', secret_key): kwargs.api_auth = IntersightAuth(api_key_id=api_key_id, secret_key_string=secret_key)
            else: kwargs.api_auth = IntersightAuth(api_key_id=api_key_id, secret_key_string=repair_pem(secret_key))
            kwargs.auth_time= time.time()
            return kwargs
        if not kwargs.get('api_auth'): kwargs = api_auth_function(kwargs)
        #=====================================================================
        # Setup API Parameters
        #=====================================================================
        def api_calls(kwargs):
            #=================================================================
            # Perform the apiCall
            #=================================================================
            if type(kwargs.api_body) == kwargs.type_dotmap: kwargs.api_body = kwargs.api_body.toDict()
            aargs   = kwargs.api_args
            aauth   = kwargs.api_auth
            method  = kwargs.method
            moid    = kwargs.pmoid
            payload = kwargs.api_body
            retries = 3
            uri     = kwargs.uri
            url     = f'{kwargs.args.url}/api/v1'
            for i in range(retries):
                try:
                    def send_error():
                        pcolor.Red(json.dumps(kwargs.api_body, indent=4))
                        pcolor.Red(kwargs.api_body)
                        pcolor.Red(f'!!! ERROR !!!')
                        if   method == 'get_by_moid': pcolor.Red(f'  URL: {url}/{uri}/{moid}')
                        elif method ==      'delete': pcolor.Red(f'  URL: {url}/{uri}/{moid}')
                        elif method ==         'get': pcolor.Red(f'  URL: {url}/{uri}{aargs}')
                        elif method ==       'patch': pcolor.Red(f'  URL: {url}/{uri}/{moid}')
                        elif method ==        'post': pcolor.Red(f'  URL: {url}/{uri}')
                        pcolor.Red(f'  Running Process: {method} {self.type}')
                        pcolor.Red(f'    Error status is {response}')
                        if '{' in response.text:
                            for k, v in (response.json()).items(): pcolor.Red(f"    {k} is '{v}'")
                        else: pcolor.Red(response.text)
                        len(False); sys.exit(1)
                    if   method == 'get_by_moid': response = requests.get(   f'{url}/{uri}/{moid}', verify=False, auth=aauth)
                    elif method ==      'delete': response = requests.delete(f'{url}/{uri}/{moid}', verify=False, auth=aauth)
                    elif method ==         'get': response = requests.get(   f'{url}/{uri}{aargs}', verify=False, auth=aauth)
                    elif method ==       'patch': response = requests.patch( f'{url}/{uri}/{moid}', verify=False, auth=aauth, json=payload)
                    elif method ==        'post': response = requests.post(  f'{url}/{uri}',        verify=False, auth=aauth, json=payload)
                    if re.search('40[0|3]', str(response)):
                        retry_action = False
                        #send_error()
                        for k, v in (response.json()).items():
                            if 'user_action_is_not_allowed' in v: retry_action = True
                            elif 'policy_attached_to_multiple_profiles_cannot_be_edited' in v: retry_action = True
                        if i < retries -1 and retry_action == True:
                            pcolor.Purple('     **NOTICE** Profile in Validating State.  Sleeping for 45 Seconds and Retrying.')
                            time.sleep(45)
                            continue
                        else: send_error()
                    elif not re.search('(20[0-9])', str(response)): send_error()
                except requests.HTTPError as e:
                    if re.search('Your token has expired', str(e)) or re.search('Not Found', str(e)):
                        kwargs.results = False
                        return kwargs
                    elif re.search('user_action_is_not_allowed', str(e)):
                        if i < retries -1: time.sleep(45); continue
                        else: raise
                    elif re.search('There is an upgrade already running', str(e)):
                        kwargs.running = True
                        return kwargs
                    else:
                        pcolor.Red(f"Exception when calling {url}/{uri}: {e}\n")
                        len(False); sys.exit(1)
                break
            #=================================================================
            # Print Debug Information if Turned on
            #=================================================================
            api_results = DotMap(response.json())
            if int(debug_level) >= 1: pcolor.Cyan(f'RESPONSE: {str(response)}')
            if int(debug_level)>= 5:
                if   method == 'get_by_moid': pcolor.Cyan(f'URL:      {url}/{uri}/{moid}')
                elif method ==         'get': pcolor.Cyan(f'URL:      {url}/{uri}{aargs}')
                elif method ==       'patch': pcolor.Cyan(f'URL:      {url}/{uri}/{moid}')
                elif method ==        'post': pcolor.Cyan(f'URL:      {url}/{uri}')
            if int(debug_level) >= 6:
                pcolor.Cyan('HEADERS:')
                pcolor.Cyan(json.dumps(dict(response.headers), indent=4))
                if len(payload) > 0: pcolor.Cyan('PAYLOAD:'); pcolor.Cyan(json.dumps(payload, indent=4))
            if int(debug_level) == 7: pcolor.Cyan(json.dumps(api_results, indent=4))
            #=================================================================
            # Gather Results from the apiCall
            #=================================================================
            results_keys = list(api_results.keys())
            if 'Results' in results_keys: kwargs.results = api_results.Results
            else: kwargs.results = api_results
            if not kwargs.build_skip == True: kwargs.build_skip = False
            if 'post' in method:
                if api_results.get('Responses'):
                    api_results['Results'] = deepcopy(api_results['Responses'])
                    kwargs.pmoids = api.build_pmoid_dictionary(self, api_results, kwargs)
                elif re.search('bulk.(MoCloner|Request)', api_results.ObjectType):
                    kwargs.pmoids = api.build_pmoid_dictionary(self, api_results, kwargs)
                else:
                    kwargs.pmoid = api_results.Moid
                    if kwargs.api_body.get('Name'): kwargs.pmoids[kwargs.api_body['Name']] = kwargs.pmoid
            elif 'inventory' in kwargs.uri: pass
            elif kwargs.build_skip == False: kwargs.pmoids = api.build_pmoid_dictionary(self, api_results, kwargs)
            #=================================================================
            # Print Progress Notifications
            #=================================================================
            if re.search('(patch|post)', method):
                if api_results.get('Responses'):
                    for e in api_results.Responses:
                        kwargs.api_results = e.Body
                        validating.completed_item(self.type, kwargs)
                elif re.search('bulk.(Request|RestResult)', api_results.ObjectType):
                    for e in api_results.Results:
                        kwargs.api_results = e.Body
                        if re.search('bulk.(Request|RestResult)', api_results.ObjectType):
                            if e.Body.get('Name'): name_key = 'Name'
                            elif e.Body.get('Identity'): name_key = 'Identity'
                            elif e.Body.get('PcId'): name_key = 'PcId'
                            elif e.Body.get('PortId'): name_key = 'PortId'
                            elif e.Body.get('PortIdStart'): name_key = 'PortIdStart'
                            elif e.Body.get('VlanId'): name_key = 'VlanId'
                            elif e.Body.get('VsanId'): name_key = 'VsanId'
                            elif e.Body.ObjectType == 'iam.EndPointUserRole': pass
                            else:
                                pcolor.Red(json.dumps(e.Body, indent=4))
                                pcolor.Red('Missing name_key.  isight.py line 164')
                                len(False); sys.exit(1)
                            if not e.Body['ObjectType'] == 'iam.EndPointUserRole':
                                indx = next((index for (index, d) in enumerate(kwargs.api_body['Requests']) if d['Body'][name_key] == e.Body[name_key]), None)
                                kwargs.method = (kwargs.api_body['Requests'][indx]['Verb']).lower()
                        validating.completed_item(self.type, kwargs)
                else:
                    kwargs.api_results = api_results
                    validating.completed_item(self.type, kwargs)
            return kwargs
        #=====================================================================
        # Pagenation for Get > 1000
        #=====================================================================
        kwargs_keys = list(kwargs.keys())
        if kwargs.method == 'get':
            def build_api_args(kwargs_keys, kwargs):
                if not 'api_filter' in kwargs_keys:
                    regex1 = re.compile('moid_filter|registered_device|resource_groups|workflow_os_install')
                    regex2 = re.compile('(ip|iqn|mac|uuid|wwnn|wwpn)_leases')
                    if re.search('(vlans|vsans|port.port_)', self.type): names = ", ".join(map(str, kwargs.names))
                    else: names = "', '".join(kwargs.names).strip("', '")
                    if re.search('^(organization|resource_group)$', self.type): api_filter = f"Name in ('{names}')"
                    elif 'ancestors'    == self.type:         api_filter = f"Ancestors/any(t:t/Moid in ('{names}'))"
                    elif 'asset_target' == self.type:         api_filter = f"TargetId in ('{names}')"
                    elif 'connectivity.vhbas' in self.type:   api_filter = f"Name in ('{names}') and SanConnectivityPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'connectivity.vnics' in self.type:   api_filter = f"Name in ('{names}') and LanConnectivityPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'hcl_status' == self.type:           api_filter = f"ManagedObject.Moid in ('{names}')"
                    elif 'iam_role' == self.type:             api_filter = f"Name in ('{names}') and Type eq 'IMC'"
                    elif 'iqn_pool_leases' == self.type:      api_filter = f"AssignedToEntity.Moid in ('{names}')"
                    elif 'multi_org' in self.type:            api_filter = f"Organization.Moid in ('{names}')"
                    elif 'parent_moids' in self.type:         api_filter = f"{kwargs.parent}.Moid in ('{names}')"
                    elif 'port.port_channel_' in self.type:   api_filter = f"PcId in ({names}) and PortPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'port.port_modes' == self.type:      api_filter = f"PortIdStart in ({names}) and PortPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'port.port_role_' in self.type:      api_filter = f"PortId in ({names}) and PortPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'profile_moid' == self.type:         api_filter = f"Profile.Moid in ('{names}')"
                    elif re.search(regex1, self.type):        api_filter = f"Moid in ('{names}')"
                    elif re.search(regex2, self.type):        api_filter = f"{kwargs.pkey} in ('{names}')"
                    elif 'registered_device' in self.type:    api_filter = f"RegisteredDevice.Moid in ('{names}')"
                    elif 'reservations' in self.type:         api_filter = f"Identity in ('{names}')"
                    elif 'serial_number' == self.type:        api_filter = f"Serial in ('{names}')"
                    elif 'storage.drive_groups' == self.type: api_filter = f"Name in ('{names}') and StoragePolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'switch' == self.type:               api_filter = f"Name in ('{names}') and SwitchClusterProfile.Moid eq '{kwargs.pmoid}'"
                    elif 'switch_profiles' == self.type:      api_filter = f"SwitchClusterProfile.Moid in ('{names}')"
                    elif 'sw_profile_templates' == self.type: api_filter = f"SwitchClusterProfileTemplate.Moid in ('{names}')"
                    elif 'user_role' == self.type:            api_filter = f"EndPointUser.Moid in ('{names}') and EndPointUserPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'vlan.vlans' == self.type:           api_filter = f"VlanId in ({names}) and EthNetworkPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'vsan.vsans' == self.type:           api_filter = f"VsanId in ({names}) and FcNetworkPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'wwnn_pool_leases' == self.type:     api_filter = f"PoolPurpose eq 'WWNN' and AssignedToEntity.Moid in ('{names}')"
                    elif 'wwpn_pool_leases' == self.type:     api_filter = f"PoolPurpose eq 'WWPN' and AssignedToEntity.Moid in ('{names}')"
                    else: api_filter = f"Name in ('{names}') and Organization.Moid eq '{org_moid}'"
                    if re.search('ww(n|p)n.(leases|reservations)', self.type): pass
                    elif re.search('ww(n|p)n', self.type): api_filter = api_filter + f" and PoolPurpose eq '{self.type.upper()}'"
                    api_args = f'?$filter={api_filter}'
                elif  kwargs.api_filter == '': api_args = ''
                elif  kwargs.api_filter == 'ignore': api_args = ''
                else: api_args = f'?$filter={kwargs.api_filter}'
                if 'expand' in kwargs_keys:
                    if api_args == '': api_args = f'?$expand={kwargs.expand}'
                    else: api_args = api_args + f'&$expand={kwargs.expand}'
                if 'order_by' in kwargs_keys:
                    if api_args == '': api_args = f'?$orderby={kwargs.order_by}'
                    else: api_args = api_args + f'&$orderby={kwargs.order_by}'
                return api_args

            if len(kwargs.names) > 100:
                chunked_list = list(); chunk_size = 100
                for i in range(0, len(kwargs.names), chunk_size):
                    chunked_list.append(kwargs.names[i:i+chunk_size])
                results     = []
                moid_dict   = {}
                parent_moid = kwargs.pmoid
                for i in chunked_list:
                    kwargs.names    = i
                    kwargs.api_args = build_api_args(kwargs_keys, kwargs)
                    if re.search('leases|port.port|reservations|user_role|vhbas|vlans|vsans|vnics', self.type):
                        kwargs.pmoid = parent_moid
                    kwargs = api_calls(kwargs)
                    results.extend(kwargs.results)
                    moid_dict = dict(moid_dict, **kwargs.pmoids.toDict())
                kwargs.pmoids = DotMap(moid_dict)
                kwargs.results = results
            else:
                api_args = build_api_args(kwargs_keys, kwargs)
                if '?' in api_args: kwargs.api_args = api_args + '&$count=True'
                else: kwargs.api_args = api_args + '?$count=True'
                kwargs = api_calls(kwargs)
                if   re.search('expand.+HostEthIfs', api_args) and kwargs.results.Count > 100: rcount = 1001
                if   re.search('expand.+PhysicalDisks', api_args) and kwargs.results.Count > 30: rcount = 1001
                elif re.search('expand.+Processors', api_args) and kwargs.results.Count > 250: rcount = 1001
                elif re.search('expand.+Units', api_args) and kwargs.results.Count > 30: rcount = 1001
                elif re.search('expand.+Adapters', api_args) and kwargs.results.Count > 500: rcount = 1001
                else: rcount = kwargs.results.Count
                if rcount <= 100:
                    kwargs.api_args = api_args
                    kwargs = api_calls(kwargs)
                elif rcount > 100 and rcount <= 1000:
                    if '?' in api_args: kwargs.api_args = api_args + '&$top=1000'
                    else: kwargs.api_args = api_args + '?$top=1000'
                    kwargs = api_calls(kwargs)
                elif rcount > 1000:
                    if   re.search('expand.+HostEthIfs', api_args):    get_count = kwargs.results.Count; top_count = kwargs.results.Count // 10
                    elif re.search('expand.+PhysicalDisks', api_args): get_count = kwargs.results.Count; top_count = kwargs.results.Count // 24
                    elif re.search('expand.+Processors', api_args):    get_count = kwargs.results.Count; top_count = kwargs.results.Count // 4
                    elif re.search('expand.+Units', api_args):         get_count = kwargs.results.Count; top_count = kwargs.results.Count // 32
                    elif re.search('expand.+Adapters', api_args):      get_count = kwargs.results.Count; top_count = kwargs.results.Count // 4
                    else: get_count = rcount; top_count = 1000
                    moid_dict    = {}
                    offset_count = 0
                    results      = []
                    while get_count > 0:
                        if '?' in api_args: kwargs.api_args = api_args + f'&$top={top_count}&$skip={offset_count}'
                        else: kwargs.api_args = api_args + f'?$top={top_count}&$skip={offset_count}'
                        kwargs = api_calls(kwargs)
                        results.extend(kwargs.results)
                        moid_dict    = dict(moid_dict, **kwargs.pmoids.toDict())
                        get_count    = get_count - top_count
                        offset_count = offset_count + top_count
                    kwargs.pmoids  = DotMap(moid_dict)
                    kwargs.results = results
        else:
            kwargs.api_args = ''
            kwargs          = api_calls(kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        for e in ['api_filter', 'build_skip', 'expand', 'order_by']:
            if e in kwargs_keys: kwargs.pop(e)
        return kwargs

    #=========================================================================
    # Function - Chassis Inventory - Equipment
    #=========================================================================
    def chassis_equipment(self, kwargs):
        kwargs = kwargs | DotMap(expand = 'Fanmodules,Psus', method = 'get', order_by = 'Dn', uri = 'equipment/Chasses')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('registered_device').calls(kwargs)
        for e in kwargs.results:
            kwargs.chassis[e.Moid] = DotMap(
                chassis_id = e.ChassisId, chassis_name = e.Name, contract = None, domain = e.RegisteredDevice.Moid, dn = e.Dn,
                expander_modules = [DotMap(), DotMap()], fan_modules = [], hardware_moid = e.Moid, io_modules = [DotMap(), DotMap()],
                management_mode = e.ManagementMode, model = e.Model, moid = 'None', name = 'Unassigned', organization = 'default',
                power_supplies = [], serial = e.Serial, slot = DotMap({str(x):'Open' for x in range(1,9)}))
            fan_modules, power_supplies = api.inventory_fans_psus(element=e)
            fan_modules    = sorted(fan_modules, key=lambda ele: ele.dn)
            power_supplies = sorted(power_supplies, key=lambda ele: ele.dn)
            kwargs.chassis[e.Moid].fan_modules    = fan_modules
            kwargs.chassis[e.Moid].power_supplies = power_supplies
            if kwargs.domains[e.RegisteredDevice.Moid].type == 'UCSFI':
                kwargs.chassis[e.Moid].moid = 'N/A'
                kwargs.chassis[e.Moid].name = e.Dn
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Chassis Inventory - IFM/IOMs - Expander Modules / X-Fabric
    #=========================================================================
    def chassis_io_cards(self, kwargs):
        #=========================================================================
        # Expander Modules / X-Fabric
        #=========================================================================
        kwargs_keys = list(kwargs.keys())
        if 'api_filter' in kwargs_keys: api_filter = deepcopy(kwargs.api_filter); kwargs.api_filter = api_filter
        kwargs = kwargs | DotMap(expand = 'Fanmodules', method = 'get', uri = 'equipment/ExpanderModules')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('expander_modules').calls(kwargs)
        for e in kwargs.results:
            edict = DotMap(); indx = e.ModuleId - 1
            for d in ['Dn', 'FanModules', 'Moid', 'Model', 'OperState', 'OperReason', 'Serial']: key = snakecase(d); edict[key] = e[d]
            fan_modules, power_supplies = api.inventory_fans_psus(element=e)
            edict.fan_modules = sorted(fan_modules, key=lambda ele: ele.dn)
            edict = ezfunctions.dictionary_cleanup(edict)
            kwargs.chassis[e.EquipmentChassis.Moid].expander_modules[indx] = edict
        for k in list(kwargs.chassis.keys()):
            if len(kwargs.chassis[k].expander_modules[0].toDict()) == 0: kwargs.chassis[k].expander_modules = None
        #=========================================================================
        # IO Modules - IFM/IOMs
        #=========================================================================
        if 'api_filter' in kwargs_keys: kwargs.api_filter = api_filter
        kwargs = kwargs | DotMap(expand = 'AcknowledgedPeerInterface,FanModules,NetworkPorts', uri = 'equipment/IoCards')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('io_cards').calls(kwargs)
        for e in kwargs.results:
            edict = DotMap(); indx = ord(e.ConnectionPath) - 65
            for d in ['Dn', 'FanModules', 'Moid', 'NetworkPorts', 'OperState', 'OperReason', 'Model', 'Serial']: key = snakecase(d); edict[key] = e[d]
            edict.network_ports = []
            fan_modules, power_supplies = api.inventory_fans_psus(element=e)
            edict.fan_modules = sorted(fan_modules, key=lambda ele: ele.dn)
            kwargs.chassis[e.EquipmentChassis.Moid].io_modules[indx] = edict
        domain_serials = DotMap()
        for k,v in kwargs.domains.items():
            for x in range(1,3): domain_serials[v.serial[x-1]] = v.name + '-' + chr(ord('@')+x)
        if 'api_filter' in kwargs_keys: kwargs.api_filter = api_filter
        kwargs = kwargs | DotMap(build_skip = True, expand = 'AcknowledgedPeerInterface', uri = 'ether/NetworkPorts')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('host_ports').calls(kwargs)
        for e in kwargs.results:
            if e.AcknowledgedPeerInterface != None:
                peer = e.AcknowledgedPeerInterface
                edict = dict()
                for d in ['PortId', 'Speed']: key = snakecase(d); edict[key] = e[d]
                for d in ['NetworkPort', 'OperState', 'TransceiverType']: key = snakecase(d); edict[key] = peer[d]
                serial = re.search('switch-([A-Z0-9]+)/', peer.Dn).group(1)
                dname = domain_serials[serial]
                edict['network_port'] = f'{dname}-Eth{peer.SlotId}/{peer.PortId}'
                if not peer.AggregatePortId == 0: edict['network_port'] = edict['network_port'] + '/' + peer.AggregatePortId
                edict = ezfunctions.dictionary_cleanup(edict)
                kwargs.chassis[e.Ancestors[1].Moid].io_modules[e.ModuleId].network_ports.append(edict)
        for k in list(kwargs.chassis.keys()):
            for x in range(0,len(kwargs.chassis[k].io_modules)):
                kwargs.chassis[k].io_modules[x].network_ports = sorted(kwargs.chassis[k].io_modules[x].network_ports, key=lambda ele: ele['port_id'])
                kwargs.chassis[k].io_modules[x] = DotMap(kwargs.chassis[k].io_modules[x])
                edict = ezfunctions.dictionary_cleanup(kwargs.chassis[k].io_modules[x])
                kwargs.chassis[k].io_modules[x] = edict
        kwargs.chassis = DotMap(sorted(kwargs.chassis.items(), key=lambda ele: ele[1].name))
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Chassis Inventory - Chassis Profiles
    #=========================================================================
    def chassis_profiles(self, kwargs):
        kwargs = kwargs | DotMap(method = 'get', uri = kwargs.ezdata['profiles.chassis'].intersight_uri)
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('chassis').calls(kwargs)
        for e in kwargs.results:
            if not e.AssignedChassis == None:
                kwargs.chassis[e.AssignedChassis.Moid] = kwargs.chassis[e.AssignedChassis.Moid] | DotMap(
                    moid = e.Moid, name = e.Name, organization = kwargs.org_names[e.Organization.Moid])
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Domain Inventory - Cluster Profiles
    #=========================================================================
    def domain_cluster_profiles(self, kwargs):
        kwargs = kwargs | DotMap(method = 'get', uri = 'fabric/SwitchClusterProfiles')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('cluster_profile').calls(kwargs)
        for e in kwargs.results:
            if kwargs.switch_profile[e.Moid].assigned == True:
                kwargs.domains[kwargs.switch_profile[e.Moid].registration] = kwargs.domains[kwargs.switch_profile[e.Moid].registration] | DotMap(
                    moid = e.Moid, name = e.Name, organization = kwargs.org_names[e.Organization.Moid])
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs
    
    #=========================================================================
    # Function - Domain Inventory - Device Registrations
    #=========================================================================
    def domain_device_registrations(self, kwargs):
        kwargs = kwargs | DotMap(method = 'get', uri = 'asset/DeviceRegistrations')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('moid_filter').calls(kwargs)
        for e in kwargs.results:
            kwargs.domains[e.Moid] = DotMap(
                contracts = DotMap(), device_hostname = e.DeviceHostname[0], fan_modules = [DotMap(),DotMap()], firmware = DotMap(),
                hardware_moids = ["", ""], management_mode = '', model = '', moid = 'None', name = 'Unassigned',
                power_supplies = [DotMap(),DotMap()], registration = e.Moid,
                organization = 'default', serial = e.Serial, type = e.PlatformType)
            if e.PlatformType == 'UCSFI':
                kwargs.domains[e.Moid].moid = 'N/A'
                kwargs.domains[e.Moid].name = e.DeviceHostname[0]
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Domain Inventory - Network Elements
    #=========================================================================
    def domain_network_elements(self, kwargs):
        kwargs = kwargs | DotMap(expand = 'Fanmodules,Psus', method = 'get', order_by = 'SwitchId', uri = 'network/Elements')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('registered_device').calls(kwargs)
        for e in kwargs.results:
            dev_reg = e.RegisteredDevice.Moid
            indx    = kwargs.domains[dev_reg].serial.index(e.Serial)
            kwargs.domains[dev_reg].firmware[e.Serial]   = kwargs.firmware[e.UcsmRunningFirmware.Moid].version
            kwargs.domains[dev_reg].hardware_moids[indx] = e.Moid
            kwargs.domains[dev_reg].management_mode      = e.ManagementMode
            kwargs.domains[dev_reg].model                = e.Model
            fan_modules, power_supplies = api.inventory_fans_psus(element=e)
            kwargs.domains[dev_reg].fan_modules[indx][e.Serial]    = fan_modules
            kwargs.domains[dev_reg].power_supplies[indx][e.Serial] = power_supplies
        kwargs.network_elements  = DotMap({e:k for k,v in kwargs.domains.items() for e in v.hardware_moids})
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Domain Inventory - Switch Profiles
    #=========================================================================
    def domain_switch_profiles(self, kwargs):
        kwargs = kwargs | DotMap(method = 'get', order_by = 'Name', uri = 'fabric/SwitchProfiles')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('switch_profiles').calls(kwargs)
        kwargs.switch_profile = DotMap()
        for e in kwargs.results:
            switch_keys = list(kwargs.switch_profile[e.SwitchClusterProfile.Moid].keys())
            if not 'assigned' in switch_keys:
                kwargs.switch_profile[e.SwitchClusterProfile.Moid] = DotMap(assigned = False)
            if e.AssignedSwitch != None:
                kwargs.switch_profile[e.SwitchClusterProfile.Moid].assigned     = True
                kwargs.switch_profile[e.SwitchClusterProfile.Moid].registration = kwargs.network_elements[e.AssignedSwitch.Moid]
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Inventory Contract Status - Chassis|Domain|Servers
    #=========================================================================
    def inventory_contracts(self, kwargs):
        kwargs_keys = list(kwargs.keys())
        if 'chassis' in kwargs_keys: edict = DotMap({f'{v.serial}':{'moid':k,'type':'chassis'} for k,v in kwargs.chassis.items()})
        if 'domains' in kwargs_keys:
            for k,v in kwargs.domains.items(): edict = DotMap({f'{v.serial[x]}':{'index':x,'moid':k,'type':'domains'} for x in range(0,len(v.serial))})
        if 'servers' in kwargs_keys: edict = DotMap({f'{v.serial}':{'moid':k,'type':'servers'} for k,v in kwargs.servers.items()})
        kwargs = kwargs | DotMap(method = 'get', uri = 'asset/DeviceContractInformations')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs      = api('contracts').calls(kwargs)
        serial_keys = list(edict.keys())
        for e in kwargs.results:
            if e.DeviceId in serial_keys:
                ddict = DotMap(); dtype = edict[e.DeviceId].type; moid  = edict[e.DeviceId].moid
                for d in ['ContractStatus', 'ContractStatusReason', 'DeviceId', 'DeviceType', 'SalesOrderNumber', 'ServiceDescription',
                          'ServiceEndDate', 'ServiceLevel']:
                    key = snakecase(d); ddict[key] = e[d]
                ddict = ezfunctions.dictionary_cleanup(ddict)
                if dtype == 'domains': kwargs[dtype][moid].contracts[edict[e.DeviceId].index] = ddict
                else: kwargs[dtype][moid].contract = ddict
        for k in list(kwargs.domains.keys()):
            empty = [True for x in range(0,len(kwargs.domains[k].contracts)) if len(kwargs.domains[k].contracts[x]) > 0]
            if len(empty) == 0: kwargs.domains[k].contracts = None
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Inventory Fan Modules - Chassis|Domain|Servers
    #=========================================================================
    def inventory_fans_psus(element):
        ekeys = list(element.keys())
        fan_modules = []
        for f in element.Fanmodules:
            ddict = DotMap()
            for d in ['Dn', 'Model', 'Moid', 'Pid', 'Revision', 'Serial', 'Sku', 'Vendor']:
                key = snakecase(d); ddict[key] = f[d]
            ddict = ezfunctions.dictionary_cleanup(ddict)
            fan_modules.append(ddict)
        power_supplies = []
        if 'Psus' in ekeys:
            for p in element.Psus:
                ddict = DotMap()
                for d in ['Dn', 'Model', 'Moid', 'OperReason', 'OperState', 'Pid', 'Serial', 'Sku', 'Vendor', 'Voltage']:
                    key = snakecase(d); ddict[key] = p[d]
                ddict = ezfunctions.dictionary_cleanup(ddict)
                power_supplies.append(ddict)
        #=====================================================================
        # return kwargs
        #=====================================================================
        return fan_modules, power_supplies

    #=========================================================================
    # Function - Build Running Firmware Inventory Dictionary
    #=========================================================================
    def running_firmware(self, kwargs):
        kwargs = kwargs | DotMap(method = 'get', uri = 'firmware/RunningFirmwares')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs          = api('firmware').calls(kwargs)
        kwargs.firmware = DotMap({e.Moid:{'version':e.Version} for e in kwargs.results})
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Server Inventory - CPUs|Memory|PCI Nodes/GPUs|Storage Controllers/Drives|TPM Chips
    #=========================================================================
    def server_children_equipment(self, kwargs):
        #=====================================================================
        # Function - Add Memory to Servers Dictionary
        #=====================================================================
        def memory_dictionary(e, kwargs):
            ekeys = deepcopy(list(e.keys()))
            if 'MaxDevices' in ekeys and re.search('\\d\\d', e.MaxDevices): max_count = int(e.MaxDevices) + 1
            else:
                dimms = []
                for d in e.Units: dimms.append(d.MemoryId)
                dimms = sorted(dimms); max_count = dimms[-1] + 1
            kwargs.servers[e.Ancestors[1].Moid].memory_inventory = DotMap({str(x):'N/A' for x in range(1,max_count)})
            for d in e.Units:
                if len(d.Pid) > 1: kwargs.servers[e.Ancestors[1].Moid].memory_inventory[str(d.MemoryId)] = d.Pid.strip()
                else: kwargs.servers[e.Ancestors[1].Moid].memory_inventory[str(d.MemoryId)] = d.Model.strip()
            return kwargs
        #=====================================================================
        # Function - Add CPUs and TPM to Servers Dictionary
        #=====================================================================
        def motherboard_dictionaries(e, kwargs):
            for d in e.Ancestors:
                if d.ObjectType == 'compute.Blade': ancestor = d.Moid; break
                elif d.ObjectType == 'compute.RackUnit': ancestor = d.Moid; break
            for d in e.EquipmentTpms:
                ddict = DotMap(active = d.ActivationStatus, model = d.Model, present = True, serial = d.Serial)
                ddict = ezfunctions.dictionary_cleanup(ddict)
                if ddict.model != 'NA':  kwargs.servers[ancestor].tpm = ddict
                else: kwargs.servers[ancestor].tpm = None
            for d in e.Processors: kwargs.servers[ancestor].processors[str(d.ProcessorId)] = d.Model
            return kwargs
        #=====================================================================
        # Function - Add PCI Nodes w/GPU's to Servers Dictionary
        #=====================================================================
        def pci_nodes_dictionaries(e, kwargs):
            ddict = DotMap(dn = e.Dn, graphics_cards = DotMap({str(x):'N/A' for x in range(1,5)}), model = e.Model,
                           moid = e.Moid, serial = e.Serial, server = e.ComputeBlade.Moid, slot = e.SlotId)
            for d in e.GraphicsCards:
                gpu = DotMap(description = d.Description, firmware = [kwargs.firmware[f.Moid] for f in d.RunningFirmware],
                             model = d.Pid, pci_slot = d.PciSlot, serial = d.Serial, vendor = d.Vendor)
                pci_slot = re.search('RISER..-SLOT(\\d)', d.PciSlot).group(1)
                ddict.graphics_cards[pci_slot] = gpu
            kwargs.servers[e.Ancestors[0].Moid].pci_node = ddict
            return kwargs
        #=====================================================================
        # Function - Add Storage Controllers/Physical Drives to Servers Dictionary
        #=====================================================================
        def storage_dictionaries(e, kwargs):
            for d in e.Ancestors:
                if d.ObjectType == 'compute.Blade': ancestor = d.Moid; break
                elif d.ObjectType == 'compute.RackUnit': ancestor = d.Moid; break
            ddict = DotMap(backup_battery_unit = None, controller_id = e.ControllerId, firmware = None, disks = None,
                           model = e.Model, moid = e.Moid, serial = e.Serial, slot = e.PciSlot, virtual_drives = None)
            if len(e.RunningFirmware) > 0: ddict.firmware = [d.Version for d in e.RunningFirmware]
            if not e.BackupBatteryUnit == None:
                b = e.BackupBatteryUnit; ddict.backup_battery_unit = DotMap(
                    capacity_in_joules = b.DesignCapacityInJoules, capacity_percentage = b.CapacitanceInPercent, charging_state = b.ChargingState,
                    current_in_amps = b.Current, serial = b.Serial, status = b.Status, temperature_high = b.IsTemperatureHigh,
                    temperature_in_celsius = b.TemperatureInCel, type = b.Type, vendor = b.Vendor, voltage = b.VoltageInVolts,
                    voltage_design = b.DesignVoltageInVolts, voltage_low = e.IsVoltageLow)
            for d in e.PhysicalDisks:
                if ddict.disks == None: ddict.disks = DotMap()
                ddict.disks[str(d.DiskId)] = DotMap(
                    disk_state = d.DiskState, firmware = [kwargs.firmware[f.Moid].version for f in d.RunningFirmware],
                    drive_state = d.DriveState, model = d.Model, pid = d.Pid, serial = d.Serial, size = d.Size, vendor = d.Vendor)
            if kwargs.servers[ancestor].storage_controllers == None: kwargs.servers[ancestor].storage_controllers = DotMap()
            kwargs.servers[ancestor].storage_controllers[e.Moid] = ddict
            return kwargs
        #=====================================================================
        # Loop thru API's for Server Inventory
        #=====================================================================
        kwargs_keys   = list(kwargs.keys())
        kwargs.method = 'get'
        if 'api_filter' in kwargs_keys: api_filter = deepcopy(kwargs.api_filter)
        for i in ['compute/Boards:boards', 'pci/Nodes:nodes', 'memory/Arrays:memory', 'storage/Controllers:storage']:
            kwargs.uri, etype = i.split(':')
            if   etype == 'boards':  kwargs.expand = 'EquipmentTpms,Processors'
            elif etype == 'memory':  kwargs.expand = 'Units'
            elif etype == 'nodes':   kwargs.expand = 'GraphicsCards'
            elif etype == 'storage': kwargs.expand = 'BackupBatteryUnit,PhysicalDisks,RunningFirmware'
            pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
            if 'api_filter' in kwargs_keys: kwargs.api_filter = api_filter
            kwargs = api(etype).calls(kwargs)
            for e in kwargs.results:
                if   etype == 'boards':  kwargs = motherboard_dictionaries(e, kwargs)
                elif etype == 'memory':  kwargs = memory_dictionary(e, kwargs)
                elif etype == 'nodes':   kwargs = pci_nodes_dictionaries(e, kwargs)
                elif etype == 'storage': kwargs = storage_dictionaries(e, kwargs)
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Server Inventory - Physical Summaries
    #=========================================================================
    def server_compute(self, kwargs):
        #=========================================================================
        # Function - Build Server Dictionary
        #=========================================================================
        def server_dictionary(e, kwargs):
            kwargs.servers[e.Moid] = DotMap(
                adapters = DotMap(), chassis = None, contract = None, domain = None, dn = e.Dn, fan_modules = [],
                graphics_cards = DotMap({str(x):'N/A' for x in range(1,9)}), hardware_moid = e.Moid,
                kvm_ip_addresses = [d.Address for d in e.KvmIpAddresses], memory_avialable = e.AvailableMemory, memory_installed = e.TotalMemory,
                memory_inventory = None, model = e.Model, moid = 'None', name = 'Unassigned', object_type = e.ObjectType, pci_node = None,
                power_supplies = [], power_state = e.OperPowerState, processors = DotMap({str(x):'N/A' for x in range(1,3)}),
                platform_type = e.PlatformType, profile = e.ServiceProfile, server_id = e.ServerId, serial = e.Serial, server_name = e.Name,
                slot = e.SlotId, storage_controllers = None, tpm = None, user_label = e.UserLabel)
            if len(e.ServiceProfile) > 0: kwargs.servers[e.Moid].profile = e.ServiceProfile
            else:
                kwargs.servers[e.Moid].profile = 'Unassigned'
            #=====================================================================
            # Function - Build Server Dictionary
            #=====================================================================
            for d in e.Adapters:
                pci_slot = ezfunctions.pci_slot(d)
                ddict    = DotMap()
                for a in ['AdapterId', 'Model', 'OperState', 'PciSlot', 'Serial']: key = snakecase(a); ddict[key] = d[a]
                ddict = ezfunctions.dictionary_cleanup(ddict)
                kwargs.servers[e.Moid].adapters[pci_slot] = ddict
            for d in e.GraphicsCards:
                ddict = DotMap()
                for a in ['Description', 'Firmware', 'OperState', 'Model', 'Serial', 'Vendor']: key = snakecase(a); ddict[key] = d[a]
                ddict.firmware = [kwargs.firmware[f.Moid] for f in d.RunningFirmware]
                ddict.model    = d.Pid
                ddict          = ezfunctions.dictionary_cleanup(ddict)
                if   e.ObjectType == 'compute.RackUnit' and d.PciSlot != '': kwargs.servers[e.Moid].graphics_cards[str(e.PciSlot)] = ddict
                elif e.ObjectType == 'compute.RackUnit': kwargs.servers[e.Moid].graphics_cards[str(e.CardId)] = ddict
                elif 'UCSB' in e.Model: kwargs.servers[e.Moid].graphics_cards[str(1)] = ddict
            gpu_check = False
            for k,v in kwargs.servers[e.Moid].graphics_cards.items():
                if not v == 'N/A': gpu_check = True
            if gpu_check == False: kwargs.servers[e.Moid].pop('graphics_cards')
            return kwargs
        #=========================================================================
        # Blade Inventory
        #=========================================================================
        kwargs_keys = list(kwargs.keys())
        if 'api_filter' in kwargs_keys: api_filter = deepcopy(kwargs.api_filter); kwargs.api_filter = api_filter
        kwargs = kwargs | DotMap(expand = 'Adapters,GraphicsCards', method = 'get', uri = 'compute/Blades')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('moid_filter').calls(kwargs)
        for e in kwargs.results:
            kwargs = server_dictionary(e, kwargs)
            for d in ['fan_modules', 'power_supplies', 'server_id']: kwargs.servers[e.Moid].pop(d)
            kwargs.servers[e.Moid].chassis = e.EquipmentChassis.Moid
            kwargs.servers[e.Moid].domain  = deepcopy(kwargs.chassis[e.EquipmentChassis.Moid].domain)
        #=========================================================================
        # Rackmount Inventory
        #=========================================================================
        if 'api_filter' in kwargs_keys: kwargs.api_filter = api_filter
        kwargs = kwargs | DotMap(expand = 'Adapters,Fanmodules,GraphicsCards,Psus', method = 'get', uri = 'compute/RackUnits')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('moid_filter').calls(kwargs)
        dkeys  = list(kwargs.domains.keys())
        for e in kwargs.results:
            kwargs = server_dictionary(e, kwargs)
            fan_modules, power_supplies = api.inventory_fans_psus(element=e)
            fan_modules    = sorted(fan_modules, key=lambda ele: ele.dn)
            power_supplies = sorted(power_supplies, key=lambda ele: ele.dn)
            kwargs.servers[e.Moid].fan_modules    = fan_modules
            kwargs.servers[e.Moid].power_supplies = power_supplies
            for d in ['chassis', 'slot']: kwargs.servers[e.Moid].pop(d)
            if e.RegisteredDevice.Moid in dkeys:
                kwargs.servers[e.Moid].domain  = e.RegisteredDevice.Moid
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Server Identies for Zoning host/igroups
    #=========================================================================
    def server_identities(self, kwargs):
        #=====================================================================
        # Attach Server Profile Moid to Dict
        #=====================================================================
        kwargs.server_profiles = DotMap(); boot_moids = []; hardware_moids = []; profile_moids = []
        for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            kwargs.server_profiles[e.hardware_moid] = e
            hardware_moids.append(e.hardware_moid)
        pcolor.Cyan(f'\n   - Pulling Server Identity Inventory for the following Server Profiles(s):')
        for k,v in kwargs.server_profiles.items(): pcolor.Cyan(f'     * Serial: {v.serial} Name: {v.name}')
        #=====================================================================
        # Get Server Profile Elements
        #=====================================================================
        kwargs = kwargs | DotMap(method = 'get', names = [v.moid for k,v in kwargs.server_profiles.items()], uri = kwargs.ezdata['profiles.server'].intersight_uri)
        kwargs = api('moid_filter').calls(kwargs)
        for e in kwargs.results:
            k = e.AssignedServer.Moid
            kwargs.server_profiles[k].boot_order = DotMap(boot_mode = '', method = '', moid = '', name = '', wwpn_targets = [])
            indx = next((index for (index, d) in enumerate(e.PolicyBucket) if d['ObjectType'] == 'boot.PrecisionPolicy'), None)
            if not indx == None:
                boot_moid = e.PolicyBucket[indx].Moid; boot_moids.append(boot_moid)
                kwargs.server_profiles[k].boot_order.moid = boot_moid
        #=====================================================================
        # Assign Boot Order Policies
        #=====================================================================
        kwargs = kwargs | DotMap(method = 'get', names = list(numpy.unique(numpy.array(boot_moids))), uri = kwargs.ezdata.boot_order.intersight_uri)
        kwargs = api('moid_filter').calls(kwargs)
        boot_moids = DotMap()
        for e in kwargs.results: boot_moids[e.Moid] = e
        for k in list(kwargs.server_profiles.keys()):
            v = kwargs.server_profiles[k]
            if len(v.boot_order.moid) > 0:
                kwargs.server_profiles[k].boot_order.boot_mode = boot_moids[v.boot_order.moid].ConfiguredBootMode
                kwargs.server_profiles[k].boot_order.enable_secure_boot = boot_moids[v.boot_order.moid].EnforceUefiSecureBoot
                org = kwargs.org_names[boot_moids[v.boot_order.moid].Organization.Moid]
                kwargs.server_profiles[k].boot_order.name = f'{org}/{boot_moids[v.boot_order.moid].Name}'
                for e in boot_moids[v.boot_order.moid].BootDevices:
                    if e.ObjectType == 'boot.San':
                        kwargs.server_profiles[k].boot_order.wwpn_targets.append(
                            DotMap(interface_name=e.InterfaceName,lun=e.Lun,slot=e.Slot,wwpn=e.Wwpn))
                    if len(kwargs.server_profiles[k].boot_order.wwpn_targets) > 0:
                        kwargs.server_profiles[k].boot_order.wwpn_targets = sorted(kwargs.server_profiles[k].boot_order.wwpn_targets, key=lambda ele: ele.interface_name)
        #=====================================================================
        # Get iSCSI | vHBA | vNIC Identifiers
        #=====================================================================
        kwargs = kwargs | DotMap(expand = 'HostEthIfs,HostFcIfs,HostIscsiIfs', method = 'get', names = hardware_moids, uri = 'adapter/Units')
        kwargs = api('ancestors').calls(kwargs)
        for e in kwargs.results:
            pci_slot = ezfunctions.pci_slot(e)
            for d in e.Ancestors:
                if re.search('compute.(Blade|RackUnit)', d.ObjectType): hw_moid = d.Moid; break
            def dict_update(a, ddict):
                key = snakecase(a)
                if 'InterfaceId' in a: key = 'host_interface_id'
                ddict[key] = d[a]
                return ddict
            for d in e.HostEthIfs:
                ddict = DotMap()
                for a in ['Dn', 'HostEthInterfaceId', 'InterfaceType', 'MacAddress', 'Name', 'OperState', 'StandbyVifId', 'VifId']: ddict = dict_update(a, ddict)
                ddict = ezfunctions.dictionary_cleanup(ddict)
                kwargs.server_profiles[hw_moid].adapters[pci_slot].eth_ifs[ddict.name] = ddict
            for d in e.HostFcIfs:
                ddict = DotMap()
                for a in ['Dn', 'HostFcInterfaceId', 'Name', 'OperState', 'VifId', 'Wwnn', 'Wwpn']: ddict = dict_update(a, ddict)
                ddict = ezfunctions.dictionary_cleanup(ddict)
                kwargs.server_profiles[hw_moid].adapters[pci_slot].fc_ifs[ddict.name] = ddict
            for d in e.HostIscsiIfs:
                ddict = DotMap()
                for a in ['Dn', 'HostIscsiInterfaceId', 'InterfaceType', 'MacAddress', 'Name', 'OperState']: ddict = dict_update(a, ddict)
                ddict = ezfunctions.dictionary_cleanup(ddict)
                kwargs.server_profiles[hw_moid].adapters[pci_slot].iscsi_ifs[ddict.name] = ddict
        #=====================================================================
        # Get IQN for Host and Add to Profile Map
        #=====================================================================
        kwargs = kwargs | DotMap(method = 'get', names = profile_moids, uri = 'iqnpool/Pools')
        kwargs = api('iqn_pool_leases').calls(kwargs)
        if len(kwargs.results) > 0:
            for k in list(kwargs.server_profiles.keys()):
                for e in kwargs.results:
                    if e.AssignedToEntity.Moid == kwargs.server_profiles[k].moid: kwargs.server_profiles[k].iqn = e.IqnId
        kwargs.server_profile = DotMap(kwargs.server_profiles)
        #=====================================================================
        # Update Wizard Setup Server Profile List
        #=====================================================================
        for k in list(kwargs.server_profiles.keys()):
            serial = kwargs.server_profiles[k].serial
            pvars  = dict(sorted(kwargs.server_profiles[k].items()))
            indx   = next((index for (index, d) in enumerate(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles) if d['serial'] == serial), None)
            if indx == None:
                kwargs.class_path = f'wizard,server_profiles'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
            else: kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[indx] = deepcopy(pvars)
        #=====================================================================
        # Return kwargs and kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Server Inventory - Server Profiles
    #=========================================================================
    def server_profiles(self, kwargs):
        server_keys = list(kwargs.servers.keys())
        kwargs = kwargs | DotMap(method = 'get', uri = kwargs.ezdata['profiles.server'].intersight_uri)
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('server_profile').calls(kwargs)
        for e in kwargs.results:
            if e.AssociatedServer != None and e.AssignedServer.Moid in server_keys:
                kwargs.servers[e.AssignedServer.Moid] = kwargs.servers[e.AssignedServer.Moid] | DotMap(
                    moid = e.Moid, name = e.Name, organization = kwargs.org_names[e.Organization.Moid])
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Server Inventory - Server Profiles
    #=========================================================================
    def server_virtual_drives(self, kwargs):
        kwargs = kwargs | DotMap(method = 'get', uri = 'storage/VirtualDrives')
        pcolor.Cyan(f'{" "*4}* Querying `{kwargs.uri}` for Inventory.')
        kwargs = api('virtual_drives').calls(kwargs)
        for e in kwargs.results:
            for d in e.Ancestors:
                if d.ObjectType == 'compute.Blade': ancestor = d.Moid; break
                elif d.ObjectType == 'compute.RackUnit': ancestor = d.Moid; break
            controller = e.StorageController.Moid
            if kwargs.servers[ancestor].storage_controllers[controller].virtual_drives == None:
                kwargs.servers[ancestor].storage_controllers[controller].virtual_drives = DotMap()
            ddict = DotMap()
            for d in ['AccessPolicy', 'ActualWriteCachePolicy', 'AvailableSize', 'BlockSize', 'Bootable', 'Dn', 'DriveCache',
                      'DriveSecurity', 'DriveState', 'IoPolicy', 'Model', 'Moid', 'Name', 'OperState', 'Presence', 'ReadPolicy',
                      'SecurityFlags', 'Size', 'StripSize', 'Type', 'VirtualDriveId']:
                ddict[snakecase(d)] = e[d]
            ddict = ezfunctions.dictionary_cleanup(ddict)
            kwargs.servers[ancestor].storage_controllers[controller].virtual_drives[ddict.virtual_drive_id] = ddict
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Get Organizations from Intersight
    #=========================================================================
    def organizations(self, kwargs):
        kwargs = kwargs | DotMap(method = 'get', names = kwargs.orgs, uri = 'resource/Groups')
        kwargs = api('resource_group').calls(kwargs)
        kwargs = kwargs | DotMap(rsg_moids = kwargs.pmoids, rsg_results = kwargs.results)
        #=====================================================================
        # Get Organization List from the API
        #=====================================================================
        kwargs = kwargs | DotMap(method = 'get', names = kwargs.orgs, uri = 'organization/Organizations')
        kwargs = api('organization').calls(kwargs)
        kwargs = kwargs | DotMap(org_moids = kwargs.pmoids, org_results = kwargs.results)
        org_keys = list(kwargs.org_moids.keys())
        for org in kwargs.orgs:
            create_rsg = False
            if org in org_keys:
                indx = next((index for (index, d) in enumerate(kwargs.org_results) if d['Name'] == org), None)
                if indx == None: create_rsg = True
                else:
                    if len(kwargs.org_results[indx].ResourceGroups) == 0 and type(kwargs.org_results[indx].SharedWithResources) == kwargs.type_none:
                        create_rsg = True
            if create_rsg == True:
                org_keys = list(kwargs.imm_dict.orgs[org].keys())
                if 'resource_group' in org_keys and len(kwargs.imm_dict.orgs[org].resource_groups) > 0:
                    for rg in kwargs.imm_dict.orgs[org].resource_groups:
                        kwargs = kwargs | DotMap(api_body = {'Description':f'{rg} Resource Group', 'Name':rg}, method = 'post', org = org, uri = 'resource/Groups')
                else:
                    kwargs = kwargs | DotMap(api_body = {'Description':f'{org} Resource Group', 'Name':org}, method = 'post', org = org, uri = 'resource/Groups')
                    kwargs = api(self.type).calls(kwargs)
                    kwargs.rsg_moids[org].moid      = kwargs.results.Moid
                    kwargs.rsg_moids[org].selectors = kwargs.results.Selectors
            if not org in org_keys:
                api_body = {'Description':f'{org} Organization','Name':org,'ResourceGroups':[{'Moid':kwargs.rsg_moids[org].moid,'ObjectType':'resource.Group'}]}
                kwargs = kwargs | DotMap(api_body = api_body, method = 'post', uri = 'organization/Organizations')
                kwargs = api(self.type).calls(kwargs)
                kwargs.org_moids[org].moid = kwargs.results.Moid
        return kwargs

#=============================================================================
# IMM Class
#=============================================================================
class imm(object):
    def __init__(self, type): self.type = type

    #=========================================================================
    # Function - Adapter Configuration Policy Modification
    #=========================================================================
    def adapter_configuration(self, api_body, item, kwargs):
        item  = item; kwargs = kwargs
        akeys = list(api_body.keys())
        edata = kwargs.ezdata.adapter_configuration.allOf[1].properties.add_vic_adapter_configuration['items'].properties
        if 'Settings' in akeys:
            for xx in range(0, len(api_body['Settings'])):
                skeys = list(api_body['Settings'][xx].keys())
                if 'DceInterfaceSettings' in skeys:
                    temp_dict = deepcopy(api_body['Settings'][xx]['DceInterfaceSettings'])
                    api_body['Settings'][xx]['DceInterfaceSettings'] = []
                    for x in range(0,4):
                        api_body['Settings'][xx]['DceInterfaceSettings'].append(
                            {'FecMode': temp_dict[f'FecMode{x}'], 'InterfaceId': x, 'ObjectType': 'adapter.DceInterfaceSettings'})
                else:
                    api_body['Settings'][xx]['DceInterfaceSettings'] = []
                    for x in range(0,4): api_body['Settings'][xx]['DceInterfaceSettings'].append(
                        {'FecMode': 'cl91', 'InterfaceId': x, 'ObjectType': 'adapter.DceInterfaceSettings'})
                for k,v in edata.items():
                    if 'enable' in k:
                        x = v.intersight_api.split(':')
                        if not x[1] in skeys: api_body['Settings'][xx][x[1]] = dict(sorted({'ObjectType':x[2],x[3]:v.default}.items()))
                skeys = list(api_body['Settings'][xx].keys())
                if api_body['Settings'][xx]['PhysicalNicModeSettings']['PhyNicEnabled'] == True:
                    for k,v in edata.items():
                        if re.search('enable_(fip|lldp|port_channel)', k):
                            x = v.intersight_api.split(':')
                            api_body['Settings'][xx][x[1]][x[3]] = False
        return api_body

    #=========================================================================
    # Function - Assign Physical Device
    #=========================================================================
    def assign_physical_device(self, api_body, kwargs):
        if self.type == 'profiles.switch': serial = api_body['SerialNumber'][kwargs.x_number - 1]
        else: serial = api_body['SerialNumber']
        if re.search(serial_regex, serial): serial_true = True
        else: serial_true = False
        if serial_true == True:
            if kwargs.serial_moids.get(serial):
                serial_moid = kwargs.serial_moids[serial].moid
                sobject     = kwargs.serial_moids[serial].object_type
            else: validating.error_serial_number(api_body['Name'], serial)
            api_body.update({f'Assigned{(self.type.split(".")[1]).capitalize()}':{'Moid':serial_moid, 'ObjectType':sobject}})
            api_body = dict(sorted(api_body.items()))
        api_body.pop('SerialNumber')
        return api_body

    #=========================================================================
    # Function - BIOS Policy Modification
    #=========================================================================
    def bios(self, api_body, item, kwargs):
        if api_body.get('bios_template'):
            btemplate = kwargs.ezdata['bios.template'].properties
            if '-tpm' in (api_body['bios_template']).lower():
                api_body = btemplate.tpm.toDict() | btemplate[(item.bios_template.replace('-tpm', '')).replace('-Tpm', '')].toDict() | api_body
                #api_body = dict(api_body, **btemplate[(item.bios_template.replace('-tpm', '')).replace('-Tpm', '')].toDict(), **btemplate.tpm.toDict())
            else:
                api_body = btemplate.tpm_disabled.toDict() | btemplate[item.bios_template].toDict() | api_body
                #api_body = dict(api_body, **btemplate[item.bios_template].toDict(), **btemplate.tpm_disabled.toDict())
            api_body.pop('bios_template')
        return api_body

    #=========================================================================
    # Function - Boot Order Policy Modification
    #=========================================================================
    def boot_order(self, api_body, item, kwargs):
        args = DotMap(
            flex_mmc      = DotMap( Enabled = True, Subtype = "flexmmc-mapped-dvd" ),
            http_boot     = DotMap( Enabled = True,InterfaceName = "vnic0", InterfaceSource = "name", IpConfigType = "DHCP", IpType = "IPv4", MacAddress = "",
                                   Port = -1, Protocol = "HTTPS", Slot = "MLOM", Uri = ""),
            iscsi_boot    = DotMap(Enabled = True, InterfaceName = "vnic0", Port = 0, Slot = "MLOM" ),
            local_disk    = DotMap(Enabled = True, Slot = "MSTOR-RAID" ),
            nvme          = DotMap(Enabled = True),
            pch_storage   = DotMap(Enabled = True, Lun = 0 ),
            pxe_boot      = DotMap(Enabled = True, InterfaceName = "vnic0", InterfaceSource = "name", IpType = "IPv4", MacAddress = "", Port = -1, Slot = "MLOM" ),
            san_boot      = DotMap(Enabled = True, InterfaceName = "vnic0", Lun = 0, Slot = "MLOM", Wwpn = "20:00:00:25:B5:00:00:00" ),
            sd_card       = DotMap(Enabled = True, Subtype = "SDCARD", Lun = 0 ),
            uefi_shell    = DotMap(Enabled = True),
            usb           = DotMap(Enabled = True, Subtype = "usb-cd" ),
            virtual_media = DotMap(Enabled = True, Subtype = "kvm-mapped-dvd" ))
        if item.get('boot_devices'):
            for x in range(0,len(api_body['BootDevices'])):
                idict = deepcopy(api_body['BootDevices'][x])
                ikeys = list(idict.keys())
                for e in list(args[idict['ObjectType']].keys()):
                    if not e in ikeys: idict[e] = args[idict['ObjectType']][e]
                idict = dict(sorted(idict.items()))
                object_type = deepcopy(pascalcase(idict['ObjectType'].replace('_boot', '')))
                idict['ObjectType'] = f'boot.{object_type}'
                api_body['BootDevices'][x] = idict
        return api_body

    #=========================================================================
    # Function - Add Attributes to the api_body
    #=========================================================================
    def build_api_body(self, api_body, idata, item, kwargs):
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        for k, v in item.items():
            kkey = idata[k].intersight_api
            # print(json.dumps(idata, indent=4))
            #print(k, v)
            if re.search('boolean|string|integer', idata[k].type):
                if '$ref:' in kkey:
                    x = kkey.split(':')
                    if not api_body.get(x[1]): api_body.update({x[1]:{x[3]:v, 'ObjectType':x[2]}})
                    elif not api_body[x[1]].get(x[3]): api_body[x[1]].update({x[3]:v})
                elif '$pbucket:' in kkey:
                    if not api_body.get('PolicyBucket'): api_body['PolicyBucket'] = []
                    x = kkey.split(':')
                    api_body['PolicyBucket'].append({x[2]:v,'policy':k,'ObjectType':x[1]})
                else: api_body.update({kkey:v})
            elif idata[k].type == 'array':
                item_key = idata[k]['items'].intersight_api
                if re.search('boolean|string|integer',  idata[k]['items'].type):
                    if '$ref:' in item_key:
                        x = item_key.split(':')
                        if not api_body.get(x[1]): api_body.update({x[1]:{'ObjectType':x[2]}})
                        api_body[x[1]].update({x[3]:v})
                    elif '$pbucket:' in idata[k].intersight_api:
                        if not api_body.get('PolicyBucket'): api_body['PolicyBucket'] = []
                        x = idata[k].intersight_api.split(':')
                        api_body['PolicyBucket'].append({x[2]:v,'policy':k,'ObjectType':x[1]})
                    else:
                        api_body[item_key] = []
                        for e in v: api_body[item_key].append(e)
                else:
                    api_body[item_key] = []
                    for e in v:
                        if type(e) == str: api_body[item_key].append(e)
                        else:
                            idict = {'ObjectType':idata[k]['items'].object_type}
                            for a, b in idata[k]['items'].properties.items():
                                if re.search('boolean|string|integer', b.type):
                                    if a in e and '$ref:' in b.intersight_api:
                                        x = b.intersight_api.split(':')
                                        if not idict.get(x[1]): idict.update({x[1]:{x[3]:e[a], 'ObjectType':x[2]}})
                                    elif a in e: idict.update({b.intersight_api:e[a]})
                                elif b.type == 'object' and a in e:
                                    idict.update({b.intersight_api:{'ObjectType':b.object_type}})
                                    for c, d in b.properties.items():
                                        if e[a].get(c): idict[b.intersight_api].update({d.intersight_api:e[a][c]})
                                elif b.type == 'array' and a in e:
                                    if not re.search('(l|s)an_connectivity|firmware|port|storage', self.type):
                                        pcolor.Cyan(f'\n++{"-"*108}\n\n{k}\n{a}\n{b}\n{e[c]}')
                                        pcolor.Red(f'!!! ERROR !!! undefined mapping for array in array: `{d.type}`')
                                        pcolor.Cyan(f'{self.type}\n\n++{"-"*108}\n\n')
                                        len(False); sys.exit(1)
                                    idict[b.intersight_api] = e[a]
                            idict = dict(sorted(idict.items()))
                            api_body[item_key].append(idict)
            elif idata[k].type == 'object':
                vkeys = list(v.keys())
                if not api_body.get(kkey):
                    api_body[kkey] = {'ObjectType':idata[k].object_type}
                for a, b in v.items():
                    bdata = idata[k].properties[a]
                    if a in vkeys and bdata.type == 'array':
                        if re.search('pci_(links|order)|slot_ids|switch_ids|uplink_ports', a):
                            api_body[kkey].update({bdata.intersight_api:b})
                        else:
                            api_body[kkey].update({bdata.intersight_api:[]})
                            idict = {'ObjectType':bdata.object_type}
                            for e in b:
                                for c,d in bdata['items'].properties.items():
                                    if d.type == 'string' and e.get(c):
                                        idict.update({d.intersight_api:e[c]})
                                        api_body[kkey][b.intersight_api].append(idict)
                                    else:
                                        pcolor.Cyan(f'\n{"-"*108}\n\n')
                                        pcolor.Cyan(f'---\n{c}\n---\n{d}\n---\n{e}\n---\n{e[c]}')
                                        pcolor.Cyan(f'{c}\n{d}\n{e}\n{e[c]}')
                                        pcolor.Red(f'!!! ERROR !!! undefined mapping for array in object: `{d.type}`.   isight.py line 1261')
                                        pcolor.Cyan(f'\n{"-"*108}\n\n')
                                        len(False); sys.exit(1)
                    elif a in vkeys and bdata.type == 'object':
                        akeys = list(api_body[kkey].keys())
                        if idata[k].properties[a].type == 'object':
                            if not idata[k].properties[a].intersight_api in akeys:
                                api_body[kkey][bdata.intersight_api] = {'ObjectType':bdata.object_type}
                            okeys2 = list(b.keys())
                            for c,d in bdata.properties.items():
                                if re.search('boolean|integer|string', d.type) and c in okeys2:
                                    api_body[kkey][bdata.intersight_api].update({bdata.properties[c].intersight_api:b[c]})
                                elif re.search('boolean|integer|string', d.type):
                                    api_body[kkey][bdata.intersight_api].update(
                                        {bdata.properties[c].intersight_api:bdata.properties[c].default})
                                else:
                                    pcolor.Cyan(f'\n{"-"*108}\n\n')
                                    pcolor.Cyan(f'---\n{c}\n---\n{d}\n---\n{b[c]}')
                                    pcolor.Red(f'!!! ERROR !!! undefined mapping for array in object: `{d.type}`.   isight.py line 1282')
                                    pcolor.Cyan(f'\n{"-"*108}\n\n')
                                    len(False); sys.exit(1)
                        else: api_body[kkey].update({bdata.intersight_api:b})
                    elif a in vkeys: api_body[kkey].update({bdata.intersight_api:b})
                    elif re.search('boolean|integer|string', b.type): api_body[kkey][bdata.intersight_api] = bdata.default
                    else:
                        pcolor.Cyan(f'\n{"-"*108}\n\n')
                        pcolor.Cyan(f'---\n{k}\n---\n{a}\n---\n{b}\n---\n{v}')
                        pcolor.Red('!!! ERROR !!! undefined mapping for object in object.   isight.py line 1291')
                        pcolor.Cyan(f'\n{"-"*108}\n\n')
                        len(False); sys.exit(1)
                api_body[idata[k].intersight_api] = dict(sorted(api_body[idata[k].intersight_api].items()))
        #=====================================================================
        # Validate all Parameters are String if BIOS
        #=====================================================================
        if self.type == 'bios':
            for k, v in api_body.items():
                if type(v) == int or type(v) == float: api_body[k] = str(v)
        #=====================================================================
        # Add Policy Specific Settings
        #=====================================================================
        if re.fullmatch(policy_specific_regex, self.type): api_body = eval(f'imm(self.type).{self.type}(api_body, item, kwargs)')
        plist1 = [
            'pc_appliances', 'pc_ethernet_uplinks', 'pc_fc_uplinks', 'pc_fcoe_uplinks', 'port_modes',
            'rl_appliances', 'rl_ethernet_uplinks', 'rl_fc_storage', 'rl_fc_uplinks', 'rl_fcoe_uplinks', 'rl_servers',
            'drive_groups', 'ldap_groups', 'ldap_servers', 'users', 'vhbas', 'vlans', 'vnics', 'vsans']
        pop_list = []
        for e in plist1: pop_list.append((e.replace('pc_', 'port_channel_')).replace('rl_', 'port_role_'))
        for e in pop_list:
            if api_body.get(e): api_body.pop(e)
        #=====================================================================
        # Attach Organization Map, Tags, and return Dict
        #=====================================================================
        api_body = imm(self.type).org_map(api_body, kwargs.org_moids[kwargs.org].moid)
        if not api_body.get('Tags'): api_body['Tags'] = [(DotMap(e)).toDict() for e in kwargs.ez_tags]
        else:
            tags = []
            for e in kwargs.ez_tags:
                for x in range (0,len(api_body['Tags'])):
                    if e['Key'] == api_body['Tags'][x]['Key'] and e['Value'] == api_body['Tags'][x]['Value']: pass
                    elif e['Key'] == api_body['Tags'][x]['Key']: api_body['Tags'][x]['Value'] = e.Value
                    else: tags.append(e.toDict())
            if len(tags) > 0: api_body['Tags'].extend(tags)
        api_body = dict(sorted(api_body.items()))
        if api_body.get('Description'):
            if api_body['Name'] in api_body['Description']: api_body['Description'].replace(api_body['Name'], f"{np}{api_body['Name']}{ns}")
        if not re.search('DriveGroups|EndPointUser|LdapGroups|vlan|vnic|vsan', api_body['ObjectType']):
            if api_body.get('Name'): api_body['Name'] = f"{np}{api_body['Name']}{ns}"
        #print(json.dumps(api_body, indent=4))
        return api_body

    #=========================================================================
    # Function - Bulk API Request Body
    #=========================================================================
    def bulk_request(self, kwargs):
        def post_to_api(kwargs):
            kwargs = kwargs | DotMap(method = 'post', uri = 'bulk/Requests')
            kwargs = api('bulk_request').calls(kwargs)
            return kwargs
        def loop_thru_lists(kwargs):
            if len(kwargs.api_body['Requests']) > 99:
                requests_list = deepcopy(kwargs.api_body['Requests'])
                chunked_list = list(); chunk_size = 100
                for i in range(0, len(requests_list), chunk_size):
                    chunked_list.append(requests_list[i:i+chunk_size])
                for i in chunked_list:
                    kwargs.api_body['Requests'] = i
                    kwargs = post_to_api(kwargs)
            else: kwargs = post_to_api(kwargs)
            return kwargs
        #=====================================================================
        # Create API Body for Bulk Request
        #=====================================================================
        patch_list = []
        post_list  = []
        for e in kwargs.bulk_list:
            if e.get('pmoid'):
                tmoid = e['pmoid']
                e.pop('pmoid')
                patch_list.append({
                    'Body':e, 'ClassId':'bulk.RestSubRequest', 'ObjectType':'bulk.RestSubRequest', 'TargetMoid': tmoid,
                    'Uri':f'/v1/{kwargs.uri}', 'Verb':'PATCH'})
            else:
                post_list.append({
                    'Body':e, 'ClassId':'bulk.RestSubRequest', 'ObjectType':'bulk.RestSubRequest', 'Uri':f'/v1/{kwargs.uri}', 'Verb':'POST'})
        if len(patch_list) > 0:
            kwargs.api_body = {'Requests':patch_list}
            kwargs = loop_thru_lists(kwargs)
        if len(post_list) > 0:
            kwargs.api_body = {'Requests':post_list}
            kwargs = loop_thru_lists(kwargs)
        return kwargs

    #=========================================================================
    # Function - Add Organization Key Map to Dictionaries
    #=========================================================================
    def compare_body_result(self, api_body, result):
        none_type = type(None)
        pindex    = False
        rkeys     = list(result.keys())
        if api_body.get('PolicyBucket'):
            api_body['PolicyBucket'] = sorted(api_body['PolicyBucket'], key=lambda ele: ele['ObjectType'])
            result['PolicyBucket']   = sorted(result['PolicyBucket'], key=lambda ele: ele['ObjectType'])
        patch_return = False
        for k, v in api_body.items():
            if type(v) == dict:
                for a,b in v.items():
                    if type(b) == list:
                        count = 0
                        for e in b:
                            if type(e) == dict:
                                for c,d in e.items():
                                    if len(result[k][a]) - 1 < count:
                                        if pindex == True: pcolor.Yellow('Index 11')
                                        patch_return = True
                                    elif not result[k][a][count][c] == d:
                                        if pindex == True: pcolor.Yellow('Index 12')
                                        patch_return = True
                            else:
                                if len(result[k][a]) - 1 < count:
                                    if pindex == True: pcolor.Yellow('Index 13')
                                    patch_return = True
                                elif not result[k][a][count] == e:
                                    if pindex == True: pcolor.Yellow('Index 14')
                                    patch_return = True
                    else:
                        if not k in rkeys:
                            if pindex == True: pcolor.Yellow('Index 15')
                            patch_return = True
                        elif type(result[k]) == none_type:
                            if pindex == True: pcolor.Yellow('Index 16')
                            patch_return = True
                        else: 
                            kkeys = list(result[k].keys())
                            if   not a in kkeys:
                                if pindex == True: pcolor.Yellow('Index 17')
                                patch_return = True
                            elif not result[k][a] == b:
                                if pindex == True: pcolor.Yellow('Index 18')
                                patch_return = True
            elif k == 'Tags':
                for e in v:
                    if not e in result[k]:
                        if pindex == True: pcolor.Yellow('Index 19')
                        patch_return = True
            elif type(v) == list:
                count = 0
                for e in v:
                    if type(e) == dict:
                        for a,b in e.items():
                            if type(b) == dict:
                                for c,d in b.items():
                                    if len(result[k]) - 1 < count:
                                        if pindex == True: pcolor.Yellow('Index 20')
                                        patch_return = True
                                    elif not result[k][count][a][c] == d:
                                        if pindex == True: pcolor.Yellow('Index 21')
                                        patch_return = True
                            elif type(b) == list:
                                scount = 0
                                for s in b:
                                    if type(s) == dict:
                                        for g,h in s.items():
                                            if len(result[k]) - 1 < count:
                                                if pindex == True: pcolor.Yellow('Index 22')
                                                patch_return = True
                                            elif not result[k][count][a][scount][g] == h:
                                                if pindex == True: pcolor.Yellow('Index 23')
                                                patch_return = True
                                    scount += 1
                            else:
                                if 'Password' in a: count = count
                                elif len(result[k]) - 1 < count:
                                    if pindex == True: pcolor.Yellow('Index 24')
                                    patch_return = True
                                elif not result[k][count][a] == b:
                                    if pindex == True: pcolor.Yellow('Index 25')
                                    patch_return = True
                    elif type(e) == list:
                        pcolor.Red(e)
                        pcolor.Red('compare_body_result; not accounted for')
                        sys.exit(1)
                    else:
                        if len(result[k]) - 1 < count:
                            if pindex == True: pcolor.Yellow('Index 26')
                            patch_return = True
                        elif not result[k][count] == e:
                            if pindex == True: pcolor.Yellow('Index 27')
                            patch_return = True
                    count += 1
            else:
                if not result[k] == v:
                    if pindex == True: pcolor.Yellow('Index 28')
                    patch_return = True
        return patch_return

    #=========================================================================
    # Function: Deploy Configuration to Intersight
    #=========================================================================
    def deploy(kwargs):
        kwargs.orgs = list(kwargs.imm_dict.orgs.keys())
        #=====================================================================
        # Create YAML Files
        #=====================================================================
        orgs = kwargs.orgs
        ezfunctions.create_yaml(orgs, kwargs)
        #=====================================================================
        # Build Lists from ezdata
        #=====================================================================
        kwargs.policies_list  = []
        kwargs.pools_list     = []
        kwargs.profiles_list  = ['domain', 'chassis', 'server']
        kwargs.templates_list = kwargs.profiles_list
        for k, v in kwargs.ezdata.items():
            if v.intersight_type == 'policies' and not '.' in k: kwargs.policies_list.append(k)
            elif v.intersight_type == 'pools' and not '.' in k: kwargs.pools_list.append(k)
        iboot_index = kwargs.policies_list.index('iscsi_boot')
        for e in ['vnic_template', 'vhba_template', 'iscsi_static_target']:
            kwargs.policies_list.remove(e)
            kwargs.policies_list.insert(iboot_index, e)
        #=====================================================================
        # Pools/Policies/Profiles/Templates
        #=====================================================================
        for e in ['pools', 'policies', 'templates', 'profiles']:
            for ptype in kwargs[f'{e}_list']:
            #for ptype in kwargs[f'{e}_list']:
                for org in orgs:
                    kwargs.org = org
                    pkeys = list(kwargs.imm_dict.orgs[org][e].keys())
                    if ptype in pkeys:
                        if   e == 'templates': kwargs = eval(f"imm(f'templates.{ptype}').profiles(kwargs)")
                        elif e == 'profiles':  kwargs = eval(f"imm(f'profiles.{ptype}').profiles(kwargs)")
                        else: kwargs = eval(f"imm(ptype).{e}(kwargs)")
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function: Deploy Chassis Profiles to Intersight
    #=========================================================================
    def deploy_chassis(kwargs):
        kwargs.orgs = list(kwargs.imm_dict.orgs.keys())
        #=====================================================================
        # Create YAML Files
        #=====================================================================
        orgs = kwargs.orgs
        ezfunctions.create_yaml(orgs, kwargs)
        #=====================================================================
        # Profiles/Templates
        #=====================================================================
        kwargs.profiles_list  = ['chassis']
        for e in ['profiles']:
            for ptype in kwargs[f'{e}_list']:
                for org in orgs:
                    kwargs.org = org
                    pkeys = list(kwargs.imm_dict.orgs[org][e].keys())
                    if ptype in pkeys:
                        kwargs = eval(f"imm(f'profiles.{ptype}').profiles(kwargs)")
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Assign Drive Groups to Storage Policies
    #=========================================================================
    def drive_groups(self, kwargs):
        kwargs.bulk_list = []; kwargs.names = []
        ezdata = kwargs.ezdata[self.type]
        np, ns = ezfunctions.name_prefix_suffix('storage', kwargs)
        #=====================================================================
        # Get Storage Policies
        #=====================================================================
        for e in kwargs.policies:
            ekeys = list(e.keys()); spolicy = np + e.name + ns
            if 'drive_groups' in ekeys: kwargs.names.append(kwargs.isight[kwargs.org].policies['storage'][spolicy])
        if len(kwargs.names) > 0:
            kwargs = kwargs | DotMap(method = 'get', parent = 'StoragePolicy', uri = kwargs.ezdata[self.type].intersight_uri)
            kwargs = api('parent_moids').calls(kwargs)
            drive_groups = DotMap(); storage = DotMap()
            for k,v in kwargs.isight[kwargs.org].policies['storage'].items(): storage[v] = k
            for e in kwargs.results:
                drive_groups[storage[e.StoragePolicy.Moid]][e.Name] = e
        #=====================================================================
        # Function - Create API Body for Storage Drive Groups
        #=====================================================================
        def drive_group_function(storage, d, kwargs):
            e = storage; storage_policy = np + e.name + ns
            storage_moid = kwargs.isight[kwargs.org].policies['storage'][storage_policy]
            api_body     = {'ObjectType':ezdata.object_type}
            api_body     = imm(self.type).build_api_body(api_body, ezdata.properties, d, kwargs)
            api_body.pop('Organization')
            api_body.update({'StoragePolicy':{'Moid':storage_moid,'ObjectType':'storage.StoragePolicy'}})
            for x in range(0,len(api_body['VirtualDrives'])):
                vd = api_body['VirtualDrives'][x]
                if not vd.get('VirtualDrivePolicy'):
                    vd['VirtualDrivePolicy'] = {'ObjectType':'storage.VirtualDrivePolicy'}
                else: vd['VirtualDrivePolicy'].update({'ObjectType':'storage.VirtualDrivePolicy'})
                vp = vd['VirtualDrivePolicy']
                for k,v in kwargs.ezdata['storage.virtual_drive_policy'].properties.items():
                    if not vp.get(v.intersight_api): vp[v.intersight_api] = v.default
            #=================================================================
            # Add api_body to bulk_list if necessary
            #=================================================================
            if not drive_groups[storage_policy].get(d.name): kwargs.bulk_list.append(deepcopy(api_body))
            else:
                patch_policy      = imm(self.type).compare_body_result(api_body, drive_groups[storage_policy][d.name])
                api_body['pmoid'] = drive_groups[storage_policy][d.name].Moid
                if patch_policy == True: kwargs.bulk_list.append(deepcopy(api_body))
                else:
                    pcolor.Cyan(f'{" "*6}* Skipping Org: {kwargs.org}; {parent_type}: `{storage_policy}`, DriveGroup: `{d.name}`.'\
                        f'  Intersight Matches Configuration.  Moid: {drive_groups[storage_policy][d.name].Moid}')
            return kwargs
        #=====================================================================
        # Create API Body for Storage Drive Groups
        #=====================================================================
        parent_type = 'Storage Policy'
        for e in kwargs.policies:
            ekeys = list(e.keys())
            if 'drive_groups' in ekeys:
                for d in e.drive_groups: kwargs = drive_group_function(e, d, kwargs)
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        kwargs.parent_key = 'storage'
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Drive Security Policy Modification
    #=========================================================================
    def drive_security(self, api_body, item, kwargs):
        api_body['RemoteKey']['ServerCertificate'] = base64.b64encode(str.encode(kwargs.var_value)).decode()
        akeys = list(api_body.keys())
        item  = item; kwargs = kwargs
        api_body['KeySettings'] = {}
        if 'ManualKey' in akeys:
            ekeys = list(api_body['ManualKey'].keys())
            for e in ['ExistingKey', 'NewKey']:
                if e in ekeys:
                    if 'New' in e: kwargs.sensitive_var = f"drive_security_new_security_key_passphrase"
                    else: kwargs.sensitive_var = f"drive_security_current_security_key_passphrase"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    api_body['ManualKey'][e] = kwargs.var_value
            api_body['KeySettings']['ManualKey'] = api_body['ManualKey']
            api_body.pop('ManualKey')
        elif 'RemoteKey' in akeys:
            ekeys = list(api_body['RemoteKey'].keys())
            if 'AuthCredentials' in ekeys:
                if len(api_body['RemoteKey']['AuthCredentials']['Username']) > 0:
                    kwargs.sensitive_var = f"drive_security_current_security_key_passphrase"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    api_body['RemoteKey']['AuthCredentials']['Password'] = kwargs.var_value
            kwargs.sensitive_var = f"drive_security_server_ca_certificate"
            kwargs    = ezfunctions.sensitive_var_value(kwargs)
            var_value = ezfunctions.key_file_check('drive_security_server_ca_certificate', kwargs.var_value, kwargs)
            api_body['RemoteKey']['ServerCertificate'] = base64.b64encode(str.encode(var_value)).decode()
            for e in ['AuthCredentials', 'NewKey']:
                if e in ekeys:
                    if 'New' in e: kwargs.sensitive_var = f"drive_security_new_security_key_passphrase"
                    else: kwargs.sensitive_var = f"drive_security_current_security_key_passphrase"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    api_body['RemoteKey'][e] = kwargs.var_value
            api_body['KeySettings']['RemoteKey'] = api_body['RemoteKey']
            api_body.pop('RemoteKey')
        print(json.dumps(api_body, indent=4)); exit()
        return api_body

    #=========================================================================
    # Function - Ethernet Adapter Policy Modification
    #=========================================================================
    def ethernet_adapter(self, api_body, item, kwargs):
        if api_body.get('adapter_template'):
            atemplate= kwargs.ezdata['ethernet_adapter.template'].properties
            api_body  = dict(api_body, **atemplate[item.adapter_template].toDict())
            api_body.pop('adapter_template')
        if api_body.get('RssHashSettings'):
            if api_body['RssHashSettings'].get('Enable'):
                api_body['RssSettings'] = api_body['RssHashSettings']['Enable']
                api_body['RssHashSettings'].pop('Enable')
        return api_body

    #=========================================================================
    # Function - Ethernet Network Policy Modification
    #=========================================================================
    def ethernet_network(self, api_body, item, kwargs):
        ikeys = list(item.keys())
        if 'qinq_vlan' in ikeys:
            if re.search('[0-1]', str(item.qinq_vlan)): api_body['VlanSettings']['QinqVlan'] = 2
            else: api_body['VlanSettings']['QinqVlan']['QinqEnabled'] = True
        return api_body

    #=========================================================================
    # Function - Ethernet Network Group Policy Modification
    #=========================================================================
    def ethernet_network_group(self, api_body, item, kwargs):
        ikeys = list(item.keys())
        if 'qinq_vlan' in ikeys:
            if re.search('[0-1]', str(item.qinq_vlan)): api_body['VlanSettings']['QinqVlan'] = 2
            else: api_body['VlanSettings']['QinqVlan']['QinqEnabled'] = True
        return api_body

    #=========================================================================
    # Function - Fibre-Channel Adapter Policy Modification
    #=========================================================================
    def fibre_channel_adapter(self, api_body, item, kwargs):
        if api_body.get('adapter_template'):
            atemplate= kwargs.ezdata['fibre_channel_adapter.template'].properties
            api_body  = dict(api_body, **atemplate[item.adapter_template].toDict())
            api_body.pop('adapter_template')
        return api_body

    #=========================================================================
    # Function - Fibre-Channel Network Policies Policy Modification
    #=========================================================================
    def firmware(self, api_body, item, kwargs):
        item = item; kwargs = kwargs
        if api_body.get('ExcludeComponentList'):
            api_body['ExcludeComponentList'] = [e for e in list(api_body['ExcludeComponentList'].keys()) if api_body['ExcludeComponentList'][e] == True]
        if api_body.get('ModelBundleCombo'):
            combos = deepcopy(api_body['ModelBundleCombo']); api_body['ModelBundleCombo'] = []
            for e in combos:
                for i in e['ModelFamily']:
                    idict = deepcopy(e); idict['ModelFamily'] = i
                    api_body['ModelBundleCombo'].append(idict)
            api_body['ModelBundleCombo'] = sorted(api_body['ModelBundleCombo'], key=lambda ele: ele['BundleVersion'])
        api_body = dict(sorted(api_body.items()))
        return api_body

    #=========================================================================
    # Function - Validate CCO Authorization
    #=========================================================================
    def firmware_authenticate(self, kwargs):
        for e in ['cco_password', 'cco_user']:
            if os.environ.get(e) == None:
                kwargs.sensitive_var = e
                kwargs        = ezfunctions.sensitive_var_value(kwargs)
                os.environ[e] = kwargs.value
        api_body = {'ObjectType':'softwarerepository.Authorization','Password':os.environ['cco_password'],'RepositoryType':'Cisco','UserId':os.environ['cco_user']}
        kwargs   = kwargs | DotMap(api_body = api_body, method = 'post', uri = 'softwarerepository/Authorizations')
        kwargs   = api('firmware_authorization').calls(kwargs)
        return kwargs

    #=========================================================================
    # Function - Get Pool/Policy Moid from isight Dictionary
    #=========================================================================
    def get_moid_from_isight_dict(self, parent_name, ptype, org, pname, kwargs):
        if re.search('^(ip|iqn|mac|resource|uuid|wwnn|wwpn)$', ptype): p = 'pools'
        elif re.search('^(chassis|domain|server|switch)$', ptype): p = 'templates'
        else: p = 'policies'
        pkeys = list(kwargs.isight[org][p][ptype].keys())
        if not pname in pkeys:
            api_get(False, [f'{org}/{pname}'], ptype, kwargs)
            pkeys = list(kwargs.isight[org][p][ptype].keys())
        if not pname in pkeys: validating.error_policy_doesnt_exist(self.type, parent_name, ptype, f'{org}/{pname}')
        pmoid = kwargs.isight[org][p][ptype][pname]
        return pmoid

    #=========================================================================
    # Function - Identity Reservations
    #=========================================================================
    def identity_reservations(self, profiles, kwargs):
        #=====================================================================
        # Send Begin Notification and Load Variables
        #=====================================================================
        pcolor.LightGray(f'  {"-"*60}\n')
        pcolor.LightPurple(f'   Beginning Pool Reservations Deployments\n')
        #=====================================================================
        # Build Reservation Dictionaries
        #=====================================================================
        pool_list = ['ip', 'iqn', 'mac', 'uuid', 'wwnn', 'wwpn']
        pdict = DotMap()
        for e in pool_list:
            kwargs.ibulk_list[e]    = []
            kwargs.pools[e]         = []
            kwargs.reservations[e]  = []
            kwargs.ireservations[e] = DotMap()
            pdict[e] = []
        for e in profiles:
            if e.reservations and e.ignore_reservations != True:
                for i in e.reservations:
                    kwargs.reservations[i.identity_type].append(i.identity.upper())
                    rdict = DotMap(dict(i.toDict(), **{'profile':e.name}))
                    pdict[i.identity_type].append(rdict)
                    if len(i.pool_name) > 0:
                        org, pool = imm(i.identity_type).seperate_org_pname(i.pool_name, kwargs)
                        kwargs.pools[i.identity_type].append(f'{org}/{pool}')
        #=====================================================================
        # Get Pool Moids
        #=====================================================================
        for k, v in kwargs.pools.items():
            names  = list(numpy.unique(numpy.array(v)))
            kwargs = api_get(True, names, k, kwargs)
        #=====================================================================
        # Get Pool Leases
        #=====================================================================
        def reservation_settings(k, kwargs):
            if   'ip' in k:   kwargs.pkey = 'IpV4Address'; kwargs.uri = 'ippool/IpLeases'
            elif 'iqn' in k:  kwargs.pkey = 'IqnAddress';  kwargs.uri = 'iqnpool/Leases'
            elif 'mac' in k:  kwargs.pkey = 'MacAddress';  kwargs.uri = 'macpool/Leases'
            elif 'uuid' in k: kwargs.pkey = 'Uuid';        kwargs.uri = 'uuidpool/UuidLeases'
            else:             kwargs.pkey = 'WwnId';       kwargs.uri = 'fcpool/Leases'
            return kwargs
        for k, v in kwargs.reservations.items():
            if len(v) > 0:
                kwargs = reservation_settings(k, kwargs)
                names = list(numpy.unique(numpy.array(v)))
                if k == 'ip':
                    for e in ['IPv4', 'IPv6']:
                        if 'v4' in e: check = '.'; kwargs.pkey = 'IpV4Address'
                        else: check = ':'; kwargs.pkey = 'IpV6Address'
                        names = [d for d in names if check in d]
                        if len(names) > 0:
                            kwargs = kwargs | DotMap(method = 'get', names = names)
                            kwargs = api(f'{k}_leases').calls(kwargs)
                            kwargs.leases[k][e] = kwargs.results
                else:
                    kwargs = kwargs | DotMap(method = 'get', names = names)
                    kwargs = api(f'{k}_leases').calls(kwargs)
                    kwargs.leases[k] = kwargs.results
        #=====================================================================
        # Get Identity Reservations
        #=====================================================================
        for k, v in kwargs.reservations.items():
            if len(v) > 0:
                names = list(numpy.unique(numpy.array(v)))
                kwargs = api_get(True, names, f'{k}.reservations', kwargs)
                kwargs.reservations[k] = kwargs.pmoids
        #=====================================================================
        # Build Identity Reservations api_body
        #=====================================================================
        def build_api_body(k, e, kwargs):
            if 'ip' in e.identity_type and ':' in e.identity:
                indx = next((index for (index, d) in enumerate(kwargs.leases[k]['IPv6']) if d[f'IpV6Address'] == e.identity), None)
            elif 'ip' in e.identity_type and '.' in e.identity:
                indx = next((index for (index, d) in enumerate(kwargs.leases[k]['IPv4']) if d[f'IpV4Address'] == e.identity.upper()), None)
            else: indx = next((index for (index, d) in enumerate(kwargs.leases[k]) if d[f'{kwargs.pkey}'] == e.identity.upper()), None)
            if indx == None:
                if not e.identity.upper() in kwargs.reservations[k]:
                    org, pool = imm(e.identity_type).seperate_org_pname(e.pool_name, kwargs)
                    if len(kwargs.isight[org].pools[k][pool]) == 0: validating.error_pool_doesnt_exist(org, k, f'{org}/{pool}', e.profile)
                    if re.search('wwnn|wwpn', k): otype = 'fcpool.Pool'
                    else: otype = f'{k}pool.Pool'
                    api_body = {'Identity':e.identity.upper(), 'Pool':{'Moid':kwargs.isight[org].pools[k][pool],'ObjectType':otype}}
                    if re.search('wwnn|wwpn', k): api_body['IdPurpose'] = k.upper()
                    api_body = imm(self.type).org_map(api_body, kwargs.org_moids[org].moid)
                    if 'ip' == k:
                        if '.' in e.identity: api_body.update({'IpType':'IPv4'})
                        else:  api_body.update({'IpType':'IPv4'})
                    kwargs.ibulk_list[k].append(api_body)
                else:
                    res_moid = kwargs.reservations[k][e.identity.upper()].moid
                    kwargs.ireservations[k][e.identity].moid = res_moid
                    pcolor.Cyan(f"      * Skipping Org: {kwargs.org} > Server Profile: `{e.profile}` > {k.upper()} Reservation: {e.identity.upper()}."\
                                f"  Existing reservation: {res_moid}")
            else:
                pcolor.Yellow(f"      !!!ERROR!!! with Org: {kwargs.org} > Server Profile: `{e.profile}` > {k.upper()} Reservation: {e.identity.upper()}")
                if 'ip' in e.identity_type and ':' in e.identity: entity = kwargs.leases[k]['IPv6'][indx]['AssignedToEntity']
                elif 'ip' in e.identity_type and '.' in e.identity: entity = kwargs.leases[k]['IPv4'][indx]['AssignedToEntity']
                else: entity = kwargs.leases[k][indx]['AssignedToEntity']
                pcolor.Yellow(f"      Already assigned to {entity['ObjectType']} - Moid: {entity['Moid']}")
            return kwargs
        for k, v in pdict.items():
            if len(v) > 0:
                kwargs = reservation_settings(k, kwargs)
                for e in v: kwargs = build_api_body(k, e, kwargs)
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        for e in pool_list:
            if len(kwargs.ibulk_list[e]) > 0:
                kwargs.bulk_list = kwargs.ibulk_list[e]
                kwargs.uri       = kwargs.ezdata[f'{e}.reservations'].intersight_uri
                kwargs           = imm(self.type).bulk_request(kwargs)
                for f, g in kwargs.pmoids.items(): kwargs.ireservations[e][f].moid = g.moid
        #=====================================================================
        # Send End Notification and return kwargs
        #=====================================================================
        pcolor.LightPurple(f'\n    Completed Pool Reservations Deployments\n')
        pcolor.LightGray(f'  {"-"*60}\n')
        return kwargs

    #=========================================================================
    # Function - IMC Access Policy Modification
    #=========================================================================
    def imc_access(self, api_body, item, kwargs):
        item = item
        if not api_body.get('AddressType'): api_body.update({ 'AddressType':{ 'EnableIpV4':False, 'EnableIpV6':False }})
        api_body.update({ 'ConfigurationType':{ 'ConfigureInband': False, 'ConfigureOutOfBand': False }})
        #=====================================================================
        # Attach Pools to the API Body
        #=====================================================================
        ptype = ['InbandIpPool', 'OutOfBandIpPool']
        for i in ptype:
            if api_body.get(i):
                api_body['ConfigurationType'][f'Configure{i.split("Ip")[0]}'] = True
                org, pname = imm('ip').seperate_org_pname(api_body[i]['Moid'], kwargs)
                api_body[i]['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'ip', org, pname, kwargs)
                if i == 'InbandIpPool':
                    kwargs = api_get(False, [f'{org}/{pname}'], 'ip', kwargs)
                    if len(kwargs.results[0].IpV4Blocks) > 0: api_body['AddressType']['EnableIpV4'] = True
                    if len(kwargs.results[0].IpV6Blocks) > 0: api_body['AddressType']['EnableIpV6'] = True
        return api_body

    #=========================================================================
    # Function - IPMI over LAN Policy Modification
    #=========================================================================
    def ipmi_over_lan(self, api_body, item, kwargs):
        item = item; kwargs = kwargs
        if api_body.get('encryption_key'):
            if os.environ.get('ipmi_key') == None:
                kwargs.sensitive_var = "ipmi_key"
                kwargs = ezfunctions.sensitive_var_value(kwargs)
                api_body.update({'EncryptionKey':kwargs.var_value})
            else: api_body.update({'EncryptionKey':os.environ.get('ipmi_key')})
        return api_body

    #=========================================================================
    # Function - iSCSI Adapter Policy Modification
    #=========================================================================
    def iscsi_boot(self, api_body, item, kwargs):
        item = item
        if api_body.get('IscsiAdapterPolicy'):
            org, pname = imm('iscsi_adapter').seperate_org_pname(api_body['IscsiAdapterPolicy']['Moid'], kwargs)
            api_body['IscsiAdapterPolicy']['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'iscsi_adapter', org, pname, kwargs)
        if api_body.get('InitiatorStaticIpV4Config'):
            api_body['InitiatorStaticIpV4Address'] = api_body['InitiatorStaticIpV4Config']['IpAddress']
            api_body['InitiatorStaticIpV4Config'].pop('IpAddress')
        if api_body.get('Chap'):
            kwargs.sensitive_var = 'iscsi_boot_password'
            kwargs = ezfunctions.sensitive_var_value(kwargs)
            if api_body['authentication'] == 'mutual_chap':
                api_body['MutualChap'] = api_body['Chap']; api_body.pop('Chap')
                api_body['MutualChap']['Password'] = kwargs.var_value
            else: api_body['Chap']['Password'] = kwargs.var_value
        if api_body['authentication']: api_body.pop('authentication')
        #=====================================================================
        # Attach Pools/Policies to the API Body
        #=====================================================================
        if api_body.get('InitiatorIpPool'):
            org, pname = imm('ip').seperate_org_pname(api_body['InitiatorIpPool']['Moid'], kwargs)
            api_body['InitiatorIpPool']['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'ip', org, pname, kwargs)
        plist = ['PrimaryTargetPolicy', 'SecondaryTargetPolicy']
        for p in plist:
            if api_body.get(p):
                org, pname = imm('iscsi_static_target').seperate_org_pname(api_body[p]['Moid'], kwargs)
                api_body[p]['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'iscsi_static_target', org, pname, kwargs)
        return api_body

    #=========================================================================
    # Function - iSCSI Static Target Policy Modification
    #=========================================================================
    def iscsi_static_target(self, api_body, item, kwargs):
        item = item; kwargs = kwargs; api_body['Lun'] = {'Bootable':True}
        return api_body

    #=========================================================================
    # Function - Assign Users to Local User Policies
    #=========================================================================
    def ldap_groups(self, kwargs):
        #=====================================================================
        # Get Existing Users
        #=====================================================================
        ezdata = kwargs.ezdata[self.type]
        kwargs.group_post_list = []; kwargs.server_post_list = []; role_names = []; kwargs.cp = DotMap()
        np, ns = ezfunctions.name_prefix_suffix('ldap', kwargs)
        for i in kwargs.policies:
            if i.get('ldap_groups'):
                kwargs.parent_name = f'{np}{i.name}{ns}'
                for e in i.ldap_groups: role_names.append(e.role)
                kwargs.pmoid = kwargs.isight[kwargs.org].policies[self.type.split('.')[0]][kwargs.parent_name]
                names  = [e.name for e in i.ldap_groups]
                kwargs = api_get(True, names, self.type, kwargs)
                kwargs.cp[kwargs.pmoid].group_moids  = kwargs.pmoids
                kwargs.cp[kwargs.pmoid].group_results= kwargs.results
                kwargs.pmoid = kwargs.isight[kwargs.org].policies[self.type.split('.')[0]][kwargs.parent_name]
            if i.get('ldap_servers'):
                names  = [e.server for e in i.ldap_servers]
                kwargs = api_get(True, names, 'ldap.ldap_servers', kwargs)
                kwargs.cp[kwargs.pmoid].server_moids  = kwargs.pmoids
                kwargs.cp[kwargs.pmoid].server_results= kwargs.results
        if len(role_names) > 0:
            kwargs.names       = list(numpy.unique(numpy.array(role_names)))
            kwargs.uri         = 'iam/EndPointRoles'
            kwargs             = api('iam_role').calls(kwargs)
            kwargs.role_moids  = kwargs.pmoids
            kwargs.role_results= kwargs.results
        #=====================================================================
        # Construct API Body LDAP Policies
        #=====================================================================
        for i in kwargs.policies:
            kwargs.parent_key  = self.type.split('.')[0]
            kwargs.parent_name = f'{np}{i.name}{ns}'
            kwargs.parent_type = 'LDAP Policy'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policies[self.type.split('.')[0]][kwargs.parent_name]
            for e in i.ldap_groups:
                #=============================================================
                # Create API Body for User Role
                #=============================================================
                api_body = {'LdapPolicy':{'Moid':kwargs.parent_moid,'ObjectType':'iam.LdapPolicy'},'ObjectType':ezdata.object_type}
                api_body = imm(self.type).build_api_body(api_body, ezdata, e, kwargs)
                api_body['EndPointRole']['Moid'] = kwargs.role_moids[e.role].moid
                #=============================================================
                # Create or Patch the Policy via the Intersight API
                #=============================================================
                if kwargs.cp[kwargs.parent_moid].group_moids.get(e.name):
                    indx = next((index for (index, d) in enumerate(kwargs.cp[kwargs.parent_moid].group_results) if d['Name'] == api_body['Name']), None)
                    patch_policy = imm(self.type).compare_body_result(api_body, kwargs.cp[kwargs.parent_moid].group_results[indx])
                    api_body['pmoid'] = kwargs.cp[kwargs.parent_moid].moids[e.name].moid
                    if patch_policy == True: kwargs.group_post_list.append(deepcopy(api_body))
                    else:
                        pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {kwargs.parent_type}: `{kwargs.parent_name}`, Group: `{api_body['Name']}`."\
                            f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
                else: kwargs.group_post_list.append(deepcopy(api_body))
            for e in i.ldap_servers:
                #=============================================================
                # Create API Body for User Role
                #=============================================================
                api_body = {'LdapPolicy':{'Moid':kwargs.parent_moid,'ObjectType':'iam.LdapPolicy'},'ObjectType':kwargs.ezdata['ldap.ldap_servers'].object_type}
                api_body = imm('ldap.ldap_servers').build_api_body(api_body, ezdata, e, kwargs)
                #=============================================================
                # Create or Patch the Policy via the Intersight API
                #=============================================================
                if kwargs.cp[kwargs.parent_moid].server_moids.get(e.server):
                    indx = next((index for (index, d) in enumerate(kwargs.cp[kwargs.parent_moid].server_results) if d['Name'] == api_body['Name']), None)
                    patch_policy = imm(self.type).compare_body_result(api_body, kwargs.cp[kwargs.parent_moid].server_results[indx])
                    api_body['pmoid'] = kwargs.cp[kwargs.parent_moid].moids[e.server].moid
                    if patch_policy == True: kwargs.server_post_list.append(deepcopy(api_body))
                    else:
                        pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {kwargs.parent_type}: `{kwargs.parent_name}`, Group: `{api_body['Name']}`."\
                            f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
                else: kwargs.server_post_list.append(deepcopy(api_body))
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.group_post_list) > 0:
            kwargs.bulk_list = kwargs.group_post_list
            kwargs.uri       = ezdata.interight_uri
            kwargs           = imm(self.type).bulk_request(kwargs)
        if len(kwargs.server_post_list) > 0:
            kwargs.bulk_list = kwargs.server_post_list
            kwargs.uri       = ezdata.interight_uri
            kwargs           = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - LAN Connectivity Policy Modification
    #=========================================================================
    def lan_connectivity(self, api_body, item, kwargs):
        if not api_body.get('PlacementMode'): api_body.update({'PlacementMode':'custom'})
        if not api_body.get('TargetPlatform'): api_body.update({'TargetPlatform': 'FIAttached'})
        if api_body.get('StaticIqnName'): api_body['IqnAllocationType'] = 'Static'
        if api_body.get('IqnPool'):
            api_body['IqnAllocationType'] = 'Pool'
            org, pname = imm('iqn').seperate_org_pname(item.iqn_pool, kwargs)
            api_body['IqnPool']['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'iqn', org, pname, kwargs)
        return api_body

    #=========================================================================
    # Function - Local User Policy Modification
    #=========================================================================
    def local_user(self, api_body, item, kwargs):
        if not api_body.get('PasswordProperties'): api_body['PasswordProperties'] = {}
        ikeys = list(item.keys())
        if 'password_properties' in ikeys:
            pkeys = list(item.password_properties.keys())
            for k, v in kwargs.ezdata['local_user.password_properties'].properties.items():
                if k in pkeys: api_body['PasswordProperties'][v.intersight_api] =  item.password_properties[k]
                else: api_body['PasswordProperties'][v.intersight_api] = v.default
        else:
            for k, v in kwargs.ezdata['local_user.password_properties'].properties.items():
                api_body['PasswordProperties'][v.intersight_api] = v.default
        return api_body

    #=========================================================================
    # Function - Network Connectivity Policy Modification
    #=========================================================================
    def network_connectivity(self, api_body, item, kwargs):
        ip_versions = ['v4', 'v6']; kwargs = kwargs
        body_keys = list(api_body.keys())
        if 'dns_servers_v6' in body_keys:
            if len(api_body['dns_servers_v6']) > 0: api_body['EnableIpv6'] = True
        elif 'EnableIpv6dnsFromDhcp' in body_keys:
            if api_body['EnableIpv6dnsFromDhcp'] == True: api_body['EnableIpv6'] = True
        for i in ip_versions:
            dtype = f'dns_servers_{i}'
            if dtype in api_body:
                if len(item[dtype]) > 0: api_body.update({f'PreferredIp{i}dnsServer':item[dtype][0]})
                if len(item[dtype]) > 1: api_body.update({f'AlternateIp{i}dnsServer':item[dtype][1]})
                api_body.pop(dtype)
        return api_body

    #=========================================================================
    # Function - Add Organization Key Map to Dictionaries
    #=========================================================================
    def org_map(self, api_body, org_moid):
        api_body.update({'Organization':{'Moid':org_moid, 'ObjectType':'organization.Organization'}})
        return api_body

    #=========================================================================
    # Function - Build Policies - BIOS
    #=========================================================================
    def os_install(self, kwargs):
        #=====================================================================
        # Load Variables and Send Begin Notification
        #=====================================================================
        validating.begin_section(self.type, 'Install')
        server_profiles       = deepcopy(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles)
        install_flag          = False
        kwargs.models         = sorted(list(numpy.unique(numpy.array([e.model for e in server_profiles]))))
        kwargs.org_moid       = kwargs.org_moids[kwargs.org].moid
        os_install_fail_count = 0
        #=====================================================================
        # Get Physical Server Tags to Check for
        # Existing OS Install
        #=====================================================================
        kwargs = kwargs | DotMap(method = 'get', names = [e.serial for e in server_profiles], uri = 'compute/PhysicalSummaries')
        kwargs = api('serial_number').calls(kwargs)
        compute_moids = kwargs.pmoids
        boot_names    = []
        os_cfg_moids  = []
        for x in range(0,len(server_profiles)):
            v = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x]
            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].tags = compute_moids[server_profiles[x].serial].tags
            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].os_installed  = False
            boot_names.append(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].boot_order.name)
            os_cfg_moids.append(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].os_configuration)
            for e in compute_moids[v.serial].tags:
                if e.Key == 'os_installed' and e.Value == f'{v.os_vendor}: {v.os_version.name}':
                    kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].os_installed = True
                else: install_flag = True
            if kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].boot_volume.lower() == 'm2':
                m2_found = False
                for k,v in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].storage_controllers.items():
                    if re.search('MSTOR-RAID', v.slot):
                        m2_found = True
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].virtual_drive = v.virtual_drives['0'].name
                if m2_found == False:
                    pcolor.Red(f'\n{"-"*108}\n')
                    pcolor.Red(f'  !!! ERROR !!!\n  Could not determine the Controller Slot for:')
                    pcolor.Red(f'  * Profile: {server_profiles[x].name}')
                    pcolor.Red(f'  * Serial:  {server_profiles[x].serial}')
                    pcolor.Red(f'  Exiting... (intersight-tools/classes/isight.py Line 1448)')
                    pcolor.Red(f'\n{"-"*108}\n')
                    len(False); sys.exit(1)
        #=====================================================================
        # Setup OS Settings for ezci
        #=====================================================================
        def sensitive_list_check(sensitive_list, kwargs):
            for e in sensitive_list:
                kwargs.sensitive_var = e
                kwargs = ezfunctions.sensitive_var_value(kwargs)
                kwargs[e] = kwargs.var_value
            return kwargs
        #=====================================================================
        # Get Software Repository Data - If os_install is True
        #=====================================================================
        if install_flag == True:
            kwargs = software_repository('os_cfg').os_configuration(kwargs)
            kwargs = software_repository('scu').scu(kwargs)
            for e in kwargs.os_cfg_results: kwargs.os_cfg_moids[e.Moid] = e
            for e in kwargs.scu_results: kwargs.scu[e.Moid] = e
        #=====================================================================
        # Deployment Type Customization
        #=====================================================================
        if install_flag == True and kwargs.script_name == 'ezci' and kwargs.args.deployment_type == 'azure_stack':
            kwargs.os_version = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[0].os_version
            # kwargs = sensitive_list_check(['azure_stack_lcm_password', 'local_administrator_password'], kwargs)
            kwargs = sensitive_list_check(['local_administrator_password'], kwargs)
            kwargs = software_repository('azure_stack').os_cfg_azure_stack(kwargs)
            for x in range(0,len(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles)):
                kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].os_configuration = kwargs.os_cfg_moid
        elif install_flag == True and kwargs.script_name == 'ezci':
            kwargs = sensitive_list_check(['vmware_esxi_password'], kwargs)
        #=====================================================================
        # Install Operating System on Servers
        #=====================================================================
        count = 1
        for x in range(0,len(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles)):
            v = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x]
            if v.os_installed == False:
                #=============================================================
                # Test Intersight Transition URL
                #=============================================================
                url = kwargs.scu[v.scu].Source.LocationLink
                if kwargs.args.repository_check_skip == False: ezfunctions.test_repository_url(url)
                #=============================================================
                # Get Installation Interface
                #=============================================================
                if type(v.install_interface) == str:
                    for a,b in v.adapters.items():
                        vnic = [DotMap(name = c, mac = d.mac_address, slot = d.pci_slot) for c,d in b.eth_ifs.items() if d.mac_address == v.install_interface][0]
                if v.boot_volume.lower() == 'san':
                    if count % 2 == 0: kwargs.wwpn_index = 0; kwargs.san_target = v.boot_order.wwpn_targets[0]
                    else:
                        if len(v.boot_order.wwpn_targets) > 1: kwargs.wwpn_index = 1; kwargs.san_target = v.boot_order.wwpn_targets[1]
                        else: kwargs.wwpn_index = 0; kwargs.san_target = v.boot_order.wwpn_targets[0]
                    #kwargs.fc_ifs = [b for a,b in v.adapters[kwargs.san_target.slot].fc_ifs.items()]
                    kwargs.fc_ifs = v.adapters[kwargs.san_target.slot].fc_ifs
                    stgt = kwargs.san_target
                    pcolor.Green(f'\n{"-"*52}\n')
                    pcolor.Green(f'\n{" "*2}- boot_mode: SAN\n{" "*5}boot_target:')
                    pcolor.Green(f'{" "*4}initiator: {kwargs.fc_ifs[stgt.interface_name].wwpn}\n{" "*7}lun: {stgt.lun}\n{" "*7}target: {stgt.wwpn}')
                    pcolor.Green(f'{" "*4}profile: {v.name}\n{" "*5}serial: {v.serial}')
                    pcolor.Green(f'{" "*4}vnic:\n{" "*7}name: {vnic.name}\n{" "*7}mac: {vnic.mac}\n')
                elif v.boot_volume.lower() == 'm2' and type(v.install_interface) == str:
                    pcolor.Green(f'\n{"-"*52}\n')
                    pcolor.Green(f'{" "*2}- boot_mode: {v.boot_volume}')
                    pcolor.Green(f'{" "*4}profile: {v.name}\n{" "*5}serial: {v.serial}')
                    pcolor.Green(f'{" "*4}vnic:\n{" "*7}name: {vnic.name}\n{" "*7}mac: {vnic.mac}\n')
                else:
                    pcolor.Green(f'\n{"-"*52}\n')
                    pcolor.Green(f'{" "*2}- boot_mode: {v.boot_volume}')
                    pcolor.Green(f'{" "*4}profile: {v.name}\n{" "*5}serial: {v.serial}')
                #=============================================================
                # POST OS Install
                #=============================================================
                kwargs = kwargs | DotMap(api_body = ezfunctions.installation_body(v, kwargs), method = 'post', uri = 'os/Installs')
                kwargs = api(self.type).calls(kwargs)
                kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].os_install = DotMap(moid = kwargs.pmoid, workflow = '')
        names  = [e.os_install.moid for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles if v.os_installed == False and len(e.os_install.moid) > 0]
        if install_flag == True:
            pcolor.Cyan(f'\n{"-" * 108}\n\n    Sleeping for 30 Minutes to pause for Workflow/Infos Lookup.')
            pcolor.Cyan(f'\n{"-" * 108}\n')
            time.sleep(1800)
        #=====================================================================
        # Monitor OS Installation until Complete
        #=====================================================================
        kwargs = kwargs | DotMap(method = 'get', names = names, uri = 'os/Installs')
        kwargs = api('moid_filter').calls(kwargs)
        install_pmoids  = kwargs.pmoids
        install_results = kwargs.results
        for x in range(0,len(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles)):
            v = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x]
            indx = next((index for (index, d) in enumerate(install_results) if d['Moid'] == v.os_install.moid), None)
            v.install_success = False
            if indx != None:
                v.os_install.workflow = install_results[indx].WorkflowInfo.Moid
                install_complete = False
                while install_complete == False:
                    kwargs = kwargs | DotMap(method = 'get_by_moid', pmoid = v.os_install.workflow, uri = 'workflow/WorkflowInfos')
                    kwargs = api('workflow_info').calls(kwargs)
                    if kwargs.results.WorkflowStatus == 'Completed':
                        install_complete = True; v.install_success  = True
                        pcolor.Green(f'    - Completed Operating System Installation for `{v.name}`.')
                    elif re.search('Failed|Terminated|Canceled', kwargs.results.WorkflowStatus):
                        kwargs.upgrade.failed.update({v.name:v.moid})
                        pcolor.Red(f'!!! ERROR !!! Failed Operating System Installation for Server Profile `{v.name}`.')
                        install_complete = True; os_install_fail_count += 1
                    else:
                        progress= kwargs.results.Progress
                        status  = kwargs.results.WorkflowStatus
                        pcolor.Cyan(f'{" "*6}* Operating System Installation for `{v.name}` still In Progress.'\
                                    f'  Status is: `{status}`, Progress is: {progress} Percent, Sleeping for 120 seconds.')
                        time.sleep(120)
                #=============================================================
                # Add os_installed Tag to Physical Server
                #=============================================================
                if v.install_success == True:
                    tags = deepcopy(v.tags)
                    tag_body = []
                    os_installed = False
                    for e in tags:
                        if e.Key == 'os_installed':
                            os_installed = True
                            tag_body.append({'Key':e.Key,'Value':f'{v.os_vendor}: {v.os_version.name}'})
                        else: tag_body.append(e.toDict())
                    if os_installed == False:
                        tag_body.append({'Key':'os_installed','Value':f'{v.os_vendor}: {v.os_version.name}'})
                    tags = list({d['Key']:d for d in tags}.values())
                    kwargs     = kwargs | DotMap(api_body = {'Tags':tag_body}, method = 'patch', pmoid = v.hardware_moid, tag_server_profile = v.name)
                    kwargs.uri = f'{v.object_type}s'.replace('.', '/')
                    kwargs     = api('update_tags').calls(kwargs)
            elif v.os_installed == False:
                os_install_fail_count += 1
                pcolor.Red(f'      * Something went wrong with the OS Install Request for {v.name}. Please Validate the Server.')
            else: pcolor.Cyan(f'      * Skipping Operating System Install for {v.name}.')
        #=====================================================================
        # Send End Notification and return kwargs
        #=====================================================================
        validating.end_section(self.type, 'Install')
        if os_install_fail_count > 0:
            pcolor.Yellow(names)
            pcolor.Yellow(install_pmoids)
            pcolor.Yellow(json.dumps(install_results, indent=4))
            pcolor.Red(f'\n{"-"*108}\n')
            for x in range(0,len(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles)):
                v = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x]
                if not v.install_success == True: pcolor.Red(f'      * OS Install Failed for `{v.name}`.  Please Validate the Logs.')
            pcolor.Red(f'\n{"-"*108}\n')
            pcolor.Red(f'  Exiting... (intersight-tools/classes/isight.py Line 1576)'); len(False); sys.exit(1)
        return kwargs

    #=========================================================================
    # Function - Policies Function
    #=========================================================================
    def policies(self, kwargs):
        #=====================================================================
        # Send Begin Notification and Load Variables
        #=====================================================================
        ptitle = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        validating.begin_section(ptitle, 'policies')
        idata = DotMap(dict(pair for d in kwargs.ezdata[self.type].allOf for pair in d.properties.items()))
        pdict = deepcopy(kwargs.imm_dict.orgs[kwargs.org].policies[self.type])
        if self.type == 'port': policies = list({v.names[0]:v for v in pdict}.values())
        elif self.type == 'firmware_authenticate':
            kwargs = imm(self.type).firmware_authenticate(kwargs)
            validating.end_section(ptitle, 'policies')
            return kwargs
        else: policies = list({v.name:v for v in pdict}.values())
        kwargs.idata = idata
        #=====================================================================
        # Get Existing Policies
        #=====================================================================
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        names = []
        for e in policies:
            if self.type == 'port': names.extend([f'{np}{e.names[x]}{ns}' for x in range(0,len(e.names))])
            else: names.append(f"{np}{e['name']}{ns}")
        kwargs = api_get(True, names, self.type, kwargs)
        kwargs.policy_results = kwargs.results
        #=====================================================================
        # Validate the Sub Policies are defined or get Moids
        #=====================================================================
        if re.search('imc_access|iscsi_boot|(l|s)an_connectivity|(vhba|vnic)_template', self.type):
            kwargs.cp = DotMap()
            for e in policies: kwargs = imm(self.type).policy_existing_check(e, kwargs)
            for e in list(kwargs.cp.keys()):
                if len(kwargs.cp[e].names) > 0:
                    names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                    kwargs = api_get(False, names, e, kwargs)
                    kwargs.pchildren[e] = kwargs.results
        #=====================================================================
        # If Modified, Patch the Policy via the Intersight API
        #=====================================================================
        def policies_to_api(api_body, kwargs):
            kwargs.uri   = kwargs.ezdata[self.type].intersight_uri
            if not api_body.get('Description'):
                policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
                api_body['Description'] = f'{api_body["Name"]} {policy_title} Policy.'
            if api_body['Name'] in kwargs.isight[kwargs.org].policies[self.type]:
                indx = next((index for (index, d) in enumerate(kwargs.policy_results) if d['Name'] == api_body['Name']), None)
                patch_policy = imm(self.type).compare_body_result(api_body, kwargs.policy_results[indx])
                api_body['pmoid']  = kwargs.isight[kwargs.org].policies[self.type][api_body['Name']]
                if patch_policy == True:
                    kwargs.bulk_list.append(deepcopy(api_body))
                    kwargs.pmoids[api_body['Name']].moid = api_body['pmoid']
                else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {ptitle} Policy: `{api_body['Name']}`.  Intersight Matches Configuration."\
                                  f"  Moid: {api_body['pmoid']}")
            else: kwargs.bulk_list.append(deepcopy(api_body))
            return kwargs
        #=====================================================================
        # Loop through Policy Items
        #=====================================================================
        kwargs.bulk_list = []
        for item in policies:
            if self.type == 'port':
                names = item.names; item.pop('names')
                for x in range(0,len(names)):
                    #=========================================================
                    # Construct api_body Payload
                    #=========================================================
                    api_body = deepcopy({'Name':f'{np}{names[x]}{ns}','ObjectType':kwargs.ezdata[self.type].object_type})
                    api_body = imm(self.type).build_api_body(api_body, idata, item, kwargs)
                    kwargs = policies_to_api(api_body, kwargs)
            else:
                #=============================================================
                # Construct api_body Payload
                #=============================================================
                api_body = deepcopy({'ObjectType':kwargs.ezdata[self.type].object_type})
                api_body = imm(self.type).build_api_body(api_body, idata, item, kwargs)
                kwargs   = policies_to_api(api_body, kwargs)
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
            for e in kwargs.results: kwargs.isight[kwargs.org].policies[self.type][e.Body.Name] = e.Body.Moid
        #=====================================================================
        # Loop Thru Sub-Items
        #=====================================================================
        pdict = deepcopy(kwargs.imm_dict.orgs[kwargs.org].policies[self.type])
        if self.type == 'port': kwargs.policies = list({v['names'][0]:v for v in pdict}.values())
        else: kwargs.policies = list({v['name']:v for v in pdict}.values())
        if 'port' == self.type:
            kwargs = imm('port.port_modes').port_modes(kwargs)
            kwargs = imm('port').ports(kwargs)
        elif re.search('local_user|storage|v(l|s)an', self.type):
            sub_list = ['local_user.users', 'storage.drive_groups', 'vlan.vlans', 'vsan.vsans']
            for e in sub_list:
                a, b = e.split('.')
                if a == self.type: kwargs = eval(f'imm(e).{b}(kwargs)')
        elif re.search('(l|s)an_connectivity', self.type):
            sub_list = ['lan_connectivity.vnics', 'lan_connectivity.vnics_from_template', 'san_connectivity.vhbas', 'san_connectivity.vhbas_from_template']
            for e in sub_list:
                a, b = e.split('.')
                if a == self.type:
                    scount = 0
                    for i in kwargs.policies:
                        ikeys = list(i.keys())
                        if b in ikeys: scount += 1
                    if scount > 0: kwargs = eval(f'imm(e).vnics(kwargs)')
        #=====================================================================
        # Send End Notification and return kwargs
        #=====================================================================
        validating.end_section(ptitle, 'policies')
        return kwargs

    #=========================================================================
    # Function - Check if Sub Policies are Defined or Get Moid via API
    #=========================================================================
    def policy_existing_check(self, item, kwargs):
        def policy_list(k, pname, ptype, kwargs):
            if 'pool' in k: p = 'pools'
            else: p = 'policies'
            org, pname = imm(ptype).seperate_org_pname(pname, kwargs)
            pkeys  = list(kwargs.isight[org][p][ptype].keys())
            if 'template' in k: kwargs.cp[ptype].names.append(f'{org}/{pname}')
            elif not pname in pkeys: kwargs.cp[ptype].names.append(f'{org}/{pname}')
            return kwargs
        for k, v in item.items():
            cp_keys = list(kwargs.cp.keys())
            if re.search('_polic(ies|y)|_pool(s)?|(vhba|vnic)_template$', k):
                ptype = ((((((k.replace('_policies', '')).replace('_address_pools', '')).replace('_pools', '')
                          ).replace('_policy', '')).replace('_address', '')).replace('_pool', '')).replace('initiator_', '')
                if   re.search('band_ip', ptype): ptype = 'ip'
                elif re.search('(primary|secondary)_target', ptype): ptype = 'iscsi_static_target'
                if not ptype in cp_keys: kwargs.cp[ptype].names = []
                #if not kwargs.cp.get(ptype): kwargs.cp[ptype].names = []
                if type(v) == list:
                    for e in v: kwargs = policy_list(k, e, ptype, kwargs)
                else: kwargs = policy_list(k, v, ptype, kwargs)
            elif re.search('vmq|usnic', k):
                kkeys = list(item[k].keys())
                if 'vmmq_adapter_policy' in kkeys and len(item[k]['vmmq_adapter_policy']) > 0:
                    kwargs = policy_list('ethernet_adapter_policy', item[k]['vmmq_adapter_policy'], 'ethernet_adapter', kwargs)
                elif 'usnic_adapter_policy' in kkeys and len(item[k]['usnic_adapter_policy']) > 0:
                    kwargs = policy_list('ethernet_adapter_policy', item[k]['usnic_adapter_policy'], 'ethernet_adapter', kwargs)
        return kwargs

    #=========================================================================
    # Function - Pools Function
    #=========================================================================
    def pools(self, kwargs):
        #=====================================================================
        # Send Begin Notification and Load Variables
        #=====================================================================
        ptitle = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        validating.begin_section(ptitle, 'pool')
        kwargs.bulk_list = []
        idata = DotMap(dict(pair for d in kwargs.ezdata[self.type].allOf for pair in d.properties.items()))
        pools = list({v['name']:v for v in kwargs.imm_dict.orgs[kwargs.org].pools[self.type]}.values())
        #=====================================================================
        # Get Existing Pools
        #=====================================================================
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        kwargs = api_get(True, [f'{np}{e.name}{ns}' for e in pools], self.type, kwargs)
        kwargs.pool_results = kwargs.results
        #=====================================================================
        # Loop through Items
        #=====================================================================
        for item in pools:
            #=================================================================
            # Construct api_body Payload
            #=================================================================
            api_body = {'ObjectType':kwargs.ezdata[self.type].object_type}
            api_body = imm(self.type).build_api_body(api_body, idata, item, kwargs)
            akeys = list(api_body.keys())
            if not 'AssignmentOrder' in akeys: api_body['AssignmentOrder'] = 'sequential'
            #=================================================================
            # Add Pool Specific Attributes
            #=================================================================
            if re.search('ww(n|p)n', self.type):  api_body.update({'PoolPurpose':self.type.upper()})
            #=================================================================
            # Resource Pool Updates
            #=================================================================
            if self.type == 'resource':
                kwargs = kwargs | DotMap(method = 'get', names = api_body['serial_number_list'], uri = kwargs.ezdata[self.type].intersight_uri_serial)
                kwargs = api('serial_number').calls(kwargs)
                smoids = kwargs.pmoids
                selector = "','".join(kwargs.names); selector = f"'{selector}'"
                stype = f"{smoids[api_body['serial_number_list'][0]].object_type.split('.')[1]}s"
                mmode = smoids[api_body['serial_number_list'][0]].management_mode
                api_body['ResourcePoolParameters'] = {'ManagementMode':mmode,'ObjectType':'resourcepool.ServerPoolParameters'}
                api_body['Selectors'] = [{
                    'ObjectType': 'resource.Selector',
                    'Selector': f"/api/v1/compute/{stype}?$filter=(Serial in ({selector})) and (ManagementMode eq '{mmode}')"
                }]
                api_body.pop('serial_number_list')
            #=================================================================
            # If Modified Patch the Pool via the Intersight API
            #=================================================================
            if api_body['Name'] in kwargs.isight[kwargs.org].pools[self.type]:
                indx = next((index for (index, d) in enumerate(kwargs.pool_results) if d['Name'] == api_body['Name']), None)
                patch_pool = imm(self.type).compare_body_result(api_body, kwargs.pool_results[indx])
                api_body['pmoid'] = kwargs.isight[kwargs.org].pools[self.type][api_body['Name']]
                if patch_pool == True: kwargs.bulk_list.append(deepcopy(api_body))
                else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {ptitle} Pool: `{api_body['Name']}`.  Intersight Matches Configuration."\
                                  f"  Moid: {api_body['pmoid']}")
            else: kwargs.bulk_list.append(deepcopy(api_body))
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri    = kwargs.ezdata[self.type].intersight_uri
            kwargs        = imm(self.type).bulk_request(kwargs)
            for e in kwargs.results: kwargs.isight[kwargs.org].pools[self.type][e.Body.Name] = e.Body.Moid
        #=====================================================================
        # Send End Notification and return kwargs
        #=====================================================================
        validating.end_section(ptitle, 'pool')
        return kwargs

    #=========================================================================
    # Function - Port Modes for Port Policies
    #=========================================================================
    def port_modes(self, kwargs):
        #=====================================================================
        # Loop Through Port Modes
        #=====================================================================
        np, ns = ezfunctions.name_prefix_suffix('port', kwargs)
        kwargs.bulk_list = []
        ezdata= kwargs.ezdata[self.type]
        p     = self.type.split('.')
        for item in kwargs.policies:
            if item.get(p[1]):
                for x in range(0,len(item['names'])):
                    kwargs.port_policy[f"{np}{item['names'][x]}{ns}"].names = []
                    for e in item[p[1]]: kwargs.port_policy[f"{np}{item['names'][x]}{ns}"].names.append(e.port_list[0])
                for i in list(kwargs.port_policy.keys()):
                    kwargs.parent_moid = kwargs.isight[kwargs.org].policies['port'][i]
                    kwargs.pmoid       = kwargs.parent_moid
                    kwargs = api_get(True, kwargs.port_policy[i].names, self.type, kwargs)
                    port_modes  = kwargs.pmoids
                    port_results= deepcopy(kwargs.results)
                    for e in item[p[1]]:
                        api_body = {'CustomMode':e.custom_mode,'ObjectType':ezdata.object_type,
                                          'PortIdStart':e.port_list[0],'PortIdEnd':e.port_list[1],
                                          ezdata.parent_policy:{'Moid':kwargs.parent_moid,'ObjectType':ezdata.parent_object}}
                        if e.get('slot_id'): api_body.update({'SlotId':e.slot_id})
                        else: api_body.update({'SlotId':1})
                        #=========================================================
                        # Create or Patch the Policy via the Intersight API
                        #=========================================================
                        kwargs.parent_key  = self.type.split('.')[0]
                        kwargs.parent_name = i
                        kwargs.parent_type = 'Port Policy'
                        kwargs.parent_moid = kwargs.isight[kwargs.org].policies['port'][i]
                        if port_modes.get(kwargs.parent_moid):
                            kwargs.method   = 'patch' if port_modes[kwargs.parent_moid].get(str(e.port_list[0])) else 'post'
                        else: kwargs.method = 'post'
                        if    kwargs.method == 'post': kwargs.bulk_list.append(deepcopy(api_body))
                        else:
                            indx = next((index for (index, d) in enumerate(port_results) if d['PortIdStart'] == e.port_list[0]), None)
                            patch_port = imm(self.type).compare_body_result(api_body, port_results[indx])
                            api_body['pmoid'] = port_modes[kwargs.parent_moid][str(e.port_list[0])].moid
                            if patch_port == True: kwargs.bulk_list.append(deepcopy(api_body))
                            else:
                                ps = e.port_list[0]; pe = e.port_list[1]
                                pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; Port Policy: `{i}`, CustomMode: `{e.custom_mode}`,  PortIdStart: `{ps}`"\
                                            f" and PortIdEnd: `{pe}`.  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri    = kwargs.ezdata[self.type].intersight_uri
            kwargs        = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign Port Types to Port Policies
    #=========================================================================
    def ports(self, kwargs):
        #=====================================================================
        # Create/Patch the Port Policy Port Types
        #=====================================================================
        def api_calls(port_type, kwargs):
            #=================================================================
            # Create or Patch the Policy via the Intersight API
            #=================================================================
            if re.search('port_channel', port_type): name = int(kwargs.api_body['PcId']); key_id = 'PcId'
            else: name = int(kwargs.api_body['PortId']); key_id = 'PortId'
            if kwargs.port_moids[port_type].get(kwargs.parent_moid):
                if kwargs.port_moids[port_type][kwargs.parent_moid].get(str(name)):
                    kwargs.method = 'patch'
                    kwargs.pmoid  = kwargs.port_moids[port_type][kwargs.parent_moid][str(name)].moid
                else: kwargs.method = 'post'
            else: kwargs.method = 'post'
            kwargs.uri = kwargs.ezdata[f'port.{port_type}'].intersight_uri
            if kwargs.method == 'patch':
                indx = next((index for (index, d) in enumerate(kwargs.port_results[port_type]) if d[key_id] == name), None)
                patch_port = imm(self.type).compare_body_result(kwargs.api_body, kwargs.port_results[port_type][indx])
                if patch_port == True: kwargs = api(f'port.{port_type}').calls(kwargs)
                else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; Port Policy: `{kwargs.parent_name}`, {key_id}: `{name}`."\
                                  f"  Intersight Matches Configuration.  Moid: {kwargs.pmoid}")
            else: kwargs.plist[port_type].append({'Body':deepcopy(kwargs.api_body), 'ClassId':'bulk.RestSubRequest', 'ObjectType':'bulk.RestSubRequest',
                                                  'Verb':'POST', 'Uri':f'/v1/{kwargs.uri}'})
            return kwargs
        #=====================================================================
        # Check if the Port Policy Port Type Exists
        #=====================================================================
        def get_ports(port_type, item, x, kwargs):
            names = []
            for i in item[port_type]:
                if re.search('port_channel', port_type):
                    if len(i.pc_ids) == 2: names.append(int(i.pc_ids[x]))
                    else: names.append(int(i.pc_ids[0]))
                else:
                    for e in ezfunctions.vlan_list_full(i.port_list): names.append(e)
            kwargs.pmoid = kwargs.parent_moid
            kwargs = api_get(True, names, f'port.{port_type}', kwargs)
            kwargs.port_moids[port_type] = kwargs.pmoids
            kwargs.port_results[port_type] = kwargs.results
            return kwargs
        #=====================================================================
        # Attach Ethernet/Flow/Link Policies
        #=====================================================================
        def policy_update(port_type, kwargs):
            for p in ['EthNetworkControl', 'EthNetworkGroup', 'FlowControl', 'LinkAggregation', 'LinkControl']:
                p = f'{p}Policy'
                if kwargs.api_body.get(p):
                    if 'port_channel' in port_type: parent = f"{port_type}:pc_id:{kwargs.api_body['PcId']}"
                    else: parent = f"{port_type}:port_id:{kwargs.api_body['PortId']}"
                    ptype      = (snakecase(p).replace('eth_', 'ethernet_')).replace('_policy', '')
                    org, pname = imm(ptype).seperate_org_pname(kwargs.api_body[p]['Moid'], kwargs)
                    kwargs.api_body[p]['Moid'] = imm(port_type).get_moid_from_isight_dict(parent, ptype, org, pname, kwargs)
                    if 'Group' in p: kwargs.api_body[p] = [kwargs.api_body[p]]
            return kwargs
        #=====================================================================
        # Create API Body for Port Policies
        #=====================================================================
        def port_type_call(port_type, item, x, kwargs):
            ezdata = kwargs.ezdata[f'port.{port_type}']
            for i in item[port_type]:
                api_body = {'ObjectType':ezdata.object_type, 'PortPolicy':{'Moid':kwargs.parent_moid,'ObjectType':'fabric.PortPolicy'}}
                kwargs.api_body = imm(f'port.{port_type}').build_api_body(api_body, ezdata.properties, i, kwargs)
                if i.get('pc_ids'):
                    if len(kwargs.api_body['PcId']) == 2: kwargs.api_body['PcId'] = i.pc_ids[x]
                    else: kwargs.api_body['PcId'] = i.pc_ids[0]
                    if re.search('appliance|ethernet|fcoe', port_type): kwargs = policy_update(f'port.{port_type}', kwargs)
                    for y in range(len(api_body['Ports'])):
                        if not kwargs.api_body['Ports'][y].get('AggregatePortId'): kwargs.api_body['Ports'][y]['AggregatePortId'] = 0
                        if not kwargs.api_body['Ports'][y].get('SlotId'): kwargs.api_body['Ports'][y]['SlotId'] = 1
                else:
                    if not kwargs.api_body.get('AggregatePortId'): kwargs.api_body['AggregatePortId'] = 0
                    if not kwargs.api_body.get('SlotId'): kwargs.api_body['SlotId'] = 1
                if i.get('vsan_ids'):
                    if len(i['vsan_ids']) > 1: kwargs.api_body['VsanId'] = i['vsan_ids'][x]
                    else: kwargs.api_body['VsanId'] = i['vsan_ids'][0]
                kwargs.api_body.pop('Organization')
                if re.search('port_channel', port_type): kwargs = api_calls(port_type, kwargs)
                elif re.search('role', port_type):
                    for e in ezfunctions.vlan_list_full(i.port_list):
                        kwargs.api_body['PortId'] = int(e)
                        kwargs = api_calls(port_type, kwargs)
            return kwargs
        #=====================================================================
        # Build Child Policy Map
        #=====================================================================
        kwargs.cp = DotMap(); kwargs.port_types = []; kwargs.ports = []
        for k in list(kwargs.ezdata.port.allOf[1].properties.keys()):
            if re.search('^port_(cha|rol)', k): kwargs.port_types.append(k)
        for e in kwargs.port_types:
            kwargs.port_type[e].names = []
            for item in kwargs.policies:
                if item.get(e):
                    kwargs.ports.append(e)
                    for i in item[e]:
                        if 'port_channel' in e: kwargs.port_type[e].names.extend(i.pc_ids)
                        kwargs = imm(f'port.{e}').policy_existing_check(i, kwargs)
        kwargs.ports = list(numpy.unique(numpy.array(kwargs.ports)))
        for e in list(kwargs.cp.keys()):
            if len(kwargs.cp[e].names) > 0:
                names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                kwargs = api_get(False, names, e, kwargs)
        #=====================================================================
        # Loop Through Port Types
        #=====================================================================
        kwargs.plist = DotMap()
        for item in kwargs.policies:
            for x in range(0,len(item.names)):
                for e in kwargs.ports:
                    if item.get(e):
                        np, ns = ezfunctions.name_prefix_suffix('port', kwargs)
                        kwargs.plist[e] = []
                        kwargs = kwargs | DotMap(parent_key = self.type.split('.')[0], parent_name = f'{np}{item.names[x]}{ns}', parent_type = 'Port Policy')
                        kwargs.parent_moid = kwargs.isight[kwargs.org].policies['port'][kwargs.parent_name]
                        kwargs = get_ports(e, item, x, kwargs)
                        port_type_call(e, item, x, kwargs)
                        if len(kwargs.plist[e]) > 0:
                            kwargs = kwargs | DotMap(api_body = {'Requests':kwargs.plist[e]}, method = 'post', uri = 'bulk/Requests')
                            kwargs = api('bulk_request').calls(kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Server Profile Templates
    #=========================================================================
    def profile_templates_chassis_server(self, profiles, kwargs):
        ezdata = kwargs.ezdata[self.type]
        kwargs.bulk_list = []
        for item in profiles:
            api_body = {'ObjectType':ezdata.object_type}
            api_body = imm(self.type).build_api_body(api_body, kwargs.idata, item, kwargs)
            if not api_body.get('TargetPlatform'): api_body['TargetPlatform'] = 'FIAttached'
            api_body = imm(self.type).profiles_policy_bucket(api_body, kwargs)
            api_body.pop('create_template')
            kwargs = imm(self.type).profiles_api_calls(api_body, kwargs)
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Profiles Function
    #=========================================================================
    def profiles(self, kwargs):
        #=====================================================================
        # Send Begin Notification and Load Variables
        #=====================================================================
        profile_type, dtype = self.type.split('.')
        if 'template' in self.type: ptitle = ezfunctions.mod_pol_description((f'{dtype} Profile').title())
        else: ptitle = ezfunctions.mod_pol_description(dtype.title())
        validating.begin_section(ptitle, profile_type)
        kkeys = list(kwargs.keys())
        if not 'object_type_map' in kkeys:
            for k, v in kwargs.ezdata.items():
                if v.intersight_type == 'policies' and not '.' in k:
                    kwargs.object_type_map[v.object_type] = DotMap(ezkey = k, intersight_uri = v.intersight_uri)
                elif v.intersight_type == 'pools' and not '.' in k:
                    kwargs.object_type_map[v.object_type] = DotMap(ezkey = k, intersight_uri = v.intersight_uri)
        names  = []; kwargs.serials = []
        ezdata = kwargs.ezdata[self.type]
        idata  = DotMap(dict(pair for d in ezdata.allOf for pair in d.properties.items()))
        if re.search('profiles.(chassis|server)', self.type):
            targets = DotMap(dict(pair for d in idata.targets['items'].allOf for pair in d.properties.items()))
            idata.pop('targets')
            idata = DotMap(dict(idata.toDict(), **targets.toDict()))
        #=====================================================================
        # Compile List of Profile Names
        #=====================================================================
        profiles            = []
        profile_policy_list = []
        run_reservation     = False
        if 'templates' in self.type:
            for e in kwargs.imm_dict.orgs[kwargs.org].templates[dtype]:
                if e.create_template == True: profiles.append(e)
                profile_policy_list.append(e)
        elif 'profiles.domain' in self.type:
            profiles = kwargs.imm_dict.orgs[kwargs.org].profiles[dtype]
            profile_policy_list = profiles
            for e in profiles: kwargs.serials.extend(e.serial_numbers)
        else:
            for v in kwargs.imm_dict.orgs[kwargs.org].profiles[dtype]:
                for e in v.targets:
                    profiles.append(DotMap(dict(e, **v)))
                    if 'reservations' in e:
                        if not e.ignore_reservations == True: run_reservation = True
                    if len(e.serial_number) > 0: kwargs.serials.append(e.serial_number)
            profile_policy_list = profiles
        #=====================================================================
        # Function - Get Template Names
        #=====================================================================
        def get_template(e, ekeys, kwargs):
            args         = DotMap(org = kwargs.org, tname = '', template = '')
            template_key = f'ucs_{dtype}_profile_template'
            if   template_key in ekeys: template_key = template_key
            elif 'ucs_server_template' in ekeys: template_key = 'ucs_server_template'
            if template_key in ekeys and len(e[template_key]) > 0 and e.get('attach_template') == True:
                args.org, args.template = imm(self.type).seperate_org_pname(e[template_key], kwargs)
                args.tkey  = template_key
                args.tname = e[template_key]
            return args
        #=====================================================================
        # Determine if the templates are not locally defined and append data
        #=====================================================================
        templates = []
        for e in profiles:
            if 'profiles.' in self.type:
                ekeys = list(e.keys())
                args  = get_template(e, ekeys, kwargs)
                if len(args.template) > 0:
                     tkeys = list(kwargs.isight[args.org].templates[dtype].keys())
                     if not args.template in tkeys: templates.append(f'{args.org}/{args.template}')
        if len(templates) > 0:
            kwargs.policy_lookup = DotMap()
            if re.search('chassis|server', self.type):
                kwargs = imm(self.type).profiles_chassis_server_lookup_templates(templates, kwargs)
            elif 'profiles.domain' == self.type:
                kwargs = imm(self.type).profiles_domain_lookup_templates(templates, kwargs)
        #=====================================================================
        # Loop Through Profiles for Templates
        #=====================================================================
        if 'profiles.' in self.type:
            for e in profiles:
                ekeys = list(e.keys())
                if 'targets' in ekeys: e.pop('targets')
                args = get_template(e, ekeys, kwargs)
                if len(args.template) > 0:
                    tkeys = list(kwargs.isight[args.org].templates[dtype].keys())
                    if not args.template in tkeys:
                        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
                        validating.error_policy_doesnt_exist(self.type, f'{np}{e.name}{ns}', args.tkey,  f'{args.org}/{args.template}')
                    kwargs.templates[f'{args.org}/{args.template}']
                    tdata = kwargs.imm_dict.orgs[args.org].templates[dtype]
                    indx  = next((index for (index, d) in enumerate(tdata) if d['name'] == args.template), None)
                    if indx != None: kwargs.templates[f'{args.org}/{args.template}'] = tdata[indx]
            #=================================================================
            # Loop Through Reservations if True
            #=================================================================
            if self.type == 'profiles.server' and run_reservation == True: kwargs = imm.identity_reservations(self, profiles, kwargs)
        #=====================================================================
        # Get Moids for Profiles/Templates
        #=====================================================================
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        kwargs.bulk_list = []
        for e in profiles: names.append(f'{np}{e.name}{ns}')
        if len(names) > 0:
            kwargs = api_get(True, names, self.type, kwargs)
            kwargs.profile_results = kwargs.results
        #=====================================================================
        # Get Moids for Switch Profiles
        #=====================================================================
        if 'domain' in self.type:
            kwargs.uri = ezdata.switch_intersight_uri
            swkeys     = list(kwargs.isight[kwargs.org][profile_type][dtype].keys())
            sw_names  = []
            for sw in names:
                if sw in swkeys: sw_names.append(kwargs.isight[kwargs.org][profile_type][dtype][sw])
            if len(sw_names) > 0:
                if 'profiles' in self.type: sw_key = 'switch_profiles'
                else: sw_key = 'sw_profile_templates'
                kwargs.names = sw_names
                kwargs       = api(sw_key).calls(kwargs)
                for e in kwargs.results:
                    for sw in names:
                        swm = list(kwargs.switch_moids.keys())
                        if e.Parent.Moid == kwargs.isight[kwargs.org][profile_type][dtype][sw]:
                            kwargs.isight[kwargs.org][profile_type]['switch'][e.Name] = e.Moid
                            if not sw in swm: kwargs.switch_moids[sw] = []; kwargs.switch_results[sw] = []
                            kwargs.switch_moids[sw].append(kwargs.pmoids[e.Name])
                            kwargs.switch_results[sw].append(e)
        #=====================================================================
        # Get Policy Moids
        #=====================================================================
        kwargs.cp = DotMap()
        for e in profile_policy_list: kwargs = imm(self.type).policy_existing_check(e, kwargs)
        for e in list(kwargs.cp.keys()):
            if len(kwargs.cp[e].names) > 0:
                names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                kwargs = api_get(False, names, e, kwargs)
        #=====================================================================
        # Get Serial Moids
        #=====================================================================
        if len(kwargs.serials) > 0:
            kwargs.names          = kwargs.serials
            kwargs.uri            = ezdata.intersight_uri_serial
            kwargs                = api('serial_number').calls(kwargs)
            kwargs.serial_moids   = kwargs.pmoids
            kwargs.serial_results = kwargs.results
        #=====================================================================
        # Create the Profiles with the Functions
        #=====================================================================
        kwargs.idata = idata
        kwargs.uri   = ezdata.intersight_uri
        if re.search('^profiles.(chassis|server)$', self.type):
            kwargs = imm.profiles_chassis_server(self, profiles, kwargs)
            kwargs = imm.profiles_chassis_server_deploy(self, profiles, kwargs)
        elif re.search('^templates.(chassis|server)$', self.type):
            kwargs = imm.profile_templates_chassis_server(self, profiles, kwargs)
        elif 'profiles.domain' == self.type:
            kwargs = imm.profiles_domain(self, profiles, kwargs)
            kwargs = imm.profiles_domain_deploy(self, profiles, kwargs)
        elif 'templates.domain' == self.type:
            kwargs = imm.profiles_domain(self, profiles, kwargs)
        #========================================================
        # End Function and return kwargs
        #========================================================
        validating.end_section(ptitle, profile_type)
        return kwargs

    #=========================================================================
    # Function - Profile Creation Function
    #=========================================================================
    def profiles_api_calls(self, api_body, kwargs):
        profile_type, dtype = self.type.split('.')
        ikeys = list(kwargs.isight[kwargs.org][profile_type][dtype].keys())
        if 'template' in self.type: ptitle = ezfunctions.mod_pol_description((f'{dtype} Profile {profile_type}').title())
        else: ptitle = ezfunctions.mod_pol_description(f'{dtype} {profile_type}'.title())
        if api_body['Name'] in ikeys:
            indx = next((index for (index, d) in enumerate(kwargs.profile_results) if d['Name'] == api_body['Name']), None)
            patch_profile = imm(self.type).compare_body_result(api_body, kwargs.profile_results[indx])
            api_body['pmoid'] = kwargs.isight[kwargs.org][profile_type][dtype][api_body['Name']]
            if patch_profile == True:
                if 'SrcTemplate' in api_body:
                    if api_body['SrcTemplate'] != None and kwargs.profile_results[indx].SrcTemplate != None:
                        if api_body['SrcTemplate']['Moid'] != kwargs.profile_results[indx].SrcTemplate.Moid:
                            pmoid  = kwargs.isight[kwargs.org][profile_type][dtype][api_body['Name']]
                            kwargs = kwargs | DotMap(api_body = {'SrcTemplate':None}, method = 'patch', pmoid = pmoid, uri = kwargs.ezdata[self.type].intersight_uri)
                            kwargs = api(self.type).calls(kwargs)
                kwargs.bulk_list.append(deepcopy(api_body))
            else:
                pcolor.Cyan(
                    f"{' '*6}* Skipping Org: {kwargs.org} > {ptitle}: `{api_body['Name']}`.  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
        else: kwargs.bulk_list.append(deepcopy(api_body))
        return kwargs

    #=========================================================================
    # Function - Merge Template with Chassis/Domain/Server Profile
    #=========================================================================
    def profiles_bulk_merge_template(self, profiles, kwargs):
        dtype  = self.type.split('.')[1]
        if re.search('chassis|server', self.type): otype = f'{dtype}.Profile'
        elif 'switch' in self.type: otype = 'fabric.SwitchProfile'
        else: otype = 'fabric.SwitchClusterProfile'
        kwargs.bulk_merger_template = DotMap()
        for e in profiles:
            ekeys = list(e.keys())
            template_key = 'ucs_server_template'
            if template_key in ekeys: template_key = template_key
            elif f'ucs_{dtype}_profile_template' in ekeys: template_key = f'ucs_{dtype}_profile_template'
            template_check = False
            if e.attach_template == True and template_key in ekeys and len(e[template_key]) > 0:
                org, template = imm(f'templates.{dtype}').seperate_org_pname(e[template_key], kwargs)
                if len(template) > 0: template_check = True
            if template_check == True:
                np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
                if 'switch' in self.type:
                    for x in range(1,3):
                        sw_template = f"{template}-{chr(ord('@')+x)}"
                        if not kwargs.bulk_merger_template.get(f'{org}/{sw_template}'):
                            tmoid = kwargs.isight[org].templates[dtype][sw_template]
                            kwargs.bulk_merger_template[f'{org}/{sw_template}'] = {
                                'MergeAction': 'Merge', 'ObjectType': 'bulk.MoMerger', 'Targets':[],
                                'Sources':[{'Moid':tmoid, 'ObjectType':f'{otype}Template'}]}
                        idict = {'Moid': kwargs.isight[kwargs.org].profiles[dtype][f"{np}{e.name}{ns}-{chr(ord('@')+x)}"], 'ObjectType':otype}
                        kwargs.bulk_merger_template[f'{org}/{sw_template}']['Targets'].append(idict)
                else:
                    if not kwargs.bulk_merger_template.get(f'{org}/{template}'):
                        tmoid = kwargs.isight[org].templates[dtype][template]
                        kwargs.bulk_merger_template[f'{org}/{template}'] = {
                            'MergeAction': 'Merge', 'ObjectType': 'bulk.MoMerger', 'Targets':[],
                            'Sources':[{'Moid':tmoid, 'ObjectType':f'{otype}Template'}]}
                    idict = {'Moid': kwargs.isight[kwargs.org].profiles[dtype][f'{np}{e.name}{ns}'], 'ObjectType':otype}
                    kwargs.bulk_merger_template[f'{org}/{template}']['Targets'].append(idict)
        #=====================================================================
        # POST bulk/MoMergers if Map > 0 and return kwargs
        #=====================================================================
        if len(kwargs.bulk_merger_template) > 0:
            for e in kwargs.bulk_merger_template.keys():
                kwargs = kwargs | DotMap(api_body = kwargs.bulk_merger_template[e], method = 'post', uri = 'bulk/MoMergers')
                kwargs = api('bulk').calls(kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Chassis/Server Profiles
    #=========================================================================
    def profiles_chassis_server(self, profiles, kwargs):
        dtype  = self.type.split('.')[1]
        ezdata = kwargs.ezdata[self.type]
        #=====================================================================
        # Assign Server Profile Identity Reservations - If Defined
        #=====================================================================
        if self.type == 'profiles.server':
            np,ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
            #ikeys = list(kwargs.isight[kwargs.org].profiles.server.keys())
            for e in profiles:
                name  = f'{np}{e.name}{ns}'
                ekeys = list(e.keys())
                #if not name in ikeys and 'reservations' in ekeys:
                if 'reservations' in ekeys:
                    api_body = {'Name': name, 'ObjectType': ezdata.object_type,'TargetPlatform':'FIAttached'}
                    api_body = imm(self.type).org_map(api_body, kwargs.org_moids[kwargs.org].moid)
                    kwargs   = imm.profiles_server_reservations(self, e, api_body, kwargs)
                    if len(api_body['ReservationReferences']) > 0: kwargs.bulk_list.append(api_body)
            #=================================================================
            # POST bulk/Requests if Bulk List > 0
            #=================================================================
            if len(kwargs.bulk_list) > 0:
                kwargs.uri = kwargs.ezdata[self.type].intersight_uri
                kwargs     = imm(self.type).bulk_request(kwargs)
                for e in kwargs.results:
                    kwargs.isight[kwargs.org].profiles[dtype][e.Body.Name] = e.Body.Moid
                    kwargs.profile_results.append(e.Body)
        #=====================================================================
        # Assign Server Profile Identity Reservations - If Defined
        #=====================================================================
        kwargs.bulk_list = []
        for e in profiles:
            ekeys    = list(e.keys())
            api_body = {'ObjectType':ezdata.object_type}
            template_key = f'ucs_{dtype}_profile_template'
            if template_key in ekeys: template_key = template_key
            elif 'ucs_server_template' in ekeys: template_key = 'ucs_server_template'
            if template_key in ekeys and len(e[template_key]) > 0:
                org, template   = imm(f'templates.{dtype}').seperate_org_pname(e[template_key], kwargs)
            if e.attach_template != True and template_key in ekeys and len(e[template_key]) > 0:
                pitems = dict(kwargs.templates[f'{org}/{template}'], **deepcopy(e))
            else: pitems = deepcopy(e)
            pop_items = ['action', 'attach_template', 'create_template', 'domain_name', 'ignore_reservations', 'reservations',
                         'ucs_chassis_profile_template', 'ucs_server_template', 'ucs_server_profile_template']
            pkeys = list(pitems.keys())
            for p in pop_items:
                if p in pkeys: pitems.pop(p)
            plist = []
            for k in list(kwargs.idata.keys()):
                if re.search('_policy|_pool$', k): plist.append(k)
            pitem_keys = list(pitems.keys())
            for p in plist:
                if p in pitem_keys:
                    org, policy = imm(p).seperate_org_pname(pitems[p], kwargs)
                    pitems[p] = f'{org}/{policy}'
            api_body = {'ObjectType':ezdata.object_type}
            api_body = imm(self.type).build_api_body(api_body, kwargs.idata, pitems, kwargs)
            if not api_body.get('TargetPlatform'): api_body['TargetPlatform'] = 'FIAttached'
            if api_body.get('PolicyBucket') or api_body.get('UuidPool'): api_body = imm(self.type).profiles_policy_bucket(api_body, kwargs)
            if api_body.get('SerialNumber'): api_body = imm(self.type).assign_physical_device(api_body, kwargs)
            if api_body.get('ServerPreAssignBySlot'):
                if api_body['ServerPreAssignBySlot'].get('SerialNumber'):
                    api_body['ServerPreAssignBySerial'] = api_body['ServerPreAssignBySlot']['SerialNumber']
                    api_body.pop('ServerPreAssignBySlot')
                else:
                    if not e.get('domain_name'):
                        kwargs.name = e.name; kwargs.argument = 'domain_name'
                        validating.error_required_argument_missing(self.type, kwargs)
                    api_body['ServerPreAssignBySlot']['DomainName'] = e.domain_name
            if e.attach_template == True and template_key in ekeys and len(e[template_key]) > 0:
                api_body['SrcTemplate'] = {'Moid':kwargs.isight[org].templates[dtype][template], 'ObjectType':f'{ezdata.object_type}Template'}
            else: api_body['SrcTemplate'] = None
            kwargs = imm(self.type).profiles_api_calls(api_body, kwargs)
        #=====================================================================
        # POST bulk/Requests if Bulk List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
            for e in kwargs.results: kwargs.isight[kwargs.org].profiles[dtype][e.Body.Name] = e.Body.Moid
        kwargs = imm(self.type).profiles_bulk_merge_template(profiles, kwargs)
        #=====================================================================
        # PATCH Profiles if has attach_template True and has a description
        #=====================================================================
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        kwargs.bulk_list = []
        for e in profiles:
            ekeys = list(e.keys())
            template_key = f'ucs_{dtype}_profile_template'
            if template_key in ekeys: template_key = template_key
            elif 'ucs_server_template' in ekeys: template_key = 'ucs_server_template'
            if template_key in ekeys and len(e[template_key]) > 0:
                pname = f'{np}{e.name}{ns}'
                api_body = dict(Description = '', Name = pname, ObjectType = ezdata.object_type,
                                pmoid = kwargs.isight[kwargs.org].profiles[dtype][pname])
                if 'description' in ekeys: api_body['Description'] = e.description
                else: api_body['Description'] = f'{pname} {dtype.capitalize()} Profile'
                kwargs.bulk_list.append(api_body)
        if len(kwargs.bulk_list) > 0:
            pcolor.Cyan('')
            pcolor.Cyan(f'{" "*3}Updating {dtype.capitalize()} Profile descriptions.')
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Deploy Profile if Action is Deploy
    #=========================================================================
    def profiles_chassis_server_deploy(self, profiles, kwargs):
        dtype  = self.type.split('.')[1]
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        cregex = re.compile('Analyzing|Assigned|Failed|Inconsistent|Validating')
        pending_changes = False
        kwargs.profile_update = DotMap()
        kwargs.uri = kwargs.ezdata[self.type].intersight_uri
        for e in profiles:
            ekeys = list(e.keys())
            if 'action' in ekeys and 'serial_number' in ekeys and re.search(serial_regex, e.serial_number):
                kwargs.profile_update[f'{np}{e.name}{ns}'] = e
                kwargs.profile_update[f'{np}{e.name}{ns}'].pending_changes = 'Empty'
        if len(kwargs.profile_update) > 0:
            kwargs = api_get(False, list(kwargs.profile_update.keys()), self.type, kwargs)
            profile_results = kwargs.results
            for e in list(kwargs.profile_update.keys()):
                indx = next((index for (index, d) in enumerate(profile_results) if d['Name'] == e), None)
                changes  = profile_results[indx].ConfigChanges.Changes
                cstate   = profile_results[indx].ConfigContext.ConfigState
                csummary = profile_results[indx].ConfigContext.ConfigStateSummary
                if len(changes) > 0 or re.search(cregex, cstate) or re.search(cregex, csummary):
                    pending_changes = True
                    kwargs.profile_update[e].pending_changes = 'Deploy'
                elif len(profile_results[indx].ConfigChanges.PolicyDisruptions) > 0:
                    pending_changes = True
                    kwargs.profile_update[e].pending_changes = 'Activate'
            if pending_changes == True:
                pcolor.LightPurple(f'\n{"-"*108}\n')
                deploy_pending = False
                for e in list(kwargs.profile_updates.keys()):
                    if kwargs.profile_update[e].pending_changes == 'Deploy': deploy_pending = True
                if deploy_pending == True:
                    if 'server' == dtype:  pcolor.LightPurple(f'{" "*4}* Pending Changes.  Sleeping for 120 Seconds'); time.sleep(120)
                    else:  pcolor.LightPurple('    * Pending Changes.  Sleeping for 60 Seconds'); time.sleep(60)
                for e in list(kwargs.profile_update.keys()):
                    if kwargs.profile_update[e].pending_changes == 'Deploy':
                        pcolor.Green(f'{" "*4}- Beginning Profile Deployment for `{e}`.')
                        kwargs = kwargs | DotMap(api_body = {'Action': 'Deploy', 'Name': e}, method = 'patch', pmoid = kwargs.isight[kwargs.org].profiles[dtype][e])
                        kwargs = api(self.type).calls(kwargs)
                    else: pcolor.LightPurple(f'{" "*4}- Skipping Org: {kwargs.org}; Profile Deployment for `{e}`.  No Pending Changes.')
                if deploy_pending == True:
                    if 'server' == dtype:  pcolor.LightPurple(f'{" "*4}* Deploying Changes.  Sleeping for 600 Seconds'); time.sleep(600)
                    else:  pcolor.LightPurple(f'{" "*4}* Deploying Changes.  Sleeping for 60 Seconds'); time.sleep(60)
                for e in list(kwargs.profile_update.keys()):
                    if kwargs.profile_update[e].pending_changes == 'Deploy':
                        deploy_complete= False
                        while deploy_complete == False:
                            kwargs = kwargs | DotMap(method = 'get_by_moid', pmoid = kwargs.isight[kwargs.org].profiles[dtype][e])
                            kwargs = api(self.type).calls(kwargs)
                            if kwargs.results.ConfigContext.ControlAction == 'No-op':
                                deploy_complete = True
                                if 'chassis' in self.type: pcolor.Green(f'{" "*4}- Completed Profile Deployment for `{e}`.')
                            else: 
                                if 'server' in self.type: pcolor.Cyan(f'{" "*6}* Deploy Still Occuring on `{e}`.  Waiting 120 seconds.'); time.sleep(120)
                                else: pcolor.Cyan(f'{" "*6}* Deploy Still Occuring on `{e}`.  Waiting 60 seconds.'); time.sleep(60)
                if 'profiles.server' == self.type: kwargs = imm(self.type).profiles_server_activate(kwargs)
                pcolor.LightPurple(f'\n{"-"*108}\n')
        return kwargs

    #=========================================================================
    # Function - Policy Content for Template not locally defined
    #=========================================================================
    def profiles_chassis_server_lookup_templates(self, templates, kwargs):
        dtype = self.type.split('.')[1]
        kwargs = api_get(False, templates, f'templates.{dtype}', kwargs)
        templates_results = kwargs.results
        for e in templates_results:
            rkeys = list(e.keys())
            for p in e.PolicyBucket:
                if not kwargs.lookup.get(kwargs.object_type_map[p.ObjectType].ezkey): kwargs.lookup[kwargs.object_type_map[p.ObjectType].ezkey] = []
                kwargs.lookup[kwargs.object_type_map[p.ObjectType].ezkey].append(p.Moid)
            if 'UuidPool' in rkeys and e.UuidPool != None:
                if not kwargs.lookup.get('uuid'): kwargs.lookup.uuid = []
                kwargs.lookup.uuid.append(e.UuidPool.Moid)
        for k in list(kwargs.lookup.keys()):
            kwargs = kwargs | DotMap(method = 'get', names = list(numpy.unique(numpy.array(kwargs.lookup[k]))), uri = kwargs.ezdata[k].intersight_uri)
            kwargs = api('moid_filter').calls(kwargs)
            for e in kwargs.results:
                ptype = kwargs.ezdata[k].intersight_type
                kwargs.isight[kwargs.org_names[e.Organization.Moid]][ptype][k][e.Name] = e.Moid
                kwargs.policy_moids[e.Moid] = f'{kwargs.org_names[e.Organization.Moid]}/{e.Name}'
        for e in templates_results:
            rkeys = list(e.keys())
            tdict = DotMap()
            for p in e.Policy_Bucket:
                tdict[f'{kwargs.object_type_map[p.ObjectType].ezkey}_policy'] = kwargs.policy_moids[p.Moid]
            if 'UuidPool' in rkeys and e.UuidPool != None: tdict.uuid = kwargs.policy_moids[e.UuidPool.Moid]
            kwargs.templates[f'{kwargs.org_names[e.Organization.Moid]}/{e.Name}'] = tdict
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Build Domain Profiles/Templates
    #=========================================================================
    def profiles_domain(self, profiles, kwargs):
        profile_type, dtype  = self.type.split('.')
        ezdata       = kwargs.ezdata[self.type]
        template_key = 'ucs_domain_profile_template'
        for e in profiles:
            ddict = {}; ekeys = list(e.keys())
            for d in ['description', 'name', 'tags']:
                if d in ekeys: ddict[d] = e[d]
            attach_template = False
            api_body = {'ObjectType':ezdata.object_type}
            api_body = imm(self.type).build_api_body(api_body, kwargs.idata, ddict, kwargs)
            kwargs   = imm(self.type).profiles_api_calls(api_body, kwargs)
            if template_key in ekeys and len(e[template_key]) > 0:
                attach_template = True
                org, template = imm(self.type).seperate_org_pname(e[template_key], kwargs)
            if attach_template == True and len(template) > 0:
                api_body['SrcTemplate'] = {'Moid':kwargs.isight[org].templates[dtype][template], 'ObjectType':f'{ezdata.object_type}Template'}
            else: api_body['SrcTemplate'] = None
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = ezdata.intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
            for e in kwargs.results: kwargs.isight[kwargs.org][profile_type][dtype][e.Body.Name] = e.Body.Moid
        if 'profiles.' in self.type:  kwargs = imm(self.type).profiles_bulk_merge_template(profiles, kwargs)
        #=====================================================================
        # PATCH Profiles if has attach_template True and has a description
        #=====================================================================
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        if 'profiles.' in self.type:
            kwargs.bulk_list = []
            for e in profiles:
                ekeys = list(e.keys())
                if 'description' in ekeys and template_key in ekeys and len(e[template_key]) > 0:
                    name = f'{np}{e.name}{ns}'
                    api_body = dict(Description = e.description, Name = name, ObjectType = ezdata.object_type)
                    api_body['pmoid'] = kwargs.isight[kwargs.org].profiles[dtype][api_body['Name']]
                    kwargs.bulk_list.append(api_body)
            if len(kwargs.bulk_list) > 0:
                pcolor.Cyan('')
                pcolor.Cyan(f'{" "*3}Updating {dtype.capitalize()} Profile descriptions.')
                kwargs.uri = kwargs.ezdata[self.type].intersight_uri
                kwargs     = imm(self.type).bulk_request(kwargs)
        #=====================================================================
        # Build api_body for Switch Profiles
        #=====================================================================
        cl_otype         = ezdata.object_type.split('.')[1]
        kwargs.bulk_list = []
        sw_otype         = ezdata.switch_object_type
        for e in profiles:
            attach_template = False
            name         = f'{np}{e.name}{ns}'
            cluster_moid = kwargs.isight[kwargs.org][profile_type][dtype][name]; ekeys = list(e.keys())
            kwargs.profile_results = kwargs.switch_results[name]
            if template_key in ekeys and len(e[template_key]) > 0:
                attach_template = True
                org, template = imm(self.type).seperate_org_pname(e[template_key], kwargs)
            for x in range(1,3):
                sw_name         = f"{name}-{chr(ord('@')+x)}"
                if 'profiles.' in self.type and e.attach_template != True and template_key in ekeys and len(e[template_key]) > 0:
                    sw_dict = dict(kwargs.templates[f'{org}/{template}'], **deepcopy(e))
                else: sw_dict = deepcopy(e)
                pkeys = list(sw_dict.keys())
                for p in ['action', 'attach_template', 'create_template', 'ucs_domain_profile_template']:
                    if p in pkeys: sw_dict.pop(p)
                plist = []
                for k in list(kwargs.idata.keys()):
                    if re.search('_policies|_policy$', k): plist.append(k)
                sw_dict_keys = list(sw_dict.keys())
                for p in plist:
                    if p in sw_dict_keys:
                        if re.search('_policy', p):
                            if not '/' in sw_dict[p]: sw_dict[p] = f'{kwargs.org}/{sw_dict[p]}'
                        else:
                            for y in range(0,len(sw_dict[p])):
                                if not '/' in sw_dict[p][y]: sw_dict[p][y] = f'{kwargs.org}/{sw_dict[p][y]}'
                sw_dict.name = sw_name
                api_body = {'ObjectType':sw_otype, cl_otype:{'Moid':cluster_moid,'ObjectType':f'fabric.{cl_otype}'}}
                api_body = imm(f'{profile_type}.switch').build_api_body(api_body, kwargs.idata, sw_dict, kwargs)
                api_body = imm(f'{profile_type}.switch').profiles_policy_bucket(api_body, kwargs)
                kwargs.x_number = deepcopy(x)
                if api_body.get('SerialNumber'): api_body = imm('profiles.switch').assign_physical_device(api_body, kwargs)
                for p in ['Description', 'Organization']:
                    if api_body.get(p): api_body.pop(p)
                if attach_template == True and len(template) > 0:
                    sw_template = f"{template}-{chr(ord('@')+x)}"
                    api_body['SrcTemplate'] = {
                        'Moid':kwargs.isight[org].templates['switch'][sw_template], 'ObjectType':f'{ezdata.switch_object_type}Template'}
                elif 'profiles' in self.type: api_body['SrcTemplate'] = None
                kwargs  = imm(f'{profile_type}.switch').profiles_api_calls(api_body, kwargs)
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = ezdata.switch_intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        if 'profiles.' in self.type:  kwargs = imm(f'{profile_type}.switch').profiles_bulk_merge_template(profiles, kwargs)
        return kwargs

    #=========================================================================
    # Function - Deploy Domain Profile if Action is Deploy
    #=========================================================================
    def profiles_domain_deploy(self, profiles, kwargs):
        dtype = self.type.split('.')[1]
        pending_changes = False
        kwargs.names    = []
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        for e in profiles:
            name = f'{np}{e.name}{ns}'
            kwargs.cluster_update[name].names = []
            kwargs.cluster_update[name].pending_changes = False
            if e.get('action') and e.get('serial_numbers'):
                serial_check = True
                for d in e.serial_numbers:
                    if not re.search(serial_regex, d): serial_check = False
                if e.action == 'Deploy' and serial_check == True:
                    kwargs.names.append(kwargs.isight[kwargs.org].profiles[dtype][name])
        clusters = DotMap()
        for k,v in kwargs.isight[kwargs.org].profiles[dtype].items(): clusters[v] = k
        if len(kwargs.names) > 0:
            kwargs = kwargs | DotMap(method = 'get', parent = 'SwitchClusterProfile', uri = kwargs.ezdata[self.type].switch_intersight_uri)
            kwargs = api('parent_moids').calls(kwargs)
            for e in kwargs.results:
                if len(e.ConfigChanges.Changes) > 0 or re.search("Assigned|Failed|Pending-changes", e.ConfigContext.ConfigState):
                    pending_changes = True
                    kwargs.cluster_update[clusters[e.Parent.Moid]].pending_changes = True
                    kwargs.cluster_update[clusters[e.Parent.Moid]].names.append(e.Name)
        if pending_changes == True:
            pcolor.LightPurple(f'\n{"-"*108}\n')
            pcolor.Cyan(f'{" "*6}* Sleeping for 120 Seconds'); time.sleep(120)
            pcolor.Green(f'{" "*4}- Beginning Profile Deployment for Switch Profiles')
        kwargs.bulk_list = []
        for k in list(kwargs.cluster_update.keys()):
            if kwargs.cluster_update[k].pending_changes == True:
                for e in kwargs.cluster_update[k].names:
                    kwargs.bulk_list.append({'Action':'Deploy', 'Name': e, 'pmoid':kwargs.isight[kwargs.org].profiles['switch'][e]})
        if len(kwargs.bulk_list) > 0: kwargs = imm('profiles.switch').bulk_request(kwargs)
        if pending_changes == True: pcolor.LightPurple(f'\n{"-"*108}\n'); time.sleep(60)
        for k in list(kwargs.cluster_update.keys()):
            if kwargs.cluster_update[k].pending_changes == True:
                kwargs = kwargs | DotMap(method = 'get_by_moid', uri = kwargs.ezdata[self.type].switch_intersight_uri)
                for e in kwargs.cluster_update[k].names:
                    kwargs.pmoid = kwargs.isight[kwargs.org].profiles['switch'][e]
                    deploy_complete = False
                    while deploy_complete == False:
                        kwargs = api('switch_profiles').calls(kwargs)
                        if kwargs.results.ConfigContext.ControlAction == 'No-op':
                            pcolor.Green(f'{" "*4}- Completed Switch Profile Deployment for {e}')
                            deploy_complete = True
                        else:  pcolor.Cyan(f'{" "*6}* Deploy Still Occuring on {e}.  Waiting 120 seconds.'); time.sleep(120)
        if pending_changes == True: pcolor.LightPurple(f'\n{"-"*108}\n')
        return kwargs

    #=========================================================================
    # Function - Policy Content for Template not locally defined
    #=========================================================================
    def profiles_domain_lookup_templates(self, templates, kwargs):
        dtype  = self.type.split('.')[1]
        kwargs = api_get(False, templates, f'templates.{dtype}', kwargs)
        sw     = DotMap()
        for e in kwargs.results:
            count = 1
            for d in e.SwitchProfiles:
                sw[d.Moid] = DotMap(fabric = chr(ord('@'+count)), name = e.Name); count += 1
        kwargs.names = list(sw.keys())
        kwargs.uri   = kwargs.ezdata[self.type].switch_intersight_uri
        kwargs = api('moids_filter').calls(kwargs)
        sw_results = kwargs.results
        for e in sw_results:
            for p in e.PolicyBucket:
                if not kwargs.lookup.get(kwargs.object_type_map[p.ObjectType].ezkey): kwargs.lookup[kwargs.object_type_map[p.ObjectType].ezkey] = []
                kwargs.lookup[kwargs.object_type_map[p.ObjectType].ezkey].append(p.Moid)
        for k in list(kwargs.lookup.keys()):
            kwargs = kwargs | DotMap(method = 'get', names = list(numpy.unique(numpy.array(kwargs.lookup[k]))), uri = kwargs.ezdata[k].intersight_uri)
            kwargs = api('moid_filter').calls(kwargs)
            for e in kwargs.results:
                ptype = kwargs.ezdata[k].intersight_type
                kwargs.isight[kwargs.org_names[e.Organization.Moid]][ptype][k][e.Name] = e.Moid
                kwargs.policy_moids[e.Moid] = f'{kwargs.org_names[e.Organization.Moid]}/{e.Name}'
        stemplates = DotMap()
        for e in sw_results:
            tdict = DotMap()
            for p in e.Policy_Bucket:
                tdict[f'{kwargs.object_type_map[p.ObjectType].ezkey}'] = kwargs.policy_moids[p.Moid]
            stemplates[f'{kwargs.org_names[e.Organization.Moid]}/{sw[e.Moid].name}'][sw[e.Moid].fabric] = tdict
        single_regex = 'ntp|network_control|snmp|switch_control|syslog|system_qos'
        dual_regex   = 'port|vlan|vsan'
        for k in list(stemplates.keys()):
            tdict = DotMap()
            for d in list(stemplates[k]['A'].keys()):
                if re.search(single_regex, d): tdict[f'{d}_policy'] = stemplates[k]['A'][d]
                elif re.search(dual_regex, d):
                    tdict[f'{d}_policies'] = [stemplates[k]['A'][d], stemplates[k]['B'][d]]
            kwargs.templates[k] = tdict
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Assign Moid to Policy in Bucket
    #=========================================================================
    def profiles_policy_bucket(self, api_body, kwargs):
        if api_body.get('PolicyBucket'):
            for x in range(len(api_body['PolicyBucket'])):
                ptype = ((api_body['PolicyBucket'][x]['policy']).replace('_policy', '')).replace('_policies', '')
                api_body['PolicyBucket'][x].pop('policy')
                if 'switch' in self.type:
                    if re.search('-A', api_body['Name']): f = 0
                    else: f = 1
                if type(api_body['PolicyBucket'][x]['Moid']) == list:
                    if len(api_body['PolicyBucket'][x]['Moid']) == 2: opolicy = api_body['PolicyBucket'][x]['Moid'][f]
                    else: opolicy = api_body['PolicyBucket'][x]['Moid'][0]
                else: opolicy = api_body['PolicyBucket'][x]['Moid']
                org, pname = imm(ptype).seperate_org_pname(opolicy, kwargs)
                api_body['PolicyBucket'][x]['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], ptype, org, pname, kwargs)
        if api_body.get('UuidPool'):
            api_body['UuidAddressType'] = 'POOL'
            org, pname = imm('uuid').seperate_org_pname(api_body['UuidPool']['Moid'], kwargs)
            api_body['UuidPool']['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'uuid', org, pname, kwargs)
        return api_body

    #=========================================================================
    # Function - Deploy Profile if Action is Deploy
    #=========================================================================
    def profiles_server_activate(self, kwargs):
        dtype  = self.type.split('.')[1]
        pcolor.LightPurple(f'\n{"-"*108}\n')
        names = []
        for e in list(kwargs.profile_update.keys()):
            if not kwargs.profile_update[e].pending_changes == 'Empty': names.append(e)
        if len(names) > 0:
            kwargs = api_get(False, names, self.type, kwargs)
            profile_results = kwargs.results
        pending_activations = False
        for e in list(kwargs.profile_update.keys()):
            if not kwargs.profile_update[e].pending_changes == 'Empty':
                indx = next((index for (index, d) in enumerate(profile_results) if d['Name'] == e), None)
                if len(profile_results[indx].ConfigChanges.PolicyDisruptions) > 0:
                    pcolor.Green(f'{" "*4}- Beginning Profile Activation for `{e}`.')
                    api_body = {'ScheduledActions':[{'Action':'Activate', 'ProceedOnReboot':True}]}
                    kwargs   = kwargs | DotMap(api_body = api_body, method = 'patch', pmoid = kwargs.isight[kwargs.org].profiles[dtype][e])
                    kwargs   = api(self.type).calls(kwargs)
                    pending_activations = True
                else:
                    pcolor.LightPurple(f'{" "*4}- Skipping Org: {kwargs.org}; Profile Activation for `{e}`.  No Pending Changes.')
                    kwargs.profile_update[e].pending_changes = 'Empty'
        if pending_activations == True:
            pcolor.LightPurple(f'\n{"-"*108}\n')
            pcolor.LightPurple('    * Pending Activitions.  Sleeping for 300 Seconds'); time.sleep(300)
        activate_names = []
        for e in list(kwargs.profile_update.keys()):
            if not kwargs.profile_update[e].pending_changes == 'Empty':
                activate_names.append(kwargs.isight[kwargs.org].profiles[self.type][e])
        if len(activate_names) > 0:
            dt     = datetime.today().strftime('%Y-%m-%d')
            names  = "', '".join(activate_names).strip("', '")
            str1   = f"CreateTime gt {dt}T00:00:00.000Z and CreateTime lt {dt}T23:59:59.999Z and AssociatedObject.Moid in ('{names}')"
            str2   = f" and WorkflowCtx.WorkflowType eq 'Activate'"
            kwargs = kwargs | DotMap(api_filter = str1 + str2, method = 'get', uri = 'workflow/WorkflowInfos')
            kwargs = api('workflows').calls(kwargs)
            activate_results = sorted(kwargs.results, key=itemgetter('CreateTime'), reverse=True)
        loop_count = 0
        def activation_message(e, progress, status):
            pcolor.Cyan(f'{" "*6}* Still In Progress for `{e}`.  Status: `{status}` Progress Percentage: `{progress}`, Sleeping for 120 seconds.')
        def failed_message(e):
            pcolor.Yellow(f'\n{"-"*75}\n')
            pcolor.Red(f'  - Failed to Activate Profile `{e}`.  Please validate in Intersight the reason for the failure.')
            pcolor.Yellow(f'\n{"-"*75}\n')
        def success_message(e):
            pcolor.Green(f'{" "*4}- Completed Profile Activiation for `{e}`.')
        for e in list(kwargs.profile_update.keys()):
            retry_count = 60
            if not kwargs.profile_update[e].pending_changes == 'Empty':
                prmoid = kwargs.isight[kwargs.org].profiles[dtype][e]
                indx   = next((index for (index, d) in enumerate(activate_results) if d['AssociatedObject']['Moid'] == prmoid), None)
                deploy_complete = False
                while deploy_complete == False:
                    if retry_count > 60: failed_message(e); deploy_complete == True
                    if loop_count > 0:
                        kwargs = kwargs | DotMap(method = 'get_by_moid', pmoid = activate_results[indx].Moid)
                        kwargs = api(self.type).calls(kwargs)
                        active_result = kwargs.results
                    else: active_result = activate_results[indx]
                    if active_result.WorkflowStatus == 'Completed': success_message(e); deploy_complete   = True
                    elif re.search('Failed|Terminated|Canceled', active_result.WorkflowStatus):
                        failed_message(e); deploy_complete == True
                    else:  
                        progress = active_result.Progress; status = active_result.WorkflowStatus
                        activation_message(e, progress, status); time.sleep(120)
                    loop_count += 1
            else: success_message(e)
        return kwargs

    #=========================================================================
    # Function - Build Server Profile Reservations
    #=========================================================================
    def profiles_server_reservations(self, e, api_body, kwargs):
        api_body['ReservationReferences'] = []
        for i in e.reservations:
            if i.identity in kwargs.ireservations[i.identity_type]:
                if 'ww' in i.identity_type: rdict = {'ObjectType':'fcpool.ReservationReference'}
                else: rdict = {'ObjectType':f'{i.identity_type}pool.ReservationReference'}
                rdict.update({'ReservationMoid':kwargs.ireservations[i.identity_type][i.identity].moid})
                if re.search('ip|mac|wwnn|wwpn', i.identity_type):
                    if 'ip' in i.identity_type and re.search('band', i.management_type):
                        rdict.update({'ConsumerType':f'{(i.management_type.lower()).title()}{(i.ip_type.lower()).title()}-Access'})
                    elif 'ip' in i.identity_type: rdict.update({'ConsumerType':'ISCSI'})
                    elif 'mac' in i.identity_type: rdict.update({'ConsumerType':'Vnic'})
                    elif 'wwpn' in i.identity_type: rdict.update({'ConsumerType':f'Vhba'})
                    elif 'wwnn' in i.identity_type: rdict.update({'ConsumerType':f'WWNN'})
                    if len(i.management_type) == 0 and i.identity_type != 'wwnn': rdict.update({'ConsumerName':i.interface})
                api_body['ReservationReferences'].append(rdict)
        return kwargs

    #=========================================================================
    # Function - SAN Connectivity Policy Modification
    #=========================================================================
    def san_connectivity(self, api_body, item, kwargs):
        if not api_body.get('PlacementMode'): api_body.update({'PlacementMode':'custom'})
        if not api_body.get('TargetPlatform'): api_body.update({'TargetPlatform': 'FIAttached'})
        if api_body.get('StaticWwnnAddress'): api_body['WwnnAddressType'] = 'STATIC'
        else: api_body['WwnnAddressType'] = 'POOL'
        if api_body.get('WwnnPool'):
            org, pname = imm(self.type).seperate_org_pname(item.wwnn_pool, kwargs)
            api_body['WwnnPool']['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'wwnn', org, pname, kwargs)
        return api_body

    #=========================================================================
    # Function - Check if Org in Pool/Policy Name and Split
    #=========================================================================
    def seperate_org_pname(self, policy, kwargs):
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        if '/' in policy: org, pname  = policy.split('/')
        else: org = kwargs.org; pname = policy
        pname = np + pname + ns
        return org, pname

    #=========================================================================
    # Function - SNMP Policy Modification
    #=========================================================================
    def snmp(self, api_body, item, kwargs):
        item = item
        for e in ['AccessCommunityString', 'TrapCommunity']:
            if e in api_body:
                if 'Access' in e: kwargs.sensitive_var = f"access_community_string_{api_body[e]}"
                else: kwargs.sensitive_var = f"snmp_trap_community_{api_body[e]}"
                kwargs = ezfunctions.sensitive_var_value(kwargs)
                api_body[e] = kwargs.var_value
        if api_body.get('SnmpTraps'):
            for x in range(len(api_body['SnmpTraps'])):
                if api_body['SnmpTraps'][x].get('Community'):
                    kwargs.sensitive_var = f"snmp_trap_community_{api_body['SnmpTraps'][x]['Community']}"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    api_body['SnmpTraps'][x]['Community'] = kwargs.var_value
                    api_body['SnmpTraps'][x]['Version'] = 'V2'
                else: api_body['SnmpTraps'][x]['Version'] = 'V3'
        if api_body.get('SnmpUsers'):
            for x in range(len(api_body['SnmpUsers'])):
                if api_body['SnmpUsers'][x].get('AuthPassword'):
                    kwargs.sensitive_var = f"snmp_auth_password_{api_body['SnmpUsers'][x]['AuthPassword']}"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    api_body['SnmpUsers'][x]['AuthPassword'] = kwargs.var_value
                if api_body['SnmpUsers'][x].get('PrivacyPassword'):
                    kwargs.sensitive_var = f"snmp_privacy_password_{api_body['SnmpUsers'][x]['PrivacyPassword']}"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    api_body['SnmpUsers'][x]['PrivacyPassword'] = kwargs.var_value
        return api_body

    #=========================================================================
    # Function - Storage Policy Modification
    #=========================================================================
    def storage(self, api_body, item, kwargs):
        item = item; kwargs = kwargs
        if api_body.get('M2VirtualDrive'): api_body['M2VirtualDrive']['Enable'] = True
        if api_body.get('Raid0Drive'):
            if not api_body['Raid0Drive'].get('Enable'): api_body['Raid0Drive']['Enable'] = True
            if not api_body['Raid0Drive'].get('VirtualDrivePolicy'):
                api_body['Raid0Drive']['VirtualDrivePolicy'] = {'ObjectType':'storage.VirtualDrivePolicy'}
                for k,v in kwargs.ezdata['storage.virtual_drive_policy'].properties.items():
                    if api_body['Raid0Drive']['VirtualDrivePolicy'].get(k):
                        api_body['Raid0Drive']['VirtualDrivePolicy'][v.intersight_api] = api_body['Raid0Drive']['VirtualDrivePolicy'][k]
                    else: api_body['Raid0Drive']['VirtualDrivePolicy'][v.intersight_api] = v.default
        if api_body.get('DriveGroup'): api_body.pop('DriveGroup')
        return api_body

    #=========================================================================
    # Function - Syslog Policy Modification
    #=========================================================================
    def syslog(self, api_body, item, kwargs):
        item = item; kwargs = kwargs
        if api_body.get('LocalClients'): api_body['LocalClients'] = [api_body['LocalClients']]
        return api_body

    #=========================================================================
    # Function - System QoS Policy Modification
    #=========================================================================
    def system_qos(self, api_body, item, kwargs):
        item = item
        if api_body.get('configure_recommended_classes'):
            if api_body['configure_recommended_classes'] == True:
                api_body['Classes'] = kwargs.ezdata['system_qos.classes_recommended'].classes
            api_body.pop('configure_recommended_classes')
        elif api_body.get('configure_default_classes'):
            if api_body['configure_default_classes'] == True:
                api_body['Classes'] = kwargs.ezdata['system_qos.classes_default'].classes
            api_body.pop('configure_default_classes')
        elif api_body.get('configure_recommended_classes') == None and (api_body.get('Classes') == None or len(api_body.get('Classes')) == 0):
            api_body['Classes'] = kwargs.ezdata['system_qos.classes_default'].classes
        if api_body.get('jumbo_mtu'):
            for x in range(0, len(api_body['Classes'])):
                if api_body['Classes'][x].get('Priority'):
                    api_body['Classes'][x]['Name'] = api_body['Classes'][x]['Priority']; api_body['Classes'][x].pop('Priority')
                if api_body['jumbo_mtu'] == True: api_body['Classes'][x]['Mtu'] = 9216
                else: api_body['Classes'][x]['Mtu'] = 9216
                if api_body['Classes'][x]['Name'] == 'FC': api_body['Classes'][x]['Mtu'] = 2240
            api_body.pop('jumbo_mtu')
        classes = api_body['Classes']
        api_body['Classes'] = []
        for e in classes:
            if type(e) == dict: api_body['Classes'].append(e)
            else: api_body['Classes'].append(e.toDict())
        api_body['Classes'] = sorted(api_body['Classes'], key=lambda ele: ele['Name'])
        return api_body

    #=========================================================================
    # Function - Assign Users to Local User Policies
    #=========================================================================
    def users(self, kwargs):
        #=====================================================================
        # Get Existing Users
        #=====================================================================
        names = []; kwargs.bulk_list = []; role_names = []; kwargs.cp = DotMap()
        ezdata = kwargs.ezdata[self.type]
        for i in kwargs.policies:
            if i.get('users'):
                for e in i.users: names.append(e.username); role_names.append(e.role)
        if len(names) > 0:
            names  = list(numpy.unique(numpy.array(names)))
            kwargs = api_get(True, names, self.type, kwargs)
            kwargs.user_moids   = kwargs.pmoids
            kwargs.user_results = kwargs.results
        if len(role_names) > 0:
            kwargs.names       = list(numpy.unique(numpy.array(role_names)))
            kwargs.uri         = 'iam/EndPointRoles'
            kwargs             = api('iam_role').calls(kwargs)
            kwargs.role_moids  = kwargs.pmoids
            kwargs.role_results= kwargs.results
        for i in kwargs.policies:
            if i.get('users'):
                if len(names) > 0:
                    kwargs.names = [v.moid for k, v in kwargs.user_moids.items()]
                    kwargs.pmoid = kwargs.isight[kwargs.org].policies[self.type.split('.')[0]][i.name]
                    kwargs.uri   = 'iam/EndPointUserRoles'
                    kwargs       = api('user_role').calls(kwargs)
                    kwargs.cp[kwargs.pmoid].moids  = kwargs.pmoids
                    kwargs.cp[kwargs.pmoid].results= kwargs.results

        #=====================================================================
        # Construct API Body Users
        #=====================================================================
        for e in names:
            if not kwargs.user_moids.get(e):
                api_body = {'Name':e,'ObjectType':ezdata.object_type}
                api_body = imm(self.type).org_map(api_body, kwargs.org_moids[kwargs.org].moid)
                kwargs.bulk_list.append(deepcopy(api_body))
            else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; User: `{e}`.  Intersight Matches Configuration.  Moid: {kwargs.user_moids[e].moid}")
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        kwargs.user_moids = DotMap(dict(kwargs.user_moids, **kwargs.pmoids))
        kwargs.bulk_list = []
        np, ns = ezfunctions.name_prefix_suffix('local_user', kwargs)
        for i in kwargs.policies:
            kwargs.parent_key  = self.type.split('.')[0]
            kwargs.parent_name = f'{np}{i.name}{ns}'
            kwargs.parent_type = 'Local User Policy'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policies[self.type.split('.')[0]][kwargs.parent_name]
            if i.get('users'):
                for e in i.users:
                    kwargs.sensitive_var = f"local_user_password_{e.password}"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    user_moid = kwargs.user_moids[e.username].moid
                    #=========================================================
                    # Create API Body for User Role
                    #=========================================================
                    if e.get('enabled'): api_body = {'Enabled':e.enabled,'ObjectType':'iam.EndPointUserRole'}
                    else: api_body = {'Enabled':True,'ObjectType':'iam.EndPointUserRole'}
                    api_body.update({
                        'EndPointRole':[{'Moid':kwargs.role_moids[e.role].moid,'ObjectType':'iam.EndPointRole'}],
                        'EndPointUser':{'Moid':user_moid,'ObjectType':'iam.EndPointUser'},
                        'EndPointUserPolicy':{'Moid':kwargs.parent_moid,'ObjectType':'iam.EndPointUserPolicy'},
                        'Password':kwargs.var_value})
                    #=========================================================
                    # Create or Patch the Policy via the Intersight API
                    #=========================================================
                    if kwargs.cp[kwargs.parent_moid].moids.get(user_moid):
                        api_body['pmoid'] = kwargs.cp[kwargs.parent_moid].moids[user_moid].moid
                        kwargs.bulk_list.append(deepcopy(api_body))
                    else: kwargs.bulk_list.append(deepcopy(api_body))
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = 'iam/EndPointUserRoles'
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - vHBA Specific settings
    #=========================================================================
    def vhba_settings(self, api_body, item, x, kwargs):
        def zone_update(api_body, e, ptype, kwargs):
            org, pname = imm(ptype).seperate_org_pname(e.Moid, kwargs)
            e['Moid']  = imm(self.type).get_moid_from_isight_dict(api_body['Name'], ptype, org, pname, kwargs)
            return e
        if api_body.get('FcZonePolicies'):
            kwargs.zbody = deepcopy(api_body['FcZonePolicies'])
            api_body['FcZonePolicies'] = []
            if 'template' in self.type: name_length = 1
            else: name_length = len(item.names)
            if name_length == 2:
                half = len(kwargs.zbody)//2
                if x == 0: zlist = kwargs.zbody[half:]
                else: zlist = kwargs.zbody[:half]
                for e in zlist: api_body['FcZonePolicies'].append(zone_update(api_body, e, 'fc_zone', kwargs))
            else:
                for e in kwargs.zbody: api_body['FcZonePolicies'].append(zone_update(api_body, e, 'fc_zone', kwargs))
        if api_body.get('StaticWwpnAddress'):
            if 'template' in self.type: api_body.update({'WwpnAddressType': 'STATIC'})
            else: api_body.update({'WwpnAddressType': 'STATIC','StaticWwpnAddress':api_body['StaticWwpnAddress'][x]})
        return api_body

    #=========================================================================
    # Function - Build api_body for vHBA Templates
    #=========================================================================
    def vhba_template(self, api_body, item, kwargs):
        akeys = list(api_body.keys())
        plist = []
        for k,v in kwargs.ezdata[self.type].allOf[1].properties.items():
            if re.search('_(polic(ies|y)|pool)$', k):
                plist.append(f"{k}:{v.intersight_api.split(':')[1]}")
        for p in plist:
            i,e = p.split(':')
            if e in akeys:
                if type(api_body[e]['Moid']) == list:
                    api_body[e]['Moid'] = []
                    for d in api_body[e]['Moid']:
                        ptype = re.search('([a-z\\_]+)_policies$', i).group(1)
                        org, pname = imm(ptype).seperate_org_pname(d, kwargs)
                        api_body[e]['Moid'].append(imm(self.type).get_moid_from_isight_dict(api_body['Name'], ptype, org, pname, kwargs))
                elif 'wwpn' in i:
                    org, pname = imm('wwpn').seperate_org_pname(api_body[e]['Moid'], kwargs)
                    api_body[e]['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'wwpn', org, pname, kwargs)
                else:
                    ptype      = re.search('([a-z\\_]+)_policy$', i).group(1)
                    org, pname = imm(ptype).seperate_org_pname(api_body[e]['Moid'], kwargs)
                    api_body[e]['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], ptype, org, pname, kwargs)
        return api_body

    #=========================================================================
    # Function - Virtual Media Policy Modification
    #=========================================================================
    def virtual_media(self, api_body, item, kwargs):
        item = item
        if api_body.get('Mappings'):
            for x in range(api_body['Mappings']):
                if api_body['Mappings'][x].get('Password'):
                    kwargs.sensitive_var = f"vmedia_password_{api_body['Mappings'][x]['Password']}"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    api_body['Mappings'][x]['Password'] = kwargs.var_value
                if   api_body['Mappings'][x].get('FileLocation') and api_body['Mappings'][x].get('MountProtocol') == 'cifs':
                    api_body['Mappings'][x]['MountProtocol'] = (api_body['Mappings'][x]['MountProtocol']).replace('cifs://', '')
                elif api_body['Mappings'][x].get('FileLocation') and api_body['Mappings'][x].get('MountProtocol') == 'nfs':
                    api_body['Mappings'][x]['MountProtocol'] = (api_body['Mappings'][x]['MountProtocol']).replace('nfs://', '')
        return api_body

    #=========================================================================
    # Function - Assign VLANs to VLAN Policies
    #=========================================================================
    def vlans(self, kwargs):
        #=====================================================================
        # Loop Through VLAN Lists to Create api_body(s)
        #=====================================================================
        def configure_vlans(e, kwargs):
            ezdata = kwargs.ezdata[self.type]
            api_body = {'EthNetworkPolicy':{'Moid':kwargs.parent_moid, 'ObjectType':'fabric.EthNetworkPolicy'}, 'ObjectType':ezdata.object_type}
            api_body = imm(self.type).build_api_body(api_body, ezdata.properties, e, kwargs)
            api_keys = list(api_body.keys())
            for i in ['Organization', 'Tags', 'name_prefix']:
                if i in api_keys: api_body.pop(i)
            if not api_body.get('AutoAllowOnUplinks'): api_body.update({'AutoAllowOnUplinks':False})
            org, pname = imm('multicast').seperate_org_pname(e.multicast_policy, kwargs)
            api_body['MulticastPolicy']['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], 'multicast', org, pname, kwargs)
            if not api_body.get('IsNative'): api_body['IsNative'] = False
            vkeys = list(e.keys())
            if not 'name_prefix' in vkeys: name_prefix = True
            else: name_prefix = e.name_prefix
            vlans = ezfunctions.vlan_list_full(e.vlan_list)
            for x in ezfunctions.vlan_list_full(e.vlan_list):
                if type(x) == str: x = int(x)
                if len(vlans) > 1 and name_prefix == True: api_body['Name'] = f"{e.name}{'0'*(4 - len(str(x)))}{x}"
                api_body['VlanId'] = x
                #=============================================================
                # Create or Patch the VLANs via the Intersight API
                #=============================================================
                pkeys = list(kwargs.isight[kwargs.org].policies[self.type].keys())
                if not str(x) in pkeys: kwargs.bulk_list.append(deepcopy(api_body))
                else:
                    indx = next((index for (index, d) in enumerate(kwargs.vlans_results) if d['VlanId'] == x), None)
                    if not indx == None:
                        patch_vlan = imm(self.type).compare_body_result(api_body, kwargs.vlans_results[indx])
                        api_body['pmoid'] = kwargs.isight[kwargs.org].policies[self.type][str(x)]
                        if patch_vlan == True: kwargs.bulk_list.append(deepcopy(api_body))
                        else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; VLAN Policy: `{kwargs.parent_name}`, VLAN: `{x}`."\
                                          f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
                        api_body.pop('pmoid')
                    else: kwargs.bulk_list.append(deepcopy(api_body))
            return kwargs
        #=====================================================================
        # Get Multicast Policies
        #=====================================================================
        mcast_names = []
        for i in kwargs.policies:
            if i.get('vlans'):
                for e in i.vlans:
                    org, policy = imm('multicast').seperate_org_pname(e.multicast_policy, kwargs)
                    pkeys       = list(kwargs.isight[org].policies['multicast'].keys())
                    if not policy in pkeys: mcast_names.append(f'{org}/{policy}')
        mcast_names = list(numpy.unique(numpy.array(mcast_names)))
        kwargs      = api_get(False, mcast_names, 'multicast', kwargs)
        #=====================================================================
        # Loop Through VLAN Policies
        #=====================================================================
        kwargs.bulk_list = []
        np, ns = ezfunctions.name_prefix_suffix('vlan', kwargs)
        for i in kwargs.policies:
            kwargs.bulk_list = []
            vnames           = []
            kwargs.parent_key  = self.type.split('.')[0]
            kwargs.parent_name = f'{np}{i.name}{ns}'
            kwargs.parent_type = 'VLAN Policy'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policies['vlan'][kwargs.parent_name]
            kwargs.pmoid       = kwargs.parent_moid
            kwargs.vlan_policy = kwargs.parent_name
            if i.get('vlans'):
                for e in i.vlans: vnames.extend(ezfunctions.vlan_list_full(e.vlan_list))
                kwargs = api_get(True, vnames, self.type, kwargs)
                kwargs.vlans_results = kwargs.results
                for e in i.vlans: kwargs = configure_vlans(e, kwargs)
            #=================================================================
            # POST Bulk Request if Post List > 0
            #=================================================================
            if len(kwargs.bulk_list) > 0:
                kwargs.uri = kwargs.ezdata[self.type].intersight_uri
                kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - vNIC Placement Settings
    #=========================================================================
    def vnic_placement(self, api_body, item, x, kwargs):
        ikeys = list(item.keys())
        if 'template' in self.type: switch_id = 'A'
        else: switch_id = chr(ord('@')+x+1)
        pdict = {'Placement':{'AutoPciLink':False,'AutoSlotId':False,'ObjectType':'vnic.PlacementSettings','SwitchId':switch_id,'Uplink':0}}
        api_body.update(pdict)
        if 'placement' in ikeys:
            pkeys = list(item.placement.keys())
            for p in ['automatic_pci_link_assignment', 'automatic_slot_id_assignment', 'pci_links', 'slot_ids', 'switch_ids', 'uplink_ports']:
                if 'template' in self.type and re.search('ids|inks|ports', p): p = p[:-1]
                if p in pkeys:
                    if 'template' in self.type: pval = item[p]
                    elif type(item['placement'][p]) == bool: pval = item['placement'][p]
                    elif len(item['placement'][p]) == 2: pval = item['placement'][p][x]
                    else: pval = item['placement'][p][0]
                    api_body['Placement'][kwargs.ezdata[self.type].properties.placement.properties[p].intersight_api] = pval
        if not api_body['Placement'].get('Id'): api_body['Placement'].update({'AutoSlotId':True,'Id':''})
        if not api_body['Placement'].get('PciLink'): api_body['Placement'].update({'AutoPciLink':True,'PciLink':0})
        return api_body

    #=========================================================================
    # Function - vNIC Settings
    #=========================================================================
    def vnic_settings(self, api_body, x, kwargs):
        akeys = list(api_body.keys())
        if not api_body.get('Cdn'): api_body.update({'Cdn':{'Value':api_body['Name'],'Source':'vnic','ObjectType':'vnic.Cdn'}})
        if api_body.get('FabricEthNetworkGroupPolicy'):
            api_body['FabricEthNetworkGroupPolicy'] = [api_body['FabricEthNetworkGroupPolicy']]
        if api_body.get('StaticMacAddress'):
            if 'template' in self.type: api_body.update({'MacAddressType': 'STATIC'})
            else: api_body.update({'MacAddressType': 'STATIC','StaticMacAddress':api_body['StaticMacAddress'][x]})
        #=====================================================================
        # Usnic/Vmq Ethernet Adapter Policies
        #=====================================================================
        ptype = 'ethernet_adapter'
        for p in ['UsnicSettings:UsnicAdapterPolicy', 'VmqSettings:VmmqAdapterPolicy']:
            i,e = p.split(':')
            if i in akeys:
                skeys = list(api_body[i].keys())
                if e in skeys and len(api_body[i][e]) > 0:
                    org, pname     = imm(ptype).seperate_org_pname(api_body[i][e], kwargs)
                    api_body[i][e] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], ptype, org, pname, kwargs)
        return api_body

    #=========================================================================
    # Function - Build api_body for vNIC Templates
    #=========================================================================
    def vnic_template(self, api_body, item, kwargs):
        akeys = list(api_body.keys())
        plist = []
        for k,v in kwargs.ezdata[self.type].allOf[1].properties.items():
            if re.search('_(policy|pool)$', k):
                plist.append(f"{k}:{v.intersight_api.split(':')[1]}")
        for p in plist:
            i,e = p.split(':')
            if e in akeys:
                if 'mac' in i: ptype = 'mac'
                else: ptype = re.search('([a-z\\_]+)_policy$', i).group(1)
                org, pname = imm(ptype).seperate_org_pname(item[i], kwargs)
                api_body[e]['Moid'] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], ptype, org, pname, kwargs)
        ptype = 'ethernet_adapter'
        for p in ['UsnicSettings:UsnicAdapterPolicy', 'VmqSettings:VmmqAdapterPolicy']:
            i,e = p.split(':')
            if i in akeys:
                skeys = list(api_body[i].keys())
                if e in skeys and len(api_body[i][e]) > 0:
                    org, pname     = imm(ptype).seperate_org_pname(api_body[i][e], kwargs)
                    api_body[i][e] = imm(self.type).get_moid_from_isight_dict(api_body['Name'], ptype, org, pname, kwargs)
        if api_body.get('FabricEthNetworkGroupPolicy'): api_body['FabricEthNetworkGroupPolicy'] = [api_body['FabricEthNetworkGroupPolicy']]
        return api_body

    #=========================================================================
    # Function - vHBA/vNICs from Template Merge Data
    #=========================================================================
    def vnic_template_settings(self, api_body, item, kwargs):
        vtype = f"{re.search('(vhba|vnic)s_from_template', self.type).group(1)}_template"
        indx  = next((index for (index, d) in enumerate(kwargs.template_results) if d['Moid'] == api_body['SrcTemplate']['Moid']), None)
        if indx != None:
            t = kwargs.template_results[indx]; policies = ['PinGroupName']
            for k,v in kwargs.ezdata[self.type].properties.items():
                if re.search('polic(ies|y)|pool', k): policies.append(re.search("ref:([a-zA-Z]+):", v.intersight_api).group(1))
            if t['EnableOverride'] != True:
                for d in policies:
                    if type(t[d]) == kwargs.type_dotmap: api_body[d] = t[d].toDict()
                    else: api_body[d] = t[d]
                api_body['Placement']['SwitchId'] = t['SwitchId']
                api_body['PinGroupName'] = t[d]
            else:
                for d in policies:
                    if not api_body.get(d):
                        if type(t[d]) == kwargs.type_dotmap: api_body[d] = t[d].toDict()
                        else: api_body[d] = t[d]
            tpolicies = []
            if 'vnic' in self.type: tdata = kwargs.ezdata['vnic_template'].allOf[1].properties
            else: tdata = kwargs.ezdata['vhba_template'].allOf[1].properties.items()
            for k,v in tdata.items():
                if 'policy' in k:
                    p = re.search('ref:([a-zA-Z]+):', v.intersight_api).group(1)
                    if not p in policies: tpolicies.append(p)
            for d in tpolicies:
                if not api_body.get(d):
                    if type(t[d]) == list: api_body[d] = [f.toDict() for f in t[d]]
                    else: api_body[d] = t[d].toDict()
            if 'vnic' in self.type:
                api_body['Cdn'] = t['Cdn'].toDict()
                if api_body['Cdn']['Source'] == 'user': api_body['Cdn']['Value'] = item.cdn_value
                else: api_body['Cdn']['Value'] = api_body['Name']
                for d in ['FailoverEnabled']: api_body[d] = t[d]
                def update_api_body_keys(api_body):
                    for d in ['SriovSettings', 'UsnicSettings', 'VmqSettings']: api_body[d] = t[d].toDict()
                    return api_body
                if   t['SriovSettings']['Enabled'] == True: api_body = update_api_body_keys(api_body)
                elif t['UsnicSettings']['Count'] > 0:       api_body = update_api_body_keys(api_body)
                elif t['VmqSettings']['Enabled'] == True:   api_body = update_api_body_keys(api_body)
            else:
                for d in ['PersistentBindings', 'Type']: api_body[d] = t[d]
        else:
            np,ns = ezfunctions.name_prefix_suffix(vtype, kwargs)
            validating.error_policy_doesnt_exist(self.type, api_body['Name'], vtype, f'{np}{item[vtype]}{ns}')
        return api_body

    #=========================================================================
    # Function - Assign VNICs to LAN Connectivity Policies
    #=========================================================================
    def vnics(self, kwargs):
        ezdata             = kwargs.ezdata[self.type]
        kwargs.bulk_list   = []
        sts                = self.type.split('.')
        kwargs.vpolicy     = (kwargs.ezdata[sts[0]].object_type).split('.')[1]
        kwargs.parent_key  = self.type.split('.')[0]
        kwargs.parent_type = (snakecase(kwargs.vpolicy).replace('_', ' ')).title()
        vtype              = sts[1]
        #=====================================================================
        # Get Policies and Pools
        #=====================================================================
        kwargs.cp = DotMap()
        for item in kwargs.policies:
            for i in item[vtype]:
                kwargs = imm(self.type).policy_existing_check(i, kwargs)
        for e in list(kwargs.cp.keys()):
            if len(kwargs.cp[e].names) > 0:
                names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                kwargs = api_get(False, names, e, kwargs)
                if 'template' in e: kwargs.template_results = kwargs.results
        #=====================================================================
        # Create API Body for vHBAs/vNICs
        #=====================================================================
        for item in kwargs.policies:
            np, ns = ezfunctions.name_prefix_suffix(self.type.split('.')[0], kwargs)
            kwargs.parent_name = f'{np}{item.name}{ns}'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policies[self.type.split('.')[0]][kwargs.parent_name]
            kwargs.pmoid       = kwargs.parent_moid
            names   = []
            for i in item[vtype]: 
                if 'template' in self.type: names.append(i.name)
                else: names.extend(i.names)
            kwargs       = api_get(True, names, self.type, kwargs)
            vnic_results = kwargs.results
            vnic_keys    = list(kwargs.isight[kwargs.org].policies[self.type].keys())
            #=================================================================
            # Function - vNIC Loop - Build API Body
            #=================================================================
            def vnic_loop(i, x, kwargs):
                api_body = {kwargs.vpolicy:{'Moid':kwargs.parent_moid,'ObjectType':f'vnic.{kwargs.vpolicy}'}, 'ObjectType':ezdata.object_type}
                api_body = imm(self.type).build_api_body(api_body, ezdata.properties, i, kwargs)
                if not 'template' in self.type: api_body.update({'Name':i.names[x]})
                api_body.pop('Organization')
                if 'template' in self.type: api_body['Order'] = i.placement.pci_order
                else: api_body['Order'] = i.placement.pci_order[x]
                #=============================================================
                # Assign Pool/Policy/Template Moids
                #=============================================================
                for k, v in i.items():
                    if re.search('(_polic(ies|y)|_pool(s)?|_template)$', k):
                        ptype = (((k.replace('_policies', '')).replace('_address_pools', '')).replace('_pools', '')).replace('_policy', '')
                        if type(v) == list:
                            if len(v) >= 2: pname = v[x]
                            else: pname = v[0]
                        else: pname = v
                        org, pname = imm(ptype).seperate_org_pname(pname, kwargs)
                        pmoid      = imm(self.type).get_moid_from_isight_dict(api_body['Name'], ptype, org, pname, kwargs)
                        api_body[ezdata.properties[k].intersight_api.split(':')[1]]['Moid'] = pmoid
                #=============================================================
                # vHBA/vNIC specific settings
                #=============================================================
                if 'vnics' in self.type: api_body = imm(self.type).vnic_settings(api_body, x, kwargs)
                else: api_body = imm(self.type).vhba_settings(api_body, i, x, kwargs)
                #=============================================================
                # Update Placement Settings
                #=============================================================
                api_body = imm(self.type).vnic_placement(api_body, i, x, kwargs)
                #=============================================================
                # vHBA/vNIC Template Specific Settings
                #=============================================================
                if 'template' in self.type: api_body = imm(self.type).vnic_template_settings(api_body, i, kwargs)
                api_body = dict(sorted(api_body.items()))
                #=========================================================
                # Create or Patch the vHBA/vNICs via the Intersight API
                #=========================================================
                if api_body['Name'] in vnic_keys:
                    indx              = next((index for (index, d) in enumerate(vnic_results) if d['Name'] == api_body['Name']), None)
                    patch_vnics       = imm(self.type).compare_body_result(api_body, vnic_results[indx])
                    api_body['pmoid'] = kwargs.isight[kwargs.org].policies[self.type][api_body['Name']]
                    if patch_vnics == True: kwargs.bulk_list.append(deepcopy(api_body))
                    else:
                        pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {kwargs.parent_type} `{kwargs.parent_name}`: VNIC: `{api_body['Name']}`."\
                            f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
                else: kwargs.bulk_list.append(deepcopy(api_body))
                return kwargs
            #=================================================================
            # Loop Through vHBA/vNICs
            #=================================================================
            for i in item[vtype]:
                if 'template' in self.type: kwargs = vnic_loop(i, 99, kwargs)
                else:
                    for x in range(len(i.names)): kwargs = vnic_loop(i, x, kwargs)
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri    = ezdata.intersight_uri
            kwargs        = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign VSANs to VSAN Policies
    #=========================================================================
    def vsans(self, kwargs):
        #=====================================================================
        # Loop Through VLAN Lists
        #=====================================================================
        def configure_vsans(e, kwargs):
            ezdata = kwargs.ezdata[self.type]
            api_body = {'FcNetworkPolicy':{'Moid':kwargs.parent_moid, 'ObjectType':'fabric.FcNetworkPolicy'}, 'ObjectType':ezdata.object_type}
            api_body = imm(self.type).build_api_body(api_body, ezdata.properties, e, kwargs)
            api_body.pop('Organization'); api_body.pop('Tags')
            if not api_body.get('VsanScope'): api_body['VsanScope'] = 'Uplink'
            if not api_body.get('FcoeVlan'): api_body['FcoeVlan'] = api_body['VsanId']
            #=================================================================
            # Create or Patch the VLANs via the Intersight API
            #=================================================================
            if not str(api_body['VsanId']) in kwargs.vsans_keys: kwargs.bulk_list.append(deepcopy(api_body))
            else:
                indx = next((index for (index, d) in enumerate(kwargs.vsans_results) if d['VsanId'] == api_body['VsanId']), None)
                patch_vsan = imm(self.type).compare_body_result(api_body, kwargs.vsans_results[indx])
                api_body['pmoid']  = kwargs.isight[kwargs.org].policies[self.type][str(api_body['VsanId'])]
                if patch_vsan == True: kwargs.bulk_list.append(deepcopy(api_body))
                else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; VSAN Policy: `{kwargs.parent_name}`, VSAN: `{api_body['VsanId']}`."\
                                  f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
            return kwargs
        #=====================================================================
        # Loop Through VSAN Policies
        #=====================================================================
        kwargs.bulk_list = []
        np, ns = ezfunctions.name_prefix_suffix('vsan', kwargs)
        for i in kwargs.policies:
            ikeys  = list(i.keys())
            vnames = []
            kwargs.parent_key  = self.type.split('.')[0]
            kwargs.parent_name = f'{np}{i.name}{ns}'
            kwargs.parent_type = 'VSAN Policy'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policies[self.type.split('.')[0]][kwargs.parent_name]
            kwargs.pmoid       = kwargs.parent_moid
            if 'vsans' in ikeys:
                for e in i.vsans: vnames.append(e.vsan_id)
                kwargs = api_get(True, vnames, self.type, kwargs)
                kwargs.vsans_results= kwargs.results
                kwargs.vsans_keys = list(kwargs.isight[kwargs.org].policies[self.type].keys())
                #=============================================================
                # Create API Body for VSANs
                #=============================================================
                for e in i.vsans: kwargs = configure_vsans(e, kwargs)
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

#=============================================================================
# IMM Class
#=============================================================================
class software_repository(object):
    def __init__(self, type): self.type = type

    #=========================================================================
    # Function - Build Azure Stack HCI Operating System Auto Install File
    #=========================================================================
    def os_cfg_azure_stack(self, kwargs):
        #=====================================================================
        # Load Windows Languages and Timezone
        #=====================================================================
        #windows_language = DotMap(language_pack  = kwargs.imm_dict.wizard.windows_install.language_pack,
        #                          layered_driver = kwargs.imm_dict.wizard.windows_install.layered_driver)
        windows_language = DotMap(language_pack = 'English - United States', layered_driver = 0)
        kwargs = ezfunctions.windows_languages(windows_language, kwargs)
        kwargs = ezfunctions.windows_timezones(kwargs)
        #=====================================================================
        # Upload the Operating System Configuration File
        #=====================================================================
        answer        = os.path.join(kwargs.script_path, 'examples', 'azure_stack_hci', '23H2', 'AzureStackHCIIntersight.xml')
        vsplist       = (kwargs.os_version.name.split(' '))
        version       = f'{vsplist[0]}{vsplist[2]}'
        ctemplate     = answer.split(os.sep)[-1]
        template_name = version + '-' + ctemplate.split('_')[0]
        kwargs.os_config_template = template_name
        if not kwargs.distributions.get(version):
            kwargs = kwargs | DotMap(api_filter = f"Version eq '{kwargs.os_version.name}'", build_skip = True, method = 'get', uri = 'hcl/OperatingSystems')
            kwargs = api('hcl_operating_system').calls(kwargs)
            kwargs.distributions[version].moid = kwargs.results[0].Moid
        kwargs.distribution_moid = kwargs.distributions[version].moid
        file_content = (open(os.path.join(answer), 'r')).read()
        for e in ['LayeredDriver:layered_driver', 'UILanguageFallback:secondary_language']:
            elist = e.split(':')
            rstring = '%s<%s>{{ .%s }}</%s>\n' % (" "*12, elist[0], elist[1], elist[0])
            if kwargs.language[elist[1]] == '': file_content = file_content.replace(rstring, '')
        kwargs.file_content = file_content
        api_body = ezfunctions.os_configuration_file(kwargs)
        existing = False
        for e in kwargs.os_cfg_results:
            if e.Name == api_body['Name'] and e.Distributions[0].Moid == kwargs.distribution_moid:
                existing = True; kwargs.pmoid = e.Moid; break
        kwargs = kwargs | DotMap(api_body = api_body, method = 'post', uri = 'os/ConfigurationFiles')
        if existing == True: kwargs.method = 'patch'
        kwargs = api('os_configuration').calls(kwargs)
        kwargs.os_cfg_moids[template_name] = DotMap(moid = kwargs.pmoid)
        kwargs.os_cfg_moid = kwargs.os_cfg_moids[template_name].moid
        if existing == False:
            kwargs.os_cfg_results.append(kwargs.results); kwargs.os_cfg_moids = kwargs.os_cfg_moids | kwargs.pmoids
        else:
            indx = next((index for (index, d) in enumerate(kwargs.os_cfg_results) if d.Moid == kwargs.pmoid), None)
            kwargs.os_cfg_results[indx] = kwargs.results
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - OS Configuration Files
    #=========================================================================
    def os_configuration(self, kwargs):
        org_moid = kwargs.org_moids[kwargs.org].moid
        kwargs   = kwargs | DotMap(api_filter = f"Name in ('{org_moid}','shared')", method = 'get', uri = 'os/Catalogs')
        kwargs   = api('os_catalog').calls(kwargs)
        catalog_moids = kwargs.pmoids
        kwargs.api_filter = f"Catalog.Moid in ('{catalog_moids[org_moid].moid}','{catalog_moids.shared.moid}')"
        kwargs = kwargs | DotMap(uri = 'os/ConfigurationFiles')
        kwargs = api('os_configuration').calls(kwargs)
        kwargs.org_catalog_moid = catalog_moids[org_moid].moid
        kwargs.os_cfg_moids     = kwargs.pmoids
        kwargs.os_cfg_results   = kwargs.results
        return kwargs

    #=========================================================================
    # Function - OS Image Links
    #=========================================================================
    def os_images(self, kwargs):
        # Get Organization Software Repository Catalog
        kwargs = kwargs | DotMap(method = 'get', names = ['user-catalog'], uri = 'softwarerepository/Catalogs')
        kwargs = api('org_catalog').calls(kwargs)
        catalog_moid = kwargs.pmoids['user-catalog'].moid
        # Get Organization Operating System Images
        kwargs = kwargs | DotMap(api_filter = f"Catalog.Moid eq '{catalog_moid}'", names = [], uri = 'softwarerepository/OperatingSystemFiles')
        kwargs = api('operating_system').calls(kwargs)
        kwargs.os_image_results = sorted(kwargs.results, key=itemgetter('CreateTime'), reverse=True)
        return kwargs

    #=========================================================================
    # Function - Vendor Operating Systems
    #=========================================================================
    def os_vendor_and_version(self, kwargs):
        org_moid                = kwargs.org_moids[kwargs.org].moid
        kwargs = kwargs | DotMap(api_filter = 'ignore', method = 'get', uri = 'hcl/OperatingSystemVendors')
        kwargs = api('os_vendors').calls(kwargs)
        kwargs.os_vendors = kwargs.pmoids
        kwargs = kwargs | DotMap(api_filter = 'ignore', method = 'get', uri = 'hcl/OperatingSystems')
        kwargs = api('os_vendors').calls(kwargs)
        kwargs.os_versions = kwargs.pmoids
        kwargs = kwargs | DotMap(api_filter = f"Name in ('{kwargs.org_moids[kwargs.org].moid}','shared')", method = 'get', uri = 'os/Catalogs')
        kwargs = api('os_catalog').calls(kwargs)
        catalog_moids = kwargs.pmoids
        api_filter = f"Catalog.Moid in ('{catalog_moids[org_moid].moid}','{catalog_moids.shared.moid}')"
        kwargs     = kwargs | DotMap(api_filter = api_filter, method = 'get', uri = 'os/ConfigurationFiles')
        kwargs     = api('os_configuration').calls(kwargs)
        kwargs.org_catalog_moid = catalog_moids[org_moid].moid
        kwargs.os_cfg_moids     = kwargs.pmoids
        kwargs.os_cfg_results   = kwargs.results
        return kwargs

    #=========================================================================
    # Function - SCU Links
    #=========================================================================
    def scu(self, kwargs):
        # Get Organization Software Repository Catalog
        kwargs = kwargs | DotMap(method = 'get', names = ['user-catalog'], uri = 'softwarerepository/Catalogs')
        kwargs = api('org_catalog').calls(kwargs)
        catalog_moid = kwargs.pmoids['user-catalog'].moid
        # Get Organization Software Configuration Utility Repositories
        kwargs = kwargs | DotMap(api_filter = f"Catalog.Moid eq '{catalog_moid}'", names = [], uri = 'firmware/ServerConfigurationUtilityDistributables')
        kwargs = api('server_configuration_utility').calls(kwargs)
        kwargs.scu_results = sorted(kwargs.results, key=itemgetter('CreateTime'), reverse=True)
        return kwargs

#=============================================================================
# Function - API Get Calls
#=============================================================================
def api_get(empty, names, otype, kwargs):
    original_org = kwargs.org; kwargs.glist = DotMap()
    for e in names:
        if '/' in str(e): org, policy = e.split('/')
        else: org = kwargs.org; policy = e
        if not kwargs.glist[org].names: kwargs.glist[org].names = []
        kwargs.glist[org].names.append(policy)
    orgs = list(kwargs.glist.keys()); results = []; pmoids  = DotMap()
    for org in orgs:
        kwargs = kwargs | DotMap(names = kwargs.glist[org].names, org = org, method = 'get', uri = kwargs.ezdata[otype].intersight_uri)
        kwargs = api(otype).calls(kwargs)
        if empty == False and kwargs.results == []: empty_results(kwargs)
        else:
            if kwargs.ezdata[otype].get('intersight_type'):
                for k, v in kwargs.pmoids.items():
                    ntype = (otype.replace('profiles.', '')).replace('templates.', '') if re.search('(profiles|templates)\\.', otype) else otype
                    kwargs.isight[org][kwargs.ezdata[otype].intersight_type][ntype][k] = v.moid
            if len(kwargs.results) > 0: results.extend(kwargs.results); pmoids = DotMap(dict(pmoids.toDict(), **kwargs.pmoids.toDict()))
    kwargs.org = original_org; kwargs.pmoids  = pmoids; kwargs.results = results
    return kwargs

#=============================================================================
# Function - Exit on Empty Results
#=============================================================================
def empty_results(kwargs): pcolor.Red(f"The API Query Results were empty for {kwargs.uri}.  Exiting..."); len(False); sys.exit(1)
