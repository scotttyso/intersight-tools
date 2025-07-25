#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import pcolor
    from dotmap import DotMap
    from stringcase import pascalcase
    import ipaddress, json, re, validators
except ImportError as e:
    prRed(f'classes/validating.py line 6 - !!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

oregex = re.compile('fabric.([a-zA-z]+(Mode|Role)|V[l|s]an)|vnic.(Eth|Fc)If|iam.EndPointUserRole|DriveGroup|Ldap(Group|Provider)')
policy_regex = re.compile('(network_connectivity|ntp|port|snmp|switch_control|syslog|system_qos|vlan|vsan)')

#=============================================================================
# Function - Change Policy Description to Sentence
#=============================================================================
def mod_pol_description(pol_description):
    pdescr = str.title(pol_description.replace('_', ' '))
    pdescr = (((pdescr.replace('Fiattached', 'FIAttached')).replace('Imc', 'IMC')).replace('Mac', 'MAC')).replace('Uuid', 'UUID')
    pdescr = (((pdescr.replace('Iscsi', 'iSCSI')).replace('Fc', 'FC')).replace('San', 'SAN')).replace('Lan', 'LAN')
    pdescr = (((pdescr.replace('Ipmi', 'IPMI')).replace('Ip', 'IP')).replace('Iqn', 'IQN')).replace('Ldap', 'LDAP')
    pdescr = (((pdescr.replace('Ntp', 'NTP')).replace('Sd', 'SD')).replace('Smtp', 'SMTP')).replace('Snmp', 'SNMP')
    pdescr = (((pdescr.replace('Ssh', 'SSH')).replace('Wwnn', 'WWNN')).replace('Wwpn', 'WWPN')).replace('Vsan', 'VSAN')
    pdescr = ((pdescr.replace('Vnics', 'vNICs')).replace('Vhbas', 'vHBAs')).replace('Vlan', 'VLAN')
    return pdescr

# Errors & Notifications
def begin_loop(ptype1, ptype2):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.LightPurple(f"  Beginning {' '.join(ptype1.split('_')).title()} {ptype2} Deployment.\n")

def begin_section(ptype1, ptype2):
    ptype1 = mod_pol_description((' '.join(ptype1.split('_'))).title())
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.LightPurple(f"  Beginning {ptype1} {' '.join(ptype2.split('_')).title()} Deployments.\n")

def completed_item(ptype, kwargs):
    iresults = kwargs.api_results
    method = kwargs.method
    name   = None
    pmoid  = iresults.Moid
    if   'vnic.EthIf' == iresults.ObjectType: name = f"vNIC {iresults.Name}"
    elif 'vnic.FcIf' == iresults.ObjectType:  name = f"vHBA {iresults.Name}"
    elif 'asset.DeviceClaim' == iresults.ObjectType:  name = f"Claiming Server `{iresults.SerialNumber}` Registration"
    elif 'autosupport' == ptype:        name = "AutoSupport"
    elif iresults.get('PcId'):          name = f"PC {iresults['PcId']}"
    elif iresults.get('PortId'):        name = f"Port {iresults['PortId']}"
    elif iresults.get('PortIdStart'):   name = f"PortIdStart {iresults['PortIdStart']}"
    elif iresults.get('VirtualDrives'): name = f"DriveGroup {iresults['Name']}"
    elif iresults.get('VlanId'):        name = f"VLAN {iresults['VlanId']}"
    elif iresults.get('VsanId'):        name = f"VSAN {iresults['VsanId']}"
    elif 'user_role' in ptype:          name = f"Role for {ptype}"
    elif 'upgrade' in ptype:     name = f".  Performing Firmware Upgrade on {kwargs.serial} - {kwargs.server} Server Profile"
    elif iresults.get('UserId'):        name = f"{iresults['UserId']} CCO User Authentication"
    elif 'eula' in ptype:        name = f"Account EULA Acceptance"
    elif iresults.get('Action'):
        if iresults['Action'] == 'Deploy': name = f"Deploy Profile {pmoid}"
        else: name = iresults['Name']
    elif iresults.get('ScheduledActions'): name = f"Activating Profile {pmoid}"
    elif iresults.get('Targets'):          name = iresults['Targets'][0]['Name']
    elif 'update_tags' in ptype:           name = f"Tags updated for Physical Server attached to {kwargs.tag_server_profile}"
    elif iresults.get('Identity'):         name = f"Reservation: `{iresults.Identity}`"
    elif iresults.get('Name'):             name = iresults['Name']
    elif iresults.get('EndPointRole'):
        users = DotMap()
        for k,v in kwargs.user_moids.items(): users[v.moid] = k
        name = list(users.values())[list(users.keys()).index(iresults.EndPointUser.Moid)]
    if name == None:
        print(json.dumps(iresults, indent=4))
        print(kwargs.ptype)
        print(kwargs.parent_name)
        print(kwargs.parent_type)
        print('missing definition')
        len(False); sys.exit(1)
    if re.search(oregex, iresults.get('ObjectType')):
        parent_title = ((kwargs.parent_key.replace('_', ' ')).title())
        parent_title = mod_pol_description(parent_title)
        parents      = DotMap()
        for k,v in kwargs.isight[kwargs.org].policies[kwargs.parent_key].items(): parents[v] = k
        if 'an_connectivity' in kwargs.parent_key: kwargs.parent_name = parents[iresults[f'{pascalcase(kwargs.parent_key)}Policy'].Moid]
        elif kwargs.parent_key == 'local_user': kwargs.parent_name = parents[iresults[f'EndPointUserPolicy'].Moid]
        elif kwargs.parent_key == 'port':       kwargs.parent_name = parents[iresults[f'PortPolicy'].Moid]
        elif kwargs.parent_key == 'vlan':       kwargs.parent_name = parents[iresults[f'EthNetworkPolicy'].Moid]
        elif kwargs.parent_key == 'vsan':       kwargs.parent_name = parents[iresults[f'FcNetworkPolicy'].Moid]
        else: kwargs.parent_name = list(parents.values())[list(parents.keys()).index(iresults.Parent.Moid)]
        if method == 'post':
            pcolor.Green(f'{" "*6}* Completed {method.upper()} for Org: {kwargs.org} > {parent_title} `{kwargs.parent_name}`: {name} - Moid: {pmoid}')
        else:
            pcolor.LightPurple(f'{" "*6}* Completed {method.upper()} for Org: {kwargs.org} > {parent_title} `{kwargs.parent_name}`: {name} - Moid: {pmoid}')
    elif re.search('^(Activating|Deploy)', name): pcolor.Cyan(f'      * {name}.')
    elif re.search('(eula|upgrade)', ptype) and ptype == 'firmware':
        if method == 'post': pcolor.Green(f'{" "*6}* Completed {method.upper()} for {ptype} {name}.')
        else: pcolor.LightPurple(f'      * Completed {method.upper()} for {ptype} {name}.')
    elif 'Claiming' in name: pcolor.Green(f'{" "*6}- Completed POST for {name} - Moid: {pmoid}')
    elif 'Reservation' in name: pcolor.Green(f'{" "*6}- Completed POST for {name} - Moid: {pmoid}')
    elif 'bulk/MoMergers' == kwargs.uri:
        if method == 'post': pcolor.Green(f'{" "*6}- Completed Bulk Merger {method.upper()} for Org: {kwargs.org} > Name: {name} - Moid: {pmoid}')
        else: pcolor.LightPurple(f'{" "*4}- Completed Bulk Merger {method.upper()} for Org: {kwargs.org} > Name: {name} - Moid: {pmoid}')
    else:
        if method == 'post': pcolor.Green(f'{" "*6}- Completed {method.upper()} for Org: {kwargs.org} Name: {name} - Moid: {pmoid}')
        else: pcolor.LightPurple(f'{" "*6}- Completed {method.upper()} for Org: {kwargs.org} > Name: {name} - Moid: {pmoid}')

def deploy_notification(profile, profile_type):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.LightPurple(f'   Deploy Action Still ongoing for {profile_type} Profile {profile}')
    pcolor.LightGray(f'\n{"-"*108}\n')

def error_file_location(varName, varValue):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'  !!! ERROR !!! The "{varName}" "{varValue}"')
    pcolor.Yellow(f'  is invalid.  Please valid the Entry for "{varName}".')
    pcolor.LightGray(f'\n{"-"*108}\n')

def end_loop(ptype1, ptype2):
    pcolor.LightPurple(f"\n   Completed {' '.join(ptype1.split('_')).title()} {ptype2} Deployment.")

def end_section(ptype1, ptype2):
    ptype1 = mod_pol_description((' '.join(ptype1.split('_'))).title())
    pcolor.LightPurple(f"\n   Completed {ptype1} {' '.join(ptype2.split('_')).title()} Deployments.")

def error_policy_doesnt_exist(parent_type, parent_name, ptype, pname):
    if re.search('chassis|domain|server|switch', parent_type):
        p2, p1 = parent_type.split('.'); parent_ptype = p1.capitalize(); parent_stype = (p2.capitalize())[:-1]
    else: parent_ptype = mod_pol_description(' '.join(parent_type.split('.'))); parent_stype = 'Policy'
    if re.search('ip|iqn|mac|resource|uuid|wwnn|wwpn', ptype): dtype = 'Pool'
    elif 'template' in ptype: dtype = 'Template'
    else: dtype = 'Policy'
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'   !!! ERROR !!!')
    pcolor.Yellow(f'   The Following {dtype} was attached to {parent_ptype} {parent_stype} `{parent_name}`, but it has not been created.')
    pcolor.Yellow(f'   {dtype} Type: {ptype}')
    pcolor.Yellow(f'   {dtype} Name: {pname}')
    pcolor.LightGray(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def error_pool_doesnt_exist(org, pool_type, pool_name, profile):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'   !!! ERROR !!! The Following Pool was used in reservations for Server Profile {profile}')
    pcolor.Yellow(f'   But it has not been created.')
    pcolor.Yellow(f'   Organization: {org}')
    pcolor.Yellow(f'   Pool Type: {pool_type}')
    pcolor.Yellow(f'   Pool Name: {pool_name}')
    pcolor.LightGray(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def error_required_argument_missing(ptype, kwargs):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'   !!! ERROR !!! {ptype}: `{kwargs.name}` missing required argument {kwargs.argument}')
    pcolor.LightGray(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def error_request(status, text):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'   !!! ERROR !!! in Retreiving Terraform Cloud Organization Workspaces')
    pcolor.Yellow(f'   Exiting on Error {status} with the following output:')
    pcolor.Yellow(f'   {text}')
    pcolor.LightGray(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def error_requests(method, status, text, uri):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'   !!! ERROR !!! when attempting {method} to {uri}')
    pcolor.Yellow(f'   Exiting on Error {status} with the following output:')
    pcolor.Yellow(f'   {text}')
    pcolor.LightGray(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def error_request_netapp(method, status, text, uri):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'   !!! ERROR !!! when attempting {method} to {uri}')
    pcolor.Yellow(f'   Exiting on Error {status} with the following output:')
    pcolor.Yellow(f'   {text}')
    pcolor.LightGray(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def error_request_pure_storage(method, status, text, uri):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'   !!! ERROR !!! when attempting {method} to {uri}')
    pcolor.Yellow(f'   Exiting on Error {status} with the following output:')
    pcolor.Yellow(f'   {text}')
    pcolor.LightGray(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def error_serial_number(name, serial):
    pcolor.LightGray(f'\n{"-"*108}\n')
    pcolor.Yellow(f'  !!! ERROR !!! The Serial Number "{serial}" for "{name}" was not found in inventory.')
    pcolor.Yellow(f'  Please check the serial number for "{name}".')
    pcolor.LightGray(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def error_subnet_check(args):
    prefix    = args.subnetMask if args.ip_version == 'v4'else args.prefix
    gateway   = args.defaultGateway
    pool_from = ipaddress.ip_address(args.pool_from)
    pool_to   = ipaddress.ip_address(args.pool_to)
    if not pool_from in ipaddress.ip_network(f"{gateway}/{prefix}", strict=False):
        print(f'\n{"-"*108}\n')
        print(f'   !!! ERROR !!!  {pool_from} is not in network {gateway}/{prefix}:')
        print(f'   Exiting....')
        print(f'\n{"-"*108}\n')
        len(False); sys.exit(1)
    if not pool_to in ipaddress.ip_network(f"{gateway}/{prefix}", strict=False):
        print(f'\n{"-"*108}\n')
        print(f'   !!! ERROR !!!  {pool_to} is not in network {gateway}/{prefix}:')
        print(f'   Exiting....')
        print(f'\n{"-"*108}\n')
        len(False); sys.exit(1)

def error_subnet_not_found(kwargs):
    poolFrom = kwargs['pool_from']
    print(f'\n{"-"*108}\n')
    print(f'   !!! ERROR !!!  Did not Find a Correlating Network for {poolFrom}.')
    print(f'   Defined Network List:')
    for i in kwargs['networks']:
        print(f'    * {i}')
        print(f'   Exiting....')
    print(f'\n{"-"*108}\n')
    len(False); sys.exit(1)

def unmapped_keys(policy_type, name, key):
    print(f'\n{"-"*108}\n')
    print(f'   !!! ERROR !!!! For {policy_type}, {name}, unknown key {key}')
    print(f'\n{"-"*108}\n')
    len(False); sys.exit(1)
 
# Validations
def boolean(var, kwargs):
    row_num = kwargs['row_num']
    ws = kwargs['ws']
    varValue = kwargs['var_dict'][var]
    valid_count = 1
    if varValue == 'True' or varValue == 'False':
        valid_count = 0
    if not valid_count == 0:
        print(f'{"-"*108}')
        print(f'   Error on Worksheet "{ws.title}", Row {row_num}, Variable {var};')
        print(f'   must be True or False.  Exiting....')
        print(f'{"-"*108}')
        len(False); sys.exit(1)

def description(varName, varValue, minLength, maxLength):
    if not (re.search(r'^[a-zA-Z0-9\\!#$%()*,-./:;@ _{|}~?&+]+$',  varValue) and \
    validators.length(str(varValue), min=int(minLength), max=int(maxLength))):
        print(f'{"-"*108}')
        print(f'   The description is an invalid Value... It failed one of the following')
        print(f'   complexity tests:')
        print(f'    - Min Length {minLength}')
        print(f'    - Max Length {maxLength}')
        print('    - Regex [a-zA-Z0-9\\!#$%()*,-./:;@ _{|}~?&+]+')
        print(f'{"-"*108}')
        return False
    else: return True

def domain(varName, varValue):
    if not validators.domain(varValue):
        print(f'{"-"*108}')
        print(f'   Error with {varName}!!!  Invalid Domain {varValue}')
        print(f'   Please Validate the domain and retry.')
        print(f'{"-"*108}')
        return False
    else: return True

def domain_ws(var, kwargs):
    row_num  = kwargs['row_num']
    ws       = kwargs['ws']
    varValue = kwargs['var_dict'][var]
    if not validators.domain(varValue):
        print(f'{"-"*108}')
        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}, {varValue} ')
        print(f'   Error with {var}. Invalid Domain "{varValue}"')
        print(f'   Please Validate the domain and retry.')
        print(f'{"-"*108}')
        len(False); sys.exit(1)
    else: return True

def dns_name(varName, varValue):
    hostname = varValue
    valid_count = 0
    if len(hostname) > 255: valid_count =+ 1
    if not validators.domain(hostname): valid_count =+ 1
    if hostname[-1] == ".": hostname = hostname[:-1] # strip exactly one dot from the right, if present
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    if not all(allowed.match(x) for x in hostname.split(".")): valid_count =+ 1
    if not valid_count == 0:
        print(f'{"-"*108}')
        print(f'   Error with {varName}.  "{varValue}" is not a valid Hostname/Domain.')
        print(f'   Confirm that you have entered the DNS Name Correctly.')
        print(f'{"-"*108}')
        return False
    else: return True

def dns_name_ws(var, kwargs):
    row_num  = kwargs['row_num']
    ws       = kwargs['ws']
    varValue = kwargs['var_dict'][var]
    hostname = varValue
    valid_count = 0
    if len(hostname) > 255:
        valid_count =+ 1
    if re.search('^\\..*', varValue):
        domain = varValue.strip('.')
        if not validators.domain(domain): valid_count =+ 1
    if not re.search('^\\..*', hostname):
        if hostname[-1] == ".": hostname = hostname[:-1] # strip exactly one dot from the right, if present
        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        if not all(allowed.match(x) for x in hostname.split(".")):
            valid_count =+ 1
    if not valid_count == 0:
        print(f'{"-"*108}')
        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}, {varValue} ')
        print(f'   is not a valid Hostname.  Confirm that you have entered the DNS Name Correctly.')
        print(f'   Exiting....')
        print(f'{"-"*108}')
        len(False); sys.exit(1)

def email(varName, varValue):
    if not validators.email(varValue, whitelist=None):
        print(f'{"-"*108}')
        print(f'   Error with {varName}. Email address "{varValue}"')
        print(f'   is invalid.  Please Validate the email and retry.')
        print(f'{"-"*108}')
        return False
    else: return True

def email_ws(var, kwargs):
    row_num  = kwargs['row_num']
    ws       = kwargs['ws']
    varValue = kwargs['var_dict'][var]
    if not validators.email(varValue, whitelist=None):
        print(f'{"-"*108}')
        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}, {varValue} ')
        print(f'   Error with {var}. Email address "{varValue}"')
        print(f'   is invalid.  Please Validate the email and retry.')
        print(f'{"-"*108}')
        len(False); sys.exit(1)
    else: return True

def ip_address(varName, varValue):
    if re.search('/', varValue):
        x = varValue.split('/')
        address = x[0]
    else: address = varValue
    valid_count = 0
    if re.search(r'\.', address):
        if not validators.ip_address.ipv4(address): valid_count =+ 1
    else:
        if not validators.ip_address.ipv6(address): valid_count =+ 1
    if not valid_count == 0 and re.search(r'\.', address):
        print(f'{"-"*108}')
        print(f'   Error with {varName}. "{varValue}" is not a valid IPv4 Address.')
        print(f'{"-"*108}')
        return False
    elif not valid_count == 0:
        print(f'{"-"*108}')
        print(f'   Error with {varName}. "{varValue}" is not a valid IPv6 Address.')
        print(f'{"-"*108}')
        return False
    else: return True

def ip_address_ws(var, kwargs):
    row_num  = kwargs['row_num']
    ws       = kwargs['ws']
    varValue = kwargs['var_dict'][var]
    if re.search('/', varValue):
        x = varValue.split('/')
        address = x[0]
    else: address = varValue
    valid_count = 0
    if re.search(r'\.', address):
        if not validators.ip_address.ipv4(address): valid_count =+ 1
    else:
        if not validators.ip_address.ipv6(address): valid_count =+ 1
    if not valid_count == 0 and re.search(r'\.', address):
        print(f'{"-"*108}')
        print(f'   Error on row {row_num} with {var}. "{varValue}" is not a valid IPv4 Address.')
        print(f'{"-"*108}')
        return False
    elif not valid_count == 0:
        print(f'{"-"*108}')
        print(f'   Error on row {row_num} with {var}. "{varValue}" is not a valid IPv6 Address.')
        print(f'{"-"*108}')
        return False
    else: return True

def iqn_prefix(varName, varValue):
    invalid_count = 0
    if not re.fullmatch(r'^iqn\.[0-9]{4}-[0-9]{2}\.([A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])?)', varValue):
        invalid_count += 1
    if not invalid_count == 0:
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}" did not meet one of the following rules:')
        print(f'     - it must start with "iqn".')
        print(f"     - The second octet must be a valid date in the format YYYY-MM.")
        print(f'     - The third and fourth octet must be a valid domain that starts with a letter or ')
        print(f'       number ends with a letter or number and may have a dash in the middle.')
        print(f'{"-"*108}')
        return False
    else: return True

def iqn_address(varName, varValue):
    invalid_count = 0
    if not re.fullmatch(r'^(?:iqn\.[0-9]{4}-[0-9]{2}(?:\.[A-Za-z](?:[A-Za-z0-9\-]*[A-Za-z0-9])?)+(?::.*)?|eui\.[0-9A-Fa-f]{16})', varValue):
        invalid_count += 1
    if not invalid_count == 0:
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}" did not meet one of the following rules:')
        print(f'     - it must start with "iqn".')
        print(f"     - The second octet must be a valid date in the format YYYY-MM.")
        print(f'     - The third and fourth octet must be a valid domain that starts with a letter or ')
        print(f'       number ends with a letter or number and may have a dash in the middle.')
        print(f'     - it must have a colon to mark the beginning of the prefix.')
        print(f'{"-"*108}')
        return False
    else: return True

def ipmi_key_check(ipmi_key):
    invalid_count = 0
    if not len(ipmi_key) % 2 == 0: invalid_count += 1
    if not validators.length(ipmi_key, min=2, max=40): invalid_count += 1
    if not re.fullmatch(r'^[0-9a-fA-F]{2,40}$', ipmi_key): invalid_count += 1
    if not invalid_count == 0:
        print(f'{"-"*108}')
        print(f'   Error with IPMI Key! It should have an even number of hexadecimal characters and not exceed 40 characters.'\
            ' Use “00” to disable encryption key use. This configuration is supported by all Standalone C-Series servers.'\
            ' FI-attached C-Series servers with firmware at minimum of 4.2.3a support this configuration.'\
            ' B/X-Series servers with firmware at minimum of 5.1.0.x support this configuration.'\
            ' IPMI commands using this key should append zeroes to the key to achieve a length of 40 characters.')
        print(f'{"-"*108}')
        return False
    else: return True
   
def length_and_regex(answer, minLength, maxLength, pattern, title):
    invalid_count = 0
    if minLength == 0 and maxLength == 0: invalid_count = 0
    else:
        if not validators.length(answer, min=int(minLength), max=int(maxLength)):
            invalid_count += 1
            print(f'{"-"*108}')
            print(f'   !!! {title} value "{answer}" is Invalid!!!')
            print(f'   Length Must be between {minLength} and {maxLength} characters.')
            print(f'{"-"*108}')
    if not re.search(pattern, str(answer)):
        invalid_count += 1
        print(f'{"-"*108}')
        print(f'   !!! Invalid Characters in {answer}.  The allowed characters are:')
        print(f'   - "{pattern}"')
        print(f'{"-"*108}')
    if invalid_count == 0:
        return True
    else: return False

def list_values(var, json_data, kwargs):
    json_data = kwargs['validateData']
    row_num = kwargs['row_num']
    ws = kwargs['ws']
    varList = json_data[var]['enum']
    varValue = kwargs['var_dict'][var]
    match_count = 0
    for x in varList:
        if str(x) == str(varValue):
            match_count =+ 1
    if not match_count > 0:
        print(f'{"-"*108}')
        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}, {varValue}. ')
        print(f'   {var} should be one of the following:')
        for x in varList:
            print(f'    - {x}')
        print(f'    Exiting....')
        print(f'{"-"*108}')
        len(False); sys.exit(1)

def list_values_key(dictkey, var, kwargs):
    json_data = kwargs['validateData']
    row_num = kwargs['row_num']
    ws = kwargs['ws']
    varList = json_data[dictkey]['enum']
    varValue = kwargs['var_dict'][var]
    match_count = 0
    for x in varList:
        if x == varValue:
            match_count =+ 1
    if not match_count > 0:
        print(f'{"-"*108}')
        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}, {varValue}. ')
        print(f'   {var} should be one of the following:')
        for x in varList:
            print(f'    - {x}')
        print(f'    Exiting....')
        print(f'{"-"*108}')
        len(False); sys.exit(1)

def mac_address(varName, varValue):
    if not validators.mac_address(varValue):
        print(f'{"-"*108}')
        print(f'   Error with {varName}. "{varValue}" is not a valid MAC Address.')
        print(f'{"-"*108}')
        return False
    else: return True

def number_check(var, json_data, kwargs):
    minimum = json_data[var]['minimum']
    maximum = json_data[var]['maximum']
    row_num = kwargs['row_num']
    ws = kwargs['ws']
    varValue = kwargs['var_dict'][var]
    if not (validators.between(int(varValue), min=int(minimum), max=int(maximum))):
        print(f'{"-"*108}')
        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}, {varValue}. Valid Values ')
        print(f'   are between {minimum} and {maximum}.  Exiting....')
        print(f'{"-"*108}')
        len(False); sys.exit(1)

def number_list(var, kwargs):
    json_data = kwargs['validateData']
    minimum = json_data[var]['minimum']
    maximum = json_data[var]['maximum']
    row_num = kwargs['row_num']
    ws = kwargs['ws']
    varValue = kwargs['var_dict'][var]
    if '-' in str(varValue):
        varValue = varValue.split('-')
        if ',' in str(varValue):
            varValue = varValue.split(',')
    elif ',' in str(varValue):
        varValue = varValue.split(',')
    else:
        varValue = [varValue]
    for x in varValue:
        if not (validators.between(int(x), min=int(minimum), max=int(maximum))):
            print(f'{"-"*108}')
            print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}, {x}. Valid Values ')
            print(f'   are between {minimum} and {maximum}.  Exiting....')
            print(f'{"-"*108}')
            len(False); sys.exit(1)

def string_list(var, json_data, kwargs):
    # Get Variables from Library
    minimum = json_data[var]['minimum']
    maximum = json_data[var]['maximum']
    pattern = json_data[var]['pattern']
    row_num = kwargs['row_num']
    varValues = kwargs['var_dict'][var]
    ws = kwargs['ws']
    for varValue in varValues.split(','):
        if not (re.fullmatch(pattern,  varValue) and validators.length(
            str(varValue), min=int(minimum), max=int(maximum))):
            print(f'{"-"*108}')
            print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}. ')
            print(f'   "{varValue}" is an invalid Value...')
            print(f'   It failed one of the complexity tests:')
            print(f'    - Min Length {maximum}')
            print(f'    - Max Length {maximum}')
            print(f'    - Regex {pattern}')
            print(f'    Exiting....')
            print(f'{"-"*108}')
            len(False); sys.exit(1)

def string_pattern(var, json_data, kwargs):
    # Get Variables from Library
    minimum = json_data[var]['minimum']
    maximum = json_data[var]['maximum']
    pattern = json_data[var]['pattern']
    row_num = kwargs['row_num']
    varValue = kwargs['var_dict'][var]
    ws = kwargs['ws']
    if not (re.fullmatch(pattern,  varValue) and validators.length(
        str(varValue), min=int(minimum), max=int(maximum))):
        print(f'{"-"*108}')
        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}. ')
        print(f'   "{varValue}" is an invalid Value...')
        print(f'   It failed one of the complexity tests:')
        print(f'    - Min Length {minimum}')
        print(f'    - Max Length {maximum}')
        print(f'    - Regex {pattern}')
        print(f'    Exiting....')
        print(f'{"-"*108}')
        len(False); sys.exit(1)

def wwxn_address(varName, varValue):
    if not re.search(r'([0-9A-F]{2}[:-]){7}([0-9A-F]{2})', varValue):
        print(f'{"-"*108}')
        print(f'   Error with {varName}. "{varValue}" is not a valid WWxN Address.')
        print(f'{"-"*108}')
        return False
    else: return True

def name_rule(varName, varValue, minLength, maxLength):
    if not (re.search(r'^[a-zA-Z0-9_-]+$',  varValue) and validators.length(str(varValue), min=int(minLength), max=int(maxLength))):
        print(f'{"-"*108}')
        print(f'   Error with {varName}!!  "{varValue}" failed one of the complexity tests:')
        print(f'    - Min Length {minLength}')
        print(f'    - Max Length {maxLength}')
        print(f'    - Name can only contain letters(a-z,A-Z), numbers(0-9), hyphen(-),')
        print(f'      or an underscore(_)')
        print(f'{"-"*108}')
        return False
    else: return True

def org_rule(varName, varValue, minLength, maxLength):
    if not (re.search(r'^[a-zA-Z0-9:_-]+$',  varValue) and validators.length(str(varValue), min=int(minLength), max=int(maxLength))):
        print(f'{"-"*108}')
        print(f'   Error with {varName}!!  "{varValue}" failed one of the complexity tests:')
        print(f'    - Min Length {minLength}')
        print(f'    - Max Length {maxLength}')
        print(f'    - Name can only contain letters(a-z,A-Z), numbers(0-9), hyphen(-),')
        print(f'      period(.), colon(:), or an underscore(_)')
        print(f'{"-"*108}')
        return False
    else: return True

def number_in_range(varName, varValue, minNum, maxNum):
    if not validators.between(int(varValue), min=int(minNum), max=int(maxNum)):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}".')
        print(f'   Valid values are between {minNum} and {maxNum}.')
        print(f'{"-"*108}')
        return False
    else: return True

def snmp_port(varName, varValue, minNum, maxNum):
    valid_count = 1
    if not (int(varValue) >= int(minNum) and int(varValue) <= int(maxNum)):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}".')
        print(f'   Valid values are between {minNum} and {maxNum}.')
        print(f'{"-"*108}')
        valid_count = 0
    if re.fullmatch(r'^(22|23|80|123|389|443|623|636|2068|3268|3269)$', str(varValue)):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}".')
        print(f'   The following ports are not allowed:')
        print(f'   [22, 23, 80, 123, 389, 443, 623, 636, 2068, 3268, 3269]')
        print(f'{"-"*108}')
        valid_count = 0
    if valid_count == 0: return False
    else: return True

def snmp_string(varName, varValue):
    if not (re.fullmatch(r'^([a-zA-Z]+[a-zA-Z0-9\-\_\.\@]+)$', varValue) and validators.length(varValue, min=8, max=32)):
        print(f'{"-"*108}')
        print(f'   Error!!  {varName} is invalid.  The community and ')
        print(f'   username policy name must be a minimum of 8 and maximum of 32 characters ')
        print(f'   in length.  The name can contain only letters, numbers and the special ')
        print(f'   characters of underscore (_), hyphen (-), at sign (@), or period (.).')
        print(f'{"-"*108}')
        return False
    else: return True

def string_length(varName, varValue, minLength, maxLength):
    if not validators.length(str(varValue), min=int(minLength), max=int(maxLength)):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! {varValue} must be between')
        print(f'   {minLength} and {maxLength} characters.')
        print(f'{"-"*108}')
        return False
    else: return True

def url(varName, varValue):
    if not validators.url(varValue):
        print(f'{"-"*108}')
        print(f'   Error with {varName}, {varValue}. ')
        print(f'   {varName} should be a valid URL.  The Following is not a valid URL:')
        print(f'    - {varValue}')
        print(f'{"-"*108}')
        return False
    else: return True

def username(varName, varValue, minLength, maxLength):
    if not re.search(r'^[a-zA-Z0-9\.\-\_]+$', varValue) and validators.length(str(varValue), min=int(minLength), max=int(maxLength)):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! Username {varValue} must be between ')
        print(f'   {varName} should be a valid URL.  The Following is not a valid URL:')
        print(f'    - {varValue}')
        print(f'    Exiting....')
        print(f'{"-"*108}')
        return False
    else: return True

def uuid(varName, varValue):
    if not re.fullmatch(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', varValue):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}"')
        print(f'   Is not a Valid UUID Identifier.')
        print(f'{"-"*108}')
        return False
    else: return True

def uuid_prefix(varName, varValue):
    if not re.fullmatch(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}$', varValue):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}"')
        print(f'   Is not a Valid UUID Prefix.')
        print(f'{"-"*108}')
        return False
    else: return True

def uuid_suffix(varName, varValue):
    if not re.fullmatch(r'^[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', varValue):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}"')
        print(f'   Is not a Valid UUID Suffix.')
        print(f'{"-"*108}')
        return False
    else: return True

def vlan_list(vlan_list):
    for e in vlan_list:
        if not validators.between(e, min=1, max=4093):
            pcolor.Red(f'\n{"-"*108}')
            pcolor.Red(f'   !!! ERROR !!! VLAN Id `{e}` is invalid.  It must be an integer between 1 and 4093:')
            pcolor.Red(f'{"-"*108}')
            return False
    return True

def vlans(var, kwargs):
    row_num = kwargs['row_num']
    ws = kwargs['ws']
    varValue = kwargs['var_dict'][var]
    if re.search(',', str(varValue)):
        vlan_split = varValue.split(',')
        for x in vlan_split:
            if re.search('\\-', x):
                dash_split = x.split('-')
                for z in dash_split:
                    if not validators.between(int(z), min=1, max=4095):
                        print(f'{"-"*108}')
                        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}. Valid VLAN Values are:')
                        print(f'   between 1 and 4095.  "{z}" is not valid.  Exiting....')
                        print(f'{"-"*108}')
                        len(False); sys.exit(1)
            elif not validators.between(int(x), min=1, max=4095):
                print(f'{"-"*108}')
                print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}. Valid VLAN Values are:')
                print(f'   between 1 and 4095.  "{x}" is not valid.  Exiting....')
                print(f'{"-"*108}')
                len(False); sys.exit(1)
    elif re.search('\\-', str(varValue)):
        dash_split = varValue.split('-')
        for x in dash_split:
            if not validators.between(int(x), min=1, max=4095):
                print(f'{"-"*108}')
                print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}. Valid VLAN Values are:')
                print(f'   between 1 and 4095.  "{x}" is not valid.  Exiting....')
                print(f'{"-"*108}')
                len(False); sys.exit(1)
    elif not validators.between(int(varValue), min=1, max=4095):
        print(f'{"-"*108}')
        print(f'   Error on Worksheet {ws.title}, Row {row_num} {var}. Valid VLAN Values are:')
        print(f'   between 1 and 4095.  "{varValue}" is not valid.  Exiting....')
        print(f'{"-"*108}')
        len(False); sys.exit(1)

def vname(varName, varValue):
    if not re.fullmatch(r'^[a-zA-Z0-9\-\.\_:]{1,31}$', varValue):
        print(f'{"-"*108}')
        print(f'   Error with {varName}! "{varValue}" did not meet the validation rules.  The name can')
        print(f'   can contain letters (a-zA-Z), numbers (0-9), dash "-", period ".", underscore "_",')
        print(f'   and colon ":". and be between 1 and 31 characters.')
        print(f'{"-"*108}')
        return False
    else: return True
