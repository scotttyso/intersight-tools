#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, isight, pcolor, policies, validating, questions
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
        kwargs.top1000    = True
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
        exit()
        return kwargs

    #=================================================================
    # Function: Main Menu, Prompt User for Deployment Type
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

    #=================================================================
    # Function: Main Menu, Prompt User for Deployment Type
    #=================================================================
    def profiles(self, kwargs):
        if not kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            if kwargs.imm_dict.orgs[kwargs.org].profile.server: kwargs.imm_dict.orgs[kwargs.org].pop('profile')
            accept_profiles = False
            while accept_profiles == False:
                #=======================================================
                # Obtain Physical Servers
                #=======================================================
                api_filter = f"PermissionResources.Moid eq '{kwargs.org_moids[kwargs.org].moid}' and ManagementMode eq "
                if self.type == 'FIAttached': kwargs.api_filter = api_filter + f"'Intersight'"
                else: kwargs.api_filter = api_filter + f"'IntersightStandalone'"
                kwargs.method     = 'get'
                kwargs.top1000    = True
                kwargs.uri        = 'compute/PhysicalSummaries'
                kwargs = isight.api('physical_servers').calls(kwargs)
                physical_servers = kwargs.pmoids
                physical_results = kwargs.results
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
                kwargs.api_filter = f"TargetPlatform eq '{self.type}' and Organization.Moid eq '{kwargs.org_moids[kwargs.org].moid}'"
                kwargs.method     = 'get'
                kwargs.top1000    = True
                kwargs.uri        = kwargs.ezdata[profile_type].intersight_uri
                kwargs = isight.api('server').calls(kwargs)
                source_results    = kwargs.results
                kwargs.api_filter = f"TargetPlatform eq '{self.type}' and Organization.Moid eq '{kwargs.org_moids[kwargs.org].moid}'"
                kwargs.method     = 'get'
                kwargs.top1000    = True
                kwargs.uri        = kwargs.ezdata['server'].intersight_uri
                kwargs = isight.api('server').calls(kwargs)
                profile_results   = kwargs.results
                #=======================================================
                # Prompt user for Profile Source
                #=======================================================
                names = sorted([e.Name for e in source_results])
                kwargs.jdata = DotMap(
                    default     = names[0],
                    enum        = names,
                    description = 'Select the existing profile to use.',
                    title       = 'Profile Source',
                    type        = 'string')
                profile_source = ezfunctions.variable_prompt(kwargs)
                kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_source = profile_source
                #=======================================================
                # Prompt user for Profile Count,
                #=======================================================
                kwargs.jdata = kwargs.ezwizard.server.properties.profile_count
                pcount = int(ezfunctions.variable_prompt(kwargs))
                kwargs.jdata = kwargs.ezwizard.server.properties.profile_start
                profile_start = ezfunctions.variable_prompt(kwargs)
                if pcount > 1:
                    kwargs.jdata = kwargs.ezwizard.server.properties.profile_suffix
                    kwargs.jdata.description = f'{kwargs.jdata.description} {profile_start}?'
                    suffix = ezfunctions.variable_prompt(kwargs)
                else: suffix = 2
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
                pprefix        = profile_start[:-(suffix)]
                pstart         = int(profile_start[-(suffix):])
                for x in range(0,pcount):
                    server_list = []
                    assignment_map = DotMap({k: v for k, v in sorted(assignment_map.items(), key=lambda item: (item[1]['name']))})
                    for k, v in assignment_map.items():
                        server_list.append(f'Serial: {k}, Name: {v.name}, ObjectType: {v.object_type}')
                    server_list = sorted(server_list)
                    kwargs.jdata = deepcopy(kwargs.ezwizard.server.properties.profile_name)
                    kwargs.jdata.description = f'{kwargs.jdata.description} {x+1}?'
                    if pcount == 1: kwargs.jdata.default = profile_start
                    else:
                        kwargs.jdata.default = f"{pprefix}{str(pstart+x).zfill(suffix)}"
                        name = ezfunctions.variable_prompt(kwargs)
                    if len(server_list) > 0:
                        kwargs.jdata         = kwargs.ezwizard.server.properties.physical_server
                        kwargs.jdata.default = server_list[0]
                        kwargs.jdata.enum    = server_list
                        pserver = ezfunctions.variable_prompt(kwargs)
                        serial  = re.search(r'Serial: ([A-Z0-9]+), Name', pserver).group(1)
                        indx = next((index for (index, d) in enumerate(physical_results) if d['Serial'] == serial), None)
                        pcolor.Cyan('')
                        pcolor.Cyan(f'   - Pulling Server Inventory for the Server: {serial}')
                        kwargs = isight.api(self.type).build_compute_dictionary(physical_results[indx], kwargs)
                        pcolor.Cyan(f'     Completed Server Inventory for Server: {serial}')
                        pcolor.Cyan('')
                        kwargs.servers[serial].name     = name
                        kwargs.servers[serial].os_type  = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems[0]
                        kwargs.servers[serial].template = profile_source
                        kwargs.servers[serial].template_type = profile_type
                        assignment_map.pop(serial)
                    else:
                        pcolor.Red(f'\n{"-"*108}\n\n  !!!ERROR!!! Did Not Find Any servers to attach to profile `{name}`')
                        pcolor.Red(f'\n{"-"*108}\n'); sys.exit(1)
                answer = questions.prompt_user_to_accept('profiles', kwargs.servers, kwargs)
                if answer == True: accept_profiles = True
            #=======================================================
            # Create YAML Files
            #=======================================================
            kwargs.server_profiles = kwargs.servers
            for k,v in kwargs.server_profiles.items():
                pvars = v.toDict()
                # Add Policy Variables to imm_dict
                kwargs.class_path = f'wizard,server_profiles'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
            orgs   = list(kwargs.org_moids.keys())
            kwargs = ezfunctions.remove_duplicates(orgs, ['profiles', 'templates', 'wizard'], kwargs)
            ezfunctions.create_yaml(orgs, kwargs)
        if not kwargs.imm_dict.orgs[kwargs.org].profile.server:
            #=======================================================
            # Create Profile Dictionary
            #=======================================================
            for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles: kwargs.server_profiles[k] = e
            profile_source = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_source
            profile_type   = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_type
            kwargs.method  = 'get'
            kwargs.names   = [profile_source]
            kwargs.uri     = kwargs.ezdata[profile_type].intersight_uri
            kwargs         = isight.api(profile_type).calls(kwargs)
            source_results = kwargs.results
            if profile_type == 'server':
                indx  = next((index for (index, d) in enumerate(source_results) if d['Name'] == profile_source), None)
                pvars = intersight(profile_type).create_profile_from_source(source_results[indx], kwargs)
                for k, v in kwargs.server_profiles.items(): pvars.targets.append(dict(name = v.name, serial = k))
                # Add Profile Variables to imm_dict
                kwargs.class_path = f'profiles,server'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
            else:
                pvars = dict(
                    attach_template     = True,
                    target_platform     = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform,
                    targets             = [dict(name = v.name, serial_number=k) for k, v in kwargs.server_profiles.items()],
                    ucs_server_template = profile_source)
                # Add Profile Variables to imm_dict
                kwargs.class_path = f'profiles,server'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
                # Create Template pvars
                indx  = next((index for (index, d) in enumerate(source_results) if d['Name'] == profile_source), None)
                pvars = intersight(profile_type).create_profile_from_source(source_results[indx], kwargs)
                # Add Profile Variables to imm_dict
                kwargs.class_path = f'templates,server'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
                # Get Moid for Template
                kwargs.method = 'get'
                kwargs.names  = [profile_source]
                kwargs.uri    = kwargs.ezdata.server_template.intersight_uri
                kwargs = isight.api('server_template').calls(kwargs)
                for e in kwargs.results: kwargs.isight[kwargs.org].profile['server_template'][e.Name] = e.Moid
        #=======================================================
        # Create YAML Files
        #=======================================================
        orgs   = list(kwargs.org_moids.keys())
        kwargs = ezfunctions.remove_duplicates(orgs, ['profiles', 'templates', 'wizard'], kwargs)
        ezfunctions.create_yaml(orgs, kwargs)
        #=======================================================
        # Create Profile in Intersight and Get Identities
        #=======================================================
        kwargs = isight.imm('server').profiles(kwargs)
        kwargs = isight.imm('wizard').server_identities(kwargs)
        #=======================================================
        # Return kwargs
        #=======================================================
        return kwargs

    #=================================================================
    # Function: Main Menu, Prompt User for Deployment Type
    #=================================================================
    def quick_start(self, kwargs):

        # Return kwargs
        return kwargs