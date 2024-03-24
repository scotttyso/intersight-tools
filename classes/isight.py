#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, pcolor, validating
    from intersight_auth import IntersightAuth, repair_pem
    from copy import deepcopy
    from dotmap import DotMap
    from stringcase import snakecase
    import json, numpy, os, re, requests, time, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
serial_regex = re.compile('^[A-Z]{3}[2-3][\\d]([0][1-9]|[1-4][0-9]|[5][0-3])[\\dA-Z]{4}$')
part1 = 'adapter_configuration|bios|boot_order|(ethernet|fibre_channel)_adapter|firmware|imc_access|ipmi_over_lan|iscsi_(boot|static_target)'
part2 = '(l|s)an_connectivity|local_user|network_connectivity|snmp|storage|syslog|system_qos'
policy_specific_regex = re.compile(f'^{part1}|{part2}$')

#=======================================================
# API Class
#=======================================================
class api(object):
    def __init__(self, type):
        self.type = type

    #=============================================================================
    # Function - Build Compute Dictionary
    #=============================================================================
    def build_compute_dictionary(self, i, kwargs):
        kwargs.api_filter = f"Ancestors/any(t:t/Moid eq '{i.Moid}')"
        kwargs.method     = 'get'
        kwargs.uri        = 'processor/Units'
        kwargs            = api('processor').calls(kwargs)
        cpu               = kwargs.results[0]
        kwargs.api_filter = f"Ancestors/any(t:t/Moid eq '{i.Moid}')"
        kwargs.uri        = 'storage/Controllers'
        kwargs            = api('storage_controllers').calls(kwargs)
        storage           = kwargs.results
        kwargs.api_filter = f"Ancestors/any(t:t/Moid eq '{i.Moid}')"
        kwargs.uri        = 'equipment/Tpms'
        kwargs            = api('tpm').calls(kwargs)
        tpmd              = kwargs.results
        if 'Intel' in cpu.Vendor: cv = 'intel'
        else: cv = 'amd'
        storage_controllers = DotMap()
        for e in storage:
            if len(e.Model) > 0:
                mstring = 'Cisco Boot optimized M.2 Raid controller'
                if e.Model == mstring: storage_controllers['UCS-M2-HWRAID'] = e.ControllerId
                else: storage_controllers[e.Model] = e.ControllerId
        kwargs.api_filter = f"Ancestors/any(t:t/Moid eq '{i.Moid}')"
        kwargs.uri        = 'adapter/Units'
        kwargs            = api('adapter').calls(kwargs)
        vic               = kwargs.results
        vics              = []
        for e in vic:
            if re.search('(V5)', e.Model):    vic_generation = 'gen5'
            elif re.search('INTEL', e.Model): vic_generation = 'INTEL'
            elif re.search('MLNX', e.Model):  vic_generation = 'MLNX'
            else: vic_generation = 'gen4'
            if 'MLOM' in e.PciSlot:
                vic_slot = 'MLOM'
                vics.append(DotMap(vic_gen = vic_generation, vic_slot = vic_slot))
            elif not 'MEZZ' in e.PciSlot and 'SlotID' in e.PciSlot:
                vic_slot = re.search('SlotID:(\\d)', e.PciSlot).group(1)
                vics.append(DotMap(vic_gen = vic_generation, vic_slot = vic_slot))
            elif re.search("\\d", str(e.PciSlot)):
                vic_slot = int(e.PciSlot)
                vics.append(DotMap(vic_gen = vic_generation, vic_slot = vic_slot))
        sg = re.search('-(M[\\d])', i.Model).group(1)
        if i.SourceObjectType == 'compute.RackUnit': ctype = 'rack'
        else: ctype = 'blade'
        if len(vics) > 0:
            if type(vics[0].vic_slot) == str: vs1= (vics[0].vic_slot).lower()
            else: vs1= vics[0].vic_slot
            if len(vics) == 2:
                if type(vics[1].vic_slot) == str: vs2= (vics[1].vic_slot).lower()
                else: vs2= vics[1].vic_slot
        if   kwargs.boot_volume.lower() == 'san': boot_type = 'fcp'
        else: boot_type = kwargs.boot_volume.lower()
        if self.type == 'azurestack':
            if len(tpmd) > 0: tpm = 'tpm'; template = f"{sg}-{cv}-azure-{ctype}-{boot_type}-tpm"
            else:             tpm = '';    template = f"{sg}-{cv}-azure-{ctype}-{boot_type}"
        elif len(tpmd) > 0:
            tpm = 'tpm'
            if len(vics) > 1:
                template   = f"{sg}-{cv}-tpm-{ctype}-{boot_type}-vic-{vics[0].vic_gen}-{vs1}-{vs2}"
            else: template = f"{sg}-{cv}-tpm-{ctype}-{boot_type}-vic-{vics[0].vic_gen}-{vs1}"
        else:
            tpm = ''
            if len(vics) > 1:
                template   = f"{sg}-{cv}-{ctype}-{boot_type}-vic-{vics[0].vic_gen}-{vs1}-{vs2}"
            else: template = f"{sg}-{cv}-{ctype}-{boot_type}-vic-{vics[0].vic_gen}-{vs1}"
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
        # Return kwargs
        return kwargs

    #=======================================================
    # Perform API Calls to Intersight
    #=======================================================
    def calls(self, kwargs):
        #=======================================================
        # Global options for debugging
        # 1 - Shows the api request response status code
        # 5 - Show URL String + Lower Options
        # 6 - Adds Results + Lower Options
        # 7 - Adds json payload + Lower Options
        # Note: payload shows as pretty and straight to check
        #       for stray object types like Dotmap and numpy
        #=======================================================
        debug_level   = kwargs.args.debug_level
        #=======================================================
        # Authenticate to the API
        #=======================================================
        if not re.search('^(organization|resource)/', kwargs.uri): org_moid = kwargs.org_moids[kwargs.org].moid
        #=======================================================
        # Authenticate to the API
        #=======================================================
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
        #=======================================================
        # Setup API Parameters
        #=======================================================
        def api_calls(kwargs):
            #=======================================================
            # Perform the apiCall
            #=======================================================
            aargs   = kwargs.api_args
            aauth   = kwargs.api_auth
            moid    = kwargs.pmoid
            payload = kwargs.api_body
            retries = 3
            uri     = kwargs.uri
            url     = kwargs.args.url
            for i in range(retries):
                try:
                    def send_error():
                        pcolor.Red(json.dumps(kwargs.api_body, indent=4))
                        pcolor.Red(kwargs.api_body)
                        pcolor.Red(f'!!! ERROR !!!')
                        if kwargs.method == 'get_by_moid': pcolor.Red(f'  URL: {url}/api/v1/{uri}/{moid}')
                        elif kwargs.method ==    'delete': pcolor.Red(f'  URL: {url}/api/v1/{uri}/{moid}')
                        elif kwargs.method ==       'get': pcolor.Red(f'  URL: {url}/api/v1/{uri}{aargs}')
                        elif kwargs.method ==     'patch': pcolor.Red(f'  URL: {url}/api/v1/{uri}/{moid}')
                        elif kwargs.method ==      'post': pcolor.Red(f'  URL: {url}/api/v1/{uri}')
                        pcolor.Red(f'  Running Process: {kwargs.method} {self.type}')
                        pcolor.Red(f'    Error status is {status}')
                        for k, v in (response.json()).items(): pcolor.Red(f"    {k} is '{v}'")
                        sys.exit(1)
                    if 'get_by_moid' in kwargs.method: response = requests.get(   f'{url}/api/v1/{uri}/{moid}', auth=aauth)
                    elif 'delete' in kwargs.method:    response = requests.delete(f'{url}/api/v1/{uri}/{moid}', auth=aauth)
                    elif 'get' in kwargs.method:       response = requests.get(   f'{url}/api/v1/{uri}{aargs}', auth=aauth)
                    elif 'patch' in kwargs.method:     response = requests.patch( f'{url}/api/v1/{uri}/{moid}', auth=aauth, json=payload)
                    elif 'post' in kwargs.method:      response = requests.post(  f'{url}/api/v1/{uri}',        auth=aauth, json=payload)
                    status = response
                    if re.search('40[0|3]', str(status)):
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
                    elif not re.search('(20[0-9])', str(status)): send_error()
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
                        pcolor.Red(f"Exception when calling {kwargs.uri}: {e}\n")
                        sys.exit(1)
                break
            #=======================================================
            # Print Debug Information if Turned on
            #=======================================================
            api_results = DotMap(response.json())
            if int(debug_level) >= 1: pcolor.Cyan(str(response))
            if int(debug_level)>= 5:
                if kwargs.method == 'get_by_moid': pcolor.Cyan(f'  URL: {url}/api/v1/{uri}/{moid}')
                elif kwargs.method ==       'get': pcolor.Cyan(f'  URL: {url}/api/v1/{uri}{aargs}')
                elif kwargs.method ==     'patch': pcolor.Cyan(f'  URL: {url}/api/v1/{uri}/{moid}')
                elif kwargs.method ==      'post': pcolor.Cyan(f'  URL: {url}/api/v1/{uri}')
            if int(debug_level) >= 6: pcolor.Cyan(api_results)
            if int(debug_level) == 7:
                pcolor.Cyan(json.dumps(payload, indent=4))
                pcolor.Cyan(json.dumps(dict(response.headers), indent=4))
            #=======================================================
            # Gather Results from the apiCall
            #=======================================================
            results_keys = list(api_results.keys())
            if 'Results' in results_keys: kwargs.results = api_results.Results
            else: kwargs.results = api_results
            if not kwargs.build_skip == True: kwargs.build_skip = False
            if 'post' in kwargs.method:
                if api_results.get('Responses'):
                    api_results['Results'] = deepcopy(api_results['Responses'])
                    kwargs.pmoids = api.build_pmoid_dictionary(self, api_results, kwargs)
                elif re.search('bulk.(MoCloner|Request)', api_results.ObjectType):
                    kwargs.pmoids = api.build_pmoid_dictionary(self, api_results, kwargs)
                else:
                    kwargs.pmoid = api_results.Moid
                    if kwargs.api_body.get('Name'): kwargs.pmoids[kwargs.api_body['Name']] = kwargs.pmoid
            elif 'inventory' in kwargs.uri: icount = 0
            elif kwargs.build_skip == False: kwargs.pmoids = api.build_pmoid_dictionary(self, api_results, kwargs)
            #=======================================================
            # Print Progress Notifications
            #=======================================================
            if re.search('(patch|post)', kwargs.method):
                if api_results.get('Responses'):
                    for e in api_results.Responses:
                        kwargs.api_results = e.Body
                        validating.completed_item(self.type, kwargs)
                elif re.search('bulk.Request', api_results.ObjectType):
                    for e in api_results.Results:
                        kwargs.api_results = e.Body
                        if 'bulk.Request' in api_results.ObjectType:
                            if e.Body.get('Name'): name_key = 'Name'
                            elif e.Body.get('Identity'): name_key = 'Identity'
                            elif e.Body.get('PcId'): name_key = 'PcId'
                            elif e.Body.get('PortId'): name_key = 'PortId'
                            elif e.Body.get('PortIdStart'): name_key = 'PortIdStart'
                            elif e.Body.get('VlanId'): name_key = 'VlanId'
                            elif e.Body.get('VsanId'): name_key = 'VsanId'
                            elif e.Body.ObjectType == 'iam.EndPointUserRole': icount = 0
                            else:
                                pcolor.Red(json.dumps(e.Body, indent=4))
                                pcolor.Red('Missing name_key.  isight.py line 164')
                                sys.exit(1)
                            if not e.Body['ObjectType'] == 'iam.EndPointUserRole':
                                indx = next((index for (index, d) in enumerate(kwargs.api_body['Requests']) if d['Body'][name_key] == e.Body[name_key]), None)
                                kwargs.method = (kwargs.api_body['Requests'][indx]['Verb']).lower()
                        validating.completed_item(self.type, kwargs)
                else:
                    kwargs.api_results = api_results
                    validating.completed_item(self.type, kwargs)
            return kwargs
        #=======================================================
        # Pagenation for Get > 1000
        #=======================================================
        if kwargs.method == 'get':
            def build_api_args(kwargs):
                if not kwargs.get('api_filter'):
                    regex1 = re.compile('registered_device|resource_groups|workflow_os_install')
                    regex2 = re.compile('(ip|iqn|mac|uuid|wwnn|wwpn)_leases')
                    if re.search('(vlans|vsans|port.port_)', self.type): names = ", ".join(map(str, kwargs.names))
                    else: names = "', '".join(kwargs.names).strip("', '")
                    if re.search('(organization|resource_group)', self.type): api_filter = f"Name in ('{names}')"
                    else: api_filter = f"Name in ('{names}') and Organization.Moid eq '{org_moid}'"
                    if 'asset_target' == self.type:          api_filter = f"TargetId in ('{names}')"
                    elif 'connectivity.vhbas' in self.type:  api_filter = f"Name in ('{names}') and SanConnectivityPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'connectivity.vnics' in self.type:  api_filter = f"Name in ('{names}') and LanConnectivityPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'hcl_status' == self.type:          api_filter = f"ManagedObject.Moid in ('{names}')"
                    elif 'iam_role' == self.type:            api_filter = f"Name in ('{names}') and Type eq 'IMC'"
                    elif 'port.port_channel_' in self.type:  api_filter = f"PcId in ({names}) and PortPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'port.port_modes' == self.type:     api_filter = f"PortIdStart in ({names}) and PortPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'port.port_role_' in self.type:     api_filter = f"PortId in ({names}) and PortPolicy.Moid eq '{kwargs.pmoid}'"
                    elif re.search(regex1, self.type):       api_filter = f"Moid in ('{names}')"
                    elif re.search(regex2, self.type):       api_filter = f"{kwargs.pkey} in ('{names}')"
                    elif 'reservations' in self.type:        api_filter = f"Identity in ('{names}')"
                    elif 'serial_number' == self.type:       api_filter = f"Serial in ('{names}')"
                    elif 'storage.drive_groups' == self.type:api_filter = f"Name in ('{names}') and StoragePolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'switch' == self.type:              api_filter = f"Name in ('{names}') and SwitchClusterProfile.Moid eq '{kwargs.pmoid}'"
                    elif 'user_role' == self.type:           api_filter = f"EndPointUser.Moid in ('{names}') and EndPointUserPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'vlan.vlans' == self.type:          api_filter = f"VlanId in ({names}) and EthNetworkPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'vsan.vsans' == self.type:          api_filter = f"VsanId in ({names}) and FcNetworkPolicy.Moid eq '{kwargs.pmoid}'"
                    elif 'wwnn_pool_leases' == self.type:    api_filter = f"PoolPurpose eq 'WWNN' and AssignedToEntity.Moid in ('{names}')"
                    elif 'wwpn_pool_leases' == self.type:    api_filter = f"PoolPurpose eq 'WWPN' and AssignedToEntity.Moid in ('{names}')"
                    elif re.search('ww(n|p)n', self.type):   api_filter = api_filter + f" and PoolPurpose eq '{self.type.upper()}'"
                    if kwargs.top1000 == True and len(kwargs.api_filter) > 0: api_args = f'?$filter={kwargs.api_filter}&$top=1000'
                    elif len(kwargs.names) > 99: api_args = f'?$filter={api_filter}&$top=1000'
                    elif kwargs.top1000 == True: api_args = '?$top=1000'
                    elif api_filter == '': ''
                    else: api_args = f'?$filter={api_filter}'
                elif kwargs.api_filter == 'ignore': api_args=''
                else: api_args = f'?$filter={kwargs.api_filter}'
                return api_args

            if len(kwargs.names) > 1000:
                chunked_list = list(); chunk_size = 1000
                for i in range(0, len(kwargs.names), chunk_size):
                    chunked_list.append(kwargs.names[i:i+chunk_size])
                results     = []
                moid_dict   = {}
                parent_moid = kwargs.pmoid
                for i in chunked_list:
                    kwargs.names = i
                    kwargs.api_args = build_api_args(kwargs)
                    if re.search('leases|port.port|reservations|user_role|vhbas|vlans|vsans|vnics', self.type):
                        kwargs.pmoid = parent_moid
                    kwargs = api_calls(kwargs)
                    results.extend(kwargs.results)
                    moid_dict = dict(moid_dict, **kwargs.pmoids.toDict())
                kwargs.pmoids = DotMap(moid_dict)
                kwargs.results = results
            else:
                api_args = build_api_args(kwargs)
                if '?' in api_args: kwargs.api_args = api_args + '&$count=True'
                else: kwargs.api_args = api_args + '?$count=True'
                kwargs = api_calls(kwargs)
                if kwargs.results.Count <= 1000:
                    kwargs.api_args = api_args
                    kwargs = api_calls(kwargs)
                else:
                    get_count    = kwargs.results.Count
                    moid_dict    = {}
                    offset_count = 0
                    results      = []
                    while get_count > 0:
                        if 'top=1000' in api_args: kwargs.api_args = api_args + f'&$skip={offset_count}'
                        else: api_args + f'&$top=1000&$skip={offset_count}'
                        kwargs = api_calls(kwargs)
                        results.extend(kwargs.results)
                        moid_dict    = dict(moid_dict, **kwargs.pmoids.toDict())
                        get_count    = get_count - 1000
                        offset_count = offset_count + 1000
                    kwargs.pmoids = DotMap(moid_dict)
                    kwargs.results = results
        else:
            kwargs.api_args = ''
            kwargs = api_calls(kwargs)
        #=======================================================
        # Return kwargs
        #=======================================================
        if kwargs.get('api_filter'): kwargs.pop('api_filter')
        if kwargs.get('build_skip'): kwargs.pop('build_skip')
        if kwargs.get('top1000'): kwargs.pop('top1000')
        return kwargs

    #=====================================================
    # Process API Results
    #=====================================================
    def build_pmoid_dictionary(self, api_results, kwargs):
        api_dict = DotMap()
        if not kwargs.build_skip == True and api_results.get('Results'):
            for i in api_results.Results:
                if i.get('Body'): i = i.Body
                if i.get('VlanId'): iname = str(i.VlanId)
                elif i.get('PcId'): iname = str(i.PcId)
                elif i.get('PortId'): iname = str(i.PortId)
                elif i.ObjectType == 'asset.DeviceRegistration': iname = i.Serial[0]
                elif i.get('Serial'): iname = i.Serial
                elif i.get('VsanId'): iname = str(i.VsanId)
                elif i.get('Answers'): iname = i.Answers.Hostname
                elif i.get('Name'): iname = i.Name
                elif self.type == 'upgrade':
                    if i.Status == 'IN_PROGRESS': iname = kwargs.srv_moid
                elif i.get('SocketDesignation'): iname = i.Dn
                elif i.get('EndPointUser'): iname = i.EndPointUser.Moid
                elif i.get('PortIdStart'): iname = str(i.PortIdStart)
                elif i.get('Version'): iname = i.Version
                elif i.get('ControllerId'): iname = i.ControllerId
                elif i.get('Identity'): iname = i.Identity
                elif i.get('MacAddress'): iname = i.MacAddress
                elif i.get('WWnId'): iname = i.WWnId
                elif i.get('IpV4Address'): iname = i.IpV4Address
                elif i.get('IpV6Address'): iname = i.IpV6Address
                elif i.get('IqnAddress'): iname = i.IqnAddress
                elif i.get('Uuid'): iname = i.Uuid
                elif i.get('PciSlot'): iname = str(i.PciSlot)
                if i.get('PcId') or i.get('PortId') or i.get('PortIdStart'):
                    api_dict[i.PortPolicy.Moid][iname].moid = i.Moid
                else: api_dict[iname].moid = i.Moid
                if i.get('IpV4Config'): api_dict[iname].ipv4_config = i.IpV4Config
                if i.get('IpV6Config'): api_dict[iname].ipv6_config = i.IpV6Config
                if i.get('ManagementMode'): api_dict[iname].management_mode = i.ManagementMode
                if i.get('MgmtIpAddress'): api_dict[iname].management_ip_address = i.MgmtIpAddress
                if i.get('Model'):
                    api_dict[iname].model = i.Model
                    api_dict[iname].name = i.Name
                    api_dict[iname].object_type = i.ObjectType
                    api_dict[iname].registered_device = i.RegisteredDevice.Moid
                    if i.get('ChassisId'): api_dict[iname].id = i.ChassisId
                    if i.get('SourceObjectType'): api_dict[iname].object_type = i.SourceObjectType
                if i.get('PolicyBucket'): api_dict[iname].policy_bucket = i.PolicyBucket
                if i.get('Selectors'): api_dict[iname].selectors = i.Selectors
                if i.get('Source'):
                    if i.Source.get('LocationLink'): api_dict[iname].url = i.Source.LocationLink
                if i.get('SwitchId'): api_dict[iname].switch_id = i.SwitchId
                if i.get('Tags'): api_dict[iname].tags = i.Tags
                if i.get('UpgradeStatus'): api_dict[iname].upgrade_status = i.UpgradeStatus
                if i.get('WorkflowInfo'): api_dict[iname].workflow_moid = i.WorkflowInfo.Moid
                if i.get('Profiles'):
                    api_dict[iname].profiles = []
                    for x in i['Profiles']:
                        xdict = DotMap(Moid=x.Moid,ObjectType=x.ObjectType)
                        api_dict[iname].profiles.append(xdict)
        return api_dict

    #=======================================================
    # Get Organizations from Intersight
    #=======================================================
    def all_organizations(self, kwargs):
        #=======================================================
        # Get Organization List from the API
        #=======================================================
        kwargs.api_filter= 'ignore'
        kwargs.method    = 'get'
        kwargs.uri       = 'organization/Organizations'
        kwargs           = api(self.type).calls(kwargs)
        kwargs.org_moids = kwargs.pmoids
        for k, v in kwargs.org_moids.items(): kwargs.org_names[v.moid] = k
        return kwargs

    #=======================================================
    # Get Organizations from Intersight
    #=======================================================
    def organizations(self, kwargs):
        kwargs.method    = 'get'
        kwargs.names     = kwargs.orgs
        kwargs.uri       = 'resource/Groups'
        kwargs           = api('resource_group').calls(kwargs)
        kwargs.rsg_moids = kwargs.pmoids
        kwargs.rsg_results = kwargs.results
        #=======================================================
        # Get Organization List from the API
        #=======================================================
        kwargs.uri         = 'organization/Organizations'
        kwargs             = api('organization').calls(kwargs)
        kwargs.org_moids   = kwargs.pmoids
        kwargs.org_results = kwargs.results
        for org in kwargs.orgs:
            create_rsg = False
            if org in kwargs.org_moids:
                indx = next((index for (index, d) in enumerate(kwargs.org_results) if d['Name'] == org), None)
                if indx == None: create_rsg = True
                else:
                    if len(kwargs.org_results[indx].ResourceGroups) == 0:
                        if len(kwargs.org_results[indx].SharedWithResources) == 0: create_rsg = True
            else: create_rsg = True
            if create_rsg == True:
                kwargs.org      = org
                kwargs.api_body = {'Description':f'{org} Resource Group', 'Name':org}
                kwargs.method   = 'post'
                kwargs.uri      = 'resource/Groups'
                kwargs          = api(self.type).calls(kwargs)
                kwargs.rsg_moids[org].moid      = kwargs.results.Moid
                kwargs.rsg_moids[org].selectors = kwargs.results.Selectors
            if not org in kwargs.org_moids:
                kwargs.api_body = {'Description':f'{org} Organization', 'Name':org,
                                   'ResourceGroups':[{'Moid': kwargs.rsg_moids[org].moid, 'ObjectType': 'resource.Group'}]}
                kwargs.method = 'post'
                kwargs.uri    = 'organization/Organizations'
                kwargs        = api(self.type).calls(kwargs)
                kwargs.org_moids[org].moid = kwargs.results.Moid
        return kwargs

#=======================================================
# Policies Class
#=======================================================
class imm(object):
    def __init__(self, type): self.type = type

    #=======================================================
    # BIOS Policy Modification
    #=======================================================
    def adapter_configuration(self, api_body, item, kwargs):
        item = item; kwargs = kwargs
        if api_body.get('Settings'):
            for xx in range(0, len(api_body['Settings'])):
                fec_mode = api_body['Settings'][xx]['DceInterfaceSettings']['FecMode']
                api_body['Settings'][xx]['DceInterfaceSettings'] = []
                for x in range(0,4):
                    idict = {'FecMode': '', 'InterfaceId': x, 'ObjectType': 'adapter.DceInterfaceSettings'}
                    if len(fec_mode) - 1 >= x: idict['FecMode'] = fec_mode[x]
                    else: idict['FecMode'] = fec_mode[0]
                    api_body['Settings'][xx]['DceInterfaceSettings'].append(idict)
        return api_body

    #=======================================================
    # Function - Assign Physical Device
    #=======================================================
    def assign_physical_device(self, api_body, kwargs):
        if self.type == 'switch':
            if len(api_body['SerialNumber']) == 2: serial = api_body['SerialNumber'][kwargs.x_number]
            else: serial = 'BLAH'
        else: serial = api_body['SerialNumber']
        if re.search(serial_regex, serial): serial_true = True
        else: serial_true = False
        if serial_true == True:
            if kwargs.serial_moids.get(serial):
                serial_moid = kwargs.serial_moids[serial].moid
                sobject     = kwargs.serial_moids[serial]['object_type']
            else: validating.error_serial_number(api_body['Name'], serial)
            ptype = self.type.capitalize()
            api_body.update({f'Assigned{ptype}':{'Moid':serial_moid, 'ObjectType':sobject}})
            api_body = dict(sorted(api_body.items()))
        api_body.pop('SerialNumber')
        return api_body

    #=======================================================
    # BIOS Policy Modification
    #=======================================================
    def bios(self, api_body, item, kwargs):
        if api_body.get('bios_template'):
            btemplate = kwargs.ezdata['bios.template'].properties
            if '-tpm' in api_body['bios_template']:
                api_body = dict(api_body, **btemplate[item.bios_template.replace('-tpm', '')].toDict(), **btemplate.tpm.toDict())
            else: api_body = dict(api_body, **btemplate[item.bios_template].toDict(), **btemplate.tpm_disabled.toDict())
            api_body.pop('bios_template')
        return api_body

    #=======================================================
    # Boot Order Policy Modification
    #=======================================================
    def boot_order(self, api_body, item, kwargs):
        ezdata = kwargs.ezdata['boot_order.boot_devices'].properties
        if item.get('boot_devices'):
            api_body['BootDevices'] = []
            for i in item.boot_devices:
                boot_dev = {'Name':i.name,'ObjectType':i.object_type}
                for k, v in i.items():
                    if k in ezdata: boot_dev.update({ezdata[k].intersight_api:v})
                bkeys = list(boot_dev.keys())
                if not 'Enabled' in bkeys: boot_dev['Enabled'] = True
                if not 'IpType' in bkeys and 'boot.Pxe' == i.object_type: boot_dev['IpType'] = 'IPv4'
                boot_dev = dict(sorted(boot_dev.items()))
                api_body['BootDevices'].append(deepcopy(boot_dev))
        return api_body

    #=======================================================
    # Add Attributes to the api_body
    #=======================================================
    def build_api_body(self, api_body, idata, item, kwargs):
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        for k, v in item.items():
            #print(json.dumps(idata, indent=4))
            #print(k, v)
            if re.search('boolean|string|integer', idata[k].type):
                if '$ref:' in idata[k].intersight_api:
                    x = idata[k].intersight_api.split(':')
                    if not api_body.get(x[1]): api_body.update({x[1]:{x[3]:v, 'ObjectType':x[2]}})
                    elif not api_body[x[1]].get(x[3]): api_body[x[1]].update({x[3]:v})
                elif '$pbucket:' in idata[k].intersight_api:
                    if not api_body.get('PolicyBucket'): api_body['PolicyBucket'] = []
                    x = idata[k].intersight_api.split(':')
                    api_body['PolicyBucket'].append({x[2]:v,'policy':k,'ObjectType':x[1]})
                else: api_body.update({idata[k].intersight_api:v})
            elif idata[k].type == 'array':
                if re.search('boolean|string|integer',  idata[k]['items'].type):
                    if '$ref:' in idata[k]['items'].intersight_api:
                        x = idata[k]['items'].intersight_api.split(':')
                        if not api_body.get(x[1]): api_body.update({x[1]:{'ObjectType':x[2]}})
                        api_body[x[1]].update({x[3]:v})
                    elif '$pbucket:' in idata[k].intersight_api:
                        if not api_body.get('PolicyBucket'): api_body['PolicyBucket'] = []
                        x = idata[k].intersight_api.split(':')
                        api_body['PolicyBucket'].append({x[2]:v,'policy':k,'ObjectType':x[1]})
                    else:
                        api_body[idata[k]['items'].intersight_api] = []
                        for e in v: api_body[idata[k]['items'].intersight_api].append(e)
                else:
                    api_body[idata[k]['items'].intersight_api] = []
                    for e in v:
                        if type(e) == str: api_body[idata[k]['items'].intersight_api].append(e)
                        else:
                            idict = {'ObjectType':idata[k]['items'].ObjectType}
                            for a, b in idata[k]['items'].properties.items():
                                if re.search('boolean|string|integer', b.type):
                                    if a in e and '$ref:' in b.intersight_api:
                                        x = b.intersight_api.split(':')
                                        if not idict.get(x[1]): idict.update({x[1]:{x[3]:e[a], 'ObjectType':x[2]}})
                                    elif a in e: idict.update({b.intersight_api:e[a]})
                                elif b.type == 'object' and a in e:
                                    idict.update({b.intersight_api:{'ObjectType':b.ObjectType}})
                                    for c, d in b.properties.items():
                                        if e[a].get(c): idict[b.intersight_api].update({d.intersight_api:e[a][c]})
                                elif b.type == 'array' and a in e:
                                    if not re.search('(l|s)an_connectivity|firmware|port|storage', self.type):
                                        pcolor.Cyan(f'\n++{"-"*108}\n\n{k}\n{a}\n{b}\n{e[c]}')
                                        pcolor.Red(f'!!! ERROR !!! undefined mapping for array in array: `{d.type}`')
                                        pcolor.Cyan(f'{self.type}\n\n++{"-"*108}\n\n')
                                        sys.exit(1)
                                    idict[b.intersight_api] = e[a]
                            idict = dict(sorted(idict.items()))
                            api_body[idata[k]['items'].intersight_api].append(idict)
            elif idata[k].type == 'object':
                if not api_body.get(idata[k].intersight_api):
                    api_body[idata[k].intersight_api] = {'ObjectType':idata[k].ObjectType}
                for a, b in idata[k].properties.items():
                    if b.type == 'array':
                        if re.search('pci_(links|order)|slot_ids|switch_ids|uplink_ports', a):
                            if v.get(a): api_body[idata[k].intersight_api].update({b.intersight_api:v[a]})
                        elif v.get(a):
                            api_body[idata[k].intersight_api].update({b.intersight_api:[]})
                            idict = {'ObjectType':b['items'].ObjectType}
                            for e in v[a]:
                                for c,d in b['items'].properties.items():
                                    if d.type == 'string' and e.get(c):
                                        idict.update({d.intersight_api:e[c]})
                                        api_body[idata[k].intersight_api][b.intersight_api].append(idict)
                                    else:
                                        pcolor.Cyan(f'\n{"-"*108}\n\n')
                                        pcolor.Cyan(f'{c}\n{d}\n{e}\n{e[c]}')
                                        pcolor.Red(f'!!! ERROR !!! undefined mapping for array in object: `{d.type}`')
                                        pcolor.Cyan(f'\n{"-"*108}\n\n')
                                        sys.exit(1)
                    elif idata[k].type == 'object':
                        if v.get(a): api_body[idata[k].intersight_api].update({idata[k].properties[a].intersight_api:v[a]})
                    elif b.type == 'object':
                        pcolor.Cyan(f'\n{"-"*108}\n\n')
                        pcolor.Cyan(f'---\n{k}---\n{a}---\n{b}---\n{v}')
                        pcolor.Red('!!! ERROR !!! undefined mapping for object in object')
                        pcolor.Cyan(f'\n{"-"*108}\n\n')
                        sys.exit(1)
                    elif v.get(a): api_body[idata[k].intersight_api].update({b.intersight_api:v[a]})
                api_body[idata[k].intersight_api] = dict(sorted(api_body[idata[k].intersight_api].items()))
        #=======================================================
        # Validate all Parameters are String if BIOS
        #=======================================================
        if self.type == 'bios':
            for k, v in api_body.items():
                if type(v) == int or type(v) == float: api_body[k] = str(v)
        #=======================================================
        # Add Policy Specific Settings
        #=======================================================
        if re.fullmatch(policy_specific_regex, self.type): api_body = eval(f'imm(self.type).{self.type}(api_body, item, kwargs)')
        plist1 = [
            'pc_appliances', 'pc_ethernet_uplinks', 'pc_fc_uplinks', 'pc_fcoe_uplinks', 'port_modes',
            'rl_appliances', 'rl_ethernet_uplinks', 'rl_fc_storage', 'rl_fc_uplinks', 'rl_fcoe_uplinks', 'rl_servers',
            'drive_groups', 'ldap_groups', 'ldap_servers', 'users', 'vhbas', 'vlans', 'vnics', 'vsans']
        pop_list = []
        for e in plist1: pop_list.append((e.replace('pc_', 'port_channel_')).replace('rl_', 'port_role_'))
        for e in pop_list:
            if api_body.get(e): api_body.pop(e)
        #=======================================================
        # Attach Organization Map, Tags, and return Dict
        #=======================================================
        api_body = imm(self.type).org_map(api_body, kwargs.org_moids[kwargs.org].moid)
        if api_body.get('Tags'): api_body['Tags'].append(kwargs.ez_tags.toDict())
        else: api_body.update({'Tags':[kwargs.ez_tags.toDict()]})
        api_body = dict(sorted(api_body.items()))
        if api_body.get('Descr'):
            if api_body['Name'] in api_body['Descr']: api_body['Descr'].replace(api_body['Name'], f"{np}{api_body['Name']}{ns}")
        if not re.search('DriveGroups|EndPointUser|LdapGroups|vlan|vnic|vsan', api_body['ObjectType']):
            if api_body.get('Name'): api_body['Name'] = f"{np}{api_body['Name']}{ns}"
        #print(json.dumps(api_body, indent=4))
        return api_body

    #=======================================================
    # Bulk API Request Body
    #=======================================================
    def bulk_request(self, kwargs):
        def post_to_api(kwargs):
            kwargs.method = 'post'
            kwargs.uri    = 'bulk/Requests'
            kwargs        = api('bulk_request').calls(kwargs)
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
        #=======================================================
        # Create API Body for Bulk Request
        #=======================================================
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

    #=======================================================
    # Add Organization Key Map to Dictionaries
    #=======================================================
    def compare_body_result(self, api_body, result):
        if api_body.get('PolicyBucket'):
            api_body['PolicyBucket'] = sorted(api_body['PolicyBucket'], key=lambda item: item['ObjectType'])
            result['PolicyBucket'] = sorted(result['PolicyBucket'], key=lambda item: item['ObjectType'])
        patch_return = False
        for k, v in api_body.items():
            if type(v) == dict:
                for a,b in v.items():
                    if type(b) == list:
                        count = 0
                        for e in b:
                            if type(e) == dict:
                                for c,d in e.items():
                                    if len(result[k][a]) - 1 < count: patch_return = True
                                    elif not result[k][a][count][c] == d: patch_return = True
                            else:
                                if len(result[k][a]) - 1 < count: patch_return = True
                                elif not result[k][a][count] == e: patch_return = True
                    else:
                        if not result.get(k): patch_return = True
                        elif not result[k].get(a): patch_return = True
                        elif not result[k][a] == b: patch_return = True
            elif type(v) == list:
                count = 0
                for e in v:
                    if type(e) == dict:
                        for a,b in e.items():
                            if type(b) == dict:
                                for c,d in b.items():
                                    if len(result[k]) - 1 < count: patch_return = True
                                    elif not result[k][count][a][c] == d: patch_return = True
                            elif type(b) == list:
                                scount = 0
                                for s in b:
                                    if type(s) == dict:
                                        for g,h in s.items():
                                            if len(result[k]) - 1 < count: patch_return = True
                                            elif not result[k][count][a][scount][g] == h: patch_return = True
                                    scount += 1
                            else:
                                if 'Password' in a: count = count
                                elif len(result[k]) - 1 < count: patch_return = True
                                elif not result[k][count][a] == b: patch_return = True
                    elif type(e) == list:
                        pcolor.Red(e)
                        pcolor.Red('compare_body_result; not accounted for')
                        sys.exit(1)
                    else:
                        if len(result[k]) - 1 < count: patch_return = True
                        elif not result[k][count] == e: patch_return = True
                    count += 1
            else:
                if not result[k] == v: patch_return = True
        return patch_return

    #=======================================================
    # Assign Drive Groups to Storage Policies
    #=======================================================
    def drive_groups(self, kwargs):
        ezdata = kwargs.ezdata[self.type]
        kwargs.bulk_list = []
        np, ns = ezfunctions.name_prefix_suffix('storage', kwargs)
        for i in kwargs.policies:
            if i.get('drive_groups'):
                #=======================================================
                # Get Storage Policies
                #=======================================================
                names = []
                for e in i.drive_groups: names.append(e.name)
                kwargs.parent_key  = self.type.split('.')[0]
                kwargs.parent_name = f'{np}{i.name}{ns}'
                kwargs.parent_type = 'storage'
                kwargs.parent_moid = kwargs.isight[kwargs.org].policy['storage'][kwargs.parent_name]
                kwargs.pmoid       = kwargs.parent_moid
                kwargs = api_get(True, names, self.type, kwargs)
                dg_results = kwargs.results
                #=======================================================
                # Create API Body for Storage Drive Groups
                #=======================================================
                for e in i.drive_groups:
                    api_body = {'ObjectType':ezdata.ObjectType}
                    api_body.update({'StoragePolicy':{'Moid':kwargs.parent_moid,'ObjectType':'storage.StoragePolicy'}})
                    api_body = imm(self.type).build_api_body(api_body, ezdata.properties, e, kwargs)
                    api_body.pop('Organization'); api_body.pop('Tags')
                    for x in range(len(api_body['VirtualDrives'])):
                        if not api_body['VirtualDrives'][x].get('VirtualDrivePolicy'):
                            api_body['VirtualDrives'][x]['VirtualDrivePolicy'] = {'ObjectType':'storage.VirtualDrivePolicy'}
                            for k,v in kwargs.ezdata['storage.virtual_drive_policy'].properties.items():
                                if api_body['VirtualDrives'][x]['VirtualDrivePolicy'].get(k):
                                    api_body['VirtualDrives'][x]['VirtualDrivePolicy'][v.intersight_api] = api_body['VirtualDrives'][x]['VirtualDrivePolicy'][k]
                                else: api_body['VirtualDrives'][x]['VirtualDrivePolicy'][v.intersight_api] = v.default
                        api_body['VirtualDrives'][x]['VirtualDrivePolicy'] = dict(
                            sorted(api_body['VirtualDrives'][x]['VirtualDrivePolicy'].items()))
                    #=======================================================
                    # Create or Patch the VLANs via the Intersight API
                    #=======================================================
                    if not kwargs.isight[kwargs.org].policy[self.type].get(api_body['Name']): kwargs.bulk_list.append(deepcopy(api_body))
                    else:
                        indx = next((index for (index, d) in enumerate(dg_results) if d['Name'] == api_body['Name']), None)
                        patch_policy = imm(self.type).compare_body_result(api_body, dg_results[indx])
                        api_body['pmoid'] = kwargs.isight[kwargs.org].policy[self.type][api_body['Name']]
                        if patch_policy == True: kwargs.bulk_list.append(deepcopy(api_body))
                        else:
                            pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {kwargs.parent_type}: `{kwargs.parent_name}`, DriveGroup: `{api_body['Name']}`."\
                                f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    # Ethernet Adapter Policy Modification
    #=======================================================
    def ethernet_adapter(self, api_body, item, kwargs):
        if api_body.get('adapter_template'):
            atemplate= kwargs.ezdata['ethernet_adapter.template'].properties
            api_body  = dict(api_body, **atemplate[item.adapter_template].toDict())
            api_body.pop('adapter_template')
        return api_body

    #=======================================================
    # Fibre-Channel Adapter Policy Modification
    #=======================================================
    def fibre_channel_adapter(self, api_body, item, kwargs):
        if api_body.get('adapter_template'):
            atemplate= kwargs.ezdata['fibre_channel_adapter.template'].properties
            api_body  = dict(api_body, **atemplate[item.adapter_template].toDict())
            api_body.pop('adapter_template')
        return api_body

    #=======================================================
    # Fibre-Channel Network Policies Policy Modification
    #=======================================================
    def firmware(self, api_body, item, kwargs):
        item = item; kwargs = kwargs
        if api_body.get('ExcludeComponentList'):
            exclude_components = list(api_body['ExcludeComponentList'].keys())
            api_body['ExcludeComponentList'] = exclude_components
        if api_body.get('ModelBundleCombo'):
            combos = deepcopy(api_body['ModelBundleCombo']); api_body['ModelBundleCombo'] = []
            for e in combos:
                for i in e['ModelFamily']:
                    idict = deepcopy(e); idict['ModelFamily'] = i
                    api_body['ModelBundleCombo'].append(idict)
            api_body['ModelBundleCombo'] = sorted(api_body['ModelBundleCombo'], key=lambda item: item['BundleVersion'])
        return api_body

    #=======================================================
    # Function - Validate CCO Authorization
    #=======================================================
    def firmware_authenticate(self, kwargs):
        for e in ['cco_password', 'cco_user']:
            if os.environ.get(e) == None:
                kwargs.sensitive_var = e
                kwargs = ezfunctions.sensitive_var_value(kwargs)
                os.environ[e] = kwargs.value
        kwargs.api_body = {
            'ObjectType':'softwarerepository.Authorization','Password':os.environ['cco_password'],
            'RepositoryType':'Cisco','UserId':os.environ['cco_user']}
        kwargs.method   = 'post'
        kwargs.uri      = 'softwarerepository/Authorizations'
        kwargs          = api('firmware_authorization').calls(kwargs)
        return kwargs

    #=======================================================
    # Identity Reservations
    #=======================================================
    def identity_reservations(self, profiles, kwargs):
        #=======================================================
        # Send Begin Notification and Load Variables
        #=======================================================
        pcolor.LightGray(f'  {"-"*60}\n')
        pcolor.LightPurple(f'   Beginning pool Reservations Deployments\n')
        #=======================================================
        # Build Reservation Dictionaries
        #=======================================================
        pool_list = ['ip', 'iqn', 'mac', 'uuid', 'wwnn', 'wwpn']
        pdict = DotMap()
        for e in pool_list:
            kwargs.ibulk_list[e] = []
            kwargs.pools[e]         = []
            kwargs.reservations[e]  = []
            kwargs.ireservations[e] = DotMap()
            pdict[e] = []
        for e in profiles:
            if e.reservations and e.ignore_reservations != True:
                for i in e.reservations:
                    kwargs.reservations[i.identity_type].append(i.identity)
                    rdict = DotMap(dict(i.toDict(), **{'profile':e.name}))
                    pdict[i.identity_type].append(rdict)
                    if len(i.pool_name) > 0:
                        if '/' in i.pool_name: kwargs.pools[i.identity_type].append(i.pool_name)
                        else: kwargs.pools[i.identity_type].append(f"{kwargs.org}/{i.pool_name}")
        #=======================================================
        # Get Pool Moids
        #=======================================================
        for k, v in kwargs.pools.items():
            names         = list(numpy.unique(numpy.array(v)))
            kwargs.method = 'get'
            kwargs        = api_get(True, names, k, kwargs)
        #=======================================================
        # Get Pool Leases
        #=======================================================
        def reservation_settings(k, kwargs):
            if 'ip' in k:     kwargs.pkey = 'IpV4Address'; kwargs.uri = 'ippool/IpLeases'
            elif 'iqn' in k:  kwargs.pkey = 'IqnAddress';  kwargs.uri = 'iqnpool/Leases'
            elif 'mac' in k:  kwargs.pkey = 'MacAddress';  kwargs.uri = 'macpool/Leases'
            elif 'uuid' in k: kwargs.pkey = 'Uuid';        kwargs.uri = 'uuidpool/UuidLeases'
            else:             kwargs.pkey = 'WWnId';       kwargs.uri = 'fcpool/Leases'
            return kwargs
        for k, v in kwargs.reservations.items():
            kwargs = reservation_settings(k, kwargs)
            kwargs.method = 'get'
            names = list(numpy.unique(numpy.array(v)))
            if k == 'ip':
                names  = list(numpy.unique(numpy.array(v)))
                for e in ['IPv4', 'IPv6']:
                    if 'v4' in e: check = '.'; kwargs.pkey = 'IpV4Address'
                    else: check = ':'; kwargs.pkey = 'IpV6Address'
                    kwargs.names = [d for d in names if check in d]
                    if len(kwargs.names) > 0:
                        kwargs        = api(f'{k}_leases').calls(kwargs)
                        kwargs.leases[k][e] = kwargs.results
            else:
                kwargs.names  = list(numpy.unique(numpy.array(v)))
                kwargs        = api(f'{k}_leases').calls(kwargs)
                kwargs.leases[k] = kwargs.results
        #=======================================================
        # Get Identity Reservations
        #=======================================================
        for k, v in kwargs.reservations.items():
            names = list(numpy.unique(numpy.array(v)))
            kwargs = api_get(True, names, f'{k}.reservations', kwargs)
            kwargs.reservations[k] = kwargs.pmoids
        #=======================================================
        # Build Identity Reservations api_body
        #=======================================================
        for k, v in pdict.items():
            kwargs = reservation_settings(k, kwargs)
            for e in v:
                if 'ip' in e.identity_type and ':' in e.identity:
                    indx = next((index for (index, d) in enumerate(kwargs.leases[k]['IPv6']) if d[f'IpV6Address'] == e.identity), None)
                elif 'ip' in e.identity_type and '.' in e.identity:
                    indx = next((index for (index, d) in enumerate(kwargs.leases[k]['IPv4']) if d[f'IpV4Address'] == e.identity), None)
                else: indx = next((index for (index, d) in enumerate(kwargs.leases[k]) if d[f'{kwargs.pkey}'] == e.identity), None)
                if indx == None:
                    if not e.identity in kwargs.reservations[k]:
                        if '/' in e.pool_name: org, pname = e.pool_name.split('/')
                        else: org = kwargs.org; pname = e.pool_name
                        if len(kwargs.isight[org].pool[k][pname]) == 0: validating.error_pool_doesnt_exist(org, k, pname, e.profile)
                        if re.search('wwnn|wwpn', k): otype = 'fcpool.Pool'
                        else: otype = f'{k}pool.Pool'
                        api_body = {'Identity':e.identity, 'Pool':{'Moid':kwargs.isight[org].pool[k][pname],'ObjectType':otype}}
                        api_body = imm(self.type).org_map(api_body, kwargs.org_moids[org].moid)
                        if 'ip' == k:
                            if '.' in e.identity: api_body.update({'IpType':'IPv4'})
                            else:  api_body.update({'IpType':'IPv4'})
                        kwargs.ibulk_list[k].append(api_body)
                    else:
                        res_moid = kwargs.reservations[k][e.identity].moid
                        kwargs.ireservations[k][e.identity].moid = res_moid
                        pcolor.Cyan(f"      * Skipping Org: {kwargs.org} > Server Profile: `{e.profile}` > {k.upper()} Reservation: {e.identity}.  Existing reservation: {res_moid}")
                else:
                    pcolor.Yellow(f"      !!!ERROR!!! with Org: {kwargs.org} > Server Profile: `{e.profile}` > {k.upper()} Reservation: {e.identity}")
                    if 'ip' in e.identity_type and ':' in e.identity: entity = kwargs.leases[k]['IPv6'][indx]['AssignedToEntity']
                    elif 'ip' in e.identity_type and '.' in e.identity: entity = kwargs.leases[k]['IPv4'][indx]['AssignedToEntity']
                    else: entity = kwargs.leases[k][indx]['AssignedToEntity']
                    pcolor.Yellow(f"      Already assigned to {entity['ObjectType']} - Moid: {entity['Moid']}")
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        for e in pool_list:
            if len(kwargs.ibulk_list[e]) > 0:
                kwargs.bulk_list = kwargs.ibulk_list[e]
                kwargs.uri = kwargs.ezdata[f'{e}.reservations'].intersight_uri
                kwargs     = imm(self.type).bulk_request(kwargs)
                for f, g in kwargs.pmoids.items():
                    kwargs.ireservations[e][f].moid = g.moid
        #=======================================================
        # Send End Notification and return kwargs
        #=======================================================
        pcolor.LightPurple(f'\n    Completed pool Reservations Deployments\n')
        pcolor.LightGray(f'  {"-"*60}\n')
        return kwargs

    #=======================================================
    # IMC Access Policy Modification
    #=======================================================
    def imc_access(self, api_body, item, kwargs):
        item = item
        if not api_body.get('AddressType'): api_body.update({ 'AddressType':{ 'EnableIpV4':False, 'EnableIpV6':False }})
        api_body.update({ 'ConfigurationType':{ 'ConfigureInband': False, 'ConfigureOutOfBand': False }})
        #=======================================================
        # Attach Pools to the API Body
        #=======================================================
        names = []; ptype = ['InbandIpPool', 'OutOfBandIpPool']
        np, ns = ezfunctions.name_prefix_suffix('ip', kwargs)
        for i in ptype:
            if api_body.get(i):
                if '/' in api_body[i]['Moid']: org, pool = api_body[i]['Moid'].split('/')
                else: org = kwargs.org; pool = api_body[i]['Moid']
                pool = f"{np}{pool}{ns}"
                if '/' in api_body[i]['Moid']: new_pool = f'{org}/{pool}'
                else: new_pool = pool
                names.append(new_pool)
                api_body['ConfigurationType'][f'Configure{i.split("Ip")[0]}'] = True
        if len(names) > 0: kwargs = api_get(False, names, 'ip', kwargs)
        for i in ptype:
            if api_body.get(i):
                if '/' in api_body[i]['Moid']: org, pool = api_body[i]['Moid'].split('/')
                else: org = kwargs.org; pool = api_body[i]['Moid']
                pool = f"{np}{pool}{ns}"
                if not kwargs.isight[org].pool['ip'].get(pool):
                    if '/' in api_body[i]['Moid']: new_pool = f'{org}/{pool}'
                    else: new_pool = pool
                    validating.error_policy_doesnt_exist(i, new_pool, self.type, 'policy', api_body['Name'])
                org_moid = kwargs.org_moids[org].moid
                indx = next((index for (index, d) in enumerate(kwargs.results) if d.Name == pool and d.Organization.Moid == org_moid), None)
                if len(kwargs.results[indx].IpV4Config.Gateway) > 0: api_body['AddressType']['EnableIpV4'] = True
                if len(kwargs.results[indx].IpV6Config.Gateway) > 0: api_body['AddressType']['EnableIpV6'] = True
                api_body[i]['Moid'] = kwargs.isight[org].pool['ip'][pool]
        return api_body

    #=======================================================
    # IPMI over LAN Policy Modification
    #=======================================================
    def ipmi_over_lan(self, api_body, item, kwargs):
        item = item; kwargs = kwargs
        if api_body.get('encryption_key'):
            if os.environ.get('ipmi_key') == None:
                kwargs.sensitive_var = "ipmi_key"
                kwargs = ezfunctions.sensitive_var_value(kwargs)
                api_body.update({'EncryptionKey':kwargs.var_value})
            else: api_body.update({'EncryptionKey':os.environ.get('ipmi_key')})
        return api_body

    #=======================================================
    # iSCSI Adapter Policy Modification
    #=======================================================
    def iscsi_boot(self, api_body, item, kwargs):
        item = item
        if api_body.get('IscsiAdapterPolicy'):
            names = []
            if '/' in api_body['IscsiAdapterPolicy']['Moid']: org, policy = api_body['IscsiAdapterPolicy']['Moid'].split('/')
            else: org = kwargs.org; policy = api_body['IscsiAdapterPolicy']['Moid']
            if not kwargs.isight[org].policy['iscsi_adapter'].get(policy): kwargs = api_get(False, [item.iscsi_adapter_policy], 'iscsi_adapter', kwargs)
            if not kwargs.isight[org].policy['iscsi_adapter'].get(policy):
                validating.error_policy_doesnt_exist('iscsi_adapter', api_body['IscsiAdapterPolicy']['Moid'], self.type, 'policy', api_body['Name'])
            api_body['IscsiAdapterPolicy']['Moid'] = kwargs.isight[org].policy['iscsi_adapter'][policy]

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
        #=======================================================
        # Attach Pools/Policies to the API Body
        #=======================================================
        if api_body.get('InitiatorIpPool'):
            ip_pool= api_body['InitiatorIpPool']['Moid']
            if '/' in api_body['InitiatorIpPool']['Moid']: org, pool = api_body['InitiatorIpPool']['Moid'].split('/')
            else: org = kwargs.org; pool = api_body['InitiatorIpPool']['Moid']
            if not kwargs.isight[org].pool['ip'].get(pool): kwargs = api_get(False, [ip_pool], 'ip', kwargs)
            api_body['InitiatorIpPool']['Moid'] = kwargs.isight[org].pool['ip'][pool]
        names = []; plist = ['PrimaryTargetPolicy', 'SecondaryTargetPolicy']
        for p in plist:
            if api_body.get(p):
                if '/' in api_body[p]['Moid']: org, policy = api_body[p]['Moid'].split('/')
                else: org = kwargs.org; policy = api_body[p]['Moid']
                if not kwargs.isight[org].policy['iscsi_static_target'].get(policy): names.append(api_body[p]['Moid'])
        if len(kwargs.names) > 0: kwargs = api_get(False, names, 'iscsi_static_target', kwargs)
        for p in plist:
            if api_body.get(p):
                if '/' in api_body[p]['Moid']: org, policy = api_body[p]['Moid'].split('/')
                else: org = kwargs.org; policy = api_body[p]['Moid']
                if not kwargs.isight[org].policy['iscsi_static_target'].get(policy):
                    validating.error_policy_doesnt_exist(p, api_body[p]['Moid'], self.type, 'policy', api_body['Name'])
                api_body[p]['Moid'] = kwargs.isight[org].policy['iscsi_static_target'][policy]
        return api_body

    #=======================================================
    # iSCSI Static Target Policy Modification
    #=======================================================
    def iscsi_static_target(self, api_body, item, kwargs):
        item = item; kwargs = kwargs; api_body['Lun'] = {'Bootable':True}
        return api_body

    #=======================================================
    # Assign Users to Local User Policies
    #=======================================================
    def ldap_groups(self, kwargs):
        #=======================================================
        # Get Existing Users
        #=======================================================
        ezdata = kwargs.ezdata[self.type]
        kwargs.group_post_list = []; kwargs.server_post_list = []; role_names = []; kwargs.cp = DotMap()
        np, ns = ezfunctions.name_prefix_suffix('ldap', kwargs)
        for i in kwargs.policies:
            if i.get('ldap_groups'):
                kwargs.parent_name = f'{np}{i.name}{ns}'
                for e in i.ldap_groups: role_names.append(e.role)
                kwargs.pmoid = kwargs.isight[kwargs.org].policy[self.type.split('.')[0]][kwargs.parent_name]
                names  = [e.name for e in i.ldap_groups]
                kwargs = api_get(True, names, self.type, kwargs)
                kwargs.cp[kwargs.pmoid].group_moids  = kwargs.pmoids
                kwargs.cp[kwargs.pmoid].group_results= kwargs.results
                kwargs.pmoid = kwargs.isight[kwargs.org].policy[self.type.split('.')[0]][kwargs.parent_name]
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
        #=======================================================
        # Construct API Body LDAP Policies
        #=======================================================
        for i in kwargs.policies:
            kwargs.parent_key  = self.type.split('.')[0]
            kwargs.parent_name = f'{np}{i.name}{ns}'
            kwargs.parent_type = 'LDAP Policy'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policy[self.type.split('.')[0]][kwargs.parent_name]
            for e in i.ldap_groups:
                #=======================================================
                # Create API Body for User Role
                #=======================================================
                api_body = {'LdapPolicy':{'Moid':kwargs.parent_moid,'ObjectType':'iam.LdapPolicy'},'ObjectType':ezdata.ObjectType}
                api_body = imm(self.type).build_api_body(api_body, ezdata, e, kwargs)
                api_body['EndPointRole']['Moid'] = kwargs.role_moids[e.role].moid
                #=======================================================
                # Create or Patch the Policy via the Intersight API
                #=======================================================
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
                #=======================================================
                # Create API Body for User Role
                #=======================================================
                api_body = {'LdapPolicy':{'Moid':kwargs.parent_moid,'ObjectType':'iam.LdapPolicy'},'ObjectType':kwargs.ezdata['ldap.ldap_servers'].ObjectType}
                api_body = imm('ldap.ldap_servers').build_api_body(api_body, ezdata, e, kwargs)
                #=======================================================
                # Create or Patch the Policy via the Intersight API
                #=======================================================
                if kwargs.cp[kwargs.parent_moid].server_moids.get(e.server):
                    indx = next((index for (index, d) in enumerate(kwargs.cp[kwargs.parent_moid].server_results) if d['Name'] == api_body['Name']), None)
                    patch_policy = imm(self.type).compare_body_result(api_body, kwargs.cp[kwargs.parent_moid].server_results[indx])
                    api_body['pmoid'] = kwargs.cp[kwargs.parent_moid].moids[e.server].moid
                    if patch_policy == True: kwargs.server_post_list.append(deepcopy(api_body))
                    else:
                        pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {kwargs.parent_type}: `{kwargs.parent_name}`, Group: `{api_body['Name']}`."\
                            f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
                else: kwargs.server_post_list.append(deepcopy(api_body))
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.group_post_list) > 0:
            kwargs.uri = ezdata.interight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        if len(kwargs.server_post_list) > 0:
            kwargs.uri = ezdata.interight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    # LAN Connectivity Policy Modification
    #=======================================================
    def lan_connectivity(self, api_body, item, kwargs):
        if not api_body.get('PlacementMode'): api_body.update({'PlacementMode':'custom'})
        if not api_body.get('TargetPlatform'): api_body.update({'TargetPlatform': 'FIAttached'})
        if item.get('IqnPool'):
            api_body['IqnAllocationType'] = 'Pool'
            if '/' in item.iqn_pool: org, pool = item.iqn_pool.split('/')
            else: org = kwargs.org; pool = item.iqn_pool
            if not kwargs.isight[org].pool['iqn'].get(pool): kwargs = api_get(False, [item.iqn_pool], 'iqn', kwargs)
            api_body['IqnPool']['Moid'] = kwargs.isight[org].pool['iqn'][pool]
        return api_body

    #=======================================================
    # Local User Policy Modification
    #=======================================================
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

    #=======================================================
    # Network Connectivity Policy Modification
    #=======================================================
    def network_connectivity(self, api_body, item, kwargs):
        dns_list = ['v4', 'v6']; kwargs = kwargs
        for i in dns_list:
            dtype = f'dns_servers_{i}'
            if dtype in api_body:
                if len(item[dtype]) > 0: api_body.update({f'PreferredIp{i}dnsServer':item[dtype][0]})
                if len(item[dtype]) > 1: api_body.update({f'AlternateIp{i}dnsServer':item[dtype][1]})
                api_body.pop(dtype)
        return api_body

    #=======================================================
    # Add Organization Key Map to Dictionaries
    #=======================================================
    def org_map(self, api_body, org_moid):
        api_body.update({'Organization':{'Moid':org_moid, 'ObjectType':'organization.Organization'}})
        return api_body

    #=======================================================
    #  Policies Function
    #=======================================================
    def policies(self, kwargs):
        #=======================================================
        # Send Begin Notification and Load Variables
        #=======================================================
        ptitle= ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        validating.begin_section(ptitle, 'policies')
        idata = DotMap(dict(pair for d in kwargs.ezdata[self.type].allOf for pair in d.properties.items()))
        pdict = deepcopy(kwargs.imm_dict.orgs[kwargs.org].policies[self.type])
        if self.type == 'port': policies = list({v.names[0]:v for v in pdict}.values())
        elif self.type == 'firmware_authenticate':
            kwargs = imm(self.type).firmware_authenticate(kwargs)
            validating.end_section(ptitle, 'policies')
            return kwargs
        else: policies = list({v.name:v for v in pdict}.values())
        #=======================================================
        # Get Existing Policies
        #=======================================================
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        names = []
        for i in policies:
            if self.type == 'port': names.extend([f'{np}{i.names[x]}{ns}' for x in range(0,len(i.names))])
            else: names.append(f"{np}{i['name']}{ns}")
        kwargs = api_get(True, names, self.type, kwargs)
        kwargs.policy_results= kwargs.results
        #=======================================================
        # If Modified Patch the Policy via the Intersight API
        #=======================================================
        def policies_to_api(api_body, kwargs):
            kwargs.uri   = kwargs.ezdata[self.type].intersight_uri
            if api_body['Name'] in kwargs.isight[kwargs.org].policy[self.type]:
                indx = next((index for (index, d) in enumerate(kwargs.policy_results) if d['Name'] == api_body['Name']), None)
                patch_policy = imm(self.type).compare_body_result(api_body, kwargs.policy_results[indx])
                api_body['pmoid']  = kwargs.isight[kwargs.org].policy[self.type][api_body['Name']]
                if patch_policy == True:
                    kwargs.bulk_list.append(deepcopy(api_body))
                    kwargs.pmoids[api_body['Name']].moid = api_body['pmoid']
                else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {ptitle} Policy: `{api_body['Name']}`.  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
            else: kwargs.bulk_list.append(deepcopy(api_body))
            return kwargs
        #=======================================================
        # Loop through Policy Items
        #=======================================================
        kwargs.bulk_list = []
        for item in policies:
            if self.type == 'port':
                names = item.names; item.pop('names')
                for x in range(0,len(names)):
                    #=======================================================
                    # Construct api_body Payload
                    #=======================================================
                    api_body = {'Name':f'{np}{names[x]}{ns}','ObjectType':kwargs.ezdata[self.type].ObjectType}
                    api_body = imm(self.type).build_api_body(api_body, idata, item, kwargs)
                    kwargs = policies_to_api(api_body, kwargs)
            else:
                #=======================================================
                # Construct api_body Payload
                #=======================================================
                api_body = {'ObjectType':kwargs.ezdata[self.type].ObjectType}
                api_body = imm(self.type).build_api_body(api_body, idata, item, kwargs)
                kwargs = policies_to_api(api_body, kwargs)
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri    = kwargs.ezdata[self.type].intersight_uri
            kwargs        = imm(self.type).bulk_request(kwargs)
            for e in kwargs.results: kwargs.isight[kwargs.org].policy[self.type][e.Body.Name] = e.Body.Moid
        #=======================================================
        # Loop Thru Sub-Items
        #=======================================================
        pdict = deepcopy(kwargs.imm_dict.orgs[kwargs.org].policies[self.type])
        if self.type == 'port': kwargs.policies = list({v['names'][0]:v for v in pdict}.values())
        else: kwargs.policies = list({v['name']:v for v in pdict}.values())
        if 'port' == self.type:
            kwargs = imm('port.port_modes').port_modes(kwargs)
            kwargs = imm('port').ports(kwargs)
        elif re.search('(l|s)an_connectivity|local_user|storage|v(l|s)an', self.type):
            sub_list = ['lan_connectivity.vnics', 'local_user.users', 'san_connectivity.vhbas', 'storage.drive_groups', 'vlan.vlans', 'vsan.vsans']
            for e in sub_list:
                a, b = e.split('.')
                if a == self.type:
                    if re.search('vnics|vhbas', e): kwargs = eval(f'imm(e).vnics(kwargs)')
                    else: kwargs = eval(f'imm(e).{b}(kwargs)')
        #=======================================================
        # Send End Notification and return kwargs
        #=======================================================
        validating.end_section(ptitle, 'policies')
        return kwargs

    #=======================================================
    #  Pools Function
    #=======================================================
    def pools(self, kwargs):
        #=======================================================
        # Send Begin Notification and Load Variables
        #=======================================================
        ptitle = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        validating.begin_section(ptitle, 'pool')
        kwargs.bulk_list = []
        idata = DotMap(dict(pair for d in kwargs.ezdata[self.type].allOf for pair in d.properties.items()))
        pools = list({v['name']:v for v in kwargs.imm_dict.orgs[kwargs.org].pools[self.type]}.values())
        #=======================================================
        # Get Existing Pools
        #=======================================================
        np, ns = ezfunctions.name_prefix_suffix(self.type, kwargs)
        kwargs = api_get(True, [f'{np}{e.name}{ns}' for e in pools], self.type, kwargs)
        kwargs.pool_results = kwargs.results
        #=======================================================
        # Loop through Items
        #=======================================================
        for item in pools:
            #=======================================================
            # Construct api_body Payload
            #=======================================================
            api_body = {'ObjectType':kwargs.ezdata[self.type].ObjectType}
            api_body = imm(self.type).build_api_body(api_body, idata, item, kwargs)
            akeys = list(api_body.keys())
            if not 'AssignmentOrder' in akeys: api_body['AssignmentOrder'] = 'sequential'
            #=======================================================
            # Add Pool Specific Attributes
            #=======================================================
            if re.search('ww(n|p)n', self.type):  api_body.update({'PoolPurpose':self.type.upper()})
            #=======================================================
            # Resource Pool Updates
            #=======================================================
            if self.type == 'resource':
                kwargs.method = 'get'
                kwargs.names  = api_body['serial_number_list']
                kwargs.uri    = kwargs.ezdata[self.type].intersight_uri_serial
                kwargs        = api('serial_number').calls(kwargs)
                smoids        = kwargs.pmoids
                selector = "','".join(kwargs.names); selector = f"'{selector}'"
                stype = f"{smoids[api_body['serial_number_list'][0]].object_type.split('.')[1]}s"
                mmode = smoids[api_body['serial_number_list'][0]].management_mode
                api_body['ResourcePoolParameters'] = {'ManagementMode':mmode,'ObjectType':'resourcepool.ServerPoolParameters'}
                api_body['Selectors'] = [{
                    'ObjectType': 'resource.Selector',
                    'Selector': f"/api/v1/compute/{stype}?$filter=(Serial in ({selector})) and (ManagementMode eq '{mmode}')"
                }]
                api_body.pop('serial_number_list')
            #=======================================================
            # If Modified Patch the Pool via the Intersight API
            #=======================================================
            if api_body['Name'] in kwargs.isight[kwargs.org].pool[self.type]:
                indx = next((index for (index, d) in enumerate(kwargs.pool_results) if d['Name'] == api_body['Name']), None)
                patch_pool = imm(self.type).compare_body_result(api_body, kwargs.pool_results[indx])
                api_body['pmoid'] = kwargs.isight[kwargs.org].pool[self.type][api_body['Name']]
                if patch_pool == True: kwargs.bulk_list.append(deepcopy(api_body))
                else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {ptitle} Pool: `{api_body['Name']}`.  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
            else: kwargs.bulk_list.append(deepcopy(api_body))
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri    = kwargs.ezdata[self.type].intersight_uri
            kwargs        = imm(self.type).bulk_request(kwargs)
            for e in kwargs.results: kwargs.isight[kwargs.org].pool[self.type][e.Body.Name] = e.Body.Moid
        #=======================================================
        # Send End Notification and return kwargs
        #=======================================================
        validating.end_section(ptitle, 'pool')
        return kwargs

    #=======================================================
    # Port Modes for Port Policies
    #=======================================================
    def port_modes(self, kwargs):
        #=======================================================
        # Loop Through Port Modes
        #=======================================================
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
                    indx = next((index for (index, d) in enumerate(kwargs.policy_results) if d['Name'] == i), None)
                    kwargs.parent_moid = kwargs.policy_results[indx].Moid
                    kwargs.pmoid = kwargs.policy_results[indx].Moid
                    kwargs = api_get(True, kwargs.port_policy[i].names, self.type, kwargs)
                    port_modes  = kwargs.pmoids
                    port_results= deepcopy(kwargs.results)
                    for e in item[p[1]]:
                        api_body = {'CustomMode':e.custom_mode,'ObjectType':ezdata.ObjectType,
                                          'PortIdStart':e.port_list[0],'PortIdEnd':e.port_list[1],
                                          ezdata.parent_policy:{'Moid':kwargs.parent_moid,'ObjectType':ezdata.parent_object}}
                        if e.get('slot_id'): api_body.update({'SlotId':e.slot_id})
                        else: api_body.update({'SlotId':1})
                        #=======================================================
                        # Create or Patch the Policy via the Intersight API
                        #=======================================================
                        kwargs.parent_key  = self.type.split('.')[0]
                        kwargs.parent_name = i
                        kwargs.parent_type = 'Port Policy'
                        kwargs.parent_moid = kwargs.isight[kwargs.org].policy['port'][i]
                        if port_modes.get(kwargs.parent_moid):
                            if port_modes[kwargs.parent_moid].get(str(e.port_list[0])):
                                kwargs.method= 'patch'
                            else: kwargs.method= 'post'
                        else: kwargs.method= 'post'
                        if kwargs.method == 'post': kwargs.bulk_list.append(deepcopy(api_body))
                        else:
                            indx = next((index for (index, d) in enumerate(port_results) if d['PortIdStart'] == e.port_list[0]), None)
                            patch_port = imm(self.type).compare_body_result(api_body, port_results[indx])
                            api_body['pmoid'] = port_modes[kwargs.parent_moid][str(e.port_list[0])].moid
                            if patch_port == True: kwargs.bulk_list.append(deepcopy(api_body))
                            else:
                                ps = e.port_list[0]; pe = e.port_list[1]
                                pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; Port Policy: `{i}`, CustomMode: `{e.custom_mode}`,  PortIdStart: `{ps}` and PortIdEnd: `{pe}`.\n"\
                                       f"         Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri    = kwargs.ezdata[self.type].intersight_uri
            kwargs        = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    # Assign Port Types to Port Policies
    #=======================================================
    def ports(self, kwargs):
        #=======================================================
        # Create/Patch the Port Policy Port Types
        #=======================================================
        def api_calls(port_type, kwargs):
            #=======================================================
            # Create or Patch the Policy via the Intersight API
            #=======================================================
            if re.search('port_channel', port_type): name = int(kwargs.api_body['PcId']); key_id = 'PcId'
            else: name = int(kwargs.api_body['PortId']); key_id = 'PortId'
            if kwargs.port_moids[port_type].get(kwargs.parent_moid):
                if kwargs.port_moids[port_type][kwargs.parent_moid].get(str(name)):
                    kwargs.method= 'patch'
                    kwargs.pmoid = kwargs.port_moids[port_type][kwargs.parent_moid][str(name)].moid
                else: kwargs.method= 'post'
            else: kwargs.method= 'post'
            kwargs.uri = kwargs.ezdata[f'port.{port_type}'].intersight_uri
            if kwargs.method == 'patch':
                indx = next((index for (index, d) in enumerate(kwargs.port_results[port_type]) if d[key_id] == name), None)
                patch_port = imm(self.type).compare_body_result(kwargs.api_body, kwargs.port_results[port_type][indx])
                if patch_port == True: kwargs = api(f'port.{port_type}').calls(kwargs)
                else:
                    pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; Port Policy: `{kwargs.parent_name}`, {key_id}: `{name}`."\
                           f"  Intersight Matches Configuration.  Moid: {kwargs.pmoid}")
            else:
                kwargs.plist[port_type].append({'Body':deepcopy(kwargs.api_body), 'ClassId':'bulk.RestSubRequest',
                                                'ObjectType':'bulk.RestSubRequest', 'Verb':'POST', 'Uri':f'/v1/{kwargs.uri}'})
            return kwargs
        
        #=======================================================
        # Check if the Port Policy Port Type Exists
        #=======================================================
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

        #=======================================================
        # Attach Ethernet/Flow/Link Policies
        #=======================================================
        def policy_update(port_type, i, x, kwargs):
            for p in ['EthNetworkControl', 'EthNetworkGroup', 'FlowControl', 'LinkAggregation', 'LinkControl']:
                p = f'{p}Policy'
                if kwargs.api_body.get(p):
                    ptype = (snakecase(p).replace('eth_', 'ethernet_')).replace('_policy', '')
                    if '/' in kwargs.api_body[p]['Moid']: org, policy = kwargs.api_body[p]['Moid'].split('/')
                    else: org = kwargs.org; policy = kwargs.api_body[p]['Moid']
                    np, ns = ezfunctions.name_prefix_suffix(ptype, kwargs)
                    policy = f"{np}{policy}{ns}"
                    if '/' in kwargs.api_body[p]['Moid']: new_policy = f'{org}/{policy}'
                    else: new_policy = policy
                    if not kwargs.isight[org].policy[ptype].get(policy):
                        validating.error_policy_doesnt_exist(ptype, new_policy, f'port.{port_type}', 'policy', i.names[x])
                    kwargs.api_body[p]['Moid'] = kwargs.isight[org].policy[ptype][policy]
                    if 'Group' in p: kwargs.api_body[p] = [kwargs.api_body[p]]
            return kwargs
        
        #=======================================================
        # Create API Body for Port Policies
        #=======================================================
        def port_type_call(port_type, item, x, kwargs):
            ezdata = kwargs.ezdata[f'port.{port_type}']
            for i in item[port_type]:
                api_body = {'ObjectType':ezdata.ObjectType, 'PortPolicy':{'Moid':kwargs.parent_moid,'ObjectType':'fabric.PortPolicy'}}
                kwargs.api_body = imm(f'port.{port_type}').build_api_body(api_body, ezdata.properties, i, kwargs)
                if i.get('pc_ids'):
                    if len(kwargs.api_body['PcId']) == 2: kwargs.api_body['PcId'] = i.pc_ids[x]
                    else: kwargs.api_body['PcId'] = i.pc_ids[x]
                    if re.search('appliance|ethernet|fcoe', port_type): kwargs = policy_update(port_type, i, x, kwargs)
                    for y in range(len(api_body['Ports'])):
                        if not kwargs.api_body['Ports'][y].get('AggregatePortId'): kwargs.api_body['Ports'][y]['AggregatePortId'] = 0
                        if not kwargs.api_body['Ports'][y].get('SlotId'): kwargs.api_body['Ports'][y]['SlotId'] = 1
                else:
                    if not kwargs.api_body.get('AggregatePortId'): kwargs.api_body['AggregatePortId'] = 0
                    if not kwargs.api_body.get('SlotId'): kwargs.api_body['SlotId'] = 1
                if i.get('vsan_ids'):
                    if len(i['vsan_ids']) > 1: kwargs.api_body['VsanId'] = i['vsan_ids'][x]
                    else: kwargs.api_body['VsanId'] = i['vsan_ids'][0]
                kwargs.api_body.pop('Organization'); kwargs.api_body.pop('Tags')
                if re.search('port_channel', port_type): kwargs = api_calls(port_type, kwargs)
                elif re.search('role', port_type):
                    for e in ezfunctions.vlan_list_full(i.port_list):
                        kwargs.api_body['PortId'] = int(e)
                        kwargs = api_calls(port_type, kwargs)
            return kwargs

        #=======================================================
        # Get Policies
        #=======================================================
        def policy_list(policy, ptype, kwargs):
            original_policy = policy
            if '/' in policy: org, policy = policy.split('/')
            else: org = kwargs.org; policy = policy
            np, ns = ezfunctions.name_prefix_suffix(ptype, kwargs)
            policy = f"{np}{policy}{ns}"
            if '/' in original_policy: new_policy = f'{org}/{policy}'
            else: new_policy = policy
            if not kwargs.isign[org].policy.get('ptype'): kwargs.isight[org].policy[ptype] = DotMap()
            if not kwargs.cp.get(ptype): kwargs.cp[ptype] = DotMap(names = [])
            if not kwargs.isight[org].policy[ptype].get(policy): kwargs.cp[ptype].names.append(new_policy)
            return kwargs
        #=======================================================
        # Build Child Policy Map
        #=======================================================
        kwargs.cp = DotMap(); kwargs.port_types = []; kwargs.ports = []
        for k,v in kwargs.ezdata.port.allOf[0].properties.items():
            if re.search('^port_(cha|rol)', k): kwargs.port_types.append(k)
        for e in kwargs.port_types:
            kwargs.port_type[e].names = []
            for item in kwargs.policies:
                if item.get(e):
                    kwargs.ports.append(e)
                    for i in item[e]:
                        if 'port_channel' in e: kwargs.port_type[e].names.extend(i.pc_ids)
                        for k, v in i.items():
                            if re.search('^(ethernet|flow|link)_', k):
                                ptype = (k.replace('_policies', '')).replace('_policy', '')
                                if type(v) == list:
                                    for d in v: kwargs = policy_list(d, ptype, kwargs)
                                else: kwargs = policy_list(v, ptype, kwargs)
        kwargs.ports = list(numpy.unique(numpy.array(kwargs.ports)))
        for e in list(kwargs.cp.keys()):
            if len(kwargs.cp[e].names) > 0:
                names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                kwargs = api_get(False, names, e, kwargs)
        #=======================================================
        # Loop Through Port Types
        #=======================================================
        kwargs.plist = DotMap()
        for item in kwargs.policies:
            for x in range(0,len(item.names)):
                for e in kwargs.ports:
                    if item.get(e):
                        kwargs.plist[e] = []
                        kwargs.parent_key  = self.type.split('.')[0]
                        kwargs.parent_name = item.names[x]
                        kwargs.parent_type = 'Port Policy'
                        kwargs.parent_moid = kwargs.isight[kwargs.org].policy['port'][item.names[x]]
                        kwargs = get_ports(e, item, x, kwargs)
                        port_type_call(e, item, x, kwargs)
                        if len(kwargs.plist[e]) > 0:
                            kwargs.api_body= {'Requests':kwargs.plist[e]}
                            kwargs.method = 'post'
                            kwargs.uri    = 'bulk/Requests'
                            kwargs        = api('bulk_request').calls(kwargs)
        return kwargs

    #=======================================================
    # Profile Creation Function
    #=======================================================
    def profile_api_calls(self, api_body, kwargs):
        if kwargs.isight[kwargs.org].profile[self.type].get(api_body['Name']):
            indx = next((index for (index, d) in enumerate(kwargs.profile_results) if d['Name'] == api_body['Name']), None)
            patch_profile = imm(self.type).compare_body_result(api_body, kwargs.profile_results[indx])
            api_body['pmoid'] = kwargs.isight[kwargs.org].profile[self.type][api_body['Name']]
            if patch_profile == True:
                if 'SrcTemplate' in api_body:
                    if api_body['SrcTemplate'] != None and kwargs.profile_results[indx].SrcTemplate != None:
                        if api_body['SrcTemplate']['Moid'] != kwargs.profile_results[indx].SrcTemplate.Moid:
                            kwargs.api_body = {'SrcTemplate':None}
                            kwargs.method   = 'patch'
                            kwargs.pmoid    = kwargs.isight[kwargs.org].profile[self.type][api_body['Name']]
                            kwargs.uri      = 'server/Profiles'
                            kwargs          = api('server').calls(kwargs)
                kwargs.bulk_list.append(deepcopy(api_body))
            else:
                if 'server_template' in self.type: ntitle = 'Server Profile Template'
                else: ntitle = f'{self.type.title()} Profile'
                pcolor.Cyan(f"      * Skipping Org: {kwargs.org} > {ntitle}: `{api_body['Name']}`.  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
        else: kwargs.bulk_list.append(deepcopy(api_body))
        return kwargs

    #=======================================================
    # Build Chassis Profiles
    #=======================================================
    def profile_chassis(self, profiles, kwargs):
        ezdata = kwargs.ezdata[self.type]
        for item in profiles:
            api_body = {'ObjectType':ezdata.ObjectType}
            pitems = deepcopy(item)
            if pitems.get('action'): pitems.pop('action')
            api_body = imm(self.type).build_api_body(api_body, kwargs.idata, pitems, kwargs)
            api_body = imm(self.type).profile_policy_bucket(api_body, kwargs)
            if api_body.get('SerialNumber'): api_body = imm.assign_physical_device(self, api_body, kwargs)
            kwargs = imm(self.type).profile_api_calls(api_body, kwargs)
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    # Function - Deploy Profile if Action is Deploy
    #=======================================================
    def profile_chassis_server_deploy(self, profiles, kwargs):
        cregex = re.compile('Analyzing|Assigned|Failed|Inconsistent|Validating')
        pending_changes = False
        kwargs.profile_update = DotMap()
        for e in profiles:
            if e.get('action') and e.get('serial_number'):
                if e.action == 'Deploy' and re.search(serial_regex, e.serial_number):
                    kwargs.profile_update[e.name] = e
                    kwargs.profile_update[e.name].pending_changes = 'Blank'
        if len(kwargs.profile_update) > 0:
            kwargs = api_get(False, list(kwargs.profile_update.keys()), kwargs.type, kwargs)
            profile_results = kwargs.results
            for e in list(kwargs.profile_update.keys()):
                indx = next((index for (index, d) in enumerate(profile_results) if d['Name'] == e), None)
                changes  = profile_results[indx].ConfigChanges.Changes
                cstate   = profile_results[indx].ConfigContext.ConfigState
                csummary = profile_results[indx].ConfigContext.ConfigStateSummary
                isummary = profile_results[indx].ConfigChangeContext.InitialConfigContext.ConfigStateSummary
                if len(changes) > 0 or re.search(cregex, cstate) or re.search(cregex, csummary) or re.search(cregex, isummary):
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
                    if 'server' == kwargs.type:  pcolor.LightPurple('    * Pending Changes.  Sleeping for 120 Seconds'); time.sleep(120)
                    else:  pcolor.LightPurple('    * Pending Changes.  Sleeping for 60 Seconds'); time.sleep(60)
                for e in list(kwargs.profile_update.keys()):
                    if kwargs.profile_update[e].pending_changes == 'Deploy':
                        pcolor.Green(f'    - Beginning Profile Deployment for `{e}`.')
                        kwargs.api_body= {'Action':'Deploy'}
                        kwargs.method = 'patch'
                        kwargs.pmoid  = kwargs.isight[kwargs.org].profile[kwargs.type][e]
                        kwargs = api(kwargs.type).calls(kwargs)
                    else: pcolor.LightPurple(f'    - Skipping Org: {kwargs.org}; Profile Deployment for `{e}`.  No Pending Changes.')
                if deploy_pending == True:
                    if 'server' == kwargs.type:  pcolor.LightPurple('    * Deploying Changes.  Sleeping for 600 Seconds'); time.sleep(600)
                    else:  pcolor.LightPurple('    * Deploying Changes.  Sleeping for 60 Seconds'); time.sleep(60)
                for e in list(kwargs.profile_update.keys()):
                    if kwargs.profile_update[e].pending_changes == 'Deploy':
                        deploy_complete= False
                        while deploy_complete == False:
                            kwargs.method = 'get_by_moid'
                            kwargs.pmoid  = kwargs.isight[kwargs.org].profile[kwargs.type][e]
                            kwargs = api(self.type).calls(kwargs)
                            if kwargs.results.ConfigContext.ControlAction == 'No-op':
                                deploy_complete = True
                                if re.search('^(chassis)$', kwargs.type): pcolor.Green(f'    - Completed Profile Deployment for `{e}`.')
                            else: 
                                if 'server' == kwargs.type: pcolor.Cyan(f'      * Deploy Still Occuring on `{e}`.  Waiting 120 seconds.'); time.sleep(120)
                                else: pcolor.Cyan(f'      * Deploy Still Occuring on `{e}`.  Waiting 60 seconds.'); time.sleep(60)
                if 'server' == kwargs.type:
                    pcolor.LightPurple(f'\n{"-"*108}\n')
                    names = []
                    for e in list(kwargs.profile_update.keys()):
                        if not kwargs.profile_update[e].pending_changes == 'Blank': names.append(e)
                    if len(names) > 0:
                        kwargs = api_get(False, names, kwargs.type, kwargs)
                        profile_results = kwargs.results
                    pending_activations = False
                    for e in list(kwargs.profile_update.keys()):
                        if not kwargs.profile_update[e].pending_changes == 'Blank':
                            indx = next((index for (index, d) in enumerate(profile_results) if d['Name'] == e), None)
                            if len(profile_results[indx].ConfigChanges.PolicyDisruptions) > 0:
                                pcolor.Green(f'    - Beginning Profile Activation for `{e}`.')
                                kwargs.api_body= {'ScheduledActions':[{'Action':'Activate', 'ProceedOnReboot':True}]}
                                kwargs.method = 'patch'
                                kwargs.pmoid  = kwargs.isight[kwargs.org].profile[kwargs.type][e]
                                kwargs = api(self.type).calls(kwargs)
                                pending_activations = True
                            else:
                                pcolor.LightPurple(f'    - Skipping Org: {kwargs.org}; Profile Activation for `{e}`.  No Pending Changes.')
                                kwargs.profile_update[e].pending_changes = 'Blank'
                    if pending_activations == True:
                        pcolor.LightPurple(f'\n{"-"*108}\n')
                        pcolor.LightPurple('    * Pending Activitions.  Sleeping for 300 Seconds'); time.sleep(300)
                    for e in list(kwargs.profile_update.keys()):
                        if not kwargs.profile_update[e].pending_changes == 'Blank':
                            deploy_complete = False
                            while deploy_complete == False:
                                kwargs.method = 'get_by_moid'
                                kwargs.pmoid  = kwargs.isight[kwargs.org].profile[kwargs.type][e]
                                kwargs = api(self.type).calls(kwargs)
                                results = DotMap(kwargs['results'])
                                if results.ConfigContext.ControlAction == 'No-op':
                                    pcolor.Green(f'    - Completed Profile Activiation for `{e}`.')
                                    deploy_complete = True
                                else:  pcolor.Cyan(f'      * Activiation Still Occuring on `{e}`.  Waiting 120 seconds.'); time.sleep(120)
                        else: pcolor.Green(f'    - Completed Profile Deployment for `{e}`.')
                pcolor.LightPurple(f'\n{"-"*108}\n')
        return kwargs

    #=======================================================
    # Build Domain Profiles
    #=======================================================
    def profile_domain(self, profiles, kwargs):
        ezdata = kwargs.ezdata[self.type]
        for item in profiles:
            pdata = {'name':item.name}; plist = ['description', 'tags']
            for e in plist:
                if item.get(e): pdata.update({e:item[e]})
            api_body = {'ObjectType':ezdata.ObjectType}
            api_body = imm(self.type).build_api_body(api_body, kwargs.idata, pdata, kwargs)
            kwargs  = imm(self.type).profile_api_calls(api_body, kwargs)
            if len(kwargs.bulk_list) > 0:
                if not kwargs.plist.get('domain'): kwargs.plist.domain = []
                kwargs.plist.domain.extend(kwargs.bulk_list)
                kwargs.bulk_list = []
            #=======================================================
            # Build api_body for Switch Profiles
            #=======================================================
            cluster_moid = kwargs.isight[kwargs.org].profile[self.type][item.name]
            for x in range(0,2):
                sw_name = f"{item.name}-{chr(ord('@')+x+1)}"; otype = 'SwitchClusterProfile'
                if kwargs.switch_moids.get(item.name):
                    kwargs.isight[kwargs.org].profile['switch'][sw_name] = kwargs.switch_moids[item.name][sw_name].moid
                pdata = dict(deepcopy(item), **{'name':sw_name})
                api_body = {'Name':sw_name, 'ObjectType':'fabric.SwitchProfile', otype:{'Moid':cluster_moid,'ObjectType':f'fabric.{otype}'}}
                api_body = imm(self.type).build_api_body(api_body, kwargs.idata, pdata, kwargs)
                kwargs.x_number = x
                api_body = imm.profile_policy_bucket(self, api_body, kwargs)
                if api_body.get('SerialNumber'): api_body = imm.assign_physical_device(self, api_body, kwargs)
                pop_list = ['Action', 'Description', 'Organization', 'Tags']
                for e in pop_list:
                    if api_body.get(e): api_body.pop(e)
                temp_results = kwargs.profile_results
                kwargs.profile_results = kwargs.switch_results[item.name]
                kwargs  = imm(self.type).profile_api_calls(api_body, kwargs)
                kwargs.profile_results = temp_results
                if len(kwargs.bulk_list) > 0:
                    if not kwargs.plist.get('switch'): kwargs.plist.switch = []
                    kwargs.plist.switch.extend(kwargs.bulk_list)
                    kwargs.bulk_list = []
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        for e in list(kwargs.plist.keys()):
            if len(kwargs.plist[e]) > 0:
                if 'domain' == e: kwargs.uri = kwargs.ezdata[self.type].intersight_uri
                else: kwargs.uri = kwargs.ezdata[self.type].intersight_uri_switch
                kwargs.bulk_list = kwargs.plist[e]
                kwargs = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    # Function - Deploy Domain Profile if Action is Deploy
    #=======================================================
    def profile_domain_deploy(self, profiles, kwargs):
        deploy_profiles = False
        for item in profiles:
            for x in range(0,2):
                if item.get('action') and item.get('serial_numbers'):
                    if item.action == 'Deploy' and re.search(serial_regex, item.serial_numbers[x]):
                        pname = f"{item.name}-{chr(ord('@')+x+1)}"
                        kwargs.method = 'get_by_moid'
                        kwargs.pmoid  = kwargs.isight[kwargs.org].profile['switch'][pname]
                        kwargs.uri    = kwargs.ezdata['domain'].intersight_uri_switch
                        kwargs = api('switch').calls(kwargs)
                        r = kwargs.results
                        if len(r.ConfigChanges.Changes) > 0 or re.search("Assigned|Failed|Pending-changes", r.ConfigContext.ConfigState):
                            deploy_profiles = True
                            kwargs.cluster_update[item.name].pending_changes = True; break
        pending_changes = False
        for e in kwargs.cluster_update.keys():
            if kwargs.cluster_update[e].pending_changes == True: pending_changes = True
        if deploy_profiles == True: pcolor.LightPurple(f'\n{"-"*108}\n')
        if pending_changes == True: pcolor.Cyan('      * Sleeping for 120 Seconds'); time.sleep(120)
        for item in profiles:
            if kwargs.cluster_update[item.name].pending_changes == True:
                for x in range(0,2):
                    pname = f"{item.name}-{chr(ord('@')+x+1)}"
                    pcolor.Green(f'    - Beginning Profile Deployment for {pname}')
                    kwargs.api_body= {'Action':'Deploy'}
                    kwargs.method = 'patch'
                    kwargs.pmoid  = kwargs.isight[kwargs.org].profile['switch'][pname]
                    kwargs = api('switch').calls(kwargs)
        if deploy_profiles == True: pcolor.LightPurple(f'\n{"-"*108}\n'); time.sleep(60)
        for item in profiles:
            if kwargs.cluster_update[item.name].pending_changes == True:
                for x in range(0,2):
                    pname = f"{item.name}-{chr(ord('@')+x+1)}"
                    kwargs.method= 'get_by_moid'
                    kwargs.pmoid = kwargs.isight[kwargs.org].profile['switch'][pname]
                    deploy_complete = False
                    while deploy_complete == False:
                        kwargs = api('switch').calls(kwargs)
                        if kwargs.results.ConfigContext.ControlAction == 'No-op':
                            pcolor.Green(f'    - Completed Profile Deployment for {pname}')
                            deploy_complete = True
                        else:  pcolor.Cyan(f'      * Deploy Still Occuring on {pname}.  Waiting 120 seconds.'); time.sleep(120)
        if deploy_profiles == True: pcolor.LightPurple(f'\n{"-"*108}\n')
        return kwargs

    #=======================================================
    # Assign Moid to Policy in Bucket
    #=======================================================
    def profile_policy_bucket(self, api_body, kwargs):
        for x in range(len(api_body['PolicyBucket'])):
            ptype = ((api_body['PolicyBucket'][x]['policy']).replace('_policy', '')).replace('_policies', '')
            api_body['PolicyBucket'][x].pop('policy')
            if self.type == 'switch':
                if re.search('-A', api_body['Name']): f = 0
                else: f = 1
            if type(api_body['PolicyBucket'][x]['Moid']) == list:
                if len(api_body['PolicyBucket'][x]['Moid']) == 2: opolicy = api_body['PolicyBucket'][x]['Moid'][f]
                else: opolicy = api_body['PolicyBucket'][x]['Moid'][0]
            else: opolicy = api_body['PolicyBucket'][x]['Moid']
            if '/' in opolicy: org, policy = opolicy.split('/')
            else: org = kwargs.org; policy = opolicy
            if not kwargs.isight[org].policy[ptype].get(policy):
                validating.error_policy_doesnt_exist(ptype, opolicy, self.type, 'profile', api_body['Name'])
            api_body['PolicyBucket'][x]['Moid'] = kwargs.isight[org].policy[ptype][policy]
        if api_body.get('UuidPool'):
            api_body['UuidAddressType'] = 'POOL'
            if '/' in api_body['UuidPool']['Moid']: org, pool = api_body['UuidPool']['Moid'].split('/')
            else: org = kwargs.org; pool = api_body['UuidPool']['Moid']
            if not kwargs.isight[org].pool['uuid'].get(pool):
                validating.error_policy_doesnt_exist('uuid', api_body['UuidPool']['Moid'], self.type, 'profile', api_body['Name'])
            api_body['UuidPool']['Moid'] = kwargs.isight[org].pool['uuid'][pool]
        return api_body

    #=======================================================
    # Build Server Profiles
    #=======================================================
    def profile_server(self, profiles, kwargs):
        ezdata = kwargs.ezdata[self.type]
        for e in profiles:
            api_body = {'ObjectType':ezdata.ObjectType}
            if len(e.ucs_server_template) > 0:
                if '/' in e.ucs_server_template: org, template = e.ucs_server_template.split('/')
                else: org = kwargs.org; template = e.ucs_server_template
            if e.attach_template != True and len(e.ucs_server_template) > 0:
                pitems = dict(kwargs.templates[f'{org}/{template}'], **deepcopy(e))
            else: pitems = deepcopy(e)
            pop_items = ['action', 'attach_template', 'create_template', 'domain_name', 'ignore_reservations', 'reservations', 'ucs_server_template']
            pkeys = list(pitems.keys())
            for p in pop_items:
                if p in pkeys: pitems.pop(p)
            plist = []
            for k, v in kwargs.idata.items():
                if '_policy' in k: plist.append(k)
                if '_pool' in k: plist.append(k)
            for p in plist:
                if pitems.get(p):
                    if org != kwargs.org:
                        if not '/' in pitems[p]: pitems[p] = f'{org}/{pitems[p]}'
            api_body = {'ObjectType':ezdata.ObjectType}
            api_body = imm(self.type).build_api_body(api_body, kwargs.idata, pitems, kwargs)
            if not api_body.get('TargetPlatform'): api_body['TargetPlatform'] = 'FIAttached'
            if api_body.get('PolicyBucket'): api_body = imm.profile_policy_bucket(api_body, kwargs)
            if 'reservations' in pkeys:
                kwargs = imm.profile_server_reservations(self, e, api_body, kwargs)
            if api_body.get('SerialNumber'): api_body = imm.assign_physical_device(self, api_body, kwargs)
            if api_body.get('ServerPreAssignBySlot'):
                if api_body['ServerPreAssignBySlot'].get('SerialNumber'):
                    api_body['ServerPreAssignBySerial'] = api_body['ServerPreAssignBySlot']['SerialNumber']
                    api_body.pop('ServerPreAssignBySlot')
                else:
                    if not e.get('domain_name'):
                        kwargs.name = e.name; kwargs.argument = 'domain_name'
                        validating.error_required_argument_missing(self.type, kwargs)
                    api_body['ServerPreAssignBySlot']['DomainName'] = e.domain_name
            if e.attach_template == True and len(e.ucs_server_template) > 0:
                api_body['SrcTemplate'] = {'Moid':kwargs.isight[org].profile.server_template[template],
                                           'ObjectType':'server.ProfileTemplate'}
            else: api_body['SrcTemplate'] = None
            kwargs = imm(self.type).profile_api_calls(api_body, kwargs)
        #=======================================================
        # POST bulk/Requests if Bulk List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
            for e in kwargs.results: kwargs.isight[kwargs.org].profile[self.type][e.Body.Name] = e.Body.Moid
        for e in profiles:
            if e.attach_template == True and len(e.ucs_server_template) > 0:
                if '/' in e.ucs_server_template: org, template = e.ucs_server_template.split('/')
                else: org = kwargs.org; template = e.ucs_server_template
                if not kwargs.bulk_merger_template.get(f'{org}/{template}'):
                    tmoid = kwargs.isight[org].profile['server_template'][template]
                    kwargs.bulk_merger_template[f'{org}/{template}'] = {
                        'MergeAction': 'Merge', 'ObjectType': 'bulk.MoMerger', 'Targets':[],
                        'Sources':[{'Moid':tmoid, 'ObjectType':'server.ProfileTemplate'}]
                    }
                idict = {'Moid': kwargs.isight[kwargs.org].profile[self.type][e.name], 'ObjectType':'server.Profile'}
                kwargs.bulk_merger_template[f'{org}/{template}']['Targets'].append(idict)

        #=======================================================
        # POST bulk/MoMergers if List > 0
        #=======================================================
        if len(kwargs.bulk_merger_template) > 0:
            for e in kwargs.bulk_merger_template.keys():
                kwargs.api_body= kwargs.bulk_merger_template[e]
                kwargs.method = 'post'
                kwargs.uri    = 'bulk/MoMergers'
                kwargs = api('bulk').calls(kwargs)
        return kwargs

    #=======================================================
    # Build Server Profile Reservations
    #=======================================================
    def profile_server_reservations(self, e, api_body, kwargs):
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
        if len(api_body['ReservationReferences']) == 0: api_body.pop('ReservationReferences')
        return kwargs

    #=======================================================
    # Build Server Profile Templates
    #=======================================================
    def profile_template(self, profiles, kwargs):
        ezdata = kwargs.ezdata[self.type]
        for item in profiles:
            api_body = {'ObjectType':ezdata.ObjectType}
            api_body = imm(self.type).build_api_body(api_body, kwargs.idata, item, kwargs)
            if not api_body.get('TargetPlatform'): api_body['TargetPlatform'] = 'FIAttached'
            api_body = imm(self.type).profile_policy_bucket(api_body, kwargs)
            api_body.pop('create_template')
            kwargs = imm(self.type).profile_api_calls(api_body, kwargs)
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    #  Profiles Function
    #=======================================================
    def profiles(self, kwargs):
        #=======================================================
        # Send Begin Notification and Load Variables
        #=======================================================
        ptitle= ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        validating.begin_section(ptitle, 'profiles')
        names  = []; kwargs.cp = DotMap(); kwargs.serials = []
        ezdata = kwargs.ezdata[self.type]
        idata  = DotMap(dict(pair for d in kwargs.ezdata[self.type].allOf for pair in d.properties.items()))
        if re.search('chassis|server', self.type):
            targets = DotMap(dict(pair for d in idata.targets['items'].allOf for pair in d.properties.items()))
            idata.pop('targets')
            idata = DotMap(dict(idata.toDict(), **targets.toDict()))
        #=======================================================
        # Compile List of Profile Names
        #=======================================================
        profiles            = []
        profile_policy_list = []
        run_reservation     = False
        if 'template' in self.type:
            for e in kwargs.imm_dict.orgs[kwargs.org]['templates']['server']:
                if e.create_template == True: profiles.append(e)
                profile_policy_list.append(e)
        elif 'domain' in self.type:
            profiles = kwargs.imm_dict.orgs[kwargs.org].profiles[self.type]
            profile_policy_list = profiles
            for e in profiles: kwargs.serials.extend(e.serial_numbers)
        else:
            for v in kwargs.imm_dict.orgs[kwargs.org].profiles[self.type]:
                for e in v.targets:
                    profiles.append(DotMap(dict(e, **v)))
                    if 'reservations' in e:
                        if not e.ignore_reservations == True: run_reservation = True
                    if len(e.serial_number) > 0: kwargs.serials.append(e.serial_number)
            profile_policy_list = profiles
        if re.search('^chassis|server$', self.type):
            for e in profiles:
                e.pop('targets')
                if 'server' == self.type and e.get('ucs_server_template'):
                    if '/' in e.ucs_server_template: org, template = e.ucs_server_template.split('/')
                    else: org = kwargs.org; template = e.ucs_server_template
                    ptype = 'ucs_server_template'; tname = e.ucs_server_template
                    tdata = kwargs.imm_dict.orgs[org]['templates']['server']
                    indx  = next((index for (index, d) in enumerate(tdata) if d['name'] == template), None)
                    if indx == None:
                        validating.error_policy_doesnt_exist(ptype, tname, e.name, self.type, 'Profile')
                    elif tdata[indx].create_template == True and e.attach_template == True:
                        if len(kwargs.isight[org].profile.server_template[template]) == 0:
                            validating.error_policy_doesnt_exist(ptype, tname, e.name, self.type, 'Profile')
                    kwargs.templates[f'{org}/{template}'] = tdata[indx]
        #=======================================================
        # Loop Through Reservations if True
        #=======================================================
        if self.type == 'server' and run_reservation == True:
            kwargs = imm.identity_reservations(self, profiles, kwargs)
        kwargs.bulk_list = []
        #=======================================================
        # Get Moids for Profiles/Templates
        #=======================================================
        for e in profiles: names.append(e.name)
        if len(names) > 0:
            kwargs = api_get(True, names, self.type, kwargs)
            kwargs.profile_results = kwargs.results
        #=======================================================
        # Get Moids for Switch Profiles
        #=======================================================
        if 'domain' in self.type:
            kwargs.uri = ezdata.intersight_uri_switch
            for c in names:
                kwargs.names  = []
                if kwargs.isight[kwargs.org].profile[self.type].get(c):
                    for x in range(0,2): kwargs.names.append(f"{c}-{chr(ord('@')+x+1)}")
                    kwargs.pmoid = kwargs.isight[kwargs.org].profile[self.type][c]
                    kwargs       = api('switch').calls(kwargs)
                    kwargs.switch_moids[c]   = kwargs.pmoids
                    kwargs.switch_results[c] = kwargs.results
        #=======================================================
        # Compile List of Policy Names
        #=======================================================
        def policy_search(item, kwargs):
            for k, v in item.items():
                if re.search('_polic(ies|y)|_pool$', k):
                    ptype = (((k.replace('_policies', '')).replace(
                        '_address_pools', '')).replace('_pool', '')).replace('_policy', '')
                    if not kwargs.cp.get(ptype): kwargs.cp[ptype].names = []
                    def policy_list(k, policy, ptype, kwargs):
                        original_policy = policy
                        if '/' in policy: org, policy = policy.split('/')
                        else: org = kwargs.org; policy = policy
                        if 'pool' in k: p = 'pool'
                        else: p = 'policy'
                        np, ns = ezfunctions.name_prefix_suffix(ptype, kwargs)
                        policy = f"{np}{policy}{ns}"
                        if '/' in original_policy: new_policy = f'{org}/{policy}'
                        else: new_policy = policy
                        if not kwargs.isight[org][p][ptype].get(policy): kwargs.cp[ptype].names.append(new_policy)
                        return kwargs
                    if type(v) == list:
                        for e in v: kwargs = policy_list(k, e, ptype, kwargs)
                    else: kwargs = policy_list(k, v, ptype, kwargs)
            return kwargs
        #=======================================================
        # Get Policy Moids
        #=======================================================
        for e in profile_policy_list: kwargs = policy_search(e, kwargs)
        for e in list(kwargs.cp.keys()):
            if len(kwargs.cp[e].names) > 0:
                names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                kwargs = api_get(False, names, e, kwargs)
        #=======================================================
        # Get Serial Moids
        #=======================================================
        if len(kwargs.serials) > 0:
            kwargs.names        = kwargs.serials
            kwargs.uri          = ezdata.intersight_uri_serial
            kwargs              = api('serial_number').calls(kwargs)
            kwargs.serial_moids = kwargs.pmoids
        kwargs.uri = ezdata.intersight_uri
        #=======================================================
        # Create the Profiles with the Functions
        #=======================================================
        kwargs.idata = idata
        if 'server' == self.type:
            kwargs = imm.profile_server(self, profiles, kwargs)
            kwargs = imm.profile_chassis_server_deploy(self, profiles, kwargs)
        elif 'chassis' == self.type:
            kwargs = imm.profile_chassis(self, profiles, kwargs)
            kwargs = imm.profile_chassis_server_deploy(self, profiles, kwargs)
        elif 'server_template' == self.type:
            kwargs = imm.profile_template(self, profiles, kwargs)
        elif 'domain' == self.type:
            kwargs = imm.profile_domain(self, profiles, kwargs)
            kwargs = imm.profile_domain_deploy(self, profiles, kwargs)
        #========================================================
        # End Function and return kwargs
        #========================================================
        validating.end_section(ptitle, 'profiles')
        return kwargs

    #=======================================================
    # SAN Connectivity Policy Modification
    #=======================================================
    def san_connectivity(self, api_body, item, kwargs):
        if not api_body.get('PlacementMode'): api_body.update({'PlacementMode':'custom'})
        if item.get('wwnn_pool'):
            api_body['WwnnAddressType'] = 'POOL'
            if '/' in item.wwnn_pool: org, pool = item.wwnn_pool.split('/')
            else: org = kwargs.org; pool = item.wwnn_pool
            if not kwargs.isight[org].pool['wwnn'].get(pool): kwargs = api_get(False, [item.wwnn_pool], 'wwnn', kwargs)
            api_body['WwnnPool']['Moid'] = kwargs.isight[org].pool['wwnn'][pool]
        return api_body

    #=============================================================================
    # Function - Build Server Identies for Zoning host/igroups
    #=============================================================================
    def server_identities(self, kwargs):
        #=====================================================
        # Attach Server Profile Moid to Dict
        #=====================================================
        kwargs.server_profiles = DotMap(); hw_moids = []; profile_moids = []
        for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            kwargs.server_profiles[e.name] = DotMap(e)
            kwargs.server_profiles[e.name].hardware_moid = e.moid
            hw_moids.append(e.moid)
        kwargs.method = 'get'
        kwargs.names  = list(kwargs.server_profiles.keys())
        kwargs.uri    = 'server/Profiles'
        kwargs        = api('server').calls(kwargs)
        for k, v in kwargs.pmoids.items(): kwargs.server_profiles[k].moid = v.moid; profile_moids.append(v.moid)
        #=====================================================
        # Get vNICs & vHBAs Identifiers
        #=====================================================
        names_join        = "', '".join(profile_moids).strip("', '")
        kwargs.api_filter = f"Profile.Moid in ('{names_join}')"
        kwargs.method     = 'get'
        kwargs.uri        = 'vnic/EthIfs'
        kwargs = api('vnics').calls(kwargs)
        vnic_results = kwargs.results
        kwargs.api_filter = f"Profile.Moid in ('{names_join}')"
        kwargs.uri        = 'vnic/FcIfs'
        kwargs = api('vhbas').calls(kwargs)
        vhba_results = kwargs.results
        #=====================================================
        # Attach vNIC(s)/Identities to server_profile Dict
        #=====================================================
        kwargs.eth_moids = []
        if len(vnic_results) > 0:
            for k in list(kwargs.server_profiles.keys()):
                mac_list = []
                for e in vnic_results:
                    if e.Profile.Moid == kwargs.server_profiles[k].moid:
                        kwargs.eth_moids.append(e.FabricEthNetworkGroupPolicy[0].Moid)
                        mac_list.append(DotMap(mac = e.MacAddress, name = e.Name,order = e.Order,
                                               switch = e.Placement.SwitchId,
                                               vgroup = e.FabricEthNetworkGroupPolicy[0].Moid))
                kwargs.server_profiles[k].macs = sorted(mac_list, key=lambda k: (k['order']))
        else:
            names_join        = "', '".join(hw_moids).strip("', '")
            kwargs.api_filter = f"Ancestors/any(t:t/Moid in '{names_join}')"
            kwargs.uri        = 'adapter/HostEthInterfaces'
            kwargs            = api('adapter').calls(kwargs)
            adapter_results   = kwargs.results
            for k in list(kwargs.server_profiles.keys()):
                adapter_list = []
                for e in adapter_results:
                    attach = False
                    for i in e.Ancestors:
                        if i.Moid == v.hardware_moid: attach = True
                    if attach == True: adapter_list.append(e)
                adapter_list = sorted(adapter_list, key=lambda k: (k['MacAddress']))
                nic_names    = ['mgmt-a', 'mgmt-b']
                for x in range(0,len(adapter_list)): nic_names.append(f'mgmt-{(chr(ord('@')+x+1)).lower()}')
                mac_list = []
                for x in range(0,len(adapter_list)):
                    mac_list.append(DotMap(mac = adapter_list[x].MacAddress, name = nic_names[x], order  = x))
                kwargs.server_profiles[k].macs = sorted(mac_list, key=lambda k: (k['order']))
        #=====================================================
        # Attach vHBA(s)/Identities to server_profile Dict
        #=====================================================
        if len(vhba_results) > 0:
            for k in list(kwargs.server_profiles.keys()):
                wwpn_list = []
                for e in vhba_results:
                    if e.Profile.Moid == kwargs.server_profiles[k].moid:
                        wwpn_list.append(DotMap(name = e.Name,order = e.Order, wwpn = e.Wwpn,
                                               switch = e.Placement.SwitchId))
                kwargs.server_profiles[k].macs = sorted(wwpn_list, key=lambda k: (k['order']))
        #=====================================================
        # Get IQN for Host and Add to Profile Map
        #=====================================================
        names_join        = "', '".join(profile_moids).strip("', '")
        kwargs.api_filter = f"AssignedToEntity.Moid eq ('{names_join}')"
        kwargs.method     = 'get'
        kwargs.uri        = 'iqnpool/Pools'
        kwargs            = api('iqn').calls(kwargs)
        if len(kwargs.results) > 0:
            for k in list(kwargs.server_profiles.keys()):
                for e in kwargs.results:
                    if e.AssignedToEntity.Moid == kwargs.server_profiles[k].moid: kwargs.server_profiles[k].iqn = e.IqnId
        kwargs.server_profile = DotMap(kwargs.server_profiles)
        if len(kwargs.eth_moids) > 0:
            #=====================================================
            # Query API for Ethernet Network Policies and Add to Server Profile Dictionaries
            #=====================================================
            eth_moids         = list(numpy.unique(numpy.array(kwargs.eth_moids)))
            names_join        = "', '".join(eth_moids).strip("', '")
            kwargs.api_filter = f"Moid in ('{names_join}')"
            kwargs.uri        = 'fabric/EthNetworkGroupPolicies'
            eth_results       = kwargs.results
            for k in list(kwargs.server_profiles.keys()):
                mcount = 0
                for e in kwargs.server_profiles[k].macs:
                    indx = next((index for (index, d) in enumerate(eth_results) if d['Moid'] == e.vgroup), None)
                    kwargs.server_profiles[k].macs[mcount].allowed    = eth_results[indx].VlanSettings.AllowedVlans
                    kwargs.server_profiles[k].macs[mcount].native     = eth_results[indx].VlanSettings.NativeVlan
                    kwargs.server_profiles[k].macs[mcount].vlan_group = eth_results[indx].Name
        for k in list(kwargs.server_profiles.keys()):
            pvars = kwargs.server_profiles[k].toDict()
            # Add Policy Variables to imm_dict
            kwargs.class_path = f'wizard,os_configuration'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=======================================================
        # Create YAML Files
        #=======================================================
        orgs   = list(kwargs.org_moids.keys())
        kwargs = ezfunctions.remove_duplicates(orgs, ['wizard'], kwargs)
        ezfunctions.create_yaml(orgs, kwargs)
        #=====================================================
        # Return kwargs and kwargs
        #=====================================================
        return kwargs

    #=======================================================
    # SNMP Policy Modification
    #=======================================================
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

    #=======================================================
    # Storage Policy Modification
    #=======================================================
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
        return api_body

    #=======================================================
    # Syslog Policy Modification
    #=======================================================
    def syslog(self, api_body, item, kwargs):
        item = item; kwargs = kwargs
        if api_body.get('LocalClients'): api_body['LocalClients'] = [api_body['LocalClients']]
        return api_body

    #=======================================================
    # System QoS Policy Modification
    #=======================================================
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
        api_body['Classes'] = sorted(api_body['Classes'], key=lambda item: item['Name'])
        return api_body

    #=======================================================
    # Assign Users to Local User Policies
    #=======================================================
    def users(self, kwargs):
        #=======================================================
        # Get Existing Users
        #=======================================================
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
                    kwargs.pmoid = kwargs.isight[kwargs.org].policy[self.type.split('.')[0]][i.name]
                    kwargs.uri   = 'iam/EndPointUserRoles'
                    kwargs       = api('user_role').calls(kwargs)
                    kwargs.cp[kwargs.pmoid].moids  = kwargs.pmoids
                    kwargs.cp[kwargs.pmoid].results= kwargs.results

        #=======================================================
        # Construct API Body Users
        #=======================================================
        for e in names:
            if not kwargs.user_moids.get(e):
                api_body = {'Name':e.username,'ObjectType':ezdata.ObjectType}
                api_body = imm(self.type).org_map(api_body, kwargs.org_moids[kwargs.org].moid)
                kwargs.bulk_list.append(deepcopy(api_body))
            else: pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; User: `{e}`.  Intersight Matches Configuration.  Moid: {kwargs.user_moids[e].moid}")
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[self.type].intersight_uri
            kwargs     = imm(self.type).bulk_request(kwargs)
        kwargs.user_moids = dict(kwargs.user_moids, **kwargs.pmoids)
        kwargs.bulk_list = []
        np, ns = ezfunctions.name_prefix_suffix('local_user', kwargs)
        for i in kwargs.policies:
            kwargs.parent_key  = self.type.split('.')[0]
            kwargs.parent_name = f'{np}{i.name}{ns}'
            kwargs.parent_type = 'Local User Policy'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policy[self.type.split('.')[0]][kwargs.parent_name]
            if i.get('users'):
                for e in i.users:
                    kwargs.sensitive_var = f"local_user_password_{e.password}"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    user_moid = kwargs.user_moids[e.username].moid
                    #=======================================================
                    # Create API Body for User Role
                    #=======================================================
                    if e.get('enabled'): api_body = {'Enabled':e.enabled,'ObjectType':'iam.EndPointUserRole'}
                    else: api_body = {'Enabled':True,'ObjectType':'iam.EndPointUserRole'}
                    api_body.update({
                        'EndPointRole':[{'Moid':kwargs.role_moids[e.role].moid,'ObjectType':'iam.EndPointRole'}],
                        'EndPointUser':{'Moid':user_moid,'ObjectType':'iam.EndPointUser'},
                        'EndPointUserPolicy':{'Moid':kwargs.parent_moid,'ObjectType':'iam.EndPointUserPolicy'},
                        'Password':kwargs.var_value})
                    #=======================================================
                    # Create or Patch the Policy via the Intersight API
                    #=======================================================
                    if kwargs.cp[kwargs.parent_moid].moids.get(user_moid):
                        api_body['pmoid'] = kwargs.cp[kwargs.parent_moid].moids[user_moid].moid
                        kwargs.bulk_list.append(deepcopy(api_body))
                    else: kwargs.bulk_list.append(deepcopy(api_body))
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = 'iam/EndPointUserRoles'
            kwargs     = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    # Virtual Media Policy Modification
    #=======================================================
    def virtual_media(self, api_body, item, kwargs):
        item = item
        if api_body.get('Mappings'):
            for x in range(api_body['Mappings']):
                if api_body['Mappings'][x].get('Password'):
                    kwargs.sensitive_var = f"vmedia_password_{api_body['Mappings'][x]['Password']}"
                    kwargs = ezfunctions.sensitive_var_value(kwargs)
                    api_body['Mappings'][x]['Password'] = kwargs.var_value
        return api_body

    #=======================================================
    # Assign VLANs to VLAN Policies
    #=======================================================
    def vlans(self, kwargs):
        #=======================================================
        # Loop Through VLAN Lists to Create api_body(s)
        #=======================================================
        def configure_vlans(e, kwargs):
            ezdata = kwargs.ezdata[self.type]
            api_body = {'EthNetworkPolicy':{'Moid':kwargs.parent_moid, 'ObjectType':'fabric.EthNetworkPolicy'}, 'ObjectType':ezdata.ObjectType}
            api_body = imm(self.type).build_api_body(api_body, ezdata.properties, e, kwargs)
            api_keys = list(api_body.keys())
            for i in ['Organization', 'Tags', 'name_prefix']:
                if i in api_keys: api_body.pop(i)
            if not api_body.get('AutoAllowOnUplinks'): api_body.update({'AutoAllowOnUplinks':False})
            if '/' in e.multicast_policy: org, policy = e.multicast_policy.split('/')
            else: org = kwargs.org; policy = e.multicast_policy
            np, ns = ezfunctions.name_prefix_suffix('multicast', kwargs)
            policy = f"{np}{policy}{ns}"
            if not kwargs.isight[org].policy['multicast'].get(policy):
                validating.error_policy_doesnt_exist('multicast_policy', e.multicast_policy, self.type, 'Vlans', e.vlan_list)
            api_body['MulticastPolicy']['Moid'] = kwargs.isight[org].policy['multicast'][policy]
            if not api_body.get('IsNative'): api_body['IsNative'] = False
            vkeys = list(e.keys())
            if not 'name_prefix' in vkeys: name_prefix = True
            else: name_prefix = e.name_prefix
            vlans = ezfunctions.vlan_list_full(e.vlan_list)
            for x in ezfunctions.vlan_list_full(e.vlan_list):
                if type(x) == str: x = int(x)
                if len(vlans) > 1 and name_prefix == True: api_body['Name'] = f"{e.name}{'0'*(4 - len(str(x)))}{x}"
                api_body['VlanId'] = x
                #=======================================================
                # Create or Patch the VLANs via the Intersight API
                #=======================================================
                if not kwargs.isight[kwargs.org].policy[self.type].get(str(x)): kwargs.bulk_list.append(deepcopy(api_body))
                else:
                    indx = next((index for (index, d) in enumerate(kwargs.vlans_results) if d['VlanId'] == x), None)
                    if not indx == None:
                        patch_vlan = imm(self.type).compare_body_result(api_body, kwargs.vlans_results[indx])
                        api_body['pmoid'] = kwargs.isight[kwargs.org].policy[self.type][str(x)]
                        if patch_vlan == True: kwargs.bulk_list.append(deepcopy(api_body))
                        else:
                            pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; VLAN Policy: `{kwargs.parent_name}`, VLAN: `{x}`."\
                                f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
                        api_body.pop('pmoid')
                    else: kwargs.bulk_list.append(deepcopy(api_body))
            return kwargs
        #=======================================================
        # Get Multicast Policies
        #=======================================================
        mcast_names = []
        for i in kwargs.policies:
            if i.get('vlans'):
                for e in i.vlans:
                    if '/' in e.multicast_policy: org, policy = e.multicast_policy.split('/')
                    else: org = kwargs.org; policy = e.multicast_policy
                    np, ns = ezfunctions.name_prefix_suffix('multicast', kwargs)
                    policy = f"{np}{policy}{ns}"
                    if not kwargs.isight[org].policy['multicast'].get(policy):
                        if '/' in e.multicast_policy: policy = f'{org}/{policy}'
                        mcast_names.append(policy)
        mcast_names= list(numpy.unique(numpy.array(mcast_names)))
        kwargs     = api_get(False, mcast_names, 'multicast', kwargs)
        #=======================================================
        # Loop Through VLAN Policies
        #=======================================================
        kwargs.bulk_list = []
        np, ns = ezfunctions.name_prefix_suffix('vlan', kwargs)
        for i in kwargs.policies:
            kwargs.bulk_list = []
            vnames = []
            kwargs.parent_key  = self.type.split('.')[0]
            kwargs.parent_name = f'{np}{i.name}{ns}'
            kwargs.parent_type = 'VLAN Policy'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policy[self.type.split('.')[0]][kwargs.parent_name]
            kwargs.pmoid       = kwargs.parent_moid
            kwargs.vlan_policy = f'{np}{i.name}{ns}'
            if i.get('vlans'):
                for e in i.vlans: vnames.extend(ezfunctions.vlan_list_full(e.vlan_list))
                kwargs = api_get(True, vnames, self.type, kwargs)
                kwargs.vlans_results= kwargs.results
                for e in i.vlans: kwargs = configure_vlans(e, kwargs)
            #=======================================================
            # POST Bulk Request if Post List > 0
            #=======================================================
            if len(kwargs.bulk_list) > 0:
                kwargs.uri    = kwargs.ezdata[self.type].intersight_uri
                kwargs        = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    # Assign VNICs to LAN Connectivity Policies
    #=======================================================
    def vnics(self, kwargs):
        #=======================================================
        # Get Policies and Pools
        #=======================================================
        ezdata = kwargs.ezdata[self.type]
        kwargs.cp = DotMap(); kwargs.bulk_list = []
        x = self.type.split('.')
        vpolicy = (kwargs.ezdata[x[0]].ObjectType).split('.')[1]
        kwargs.parent_key  = self.type.split('.')[0]
        kwargs.parent_type = (snakecase(vpolicy).replace('_', ' ')).title()
        vtype = x[1]
        for item in kwargs.policies:
            for i in item[vtype]:
                for k,v in i.items():
                    if re.search('_polic(ies|y)|_pools$', k):
                        ptype = (((k.replace('_policies', '')).replace('_address_pools', '')).replace('_pools', '')).replace('_policy', '')
                        if not kwargs.cp.get(ptype): kwargs.cp[ptype].names = []
                        def policy_list(k, policy, ptype, kwargs):
                            original_policy = policy
                            if '/' in policy: org, policy = policy.split('/')
                            else: org = kwargs.org; policy = policy
                            if 'pool' in k: p = 'pool'
                            else: p = 'policy'
                            np, ns = ezfunctions.name_prefix_suffix(ptype, kwargs)
                            policy = f"{np}{policy}{ns}"
                            if '/' in original_policy: new_policy = f'{org}/{policy}'
                            else: new_policy = policy
                            if not kwargs.isight[org][p][ptype].get(policy): kwargs.cp[ptype].names.append(new_policy)
                            return kwargs
                        if type(v) == list:
                            for e in v: kwargs = policy_list(k, e, ptype, kwargs)
                        else: kwargs = policy_list(k, v, ptype, kwargs)
        for e in list(kwargs.cp.keys()):
            if len(kwargs.cp[e].names) > 0:
                names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                kwargs = api_get(False, names, e, kwargs)
        #=======================================================
        # Create API Body for vNICs
        #=======================================================
        for item in kwargs.policies:
            np, ns = ezfunctions.name_prefix_suffix('lan_connectivity', kwargs)
            kwargs.parent_name= f'{np}{item.name}{ns}'
            kwargs.parent_moid= kwargs.isight[kwargs.org].policy[self.type.split('.')[0]][kwargs.parent_name]
            kwargs.pmoid      = kwargs.parent_moid
            names   = []
            for i in item[vtype]: names.extend(i.names)
            kwargs = api_get(True, names, self.type, kwargs)
            vnic_results= kwargs.results
            for i in item[vtype]:
                for x in range(len(i.names)):
                    api_body = {vpolicy:{'Moid':kwargs.parent_moid,'ObjectType':f'vnic.{vpolicy}'}, 'ObjectType':ezdata.ObjectType}
                    api_body = imm(self.type).build_api_body(api_body, ezdata.properties, i, kwargs)
                    api_body.update({'Name':i.names[x]})
                    api_body.pop('Organization'); api_body.pop('Tags')
                    api_body['Order'] = i.placement.pci_order[x]
                    if api_body['Placement'].get('Order'): api_body['Placement'].pop('Order')
                    for k, v in i.items():
                        if re.search('_polic(ies|y)|_pools$', k):
                            ptype = (((k.replace('_policies', '')).replace('_address_pools', '')).replace('_pools', '')).replace('_policy', '')
                            if type(v) == list:
                                if len(v) >= 2: pname = v[x]
                                else: pname = v[0]
                            else: pname = v
                            if '/' in pname: org, policy = pname.split('/')
                            else: org = kwargs.org; policy = pname
                            if 'pool' in k: p = 'pool'
                            else: p = 'policy'
                            np, ns = ezfunctions.name_prefix_suffix(ptype, kwargs)
                            policy = f"{np}{policy}{ns}"
                            if not kwargs.isight[org][p][ptype].get(policy):
                                if '/' in pname: err_policy = f'{org}/{policy}'
                                else: err_policy = policy
                                validating.error_policy_doesnt_exist(ptype, err_policy, self.type, p, i.names[x])
                            api_body[ezdata.properties[k].intersight_api.split(':')[1]]['Moid'] = kwargs.isight[org][p][ptype][policy]
                    if 'vnics' in self.type:
                        if not api_body.get('Cdn'): api_body.update({'Cdn':{'Value':i.names[x],'Source':'vnic','ObjectType':'vnic.Cdn'}})
                        api_body['FabricEthNetworkGroupPolicy'] = [api_body['FabricEthNetworkGroupPolicy']]
                        if api_body.get('StaticMacAddress'): api_body['StaticMacAddress'] = api_body['StaticMacAddress'][x]
                    else:
                        def zone_update(pname, ptype, kwargs):
                            if '/' in pname: org, policy = pname.split('/')
                            else: org = kwargs.org; policy = pname
                            np, ns = ezfunctions.name_prefix_suffix(ptype, kwargs)
                            policy = f"{np}{policy}{ns}"
                            if not kwargs.isight[org].policy[ptype].get(policy):
                                if '/' in pname: err_policy = f'{org}/{policy}'
                                else: err_policy = policy
                                validating.error_policy_doesnt_exist(ptype, err_policy, self.type, 'policy', i.names[x])
                            kwargs.zbody['Moid'] = kwargs.isight[org].policy[ptype][policy]
                            return kwargs.zbody
                        if i.get('fc_zone_policies'):
                            kwargs.zbody= deepcopy(api_body['FcZonePolicies'])
                            api_body['FcZonePolicies'] = []
                            if len(i.names) == 2:
                                half = len(i.fc_zone_policies)//2
                                if x == 0: zlist = i.fc_zone_policies[half:]
                                else: zlist = i.fc_zone_policies[:half]
                                for e in zlist: api_body['FcZonePolicies'].append(zone_update(e, 'fc_zone', kwargs))
                            else:
                                for e in i.fc_zone_policies: api_body['FcZonePolicies'].append(zone_update(e, 'fc_zone', kwargs))
                        if api_body.get('StaticWwpnAddress'): api_body['StaticWwpnAddress'] = api_body['StaticWwpnAddress'][x]
                    if x == 0: side = 'A'
                    else: side = 'B'
                    api_body.update({'Placement':{'Id':'MLOM','ObjectType':'vnic.PlacementSettings','PciLink':0,'SwitchId':side,'Uplink':0}})
                    if i.get('placement'):
                        place_list = ['pci_links', 'slot_ids', 'switch_ids', 'uplink_ports']
                        for p in place_list:
                            if i.get(p):
                                if len(i[p]) == 2: pval = i[p][x]
                                else: pval = i[p][0]
                                api_body['Placement'][ezdata.properties.placement.properties[p].intersight_api] = pval
                    #=======================================================
                    # Create or Patch the VLANs via the Intersight API
                    #=======================================================
                    if kwargs.isight[kwargs.org].policy[self.type].get(i.names[x]):
                        indx = next((index for (index, d) in enumerate(vnic_results) if d['Name'] == i.names[x]), None)
                        patch_vsan = imm(self.type).compare_body_result(api_body, vnic_results[indx])
                        api_body['pmoid'] = kwargs.isight[kwargs.org].policy[self.type][i.names[x]]
                        if patch_vsan == True: kwargs.bulk_list.append(deepcopy(api_body))
                        else:
                            pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; {kwargs.parent_type} `{kwargs.parent_name}`: VNIC: `{i.names[x]}`."\
                                f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
                    else: kwargs.bulk_list.append(deepcopy(api_body))
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri    = ezdata.intersight_uri
            kwargs        = imm(self.type).bulk_request(kwargs)
        return kwargs

    #=======================================================
    # Assign VSANs to VSAN Policies
    #=======================================================
    def vsans(self, kwargs):
        #=======================================================
        # Loop Through VLAN Lists
        #=======================================================
        def configure_vsans(e, kwargs):
            ezdata = kwargs.ezdata[self.type]
            api_body = {'FcNetworkPolicy':{'Moid':kwargs.parent_moid, 'ObjectType':'fabric.FcNetworkPolicy'}, 'ObjectType':ezdata.ObjectType}
            api_body = imm(self.type).build_api_body(api_body, ezdata.properties, e, kwargs)
            api_body.pop('Organization'); api_body.pop('Tags')
            if not api_body.get('VsanScope'): api_body['VsanScope'] = 'Uplink'
            if not api_body.get('FcoeVlan'): api_body['FcoeVlan'] = api_body['VsanId']
            #=======================================================
            # Create or Patch the VLANs via the Intersight API
            #=======================================================
            if not kwargs.isight[kwargs.org].policy[self.type].get(str(api_body['VsanId'])): kwargs.bulk_list.append(deepcopy(api_body))
            else:
                indx = next((index for (index, d) in enumerate(kwargs.vsans_results) if d['VsanId'] == api_body['VsanId']), None)
                patch_vsan = imm(self.type).compare_body_result(api_body, kwargs.vsans_results[indx])
                api_body['pmoid']  = kwargs.isight[kwargs.org].policy[self.type][str(api_body['VsanId'])]
                if patch_vsan == True: kwargs.bulk_list.append(deepcopy(api_body))
                else:
                    pcolor.Cyan(f"      * Skipping Org: {kwargs.org}; VSAN Policy: `{kwargs.parent_name}`, VSAN: `{api_body['VsanId']}`."\
                           f"  Intersight Matches Configuration.  Moid: {api_body['pmoid']}")
            return kwargs
        #=======================================================
        # Loop Through VSAN Policies
        #=======================================================
        kwargs.bulk_list = []
        np, ns = ezfunctions.name_prefix_suffix('vsan', kwargs)
        for i in kwargs.policies:
            vnames = []
            kwargs.parent_key  = self.type.split('.')[0]
            kwargs.parent_name = f'{np}{i.name}{ns}'
            kwargs.parent_type = 'VSAN Policy'
            kwargs.parent_moid = kwargs.isight[kwargs.org].policy[self.type.split('.')[0]][kwargs.parent_name]
            kwargs.pmoid       = kwargs.parent_moid
            if i.get('vsans'):
                for e in i.vsans: vnames.append(e.vsan_id)
                kwargs = api_get(True, vnames, self.type, kwargs)
                kwargs.vsans_results= kwargs.results
                #=======================================================
                # Create API Body for VSANs
                #=======================================================
                for e in i.vsans: kwargs = configure_vsans(e, kwargs)
        #=======================================================
        # POST Bulk Request if Post List > 0
        #=======================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri    = kwargs.ezdata[self.type].intersight_uri
            kwargs        = imm(self.type).bulk_request(kwargs)
        return kwargs

#=======================================================
# Function - API Get Calls
#=======================================================
def api_get(empty, names, otype, kwargs):
    original_org = kwargs.org
    kwargs.glist = DotMap()
    for e in names:
        if '/' in str(e): org, policy = e.split('/')
        else: org = kwargs.org; policy = e
        if not kwargs.glist[org].names: kwargs.glist[org].names = []
        kwargs.glist[org].names.append(policy)
    orgs    = list(kwargs.glist.keys())
    results = []
    pmoids  = DotMap()
    for org in orgs:
        kwargs.org    = org
        kwargs.names  = kwargs.glist[org].names
        kwargs.method = 'get'
        kwargs.uri    = kwargs.ezdata[otype].intersight_uri
        kwargs        = api(otype).calls(kwargs)
        if empty == False and kwargs.results == []: empty_results(kwargs)
        else:
            if kwargs.ezdata[otype].get('intersight_type'):
                for k, v in kwargs.pmoids.items():
                    kwargs.isight[org][kwargs.ezdata[otype].intersight_type][otype][k] = v.moid
            if len(kwargs.results) > 0:
                results.extend(kwargs.results)
                pmoids = DotMap(dict(pmoids.toDict(), **kwargs.pmoids.toDict()))
    kwargs.org     = original_org
    kwargs.pmoids  = pmoids
    kwargs.results = results
    return kwargs

#=======================================================
# Function - Exit on Empty Results
#=======================================================
def empty_results(kwargs):
        pcolor.Red(f"The API Query Results were empty for {kwargs.uri}.  Exiting..."); sys.exit(1)
