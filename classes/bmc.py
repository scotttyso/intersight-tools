#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, pcolor, isight, validating
    from copy import deepcopy
    from dotmap import DotMap
    import inspect, json, os, re, requests, socket, time, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Global options for debugging
print_payload = False
print_response_always = True
print_response_on_fail = True

# Log levels 0 = None, 1 = Class only, 2 = Line
log_level = 2

# Exception Classes
class InsufficientArgs(Exception): pass
class ErrException(Exception): pass
class InvalidArg(Exception): pass
class LoginFailed(Exception): pass

# Class must be instantiated with Variables
class api(object):
    def __init__(self, type):
        self.type = type
    #=====================================================
    # Function - API Authentication
    #=====================================================
    def auth(kwargs):
        url      = f"https://{kwargs.hostname}"
        username = kwargs.username
        password = kwargs.password
        #kwargs.sensitive_var = 'ucs_password'
        #kwargs = ezfunctions.sensitive_var_value(kwargs)
        s = requests.Session()
        s.auth = (username, password)
        auth = ''
        while auth == '':
            try: auth = s.post(url, verify=False)
            except requests.exceptions.ConnectionError as e:
                pcolor.Red("Connection error, pausing before retrying. Error: %s" % (e))
                time.sleep(5)
            except Exception as e:
                pcolor.Red(f'{url}')
                pcolor.Red(f"!!! ERROR !!! Method {(inspect.currentframe().f_code.co_name).upper()} Failed. Exception: {e}\n")
                len(False); sys.exit(1)
        return s, url

    #=====================================================
    # UCS - Device Connector - HTTP Proxy
    #=====================================================
    def device_connector_proxy(self, kwargs):
        #=====================================================
        # Patch the Management Interface
        #=====================================================
        kwargs = kwargs | DotMap(
            clist = ['AuthenticationEnabled', 'HostProperties', 'ProxyHost', 'ProxyPassword', 'ProxyPort', 'ProxyType', 'ProxyUsername'],
            method = 'put', uri = 'connector/HttpProxies',
            payload = {"AuthenticationEnabled": False,
            "HostProperties": {"ProxyHost": kwargs.item.proxy_settings.proxy_hostname, "ProxyPort": kwargs.item.proxy_settings.proxy_port},
            "ProxyHost": kwargs.item.proxy_settings.proxy_hostname, "ProxyPassword": "",
            "ProxyPort": kwargs.item.proxy_settings.proxy_port, "ProxyType": "Manual", "ProxyUsername": ""}
        )
        pkeys = kwargs.item.proxy_settings.toDict().keys()
        if 'proxy_username' in pkeys:
            kwargs.payload['AuthenticationEnabled'] = True
            kwargs.payload['ProxyUsername'] = kwargs.item.proxy_settings.proxy_username
            kwargs.payload['ProxyPassword'] = kwargs.item.proxy_settings.proxy_password
        api(inspect.currentframe().f_code.co_name).run_api_commands(kwargs.item, kwargs)
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs

    #=====================================================
    # UCS - Device Connector - Registration
    #=====================================================
    def device_connector_registration(self, kwargs):
        #=====================================================
        # Load Variables and Send Begin Notification
        #=====================================================
        #kwargs.uri = '/connector/DeviceConfigurations'
        #dcdata = api.get(kwargs)
        validating.begin_section('ucs', self.type)
        kwargs.uri = '/connector/Systems'
        sys_data = api.get(kwargs)
        if sys_data[0]['AccountOwnershipState'] != 'Claimed':
            kwargs.uri = '/connector/DeviceIdentifiers'
            id         = api.get(kwargs)
            valid_time = 0
            while valid_time < 60:
                kwargs.uri = '/connector/SecurityTokens'
                token      = api.get(kwargs)
                if token[0]['Duration'] >= 60: valid_time = token[0]['Duration']
                else:
                    pcolor.Cyan(f"     * Waiting for Security Token to be valid for at least 60 seconds.")
                    pcolor.Cyan(f"     * Current Security Token Duration: {token[0]['Duration']} seconds")
                    time.sleep(60); valid_time = token[0]['Duration']
            pcolor.Cyan(f"     * {kwargs.item.hostname} is not Claimed, claiming in Intersight Now.")
            kwargs.org = kwargs.ucs_dict.shared_settings.intersight.organization
            kwargs = kwargs | DotMap(api_body = {'SecurityToken': token[0]['Token'], 'SerialNumber': id[0]['Id']}, method = 'post', uri = 'asset/DeviceClaims')
            kwargs = isight.api('device_claim').calls(kwargs)
        else: pcolor.Cyan(f"     * {kwargs.item.hostname} is already claimed in Intersight.")
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs

    #=====================================================
    # Function - API - GET
    #=====================================================
    def get(kwargs):
        s, url = api.auth(kwargs)
        r = ''
        while r == '':
            try:
                pcolor.Cyan(f"     * get: {f'{url}{kwargs.uri}'}")
                r = s.get(f'{url}{kwargs.uri}', verify=False)
                if print_response_always: pcolor.Purple(f"     * get: {r.status_code} success with {kwargs.uri}")
                if r.status_code == 200 or r.status_code == 404: return r.json()
                else: validating.error_requests('get', r.status_code, r.text, kwargs.uri)
            except requests.exceptions.ConnectionError as e:
                pcolor.Red("Connection error, pausing before retrying. Error: %s" % (e))
                time.sleep(5)
            except Exception as e:
                pcolor.Red(f'{url}/api/{kwargs.uri}')
                pcolor.Red(f"!!! ERROR !!! Method {(inspect.currentframe().f_code.co_name).upper()} Failed. Exception: {e}")
                len(False); sys.exit(1)

    #=====================================================
    # UCS - BMC Managers - Ethernet Interfaces
    #=====================================================
    def managers_ethernet_interfaces(self, kwargs):
        #=====================================================
        # Patch the Management Interface
        #=====================================================
        kwargs = kwargs | DotMap(
            clist = ['DHCPv4', 'DomainName', 'HostName', 'IPv4StaticAddresses', 'StaticNameServers'],
            method = 'patch',
            payload = {
                "DHCPv4": {"DHCPEnabled": False, "UseDNSServers": True, "UseDomainName": True, "UseNTPServers": True},
                "DomainName": kwargs.item.domain_name,
                "HostName": kwargs.item.hostname,
                "IPv4StaticAddresses": [
                    {"Address": kwargs.item.ipv4_address, "Gateway": kwargs.item.ipv4.gateway, "SubnetMask": kwargs.item.ipv4.netmask}
                ],
                "StaticNameServers": kwargs.item.dns_servers,
            },
            uri = '/redfish/v1/Managers/bmc/EthernetInterfaces/eth0'
        )
        kwargs = api(inspect.currentframe().f_code.co_name).run_api_commands(kwargs)
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs

    #=====================================================
    # UCS - BMC Managers - Network Protocols - NTP
    #=====================================================
    def managers_network_protocols(self, kwargs):
        #=====================================================
        # Patch the Management Interface
        #=====================================================
        kwargs = kwargs | DotMap(
            clist = ['NTP'],
            method = 'patch',
            payload = {"NTP": {"NTPServers": kwargs.item.ntp_servers, "ProtocolEnabled": True}},
            uri = '/redfish/v1/Managers/bmc/NetworkProtocol'
        )
        api(inspect.currentframe().f_code.co_name).run_api_commands(kwargs.item, kwargs)
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs

    #=====================================================
    # UCS - BMC Managers - Timezone
    #=====================================================
    def managers_timezone(self, kwargs):
        #=====================================================
        # Patch the Management Interface
        #=====================================================
        kwargs = kwargs | DotMap(
            clist = ['TimeZoneName'],
            method = 'patch',
            payload = {"TimeZoneName": kwargs.item.timezone},
            uri = '/redfish/v1/Managers/bmc'
        )
        api(inspect.currentframe().f_code.co_name).run_api_commands(kwargs.item, kwargs)
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs

    #=====================================================
    # Function - API - PATCH
    #=====================================================
    def patch(kwargs):
        s, url = api.auth(kwargs)
        r = ''
        while r == '':
            try:
                pcolor.Cyan(f"     * patch: {f'{url}{kwargs.uri}'}")
                r = s.patch(f'{url}{kwargs.uri}', json=kwargs.payload, verify=False)
                # Use this for Troubleshooting
                if not re.search('20[0-4]', str(r.status_code)):
                    validating.error_requests('patch', r.status_code, r.text, kwargs.uri)
                if print_response_always:
                    pcolor.Purple(f"     * patch: {r.status_code} success with {kwargs.uri}")
                if r.status_code == 204: return {}
                elif len(r.text) == 0: return {}
                else:  return r.json()
            except requests.exceptions.ConnectionError as e:
                pcolor.Red(f"Connection error, pausing before retrying. Error: {e}")
                time.sleep(5)
            except Exception as e:
                pcolor.Red(f'{url}/{kwargs.uri}')
                pcolor.Red(f"!!! ERROR !!! Method {(inspect.currentframe().f_code.co_name).upper()} Failed. Exception: {e}\n")
                print(e)
                len(False); sys.exit(1)

    #=====================================================
    # Function - API - POST
    #=====================================================
    def post(kwargs):
        s, url = api.auth(kwargs)
        r = ''
        while r == '':
            try:
                pcolor.Cyan(f"     * post: {f'{url}{kwargs.uri}'}")
                r = s.post(f'{url}{kwargs.uri}', data=kwargs.payload, verify=False)
                # Use this for Troubleshooting
                if not re.search('20[0-4]', str(r.status_code)):
                    validating.error_requests('post', r.status_code, r.text, kwargs.uri)
                if print_response_always:
                    pcolor.Green(f"     * post: {r.status_code} success with {kwargs.uri}")
                return r.json()
            except requests.exceptions.ConnectionError as e:
                pcolor.Red(f"Connection error, pausing before retrying. Error: {e}")
                time.sleep(5)
            except Exception as e:
                pcolor.Red(f'{url}/{kwargs.uri}')
                pcolor.Red(f"!!! ERROR !!! Method {(inspect.currentframe().f_code.co_name).upper()} Failed. Exception: {e}\n")
                len(False); sys.exit(1)

    #=====================================================
    # Function - API - PUT
    #=====================================================
    def put(kwargs):
        s, url = api.auth(kwargs)
        r = ''
        while r == '':
            try:
                pcolor.Cyan(f"     * put: {f'{url}{kwargs.uri}'}")
                r = s.put(f'{url}{kwargs.uri}', json=kwargs.payload, verify=False)
                # Use this for Troubleshooting
                if not re.search('20[0-4]', str(r.status_code)):
                    validating.error_requests('put', r.status_code, r.text, kwargs.uri)
                if print_response_always:
                    pcolor.Purple(f"     * put: {r.status_code} success with {kwargs.uri}")
                if r.status_code == 204: return {}
                else: return r.json()
            except requests.exceptions.ConnectionError as e:
                pcolor.Red(f"Connection error, pausing before retrying. Error: {e}")
                time.sleep(5)
            except Exception as e:
                pcolor.Red(f'{url}/{kwargs.uri}')
                pcolor.Red(f"!!! ERROR !!! Method {(inspect.currentframe().f_code.co_name).upper()} Failed. Exception: {e}\n")
                print(e)
                len(False); sys.exit(1)

    #=====================================================
    # Function - Reboot the System
    #=====================================================
    def reboot_system(kwargs):
            kwargs = kwargs | DotMap(
                method = 'post',
                payload = {"ResetType": "GracefulRestart"},
                uri = '/redfish/v1/Systems/system/Actions/ComputerSystem.Reset'
            )
            rdata = api.post(kwargs)
            if print_response_always: pcolor.Purple(f"     * post: {rdata} success with {kwargs.uri}")
            if print_response_on_fail and rdata.get('error', None):
                pcolor.Red(f"!!! ERROR !!! Method {kwargs.method.upper()} Failed. Exception: {rdata.get('error', {}).get('message', 'Unknown Error')}")
                len(False); sys.exit(1)
            pcolor.Cyan(f"     * Rebooting {kwargs.item.hostname} to apply Changes.")

    #=====================================================
    # UCS - System - BIOS
    #=====================================================
    def system_bios(self, kwargs):
        #=================================================
        # Load Variables and Send Begin Notification
        #=================================================
        validating.begin_section('ucs', self.type)
        kwargs = kwargs | DotMap(
            clist = list(kwargs.item.bios.toDict().keys()),
            method = 'get',
            payload = {'Attributes': kwargs.item.bios.toDict()},
            uri = '/redfish/v1/Systems/system/Bios'
        )
        #=================================================
        # Get existing BIOS Settings
        #=================================================
        rdata = api.get(kwargs)
        bkeys = kwargs.clist
        rkeys = rdata['Attributes'].keys()
        cdata = {'Attributes': {}}
        for e in bkeys:
            if e in rkeys: cdata['Attributes'][e] = rdata['Attributes'][e]
        if not cdata == kwargs.payload:
            pcolor.Cyan(f"     * BIOS Settings on {kwargs.item.hostname} do not match")
            pcolor.Green(f"     * Configuring BIOS Settings on {kwargs.item.hostname}")
            if print_payload: pcolor.Cyan(json.dumps(kwargs.payload, indent=4))
            #=====================================================
            # Patch the System - BIOS
            #=====================================================
            kwargs.uri = '/redfish/v1/Systems/system/Bios/Settings'
            rdata      = api.patch(kwargs)
            serial     = kwargs.item.serial_number
            kwargs.servers[serial] = kwargs.servers[serial] | DotMap(bios = kwargs.payload, check_bios = True, reboot_required = True)
            #=====================================================
            # Get the System BIOS to verify the patch
            #=====================================================
            kwargs.uri = '/redfish/v1/Systems/system/Bios'
            rdata      = api.get(kwargs)
            question   = 'y'
            compare_data = {'Attributes': {}}
            rkeys = rdata['Attributes'].keys()
            for e in bkeys:
                if e in rkeys:
                    compare_data['Attributes'][e] = rdata['Attributes'][e]
            if not compare_data == kwargs.payload:
                pcolor.Red(f"!!! ERROR !!! does not match after patching")
                pcolor.Red(f"* Expected:")
                pcolor.Green(json.dumps(kwargs.payload, indent=4))
                pcolor.Red(f"* Received:")
                pcolor.Yellow(json.dumps(compare_data, indent=4))
                pcolor.Cyan(f"\nCompare the outputs above to determine if there is an issue.")
                pcolor.Cyan(f"If you are okay with the comparisons, you can continue by answering 'Y' to the next question.")
                question = input(f"  Do you want to continue? [Y/N]: ").strip().lower()
            if question not in ['y', 'yes']:
                pcolor.Red(f"!!! ERROR !!! Configuration failed for {kwargs.item.hostname}")
                len(False); sys.exit(1)
        else: pcolor.Cyan(f"     * BIOS Settings on {kwargs.item.hostname} are already configured")
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs

    #=====================================================
    # UCS - System - Boot Order
    #=====================================================
    def system_boot_order(self, kwargs):
        #=================================================
        # Get Network Adapters
        #=================================================
        adapters   = DotMap()
        kwargs.uri = '/redfish/v1/Chassis/chassis/NetworkAdapters'
        rdata = api.get(kwargs)
        for e in rdata['Members']:
            kwargs.uri = e['@odata.id']
            if re.search('FHHL', kwargs.uri):
                edata = api.get(kwargs)
                for i in edata['Controllers']:
                    kwargs.uri = i['Links']['NetworkPorts'][0]['@odata.id']
                    idata = api.get(kwargs)
                    adapters[idata['AssociatedNetworkAddresses'][0]] = DotMap(Parent = edata['Id'], Id = idata['Id'], Model = edata['Model'])
        mac_list = list(adapters.keys())
        #=================================================
        # Get Boot Options
        #=================================================
        kwargs.uri = '/redfish/v1/Systems/system/BootOptions'
        rdata      = api.get(kwargs)
        boot_options = []
        for e in rdata['Members']:
            kwargs.uri = e['@odata.id']
            rdata      = api.get(kwargs)
            boot_options.append(rdata)
        names = []
        for e in boot_options:
            e = DotMap(e)
            if re.search('Hdd|UefiShell', e.Alias): names.append(f"{e.Name}: {e.Alias} - {e.DisplayName}")
            elif re.search('Pxe|UefiHttp', e.Alias):
                for m in mac_list:
                    if re.search(m, e.DisplayName):
                        names.append(f"{e.Name}: {e.Alias} - ({adapters[m].Model} - {adapters[m].Parent} - {adapters[m].Id} - {m})")
        #=================================================
        # Prompt User for Boot Options
        #=================================================
        kwargs.jdata = DotMap(
            default      = names[0],
            enum         = names,
            description  = 'Enter the Number for each Boot Option in the order you want for the boot policy.',
            keep_order   = True,
            multi_select = True,
            title        = 'Boot Options',
            type         = 'string'
        )
        boot_order = ezfunctions.variable_prompt(kwargs)
        #=================================================
        # Compare Boot Order with Desired Boot Order
        #=================================================
        selection = []
        for e in kwargs.selection_list:
            selection.append(names[int(e) - 1])
        kwargs = kwargs | DotMap(
            clist   = ['BootOrder', 'BootMode'],
            method  = 'get',
            payload = {'Boot': {"BootOrder": selection}},
            uri     = '/redfish/v1/Systems/system'
        )
        rdata = api.get(kwargs)
        cdata = {'Boot': {'BootOrder': rdata['Boot']['BootOrder']}}
        if not cdata == kwargs.payload:
            kwargs.method  = 'patch'
            pcolor.Green(f"     * Configuring {(' '.join((self.type).split('_'))).title()} on {kwargs.item.hostname}")
            if print_payload: pcolor.Cyan(json.dumps(kwargs.payload, indent=4))
            rdata  = eval(f"api.{kwargs.method}(kwargs)")
            serial = kwargs.item.serial_number
            kwargs.servers[serial] = kwargs.servers[serial] | DotMap(boot_order = kwargs.payload, check_boot_order = True, reboot_required = True)
        else: pcolor.Cyan(f"     * {(' '.join((self.type).split('_'))).title()} on {kwargs.item.hostname} is already configured")
        #=================================================
        # return kwargs
        #=================================================
        return kwargs

    #=====================================================
    # UCS - System - Power Restore
    #=====================================================
    def system_power_restore(self, kwargs):
        #=====================================================
        # Patch the Management Interface
        #=====================================================
        kwargs = kwargs | DotMap(
            clist = ['PowerRestorePolicy'],
            method = 'patch',
            payload = {"PowerRestorePolicy": 'LastState'},
            uri = '/redfish/v1/Systems/system'
        )
        api(inspect.currentframe().f_code.co_name).run_api_commands(kwargs.item, kwargs)
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs

    #=====================================================
    # UCS - Compare API Data - Patch if Necessary
    #=====================================================
    def run_api_commands(self, kwargs):
        #=================================================
        # Modify the rdata for comparison
        #=================================================
        def modify_rdata(rdata, kwargs):
            compare_result = False
            compare_data = {}
            if self.type == 'device_connector_proxy':
                rdata = deepcopy(rdata[0])
                rkeys = rdata.keys()
                if 'ProxyUsername' in rkeys and len(rdata['ProxyUsername']) > 0:
                    rdata.update({'AuthenticationEnabled': True})
                else:
                    rdata.update({'AuthenticationEnabled': False})
                    rdata.update({'ProxyUsername': ''})
                for e in kwargs.clist:
                    if not e in ['HostProperties', 'ProxyPassword']: compare_data.update({e: rdata[e]})
                compare_data['HostProperties'] = rdata['Targets'][0]
                compare_data['HostProperties'].pop('Preference')
                compare_data['ProxyPassword']  = kwargs.payload['ProxyPassword']
                compare_data = dict(sorted(compare_data.kwargs.items()))
            else:
                for e in kwargs.clist:
                    compare_data.update({e: rdata[e]})
                ckeys = compare_data.keys()
                if 'IPv4StaticAddresses' in ckeys:
                    for i in range(0,len(compare_data['IPv4StaticAddresses'])):
                        compare_data['IPv4StaticAddresses'][i].pop('AddressOrigin')
            if compare_data == kwargs.payload: compare_result = True
            return compare_data, compare_result
        #=================================================
        # Load Variables and Send Begin Notification
        #=================================================
        validating.begin_section('ucs', self.type)
        rdata = api.get(kwargs)
        compare_data, compare_result = modify_rdata(rdata, kwargs)
        if compare_result == False:
            print(kwargs.payload)
            print(compare_data)
            exit()
            pcolor.Green(f"     * Configuring {(' '.join((self.type).split('_'))).title()} on {kwargs.item.hostname}")
            if print_payload: pcolor.Cyan(json.dumps(kwargs.payload, indent=4))
            rdata = eval(f"api.{kwargs.method}(kwargs)")
            if self.type == 'managers_ethernet_interfaces' and kwargs.item.api != kwargs.item.ipv4_address:
                kwargs.hostname = kwargs.item.ipv4_address
                pcolor.Cyan(f"     * IP Address changed for `{kwargs.item.hostname}`, sleeping for 90 seconds to allow the change to take effect.")
                time.sleep(90)
            rdata = api.get(kwargs)
            compare_data, compare_result = modify_rdata(rdata, kwargs)
            question = 'y'
            if compare_result == False:
                pcolor.Red(f"!!! ERROR !!! does not match after patching")
                pcolor.Red(f"* Expected:")
                pcolor.Green(json.dumps(kwargs.payload, indent=4))
                pcolor.Red(f"* Received:")
                pcolor.Yellow(json.dumps(compare_data, indent=4))
                pcolor.Cyan(f"\nCompare the outputs above to determine if there is an issue.")
                pcolor.Cyan(f"If you are okay with the comparisons, you can continue by answering 'Y' to the next question.")
                question = input(f"  Do you want to continue? [Y/N]: ").strip().lower()
            if question not in ['y', 'yes']:
                pcolor.Red(f"!!! ERROR !!! Configuration failed for {kwargs.item.hostname}")
                len(False); sys.exit(1)
        else: pcolor.Cyan(f"     * {(' '.join((self.type).split('_'))).title()} on {kwargs.item.hostname} is already configured")
        #=================================================
        # Send End Notification and return kwargs
        #=================================================
        validating.end_section('ucs', self.type)
        return kwargs

    #=====================================================
    # UCS - Validate - BIOS
    #=====================================================
    def validate_bios(self, kwargs):
        #=================================================
        # Load Variables and Send Begin Notification
        #=================================================
        validating.begin_section('ucs', self.type)
        kwargs = kwargs | DotMap(
            method = 'get',
            payload = kwargs.item.bios.toDict(),
            uri = '/redfish/v1/Systems/system/Bios'
        )
        #=================================================
        # Get existing BIOS Settings
        #=================================================
        rdata = api.get(kwargs)
        bkeys = kwargs.item.bios.toDict().keys()
        rkeys = rdata['Attributes'].keys()
        cdata = {'Attributes': {}}
        for e in bkeys:
            if e in rkeys: cdata['Attributes'][e] = rdata['Attributes'][e]
        question   = 'y'
        if not cdata == kwargs.payload:
            pcolor.Red(f"!!! ERROR !!! does not match after patching")
            pcolor.Red(f"* Expected:")
            pcolor.Green(json.dumps(kwargs.payload, indent=4))
            pcolor.Red(f"* Received:")
            pcolor.Yellow(json.dumps(cdata, indent=4))
            pcolor.Cyan(f"\nCompare the outputs above to determine if there is an issue.")
            pcolor.Cyan(f"If you are okay with the comparisons, you can continue by answering 'Y' to the next question.")
            question = input(f"  Do you want to continue? [Y/N]: ").strip().lower()
            if question not in ['y', 'yes']:
                pcolor.Red(f"!!! ERROR !!! BIOS Configuration failed for {kwargs.item.hostname}")
                len(False); sys.exit(1)
        else: pcolor.Cyan(f"     * BIOS Settings on {kwargs.item.hostname} are already configured")
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs

    #=====================================================
    # UCS - Validate - Boot Order
    #=====================================================
    def validate_boot_order(self, kwargs):
        #=================================================
        # Load Variables and Send Begin Notification
        #=================================================
        validating.begin_section('ucs', self.type)
        kwargs = kwargs | DotMap(
            method = 'get',
            payload = kwargs.item.boot_order.toDict(),
            uri = '/redfish/v1/Systems/system'
        )
        #=================================================
        # Get existing Boot Order Settings
        #=================================================
        rdata = api.get(kwargs)
        cdata = {'Boot': {'BootOrder': rdata['Boot']['BootOrder']}}
        question   = 'y'
        if not cdata == kwargs.payload:
            pcolor.Red(f"!!! ERROR !!! does not match after patching")
            pcolor.Red(f"* Expected:")
            pcolor.Green(json.dumps(kwargs.payload, indent=4))
            pcolor.Red(f"* Received:")
            pcolor.Yellow(json.dumps(cdata, indent=4))
            pcolor.Cyan(f"\nCompare the outputs above to determine if there is an issue.")
            pcolor.Cyan(f"If you are okay with the comparisons, you can continue by answering 'Y' to the next question.")
            question = input(f"  Do you want to continue? [Y/N]: ").strip().lower()
            if question not in ['y', 'yes']:
                pcolor.Red(f"!!! ERROR !!! Boot Order Configuration failed for {kwargs.item.hostname}")
                len(False); sys.exit(1)
        else: pcolor.Cyan(f"     * Boot Order Settings on {kwargs.item.hostname} are already configured")
        #=====================================================
        # return kwargs
        #=====================================================
        return kwargs


#=========================================================
# Build Storage Class
#=========================================================
class build(object):
    def __init__(self, type):
        self.type = type

    #=====================================================
    # Function - UCS BMC - Nodes
    #=====================================================
    def hosts(self, kwargs):
        kwargs = kwargs | DotMap(username = kwargs.ucs_dict.username, password = kwargs.ucs_dict.password, reboot_required = False)
        for e in kwargs.ucs_dict.hosts:
            kwargs = kwargs | DotMap(hostname = e.api, uri = f'/connector/DeviceIdentifiers')
            id     = api.get(kwargs)
            kwargs.servers[id[0]['Id']] = DotMap(check_bios = False, check_boot_order = False, hostname = e.ipv4_address, reboot_required = False)
            kwargs.item = kwargs.ucs_dict.shared_settings.toDict() | e
            kwargs.item.serial_number = id[0]['Id']
            api_list = [
                'managers_ethernet_interfaces',
                'managers_network_protocols',
                'managers_timezone',
                'system_power_restore',
                'device_connector_proxy',
                'device_connector_registration',
                'system_boot_order',
                'system_bios'
            ]
            for i in api_list: kwargs = eval(f"api('{i}').{i}(kwargs)")
        #=================================================
        # Add servers to resource group if not default
        #=================================================
        kwargs = build(inspect.currentframe().f_code.co_name).intersight_resource_group(kwargs)
        #=================================================
        # Reboot servers if required
        #=================================================
        reboot_required = False
        for s in list(kwargs.servers.keys()):
            if kwargs.servers[s].reboot_required == True:
                kwargs.hostname = kwargs.servers[s].ipv4_address
                reboot_required = True
                pcolor.Cyan(f"     * {kwargs.servers[s].hostname} requires a reboot to apply changes.")
                api('reboot_system').reboot_system(kwargs)
        if reboot_required == True:
            pcolor.Cyan(f"     * Sleeping for 17 Minutes to Allow Hosts to come back online.")
            time.sleep(1020)  # Wait 17 minutes for the system to reboot and apply Changes.
            for s in list(kwargs.servers.keys()):
                if kwargs.servers[s].reboot_required == True:
                    kwargs.hostname = kwargs.servers[s].ipv4_address
                    pcolor.Cyan(f"     * Rechecking {kwargs.servers[s].hostname} for BIOS and Boot Order Settings.")
                    kwargs = kwargs | DotMap(item = kwargs.servers[s])
                    if kwargs.servers[s].check_bios == True:
                        #=================================================
                        # Validate BIOS Settings
                        #=================================================
                        kwargs = api('validate_bios').validate_bios(kwargs)
                    if kwargs.servers[s].check_boot_order == True:
                        #=================================================
                        # Validate Boot Order Settings
                        #=================================================
                        kwargs = api('validate_boot_order').validate_boot_order(kwargs)
        else: pcolor.Cyan(f"     * No Reboot Required for any Hosts.")
        #=================================================
        # return kwargs
        #=================================================
        return kwargs

    #=====================================================
    # Function - UCS BMC - Nodes
    #=====================================================
    def intersight_resource_group(self, kwargs):
        #=================================================
        # Add servers to resource group if not default
        #=================================================
        if not kwargs.ucs_dict.shared_settings.intersight.resource_group == 'default':
            org     = kwargs.ucs_dict.shared_settings.intersight.organization
            kwargs  = kwargs | DotMap(method = 'get', names = list(kwargs.servers.keys()), org = org, uri = 'compute/PhysicalSummaries')
            kwargs  = isight.api('serial_number').calls(kwargs)
            serials = kwargs.pmoids
            #=============================================
            # Get Intersight Resource Groups
            #=============================================
            resource_group = kwargs.ucs_dict.shared_settings.intersight.resource_group
            kwargs = kwargs | DotMap(api_filter = f"Name in ('{resource_group}')", method = 'get', uri = 'resource/Groups')
            kwargs = isight.api('resource_group').calls(kwargs)
            resource_groups = kwargs.pmoids
            null_selector = False
            if len(resource_groups[resource_group].selectors) > 0 and re.search(r'ParentConnection eq null',  resource_groups[resource_group].selectors[0].Selector):
                null_selector = True
            elif len(resource_groups[resource_group].selectors) > 0 and re.search(r'\(([0-9a-f\'\, ]+)\)', resource_groups[resource_group].selectors[0].Selector):
                device_registrations = re.search(r'\(([0-9a-f\'\, ]+)\)', resource_groups[resource_group].selectors[0].Selector).group(1)
            else: device_registrations = ''
            if null_selector == False:
                update_resource_group = False
                for s in list(kwargs.servers.keys()):
                    if not serials[s].registered_device in device_registrations:
                        update_resource_group = True
                        if len(device_registrations) > 0:
                            appended_targets = device_registrations + "," + f"'{serials[s].registered_device}'"
                        else: appended_targets = f"'{serials[s].registered_device}'"
                if update_resource_group == True:
                    kwargs.api_body = { 'Selectors':[{'ClassId': 'resource.Selector','ObjectType': 'resource.Selector',
                        'Selector': '/api/v1/asset/DeviceRegistrations?$filter=Moid in('f"{appended_targets})"}] }
                    kwargs = kwargs | DotMap(method = 'patch', pmoid = resource_groups[resource_group].moid, uri = 'resource/Groups')
                    kwargs = isight.api('resource_group').calls(kwargs)
        #=================================================
        # return kwargs
        #=================================================
        return kwargs
