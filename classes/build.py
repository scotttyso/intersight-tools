#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, isight, pcolor, questions
    from copy import deepcopy
    from dotmap import DotMap
    import crypt, ipaddress, json, inflect, os, re, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
#=======================================================
# Build IMM Policies
#=======================================================
class intersight(object):
    def __init__(self, type):
        self.type = type

    #=================================================================
    # Function: Create Profile YAML from Source
    #=================================================================
    def create_profile_from_source(self, item, kwargs):
        pvars = DotMap()
        if self.type == 'server_template':
            pvars['create_template'] = False
            pvars['name'] = item.Name
        else: pvars['targets'] = []
        pvars['target_platform'] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform
        if item.PolicyBucket:
            kwargs.method = 'get_by_moid'
            for e in item.PolicyBucket:
                key_id       = [k for k, v in kwargs.ezdata.items() if v.ObjectType == e.ObjectType][0]
                kwargs.pmoid = e.Moid
                kwargs.uri   = kwargs.ezdata[key_id].intersight_uri
                kwargs       = isight.api(key_id).calls(kwargs)
                pvars[f'{key_id}_policy'] = kwargs.results.Name
        if item.Tags: pvars['tags'] = item.Tags
        if item.UuidAddressType == 'POOL':
            kwargs.pmoid       = item.UuidPool.Moid
            kwargs.uri         = kwargs.ezdata.uuid.intersight_uri
            kwargs             = isight.api('uuid').calls(kwargs)
            pvars['uuid_pool'] = kwargs.results.Name
        pvars = DotMap(dict(sorted(pvars.toDict().items())))
        # Return pvars
        return pvars

    #=================================================================
    # Function: Domain Discovery
    #=================================================================
    def domain_discovery(self, kwargs):
        #=======================================================
        # Obtain List of Physical Domains
        #=======================================================
        kwargs.api_filter = "PlatformType in ('UCSFIISM')"
        kwargs.method     = 'get'
        kwargs.uri        = 'asset/DeviceRegistrations'
        kwargs = isight.api('device_registrations').calls(kwargs)
        domains = kwargs.results
        names = [e.DeviceHostname[0] for e in domains]
        names.sort()
        kwargs.jdata = DotMap(
            default     = names[0],
            enum        = names,
            description = 'Select the Physical Domain to configure.',
            title       = 'Physical Domain',
            type        = 'string')
        phys_domain = ezfunctions.variable_prompt(kwargs)
        indx = next((index for (index, d) in enumerate(domains) if d['DeviceHostname'][0] == phys_domain), None)
        kwargs.domain = DotMap(
            moid    = domains[indx].Moid,
            name    = domains[indx].DeviceHostname[0],
            serials = domains[indx].Serial,
            type    = domains[indx].Pid[0])
        #=======================================================
        # Domain Profile name
        #=======================================================
        kwargs.jdata             = kwargs.ezdata.abstract_profile.properties.name
        kwargs.jdata.description = 'Domain Profile Name\n\n' + kwargs.jdata.description
        kwargs.jdata.default     = kwargs.domain.name
        kwargs.domain.name       = ezfunctions.variable_prompt(kwargs)
        #=======================================================
        # Confirm Domain is Assigned to the Organization
        #=======================================================
        kwargs.method     = 'get_by_moid'
        kwargs.pmoid      = kwargs.org_moids[kwargs.org].moid
        kwargs.uri        = 'organization/Organizations'
        kwargs = isight.api(self.type).calls(kwargs)
        resource_groups = [e.Moid for e in kwargs.results.ResourceGroups]
        kwargs.method     = 'get'
        kwargs.names      = resource_groups
        kwargs.uri        = 'resource/Groups'
        kwargs = isight.api('resource_groups').calls(kwargs)
        if len(resource_groups) > 1:
            names = [e.Name for e in kwargs.results]
            names.sort()
            kwargs.jdata = DotMap(
                default     = names[0],
                enum        = names,
                description = f'Select the Resource Group in organization `{kwargs.org}` to Assign `{kwargs.domain.name}`.',
                title       = 'Organization Resource Group',
                type        = 'string')
            resource_group = ezfunctions.variable_prompt(kwargs)
            indx = next((index for (index, d) in enumerate(kwargs.results) if d['Name'] == resource_group), None)
            rgroup = kwargs.results[indx]
        else: rgroup = kwargs.results[0]
        if not rgroup.Qualifier == 'Allow-All':
            if not kwargs.domain.moid in rgroup.Selectors[0].Selector:
                flist = re.search(r'\(([\'a-z0-9, ]+)\)', rgroup.Selectors[0].Selector).group(1)
                flist = [(e.replace("'", "")).replace(' ', '') for e in flist.split(',')]
                flist.append(kwargs.domain.moid)
                flist.sort()
                flist = "', '".join(flist).strip("', '")
                idict = rgroup.Selectors
                idict[0].Selector = f"/api/v1/asset/DeviceRegistrations?$filter=(Moid in ('{flist}'))"
                kwargs.api_body = {'Selectors':[e.toDict() for e in idict]}
                kwargs.method   = 'patch'
                kwargs.pmoid    = rgroup.Moid
                kwargs = isight.api('resource_group').calls(kwargs)
            else: pcolor.Cyan(f'\n   Domain already assigned to Organization `{kwargs.org}` Resource Group `{rgroup.Name}`\n')
        #=======================================================
        # Query for Physical Ports with Optics Installed
        #=======================================================
        for e in ['ether', 'fc']:
            kwargs.api_filter = f"RegisteredDevice.Moid eq '{kwargs.domain.moid}'"
            kwargs.build_skip = True
            kwargs.method     = 'get'
            kwargs.uri        = f'{e}/PhysicalPorts'
            kwargs = isight.api('physical_ports').calls(kwargs)
            kwargs[f'{e}_results'] = kwargs.results
        kwargs.eth_ports = []
        kwargs.fc_ports = []
        for i in ['ether_results', 'fc_results']:
            for e in kwargs[i]:
                if ('FC' in e.TransceiverType or 'sfp' in e.TransceiverType) and e.SwitchId == 'A':
                    kwargs.fc_ports.append(DotMap(breakout_port_id = e.AggregatePortId, moid = e.Moid, port_id = e.PortId, slot_id = e.SlotId, transceiver = e.TransceiverType))
                elif e.TransceiverType != 'absent' and e.SwitchId == 'A':
                    kwargs.eth_ports.append(DotMap(breakout_port_id = e.AggregatePortId, moid = e.Moid, port_id = e.PortId, slot_id = e.SlotId, transceiver = e.TransceiverType))
        #=======================================================
        # Configure Fibre-Channel if FC Optics Found
        #=======================================================
        if len(kwargs.fc_ports) > 0:
            # Converted Port List
            kwargs = questions.port_mode_fc(kwargs)
            kwargs.domain.port_modes = []
            kwargs.domain.port_modes.append(kwargs.port_modes)
            # FC Switching Mode
            kwargs.jdata             = kwargs.ezdata.switch_control.allOf[1].properties.fc_switching_mode
            kwargs.jdata.description = 'Configure FC Switching Mode\n\n' + kwargs.jdata.description
            fc_sw_mode               = ezfunctions.variable_prompt(kwargs)
            kwargs.domain.sw_ctrl    = fc_sw_mode
            print(json.dumps(kwargs.domain, indent=4))
            # FC Connections
            kwargs.jdata = DotMap(
                default     = 'port_channel',
                enum        = ['port_channel', 'storage_appliance', 'uplink'],
                description = f'What type of Interfaces do you want to configure for the Fibre-Channel Ports?',
                title       = 'Uplink Type',
                type        = 'string')
            if fc_sw_mode == 'end-host': kwargs.jdata.enum.pop('storage_appliance')
            else: kwargs.jdata.multi_select = True
            uplink_types  = ezfunctions.variable_prompt(kwargs)
            if fc_sw_mode == 'end-host': uplink_types = [uplink_types]
            for e in uplink_types:
                if e == 'port_channel': questions.fc_port_channels(kwargs)
                elif e == 'uplink': questions.fc_uplink_ports(kwargs)
                else: questions.fc_storage_ports(kwargs)
            #if uplink_type == 'port_channel':
        return kwargs

    #=================================================================
    # Function: Main Menu, Prompt User for Policy Elements
    #=================================================================
    def ezimm(self, kwargs):
        idata = deepcopy(DotMap(dict(pair for d in kwargs.ezdata[self.type].allOf for pair in d.properties.items())))
        if kwargs.build_type == 'Machine':
            if re.search('ip|iqn|mac|wwnn|wwpn', self.type): pop_list = ['assignment_order', 'description', 'name', 'tags']
            for p in pop_list: idata.pop(p)
        ptype = kwargs.ezdata[self.type].intersight_type

        kwargs.configure_more = True
        if kwargs.imm_dict[kwargs.org][ptype].get(self.type):
            kwargs = questions.existing_object(ptype, self.type, kwargs)
        if kwargs.configure_more == True:
            ilist = []
            kwargs.loop_count = 0
            if kwargs.build_type == 'Machine': config_object = True
            else: config_object = questions.prompt_user_to_configure(self.type, ptype, kwargs)
            while config_object == True:
                idict = DotMap()
                for k, v in idata.items():
                    if re.search('boolean|integer|string', v.type):
                        idict[k] = questions.prompt_user_item(k, v, kwargs)
                    elif v.type == 'array':
                        kwargs.inner_count = 0
                        if k in v.required: config_inner = True
                        else: config_inner = questions.prompt_user_for_sub_item(k, kwargs)
                        while config_inner == True:
                            if not idict.get(k): idict[k] = []
                            edict = DotMap()
                            for a,b in v['items'].properties.items():
                                if re.search('boolean|integer|string', b.type) and a != 'size':
                                    edict[a] = questions.prompt_user_item(a, b, kwargs)
                            accept = questions.prompt_user_to_accept(k, edict, kwargs)
                            additional = questions.promp_user_to_add(k, kwargs)
                            if accept == True: idict[k].append(edict)
                            if additional == False: config_inner = False
                            kwargs.inner_count += 1
                    elif v.type == 'object':
                        if k in v.required: config = True
                        else: config = questions.prompt_user_for_sub_item(k, kwargs)
                        while config == True:
                            edict = DotMap()
                            for a,b in v.properties.items():
                                if re.search('boolean|integer|string', b.type):
                                    edict[a] = questions.prompt_user_item(a, b, kwargs)
                            accept = questions.prompt_user_to_accept(k, edict, kwargs)
                            if accept == True: idict[k] = edict; config = False
                accept = questions.prompt_user_to_accept(self.type, idict, kwargs)
                additional = questions.promp_user_to_add(self.type, kwargs)
                if accept == True: ilist.append(idict)
                if additional == False: config_object = False
                kwargs.loop_count += 1
            kwargs.imm_dict.orgs[kwargs.org][ptype][self.type] = ilist
        return kwargs

    def os_configuration_answers(kwargs):
        #rows = []
        #for e in kwargs.os_cfg.Placeholders:
        #    rows.append([f'Label: {e.Type.Label}', f'Name: {e.Type.Name}', f'Sensitive: {e.Type.Properties.Secure}', f'Required: {e.Type.Required}'])
        #cwidth = max(len(word) for row in rows for word in row) + 2
        #prows = []
        #for row in rows:
        #    prows.append("".join(word.ljust(cwidth) for word in row))
        #prows.sort()
        #for row in prows: print(row)
        #exit()
        valid_answers = False
        while valid_answers == False:
            #=======================================================
            # Function: Add Keys to Server Profile answers dict
            #=======================================================
            def add_to_server_dict(variable, answer, kwargs):
                for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
                    e.answers[variable] = answer
                return kwargs
            kwargs.server_profiles = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles
            sprofile = kwargs.server_profiles[0]
            #=======================================================
            # Process for Intersight defined OS Configuration
            #=======================================================
            answers = [e.Type.Name for e in kwargs.os_cfg.Placeholders]
            if 'shared' in kwargs.os_cfg.Owners:
                #=======================================================
                # Boot Parameters
                #=======================================================
                for x in range(0,len(kwargs.server_profiles)):
                    boot_order = kwargs.server_profiles[x].boot_order
                    if '.answers.BootMode' in answers:
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers['.answers.BootMode'] = boot_order.boot_mode
                    if '.answers.SecureBoot' in answers:
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers['.answers.SecureBoot'] = boot_order.enable_secure_boot
                #=======================================================
                # RootPassword
                #=======================================================
                if '.answers.RootPassword' in answers:
                    kwargs.jdata             = kwargs.ezdata.sensitive_variables.properties.root_password
                    if sprofile.os_vendor == 'Microsoft':
                        kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE Root', 'Windows Login')
                        kwargs.jdata.title = 'Windows Login Password'
                    else: kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', sprofile.os_vendor)
                    kwargs.sensitive_var = 'root_password'
                    kwargs               = ezfunctions.sensitive_var_value(kwargs)
                    kwargs               = add_to_server_dict('.answers.RootPassword', 'sensitive_root_password', kwargs)
                    root_password        = kwargs.var_value
                    os.environ['root_password'] = crypt.crypt(root_password, crypt.mksalt(crypt.METHOD_SHA512))
                    if sprofile.os_vendor == 'Microsoft':
                        kwargs               = add_to_server_dict('.answers.LogonPassword', 'sensitive_logon_password', kwargs)
                        os.environ['logon_password'] = crypt.crypt(root_password, crypt.mksalt(crypt.METHOD_SHA512))
                #=======================================================
                # Host FQDN
                #=======================================================
                if '.answers.FQDN' in answers or '.answers.Hostname' in answers:
                    for x in range(0,len(kwargs.server_profiles)):
                        kwargs.jdata             = kwargs.ezwizard.os_configuration.properties.fqdn
                        kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', kwargs.server_profiles[x].name)
                        if x == 0: kwargs.jdata.default = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].name
                        else: kwargs.jdata.default = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].name + '.' + fqdn
                        host_fqdn = ezfunctions.variable_prompt(kwargs)
                        fqdn      = host_fqdn[len(host_fqdn.split('.')[0])+1:]
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers['.answers.FQDN']     = host_fqdn
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers['.answers.Hostname'] = host_fqdn.split('.')[0]
                #=======================================================
                # DHCP or static IP configuration
                #=======================================================
                if '.answers.IpConfigType' in answers:
                    kwargs.jdata   = kwargs.ezwizard.os_configuration.properties.ip_config_type
                    ip_config_type = ezfunctions.variable_prompt(kwargs)
                    kwargs         = add_to_server_dict('.answers.IpConfigType', ip_config_type, kwargs)
                #=======================================================
                # Static IP Configuration
                #=======================================================
                if ip_config_type == 'static':
                    kwargs.jdata             = kwargs.ezwizard.os_configuration.properties.ip_version
                    ip_version               = ezfunctions.variable_prompt(kwargs)
                    kwargs                   = add_to_server_dict('.answers.IpVersion', ip_version, kwargs)
                    kwargs.jdata             = kwargs.ezwizard.os_configuration.properties.network_interface
                    kwargs.jdata.enum        = [f'Name: {e.name} MAC Address: {e.mac}' for e in kwargs.server_profiles[0].macs]
                    kwargs.jdata.default     = kwargs.jdata.enum[0]
                    kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', kwargs.server_profiles[0].name)
                    network_interface        = ezfunctions.variable_prompt(kwargs)
                    mregex                   = re.compile(r'MAC Address: ([0-9a-fA-F\:]+)$')
                    match                    = mregex.search(network_interface)
                    mac                      = match.group(1)
                    indx                     = next((index for (index, d) in enumerate(kwargs.server_profiles[0].macs) if d['mac'] == mac), None)
                    #=======================================================
                    # Assign MAC Address to answers
                    #=======================================================
                    if '.answers.NetworkDevice' in answers:
                        for x in range(0,len(kwargs.server_profiles)):
                            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers['.answers.NetworkDevice'] = kwargs.server_profiles[x].macs[indx].mac
                    if '.MACAddress' in answers:
                        for x in range(0,len(kwargs.server_profiles)):
                            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers['.MACAddress'] = kwargs.server_profiles[x].macs[indx].mac
                    #=======================================================
                    # Prompt for Gateway, Netmask/Prefix, and DNS
                    #=======================================================
                    for key in list(kwargs.ezdata[f'ip.ip{ip_version.lower()}_configuration'].properties.keys()):
                        kwargs.jdata = kwargs.ezdata[f'ip.ip{ip_version.lower()}_configuration'].properties[key]
                        if key == 'gateway':
                            kwargs.jdata.description = 'Default Gateway to configure.'
                        kwargs[key] = ezfunctions.variable_prompt(kwargs)
                        if re.search('gateway|netmask|prefix', key) and f'.answers.Ip{ip_version.lower()}Config.{key.capitalize()}' in answers:
                            kwargs = add_to_server_dict(f'.answers.Ip{ip_version.lower()}Config.{key.capitalize()}', kwargs[key], kwargs)
                        elif 'primary_dns' == key and '.answers.NameServer' in answers:
                            kwargs = add_to_server_dict('.answers.NameServer', kwargs[key], kwargs)
                        elif 'secondary_dns' == key and '.answers.AlternateNameServer' in answers:
                            kwargs = add_to_server_dict('.answers.AlternateNameServer', kwargs[key], kwargs)
                    #=======================================================
                    # Prompt for Server IP Address's
                    #=======================================================
                    for x in range(0,len(kwargs.server_profiles)):
                        kwargs.jdata             = kwargs.ezdata[f'ip.ip{ip_version.lower()}_configuration'].properties.gateway
                        kwargs.jdata.description = f'{kwargs.server_profiles[x].fqdn} IP{ip_version.lower()} Address.'
                        kwargs.jdata.title       = f'IP{ip_version.lower()} Address'
                        if x > 0: kwargs.jdata.default = network_list[indx+1]
                        ip_address = ezfunctions.variable_prompt(kwargs)
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers[f'.answers.Ip{ip_version.lower()}.IpAddress'] = ip_address
                        if x == 0:
                            if f'IP{ip_version.lower()}' == 'IPv4':
                                netmask = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers['.answers.IpV4Config.Netmask']
                                network_list = [str(address) for address in ipaddress.IPv4Network(f'{ip_address}/{netmask}')]
                            else:
                                prefix = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers['.answers.IpV6Config.Prefix']
                                network_list = [str(address) for address in ipaddress.IPv6Network(f'{ip_address}/{prefix}')]
                        indx = network_list.index(ip_address)
            #=======================================================
            # Process for User defined OS Configuration
            #=======================================================
            else:
                for a in range(0,len(answers)):
                    adict = kwargs.os_cfg.Placeholders[a]
                    kwargs.jdata = DotMap()
                    if adict.Type.Default.Value == None: kwargs.jdata.default = ''
                    else: kwargs.jdata.default = adict.Type.Default.Value
                    kwargs.jdata.description = adict.Type.Description
                    kwargs.jdata.type        = adict.Type.Properties.Type
                    kwargs.jdata.title       = adict.Type.Label
                    if kwargs.jdata.type == 'integer':
                        kwargs.jdata.maximum = adict.Type.Properties.Constraints.Max
                        kwargs.jdata.minimum = adict.Type.Properties.Constraints.Min
                    elif kwargs.jdata.type == 'string':
                        kwargs.jdata.maxLength = adict.Type.Properties.Constraints.Max
                        kwargs.jdata.minLength = adict.Type.Properties.Constraints.Min
                        kwargs.jdata.pattern   = adict.Type.Properties.Constraints.Regex
                        if len(adict.Type.Properties.Constraints.EnumList) > 0:
                            kwargs.jdata.default = adict.Type.Properties.Constraints.EnumList[0]
                            kwargs.jdata.enum    = adict.Type.Properties.Constraints.EnumList
                    #=======================================================
                    # Sensitive Variables
                    #=======================================================
                    if adict.Type.Properties.Secure:
                        kwargs.sensitive_var = f'undefined_{a}'
                        kwargs               = ezfunctions.sensitive_var_value(kwargs)
                        kwargs               = add_to_server_dict('.answers.RootPassword', 'sensitive_root_password', kwargs)
                        os.environ[a]        = kwargs.var_value
                        kwargs               = add_to_server_dict(a, f'sensitive_{a}', kwargs)
                    #=======================================================
                    # All other Variables
                    #=======================================================
                    elif 'shared_variable' in adict.Type.Description:
                        answer = ezfunctions.variable_prompt(kwargs)
                        kwargs = add_to_server_dict(a, answer, kwargs)
                    else:
                        for e in kwargs.server_profiles:
                            kwargs.jdata.description = adict.Type.Description + f'for Server Profile `{kwargs.server_profiles[e]}`.'
                            if x > 0: kwargs.jdata.default = answer
                            answer = ezfunctions.variable_prompt(kwargs)
                            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers[a] = answer
            #=======================================================
            # Prompt User to Accept Configuration
            #=======================================================
            idict = DotMap(answers = [])
            for x in range(0,len(kwargs.server_profiles)):
                answers = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.toDict()
                kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers = DotMap(dict(sorted(answers)))
                server = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x]
                idict.answers.append(dict(answers=server.answers,server_profile=server.name))
            print(json.dumps(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles, indent=4))
            accept = questions.prompt_user_to_accept('os_configuration_answers', idict, kwargs)
            if accept == True: valid_answers = True
        # Return kwargs
        return kwargs

    #=================================================================
    # Function: Main Menu, Profile Deployment
    #=================================================================
    def profiles(self, kwargs):
        kwargs.models = ['UCSC-C240-M6', 'UCSC-C240-M7']
        os     = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems[0]
        if not kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            #if kwargs.imm_dict.orgs[kwargs.org].profile.server: kwargs.imm_dict.orgs[kwargs.org].pop('profile')
            accept_profiles = False
            while accept_profiles == False:
                #=======================================================
                # Obtain Physical Servers
                #=======================================================
                api_filter = f"PermissionResources.Moid eq '{kwargs.org_moids[kwargs.org].moid}' and ManagementMode eq "
                if self.type == 'FIAttached': kwargs.api_filter = api_filter + f"'Intersight'"
                else: kwargs.api_filter = api_filter + f"'IntersightStandalone'"
                kwargs.method     = 'get'
                kwargs.uri        = 'compute/PhysicalSummaries'
                kwargs = isight.api('physical_servers').calls(kwargs)
                physical_servers = kwargs.pmoids
                physical_results = kwargs.results
                physical_compute = []
                #=======================================================
                # Prompt user for Boot Mode and Profile Source
                #=======================================================
                kwargs.jdata       = kwargs.ezwizard.server.properties.boot_volume
                kwargs.boot_volume = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata       = kwargs.ezwizard.server.properties.profile_source
                profile_type       = ezfunctions.variable_prompt(kwargs)
                kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_type = profile_type
                #=======================================================
                # Get Existing Profiles or Templates
                #=======================================================
                if kwargs.imm_dict.orgs[kwargs.org].wizard.setup.get('shared_org'):
                    shared_org = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.shared_org
                    kwargs.api_filter = f"TargetPlatform eq '{self.type}' and Organization.Moid in ('{kwargs.org_moids[kwargs.org].moid}', '{kwargs.org_moids[shared_org].moid}')"
                else: kwargs.api_filter = f"TargetPlatform eq '{self.type}' and Organization.Moid eq '{kwargs.org_moids[kwargs.org].moid}'"
                kwargs.method     = 'get'
                kwargs.uri        = kwargs.ezdata[profile_type].intersight_uri
                kwargs = isight.api('server').calls(kwargs)
                source_results    = kwargs.results
                kwargs.api_filter = f"TargetPlatform eq '{self.type}' and Organization.Moid eq '{kwargs.org_moids[kwargs.org].moid}'"
                kwargs.method     = 'get'
                kwargs.uri        = kwargs.ezdata['server'].intersight_uri
                kwargs = isight.api('server').calls(kwargs)
                profile_results   = kwargs.results
                #=======================================================
                # Prompt user for Profile Source
                #=======================================================
                names = sorted([f'{kwargs.org_names[e.Organization.Moid]}/{e.Name}' for e in source_results])
                kwargs.jdata = DotMap(
                    default     = names[0],
                    enum        = names,
                    description = 'Select the existing profile to use.',
                    title       = 'Profile Source',
                    type        = 'string')
                profile_source = ezfunctions.variable_prompt(kwargs)
                kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_source = profile_source
                #=======================================================
                # Prompt user for Profile Count
                #=======================================================
                kwargs.jdata = kwargs.ezwizard.server.properties.profile_count
                pcount = int(ezfunctions.variable_prompt(kwargs))
                #=======================================================
                # Remove Servers already assigned to profiles
                #=======================================================
                physical_moids = DotMap()
                for k, v in physical_servers.items(): physical_moids[v.moid] = DotMap(dict(v.toDict(), **{'serial':k}))
                physical_servers = physical_servers.toDict()
                phys_keys = list(physical_moids.keys())
                for e in profile_results:
                    if e.AssignedServer != None and e.AssignedServer.Moid in phys_keys:
                        physical_servers.pop(physical_moids[e.AssignedServer.Moid].serial)
                physical_servers = DotMap(physical_servers)
                #=======================================================
                # Prompt user for Server Profile Data
                #=======================================================
                assignment_map = physical_servers.toDict()
                cvt = inflect.engine()
                for x in range(0,pcount):
                    server_list = []
                    assignment_map = DotMap({k: v for k, v in sorted(assignment_map.items(), key=lambda item: (item[1]['name']))})
                    for k, v in assignment_map.items():
                        server_list.append(f'Serial: {k}, Name: {v.name}, ObjectType: {v.object_type}')
                    server_list = sorted(server_list)
                    kwargs.jdata = deepcopy(kwargs.ezwizard.server.properties.profile_name)
                    if x == 0:
                        name = ezfunctions.variable_prompt(kwargs)
                        if pcount > 1:
                            kwargs.jdata = kwargs.ezwizard.server.properties.profile_suffix
                            kwargs.jdata.description = kwargs.jdata.description.replace('Example', name)
                            suffix = ezfunctions.variable_prompt(kwargs)
                        else: suffix = 2
                        pprefix = name[:-(int(suffix))]
                        pstart  = int(name[-int(suffix):])
                    else:
                        if pcount > 1 and x > 0:
                            pprefix = name[:-(int(suffix))]
                            pstart  = int(name[-int(suffix):])
                        kwargs.jdata.description = kwargs.jdata.description.replace('First', (cvt.number_to_words(cvt.ordinal(x+1))).capitalize())
                        kwargs.jdata.title = kwargs.jdata.title.replace('First', (cvt.number_to_words(cvt.ordinal(x+1))).capitalize())
                        kwargs.jdata.default = f"{pprefix}{str(pstart+1).zfill(int(suffix))}"
                        name = ezfunctions.variable_prompt(kwargs)
                    if len(server_list) > 0:
                        kwargs.jdata         = kwargs.ezwizard.server.properties.physical_server
                        kwargs.jdata.default = server_list[0]
                        kwargs.jdata.enum    = server_list
                        pserver = ezfunctions.variable_prompt(kwargs)
                        serial  = re.search(r'Serial: ([A-Z0-9]+), Name', pserver).group(1)
                        indx = next((index for (index, d) in enumerate(physical_results) if d['Serial'] == serial), None)
                        kwargs.temp_servers[serial].name          = name
                        kwargs.temp_servers[serial].os_vendor     = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems[0].vendor
                        kwargs.temp_servers[serial].os_version    = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems[0].version.toDict()
                        kwargs.temp_servers[serial].template      = profile_source
                        kwargs.temp_servers[serial].template_type = profile_type
                        physical_compute.append(physical_results[indx])
                        assignment_map.pop(serial)
                    else:
                        pcolor.Red(f'\n{"-"*108}\n\n  !!!ERROR!!! Did Not Find Any servers to attach to profile `{name}`')
                        pcolor.Red(f'\n{"-"*108}\n'); sys.exit(1)
                answer = questions.prompt_user_to_accept('profiles', kwargs.temp_servers, kwargs)
                if answer == True: accept_profiles = True
            #=======================================================
            # Build Server Profile Dictionaries
            #=======================================================
            kwargs.results = physical_compute
            kwargs         = isight.api(self.type).build_compute_dictionary(kwargs)
            for k in list(kwargs.servers.keys()):
                kwargs.server_profiles[k] = DotMap(sorted(dict(kwargs.servers[k].toDict(), **kwargs.temp_servers[k].toDict()).items()))
            for k,v in kwargs.server_profiles.items():
                pvars = v.toDict()
                # Add Policy Variables to imm_dict
                kwargs.class_path = f'wizard,server_profiles'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
            #=======================================================
            # Create YAML Files
            #=======================================================
            orgs   = list(kwargs.org_moids.keys())
            kwargs = ezfunctions.remove_duplicates(orgs, ['profiles', 'templates', 'wizard'], kwargs)
            ezfunctions.create_yaml(orgs, kwargs)
        #=================================================================
        # Create Server Profile(s) from Inputs
        #=================================================================
        if not kwargs.imm_dict.orgs[kwargs.org].profile.get('server'):
            #=======================================================
            # Create Profile Dictionary
            #=======================================================
            for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles: kwargs.server_profiles[e.serial] = e
            profile_source = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_source
            profile_type   = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_type
            original_org   = kwargs.org
            kwargs.org     = profile_source.split('/')[0]
            kwargs.method  = 'get'
            kwargs.names   = [profile_source.split('/')[1]]
            kwargs.uri     = kwargs.ezdata[profile_type].intersight_uri
            kwargs         = isight.api(profile_type).calls(kwargs)
            source_results = kwargs.results
            if profile_type == 'server':
                kwargs.org = original_org
                indx       = next((index for (index, d) in enumerate(source_results) if d['Name'] == profile_source), None)
                pvars      = intersight(profile_type).create_profile_from_source(source_results[indx], kwargs)
                for k, v in kwargs.server_profiles.items(): pvars.targets.append(dict(name = v.name, serial = k))
                # Add Profile Variables to imm_dict
                kwargs.class_path = f'profiles,server'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
            else:
                kwargs.org = original_org
                pvars = dict(
                    attach_template     = True,
                    target_platform     = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform,
                    targets             = [dict(name = v.name, serial_number=k) for k, v in kwargs.server_profiles.items()],
                    ucs_server_template = profile_source)
                # Add Profile Variables to imm_dict
                kwargs.class_path = f'profiles,server'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=======================================================
        # Create YAML Files
        #=======================================================
        orgs   = list(kwargs.org_moids.keys())
        kwargs = ezfunctions.remove_duplicates(orgs, ['profiles', 'templates', 'wizard'], kwargs)
        ezfunctions.create_yaml(orgs, kwargs)
        if profile_type == 'server_template_dummy':
            original_org   = kwargs.org
            kwargs.org     = profile_source.split('/')[0]
            kwargs.method  = 'get'
            kwargs.names   = [profile_source.split('/')[1]]
            kwargs.uri     = kwargs.ezdata[profile_type].intersight_uri
            kwargs         = isight.api(profile_type).calls(kwargs)
            source_results = kwargs.results
            for e in kwargs.results: kwargs.isight[kwargs.org].profile['server_template'][e.Name] = e.Moid
            # Create Template pvars
            indx  = next((index for (index, d) in enumerate(source_results) if d['Name'] == profile_source.split('/')[1]), None)
            kwargs.org = original_org
            pvars      = intersight(profile_type).create_profile_from_source(source_results[indx], kwargs)
            kwargs.org = profile_source.split('/')[0]
            # Add Profile Variables to imm_dict
            kwargs.class_path = f'templates,server'
            kwargs            = ezfunctions.ez_append(pvars, kwargs)
            kwargs.org        = original_org
        #=======================================================
        # Create Profile in Intersight and Get Identities
        #=======================================================
        kwargs.temp_templates = DotMap()
        #kwargs = isight.imm('server').profiles(kwargs)
        for e in list(kwargs.imm_dict.orgs.keys()):
            if kwargs.imm_dict.orgs[e].get('templates'):
                kwargs.temp_templates[e].templates = kwargs.imm_dict.orgs[e].templates
                kwargs.imm_dict.orgs[e].pop('templates')
        identity_check = False
        for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            if not (e.get('macs') and len(e.macs) > 0): identity_check = True
        if identity_check == False:
            kwargs = isight.api('wizard').build_server_identities(kwargs)
        #=======================================================
        # Create YAML Files
        #=======================================================
        kwargs = questions.sw_repo_os_cfg(os, kwargs)
        kwargs = questions.sw_repo_os_image(os, kwargs)
        kwargs = questions.sw_repo_scu(kwargs)
        kwargs = intersight.os_configuration_answers(kwargs)
        #=======================================================
        # Return kwargs
        #=======================================================
        return kwargs

    #=================================================================
    # Function: Main Menu, 
    #=================================================================
    def setup(self, kwargs):
        #=================================================================
        # Loop Thru Wizard Menu for Deployment
        #=================================================================
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.deployment_type = kwargs.deployment_type
        if kwargs.deployment_type == 'Profile':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.assignment_method = 'Serial'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.build_type        = 'Machine'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.deployment_method = 'Python'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery         = True
        elif kwargs.deployment_type == 'Individual':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.assignment_method = 'Serial'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.build_type        = 'Interactive'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery         = False
        elif re.search('FIAttached|Standalone', kwargs.deployment_type):
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform = kwargs.deployment_type
        setup_list = ['build_type', 'deployment_method', 'target_platform', 'assignment_method', 'operating_systems', 'discovery']
        for e in setup_list:
            if not kwargs.imm_dict.orgs[kwargs.org].wizard.setup[e]: kwargs = eval(f'questions.setup_{e}(kwargs)')
            else: kwargs[e] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup[e]
        if re.search('FIAttached|Standalone', kwargs.deployment_type):
            if not 'name_prefix' in list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.keys()): kwargs = questions.setup_name_prefix(kwargs)
            if not 'name_suffix' in list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.keys()): kwargs = questions.setup_name_suffix(kwargs)
            for p in ['pools', 'policies']:
                kwargs.imm_dict.orgs[kwargs.org][p].name_prefix.default = kwargs.name_prefix
                kwargs.imm_dict.orgs[kwargs.org][p].name_suffix.default = kwargs.name_suffix
        #==============================================
        # Create YAML Files
        #==============================================
        orgs = list(kwargs.org_moids.keys())
        ezfunctions.create_yaml(orgs, kwargs)
        #==============================================
        # Build Pool/Policy/Profile List
        #==============================================
        if re.search('FIAttached|Standalone', kwargs.deployment_type): kwargs = questions.build_policy_list(kwargs)
        if 'Individual' in kwargs.deployment_type:
            kwargs = questions.main_menu_individual_types(kwargs)
            kwargs = questions.main_menu_individual(kwargs)
        if re.search('FIAttached', kwargs.deployment_type): kwargs.ptypes = ['Pools', 'Policies', 'Profiles']
        elif re.search('Standalone', kwargs.deployment_type): kwargs.ptypes = ['Policies', 'Profiles']
        if re.search('FIAttached|Standalone', kwargs.deployment_type):
            kwargs = questions.build_policy_list(kwargs)
            if 'Pools' in kwargs.ptypes: kwargs.main_menu_list.extend(kwargs.pool_list)
            if 'Policies' in kwargs.ptypes: kwargs.main_menu_list.extend(kwargs.policy_list)
            if 'Profiles' in kwargs.ptypes:
                if kwargs.target_platform == 'Standalone': kwargs.main_menu_list.extend(['server', 'server_template'])
                else: kwargs.main_menu_list.extend(['chassis', 'domain', 'server', 'server_template'])
            if not 'Resource Pool' == kwargs.imm_dict.orgs[kwargs.org].wizard.assignment_method:
                if 'resource' in kwargs.main_menu_list: kwargs.main_menu_list.remove('resource')
        # Return kwargs
        return kwargs

    #=================================================================
    # Function: Main Menu, Prompt User for Deployment Type
    #=================================================================
    def quick_start(self, kwargs):

        # Return kwargs
        return kwargs