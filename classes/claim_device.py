#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import device_connector, ezfunctions, isight, pcolor
    from dotmap import DotMap
    from time import sleep
    import json, numpy, re
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

def claim_targets(kwargs):
    return_code     = 0
    result          = DotMap()
    resource_groups = []
    connected_error = False
    for i in kwargs.yaml.device_list: resource_groups.append(i.resource_group)
    names= "', '".join(numpy.unique(numpy.array(resource_groups))).strip("', '")
    # Get Intersight Resource Groups
    kwargs = kwargs | DotMap(api_filter = f"Name in ('{names}')", method = 'get', uri = 'resource/Groups')
    kwargs = isight.api('resource_group').calls(kwargs)
    resource_groups   = kwargs.pmoids
    # Loop Through Device List
    for i in kwargs.yaml.device_list:
        if len(i.proxy_username) > 0:
            kwargs.sensitive_var  = 'proxy_password'
            kwargs                = ezfunctions.sensitive_var_value(kwargs)
            proxy_password        = kwargs.var_value
        else: proxy_password = ''
        for e in i.devices:
            kwargs.org = i.organization
            device = DotMap(
                device_type    = i.device_type,
                dns_servers    = i.dns_servers,
                hostname       = e,
                password       = kwargs.password,
                proxy_host     = i.proxy_host,
                proxy_password = proxy_password,
                proxy_port     = i.proxy_port,
                proxy_username = i.proxy_username,
                resource_group = i.resource_group,
                script_path    = kwargs.script_path,
                username       = i.username)
            result[device.hostname] = DotMap(changed=False)
            result[device.hostname].msg = f"#Host: {device.hostname}"
            if not i.get('read_only'): device.read_only = False
            
            # create device connector object based on device type
            if re.search("^(imc|ucs|ucsm|ucspe)$", device.device_type):
                # attempt ucs connection
                dc_obj = device_connector.ucs_device_connector(device)
                # if ucs connection doesnt work and device_type is imc revert to older imc login
                if not dc_obj.logged_in and device.device_type == 'imc':
                    dc_obj = device_connector.imc_device_connector(device)
            elif device.device_type == 'hx':
                dc_obj = device_connector.hx_device_connector(device)
            else:
                result[device.hostname].msg += "#Unknown device_type %s" % device.device_type
                return_code = 1
                pcolor.Cyan(json.dumps(result[device.hostname]))
                continue
            
            # Get Management IP Settings (DHCP/Static)
            if device.device_type == 'imc':
                result = dc_obj.management_interface(result)
            if result.get('ApiError'):
                result[device.hostname].msg += f"#{ro_json.ApiError}"
                return_code = 1
                pcolor.Cyan(json.dumps(result[device.hostname]))
                continue

            if not dc_obj.logged_in:
                result[device.hostname].msg += "#Login error"
                return_code = 1
                pcolor.Cyan(json.dumps(result[device.hostname]))
                continue

            ro_json = DotMap(dc_obj.configure_connector())

            if not ro_json.AdminState:
                return_code = 1
                if ro_json.get('ApiError'):
                    result[device.hostname].msg += f"#{ro_json.ApiError}"
                pcolor.Cyan(json.dumps(result[device.hostname]))
                continue

            # set access mode (ReadOnlyMode True/False) to desired state
            if (ro_json.get('ReadOnlyMode') is not None) and (ro_json.ReadOnlyMode != device.read_only):
                ro_json = dc_obj.configure_access_mode(ro_json)
                if ro_json.get('ApiError'):
                    result[device.hostname].msg += f"#{ro_json.ApiError}"
                    return_code = 1
                    pcolor.Cyan(json.dumps(result[device.hostname]))
                    continue
                result[device.hostname].changed = True

            # configure proxy settings (changes reported in called function)
            ro_json = dc_obj.configure_proxy(ro_json, result[device.hostname])
            if ro_json.get('ApiError'):
                result[device.hostname].msg += f"#{ro_json.ApiError}"
                return_code = 1
                pcolor.Cyan(json.dumps(result[device.hostname]))
                continue

            # wait for a connection to establish before checking claim state
            for _ in range(10):
                if ro_json.ConnectionState != 'Connected':
                    if ro_json.ConnectionState == 'DNS Misconfigured': result = dc_obj.configure_dns(result)
                    else: sleep(1); ro_json = dc_obj.get_status()

            result[device.hostname].msg += f"#AdminState: {ro_json.AdminState}"
            result[device.hostname].msg += f"#ConnectionState: {ro_json.ConnectionState}"
            result[device.hostname].msg += f"#Claimed state: {ro_json.AccountOwnershipState}"

            if ro_json.ConnectionState != 'Connected':
                if ('dc_obj' in locals() or 'dc_obj' in globals()): dc_obj.logout()
                connected_error = True
                return_code = 1; continue
            else:
                pcolor.Cyan(ro_json.ConnectionState)
                (claim_resp, device_id, claim_code) = dc_obj.get_claim_info(ro_json)
                result[device.hostname].msg += f"#Id: {device_id}"

            if ro_json.AccountOwnershipState != 'Claimed':
                # attempt to claim
                (claim_resp, device_id, claim_code) = dc_obj.get_claim_info(ro_json)
                if claim_resp.get('ApiError'):
                    result[device.hostname].msg += claim_resp['ApiError']
                    return_code = 1; continue

                result[device.hostname].msg += f"#Id    : {device_id}"
                result[device.hostname].msg += f"#Token : {claim_code}"

                # Post claim_code and device_id
                kwargs   = kwargs | DotMap(api_body = {'SecurityToken': claim_code, 'SerialNumber': device_id}, method = 'post', uri = 'asset/DeviceClaims')
                kwargs   = isight.api('device_claim').calls(kwargs)
                reg_moid = kwargs.results.Moid
                result[device.hostname].reg_moid = reg_moid
                result[device.hostname].changed  = True
                result[device.hostname].serial   = device_id
            else:
                kwargs   = kwargs | DotMap(api_filter = f'contains(Serial,{device_id})', method = 'get', uri = 'asset/DeviceRegistrations')
                kwargs   = isight.api('device_registration').calls(kwargs)
                reg_moid = kwargs.results[0].Moid
                result[device.hostname].reg_moid = reg_moid
                result[device.hostname].changed  = False
                result[device.hostname].serial   = device_id
            if ('dc_obj' in locals() or 'dc_obj' in globals()): dc_obj.logout()
        null_selector = False
        if len(resource_groups[i.resource_group].selectors) > 0 and re.search(r'ParentConnection eq null',  resource_groups[i.resource_group].selectors[0].Selector):
            null_selector = True
        elif len(resource_groups[i.resource_group].selectors) > 0 and re.search(r'\(([0-9a-z\'\,]+)\)', resource_groups[i.resource_group].selectors[0].Selector):
            device_registrations= re.search(r'\(([0-9a-z\'\,]+)\)', resource_groups[i.resource_group].selectors[0].Selector).group(1)
        else: device_registrations= ''
        if null_selector == False:
            update_resource_group = False
            for s in i.devices:
                result[s]['Resource Group'] = i.resource_group
                if not result[s].reg_moid in device_registrations:
                    update_resource_group = True
                    if len(device_registrations) > 0:
                        appended_targets = device_registrations + "," + f"'{result[s].reg_moid}'"
                    else: appended_targets = f"'{result[s].reg_moid}'"
                    result[s]['Resource Updated'] = True
                else: result[s]['Resource Updated'] = False
            if update_resource_group == True:
                kwargs.api_body = { 'Selectors':[{'ClassId': 'resource.Selector','ObjectType': 'resource.Selector',
                    'Selector': '/api/v1/asset/DeviceRegistrations?$filter=Moid in('f"{appended_targets})"}] }
                kwargs = kwargs | DotMap(method = 'patch', pmoid = resource_groups[i.resource_group].moid, uri = 'resource/Groups')
                kwargs = isight.api('resource_group').calls(kwargs)
    pcolor.Cyan(f'\n{"-" * 60}\n {"-" * 5}')
    for key, value in result.items():
        for k, v in value.items():
            if k == 'msg':
                msg_split = v.split('#')
                msg_split.sort()
                for msg in msg_split:
                    if not msg == '': pcolor.Cyan(msg)
            else: pcolor.Cyan(f"{k}: {v}")
        pcolor.Cyan(f'{"-" * 5}')
    pcolor.Cyan(f'{"-" * 60}')
    if connected_error == True:
        pcolor.Cyan(f'\n{"-"*108}\n')
        pcolor.Yellow(f'  !! ERROR !!\n  One or More Servers Could not Connect to Intersight.')
        pcolor.Yellow(f'  Please Check the Output above.  claim_device.py line 203.')
        pcolor.Cyan(f'\n{"-"*108}\n')
        len(False); sys.exit(1)

    # logout of any sessions active after exception handling
    kwargs.result = result
    kwargs.return_code= return_code
    return kwargs
