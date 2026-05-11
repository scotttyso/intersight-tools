# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates.
# All rights reserved.
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, pcolor, validating
    from OpenSSL import crypto
    from copy import deepcopy
    from datetime import datetime
    from dotmap import DotMap
    from intersight_auth import IntersightAuth, repair_pem
    from operator import itemgetter
    from stringcase import snakecase
    import base64, jinja2, json, numpy, os, re, requests, time, urllib3
except ImportError as e:
    prRed(f'classes/isight.py - !!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
parent_regex   = re.compile(r'^(Parent|((Eth|Fc)Network|(L|S)anConnectivity|Ldap|Port|Storage)Policy)$')
pool_regex     = re.compile(r'^((ip|iqn|mac|uuid|fc)pool\.((Ip|Uuid)?Lease|Reservation))$')
serial_regex   = re.compile('^[A-Z]{3}[2-3][\\d]([0][1-9]|[1-4][0-9]|[5][0-3])[\\dA-Z]{4}$')
template_regex = re.compile(r'^(ucs_(server|chassis)(_profile)?_template)$')

DESCRIPTION_WORD_MAP = {
    'policies': 'Policy',
    'pools': 'Pool',
    'profiles': 'Profile',
    'templates': 'Template',
    'system': 'System'
}

#=============================================================================
# Intersight -> API Class
#=============================================================================
class api(object):
    def __init__(self, type, category=None):
        self.type = type
        self.category = category

    #=========================================================================
    # Function - Get Organizations from Intersight
    #=========================================================================
    def all_organizations(self, kwargs):
        #=====================================================================
        # Get Organization List from the API
        #=====================================================================
        kwargs = kwargs | DotMap(api_filter = 'ignore', method = 'get', uri = 'organization/Organizations')
        kwargs = api(category='system', type=self.type).calls(kwargs)
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
    def build_intersight_api_dict(self, api_results, kwargs):
        # pcolor.Yellow(f'Build API Dict for {self.category} -> {self.type}')
        api_dict    = DotMap()
        kkeys       = list(kwargs.keys())
        def function_org_moids(i, kwargs):
            okeys = list(kwargs.org_moids.keys())
            if not i.Name in okeys:
                kwargs.org_moids[i.Name] = DotMap(moid = i.Moid, tags = i.Tags)
                kwargs.org_names[i.Moid] = i.Name
            return kwargs
        def function_rsg_moids(i, kwargs):
            rkeys = list(kwargs.rsg_moids.keys())
            if not i.Name in rkeys:
                kwargs.rsg_moids[i.Name] = DotMap(moid = i.Moid, tags = i.Tags)
                kwargs.rsg_names[i.Moid] = i.Name
            return kwargs
        if not kwargs.build_skip == True and api_results.get('Results'):
            def check_for_dotmap_key(i, kkeys, kwargs):
                if not 'intersight_api' in kkeys:
                    kwargs.intersight_api = DotMap()
                    kwargs.intersight_api[kwargs.org] = DotMap()
                return kwargs
            for i in api_results.Results:
                if i.get('Body'): i = i.Body
                ikeys = list(i.keys())
                if 'system' == self.category:
                    if 'Serial'           in ikeys: iname = i.Serial
                    elif 'Key'            in ikeys: iname = i.Key
                    elif 'SharedResource' in ikeys: iname = i.Moid
                    elif 'Name'           in ikeys: iname = i.Name
                    else: iname = i.Moid
                    if self.type == 'targets':
                        kwargs.intersight_api[self.category][self.type][iname] = DotMap(moid = i.RegisteredDevice.Moid, result = i)
                    else:
                        kwargs.intersight_api[self.category][self.type][iname] = DotMap(moid = i.Moid, result = i)
                    if   'organizations'   == self.type: kwargs = function_org_moids(i, kwargs)
                    elif 'resource_groups' == self.type: kwargs = function_rsg_moids(i, kwargs)
                    continue
                elif 'organization.Organization' == i.ObjectType:
                    kwargs = function_org_moids(i, kwargs)
                    continue
                elif (any(re.search(parent_regex, e) for e in ikeys) and isinstance(kwargs.org, str)) or re.search(pool_regex, i.ObjectType):
                    if re.search(pool_regex, i.ObjectType):
                        child_type   = re.search(pool_regex, i.ObjectType).group(3).replace('Ip', '').replace('Uuid', '').lower()
                        parent_match = 'Pool';
                        if   i.get('IdPurpose'): parent_type = i.IdPurpose.lower()
                        elif i.get('PoolPurpose'): parent_type = i.PoolPurpose.lower()
                        else: parent_type  = re.search(pool_regex, i.ObjectType).group(2)
                        if   'Identity'     in ikeys: iname = i.Identity
                        elif 'IpV4Address'  in ikeys: iname = i.IpV4Address
                        elif 'IpV6Address'  in ikeys: iname = i.IpV6Address
                        elif 'IqnAddress'   in ikeys: iname = i.IqnAddress
                        elif 'MacAddress'   in ikeys: iname = i.MacAddress
                        elif 'Uuid'         in ikeys: iname = i.Uuid
                        elif 'WWnId'        in ikeys: iname = i.WWnId
                        elif 'WwnId'        in ikeys: iname = i.WwnId
                        parent_name  = kwargs.pools[parent_type][i.Pool.Moid].name
                        organization = kwargs.pools[parent_type][i.Pool.Moid].organization
                        kwargs.intersight_api[organization][self.category][parent_type][parent_name][child_type][iname] = DotMap(
                            moid   = i.Moid,
                            result = i
                        )
                        continue
                    else:
                        split_name   = kwargs.intersight_object_map[i.ObjectType].split('.')
                        parent_match = next((e for e in ikeys if re.search(parent_regex, e)), None)
                        parent_type  = split_name[0]; child_type  = split_name[1]
                        if   'PcId'         in ikeys: iname = str(i.PcId)
                        elif 'PortId'       in ikeys: iname = str(i.PortId)
                        elif 'VlanId'       in ikeys: iname = str(i.VlanId)
                        elif 'EndPointUser' in ikeys: iname = i.EndPointUser.Moid
                        elif 'PortIdStart'  in ikeys: iname = str(i.PortIdStart)
                        elif 'Server'       in ikeys: iname = i.Server
                        elif 'VsanId'       in ikeys: iname = str(i.VsanId)
                        elif 'Name'         in ikeys: iname = i.Name
                        else: iname = i.Moid
                        parent_name = kwargs.intersight_api[kwargs.org][self.category][parent_type][i[parent_match].Moid]
                        kwargs.intersight_api[kwargs.org][self.category][parent_type][parent_name][child_type][iname] = DotMap(
                            moid   = i.Moid,
                            result = i
                        )
                        continue
                elif 'Name' in ikeys and type(self.category) == str and type(kwargs.org) == str:
                    # fcpool.Pool backs both wwnn and wwpn; keep the requested
                    # pool type to avoid collapsing both into a single key.
                    if self.category == 'pools' and i.ObjectType == 'fcpool.Pool' and self.type in ['wwnn', 'wwpn']: ptype = self.type
                    else: ptype = kwargs.intersight_object_map[i.ObjectType]
                    kwargs = check_for_dotmap_key(i, kkeys, kwargs)
                    iname = i.Name
                    kwargs.intersight_api[kwargs.org][self.category][ptype][iname] = DotMap(moid = i.Moid, result = i, tags = i.Tags)
                    kwargs.intersight_api[kwargs.org][self.category][ptype][i.Moid] = iname
                    continue
                elif 'Name'    in ikeys: iname = i.Name
                elif i.ObjectType == 'asset.DeviceRegistration': iname = i.Serial[0]
                elif 'Serial'  in ikeys: iname = i.Serial
                elif 'Answers' in ikeys: iname = i.Answers.Hostname
                elif self.type == 'upgrade' and i.Status == 'IN_PROGRESS': iname = kwargs.srv_moid
                elif 'SocketDesignation' in ikeys: iname = i.Dn
                elif 'Version'           in ikeys: iname = i.Version
                elif 'ControllerId'      in ikeys: iname = i.ControllerId
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
                    api_dict[iname].name  = i.Name
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
            kwargs.pmoids = api_dict
        return kwargs

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
        debug_level = kwargs.args.debug_level
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
                        if   method ==  'get_by_moid': pcolor.Red(f'  URL: {url}/{uri}/{moid}')
                        elif method ==       'delete': pcolor.Red(f'  URL: {url}/{uri}/{moid}')
                        elif method ==          'get': pcolor.Red(f'  URL: {url}/{uri}{aargs}')
                        elif method ==        'patch': pcolor.Red(f'  URL: {url}/{uri}/{moid}')
                        elif method == 'post_by_moid': pcolor.Red(f'  URL: {url}/{uri}/{moid}')
                        elif method ==         'post': pcolor.Red(f'  URL: {url}/{uri}')
                        pcolor.Red(f'  Running Process: {method} {self.type}')
                        pcolor.Red(f'    Error status is {response}')
                        if '{' in response.text:
                            for k, v in (response.json()).items(): pcolor.Red(f"    {k} is '{v}'")
                        else: pcolor.Red(response.text)
                        sys.exit(1)
                    if   method ==  'get_by_moid': response = requests.get(   f'{url}/{uri}/{moid}', verify=False, auth=aauth)
                    elif method ==       'delete': response = requests.delete(f'{url}/{uri}/{moid}', verify=False, auth=aauth)
                    elif method ==          'get': response = requests.get(   f'{url}/{uri}{aargs}', verify=False, auth=aauth)
                    elif method ==        'patch': response = requests.patch( f'{url}/{uri}/{moid}', verify=False, auth=aauth, json=payload)
                    elif method == 'post_by_moid': response = requests.post(  f'{url}/{uri}/{moid}', verify=False, auth=aauth, json=payload)
                    elif method ==         'post': response = requests.post(  f'{url}/{uri}',        verify=False, auth=aauth, json=payload)
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
                if   method ==  'get_by_moid': pcolor.Cyan(f'URL:      {url}/{uri}/{moid}')
                elif method ==          'get': pcolor.Cyan(f'URL:      {url}/{uri}{aargs}')
                elif method ==        'patch': pcolor.Cyan(f'URL:      {url}/{uri}/{moid}')
                elif method == 'post_by_moid': pcolor.Cyan(f'URL:      {url}/{uri}/{moid}')
                elif method ==         'post': pcolor.Cyan(f'URL:      {url}/{uri}')
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
                    kwargs = self.build_intersight_api_dict(api_results, kwargs)
                elif re.search('bulk.(MoCloner|Request)', api_results.ObjectType):
                    kwargs = self.build_intersight_api_dict(api_results, kwargs)
                else:
                    kwargs.pmoid = api_results.Moid
                    if kwargs.api_body.get('Name'): kwargs.pmoids[kwargs.api_body['Name']] = kwargs.pmoid
            elif 'inventory' in kwargs.uri: pass
            elif kwargs.build_skip == False: kwargs = self.build_intersight_api_dict(api_results, kwargs)
            #=================================================================
            # Print Progress Notifications
            #=================================================================
            if re.search('(patch|post)', method):
                if api_results.get('Responses'):
                    for e in api_results.Responses:
                        kwargs.api_results = e.Body
                        validating.completed_item(self.category, self.type, kwargs)
                elif re.search('bulk.(Request|RestResult)', api_results.ObjectType):
                    for e in api_results.Results:
                        kwargs.api_results = e.Body
                        if re.search('bulk.(Request|RestResult)', api_results.ObjectType):
                            if e.Body.get('Name'):          name_key = 'Name'
                            elif e.Body.get('Identity'):    name_key = 'Identity'
                            elif e.Body.get('PcId'):        name_key = 'PcId'
                            elif e.Body.get('PortId'):      name_key = 'PortId'
                            elif e.Body.get('PortIdStart'): name_key = 'PortIdStart'
                            elif e.Body.get('Server'):      name_key = 'Server'
                            elif e.Body.get('VlanId'):      name_key = 'VlanId'
                            elif e.Body.get('VsanId'):      name_key = 'VsanId'
                            elif e.Body.ObjectType == 'iam.EndPointUserRole': pass
                            else:
                                pcolor.Red(json.dumps(e.Body, indent=4))
                                pcolor.Red('Missing name_key.  isight.py line 415')
                                len(False); sys.exit(1)
                            if not e.Body['ObjectType'] == 'iam.EndPointUserRole':
                                indx = next((index for (index, d) in enumerate(kwargs.api_body['Requests']) if d['Body'][name_key] == e.Body[name_key]), None)
                                kwargs.method = (kwargs.api_body['Requests'][indx]['Verb']).lower()
                        validating.completed_item(self.category, self.type, kwargs)
                else:
                    kwargs.api_results = api_results
                    validating.completed_item(self.category, self.type, kwargs)
            return kwargs
        #=====================================================================
        # Pagenation for Get > 1000
        #=====================================================================
        kwargs_keys = list(kwargs.keys())
        if kwargs.method == 'get':
            def build_api_args(kwargs_keys, kwargs):
                scategory = self.category; stype = self.type
                if not 'api_filter' in kwargs_keys:
                    regex1 = re.compile('moid_filter|registered_device|workflow_os_install')
                    regex2 = re.compile('(ip|iqn|mac|uuid|wwnn|wwpn)_leases')
                    if re.search('(vlans|vsans)', self.type): names = ", ".join(map(str, kwargs.names))
                    else: names = "', '".join(kwargs.names).strip("', '")
                    if re.search('organizations|resource_groups', self.type): api_filter = f"Name in ('{names}')"
                    elif self.category == 'system':
                        sregex = re.compile('^(blades|chassis|domain||rackmounts|server)')
                        if 'iam_end_point_role'  == self.type: api_filter = f"Name in ('{names}') and Type eq 'IMC'"
                        elif 'iam_sharing_rules' == self.type: api_filter = f"SharedResource/Moid in ('{names}')"
                        elif 'path_tags'         == self.type: api_filter = f"Key in ('{names}')"
                        elif re.search(sregex, self.type):     api_filter = f"Serial in ('{names}')"
                        else: api_filter = f"Name in ('{names}')"
                    elif 'pools' in scategory and '.leases'       in stype: api_filter = f"Pool/Moid in ('{names}')"
                    elif 'pools' in scategory and '.reservations' in stype: api_filter = f"Pool/Moid in ('{names}')"
                    elif 'ancestors'            == self.type: api_filter = f"Ancestors/any(t:t/Moid in ('{names}'))"
                    elif 'asset_target'         == self.type: api_filter = f"TargetId in ('{names}')"
                    elif 'connectivity.v' in self.type:       api_filter = f"Parent/Moid in ('{names}')"
                    elif 'hcl_status' == self.type:           api_filter = f"ManagedObject/Moid in ('{names}')"
                    elif 'iam_end_point_role' == self.type:   api_filter = f"Name in ('{names}') and Type eq 'IMC'"
                    elif 'iqn_pool_leases' == self.type:      api_filter = f"AssignedToEntity.Moid in ('{names}')"
                    elif 'multi_org' in self.type:            api_filter = f"Organization.Moid in ('{names}')"
                    elif re.search('ldap.ldap_', self.type):  api_filter = f"LdapPolicy/Moid in ('{names}')"
                    elif 'parent_moids' in self.type:         api_filter = f"{kwargs.parent}/Moid in ('{names}')"
                    elif 'port.port_' in self.type:           api_filter = f"Parent/Moid in ('{names}')"
                    elif 'profile_moid' == self.type:         api_filter = f"Profile.Moid in ('{names}')"
                    elif re.search(regex1, self.type):        api_filter = f"Moid in ('{names}')"
                    elif re.search(regex2, self.type):        api_filter = f"{kwargs.pkey} in ('{names}')"
                    elif 'registered_device' in self.type:    api_filter = f"RegisteredDevice.Moid in ('{names}')"
                    elif 'reservations' in self.type:         api_filter = f"Identity in ('{names}')"
                    elif 'serial_number' == self.type:        api_filter = f"Serial in ('{names}')"
                    elif 'storage.drive_groups' == self.type: api_filter = f"Parent/Moid in ('{names}')"
                    elif '.switch' in stype and 'templates' == scategory: api_filter = f"SwitchClusterProfileTemplate/Moid in ('{names}')"
                    elif '.switch' in self.type:              api_filter = f"SwitchClusterProfile/Moid in ('{names}')"
                    elif 'user_role' == self.type:            api_filter = f"EndPointUser/Moid in ('{names}') and EndPointUserPolicy/Moid eq '{kwargs.pmoid}'"
                    elif re.search('v.an\.v.ans', self.type): api_filter = f"Parent/Moid in ('{names}')"
                    elif 'wwnn_pool_leases' == self.type:     api_filter = f"PoolPurpose eq 'WWNN' and AssignedToEntity/Moid in ('{names}')"
                    elif 'wwpn_pool_leases' == self.type:     api_filter = f"PoolPurpose eq 'WWPN' and AssignedToEntity/Moid in ('{names}')"
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
                prev_build_skip = kwargs.get('build_skip', False)
                kwargs.build_skip = True
                kwargs = api_calls(kwargs)
                kwargs.build_skip = prev_build_skip
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
        kwargs = kwargs | DotMap(method = 'get', uri = kwargs.ezdata['intersight.profiles.chassis'].intersight_uri)
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
    # Function - Get Organizations from Intersight
    #=========================================================================
    def organizations(self, kwargs):
        #=====================================================================
        # Functions to Create Resource Groups and Organizations
        #=====================================================================
        def create_resource_group(rg, org, kwargs):
            api_body = {'Description':f'{rg} Resource Group','Name':rg}
            kwargs = kwargs | DotMap(api_body = api_body, method = 'post', org = org, uri = 'resource/Groups')
            kwargs = api('resource_groups').calls(kwargs)
            if rg not in kwargs.rsg_moids: kwargs.rsg_moids[rg] = DotMap()
            kwargs.rsg_moids[rg].moid      = kwargs.results.Moid
            kwargs.rsg_moids[rg].selectors = kwargs.results.Selectors
            return kwargs
        def create_org_api_call(api_body, kwargs):
            kwargs = kwargs | DotMap(api_body = api_body, method = 'post', uri = 'organization/Organizations')
            kwargs = api(self.type).calls(kwargs)
            kwargs.org_moids[org].moid = kwargs.results.Moid
            return kwargs
        def create_shared_organization(o, kwargs):
            api_body = {'Description':f'{o} Organization','Name':o}
            kwargs = create_org_api_call(api_body, kwargs)
            return kwargs
        def create_org_question(org, kwargs):
            if kwargs.args.non_interactive: return True
            kwargs.jdata = DotMap(
                default     = True,
                description = f'  The organization `{org}` does not exist.  Do you want to create it?',
                sort        = False,
                title       = 'Intersight Organization',
                type        = 'boolean')
            return ezfunctions.variable_prompt(kwargs)
        def organization_type(org, kwargs):
            if kwargs.args.non_interactive: return 'Targets'
            kwargs.jdata = DotMap(
                default     = 'Targets',
                description = f'  Will the organization `{org}` be shared with other organizations, or will you be assigning targets (servers, domains, etc.)?',
                enum        = ['Shared', 'Targets'],
                sort        = False,
                title       = 'Intersight Organization',
                type        = 'string')
            return ezfunctions.variable_prompt(kwargs)
        def create_organization(org, okeys, kwargs):
            if 'resource_groups' in okeys and len(kwargs.imm_dict.orgs[org].resource_groups) > 0:
                for rg in kwargs.imm_dict.orgs[org].resource_groups:
                    if not rg in list(kwargs.rsg_moids.keys()): kwargs = create_resource_group(rg, org, kwargs)
                rgs = [{'Moid':kwargs.rsg_moids[rg].moid,'ObjectType':'resource.Group'} for rg in kwargs.imm_dict.orgs[org].resource_groups]
                api_body = {'Description':f'{org} Organization','Name':org,'ResourceGroups':rgs}
                kwargs = create_org_api_call(api_body, kwargs)
            elif 'organizations_to_share_with' in okeys and len(kwargs.imm_dict.orgs[org].organizations_to_share_with) > 0:
                for o in kwargs.imm_dict.orgs[org].organizations_to_share_with:
                    if not o in list(kwargs.org_moids.keys()):
                        create_org = create_org_question(o, kwargs)
                        if create_org == True: kwargs = create_shared_organization(o, kwargs)
                        else: validating.error_organization(o)
                shared_orgs = [{'Moid':kwargs.org_moids[o].moid,'ObjectType':'organization.Organization'} for o in kwargs.imm_dict.orgs[org].organizations_to_share_with]
                api_body = {'Description':f'{org} Organization','Name':org,'SharedWithResources':shared_orgs}
                kwargs = create_org_api_call(api_body, kwargs)
            else:
                org_type = organization_type(org, kwargs)
                if org_type == 'Shared':
                    api_body = {'Description':f'{org} Organization','Name':org,'SharedWithResources':[]}
                    kwargs = create_org_api_call(api_body, kwargs)
                else:
                    kwargs = create_resource_group(org, org, kwargs)
                    api_body = {'Description':f'{org} Organization','Name':org,'ResourceGroups':[{'Moid':kwargs.rsg_moids[org].moid,'ObjectType':'resource.Group'}]}
                    kwargs = create_org_api_call(api_body, kwargs)
            return kwargs
        if self.type == 'resource_groups':
            kwargs = kwargs | DotMap(method = 'get', names = kwargs.resource_groups, uri = 'resource/Groups')
            kwargs = api('resource_groups').calls(kwargs)
            kwargs.rsg_results = kwargs.rsg_results + kwargs.results
            for e in kwargs.pmoids:
                kwargs.rsg_moids[e] = DotMap(kwargs.pmoids[e])
            for rsg in kwargs.resource_groups:
                if not rsg in list(kwargs.rsg_moids.keys()):
                    kwargs = create_resource_group(rsg, org, kwargs)
        else:
            #=====================================================================
            # Get Resource Groups from the API
            #=====================================================================
            rsg_list = []
            for org in kwargs.orgs:
                rsg_keys = list(kwargs.imm_dict.orgs[org].keys())
                if 'resource_groups' in rsg_keys and len(kwargs.imm_dict.orgs[org].resource_groups) > 0:
                    for rg in kwargs.imm_dict.orgs[org].resource_groups: rsg_list.append(rg)
            names  = list(numpy.unique(numpy.array(rsg_list + kwargs.orgs)))
            kwargs = kwargs | DotMap(method = 'get', names = names, uri = 'resource/Groups')
            kwargs = api(category=self.category, type='resource_groups').calls(kwargs)
            kwargs = kwargs | DotMap(rsg_moids = kwargs.pmoids, rsg_results = kwargs.results)
            #=====================================================================
            # Get Organizations from the API
            #=====================================================================
            kwargs = kwargs | DotMap(method = 'get', names = kwargs.orgs, uri = 'organization/Organizations')
            kwargs = api(category=self.category, type='organizations').calls(kwargs)
            kwargs = kwargs | DotMap(org_moids = kwargs.pmoids, org_results = kwargs.results)
            #=====================================================================
            # Loop thru the List of Organizations and Create if They Don't Exist
            #=====================================================================
            okeys = list(kwargs.org_moids.keys())
            for org in kwargs.orgs:
                if not org in okeys:
                    okeys = list(kwargs.imm_dict.orgs[org].keys())
                    if 'create_organization' in okeys and kwargs.imm_dict.orgs[org].create_organization == True:
                        kwargs = create_organization(org, okeys, kwargs)
                    else:
                        create_org = create_org_question(org, kwargs)
                        if create_org == True: kwargs = create_organization(org, okeys, kwargs)
                        else: validating.error_organization(org)
        return kwargs

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
        kwargs = kwargs | DotMap(method = 'get', names = [v.moid for k,v in kwargs.server_profiles.items()], uri = kwargs.ezdata['intersight.profiles.server'].intersight_uri)
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
        kwargs = kwargs | DotMap(method = 'get', uri = kwargs.ezdata['intersight.profiles.server'].intersight_uri)
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

#=============================================================================
# Intersight -> Configure -> Policies/Pools/Profiles/Templates
#=============================================================================
class configure(object):
    def __init__(self, type, category=None):
        self.type = type
        self.category = category

    #=========================================================================
    # Function - API Get Calls
    #=========================================================================
    def api_get(self, empty=False, names=None, otype=None, kwargs=None):
        if names is None: names = []
        if kwargs is None: kwargs = DotMap()
        if otype is None: otype = self.type
        category = self.category
        #=====================================================================
        # Function - Exit on Empty Results
        #=====================================================================
        def empty_results(org, names, kwargs):
            pcolor.Red(f"The API Query Results were empty for {kwargs.uri}.");
            pcolor.Red(f"  Organization: {org}");
            pcolor.Red(f"  Names: `{', '.join(names)}`");
            pcolor.Red(f"Exiting..."); sys.exit(1)

        original_org = kwargs.org; kwargs.glist = DotMap()
        for e in names:
            org, policy = self.determine_resource_organization(False, e, kwargs)
            if not kwargs.glist[org].names: kwargs.glist[org].names = []
            kwargs.glist[org].names.append(policy)
        orgs = list(kwargs.glist.keys()); results = []; pmoids  = DotMap()
        missing_orgs = [kwargs.orgs.append(o) for o in orgs if not o in list(kwargs.org_moids)]
        if len(missing_orgs) > 0: kwargs = api('organizations').organizations(kwargs)
        for org in orgs:
            names  = kwargs.glist[org].names
            kwargs = kwargs | DotMap(names = names, org = org, method = 'get', uri = kwargs.ezdata[f"intersight.{self.category}.{otype}"].intersight_uri)
            kwargs = api(self.type, category=self.category).calls(kwargs)
            if empty == False and kwargs.results == []: empty_results(org, names,kwargs)
            elif empty == True and kwargs.results == []:
                pcolor.Yellow(f"  * API Query Results were empty for {kwargs.uri} with Organization: {org}")
                pcolor.Yellow(f"    - Names: `{', '.join(names)}`.  Continuing..."); continue
        kwargs.org = original_org
        return kwargs

    #=========================================================================
    # Function - Lookup Certificate and Private Key Files, Check for Validity, and Return Contents
    #=========================================================================
    def cert_file_check(self, expected_type, file_path, item):
        # Expand ~ to home directory
        file_path = os.path.expanduser(file_path)
        if not isinstance(file_path, str) or len(file_path.strip()) == 0:
            pcolor.Red(f'!!! ERROR !!! `{expected_type}` file path is empty for certificate policy `{item.name}`.')
            sys.exit(1)
        if not os.path.isfile(file_path):
            pcolor.Red(f'!!! ERROR !!! `{expected_type}` file `{file_path}` was not found for certificate policy `{item.name}`.')
            sys.exit(1)
        try:
            with open(file_path, 'r', encoding='utf-8') as cert_file:
                cert_content = cert_file.read()
        except OSError as exc:
            pcolor.Red(f'!!! ERROR !!! Failed to read `{expected_type}` file `{file_path}` for certificate policy `{item.name}`: {exc}')
            sys.exit(1)

        if 'BEGIN CERTIFICATE' in cert_content:
            try:
                crypto.load_certificate(crypto.FILETYPE_PEM, cert_content)
            except Exception as exc:
                pcolor.Red(f'!!! ERROR !!! `{file_path}` is not a valid PEM certificate: {exc}')
                sys.exit(1)
            detected_type = 'certificate'
        elif 'PRIVATE KEY' in cert_content:
            try:
                crypto.load_privatekey(crypto.FILETYPE_PEM, cert_content)
            except Exception as exc:
                pcolor.Red(f'!!! ERROR !!! `{file_path}` is not a valid PEM private key: {exc}')
                sys.exit(1)
            detected_type = 'private_key'
        else:
            pcolor.Red(f'!!! ERROR !!! `{file_path}` is not a valid PEM certificate or private key file.')
            sys.exit(1)
        if detected_type != expected_type:
            pcolor.Red(f'!!! ERROR !!! `{file_path}` contains a `{detected_type}` but `{expected_type}` was expected.')
            sys.exit(1)
        cert_content = base64.b64encode(cert_content.encode('utf-8')).decode('utf-8')

        return cert_content

    #=========================================================================
    # Function - Assign Children Resources to Parent Resources
    #=========================================================================
    def children_check_parent(self, child_type, kwargs):
        org = kwargs.org
        np, ns = self.name_prefix_suffix(kwargs.org, kwargs)
        #=====================================================================
        # Get Existing Assignments for Each Parent Policy.
        # Skip if No Parent Policies Exist or if Running in Check Mode.
        #=====================================================================
        continue_count = 0
        ikeys = list(kwargs.intersight_api[org][self.category][self.type].keys())
        pcategory = self.category.replace('_', ' ').title()
        ptitle    = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        for e in kwargs.resources:
            ekeys = list(e.keys())
            if f"{np}{e.name}{ns}" in ikeys and child_type in ekeys: continue_count += 1
            elif child_type in ekeys and kwargs.args.check == True:
                pcolor.Cyan(f"\n     * Running in Check Mode")
                pcolor.Cyan(f"       - Skipping {ptitle} {pcategory} Children Retrieval for Org: {org} > {ptitle}:")
                pcolor.Cyan(f"         because `{np}{e.name}{ns}` parent {ptitle} doesn't exists in Intersight.")
            elif child_type in ekeys:
                pcolor.Cyan(f"       - Skipping {ptitle} {pcategory} Children Retrieval for Org: {org} > {ptitle}:")
                pcolor.Cyan(f"         because `{np}{e.name}{ns}` parent {ptitle} doesn't exist in Intersight.")
        #=====================================================================
        # See if Children are already in Intersight
        #=====================================================================
        if continue_count > 0:
            names = []
            for e in kwargs.resources:
                names.append(kwargs.intersight_api[org][self.category][self.type][np + e.name + ns].moid)
            kwargs = configure(f'{self.type}.{child_type}', category=self.category).api_get(True, names, f'{self.type}.{child_type}', kwargs)
        return continue_count, kwargs

    #=========================================================================
    # Function - Compare Children Resources API Body to Existing API Results 
    # and Append to Bulk List if Differences or No Existing Resource.
    #=========================================================================
    def children_compare_api_body(self, api_body, kwargs):
        org = kwargs.org
        if 'port_channel'   in self.type: pkey = 'PcId'
        elif 'port_mode'    in self.type: pkey = 'PortIdStart'
        elif 'port_role'    in self.type: pkey = 'PortId'
        elif 'provider'     in self.type: pkey = 'Server'
        elif 'vlans'        in self.type: pkey = 'VlanId'
        elif 'vsans'        in self.type: pkey = 'VsanId'
        elif 'ldap_servers' in self.type: pkey = 'Server'
        else: pkey = 'Name'
        akeys        = list(api_body.keys())
        check_flag   = getattr(kwargs.args, 'check', False)
        child_type   = self.type.split('.')[1]
        child_title  = ezfunctions.mod_pol_description(child_type.replace('_', ' ').title())
        parent_moid  = api_body['Parent']['Moid']
        parent_type  = self.type.split('.')[0]
        parent_name  = kwargs.intersight_api[org][self.category][parent_type][parent_moid]
        kwargs.uri   = kwargs.ezdata[f"intersight.{self.category}.{self.type}"].intersight_uri
        policy_title = ezfunctions.mod_pol_description(((self.type.replace('_', ' ').replace('.', ' : '))).capitalize())
        if 'Description' in akeys and api_body['Description'] == '':
            api_body['Description'] = f'{api_body["Name"]} {policy_title} {self.category.capitalize()}.'
        parent_title = ezfunctions.mod_pol_description(parent_type.replace('_', ' ').title())
        category     = self.category.replace('ies', 'y').replace('pools', 'pool').title()
        ptitle       = parent_title + ' ' + category
        # If parent_name is not a string the parent policy doesn't exist in Intersight yet;
        # treat the child as new and queue it for creation.
        if not isinstance(parent_name, str):
            if not check_flag: kwargs.bulk_list.append(deepcopy(api_body))
            else:
                pcolor.Cyan(f"     * Running Check Mode: Organization: `{org}`; Non-Check mode would create new {ptitle}: (new) - {child_title}: `{api_body[pkey]}`.")
            return kwargs
        child_dict   = kwargs.intersight_api[org][self.category][parent_type][parent_name][child_type]
        ikeys        = list(child_dict.keys())
        pval         = api_body[pkey] if re.search('groups|users|vnic|vhbas|ldap_servers|ldap_groups', self.type) else str(api_body[pkey])
        if pval in ikeys:
            resource     = child_dict[pval].result
            patch_policy = self.compare_body_result(api_body, resource)
            api_body['pmoid'] = child_dict[pval].moid
            pmoid = api_body['pmoid']
            if patch_policy == True:
                if check_flag == True:
                    pcolor.Cyan(f"     * Running Check Mode: Organization: `{org}`;")
                    pcolor.Cyan(f"       Non-Check mode would update {ptitle}: `{parent_name}` - {child_title}: `{api_body[pkey]}`.  Moid: `{pmoid}`")
                else: kwargs.bulk_list.append(deepcopy(api_body))
            else:
                pcolor.Cyan(f"     * Skipping Organization: `{org}`; {ptitle}: `{parent_name}` - {child_title}: `{api_body[pkey]}`"\
                            f"  Moid: `{pmoid}`.  Intersight Matches Configuration.")
        else:
            if check_flag == True:
                pcolor.Cyan(f"     * Running Check Mode: Organization: `{org}`; Non-Check mode would create new {ptitle}: `{parent_name}` - {child_title}: `{api_body[pkey]}`.")
            else: kwargs.bulk_list.append(deepcopy(api_body))
        return kwargs

    #=========================================================================
    # Function - Assign Children Resources to Parent Resources
    #=========================================================================
    def children_resources(self, child_type, kwargs):
        continue_count, kwargs = self.children_check_parent(child_type, kwargs)
        if continue_count == 0: return kwargs
        #=====================================================================
        # See if Children are already in Intersight
        #=====================================================================
        org = kwargs.org
        np, ns = self.name_prefix_suffix(kwargs.org, kwargs)
        names = []
        for e in kwargs.resources:
            names.append(kwargs.intersight_api[org][self.category][self.type][np + e.name + ns].moid)
        kwargs = configure(category=self.category, type=f'{self.type}.{child_type}').api_get(True, names, f'{self.type}.{child_type}', kwargs)
        #=====================================================================
        # Create API Body for Sub Items and Compare to Existing API Results.
        # If Differences or No Existing Resource, Append to Bulk List for
        # POST/PATCH.  If No Differences, Skip.
        #=====================================================================
        kwargs.bulk_list = []
        for e in kwargs.resources:
            ekeys = list(e.keys())
            if child_type in ekeys:
                parent_moid = kwargs.intersight_api[org][self.category][self.type][np + e.name + ns].moid
                for item in e[child_type]:
                    item.parent = parent_moid
                    child_np = ''
                    child_ns = ''
                    api_body = configure(f'{self.type}.{child_type}', category=self.category).create_api_body(item, child_np, child_ns, kwargs)
                    kwargs   = configure(f'{self.type}.{child_type}', category=self.category).children_compare_api_body(api_body, kwargs)
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.{self.type}.{child_type}"].intersight_uri
            kwargs     = configure(f'{self.type}.{child_type}', category=self.category).create_bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Compare Body Result for Differences
    #=========================================================================
    def compare_body_result(self, api_body, result):
        if 'port_channel' in self.type: pkey = 'PcId'
        elif 'port_mode' in self.type: pkey = 'PortIdStart'
        elif 'port_role' in self.type: pkey = 'PortId'
        elif 'provider' in self.type: pkey = 'Server'
        elif 'vlans' in self.type: pkey = 'VlanId'
        elif 'vsan' in self.type: pkey = 'VsanId'
        else: pkey = 'Name'
        expected = deepcopy(api_body)
        current  = deepcopy(result)
        differences = []

        def list_sort_key(value, path=''):
            if path.endswith('Tags') and isinstance(value, dict):
                tag_key = str(value.get('Key', value.get('key', ''))).strip().lower()
                return (0, 0, tag_key)
            if path.endswith('PolicyBucket') and isinstance(value, dict):
                object_type = str(value.get('ObjectType', value.get('objectType', ''))).strip().lower()
                moid = str(value.get('Moid', value.get('moid', ''))).strip().lower()
                return (0, 0, object_type, moid)
            if self.type == 'system_qos' and path == 'Classes' and isinstance(value, dict):
                class_name = value.get('Name', value.get('name'))
                if class_name is not None:
                    return (0, 0, str(class_name).strip().lower())
            if isinstance(value, dict):
                priority = value.get('Priority', value.get('priority'))
                if priority is not None:
                    try:
                        pnum = int(priority)
                        return (0, 0, pnum)
                    except (TypeError, ValueError):
                        return (0, 1, str(priority))
            try:
                return (1, 0, json.dumps(value, sort_keys=True))
            except TypeError:
                return (1, 1, str(value))

        def normalize_for_compare(value, path=''):
            if isinstance(value, dict):
                return {
                    k: normalize_for_compare(v, f'{path}.{k}' if path else k)
                    for k, v in value.items()
                }
            if isinstance(value, list):
                normalized_list = [
                    normalize_for_compare(v, f'{path}[{idx}]' if path else f'[{idx}]')
                    for idx, v in enumerate(value)
                ]
                if self.type == 'boot_order' and path == 'BootDevices':
                    return normalized_list
                return sorted(normalized_list, key=lambda v: list_sort_key(v, path))
            return value

        expected = normalize_for_compare(expected)
        current  = normalize_for_compare(current)

        def is_sensitive_path(path, key_name=''):
            check = f'{path}.{key_name}'.lower() if key_name else str(path).lower()
            sensitive_terms = (
                'password',
                'passphrase',
                'private_key',
                'privatekey',
                'existingkey',
                'newkey',
                'secret',
                'token',
            )
            return any(term in check for term in sensitive_terms)

        def sanitize_for_display(value, path='', key_name=''):
            if is_sensitive_path(path, key_name):
                return '__SENSITIVE__'
            return value

        def format_value(value):
            if value == '__SENSITIVE__':
                return 'sensitive'
            try:
                text = json.dumps(value, sort_keys=True)
            except TypeError:
                text = str(value)
            if len(text) > 180:
                return f"{text[:177]}..."
            return text

        def record_diff(path, expected_value, current_value, reason='value mismatch', key_name=''):
            expected_display = sanitize_for_display(expected_value, path, key_name)
            current_display  = sanitize_for_display(current_value, path, key_name)
            differences.append(
                f"{path or '<root>'}: {reason} | expected={format_value(expected_display)} | current={format_value(current_display)}"
            )

        def values_differ(v1, v2, path='', key_name=''):
            changed = False
            if isinstance(v1, dict):
                if not isinstance(v2, dict):
                    record_diff(path, v1, v2, 'type mismatch', key_name)
                    return True
                for k, v in v1.items():
                    k_path = f'{path}.{k}' if path else k
                    if k not in v2:
                        record_diff(k_path, v, None, 'missing key', k)
                        changed = True
                        continue
                    if values_differ(v, v2[k], k_path, k):
                        changed = True

                return changed

            if isinstance(v1, list):
                if not isinstance(v2, list):
                    record_diff(path, v1, v2, 'type mismatch', key_name)
                    return True
                # Compare tags by Key so extra API-managed tags do not shift index alignment.
                if path.endswith('Tags') and all(isinstance(item, dict) for item in v1):
                    v2_by_key = {
                        str(tag.get('Key', tag.get('key'))): tag
                        for tag in v2
                        if isinstance(tag, dict) and (tag.get('Key') is not None or tag.get('key') is not None)
                    }
                    for tag in v1:
                        tkey = str(tag.get('Key', tag.get('key')))
                        tpath = f'{path}[Key={tkey}]'
                        if tkey not in v2_by_key:
                            record_diff(tpath, tag, None, 'missing tag key', 'Key')
                            changed = True
                            continue
                        if values_differ(tag, v2_by_key[tkey], tpath, 'Key'):
                            changed = True
                    return changed
                if len(v2) < len(v1):
                    record_diff(path, v1, v2, 'list length/type mismatch', key_name)
                    changed = True
                for idx, item in enumerate(v1):
                    if idx >= len(v2):
                        break
                    idx_path = f'{path}[{idx}]' if path else f'[{idx}]'
                    if values_differ(item, v2[idx], idx_path, key_name):
                        changed = True
                return changed

            if v1 != v2:
                record_diff(path, v1, v2, 'value mismatch', key_name)
                return True
            return False

        changed = values_differ(expected, current)
        if changed and len(differences) > 0:
            pcolor.Yellow(f'     - Differences found for `{self.type}` -> name: {api_body[pkey]} ({len(differences)}):')
            max_show = 1024
            for diff in differences[:max_show]:
                pcolor.Yellow(f'       * {diff}')
            if len(differences) > max_show:
                pcolor.Yellow(f'       * ... {len(differences) - max_show} additional differences omitted')
        return changed

    #=========================================================================
    # Function - If Modified, Patch the Resource via the Intersight API
    #=========================================================================
    def compare_resources_to_api(self, api_body, ptitle, kwargs):
        category   = self.category.replace('_', ' ').title()
        kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.{self.type}"].intersight_uri
        check_flag = getattr(kwargs.args, 'check', False)
        akeys      = list(api_body.keys())
        if 'Description' in akeys and api_body['Description'] == '':
            word = self.category
            api_body['Description'] = f'{api_body["Name"]} {ptitle} {re.sub(r"s$", "", DESCRIPTION_WORD_MAP.get(word, word))}.'
        if api_body['Name'] in kwargs.intersight_api[kwargs.org][self.category][self.type]:
            intersight_api = kwargs.intersight_api[kwargs.org][self.category][self.type][api_body['Name']]
            patch_resource = self.compare_body_result(api_body, intersight_api.result)
            api_body['pmoid']  = intersight_api.moid
            if patch_resource == True:
                if check_flag == True:
                    pcolor.Cyan(f"     * Running Check Mode: Organization: `{kwargs.org}`; Non-Check mode would update {category} -> {ptitle}: `{api_body['Name']}`."\
                                f"  Moid: `{api_body['pmoid']}`")
                else:
                    kwargs.bulk_list.append(deepcopy(api_body))
                    kwargs.pmoids[api_body['Name']].moid = api_body['pmoid']
            else: pcolor.Cyan(f"     * Skipping Organization: `{kwargs.org}`; {category} -> {ptitle}: `{api_body['Name']}` - Moid: `{api_body['pmoid']}`."\
                                f"  Intersight Matches Configuration.")
        else:
            if check_flag == True:
                pcolor.Cyan(f"     * Running Check Mode: Organization: `{kwargs.org}`; Non-Check mode would create new {category} -> {ptitle}: `{api_body['Name']}`.")
            else: kwargs.bulk_list.append(deepcopy(api_body))
        return kwargs

    #=========================================================================
    # Function - Compare Intersight API to IMM Dictionary `configure`
    #=========================================================================
    def configure(self, kwargs):
        #=====================================================================
        # Send Begin Notification and Load Variables
        #=====================================================================
        ptitle = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        validating.section_begin_org(kwargs.org, ptitle, self.category.title())
        pcolor.LightGray('')
        idata = DotMap(dict(pair for d in kwargs.ezdata[f"intersight.{self.category}.{self.type}"].allOf for pair in d.properties.items()))
        rdict = deepcopy(kwargs.imm_dict.orgs[kwargs.org][self.category][self.type])
        if   self.type == 'port':   reconcile_resources = list({v.names[0]:v for v in rdict}.values())
        elif self.type == 'firmware_authenticate':
            kwargs = self.firmware_authenticate(kwargs)
            validating.section_end_org(kwargs.org, ptitle, self.category.title())
            return kwargs
        elif self.category == 'templates' and not re.search('(vnic|vhba)_template', self.type):
            reconcile_resources = list({v.name:v for v in rdict if v.get('create_template', False) is True}.values())
        elif self.category == 'profiles' and re.search('(chassis|server)', self.type):
            reconcile_resources = list({t.name:p | t for p in rdict for t in p.targets}.values())
            for v in reconcile_resources: v.pop('targets', None)
        else: reconcile_resources = list({v.name:v for v in rdict}.values())
        kwargs.idata = idata
        #=====================================================================
        # Get Existing Resources
        #=====================================================================
        np, ns = self.name_prefix_suffix(kwargs.org, kwargs)
        names = []
        for e in reconcile_resources:
            if self.type == 'port': names.extend([f'{np}{e.names[x]}{ns}' for x in range(0,len(e.names))])
            else: names.append(f"{np}{e['name']}{ns}")
        kwargs = self.api_get(True, names, self.type, kwargs)
        #=====================================================================
        # Validate the Sub Resources are defined or get Moids
        #=====================================================================
        if self.category == 'templates' and not re.search('(vnic|vhba)_template', self.type):
            reconcile_resources = list({v.name:v for v in rdict}.values())
        regex1  = re.compile(r'id_mapping|imc_access|ip|iscsi_boot|(l|s)an_connectivity|organizations|port|resource|(vhba|vnic)_template|vlan', re.IGNORECASE)
        regex2  = re.compile(r'(chassis|domain|server|unified_edge)', re.IGNORECASE)
        regcomb = re.compile('|'.join([regex1.pattern, regex2.pattern]), re.IGNORECASE)
        if re.search(regcomb, self.type):
            kwargs.cp = DotMap()
            updated_resources = []
            for e in reconcile_resources:
                e, kwargs = self.existing_check(e, kwargs)
                updated_resources.append(e)
            reconcile_resources = updated_resources
            if not re.search('id_mapping', self.type):
                for e in list(kwargs.cp.keys()):
                    if len(kwargs.cp[e].names) > 0:
                        names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                        category = kwargs.cp[e].get('category', self.category)
                        kwargs = configure(e, category=category).api_get(False, names, e, kwargs)
        if re.search('profiles|templates', self.category):
            kwargs.policies = DotMap()
            kwargs.pools    = DotMap()
            for key, value in kwargs.intersight_api.items():
                for k, v in value.policies.items():
                    kwargs.policies.setdefault(k, DotMap())
                    for a,b in v.items():
                        if hasattr(b, 'moid'):
                            kwargs.policies[k][b.moid] = DotMap(name=a, organization=key)
                for k, v in value.pools.items():
                    kwargs.pools.setdefault(k, DotMap())
                    for a,b in v.items():
                        if hasattr(b, 'moid'):
                            kwargs.pools[k][b.moid] = DotMap(name=a, organization=key)
            if self.category == 'templates':
                for e in reconcile_resources: kwargs.imm_templates[kwargs.org].templates[self.type][f'{np}{e.name}{ns}'] = e
                reconcile_resources = list({v.name:v for v in reconcile_resources if v.get('create_template', False) is True}.values())
        #=====================================================================
        # If Domain or Unified Edge or Chassis/Server Profiles process all resources in function
        #=====================================================================
        kwargs.resources = deepcopy(reconcile_resources)
        if self.category == 'profiles' and re.search(r'(chassis|server)', self.type):
            kwargs = getattr(self, f'profiles_{self.type}')(kwargs)
            return kwargs
        elif re.search(r'(domain|unified_edge)', self.type):
            kwargs = getattr(self, f'{self.category}_{self.type}')(kwargs)
            return kwargs
        #=====================================================================
        # Else Loop through Resource Items
        #=====================================================================
        kwargs.bulk_list = []
        for item in reconcile_resources:
            if self.type == 'port':
                for x in range(0, len(item.names)):
                    # Construct api_body Payload
                    item.name = item.names[x]
                    api_body  = self.create_api_body(item, np, ns, kwargs)
                    kwargs    = self.compare_resources_to_api(api_body, ptitle, kwargs)
            else:
                # Construct api_body Payload
                api_body = self.create_api_body(item, np, ns, kwargs)
                kwargs   = self.compare_resources_to_api(api_body, ptitle, kwargs)
        #=====================================================================
        # POST Bulk Request if List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.{self.type}"].intersight_uri
            kwargs     = self.create_bulk_request(kwargs)
        #=====================================================================
        # Loop Thru Sub-Items
        #=====================================================================
        kwargs.resources = deepcopy(reconcile_resources)
        if 'port' == self.type: kwargs = self.policies_port_children(kwargs)
        elif 'snmp' == self.type: kwargs = self.policies_snmp(kwargs)
        elif re.search(r'^ldap|local_user||(l|s)an_connectivity|storage|v(l|s)an$', self.type):
            sub_list = ['lan_connectivity.vnics', 'lan_connectivity.vnics_from_template', 'ldap.ldap_groups', 'ldap.ldap_servers', 'local_user.users',
                'san_connectivity.vhbas', 'san_connectivity.vhbas_from_template', 'storage.drive_groups', 'vlan.vlans', 'vsan.vsans']
            for e in sub_list:
                a, b = e.split('.')
                if a == self.type:
                    scount = 0
                    for i in kwargs.resources:
                        ikeys = list(i.keys())
                        if b in ikeys: scount += 1
                    if scount > 0: kwargs = getattr(self, f'policies_{a}_{b}')(kwargs)
        #=====================================================================
        # Send End Notification and return kwargs
        #=====================================================================
        validating.section_end_org(kwargs.org, ptitle, self.category.title())
        return kwargs

    #=========================================================================
    # Function - Create API Request Body
    #=========================================================================
    def create_api_body(self, item, np, ns, kwargs):
        regex = re.compile(r'bios|certificate_management|drive_security|(ethernet|fibre_channel)_adapter|storage|system_qos')
        if re.fullmatch(regex, self.type):
            item = getattr(self, f'policies_{self.type}')(item, kwargs)
        elif self.category == 'templates' and re.search('(chassis|server)', self.type):
            item = getattr(self, f'templates_{self.type}')(item, kwargs)
        elif self.category == 'profiles' and re.search('(chassis|server)', self.type):
            item = getattr(self, 'profiles_templates_create_policy_bucket')(item, kwargs)

        item  = self.merge_tags(item, kwargs)
        
        template_dir  = os.path.join(kwargs.script_path, 'classes', 'templates', 'intersight', f'{self.category}')
        template_name = f'{self.type}.json.j2'
        template_env  = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir), autoescape=False)

        render_item = item.toDict() if hasattr(item, 'toDict') else item
        rendered    = template_env.get_template(template_name).render(
            item           = render_item,
            isight         = kwargs.intersight_api,
            name_prefix    = np,
            name_suffix    = ns,
            object_map     = kwargs.intersight_object_map,
            organization   = kwargs.org,
            org_moids      = kwargs.org_moids,
            rsg_moids      = kwargs.rsg_moids,
            sensitive_vars = kwargs.sensitive_vars
        )
        try:
            api_body = json.loads(rendered)
        except json.JSONDecodeError as exc:
            policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
            pcolor.Red(
                f'!!! ERROR !!! Failed to parse rendered JSON for {policy_title} template '
                f'`{template_name}` (line {exc.lineno}, column {exc.colno}).'
            )
            start = max(1, exc.lineno - 2)
            end = min(len(rendered.splitlines()), exc.lineno + 2)
            for line_no in range(start, end + 1):
                marker = '>>' if line_no == exc.lineno else '  '
                pcolor.Yellow(f'{marker} {line_no:4}: {rendered.splitlines()[line_no - 1]}')
            raise
        if type(api_body) != dict:
            policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
            pcolor.Red(f'!!! ERROR !!! {policy_title} template did not render to a dictionary payload.')
            len(False); sys.exit(1)
        return api_body

    #=========================================================================
    # Function - Create Bulk API Request Body
    #=========================================================================
    def create_bulk_request(self, kwargs):
        def post_to_api(kwargs):
            kwargs = kwargs | DotMap(method = 'post', uri = 'bulk/Requests')
            kwargs = api('bulk_request', category=self.category).calls(kwargs)
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
            if e.get('Parent'):
                e.pop('Parent')
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
    # Function: Deep Merge Dictionaries
    #=========================================================================
    def deep_merge_dicts(self,dest, src):
        for key, value in src.items():
            if key in dest and isinstance(dest[key], dict) and isinstance(value, dict):
                self.deep_merge_dicts(dest[key], value)
            else:
                dest[key] = deepcopy(value)
        return dest

    #=========================================================================
    # Function - Check if Org is in Resource Name and Split
    #=========================================================================
    def determine_resource_organization(self, add_prefix_suffix=True, resource=None, kwargs=None):
        if '/' in resource: org, rname  = resource.split('/')
        else: org = kwargs.org; rname = resource
        if add_prefix_suffix == True:
            np, ns = self.name_prefix_suffix(org, kwargs)
            rname = np + rname + ns
        return org, rname

    #=========================================================================
    # Function - Check if Sub Policies exist in the Intersight API
    #=========================================================================
    def existing_check(self, item, kwargs):
        #=====================================================================
        # Constants
        #=====================================================================
        RESOURCE_PATTERN = r'_polic(ies|y)|_pool(s)?|(vhba|vnic)_template$'
        IP_BLOCK_TYPES   = ['ipv4_blocks', 'ipv6_blocks']
        RTYPE_ADJUSTMENTS = {
            'band_ip': 'ip',
            'primary_target': 'iscsi_static_target',
            'secondary_target': 'iscsi_static_target'
        }
        #=====================================================================
        # Helper Functions
        #=====================================================================
        def extract_ptype(key_str):
            """Extract policy type from key by removing common suffixes and prefixes."""
            replacements = [
                ('_policies', ''), ('_address_pools', ''), ('_pools', ''),
                ('_policy', ''), ('_address', ''), ('initiator_', '')
            ]
            rtype = key_str
            for old, new in replacements:
                rtype = rtype.replace(old, new)
            rtype = re.sub(r'_pool$', '', rtype)
            return rtype
        
        def adjust_rtype(rtype):
            """Apply rtype adjustments based on pattern matching."""
            for pattern, adjusted_type in RTYPE_ADJUSTMENTS.items():
                if re.search(pattern, rtype):
                    return adjusted_type
            return rtype
        
        def get_resource_category(key):
            """Determine if resource is pool, template, or policy based on key."""
            if key == 'pool_name' or re.search(r'_pool[s]?$', key):
                return 'pools'
            elif 'template' in key:
                return 'templates'
            else:
                return 'policies'
        
        def update_item_with_adjusted_name(item, key, old_name, new_name, is_ip_type=False):
            """Update item dictionary with adjusted resource name. Mutates item in place."""
            CHILD_CONTAINER_KEYS = [
                'vhbas', 'vhbas_from_template', 'vnics', 'vnics_from_template',
                'port_channel_appliances', 'port_channel_ethernet_uplinks', 'port_channel_fcoe_uplinks',
                'port_role_appliances', 'port_role_ethernet_uplinks', 'port_role_fcoe_uplinks',
            ]
            if is_ip_type:
                for ip_block_type in IP_BLOCK_TYPES:
                    if ip_block_type in item and isinstance(item[ip_block_type], list):
                        for x in range(len(item[ip_block_type])):
                            if item[ip_block_type][x].get(key) == old_name:
                                item[ip_block_type][x][key] = new_name
            elif self.type == 'server' and key == 'pool_name':
                for reservation in item.get('reservations') or []:
                    if isinstance(reservation, dict) and reservation.get('pool_name') == old_name:
                        reservation['pool_name'] = new_name
            elif key in item:
                if isinstance(item[key], list):
                    indx = next((i for i, d in enumerate(item[key]) if d == old_name), None)
                    if indx is not None:
                        item[key][indx] = new_name
                else:
                    item[key] = new_name
            else:
                for container_key in CHILD_CONTAINER_KEYS:
                    if container_key in item and isinstance(item[container_key], list):
                        for child in item[container_key]:
                            if key in child:
                                if isinstance(child[key], list):
                                    indx = next((i for i, d in enumerate(child[key]) if d == old_name), None)
                                    if indx is not None:
                                        child[key][indx] = new_name
                                elif child[key] == old_name:
                                    child[key] = new_name
        
        def resource_list(k, rname, rtype, item, kwargs):
            """Validate resource existence and register missing resources. Mutates item and kwargs."""
            r = get_resource_category(k)
            org, new_rname = configure(rtype, category=r).determine_resource_organization(add_prefix_suffix=True, resource=rname, kwargs=kwargs)
            current_name = rname if '/' in rname else f'{org}/{rname}'
            target_name = f'{org}/{new_rname}'
            if current_name != target_name:
                pcolor.Yellow(f'     * Adjusted {rtype} name from `{rname}` to `{target_name}` based on org `{org}` in resource `{k}`.')
                update_item_with_adjusted_name(item, k, rname, target_name, is_ip_type=self.type == 'ip')
            ckeys = list(kwargs.cp)
            if rtype not in ckeys:
                kwargs.cp[rtype].names = []
                kwargs.cp[rtype].category = r
            rkeys = list(kwargs.intersight_api[org][r][rtype].keys())
            if 'template' in k:
                kwargs.cp[rtype].names.append(target_name)
            elif new_rname not in rkeys:
                kwargs.cp[rtype].names.append(target_name)
            return item, kwargs
        
        #=====================================================================
        # Handle template reference for chassis/domain/server/unified_edge profiles
        #=====================================================================
        if re.search(r'^(chassis|domain|server|unified_edge)', self.type):
            template_key = next((k for k in item if template_regex.match(k)), None)
            if template_key and item.get(template_key):
                m = re.search(r'ucs_(server|chassis)', template_key)
                if m:
                    rtype = f'{m.group(1)}'
                    item, kwargs = resource_list(template_key, item[template_key], rtype, item, kwargs)
        #=====================================================================
        # Process IP Type Specifically
        #=====================================================================
        if self.type == 'ip':
            for e in IP_BLOCK_TYPES:
                if e in item and isinstance(item[e], list):
                    for x in range(len(item[e])):
                        if 'id_mapping_policy' in item[e][x]:
                            item, kwargs = resource_list('id_mapping_policy', item[e][x]['id_mapping_policy'], 'id_mapping', item, kwargs)
        elif self.type == 'id_mapping':
            if 'organizations' in item:
                okeys = list(kwargs.intersight_api[kwargs.org]['system']['organizations'].keys())
                names = [e for e in item.organizations if e in okeys]
                if len(names) > 0:
                    kwargs.orgs = list(numpy.unique(numpy.array(kwargs.orgs + names)))
                    kwargs = api(category= 'system', type='organizations').organizations(kwargs)
            if 'resource_groups' in item:
                rkeys = list(kwargs.rsg_moids.keys())
                names = [e for e in item.resource_groups if e in rkeys]
                if len(names) > 0:
                    kwargs.resource_groups = list(numpy.unique(numpy.array(kwargs.resource_groups + names)))
                    kwargs = api(category= 'system', type='resource_groups').organizations(kwargs)
        #=====================================================================
        # Process LAN Connectivity Type - Extract Sub-Resources from vNICs
        #=====================================================================
        elif self.type == 'lan_connectivity':
            vnic_sub_map = {
                'ethernet_adapter_policy': 'ethernet_adapter_policy',
                'ethernet_adapter_policies': 'ethernet_adapter_policy',
                'ethernet_network_policy': 'ethernet_network_policy',
                'ethernet_network_policies': 'ethernet_network_policy',
                'ethernet_network_control_policy': 'ethernet_network_control_policy',
                'ethernet_network_control_policies': 'ethernet_network_control_policy',
                'ethernet_network_group_policies': 'ethernet_network_group_policy',
                'ethernet_qos_policy': 'ethernet_qos_policy',
                'ethernet_qos_policies': 'ethernet_qos_policy',
                'mac_address_pool': 'mac',
                'mac_address_pools': 'mac'
            }
            for vnic_container_key in ['vnics', 'vnics_from_template']:
                if vnic_container_key in item:
                    for vnic_item in item[vnic_container_key]:
                        for sub_key, rtype in vnic_sub_map.items():
                            if sub_key in vnic_item and vnic_item[sub_key]:
                                sub_value = vnic_item[sub_key]
                                config_key = extract_ptype(rtype) if sub_key != 'mac_address_pool' else rtype
                                if isinstance(sub_value, list):
                                    for sub_resource in sub_value:
                                        item, kwargs = resource_list(sub_key, sub_resource, config_key, item, kwargs)
                                else:
                                    item, kwargs = resource_list(sub_key, sub_value, config_key, item, kwargs)
                        # For vnics_from_template, also extract vnic_template reference
                        if vnic_container_key == 'vnics_from_template' and 'vnic_template' in vnic_item and vnic_item['vnic_template']:
                            item, kwargs = resource_list('vnic_template', vnic_item['vnic_template'], 'vnic_template', item, kwargs)
        #=====================================================================
        # Process Port Type Specifically - Extract Sub-Resources
        #=====================================================================
        elif self.type == 'port':
            # Map field names (as they appear in data) to resource types
            # Config key will be automatically extracted via extract_ptype
            port_sub_map = {
                'ethernet_network_group_policies': 'ethernet_network_group_policy',
                'ethernet_network_group_policy': 'ethernet_network_group_policy',
                'ethernet_network_control_policy': 'ethernet_network_control_policy',
                'flow_control_policy': 'flow_control_policy',
                'link_aggregation_policy': 'link_aggregation_policy',
                'link_control_policy': 'link_control_policy',
                'mac_sec_policy': 'mac_sec_policy'
            }
            for port_type_key in ['port_channel_appliances', 'port_channel_ethernet_uplinks',
                                  'port_channel_fcoe_uplinks', 'port_role_appliances',
                                  'port_role_ethernet_uplinks', 'port_role_fcoe_uplinks']:
                if port_type_key in item:
                    for policy_item in item[port_type_key]:
                        for sub_key, rtype in port_sub_map.items():
                            if sub_key in policy_item and policy_item[sub_key]:
                                sub_value = policy_item[sub_key]
                                # Extract config key from resource type using extract_ptype
                                config_key = extract_ptype(rtype)
                                if isinstance(sub_value, list):
                                    for sub_resource in sub_value:
                                        item, kwargs = resource_list(sub_key, sub_resource, config_key, item, kwargs)
                                else:
                                    item, kwargs = resource_list(sub_key, sub_value, config_key, item, kwargs)
        #=====================================================================
        # Process SAN Connectivity Type - Extract Sub-Resources from vHBAs
        #=====================================================================
        elif self.type == 'san_connectivity':
            # Policy-level pool reference (separate from child vHBA pools).
            if 'wwnn_pool' in item and item['wwnn_pool']:
                item, kwargs = resource_list('wwnn_pool', item['wwnn_pool'], 'wwnn', item, kwargs)
            elif 'wwnn_pools' in item and item['wwnn_pools']:
                wwnn_value = item['wwnn_pools']
                if isinstance(wwnn_value, list):
                    for pool_name in wwnn_value:
                        item, kwargs = resource_list('wwnn_pools', pool_name, 'wwnn', item, kwargs)
                else:
                    item, kwargs = resource_list('wwnn_pools', wwnn_value, 'wwnn', item, kwargs)

            vhba_sub_map = {
                'fibre_channel_adapter_policy': 'fibre_channel_adapter_policy',
                'fibre_channel_network_policy': 'fibre_channel_network_policy',
                'fibre_channel_network_policies': 'fibre_channel_network_policy',
                'fibre_channel_qos_policy': 'fibre_channel_qos_policy',
                'wwpn_pool': 'wwpn',
                'wwpn_pools': 'wwpn'
            }
            for vhba_container_key in ['vhbas', 'vhbas_from_template']:
                if vhba_container_key in item:
                    for vhba_item in item[vhba_container_key]:
                        for sub_key, rtype in vhba_sub_map.items():
                            if sub_key in vhba_item and vhba_item[sub_key]:
                                sub_value = vhba_item[sub_key]
                                config_key = extract_ptype(rtype) if sub_key not in ['wwpn_pool', 'wwpn_pools'] else rtype
                                if isinstance(sub_value, list):
                                    for sub_resource in sub_value:
                                        item, kwargs = resource_list(sub_key, sub_resource, config_key, item, kwargs)
                                else:
                                    item, kwargs = resource_list(sub_key, sub_value, config_key, item, kwargs)
                        # For vhbas_from_template, also extract vhba_template reference
                        if vhba_container_key == 'vhbas_from_template' and 'vhba_template' in vhba_item and vhba_item['vhba_template']:
                            item, kwargs = resource_list('vhba_template', vhba_item['vhba_template'], 'vhba_template', item, kwargs)
        #=====================================================================
        # Process Server Type Specifically - Extract Reservation Pools from Targets
        #=====================================================================
        elif self.type == 'server':
            reservation_identity_types = {'ip', 'iqn', 'mac', 'uuid', 'wwpn', 'wwnn'}
            for reservation in item.get('reservations') or []:
                if not isinstance(reservation, dict):
                    continue
                pool_name     = reservation.get('pool_name')
                identity_type = reservation.get('identity_type')
                if pool_name and identity_type:
                    pool_type = str(identity_type).lower()
                    if pool_type in reservation_identity_types:
                        item, kwargs = resource_list('pool_name', pool_name, pool_type, item, kwargs)
        #=====================================================================
        # Process All Other Types
        #=====================================================================
        else:
            for k, v in item.items():
                if re.search(RESOURCE_PATTERN, k):
                    rtype = extract_ptype(k)
                    rtype = adjust_rtype(rtype)
                    if isinstance(v, list):
                        for e in v:
                            item, kwargs = resource_list(k, e, rtype, item, kwargs)
                    else:
                        item, kwargs = resource_list(k, v, rtype, item, kwargs)
                elif re.search('vmq|usnic', k):
                    vkeys = list(v.keys())
                    if 'vmmq_adapter_policy' in vkeys and len(v.get('vmmq_adapter_policy', '')) > 0:
                        item, kwargs = resource_list('ethernet_adapter_policy', v['vmmq_adapter_policy'], 'ethernet_adapter', item, kwargs)
                    elif 'usnic_adapter_policy' in vkeys and len(v.get('usnic_adapter_policy', '')) > 0:
                        item, kwargs = resource_list('ethernet_adapter_policy', v['usnic_adapter_policy'], 'ethernet_adapter', item, kwargs)
        return item, kwargs

    #=========================================================================
    # Function: Define Configure Functions to Run
    #=========================================================================
    def functions_to_run(self, kwargs):
        kwargs.orgs = list(kwargs.imm_dict.orgs.keys())
        #=====================================================================
        # Create YAML Files
        #=====================================================================
        orgs = kwargs.orgs
        #ezfunctions.create_yaml(orgs, kwargs)
        #=====================================================================
        # Build Lists from ezdata
        #=====================================================================
        kwargs.policies_list = []
        kwargs.pools_list    = []
        kwargs.profiles_list = []
        kwargs.templates_list = []
        kwargs.system_list   = []
        for k, v in kwargs.ezdata.items():
            regex = re.compile(r'intersight\.(policies|pools|profiles|system|templates)\.', re.IGNORECASE)
            if regex.search(k):
                rtype = regex.search(k).group(1)
                r     = regex.sub('', k)
                if not '.' in r and v.get('object_type'): kwargs[f'{rtype}_list'].append(r)
        if 'switch' in kwargs.profiles_list: kwargs.profiles_list.remove('switch')
        if 'switch' in kwargs.templates_list: kwargs.templates_list.remove('switch')
        iboot_index = kwargs.policies_list.index('iscsi_boot') if 'iscsi_boot' in kwargs.policies_list else len(kwargs.policies_list)
        ip_index    = kwargs.pools_list.index('ip') if 'ip' in kwargs.pools_list else len(kwargs.pools_list)
        ptemplates  = ['id_mapping', 'server_pool_qualification']
        vtemplates  = ['vnic_template', 'vhba_template']
        for e in ['iscsi_static_target'] + vtemplates:
            if   e in kwargs.templates_list:
                kwargs.templates_list.remove(e)
                kwargs.policies_list.insert(iboot_index, e)
            elif e in kwargs.policies_list:
                kwargs.policies_list.remove(e)
                kwargs.policies_list.insert(iboot_index, e)
                iboot_index += 1
        if 'resource_groups' in kwargs.system_list:
            kwargs.system_list.remove('resource_groups')
            kwargs.system_list.insert(0, 'resource_groups')
        for e in ptemplates:
            if e in kwargs.policies_list:
                kwargs.policies_list.remove(e)
                kwargs.pools_list.insert(ip_index, e)
                ip_index += 1
        #=====================================================================
        # Pools/Policies/Profiles/Templates
        #=====================================================================
        kkeys = list(kwargs.imm_dict)
        if 'system' in kkeys:
            for ptype in kwargs.system_list:
                kwargs.org = 'default'
                if ptype in list(kwargs.imm_dict.get('system', {}).keys()):
                    kwargs = getattr(system(type=f'{ptype}', category='system'), 'system')(kwargs)
        # for e in ['pools', 'policies', 'templates']:
        for e in ['pools', 'policies', 'templates', 'profiles']:
            for ptype in kwargs[f'{e}_list']:
                for org in orgs:
                    kwargs.org = org
                    category = 'policies' if ptype in ptemplates else 'templates' if ptype in vtemplates else e
                    if ptype in list(kwargs.imm_dict.orgs[org].get(category, {}).keys()):
                        kwargs = configure(type=f'{ptype}', category=category).configure(kwargs)
        #=====================================================================
        # return kwargs
        #=====================================================================
        return kwargs

    #=========================================================================
    # Function - Merge Tags from Global Settings, Item, and Script
    #=========================================================================
    def merge_tags(self, item, kwargs):
        def as_tag_list(value):
            if value is None:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, DotMap):
                return [value]
            if isinstance(value, dict):
                return [value]
            return []

        gs = kwargs.intersight.get('global_settings') if kwargs.get('intersight') else None
        global_tags = as_tag_list(gs.get('tags')) if gs else []
        if isinstance(item, dict):
            item_tags = as_tag_list(item.get('tags'))
        else:
            item_tags = as_tag_list(item.get('tags')) if hasattr(item, 'get') else as_tag_list(getattr(item, 'tags', None))

        include_script_tags = True
        if gs and gs.get('include_script_tags') is False:
            include_script_tags = False
        script_tags = as_tag_list(kwargs.ez_tags) if include_script_tags and kwargs.get('ez_tags') else []

        merged_tags = []
        seen_tags = set()
        for tag in global_tags + item_tags + script_tags:
            try:
                tag_obj = tag.toDict() if hasattr(tag, 'toDict') else deepcopy(tag)
            except Exception:
                tag_obj = deepcopy(tag)
            if isinstance(tag_obj, DotMap):
                tag_obj = tag_obj.toDict()
            if not isinstance(tag_obj, dict):
                continue
            tag_key = json.dumps(tag_obj, sort_keys=True, default=str)
            if tag_key in seen_tags:
                continue
            seen_tags.add(tag_key)
            merged_tags.append(tag_obj)

        if isinstance(item, dict):
            item['tags'] = merged_tags
        else:
            item.tags = merged_tags

        # Keep a predictable shape for template rendering when no tags are defined.
        if isinstance(item, dict) and item.get('tags') is None:
            item['tags'] = []
        elif not isinstance(item, dict) and getattr(item, 'tags', None) is None:
            item.tags = []
        return item

    #=========================================================================
    # Function - Add Prefix / Suffix to Resource Name
    #=========================================================================
    def name_prefix_suffix(self, org, kwargs):
        args  = DotMap(name_prefix = '', name_suffix = '')
        ckeys = list(kwargs.imm_dict.orgs[org][self.category].keys())
        for e in ['name_prefix', 'name_suffix']:
            if e in ckeys:
                nkeys = list(kwargs.imm_dict.orgs[org][self.category][e].keys())
                if self.type in nkeys:
                    if len(kwargs.imm_dict.orgs[org][self.category][e][self.type]) > 0:
                        args[e] = kwargs.imm_dict.orgs[org][self.category][e][self.type]
                if args[e] == '':
                    if 'default' in nkeys:
                        if len(kwargs.imm_dict.orgs[org][self.category][e]['default']) > 0:
                            args[e] = kwargs.imm_dict.orgs[org][self.category][e]['default']
        return args.name_prefix, args.name_suffix

    #=========================================================================
    # Function - BIOS Policy Updates
    #=========================================================================
    def policies_bios(self, item, kwargs):
        ikeys = item.keys()
        if 'bios_template' in ikeys:
            template_name = item.bios_template
            templates     = kwargs.ezdata[f'intersight.{self.category}.{self.type}'].allOf[1].properties.bios_template.enum
            btemplates    = kwargs.ezdata[f'intersight.{self.category}.{self.type}.templates'].properties
            if template_name not in templates:
                pcolor.Red(f'!!! ERROR !!! Bios Template "{template_name}" was not found in "intersight.{self.category}.{self.type}.templates".')
                pcolor.Red(f'Available templates are: {", ".join(sorted(list(templates.keys())))}')
                sys.exit(1)
            btemplate  = btemplates[re.sub(r'-tpm$', '', item.bios_template, flags=re.IGNORECASE)]
            if '-tpm' in (item.bios_template).lower():
                item = btemplate | btemplates.tpm | item
            else: item = btemplate | item
        return item

    #=========================================================================
    # Function - Certificate Policy Updates
    #=========================================================================
    def policies_certificate_management(self, item, kwargs):
        ikeys = item.keys()
        if 'certificates' in ikeys:
            for x in range(0, len(item.certificates)):
                xkeys = list(item.certificates[x].keys())
                if 'certificate_file' in xkeys:
                    cert_content = self.cert_file_check(expected_type='certificate', file_path=item.certificates[x]['certificate_file'], item=item)
                    item.certificates[x]['certificate_file'] = cert_content
                if 'private_key_file' in xkeys and item.certificates[x].get('private_key_file'):
                    key_content = self.cert_file_check(expected_type='private_key', file_path=item.certificates[x]['private_key_file'], item=item)
                    item.certificates[x]['private_key_file'] = key_content
        return item

    #=========================================================================
    # Function - Drive Security Policy Updates
    #=========================================================================
    def policies_drive_security(self, item, kwargs):
        ikeys = item.keys()
        if 'remote_key_management' in ikeys:
            rkeys = list(item.remote_key_management.keys())
            if 'server_public_root_ca_certificate' in rkeys and len(item.remote_key_management.get('server_public_root_ca_certificate', '')) > 0:
                cert_content = self.cert_file_check(expected_type='certificate', file_path=item.remote_key_management['server_public_root_ca_certificate'], item=item)
                item.remote_key_management['server_public_root_ca_certificate'] = cert_content
        return item

    #=========================================================================
    # Function - Ethernet Adapter Policy Updates
    #=========================================================================
    def policies_ethernet_adapter(self, item, kwargs):
        item = self.policies_ethernet_fc_adapter(item, kwargs)
        return item

    #=========================================================================
    # Function - Ethernet / FC Adapter Policy Updates
    #=========================================================================
    def policies_ethernet_fc_adapter(self, item, kwargs):
        ikeys  = list(item.keys())
        ptitle = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        if 'adapter_template' in ikeys:
            templates = kwargs.ezdata[f'intersight.{self.category}.{self.type}.templates'].properties
            template_name = item.adapter_template
            if template_name not in templates:
                pcolor.Red(f'!!! ERROR !!! {ptitle} Template "{template_name}" was not found in "intersight.{self.category}.{self.type}.templates".')
                pcolor.Red(f'Available templates are: {", ".join(sorted(list(templates.keys())))}')
                sys.exit(1)
            merged = deepcopy(templates[template_name].toDict())
            merged = self.deep_merge_dicts(merged, item.toDict())
            item = DotMap(merged)
        return item

    #=========================================================================
    # Function - Fibre-Channel Adapter Policy Updates
    #=========================================================================
    def policies_fibre_channel_adapter(self, item, kwargs):
        item = self.policies_ethernet_fc_adapter(item, kwargs)
        return item

    #=========================================================================
    # Function - Validate CCO Authorization
    #=========================================================================
    def policies_firmware_authenticate(self, kwargs):
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
    # Function - Configure -> Policies -> System QoS Policy Updates
    #=========================================================================
    def policies_system_qos(self, item, kwargs):
        if not type(item.target_platform) == str: item.target_platform = "UCS Domain"
        if not type(item.classes) == list: item.classes = []
        if not type(item.jumbo_mtu) == bool: item.jumbo_mtu = False
        target = item.target_platform.lower().replace(" ", "_")
        if item.configure_recommended_classes == True:
            item.classes = kwargs.ezdata[f'intersight.{self.category}.system_qos.templates'].properties[f'recommended_classes_{target}'].classes
        elif item.configure_default_classes == True:
            item.classes = kwargs.ezdata[f'intersight.{self.category}.system_qos.templates'].properties[f'default_classes_{target}'].classes
        elif len(item.classes) == 0:
            item.classes = kwargs.ezdata[f'intersight.{self.category}.system_qos.templates'].properties[f'default_classes_{target}'].classes
        # weight_total = 0
        for x in range(0, len(item.classes)):
            if item.classes[x].priority == 'FC': item.classes[x].mtu = 2240
            elif item.jumbo_mtu == True: item.classes[x].mtu = 9216
            else: item.classes[x].mtu = 1500
            # if type(item.classes[x].weight) == int: weight_total += item.classes[x].weight
            # else: item.classes[x].weight = 1; weight_total += 1
        # for x in range(0, len(item.classes)):
        #     item.classes[x].bandwidth_percent = int((item.classes[x].weight / weight_total) * 100)
        # item.classes = sorted(item.classes, key=lambda ele: ele['priority'])
        return item

    #=========================================================================
    # Function - Assign LDAP Groups to LDAP Policies
    #=========================================================================
    def policies_ldap_ldap_groups(self, kwargs):
        names = []
        for item in kwargs.resources:
            ikeys = list(item.keys())
            if 'ldap_groups' in ikeys and len(item.ldap_groups) > 0:
                names.extend([e.get('end_point_role') for e in item.ldap_groups if e.get('end_point_role')])
        if len(names) > 0:
            kwargs = kwargs | DotMap(method = 'get', names = list(numpy.unique(numpy.array(names))), uri = 'iam/EndPointRoles')
            kwargs = api(category='system', type='iam_end_point_role').calls(kwargs)
        kwargs = self.children_resources('ldap_groups', kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign LDAP Servers to LDAP Policies
    #=========================================================================
    def policies_ldap_ldap_servers(self, kwargs):
        kwargs = self.children_resources('ldap_servers', kwargs)
        return kwargs

    #=========================================================================
    # Function - Port Policies - Sub Policies
    #=========================================================================
    def policies_port_children(self, kwargs):
        #=====================================================================
        # Get Existing Port Types Assigned to Port Policies
        #=====================================================================
        org = kwargs.org
        np, ns = self.name_prefix_suffix(org, kwargs)
        port_types = [k.split('.')[-1] for k,v in kwargs.ezdata.items() if re.search(r'^intersight\.policies\.port\.port_[a-z_]+$', k)]
        port_types = [e for e in port_types if e != 'port_modes']
        port_types.insert(0, 'port_modes')
        port = DotMap()
        for e in port_types: port[e] = DotMap(names = [])
        #=====================================================================
        # Check for Parent Port Policies and Get Existing Port Type
        # Assignments for Each Parent Policy.  Skip if No Parent Policies
        # Exist or if Running in Check Mode.
        #=====================================================================
        continue_count = 0
        ikeys = list(kwargs.intersight_api[org].policies.port.keys())
        for item in kwargs.resources:
            policy_list = [f"{np}{e}{ns}" for e in item.names if f"{np}{e}{ns}" in ikeys]
            continue_count += len(policy_list)
            if kwargs.args.check == True and len(policy_list) != len(item.names):
                pcolor.Cyan(f"\n     * Running in Check Mode")
            if len(policy_list) != len(item.names):
                pcolor.Yellow(f"\n     * Skipping Port Policy Children Retrieval for Org: {org} > Port Policies:")
                pcolor.Yellow(f"       {', '.join([f'`{np}{d}{ns}`' for d in item.names])} because no parent Port Policy exists in Intersight.")
        if continue_count == 0: return kwargs
        #=====================================================================
        # Get Parent Port Policies
        #=====================================================================
        for e in port_types:
            for item in kwargs.resources:
                ikeys = list(item.keys())
                if e in ikeys and len(item[e]) > 0:
                    try:
                        port[e].names.extend([kwargs.intersight_api[org]['policies']['port'][f"{np}{d}{ns}"].moid for d in item.names])
                    except KeyError as ex:
                        pcolor.Red(f"Warning: Missing port policy key for {e}: {ex}")
        for e in port_types:
            if len(port[e].names) > 0:
                port[e].names = list(numpy.unique(numpy.array(port[e].names)))
                kwargs = configure(f'{self.type}.{e}', category=self.category).api_get(True, port[e].names, f'port.{e}', kwargs)
        #=====================================================================
        # Generate Port Types Content
        #=====================================================================
        def pitem_generation(x, item, policy, kwargs):
            ikeys  = list(item.keys())
            try:
                parent = kwargs.intersight_api[kwargs.org]['policies']['port'][f"{np}{item['names'][x]}{ns}"].moid
            except KeyError as ex:
                pcolor.Red(f"Warning: Missing parent port policy: {ex}")
                return None
            pitem  = DotMap({'parent': parent} | policy.toDict())
            if 'tags' in ikeys: pitem.tags = item.tags
            return pitem
        #=====================================================================
        # Unified Port Handler with Dispatch
        #=====================================================================
        def process_port_attributes(pitem, policy, port_type, x):
            """Apply port-type-specific attribute processing."""
            if pitem is None:
                return
            pkeys = list(policy.keys())
            if port_type == 'channel':
                plist = ['ethernet_network_group_policies', 'pc_ids', 'user_labels', 'vsan_ids']
                for p in plist:
                    new_label = p[:-1] if p in ['pc_ids', 'user_labels', 'vsan_ids'] else p
                    if 'ethernet_network_group_policies' == p:
                        half = len(policy[p]) // 2
                        if len(policy[p]) > 1:
                            eng_value = policy[p][:half] if x == 0 else policy[p][half:]
                        else:
                            eng_value = policy[p]
                        pitem['ethernet_network_group_policies'] = eng_value
                        if isinstance(eng_value, list) and len(eng_value) > 0:
                            pitem['ethernet_network_group_policy'] = eng_value[0]
                        else:
                            pitem['ethernet_network_group_policy'] = eng_value
                    else:
                        pitem[new_label] = policy[p][x] if p in pkeys and len(policy[p]) > 1 else policy[p][0] if p in pkeys else None
            elif port_type == 'role':
                plist = ['ethernet_network_group_policies', 'user_labels', 'vsan_ids']
                port_list = ezfunctions.vlan_list_full(pitem.port_list)
                ports_length = len(port_list)
                for num in range(ports_length):
                    pitem.port_id = port_list[num]
                    for p in plist:
                        new_label = p[:-1] if p in ['user_labels', 'vsan_ids'] else p
                        if p in pkeys:
                            double = ports_length * 2
                            half = len(policy[p]) // 2
                            if len(policy[p]) == double and x == 0:
                                value = policy[p][:half][num]
                            elif len(policy[p]) == double and x == 1:
                                value = policy[p][half:][num]
                            elif len(policy[p]) == ports_length:
                                value = policy[p][num]
                            else:
                                value = policy[p][0]

                            # Keep ethernet network group references list-shaped
                            # for templates that consume index 0.
                            if p == 'ethernet_network_group_policies':
                                eng_value = value if isinstance(value, list) else [value]
                                pitem['ethernet_network_group_policies'] = eng_value
                                pitem['ethernet_network_group_policy'] = eng_value[0] if len(eng_value) > 0 else ''
                            else:
                                pitem[new_label] = value
        
        def create_and_commit_api(pitem, e, kwargs):
            """Create API body and compare against existing state."""
            if pitem is None:
                return kwargs
            api_body = configure(f'port.{e}', category=self.category).create_api_body(pitem, np, ns, kwargs)
            kwargs   = configure(f'port.{e}', category=self.category).children_compare_api_body(api_body, kwargs)
            return kwargs
        
        # Map port type patterns to handler types
        port_type_handlers = {
            'port_channel': 'channel',
            'port_mode': 'mode',
            'port_role': 'role'
        }
        #=====================================================================
        # Loop through Port Types and Generate API Bodies for Each Port
        # Policy, then POST via API if Bulk List > 0
        #=====================================================================
        for e in port_types:
            kwargs.bulk_list = []
            for item in kwargs.resources:
                ikeys = list(item.keys())
                if e in ikeys and len(item[e]) > 0:
                    for x in range(0, len(item['names'])):
                        for policy in item[e]:
                            pitem = pitem_generation(x, item, policy, kwargs)
                            # Determine handler type from port type name
                            handler_type = next((v for k, v in port_type_handlers.items() if k in e), None)
                            if handler_type == 'channel' or handler_type == 'role':
                                process_port_attributes(pitem, policy, handler_type, x)
                            kwargs = create_and_commit_api(pitem, e, kwargs)
            if len(kwargs.bulk_list) > 0:
                kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.port.{e}"].intersight_uri
                kwargs     = configure(f'port.{e}', category=self.category).create_bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign vNICs to LAN Connectivity Policies
    #=========================================================================
    def policies_lan_connectivity_vnics(self, kwargs):
        kwargs = self.policies_vnics_compile('vnics', kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign vNICs to LAN Connectivity Policies from Template
    #=========================================================================
    def policies_lan_connectivity_vnics_from_template(self, kwargs):
        kwargs = self.policies_vnics_compile('vnics_from_template', kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign Users to Local User Policies
    #=========================================================================
    def policies_local_user_users(self, kwargs):
        names = []
        for item in kwargs.resources:
            ikeys = list(item.keys())
            if 'users' in ikeys and len(item.users) > 0:
                names.extend([e.get('role') for e in item.users if e.get('role')])
        if len(names) > 0:
            kwargs = kwargs | DotMap(method = 'get', names = list(numpy.unique(numpy.array(names))), uri = 'iam/EndPointRoles')
            kwargs = api(category='system', type='iam_end_point_role').calls(kwargs)
        kwargs = self.children_resources('users', kwargs)
        kwargs = self.children_resources('users_roles', kwargs)
        return kwargs

    #=========================================================================
    # Function - SNMP Policy Port Validation
    #=========================================================================
    def policies_snmp(self, kwargs):
        reserved_ports = [22, 23, 80, 123, 389, 443, 623, 636, 2068, 3268, 3269]
        policy_name = ''
        for item in kwargs.resources:
            policy_name = f"{item.name}" if hasattr(item, 'name') else ''
            ikeys = list(item.keys())
            if 'snmp_trap_destinations' in ikeys and len(item.snmp_trap_destinations) > 0:
                for trap in item.snmp_trap_destinations:
                    if trap.get('port'):
                        trap_port = int(trap['port'])
                        if trap_port in reserved_ports:
                            pcolor.Red(
                                f"!!! ERROR !!! SNMP Policy `{policy_name}`: Trap destination port {trap_port} is a reserved port. "
                                f"Reserved ports not allowed: {', '.join(map(str, reserved_ports))}"
                            )
                            sys.exit(1)
        return kwargs

    #=========================================================================
    # Function - Assign vHBAs to SAN Connectivity Policies
    #=========================================================================
    def policies_san_connectivity_vhbas(self, kwargs):
        kwargs = self.policies_vnics_compile('vhbas', kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign vHBAs to SAN Connectivity Policies from Template
    #=========================================================================
    def policies_san_connectivity_vhbas_from_template(self, kwargs):
        kwargs = self.policies_vnics_compile('vhbas_from_template', kwargs)
        return kwargs

    #=========================================================================
    # Function - Storage Policy Updates
    #=========================================================================
    def policies_storage(self, item, kwargs):
        ikeys  = list(item.keys())
        ptitle = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        if 'storage_template' in ikeys:
            templates = kwargs.ezdata[f'intersight.{self.category}.{self.type}.templates'].properties
            template_name = item.storage_template
            if template_name not in templates:
                pcolor.Red(f'!!! ERROR !!! {ptitle} Template "{template_name}" was not found in "intersight.{self.category}.{self.type}.templates".')
                pcolor.Red(f'Available templates are: {", ".join(sorted(list(templates.keys())))}')
                sys.exit(1)
            merged = deepcopy(templates[template_name].toDict())
            merged = self.deep_merge_dicts(merged, item.toDict())
            item = DotMap(merged)
        return item

    #=========================================================================
    # Function - Assign Drive Groups to Storage Policies
    #=========================================================================
    def policies_storage_drive_groups(self, kwargs):
        kwargs = self.children_resources('drive_groups', kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign VLANs to VLAN Policies
    #=========================================================================
    def policies_vlan_vlans(self, kwargs):
        child_type = 'vlans'
        continue_count, kwargs = self.children_check_parent(child_type, kwargs)
        if continue_count == 0: return kwargs
        #=====================================================================
        # Create API Body for Sub Items and Compare to Existing API Results.
        # If Differences or No Existing Resource, Append to Bulk List for
        # POST/PATCH.  If No Differences, Skip.
        #=====================================================================
        org = kwargs.org
        np, ns = self.name_prefix_suffix(org, kwargs)
        kwargs.bulk_list = []
        for e in kwargs.resources:
            ekeys = list(e.keys())
            if child_type in ekeys:
                for item in e[child_type]:
                    ikeys = list(item.keys())
                    item.parent = kwargs.intersight_api[org][self.category][self.type][np + e.name + ns].moid
                    if not 'name_prefix' in ikeys: name_prefix = True
                    else: name_prefix = item.name_prefix
                    vlans = ezfunctions.vlan_list_full(item.vlan_list)
                    original_name = item.name
                    reserved_list = ezfunctions.vlan_list_full('4043-4047, 4094, 4095')
                    for x in vlans:
                        if type(x) == str: x = int(x)
                        if x in reserved_list:
                            pcolor.Yellow(f'!!! WARNING !!! VLAN ID {x} is a reserved VLAN and cannot be used.'\
                                          f'  Skipping assignment of VLAN ID {x} under VLAN Policy `{np + e.name + ns}` in Org `{kwargs.org}`.')
                            continue
                        if len(vlans) > 1 and name_prefix == True:
                            item.name = deepcopy(f"{original_name}{x}")
                            # item.name = deepcopy(f"{original_name}{'0'*(4 - len(str(x)))}{x}")
                        else: item.name = deepcopy(f"{original_name}")
                        item.vlan_id = x
                        item.target_platform = e.get('target_platform', 'UCS Domain')
                        api_body = configure(f'{self.type}.{child_type}', category=self.category).create_api_body(item, np, ns, kwargs)
                        kwargs   = configure(f'{self.type}.{child_type}', category=self.category).children_compare_api_body(api_body, kwargs)
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.{self.type}.{child_type}.domain"].intersight_uri
            kwargs     = configure(f'{self.type}.{child_type}', category=self.category).create_bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign VNICs to LAN Connectivity Policies
    #=========================================================================
    def policies_vnics_compile(self, child_type, kwargs):
        continue_count, kwargs = self.children_check_parent(child_type, kwargs)
        if continue_count == 0: return kwargs
        np, ns = self.name_prefix_suffix(kwargs.org, kwargs)
        #=====================================================================
        # Create API Body for Sub Items and Compare to Existing API Results.
        # If Differences or No Existing Resource, Append to Bulk List for
        # POST/PATCH.  If No Differences, Skip.
        #=====================================================================
        # Normalize legacy scalar/list forms so compile logic can treat inputs consistently.
        def normalize_child_item(item, x):
            placement_key_map = {
                'pci_links': 'pci_link',
                'pci_order': 'pci_order',
                'slot_ids': 'slot_id',
                'switch_ids': 'switch_id',
                'uplink_ports': 'uplink_port'
            }
            rename_key_map = {
                'ethernet_adapter_policies': 'ethernet_adapter_policy',
                'ethernet_network_policies': 'ethernet_network_policy',
                'ethernet_network_control_policies': 'ethernet_network_control_policy',
                'ethernet_network_group_policies': 'ethernet_network_group_policies',
                'ethernet_qos_policies': 'ethernet_qos_policy',
                'fibre_channel_network_policies': 'fibre_channel_network_policy',
                'fc_zone_policies': 'fc_zone_policies',
                'flow_monitor_policies': 'flow_monitor_policies',
                'iscsi_boot_policies': 'iscsi_boot_policy',
                'mac_address_pools': 'mac_address_pool',
                'wwpn_pools': 'wwpn_pool',
                'mac_addresses_static': 'mac_address_static'
            }
            list_policy_keys = {
                'ethernet_network_group_policies',
                'fc_zone_policies',
                'flow_monitor_policies',
            }
            if not 'template' in child_type:
                if item.get('placement') and isinstance(item.placement, dict):
                    for plural_key, singular_key  in placement_key_map.items():
                        if plural_key in item.placement and type(item.placement[plural_key]) == list and len(item.placement[plural_key]) > 0:
                            if len(item.placement[plural_key]) == len(item.names):
                                item.placement[singular_key] = item.placement[plural_key][x]
                            else: item.placement[singular_key] = item.placement[plural_key][0]
                    if item.placement.get('switch_id', None) in [None, '']:
                        item.placement['switch_id'] = 'A' if x == 0 else 'B'
                for original, new in rename_key_map.items():
                    if original in item and type(item[original]) == list and len(item[original]) > 0:
                        src_len   = len(item[original])
                        names_len = len(item.names)
                        if src_len > names_len:
                            if original in list_policy_keys:
                                if names_len > 0 and src_len % names_len == 0:
                                    chunk = int(src_len / names_len)
                                    start = x * chunk
                                    item[new] = item[original][start:start + chunk]
                                elif names_len == 2:
                                    half = int(src_len / 2)
                                    if x == 1: item[new] = item[original][half:]
                                    else: item[new] = item[original][:half]
                                else:
                                    item[new] = item[original]
                            else:
                                if x < src_len: item[new] = item[original][x]
                                else: item[new] = item[original][0]
                        elif src_len == names_len:
                            if original in list_policy_keys: item[new] = [item[original][x]]
                            else: item[new] = item[original][x]
                        else:
                            if original in list_policy_keys: item[new] = item[original]
                            else: item[new] = item[original][0]
            return item
        #=================================================================
        # Function - vNIC Loop - Build API Body
        #=================================================================
        def vnic_loop(item, x, kwargs):
            if 'template' in child_type:
                cdict = child_type.replace('s_template', '_template')
                torg, tname = self.determine_resource_organization(add_prefix_suffix=True, resource=item[cdict], kwargs=kwargs)
                item.allow_override = kwargs.intersight_api[torg].policies[cdict][tname].result['AllowOverride']
            else: item.name = item.names[x]
            item     = normalize_child_item(item, x)
            np = ''; ns = ''
            api_body = configure(f'{self.type}.{child_type}', category=self.category).create_api_body(item, np, ns, kwargs)
            kwargs   = configure(f'{self.type}.{child_type}', category=self.category).children_compare_api_body(api_body, kwargs)
            return kwargs
        #=====================================================================
        # Create API Body for vHBAs/vNICs
        #=====================================================================
        kwargs.bulk_list = []
        for item in kwargs.resources:
            ikeys = list(item.keys())
            if child_type in ikeys:
                #=================================================================
                # Loop Through vHBA/vNICs
                #=================================================================
                for i in item[child_type]:
                    i.parent = kwargs.intersight_api[kwargs.org][self.category][self.type][np + item.name + ns].moid
                    i.target_platform = item.get('target_platform', 'FIAttached')
                    if 'template' in child_type: kwargs = vnic_loop(i, 99, kwargs)
                    else:
                        original_items = deepcopy(i)
                        for x in range(len(i.names)):
                            kwargs = vnic_loop(deepcopy(original_items), x, kwargs)
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.{self.type}.{child_type}"].intersight_uri
            if isinstance(kwargs.uri, DotMap):
                kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.{self.type}.{child_type}.domain"].intersight_uri
            kwargs     = configure(f'{self.type}.{child_type}', category=self.category).create_bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Assign VSANs to VSAN Policies
    #=========================================================================
    def policies_vsan_vsans(self, kwargs):
        kwargs = self.children_resources('vsans', kwargs)
        return kwargs

    #=========================================================================
    # Function - Merge Template with Chassis/Domain/Server Profile
    #=========================================================================
    def profiles_bulk_merge_template(self, kwargs):
        original_org = kwargs.org
        kwargs.bulk_templates = DotMap()
        skeys = kwargs.intersight_api[original_org].profiles[self.type.replace('.switch', '')]
        np, ns = self.name_prefix_suffix(original_org, kwargs)
        for e in kwargs.resources:
            name = f'{np}{e.name}{ns}'
            template = next((k for k in e.keys() if template_regex.match(k)), None)
            template_value = e.get(template)
            if not template or not template_value:
                pcolor.Yellow(f'  * Skipping Org: {kwargs.org}; Profile `{name}` has no valid template reference key.')
                continue
            org, tname = self.determine_resource_organization(add_prefix_suffix=False, resource=template_value, kwargs=kwargs)
            kwargs.bulk_templates.setdefault(org, DotMap())
            if 'switch' in self.type:
                for switch_id in ['A', 'B']:
                    src_template_merged = all([
                        name in skeys and skeys[name],
                        (skeys[name].get('result', {}).get('SrcTemplate') or {}).get('Moid') if skeys.get(name) else False,
                        skeys[name].get('switch', {}).get(f'{name}-{switch_id}') if skeys.get(name) else False,
                        (skeys[name].get('switch', {}).get(f'{name}-{switch_id}', {}).get('SrcTemplate') or {}).get('Moid') if skeys.get(name) else False
                    ])
                    if src_template_merged: continue
                    sw_template = f"{tname}-{switch_id}"
                    if not kwargs.bulk_templates[org].get(sw_template):
                        tdata = kwargs.intersight_api[org].templates.domain['switch'][sw_template].result
                        if tdata is None:
                            pcolor.Red(f'!!! ERROR !!! Template "{sw_template}" not found in Intersight Org "{org}". Cannot perform bulk merge for profile "{name}".')
                            sys.exit(1)
                        kwargs.bulk_templates[org][sw_template] = {
                            'MergeAction': 'Merge', 'ObjectType': 'bulk.MoMerger', 'Targets':[],
                            'Sources':[{'Moid':tdata.Moid, 'ObjectType':tdata.ObjectType}]}
                    pdata = kwargs.intersight_api[original_org].profiles.domain[f"{name}-{switch_id}"].result
                    pdict = {'Moid': pdata.Moid, 'ObjectType': pdata.ObjectType}
                    kwargs.bulk_templates[org][sw_template]['Targets'].append(pdict)
            elif not (name in skeys and skeys[name] and (skeys[name].get('result', {}).get('SrcTemplate') or {}).get('Moid')):
                if not kwargs.bulk_templates[org].get(tname):
                    tdata = kwargs.intersight_api[org].templates[self.type][tname].result
                    if tdata is None:
                        pcolor.Red(f'!!! ERROR !!! Template "{tname}" not found in Intersight Org "{org}". Cannot perform bulk merge for profile "{name}".')
                        sys.exit(1)
                kwargs.bulk_templates[org][tname] = {
                    'MergeAction': 'Merge', 'ObjectType': 'bulk.MoMerger', 'Targets':[],
                    'Sources':[{'Moid':tdata.Moid, 'ObjectType':tdata.ObjectType}]}
                pdata = kwargs.intersight_api[original_org].profiles[self.type][f'{name}'].result
                pdict = {'Moid': pdata.Moid, 'ObjectType': pdata.ObjectType}
                kwargs.bulk_templates[org][tname]['Targets'].append(pdict)
        #=====================================================================
        # POST bulk/MoMergers if Map > 0 and return kwargs
        #=====================================================================
        if kwargs.bulk_templates:
            batch_size = 100
            def dedupe_moid_objects(items):
                unique = []
                seen = set()
                for item in items:
                    key = (item.get('Moid'), item.get('ObjectType'))
                    if key in seen: continue
                    seen.add(key)
                    unique.append(item)
                return unique

            def post_to_api(api_body, kwargs):
                kwargs = kwargs | DotMap(api_body = api_body, method = 'post', uri = 'bulk/MoMergers')
                kwargs = api(category=self.category, type='bulk_merger').calls(kwargs)
                return kwargs
            orgs = kwargs.bulk_templates.keys()
            for org in orgs:
                kwargs.org = org
                for k,v in kwargs.bulk_templates[org].items():
                    kwargs.bulk_templates[org][k]['Targets'] = dedupe_moid_objects(kwargs.bulk_templates[org][k]['Targets'])
                    kwargs.bulk_templates[org][k]['Sources'] = dedupe_moid_objects(kwargs.bulk_templates[org][k]['Sources'])
                    if len(v['Targets']) > batch_size:
                        request_list = deepcopy(v['Targets'])
                        for i in range(0, len(request_list), batch_size):
                            targets = request_list[i:i + batch_size]
                            v['Targets'] = targets
                            kwargs = post_to_api(v, kwargs)
                    elif v['Targets']: kwargs = post_to_api(v, kwargs)
        kwargs.org = original_org
        return kwargs

    #=========================================================================
    # Function - Chassis Profiles Updates
    #=========================================================================
    def profiles_chassis(self, kwargs):
        kwargs = self.profiles_chassis_server(kwargs)
        return kwargs

    #=========================================================================
    # Function - Build Chassis/Server Profiles
    #=========================================================================
    def profiles_chassis_server(self, kwargs):
        ezdata = kwargs.ezdata[f'intersight.profiles.{self.type}']
        np,ns  = self.name_prefix_suffix(kwargs.org, kwargs)
        ptitle = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        kwargs.merge_templates = DotMap()
        #=====================================================================
        # Lookup Serial Number Assignments for Chassis/Server Profiles
        #=====================================================================
        serial_numbers = []
        for item in kwargs.resources:
            ikeys = list(item.keys())
            if 'serial_number' in ikeys and re.search(serial_regex, item.serial_number):
                serial_numbers.append(item.serial_number)
        if serial_numbers:
            kwargs = kwargs | DotMap(method = 'get', names = serial_numbers, uri = ezdata.intersight_uri_serial)
            kwargs = api(category='system', type='serial_number').calls(kwargs)
        #=====================================================================
        # Assign Server Profile Identity Reservations - If Defined
        #=====================================================================
        reservations = False
        if self.type == 'server':
            for item in kwargs.resources:
                ikeys = list(item.keys())
                if 'reservations' in ikeys: reservations = True
        if reservations == True:
            kwargs = self.profiles_server_identity_reservations(kwargs)
            kwargs.bulk_list = []
            for item in kwargs.resources:
                ikeys = list(item.keys())
                name  = f'{np}{item.name}{ns}'
                if kwargs.intersight_api[kwargs.org].profiles.server.get(name):
                    continue
                if 'reservations' in ikeys:
                    api_body = {'Name': name, 'ObjectType': ezdata.object_type,'TargetPlatform':'FIAttached'}
                    api_body = self.profiles_org_map(api_body, kwargs.org_moids[kwargs.org].moid)
                    api_body = self.profiles_server_reservations(item, api_body, kwargs)
                    if api_body.get('ReservationReferences'): kwargs.bulk_list.append(api_body)
                    else: kwargs.bulk_list.append(api_body)
        else:
            kwargs.bulk_list = []
            for item in kwargs.resources:
                name  = f'{np}{item.name}{ns}'
                if kwargs.intersight_api[kwargs.org].profiles[self.type].get(name): continue
                api_body = {'Name': name, 'ObjectType': ezdata.object_type,'TargetPlatform':item.get('target_platform', 'FIAttached')}
                api_body = self.profiles_org_map(api_body, kwargs.org_moids[kwargs.org].moid)
                kwargs.bulk_list.append(api_body)
        #=================================================================
        # POST bulk/Requests if Bulk List > 0 - Initial Profile
        #=================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = ezdata.intersight_uri
            kwargs     = self.create_bulk_request(kwargs)
        #=====================================================================
        # Attach Templates either through Bulk Merger or Merging Dicts
        #=====================================================================
        kwargs.bulk_list = []
        template_attach  = False
        template_merge   = False
        for e in kwargs.resources:    
            if any(template_regex.match(k) for k in e.keys()):
                template_type = next((k for k in e.keys() if template_regex.match(k)), None)
                if e.get('attach_template', True) == True: template_attach = True
                elif e.get('attach_template', True) == False: template_merge = True
        if  template_attach == True: kwargs = self.profiles_bulk_merge_template(kwargs)
        elif template_merge == True: kwargs = self.profiles_template_lookup(template_type, kwargs)
        #=====================================================================
        # Update Intersight with Server Profile Configuration
        #=====================================================================
        kwargs.bulk_list = []
        for item in kwargs.resources:
            ikeys    = list(item.keys())
            if item.get('attach_template') == False and any(template_regex.match(k) for k in ikeys):
                template_type = next((k for k in ikeys if template_regex.match(k)), None)
                item = self.profiles_template_merge(item, item[template_type], ptitle, kwargs)
            api_body = self.create_api_body(item, np, ns, kwargs)
            kwargs   = self.compare_resources_to_api(api_body, ptitle, kwargs)
        # POST Bulk Request if List > 0
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = ezdata.intersight_uri
            kwargs     = self.create_bulk_request(kwargs)
        #=====================================================================
        # PATCH Profiles if has attach_template True and has a Description
        #=====================================================================
        kwargs.bulk_list = []
        for item in kwargs.resources:
            ikeys = list(item.keys())
            if item.get('attach_template') == False and any(template_regex.match(k) for k in ikeys):
                name = f'{np}{e.name}{ns}'
                api_body = dict(Description = '', Name = name, ObjectType = ezdata.object_type,
                                pmoid = kwargs.intersight_api[kwargs.org].profiles[self.type][name])
                if 'description' in ikeys: api_body['Description'] = item.description
                else: api_body['Description'] = f'{name} {self.type.capitalize()} Profile.'
                kwargs.bulk_list.append(api_body)
        if len(kwargs.bulk_list) > 0:
            pcolor.Cyan('')
            pcolor.Cyan(f'{" "*3}Updating {self.type.capitalize()} Profile Descriptions.')
            kwargs.uri = ezdata.intersight_uri
            kwargs     = self.create_bulk_request(kwargs)
        #=====================================================================
        # If Action is Deploy; Deploy the Profile
        #=====================================================================
        profiles = []
        for e in kwargs.resources:
            if 'action' in e and e.action == 'Deploy': profiles.append(e)
        if profiles: kwargs = self.profiles_chassis_server_deploy(profiles, kwargs)
        return kwargs

    #=========================================================================
    # Function - Deploy Profile if Action is Deploy
    #=========================================================================
    def profiles_chassis_server_deploy(self, profiles, kwargs):
        np, ns = self.name_prefix_suffix(kwargs.org, kwargs)
        profile_api = api(category=self.category, type=self.type)
        cregex = re.compile('Analyzing|Assigned|Failed|Inconsistent|Validating')
        pending_changes = False
        kwargs.profile_update = DotMap()
        kwargs.uri = kwargs.ezdata[f"intersight.profiles.{self.type}"].intersight_uri
        for e in profiles:
            if 'action' in e and 'serial_number' in e and re.search(serial_regex, e.serial_number):
                kwargs.profile_update[f'{np}{e.name}{ns}'] = e
                kwargs.profile_update[f'{np}{e.name}{ns}'].pending_changes = 'Empty'
        if kwargs.profile_update:
            names = list(kwargs.profile_update.keys())
            kwargs = self.api_get(False, names, self.type, kwargs)
            profile_map = kwargs.intersight_api[kwargs.org].profiles[self.type]
            for e in names:
                profile_data = profile_map.get(e)
                if not profile_data:
                    pcolor.Yellow(f'  * Skipping Org: {kwargs.org}; Profile `{e}` not found in API lookup.')
                    continue
                pdata = profile_data.result
                changes  = pdata.get('ConfigChanges', {}).get('Changes', [])
                cstate   = pdata.get('ConfigContext', {}).get('ConfigState') or ''
                csummary = pdata.get('ConfigContext', {}).get('ConfigStateSummary') or ''
                if changes or re.search(cregex, cstate) or re.search(cregex, csummary):
                    pending_changes = True
                    kwargs.profile_update[e].pending_changes = 'Deploy'
                elif pdata.get('ConfigChanges', {}).get('PolicyDisruptions', []):
                    pending_changes = True
                    kwargs.profile_update[e].pending_changes = 'Activate'
            if pending_changes:
                pcolor.LightPurple(f'\n{"-"*108}\n')
                deploy_pending = any(kwargs.profile_update[e].pending_changes == 'Deploy' for e in names)
                activate_pending = any(kwargs.profile_update[e].pending_changes == 'Activate' for e in names)
                if deploy_pending:
                    if 'server' == self.type:  pcolor.LightPurple(f'{" "*4}* Pending Changes.  Sleeping for 120 Seconds'); time.sleep(120)
                    else:  pcolor.LightPurple('    * Pending Changes.  Sleeping for 60 Seconds'); time.sleep(60)
                for e in names:
                    if kwargs.profile_update[e].pending_changes == 'Deploy':
                        pcolor.Green(f'{" "*4}- Beginning Profile Deployment for `{e}`.')
                        kwargs = kwargs | DotMap(api_body = {'Action': 'Deploy', 'Name': e}, method = 'patch', pmoid = profile_map[e].moid)
                        kwargs = profile_api.calls(kwargs)
                    elif kwargs.profile_update[e].pending_changes == 'Activate':
                        pcolor.LightPurple(f'{" "*4}- Skipping Org: {kwargs.org}; Profile Deployment for `{e}`.  Pending Activation.')
                    else:
                        pcolor.LightPurple(f'{" "*4}- Skipping Org: {kwargs.org}; Profile Deployment for `{e}`.  No Pending Changes.')
                if deploy_pending:
                    if 'server' == self.type:  pcolor.LightPurple(f'{" "*4}* Deploying Changes.  Sleeping for 600 Seconds'); time.sleep(600)
                    else:  pcolor.LightPurple(f'{" "*4}* Deploying Changes.  Sleeping for 60 Seconds'); time.sleep(60)
                for e in names:
                    if kwargs.profile_update[e].pending_changes == 'Deploy':
                        deploy_complete = False
                        retry_count = 0
                        max_retries = 60
                        while not deploy_complete:
                            if retry_count >= max_retries:
                                pcolor.Yellow(f'{" "*4}- Deploy timeout waiting for `{e}` after {max_retries} checks.')
                                break
                            kwargs = kwargs | DotMap(method = 'get_by_moid', pmoid = profile_map[e].moid)
                            kwargs = profile_api.calls(kwargs)
                            control_action = kwargs.results.get('ConfigContext', {}).get('ControlAction')
                            if control_action == 'No-op':
                                deploy_complete = True
                                if 'chassis' in self.type: pcolor.Green(f'{" "*4}- Completed Profile Deployment for `{e}`.')
                            else:
                                if 'server' in self.type: pcolor.Cyan(f'{" "*6}* Deploy Still Occuring on `{e}`.  Waiting 120 seconds.'); time.sleep(120)
                                else: pcolor.Cyan(f'{" "*6}* Deploy Still Occuring on `{e}`.  Waiting 60 seconds.'); time.sleep(60)
                            retry_count += 1
                if 'server' == self.type and activate_pending:
                    kwargs = self.profiles_server_activate(kwargs)
                pcolor.LightPurple(f'\n{"-"*108}\n')
        return kwargs

    #=========================================================================
    # Function - Domain Profiles Updates
    #=========================================================================
    def profiles_domain(self, kwargs):
        item = self.profiles_templates_domain_unified_edge(kwargs)
        return item

    #=========================================================================
    # Function - Deploy Domain Profile if Action is Deploy
    #=========================================================================
    def profiles_domain_deploy(self, profiles, kwargs):
        dtype = self.type.split('.')[1]
        pending_changes = False
        kwargs.names    = []
        np, ns = self.name_prefix_suffix(kwargs.org, kwargs)
        for e in profiles:
            name = f'{np}{e.name}{ns}'
            kwargs.cluster_update[name].names = []
            kwargs.cluster_update[name].pending_changes = False
            if e.get('action') and e.get('serial_numbers'):
                serial_check = True
                for d in e.serial_numbers:
                    if not re.search(serial_regex, d): serial_check = False
                if e.action == 'Deploy' and serial_check == True:
                    kwargs.names.append(kwargs.intersight_api[kwargs.org].profiles[self.type][name].moid)
        clusters = DotMap()
        for k,v in kwargs.intersight_api[kwargs.org].profiles[self.type].items(): clusters[v] = k
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
                    kwargs.bulk_list.append({'Action':'Deploy', 'Name': e, 'pmoid':kwargs.intersight_api[kwargs.org].profiles['switch'][e].moid})
        if len(kwargs.bulk_list) > 0: kwargs = configure('profiles.switch').create_bulk_request(kwargs)
        if pending_changes == True: pcolor.LightPurple(f'\n{"-"*108}\n'); time.sleep(60)
        for k in list(kwargs.cluster_update.keys()):
            if kwargs.cluster_update[k].pending_changes == True:
                kwargs = kwargs | DotMap(method = 'get_by_moid', uri = kwargs.ezdata[self.type].switch_intersight_uri)
                for e in kwargs.cluster_update[k].names:
                    kwargs.pmoid = kwargs.intersight_api[kwargs.org].profiles['switch'][e].moid
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
    # Function - Add Organization Key Map to Dictionaries
    #=========================================================================
    def profiles_org_map(self, api_body, org_moid):
        api_body.update({'Organization':{'Moid':org_moid, 'ObjectType':'organization.Organization'}})
        return api_body

    #=========================================================================
    # Function - Server Profiles Updates
    #=========================================================================
    def profiles_server(self, kwargs):
        kwargs = self.profiles_chassis_server(kwargs)
        return kwargs

    #=========================================================================
    # Function - Deploy Profile if Action is Deploy
    #=========================================================================
    def profiles_server_activate(self, kwargs):
        pcolor.LightPurple(f'\n{"-"*108}\n')
        profile_api  = api(category=self.category, type=self.type)
        profile_keys = list(kwargs.profile_update.keys())
        active_profiles = [e for e in profile_keys if kwargs.profile_update[e].pending_changes != 'Empty']
        if active_profiles:
            kwargs = self.api_get(False, active_profiles, self.type, kwargs)
            profile_results = kwargs.results
            profile_results_by_name = {d['Name']: d for d in profile_results}
        else:
            profile_results_by_name = {}
        pending_activations = False
        for e in active_profiles:
            profile_result = profile_results_by_name.get(e)
            if not profile_result:
                pcolor.LightPurple(f'{" "*4}- Skipping Org: {kwargs.org}; Profile Activation for `{e}`.  Profile not found.')
                kwargs.profile_update[e].pending_changes = 'Empty'
                continue
            if profile_result.get('ConfigChanges', {}).get('PolicyDisruptions', []):
                pcolor.Green(f'{" "*4}- Beginning Profile Activation for `{e}`.')
                api_body = {'ScheduledActions':[{'Action':'Activate', 'ProceedOnReboot':True}]}
                kwargs   = kwargs | DotMap(api_body = api_body, method = 'patch', pmoid = kwargs.intersight_api[kwargs.org].profiles[self.type][e].moid)
                kwargs   = profile_api.calls(kwargs)
                pending_activations = True
            else:
                pcolor.LightPurple(f'{" "*4}- Skipping Org: {kwargs.org}; Profile Activation for `{e}`.  No Pending Changes.')
                kwargs.profile_update[e].pending_changes = 'Empty'
        if pending_activations:
            pcolor.LightPurple(f'\n{"-"*108}\n')
            pcolor.LightPurple('    * Pending Activations.  Sleeping for 300 Seconds'); time.sleep(300)
        activate_moids = [kwargs.intersight_api[kwargs.org].profiles[self.type][e].moid for e in profile_keys if kwargs.profile_update[e].pending_changes != 'Empty']
        activate_results = []
        if activate_moids:
            dt     = datetime.today().strftime('%Y-%m-%d')
            names  = "', '".join(activate_moids).strip("', '")
            str1   = f"CreateTime gt {dt}T00:00:00.000Z and CreateTime lt {dt}T23:59:59.999Z and AssociatedObject.Moid in ('{names}')"
            str2   = f" and WorkflowCtx.WorkflowType eq 'Activate'"
            kwargs = kwargs | DotMap(api_filter = str1 + str2, method = 'get', uri = 'workflow/WorkflowInfos')
            kwargs = api('workflows').calls(kwargs)
            activate_results = sorted(kwargs.results, key=itemgetter('CreateTime'), reverse=True)
        activate_results_by_moid = {}
        for result in activate_results:
            assoc_moid = result.get('AssociatedObject', {}).get('Moid')
            if assoc_moid and not activate_results_by_moid.get(assoc_moid):
                activate_results_by_moid[assoc_moid] = result

        def activation_message(e, progress, status):
            pcolor.Cyan(f'{" "*6}* Still In Progress for `{e}`.  Status: `{status}` Progress Percentage: `{progress}`, Sleeping for 120 seconds.')
        def failed_message(e):
            pcolor.Yellow(f'\n{"-"*75}\n')
            pcolor.Red(f'  - Failed to Activate Profile `{e}`.  Please validate in Intersight the reason for the failure.')
            pcolor.Yellow(f'\n{"-"*75}\n')
        def success_message(e):
            pcolor.Green(f'{" "*4}- Completed Profile Activation for `{e}`.')

        for e in profile_keys:
            if kwargs.profile_update[e].pending_changes != 'Empty':
                prmoid = kwargs.intersight_api[kwargs.org].profiles[self.type][e].moid
                active_result = activate_results_by_moid.get(prmoid)
                if not active_result:
                    failed_message(e)
                    continue
                deploy_complete = False
                retry_count = 0
                while not deploy_complete:
                    if retry_count >= 60:
                        failed_message(e)
                        deploy_complete = True
                        continue
                    if retry_count > 0:
                        kwargs = kwargs | DotMap(method = 'get_by_moid', pmoid = active_result.Moid)
                        kwargs = api(category='profiles', type='workflows').calls(kwargs)
                        active_result = kwargs.results
                    status = active_result.get('WorkflowStatus')
                    if status == 'Completed': success_message(e); deploy_complete = True
                    elif re.search('Failed|Terminated|Canceled', status or ''):
                        failed_message(e); deploy_complete = True
                    else:
                        progress = active_result.get('Progress'); status = active_result.get('WorkflowStatus')
                        activation_message(e, progress, status); time.sleep(120)
                    retry_count += 1
            else:
                pcolor.LightPurple(f'{" "*4}- Skipping Org: {kwargs.org}; Profile Activation for `{e}`.  No Pending Changes.')
        return kwargs

    #=========================================================================
    # Function - Server Profile Identity Reservations
    #=========================================================================
    def profiles_server_identity_reservations(self, kwargs):
        #=====================================================================
        # Send Begin Notification and Load Variables
        #=====================================================================
        pcolor.LightGray(f'  {"-"*60}\n')
        pcolor.LightPurple(f'   Beginning Server Profile Pool Reservations Deployments\n')
        #=====================================================================
        # Obtain Pool Names
        #=====================================================================
        np, ns = self.name_prefix_suffix(kwargs.org, kwargs)
        kwargs.cpools = DotMap()
        for item in kwargs.resources:
            if item.get('reservations') and not item.get('ignore_reservations', False):
                for i in item.reservations:
                    pool_name = i.get('pool_name', '')
                    ptype = str(i.get('identity_type', '')).lower()
                    if pool_name and ptype:
                        org, pool = pool_name.split('/')
                        pentry = kwargs.intersight_api.get(org, {}).get('pools', {}).get(ptype, {}).get(pool)
                        if not pentry:
                            pcolor.Yellow(f'  * Skipping Org: {kwargs.org}; Pool `{pool_name}` ({ptype}) not found for reservation lookup.')
                            continue
                        pmoid = pentry.moid
                        if not kwargs.cpools.get(ptype): kwargs.cpools[ptype] = []
                        kwargs.cpools[ptype].append(pmoid)
        #=====================================================================
        # Get Identity Leases & Reservations
        #=====================================================================
        for k, v in kwargs.cpools.items():
            if v:
                names = list(set(v))
                kwargs = configure(category='pools', type=f'{k}.leases').api_get(True, names, f'{k}.leases', kwargs)
                kwargs = configure(category='pools', type=f'{k}.reservations').api_get(True, names, f'{k}.reservations', kwargs)
        #=====================================================================
        # Build Identity Reservations api_body
        #=====================================================================
        def get_ip_type(identity):
            return 'IPv6' if ':' in identity else 'IPv4'
        def build_api_body(item, e, kwargs):
            org, pool    = e.pool_name.split('/')
            ptype        = str(e.identity_type).lower()
            pdata        = kwargs.intersight_api[org].pools[ptype][pool]
            leases       = pdata.get('lease', {}) if pdata.get('lease') else {}
            profile      = f'{np}{item.name}{ns}'
            reservations = pdata.get('reservation', {}) if pdata.get('reservation') else {}
            if not e.identity in leases.keys():
                if e.identity not in reservations.keys():
                    org, pool = e.pool_name.split('/')
                    pdata     = kwargs.intersight_api[org].pools[ptype][pool].result
                    api_body  = {'Identity':e.identity, 'Pool':{'Moid':pdata.Moid,'ObjectType':pdata.ObjectType}}
                    if re.search('wwnn|wwpn', ptype): api_body['IdPurpose'] = ptype.upper()
                    api_body = self.profiles_org_map(api_body, kwargs.org_moids[org].moid)
                    if 'ip' == ptype: api_body.update({'IpType': get_ip_type(e.identity)})
                    if not bulk_list.get(ptype): bulk_list[ptype] = []
                    bulk_list[ptype].append(api_body)
                else:
                    reservations[e.identity].moid
                    pcolor.Cyan(f"  * Skipping Org: {kwargs.org} > Server Profile: `{profile}` > {ptype.upper()} Reservation: {e.identity}. "\
                                f"Existing reservation: {reservations[e.identity].moid}")
            else:
                entity = leases[e.identity].result['AssignedToEntity']
                pcolor.Yellow(f"  * NOTIFICATION: Org: {kwargs.org} > Server Profile: `{profile}` > {ptype.upper()} Reservation: {e.identity}. "\
                              f"Currently leased to {entity['ObjectType']} - Moid: {entity['Moid']}")
            return kwargs
        bulk_list = DotMap()
        for item in kwargs.resources:
            if item.reservations:
                for e in item.reservations: kwargs = build_api_body(item, e, kwargs)
        #=====================================================================
        # POST Bulk Request if Post List > 0
        #=====================================================================
        for k,v in bulk_list.items():
            if v:
                kwargs.bulk_list = v
                kwargs.uri       = kwargs.ezdata[f'intersight.pools.{k}.reservations'].intersight_uri
                kwargs           = configure(self.type, category='pools').create_bulk_request(kwargs)
        #=====================================================================
        # Send End Notification and return kwargs
        #=====================================================================
        pcolor.LightPurple(f'\n    Completed Pool Reservations Deployments\n')
        pcolor.LightGray(f'  {"-"*60}\n')
        return kwargs

    #=========================================================================
    # Function - Build Server Profile Reservations
    #=========================================================================
    def profiles_server_reservations(self, e, api_body, kwargs):
        for i in e.reservations:
            org, pool = i.pool_name.split('/')
            ptype = str(i.identity_type).lower()
            pdata = kwargs.intersight_api[org].pools[ptype][pool]
            rkeys = list(pdata.get('reservation', {}).keys()) if pdata.get('reservation') else []
            if i.identity in rkeys:
                if not api_body.get('ReservationReferences'): api_body['ReservationReferences'] = []
                rdata = pdata.reservation[i.identity].result
                if 'ww' in ptype: rdict = {'ObjectType':'fcpool.ReservationReference'}
                else: rdict = {'ObjectType':f'{ptype}pool.ReservationReference'}
                rdict.update({'ReservationMoid': rdata.Moid})
                if re.search('ip|mac|wwnn|wwpn', ptype):
                    if 'ip' in ptype and i.get('ip_usage', '') == 'Management':
                        if ':' in i.identity: rdict.update({'ConsumerType':'InbandIpv6-Access'})
                        else:
                            mgmt_type = str(i.get('management_type', 'Inband')).lower().capitalize()
                            rdict.update({'ConsumerType':f'{mgmt_type}Ipv4-Access'})
                    elif i.get('ip_usage', '') == 'iSCSI': rdict.update({'ConsumerName':i.interface,'ConsumerType':'ISCSI'})
                    elif 'mac'  in ptype: rdict.update({'ConsumerName':i.interface,'ConsumerType':'Vnic'})
                    elif 'wwpn' in ptype: rdict.update({'ConsumerName':i.interface,'ConsumerType':'Vhba'})
                    elif 'wwnn' in ptype: rdict.update({'ConsumerType':'WWNN'})
                api_body['ReservationReferences'].append(rdict)
            else:
                pcolor.Yellow(f"  * NOTIFICATION: Reservation identity `{i.identity}` not found in pool `{i.pool_name}` ({ptype}).")
        return api_body

    #=========================================================================
    # Function - Server Profiles/Templates Updates
    #=========================================================================
    def profiles_templates_create_policy_bucket(self, item, kwargs):
        ikeys = list(item.keys())

        chassis_ = ['imc_access_policy', 'power_policy', 'snmp_policy', 'thermal_policy']
        domain_  = [
            'auditd_policy', 'certificate_management_policy', 'ldap_policy', 'netflow_configuration_policy', 'network_connectivity_policy',
            'ntp_policy', 'port_policy', 'snmp_policy', 'switch_control_policy', 'syslog_policy', 'system_qos_policy', 'vlan_policy', 'vsan_policy'
        ]
        fi_only = ['drive_security_policy', 'pcie_connectivity_policy', 'san_connectivity_policy', 'sd_card_policy', 'thermal_policy']
        fi_unified_common = [
            'bios_policy', 'boot_order_policy', 'certificate_management_policy', 'firmware_policy', 'imc_access_policy', 'ipmi_over_lan_policy',
            'lan_connectivity_policy', 'local_user_policy', 'memory_policy', 'power_policy', 'scrub_policy', 'serial_over_lan_policy', 'snmp_policy',
            'storage_policy', 'syslog_policy', 'virtual_kvm_policy', 'virtual_media_policy'
        ]
        standalone_common = [
            'bios_policy', 'certificate_management_policy', 'firmware_policy', 'ipmi_over_lan_policy', 'local_user_policy', 'power_policy',
            'serial_over_lan_policy', 'smtp_policy', 'ssh_policy', 'virtual_kvm_policy', 'virtual_media_policy',
        ]
        standalone_2xx_4xx_only = [
            'boot_order_policy', 'memory_policy', 'persistent_memory_policy', 'thermal_policy', 'device_connector_policy', 'ldap_policy',
            'network_connectivity_policy', 'ntp_policy', 'snmp_policy', 'syslog_policy', 'drive_security_policy', 'sd_card_policy',
            'storage_policy', 'adapter_configuration_policy', 'lan_connectivity_policy', 'san_connectivity_policy'
        ]
        unified_edge_ = [
            'power_policy', 'thermal_policy', 'port_policy', 'switch_control_policy', 'system_qos_policy', 'vlan_policy',
            'local_user_policy', 'network_connectivity_policy', 'ntp_policy', 'syslog_policy'
        ]
        target_platform = item.get('target_platform', 'FIAttached')
        server_family = item.get('server_family', 'All')

        if   self.type == 'chassis' or target_platform == 'Chassis': allowed_policies = chassis_
        elif self.type == 'domain'  or target_platform == 'UCS Domain':  allowed_policies = domain_
        elif self.type == 'unified_edge' or target_platform == 'Unified Edge': allowed_policies = unified_edge_
        elif target_platform == 'FIAttached':        allowed_policies = fi_unified_common + fi_only
        elif target_platform == 'UnifiedEdgeServer': allowed_policies = fi_unified_common
        elif target_platform == 'Standalone':
            if   server_family == 'UCSC845A':    allowed_policies = standalone_common
            elif server_family == 'UCSC2XX/4XX': allowed_policies = standalone_common + standalone_2xx_4xx_only
            else: allowed_policies = standalone_common + standalone_2xx_4xx_only
        else: allowed_policies = fi_unified_common + fi_only
        item.allowed_policies = list(dict.fromkeys(allowed_policies))
        item.policy_bucket = DotMap()

        # Find policy keys from input item, excluding internal control attributes
        internal_keys = {'allowed_policies', 'policy_bucket', 'object_map', 'target_platform', 'server_family'}
        policy_like_keys = [k for k in ikeys if k.endswith('_policy') and item.get(k) and k not in internal_keys]
        allowed_input_keys = set(item.allowed_policies)
        skipped = [k for k in policy_like_keys if k not in allowed_input_keys]
        if len(skipped) > 0:
            message_title = f'{target_platform}/{server_family}' if self.type == 'server' else f'{target_platform.title()}'
            pcolor.Yellow(
                f"  * Skipping unsupported template policies for `{item.name}` ({message_title}): "
                f"{', '.join(sorted(skipped))}"
            )
        # Attach Allowed Policies to policy_bucket for downstream processing and API body construction.
        for key in item.allowed_policies:
            if key in ikeys and item.get(key):
                item.policy_bucket[key] = item[key]
        item.object_map = kwargs.intersight_object_map
        return item

    #=========================================================================
    # Function - Profiles Merge Defined Templates
    #=========================================================================
    def profiles_template_lookup(self, template_type, kwargs):
        ptitle = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        kwargs.templates = DotMap()
        orgs = set()
        template_success = True
        template_cfg = configure(category='templates', type=self.type)
        for e in kwargs.resources:
            if template_type in e and e.get(template_type) is not None:
                template_org, template_name = template_cfg.determine_resource_organization(False, e[template_type], kwargs)
                orgs.add(template_org)
                templates = kwargs.imm_templates[template_org].templates[self.type]
                if template_name in templates:
                    kwargs.templates[template_org][template_name] = kwargs.imm_templates[template_org].templates[self.type][template_name]
                else:
                    kwargs.templates[template_org][template_name] = DotMap()
                    template_success = False
        if template_success == False and orgs:
            template_results = []
            if re.search('domain|unified_edge', self.type): ttype = 'domain.switch'
            else: ttype = self.type
            template_cfg   = configure(category='templates', type=ttype)
            for org in orgs:
                if ttype == 'domain.switch': names = [f'{e}-{l}' for e in kwargs.templates[org].keys() for l in ['A', 'B'] if len(e.toDict()) == 0 ]
                else: names = [e for e in kwargs.templates[org].keys() if len(e.toDict()) == 0]
                if len(names) > 0:
                    kwargs = template_cfg.api_get(False, [kwargs.templates[org].keys()], ttype, kwargs)
                    kwargs.intersight_policies = DotMap()
                    kwargs.intersight_pools    = DotMap()
                    for e in kwargs.results:
                        template_results.append(e)
                        for p in e.PolicyBucket:
                            ptype = kwargs.intersight_object_map[p.ObjectType]
                            kwargs.policies.setdefault(ptype, DotMap())
                            if p.Moid in kwargs.policies[ptype]: continue
                            kwargs.intersight_policies.setdefault(ptype, [])
                            if p.Moid not in kwargs.intersight_policies[ptype]:
                                kwargs.intersight_policies[ptype].append(p.Moid)
                        if e.get('UuidPool'):
                            kwargs.pools.setdefault('uuid', DotMap())
                            if e.UuidPool.Moid in kwargs.pools['uuid']: continue
                            kwargs.intersight_pools.setdefault('uuid', [])
                            if e.UuidPool.Moid not in kwargs.intersight_pools['uuid']:
                                kwargs.intersight_pools['uuid'].append(e.UuidPool.Moid)
            policies_cfg = api(category='policies', type='moid_filter')
            for k,v in kwargs.intersight_policies.items():
                if v:
                    uri = kwargs.ezdata[f'intersight.policies.{k}'].intersight_uri
                    kwargs = kwargs | DotMap(method = 'get', names = v, uri = uri)
                    kwargs = policies_cfg.calls(kwargs)
                    for e in kwargs.results:
                        kwargs.policies[k][e.Moid] = DotMap(name = e.Name, organization = kwargs.org_names[e.Organization.Moid])
            if kwargs.intersight_pools.get('uuid'):
                uri = kwargs.ezdata[f'intersight.pools.uuid'].intersight_uri
                kwargs = kwargs | DotMap(method = 'get', names = kwargs.pools['uuid'], uri = uri)
                kwargs = api(category='pools', type='moid_filter').calls(kwargs)
                for e in kwargs.results:
                    kwargs.pools[k][e.Moid] = DotMap(name = e.Name, organization = kwargs.org_names[e.Organization.Moid])
            for e in template_results:
                name = e.get('Name', '')
                organization = kwargs.org_names[e.Organization.Moid]
                if e.get('UuidPool'):
                    pref = kwargs.pools['uuid'][e.UuidPool.Moid]
                    kwargs.templates[organization][name].uuid_pool = f'{kwargs.org_names[pref.Organization.Moid]}/{pref.Name}'
                for p in e.PolicyBucket:
                    ptype = kwargs.intersight_object_map[p.ObjectType]
                    pref  = kwargs.policies[ptype][p.Moid]
                    kwargs.templates[organization][name][f'{ptype}_policy'] = f'{kwargs.org_names[pref.Organization.Moid]}/{pref.Name}'
            if ttype == 'domain.switch':
                policy_keys = {'port_policy', 'vlan_policy', 'vsan_policy'}
                for org in orgs:
                    templates = [e for e in kwargs.templates[org].keys() if len(kwargs.templates[org][e].toDict()) == 0 and re.search('-A$', e)]
                    for template in templates:
                        tname = re.sub("-A$", "", template, flags=re.IGNORECASE)
                        kwargs.templates[org][tname] = DotMap()
                        for suffix in ['A', 'B']:
                            for k,v in kwargs.templates[org][f'{template}-{suffix}'].items():
                                if k.endswith('_policy') or k.endswith('_pool'):
                                    if k in policy_keys:
                                        plural_type = k.replace('_policy', '_policies')
                                        if not kwargs.templates[org][tname].get(plural_type, None):
                                            kwargs.templates[org][tname][plural_type] = []
                                        if not v in kwargs.templates[org][tname][plural_type]:
                                            kwargs.templates[org][tname][plural_type].append(v)
                                    elif not kwargs.templates[org][tname].get(k, None):
                                        kwargs.templates[org][tname][k] = v
        final_check = True
        for org in orgs:
            templates = [e for e in kwargs.templates[org].keys()]
            for template in templates:
                if len(kwargs.templates[org][template].toDict()) == 0:
                    final_check = False
                    pcolor.Red(f'!!! ERROR !!! {ptitle} Template(s) "{", ".join(templates)}" were not found under Organization "{org}".')
                    pcolor.Red(f'Available templates in Organization `{org}` are: {", ".join(sorted(templates))}')
        if final_check == False: sys.exit(1)
        return kwargs

    #=========================================================================
    # Function - Profiles Merge Defined Templates
    #=========================================================================
    def profiles_template_merge(self, item, template_name, ptitle, kwargs):
        org, name = template_name.split('/')
        templates = kwargs.templates[org]
        if name in templates:
            merged = self.deep_merge_dicts(deepcopy(templates[name].toDict()), item.toDict())
        else:
            pcolor.Red(f'!!! ERROR !!! {ptitle} Template "{template_name}" was not found.')
            pcolor.Red(f'Available templates in Organization `{org}` are: {", ".join(sorted(templates.keys()))}')
            sys.exit(1)
        return DotMap(merged)

    #=========================================================================
    # Function - Domain/Unified Edge Profiles/Templates Updates
    #=========================================================================
    def profiles_templates_domain_unified_edge(self, kwargs):
        kwargs.merge_templates = DotMap()
        ptitle  = ezfunctions.mod_pol_description((self.type.replace('_', ' ').title()))
        serials = []; names = []
        org     = kwargs.org
        np, ns  = self.name_prefix_suffix(org, kwargs)
        if self.type == 'unified_edge': target_platform = 'Unified Edge'
        else: target_platform = 'UCS Domain'
        template_type  = f'{target_platform.lower().replace(" ", "_")}_profile_template'
        template_cfg   = configure(category='templates', type=f'{self.type}')
        template_check = False
        resources = deepcopy(kwargs.resources)
        for e in resources:
            ekeys = list(e.keys())
            if self.category == 'profiles':
                if 'serial_numbers' in ekeys:
                    remove_count = 0
                    for s in e.serial_numbers:
                        if re.search(serial_regex, s): serials.append(s)
                        else:
                            remove_count += 1
                            pcolor.Yellow(f'!!! WARNING !!! Serial number "{s}" does not match expected format and will be skipped for profile "{e.name}".')
                    if remove_count > 0: kwargs.resources[kwargs.resources.index(e)].serial_numbers = []
                elif 'serial_number' in ekeys:
                    if re.search(serial_regex, e.serial_number): serials.append(e.serial_number)
                    else:
                        kwargs.resources[kwargs.resources.index(e)].serial_number = None
                        pcolor.Yellow(f'!!! WARNING !!! Serial number "{e.serial_number}" does not match expected format and will be skipped for profile "{e.name}".')
                if self.category == 'profiles' and item.get(template_type, None) is not None and e.get('attach_template', True) == False:
                    template_check = True
            names.append(f'{np}{e.name}{ns}')
        if template_check == True: kwargs = self.profiles_template_lookup(template_type, kwargs)
        if len(serials) > 0: kwargs = system(category='system', type=self.type).api_get(True, serials, kwargs)
        kwargs.org = org
        kwargs     = self.api_get(True, names, self.type, kwargs)
        domain_cfg = configure(category=self.category, type='domain')
        switch_cfg = configure(category=self.category, type='domain.switch')
        pdict      = kwargs.intersight_api[org][self.category].domain
        kwargs     = switch_cfg.api_get(True, [pdict[e].moid for e in names if e in pdict], 'domain.switch', kwargs)
        #=====================================================================
        # Domain/Unified Edge Profile API Body Creation and Comparison Loop.
        # If Differences or No Existing Resource, Append to Bulk List for POST/PATCH.  If No Differences, Skip.
        #=====================================================================
        kwargs.bulk_list = []
        for item in kwargs.resources:
            item.target_platform = self.type.replace('_', ' ').title()
            api_body = domain_cfg.create_api_body(item, np, ns, kwargs)
            kwargs   = domain_cfg.compare_resources_to_api(api_body, ptitle, kwargs)
        # POST Bulk Request if List > 0
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.domain"].intersight_uri
            kwargs     = domain_cfg.create_bulk_request(kwargs)
        #=====================================================================
        # Domain/Unified Edge Switch Profile API Body Creation and Comparison Loop.
        # If Differences or No Existing Resource, Append to Bulk List for POST/PATCH.  If No Differences, Skip.
        #=====================================================================
        policies        = ['port_policies', 'vlan_policies', 'vsan_policies']
        policy_singular = {p: p.replace('_policies', '_policy') for p in policies}
        kwargs.bulk_list = []
        for item in kwargs.resources:
            item.name   = f"{np}{item.name}{ns}"
            item.parent = kwargs.intersight_api[org][self.category].domain[item.name].moid
            item.target_platform = target_platform
            if self.category == 'profiles' and item.get('attach_template', True) is False and item.get(template_type, None) is not None:
                item = self.profiles_template_merge(item, item[template_type], ptitle, kwargs)
            i_orginal   = deepcopy(item)
            for s in ['A', 'B']:
                item = deepcopy(i_orginal)
                item.index = ord(s) - 65
                item.switch_id = s
                for p in policies:
                    if p in item:
                        item[policy_singular[p]] = item[p][item.index] if len(item[p]) > 1 else item[p][0]
                        item.pop(p)
                item = self.profiles_templates_create_policy_bucket(item, kwargs)
                api_body = switch_cfg.create_api_body(item, np, ns, kwargs)
                kwargs   = switch_cfg.children_compare_api_body(api_body, kwargs)
        # POST Bulk Request if List > 0
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.domain.switch"].intersight_uri
            kwargs     = switch_cfg.create_bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Unified Edge Profiles Updates
    #=========================================================================
    def profiles_unified_edge(self, kwargs):
        kwargs = self.profiles_templates_domain_unified_edge(kwargs)
        return kwargs

    #=========================================================================
    # Function - Chassis Templates Updates
    #=========================================================================
    def templates_chassis(self, item, kwargs):
        item = self.profiles_templates_create_policy_bucket(item, kwargs)
        return item

    #=========================================================================
    # Function - Domain Templates Updates
    #=========================================================================
    def templates_domain(self, kwargs):
        kwargs = self.profiles_templates_domain_unified_edge(kwargs)
        return kwargs

    #=========================================================================
    # Function - Server Templates Updates
    #=========================================================================
    def templates_server(self, item, kwargs):
        item = self.profiles_templates_create_policy_bucket(item, kwargs)
        return item

    #=========================================================================
    # Function - Unified Edge Templates Updates
    #=========================================================================
    def templates_unified_edge(self, kwargs):
        kwargs = self.profiles_templates_domain_unified_edge(kwargs)
        return kwargs

#=============================================================================
# Intersight -> System Class
#=============================================================================
class system(object):
    def __init__(self, type, category=None):
        self.type = type
        self.category = category

    #=========================================================================
    # Function - API Get Calls
    #=========================================================================
    def api_get(self, empty=False, names=None, kwargs=None):
        if names is None: names = []
        if kwargs is None: kwargs = DotMap()
        #=====================================================================
        # Function - Exit on Empty Results
        #=====================================================================
        def empty_results(names, kwargs):
            pcolor.Red(f"The API Query Results were empty for {kwargs.uri}.");
            pcolor.Red(f"  Names: `{', '.join(names)}`");
            pcolor.Red(f"Exiting..."); sys.exit(1)
        if re.search(r'^(blades|rackmounts)$', self.type):
            kwargs = kwargs | DotMap(names = names, method = 'get', uri = 'compute/PhysicalSummaries')
        elif 'iam_sharing_rules' == self.type:
            kwargs = kwargs | DotMap(names = names, method = 'get', uri = 'iam/SharingRules')
        elif 'targets' == self.type:
            kwargs = kwargs | DotMap(names = names, method = 'get', uri = 'asset/Targets')
        else:
            uri    = kwargs.ezdata[f"intersight.{self.category}.{self.type}"].intersight_uri
            kwargs = kwargs | DotMap(names = names, org = 'default', method = 'get', uri = uri)
        kwargs = api(self.type, category=self.category).calls(kwargs)
        if empty == False and kwargs.results == []: empty_results(names, kwargs)
        elif empty == True and kwargs.results == []:
            pcolor.Yellow(f"  * API Query Results were empty for {kwargs.uri}")
            pcolor.Yellow(f"    - Names: `{', '.join(names)}`.  Continuing...")
        return kwargs

    #=========================================================================
    # Function - Create API Request Body
    #=========================================================================
    def create_api_body(self, item, kwargs):
        if re.fullmatch('resource_groups', self.type):
            item = getattr(self, self.type)(item, kwargs)
        item  = configure(category=self.category, type=self.type).merge_tags(item, kwargs)
        
        template_dir  = os.path.join(kwargs.script_path, 'classes', 'templates', 'intersight', f'{self.category}')
        template_name = f'{self.type}.json.j2'
        template_env  = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir), autoescape=False)

        render_item = item.toDict() if hasattr(item, 'toDict') else item
        rendered    = template_env.get_template(template_name).render(
            item         = render_item,
            isight       = kwargs.intersight_api,
            object_map   = kwargs.intersight_object_map,
            org_moids    = kwargs.org_moids,
            rsg_moids    = kwargs.rsg_moids
        )
        try:
            api_body = json.loads(rendered)
        except json.JSONDecodeError as exc:
            policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
            pcolor.Red(
                f'!!! ERROR !!! Failed to parse rendered JSON for {policy_title} template '
                f'`{template_name}` (line {exc.lineno}, column {exc.colno}).'
            )
            start = max(1, exc.lineno - 2)
            end = min(len(rendered.splitlines()), exc.lineno + 2)
            for line_no in range(start, end + 1):
                marker = '>>' if line_no == exc.lineno else '  '
                pcolor.Yellow(f'{marker} {line_no:4}: {rendered.splitlines()[line_no - 1]}')
            raise
        if type(api_body) != dict:
            policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
            pcolor.Red(f'!!! ERROR !!! {policy_title} template did not render to a dictionary payload.')
            len(False); sys.exit(1)
        return api_body

    #=========================================================================
    # Function - Check if System Sub Attributes Exist Already
    #=========================================================================
    def existing_check(self, reconcile_resources, kwargs):
        kwargs.cp = DotMap()

        def register_cp_name(resource_type, name):
            if not kwargs.cp.get(resource_type):
                kwargs.cp[resource_type] = DotMap(names=[], category='system')
            if name not in kwargs.cp[resource_type].names:
                kwargs.cp[resource_type].names.append(name)

        for item in reconcile_resources:
            if self.type == 'organizations' and isinstance(item.get('resource_groups'), list):
                for rg in item.resource_groups:
                    register_cp_name('resource_groups', rg)
            elif self.type == 'resource_groups' and isinstance(item.get('resources'), dict):
                if isinstance(item.resources.get('targets'), list):
                    for target in item.resources['targets']:
                        register_cp_name('targets', target)
                if isinstance(item.resources.get('sub_targets'), dict):
                    for e in ['blades', 'rackmounts']:
                        if isinstance(item.resources['sub_targets'].get(e), list):
                            for target in item.resources['sub_targets'][e]:
                                register_cp_name(e, target)
        return reconcile_resources, kwargs

    #=========================================================================
    # Function - Get Organizations from Intersight
    #=========================================================================
    def organizations(self, kwargs):
        kwargs.bulk_list = []
        okeys = list(kwargs.org_moids)
        names = []
        #=====================================================================
        # Function to Create Resource Groups and Organizations
        #=====================================================================
        def compare_to_api(api_body, kwargs):
            check_count = False
            obj_id      = api_body['SharedResource']['Moid']
            org         = kwargs.org_names[api_body['SharedWithResource']['Moid']]
            shared_org  = kwargs.org_names[api_body['SharedResource']['Moid']]
            for k, v in kwargs.intersight_api.system.iam_sharing_rules.items():
                if v.result.SharedResource.Moid == api_body['SharedResource']['Moid'] and v.result.SharedWithResource.Moid == api_body['SharedWithResource']['Moid']:
                    pcolor.Cyan(f"     * Skipping System -> IAM Sharing Rule: Moid - `{k}`.  Intersight Matches Configuration. Shared Resource: `{shared_org}` -> Shared With: `{org}`")
                    check_count = True
                    break
            if check_count == False:
                if check_flag:
                    shared_org = kwargs.org_names[api_body['SharedResource']['Moid']]
                    org = kwargs.org_names[api_body['SharedWithResource']['Moid']]
                    pcolor.Cyan(f"     * Running Check Mode: Non-Check mode would create new System -> IAM Sharing Rule: Shared Resource: `{shared_org}` -> Shared With: `{org}`.")
                else: kwargs.bulk_list.append(deepcopy(api_body))
            return kwargs
        #=====================================================================
        # Function Determine if there are Shared Orgs
        #=====================================================================
        for e in kwargs.resources:
            ekeys = list(e.keys())
            if 'organizations_to_share_with' in ekeys:
                names.extend(e['organizations_to_share_with'])
        names = list(numpy.unique(numpy.array(names)))
        #=====================================================================
        # Function Loop over Shared Orgs if they are defined.
        #=====================================================================
        if len(names) > 0:
            kwargs = kwargs | DotMap(names = names, method = 'get', uri = 'organization/Organizations')
            kwargs = self.api_get(empty=False, names=names, kwargs=kwargs)
            odict  = kwargs.intersight_api.system.organizations
            names  = [odict.get(e.name).moid for e in kwargs.resources if e.get('organizations_to_share_with') is not None and len(e.organizations_to_share_with) > 0]
            kwargs = system(category=self.category, type='iam_sharing_rules').api_get(empty=False, names=names, kwargs=kwargs)
            for item in kwargs.resources:
                for e in item.organizations_to_share_with:
                    i = DotMap(name = item.name, shared_with = e)
                    api_body   = system(category=self.category, type='iam_sharing_rules').create_api_body(i, kwargs)
                    check_flag = getattr(kwargs.args, 'check', False)
                    ikeys = list(kwargs.intersight_api.system.iam_sharing_rules)
                    if len(ikeys) > 0: kwargs = compare_to_api(api_body, kwargs)
        #=====================================================================
        # POST Bulk Request if List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = 'iam/SharingRules'
            kwargs     = configure(category = self.category, type=self.type).create_bulk_request(kwargs)
        return kwargs

    #=========================================================================
    # Function - Intersight API Update -> System -> Path Tags
    #=========================================================================
    def path_tags(self, rdict, kwargs):
        names  = list(e.path_tag for e in rdict)
        uri    = kwargs.ezdata[f'intersight.system.{self.type}'].intersight_uri
        kwargs = kwargs | DotMap(method = 'get', names = names, uri = uri)
        kwargs = api(category=self.category, type=self.type).calls(kwargs)
        for item in rdict:
            if not item.path_tag in (kwargs.intersight_api.system.path_tags):
                np = ''; ns = ''
                api_body = self.create_api_body(item, np, ns, kwargs)
                kwargs = kwargs | DotMap(method = 'post', api_body = api_body, uri = uri)
                kwargs = api(category = self.category, type = self.type).calls(kwargs)
            else:
                moid = kwargs.intersight_api.system.path_tags[item.path_tag].moid
                pcolor.Cyan(f"     * Skipping System; Path Tags: `{item.path_tag}` - Moid: `{moid}`.  Intersight Matches Configuration.")
            names.remove(item.path_tag)
        return kwargs

    #=========================================================================
    # Function - Get Resource Group Sub Elements
    #=========================================================================
    def resource_groups(self, item, kwargs):
        ikeys = list(item.keys())
        if 'resources' in ikeys:
            item.selectors = []
            rkeys = list(item.resources.keys())
            if 'targets' in rkeys and len(item.resources.targets) > 0:
                targets = [kwargs.intersight_api.system.targets[e].moid for e in item.resources.targets]
                if len(targets) == 1:
                    item.selectors.append(f"/api/v1/asset/DeviceRegistrations?$filter=Moid in ('{targets[0]}')")
                else:
                    moid_list = "', '".join(targets)
                    item.selectors.append(f"/api/v1/asset/DeviceRegistrations?$filter=(Moid in ('{moid_list}'))")
            if 'sub_targets' in rkeys:
                for e in ['blades', 'rackmounts']:
                    if e in item.resources.sub_targets and len(item.resources.sub_targets[e]) > 0:
                        sub_targets = [kwargs.intersight_api.system[e][t].moid for t in item.resources.sub_targets[e]]
                        if e == 'blades': stype = 'Blades'
                        else: stype = 'RackUnits'
                        moid_list = "', '".join(sub_targets)
                        item.selectors.append(f"/api/v1/compute/{stype}?$filter=Serial in ('{moid_list}')")
        return item

    #=========================================================================
    # Function - Compare Intersight API to IMM Dictionary `system`
    #=========================================================================
    def system(self, kwargs):
        #=====================================================================
        # Send Begin Notification and Load Variables
        #=====================================================================
        ptitle = validating.mod_pol_description(self.type.replace('_', ' ').title())
        validating.section_begin(self.category, self.type)
        pcolor.LightGray('')
        kwargs.idata = DotMap(dict(pair for d in kwargs.ezdata[f"intersight.{self.category}.{self.type}"].allOf for pair in d.properties.items()))
        rdict = deepcopy(kwargs.imm_dict[self.category][self.type])
        if self.type == 'path_tags':
            kwargs = self.path_tags(rdict, kwargs)
            validating.section_end(self.category, self.type)
            return kwargs
        else: reconcile_resources = list({v.name:v for v in rdict}.values())
        #=====================================================================
        # Get Existing Resources
        #=====================================================================
        names  = list(e.name for e in rdict)
        uri    = kwargs.ezdata[f"intersight.{self.category}.{self.type}"].intersight_uri
        kwargs = api(category=self.category, type=self.type).calls(kwargs | DotMap(method = 'get', names = names, uri = uri))
        #=====================================================================
        # Validate the Sub Resources are defined or get Moids
        #=====================================================================
        if re.search(r'organizations|resource_groups', self.type):
            reconcile_resources, kwargs = self.existing_check(reconcile_resources, kwargs)
            for e in list(kwargs.cp.keys()):
                if len(kwargs.cp[e].names) > 0:
                    names  = list(numpy.unique(numpy.array(kwargs.cp[e].names)))
                    category = kwargs.cp[e].get('category', self.category)
                    kwargs = system(category=category, type=e).api_get(empty=False, names=names, kwargs=kwargs)
        #=====================================================================
        # If Modified, Patch the Resource via the Intersight API
        #=====================================================================
        def compare_resources_to_api(api_body, ptitle, kwargs):
            category   = self.category.replace('_', ' ').title()
            kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.{self.type}"].intersight_uri
            check_flag = getattr(kwargs.args, 'check', False)
            akeys      = list(api_body.keys())
            if 'Description' in akeys and api_body['Description'] == '':
                api_body['Description'] = f"{api_body['Name']} {re.sub(r's$', '', ptitle)}."
            if api_body['Name'] in kwargs.intersight_api[self.category][self.type]:
                intersight_api = kwargs.intersight_api[self.category][self.type][api_body['Name']]
                patch_resource = configure(self.type).compare_body_result(api_body, intersight_api.result)
                api_body['pmoid'] = intersight_api.moid
                if patch_resource == True:
                    if check_flag == True:
                        pcolor.Cyan(f"     * Running Check Mode: Non-Check mode would update {category} -> {ptitle}: `{api_body['Name']}`."\
                                    f"  Moid: `{api_body['pmoid']}`")
                    else:
                        kwargs.bulk_list.append(deepcopy(api_body))
                        kwargs.pmoids[api_body['Name']].moid = api_body['pmoid']
                else: pcolor.Cyan(f"     * Skipping {category} -> {ptitle}: `{api_body['Name']}` - Moid: `{api_body['pmoid']}`.  Intersight Matches Configuration.")
            else:
                if check_flag == True:
                    pcolor.Cyan(f"     * Running Check Mode: Non-Check mode would create new {category} -> {ptitle}: `{api_body['Name']}`.")
                else: kwargs.bulk_list.append(deepcopy(api_body))
            return kwargs
        #=====================================================================
        # Loop through Resource Items
        #=====================================================================
        kwargs.bulk_list = []
        for item in reconcile_resources:
            #=============================================================
            # Construct api_body Payload
            #=============================================================
            api_body = self.create_api_body(item, kwargs)
            kwargs   = compare_resources_to_api(api_body, ptitle, kwargs)
        #=====================================================================
        # POST Bulk Request if List > 0
        #=====================================================================
        if len(kwargs.bulk_list) > 0:
            kwargs.uri = kwargs.ezdata[f"intersight.{self.category}.{self.type}"].intersight_uri
            kwargs     = configure(category = self.category, type=self.type).create_bulk_request(kwargs)
        #=====================================================================
        # Loop Thru Sub-Items
        #=====================================================================
        kwargs.resources = reconcile_resources
        if self.type == 'organizations':
            kwargs = getattr(self, 'organizations')(kwargs)
        #=====================================================================
        # Send End Notification and return kwargs
        #=====================================================================
        validating.section_end(self.category, self.type)
        return kwargs

#=============================================================================
# Software Repository Class
#=============================================================================
class system_software_repository(object):
    def __init__(self, type, category=None):
        self.type = type
        self.category = category

    #=========================================================================
    # Function - OS Configuration Files
    #=========================================================================
    def os_configuration_files(self, kwargs):
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
    # Function - Build Azure Stack HCI Operating System Auto Install File
    #=========================================================================
    def os_configuration_files_azure_stack(self, kwargs):
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
    # Function - OS Image Links
    #=========================================================================
    def os_image_links(self, kwargs):
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
    # Function - Build OS Install API Body
    #=========================================================================
    def os_install(self, kwargs):
        #=====================================================================
        # Load Variables and Send Begin Notification
        #=====================================================================
        validating.section_begin_org(kwargs.org, self.type, 'Install')
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
            kwargs = system_software_repository('os_cfg').os_configuration_files(kwargs)
            kwargs = system_software_repository('scu').scu_links(kwargs)
            for e in kwargs.os_cfg_results: kwargs.os_cfg_moids[e.Moid] = e
            for e in kwargs.scu_results: kwargs.scu[e.Moid] = e
        #=====================================================================
        # Deployment Type Customization
        #=====================================================================
        if install_flag == True and kwargs.script_name == 'ezci' and kwargs.args.deployment_type == 'azure_stack':
            kwargs.os_version = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[0].os_version
            # kwargs = sensitive_list_check(['azure_stack_lcm_password', 'local_administrator_password'], kwargs)
            kwargs = sensitive_list_check(['local_administrator_password'], kwargs)
            kwargs = system_software_repository('azure_stack').os_cfg_azure_stack(kwargs)
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
        validating.section_end_org(kwargs.org, self.type, 'Install')
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
    # Function - SCU Links
    #=========================================================================
    def scu_links(self, kwargs):
        # Get Organization Software Repository Catalog
        kwargs = kwargs | DotMap(method = 'get', names = ['user-catalog'], uri = 'softwarerepository/Catalogs')
        kwargs = api('org_catalog').calls(kwargs)
        catalog_moid = kwargs.pmoids['user-catalog'].moid
        # Get Organization Software Configuration Utility Repositories
        kwargs = kwargs | DotMap(api_filter = f"Catalog.Moid eq '{catalog_moid}'", names = [], uri = 'firmware/ServerConfigurationUtilityDistributables')
        kwargs = api('server_configuration_utility').calls(kwargs)
        kwargs.scu_results = sorted(kwargs.results, key=itemgetter('CreateTime'), reverse=True)
        return kwargs
