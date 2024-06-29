#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    import pcolor
    from dotmap import DotMap
    import json, os, re, requests, time, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#=============================================================================
# API Class
#=============================================================================
class api(object):
    def __init__(self, type):
        self.type = type

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
        def api_auth_function(kwargs):
            password = os.environ['vmware_vcenter_password']
            url      = f'https://{kwargs.vcenter_hostname}/api'
            username = kwargs.vcenter_username
            session = requests.post(f"{url}/session", auth=(username, password), verify=False)
            kwargs.vcenter_session_id = session.json()
            kwargs.vcenter_auth_time= time.time()
            return kwargs
        if not kwargs.get('vcenter_session_id'): kwargs = api_auth_function(kwargs)

        #=====================================================================
        # Setup API Parameters
        #=====================================================================
        def api_calls(kwargs):
            #=================================================================
            # Perform the apiCall
            #=================================================================
            aargs      = kwargs.api_args
            method     = kwargs.method
            moid       = kwargs.pmoid
            payload    = kwargs.api_body
            retries    = 3
            session_id = kwargs.vcenter_session_id
            uri        = kwargs.uri
            url        = f'https://{kwargs.vcenter_hostname}/api'
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
                        for k, v in (response.json()).items(): pcolor.Red(f"    {k} is '{v}'")
                        len(False); sys.exit(1)
                    if re.search('delete|get', method): headers = {"vmware-api-session-id": session_id}
                    else: headers = {"vmware-api-session-id": session_id, 'Content-Type': 'application/json'}
                    if   method == 'get_by_moid': response = requests.get(   f'{url}/{uri}/{moid}', verify=False, headers=headers)
                    elif method ==      'delete': response = requests.delete(f'{url}/{uri}/{moid}', verify=False, headers=headers)
                    elif method ==         'get': response = requests.get(   f'{url}/{uri}{aargs}', verify=False, headers=headers)
                    elif method ==       'patch': response = requests.patch( f'{url}/{uri}/{moid}', verify=False, headers=headers, json=payload)
                    elif method ==        'post': response = requests.post(  f'{url}/{uri}',        verify=False, headers=headers, json=payload)
                    if re.search('40[0|3]', str(response)):
                        retry_action = False
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
                        pcolor.Red(f"Exception when calling {url}/{kwargs.uri}: {e}\n")
                        len(False); sys.exit(1)
                break
            #=================================================================
            # Print Debug Information if Turned on
            #=================================================================
            results = response.json()
            if type(results) == list: api_results = [DotMap(e) for e in results]
            else: api_results = DotMap(response.json())
            if int(debug_level) >= 1: pcolor.Cyan(f'RESPONSE: {str(response)}')
            if int(debug_level)>= 5:                            #RESPONSE: 
                if   method == 'get_by_moid': pcolor.Cyan(f'URL:      {url}/{uri}/{moid}')
                elif method ==         'get': pcolor.Cyan(f'URL:      {url}/{uri}{aargs}')
                elif method ==       'patch': pcolor.Cyan(f'URL:      {url}/{uri}/{moid}')
                elif method ==        'post': pcolor.Cyan(f'URL:      {url}/{uri}')
            if int(debug_level) >= 6:
                pcolor.Cyan('HEADERS:')
                pcolor.Cyan(json.dumps(dict(response.headers), indent=4))
                if len(payload) > 0: pcolor.Cyan('PAYLOAD:'); pcolor.Cyan(json.dumps(payload, indent=4))
            if int(debug_level) == 7: pcolor.Cyan('RESPONSE:'); pcolor.Cyan(json.dumps(api_results, indent=4))
            #=================================================================
            # Return kwargs
            #=================================================================
            kwargs.results = api_results
            return kwargs
        kwargs.api_args = ''
        kwargs          = api_calls(kwargs)
        #=====================================================================
        # Return kwargs
        #=====================================================================
        kwargs_keys = list(kwargs.keys())
        if 'api_filter' in kwargs_keys: kwargs.pop('api_filter')
        if 'build_skip' in kwargs_keys: kwargs.pop('build_skip')
        return kwargs

kwargs = DotMap(
    args = DotMap(debug_level = 0),
    vcenter_hostname = 'vcenter.rich.ciscolabs.com',
    vcenter_username = 'administrator@rich.local')
kwargs = kwargs | DotMap(method = 'get', uri = 'vcenter/vm')
kwargs = api('vm').calls(kwargs)
kwargs = kwargs | DotMap(method = 'get', uri = 'vcenter/folder')
kwargs = api('folder').calls(kwargs)
folders = kwargs.results
folder  = 'Staging'
indx    = next((index for (index, d) in enumerate(folders) if d['name'] == folder), None)
host_folder = folders[indx].folder

password = os.environ['vmware_esxi_password']
kwargs.uri    = 'vcenter/host'
kwargs        = api('host').calls(kwargs)
hosts         = kwargs.results
host_keys     = [e.name for e in hosts]
for e in ['r143e-2-1-4.rich.ciscolabs.com', 'r143e-2-1-7.rich.ciscolabs.com', 'r143e-2-1-8.rich.ciscolabs.com']:
    if not e in host_keys:
        api_body = {
            "folder": host_folder, "force_add": True, "hostname": e, "password": password, "thumbprint_verification": "NONE", "user_name": "root"}
        kwargs = kwargs | DotMap(api_body = api_body, method = 'post', uri = 'vcenter/host')
        kwargs = api('host').calls(kwargs)
