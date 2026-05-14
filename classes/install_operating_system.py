#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from .. import pcolor, shared_functions
    from datetime import datetime, timedelta
    from dotmap import DotMap
    import base64, json, pytz, re, os
except ImportError as e:
    prRed(f'src/install_operation_system.py - !!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f' Module {e.name} is required to run this script')
    prRed(f' Install the module using the following: `pip install {e.name}`')
    sys.exit(1)

class os_install(object):
    """Intersight Operating System Installation Configuration Class"""
    def __init__(self, category, type):
        super().__init__(category, type)
    #=============================================================================
    # Function - Build api_body for Operating System Installation - VMware
    #=============================================================================
    def installation_body(self, v, kwargs):
        if kwargs.script_name == 'ezci' and kwargs.args.deployment_type == 'azure_stack':
            api_body = self.installation_body_azure_stack(v, kwargs)
        elif kwargs.script_name == 'ezci' and kwargs.args.deployment_type == 'vmware':
            api_body = self.installation_body_vmware(v, kwargs)
        elif 'shared' in kwargs.os_cfg_moids[v.os_configuration].Owners:
            answers = DotMap(); encrypted = False
            answer_keys = list(v.answers.keys())
            for e in kwargs.os_cfg_moids[v.os_configuration].Placeholders:
                if re.search(r'\.answers\.', e.Type.Name): name = e.Type.Name[9:]
                elif '.internal' in e.Type.Name: continue
                elif 'FQDN' in e.Type.Name: continue
                else: name = e.Type.Name[1:]
                x = name.split('.')
                if x[0] in answer_keys:
                    if type(v.answers[x[0]]) == str and 'sensitive_' in v.answers[x[0]]:
                        kwargs.sensitive_var = v.answers[x[0]].replace('sensitive_', '')
                        kwargs   = shared_functions.sensitive_var_value(kwargs)
                        password = kwargs.var_value
                        if v.os_vendor == 'Microsoft':
                            if 'LogonPassword' in x[0]:
                                answers[x[0]]   = base64.b64encode(f'{password}Password'.encode(encoding='utf-16-le')).decode()
                            else: answers[x[0]] = base64.b64encode(f'{password}AdministratorPassword'.encode(encoding='utf-16-le')).decode()
                        else:
                            if kwargs.op_system == 'Windows':
                                answers[x[0]] = password
                                encrypted = False
                            else:
                                try:
                                    #from passlib.hash import sha512_crypt
                                    import crypt
                                except ImportError as e:
                                    prRed(f'{e}')
                                    prRed(f'src/shared_functions.py line 557 - !!! ERROR !!!\n{e.__class__.__name__}')
                                    prRed(f" Module {e.name} is required to run this script")
                                    prRed(f" Install the module using the following: `pip install {e.name}`")
                                    sys.exit(1)
                                answers[x[0]] = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
                                encrypted = True
                    elif x[0] == 'NameServer': answers['Nameserver'] = v.answers[x[0]]
                    elif x[0] == 'AlternateNameServer': answers['AlternateNameServers'] = [v.answers['AlternateNameServer']]
                    else: answers[x[0]] = v.answers[x[0]]
            if answers.get('IpV4Config') or answers.get('IpV6Config') or answers.IpConfigType == 'DHCP':
                vx = answers.IpVersion
                answers.pop('IpVersion')
                if answers.IpConfigType == 'DHCP': ip_config = {'ObjectType': f'os.Ip{vx.lower()}Configuration'}
                else: ip_config = DotMap({f'Ip{vx}Config': answers[f'Ip{vx}Config'].toDict(), 'ObjectType': f'os.Ip{vx.lower()}Configuration'}).toDict()
                answers.IpConfiguration = ip_config
                if f'Ip{vx}Config' in answer_keys: answers.pop(f'Ip{vx}Config')
            if answers.get('FQDN') and v.os_vendor == 'VMware': answers.Hostname = answers.FQDN; answers.pop('FQDN')
            api_body = {
                'Answers': dict(sorted(dict(answers, **{'IsRootPasswordCrypted': False, 'Source': 'Template'}).items())),
                'AdditionalParameters': None,
                'Description': '',
                'ConfigurationFile': {'Moid': v.os_configuration, 'ObjectType': 'os.ConfigurationFile'},
                'Image': {'Moid': v.os_image, 'ObjectType': 'softwarerepository.OperatingSystemFile'},
                'InstallMethod': 'vMedia',
                'InstallTarget': {},
                'ObjectType': 'os.Install', 
                'OperatingSystemParameters': {'Edition': 'Standard','ObjectType': 'os.WindowsParameters'},
                'Organization': {'Moid': kwargs.org_moids[kwargs.org].moid, 'ObjectType': 'organization.Organization'},
                'OsduImage': {'Moid': v.scu, 'ObjectType': 'firmware.ServerConfigurationUtilityDistributable'},
                'OverrideSecureBoot': False,
                'Server': {'Moid': v.hardware_moid, 'ObjectType': v.object_type}}
            if v.os_vendor == 'Microsoft':
                api_body['OperatingSystemParameters']['Edition'] = v.answers.EditionString
                api_body['Answers'].pop('EditionString')
            else: api_body.pop('OperatingSystemParameters')
            if api_body['Answers'].get('SecureBoot'):
                api_body['Answers'].pop('SecureBoot')
                if v.boot_order.enable_secure_boot == True: api_body.update({'OverrideSecureBoot': True})
            if api_body['Answers'].get('BootMode'): api_body['Answers'].pop('BootMode')
            if encrypted == True: api_body['Answers']['IsRootPasswordCrypted'] = True
        if v.boot_volume.lower() == 'm2':
            for k,v in v.storage_controllers.items():
                vkeys = list(v.keys())
                slot_rx = re.compile('(MSTOR-RAID)')
                if 'virtual_drives' in vkeys and re.search(slot_rx, v.slot):
                    drive = [DotMap(id = a, name = b.name, slot = re.search(slot_rx, v.slot).group(1)) for a,b in v.virtual_drives.items() if int(b.size) > 128000][0]
                    break
            api_body['InstallTarget'] = {'Id': str(drive.id), 'Name': drive.name, 'ObjectType': 'os.VirtualDrive', 'StorageControllerSlotId': drive.slot}
        elif v.boot_volume.lower() == 'san':
            api_body['InstallTarget'] = {'InitiatorWwpn': kwargs.fc_ifs[kwargs.san_target.interface_name].wwpn, 'LunId': kwargs.san_target.lun,
                                        'ObjectType': 'os.FibreChannelTarget', 'TargetWwpn': kwargs.san_target.wwpn}
        api_body = dict(sorted(api_body.items()))
        return api_body

    #=============================================================================
    # Function - Build api_body for Operating System Installation - Azure Stack
    #=============================================================================
    def installation_body_azure_stack(self, v, kwargs):
        vnics = []
        for a,b in v.adapters.items():
            bkeys = list(b.keys())
            if 'eth_ifs' in bkeys: vnics.append(b.adapter_id)
        vnics.sort()
        api_body = {
            'AdditionalParameters': [],
            'Answers': {'Source': 'Template'},
            'ConfigurationFile': {'Moid': v.os_configuration, 'ObjectType': 'os.ConfigurationFile'},
            'Description': '',
            'Image': {'Moid': v.os_image, 'ObjectType': 'softwarerepository.OperatingSystemFile'},
            'InstallMethod': 'vMedia',
            'OperatingSystemParameters': {'Edition': 'DatacenterCore', 'ObjectType': 'os.WindowsParameters'},
            'Organization': {'Moid': kwargs.org_moids[kwargs.org].moid, 'ObjectType': 'organization.Organization'},
            'OsduImage': {'Moid': v.scu, 'ObjectType': 'firmware.ServerConfigurationUtilityDistributable'},
            'OverrideSecureBoot': True,
            'Server': {'Moid': v.hardware_moid, 'ObjectType': v.object_type}}
        ad = kwargs.imm_dict.wizard.azure_stack[0].active_directory
        answers_dict = {
            #'.azure_stack_ou': f'OU={ad.azure_stack_ou},DC=' + ad.domain.replace('.', ',DC='),
            #'.domain': ad.domain,
            #'.azure_stack_lcm_user': ad.azure_stack_lcm_user.split('@')[0],
            '.hostname': v.name,
            '.interface_1_identifier': f'SlotID {vnics[0]} Port 1',
            '.interface_2_identifier': f'SlotID {vnics[0]} Port 2',
            '.ntp_server': kwargs.ntp_servers[0],
            '.organization': kwargs.imm_dict.wizard.azure_stack[0].organization,
            #'.secure.azure_stack_lcm_password': kwargs.azure_stack_lcm_password,
            '.secure.local_administrator_password': kwargs.local_administrator_password,
            #'.macAddressNic1_dash_format': mac_a,
            #'.macAddressNic2_dash_format': mac_b
            # Language Pack/Localization
            '.input_locale': kwargs.language.input_locale,
            '.language_pack': kwargs.language.ui_language,
            '.layered_driver': kwargs.language.layered_driver,
            '.secondary_language': kwargs.language.secondary_language}
            # Timezone Configuration
            #'.disable_daylight_savings': kwargs.disable_daylight,
            #'.timezone': kwargs.windows_timezone}
        answers_dict = dict(sorted(answers_dict.items()))
        for e in ['layered_driver', 'secondary_language']:
            if kwargs.language[e] == '': answers_dict.pop(f'.{e}')
        for key,value in answers_dict.items(): api_body['AdditionalParameters'].append(self.installation_body_os_placeholders(key, value))
        return api_body

    #=============================================================================
    # Function - OS Install Custom Template Parameters Map
    #=============================================================================
    def installation_body_os_placeholders(self, key, value):
        if 'secure' in key: secure = True
        else: secure = False
        if len(value) == 0: is_set = False
        else: is_set = True
        parameters = {
            'ClassId': 'os.PlaceHolder',
            'IsValueSet': is_set,
            'ObjectType': 'os.PlaceHolder',
            'Type': {
                'ClassId': 'workflow.PrimitiveDataType',
                'Default': {
                    'ClassId': 'workflow.DefaultValue',
                    'IsValueSet': False,
                    'ObjectType': 'workflow.DefaultValue',
                    'Override': False,
                    'Value': None},
                'Description': '',
                'DisplayMeta': {
                    'ClassId': 'workflow.DisplayMeta',
                    'InventorySelector': True,
                    'ObjectType': 'workflow.DisplayMeta',
                    'WidgetType': 'None'},
                'InputParameters': None,
                'Label': key,
                'Name': key,
                'ObjectType': 'workflow.PrimitiveDataType',
                'Properties': {
                    'ClassId': 'workflow.PrimitiveDataProperty',
                    'Constraints': {
                        'ClassId': 'workflow.Constraints',
                        'EnumList': [],
                        'Max': 0,
                        'Min': 0,
                        'ObjectType': 'workflow.Constraints',
                        'Regex': ''},
                    'InventorySelector': [],
                    'ObjectType': 'workflow.PrimitiveDataProperty',
                    'Secure': secure,
                    'Type': 'string'},
                'Required': False},
            'Value': value}
        return parameters

    #=============================================================================
    # Function - Build api_body for Operating System Installation - VMware
    #=============================================================================
    def installation_body_vmware(self, v, kwargs):
        api_body = {
            'AdditionalParameters': None,
            'Answers': {
                'AlternateNameServers': [],
                'Hostname': f'{v.name}.{kwargs.dns_domains[0]}',
                'IpConfigType': 'static',
                'IpConfiguration': {
                    'IpV4Config': {
                        'Gateway': v.inband.gateway,
                        'IpAddress': v.inband.ip,
                        'Netmask': v.inband.netmask,
                        'ObjectType': 'comm.IpV4Interface'},
                    'ObjectType': 'os.Ipv4Configuration'},
                'IsRootPasswordCrypted': False,
                'Nameserver': kwargs.dns_servers[0],
                'NetworkDevice': kwargs.mac_a,
                'ObjectType': 'os.Answers',
                'RootPassword': kwargs.vmware_esxi_password,
                'Source': 'Template'},
            'ConfigurationFile': {'Moid': kwargs.os_cfg_moid, 'ObjectType': 'os.ConfigurationFile'},
            'Image': {'Moid': kwargs.os_sw_moid, 'ObjectType': 'softwarerepository.OperatingSystemFile'},
            'InstallMethod': 'vMedia',
            'InstallTarget': {},
            'ObjectType': 'os.Install',
            'Organization': {'Moid': kwargs.org_moid, 'ObjectType': 'organization.Organization'},
            'OsduImage': {'Moid': kwargs.scu_moid, 'ObjectType': 'firmware.ServerConfigurationUtilityDistributable'},
            'OverrideSecureBoot': True,
            'Server': {'Moid': v.hardware_moid, 'ObjectType': v.object_type}}
        if len(kwargs.dns_servers) > 0:
            api_body['Answers']['AlternateNameServers'] = [kwargs.dns_servers[1]]
        return api_body

    #=============================================================================
    # Function - Obtain Windows Language Dictionary
    #=============================================================================
    def windows_languages(windows_language, kwargs):
        kwargs.windows_languages = json.load(open(os.path.join(kwargs.script_path, 'variables', 'windowsLocals.json'), 'r'))
        language = [e for e in kwargs.windows_languages if (
            (DotMap(e)).language.replace('(', '_')).replace(')', '_') == (windows_language.language_pack.replace('(', '_')).replace(')', '_')]
        if len(language) == 1: language = DotMap(language[0])
        else:
            pcolor.Red(f'Failed to Map `{windows_language.language_pack}` to a Windows Language.')
            pcolor.Red(f'Available Languages are:')
            for e in kwargs.windows_languages: pcolor.Red(f'  * {(DotMap(e)).language}')
            len(False); sys.exit(1)
        kwargs.language = DotMap(
            ui_language        = language.code,
            input_locale       = (re.search('\\((.*)\\)', language.local)).group(1),
            layered_driver     = windows_language.layered_driver,
            secondary_language = '')
        if language.get('secondary_language'):
            if type(language.secondary_language) == list:
                kwargs.language.secondary_language   = language.secondary_language[0]
            else: kwargs.language.secondary_language = language.secondary_language
        if kwargs.language.layered_driver == 0: kwargs.language.layered_driver = ''
        return kwargs

    #=============================================================================
    # Function - Obtain Windows Timezone
    #=============================================================================
    def windows_timezones(kwargs):
        kwargs.windows_timezones = DotMap(json.load(open(os.path.join(kwargs.script_path, 'variables', 'windowsTimeZones.json'), 'r')))
        tz = pytz.timezone(kwargs.timezone)
        june = pytz.utc.localize(datetime(2023, 6, 2, 12, 1, tzinfo=None))
        december = pytz.utc.localize(datetime(2023, 12, 2, 12, 1, tzinfo=None))
        june_dst = june.astimezone(tz).dst() != timedelta(0)
        dec_dst  = december.astimezone(tz).dst() != timedelta(0)
        if june_dst == True and dec_dst == False: kwargs.disable_daylight = 'false'
        elif june_dst == False and dec_dst == True: kwargs.disable_daylight = 'false'
        elif june_dst == False and dec_dst == False: kwargs.disable_daylight = 'true'
        else:
            pcolor.Red(f'unknown Timezone Result for {kwargs.timezone}')
            len(False); sys.exit(1)
        windows_timezone = [k for k, v in kwargs.windows_timezones.items() if v == kwargs.timezone]
        if len(windows_timezone) == 1: kwargs.windows_timezone = windows_timezone[0]
        else:
            pcolor.Red(f'Failed to Map `{kwargs.timezone}` to a Windows Timezone.')
            pcolor.Red(f'Available Timezones are:')
            for k,v in kwargs.windows_timezones.items(): pcolor.Red(f'  * {k}: {v}')
            len(False); sys.exit(1)
        return kwargs

