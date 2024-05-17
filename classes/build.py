#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, isight, pcolor, questions
    from copy import deepcopy
    from dotmap import DotMap
    import ipaddress, json, inflect, numpy, os, re, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
#=============================================================================
# Build Intersight Managed Mode Environments
#=============================================================================
class intersight(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function: Create YAML Files
    #=========================================================================
    def create_yaml_files(kwargs):
        orgs   = list(kwargs.org_moids.keys())
        kwargs = ezfunctions.remove_duplicates(orgs, ['profiles', 'templates', 'wizard'], kwargs)
        ezfunctions.create_yaml(orgs, kwargs)

    #=========================================================================
    # Function: Chassis Setup
    #=========================================================================
    def chassis_setup(self, kwargs):
        setup_keys = list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.keys())
        return kwargs

    #=========================================================================
    # Function: Clone Policy Children
    #=========================================================================
    def clone_children(self, destination_org, policy, kwargs):
        policy_name    = policy.split('/')[1]
        parent_policy  = self.type.split('.')[0]
        source_org     = policy.split('/')[0]
        parent_object  = kwargs.ezdata[parent_policy].object_type
        
        kwargs.parent  = kwargs.ezdata[parent_policy].object_type.split('.')[1]
        key_list            = intersight.clone_key_list(kwargs.ezdata[self.type].allOf[1].properties)
        associated_policies = []
        kwargs.bulk_list    = []
        kwargs.method       = 'get'
        kwargs.names        = [kwargs.policies[parent_policy][kwargs.original_index].Moid]
        kwargs.parent_moid  = kwargs.isight[destination_org].policies[parent_policy][policy_name]
        kwargs.uri          = kwargs.ezdata[self.type].intersight_uri
        kwargs              = isight.api('parent_moids').calls(kwargs)
        policy_results      = kwargs.results
        for k, v in kwargs.ezdata[self.type].allOf[1].properties.items():
            if '_policy' in k: associated_policies.append({k:v.object_type})
        policy_names   = [e.Name for e in kwargs.results]
        create_policy  = True
        if policy_name in policy_names: create_policy = False
        if create_policy == True:
            kwargs.bulk_list = []
            key_list = ['Description', 'Name', 'Tags']
            for k,v in kwargs.ezdata[e].allOf[1].properties.items():
                if v.type == 'array': key_list.append(v['items'].intersight_api)
                elif v.type == 'object': key_list.append(v.intersight_api)
                elif re.search('boolean|integer|string', v.type):
                    if re.search(r'\$ref\:', v.intersight_api): key_list.append(v.intersight_api.split(':')[1])
                    else: key_list.append(v.intersight_api)
                else: pcolor.Yellow(json.dumps(v, indent=4)); sys.exit(1)
            indx = next((index for (index, d) in enumerate(kwargs.policies[self.type]) if d['Name'] == policy_name), None)
            kwargs.parent_index   = indx
            api_body              = kwargs.policies[self.type][indx]
            for k in list(api_body.keys()):
                if not k in key_list: api_body.pop(k)
            api_body.Name         = policy_name
            api_body.ObjectType   = kwargs.ezdata[self.type].object_type
            api_body.Organization = {'Moid':kwargs.org_moids[destination_org].moid, 'ObjectType':'organization.Organization'}
            kwargs.bulk_list.append(api_body)
            #=============================================================================
            # POST Bulk Request if Post List > 0
            #=============================================================================
            if len(kwargs.bulk_list) > 0:
                kwargs.uri = kwargs.ezdata[self.type].intersight_uri
                kwargs     = isight.imm(self.type).bulk_request(kwargs)
            if re.search('port|vlan|vsan', self.type):
                if self.type == 'port': kwargs = intersight('port').clone_vxan(kwargs)
        return kwargs

    #=========================================================================
    # Function: Copy Dictionary Keys to key_list
    #=========================================================================
    def clone_key_list(policy_dict):
        key_list = ['Description', 'Name', 'Tags']
        for k,v in policy_dict.items():
            if v.type == 'array': key_list.append(v['items'].intersight_api)
            elif v.type == 'object': key_list.append(v.intersight_api)
            elif re.search('boolean|integer|string', v.type):
                if re.search(r'\$ref\:', v.intersight_api): key_list.append(v.intersight_api.split(':')[1])
                else: key_list.append(v.intersight_api)
            else: pcolor.Yellow(json.dumps(v, indent=4)); sys.exit(1)
        key_list = [e for e in key_list if not '_policy' in e]
        return key_list

    #=========================================================================
    # Function: Clone Policy
    #=========================================================================
    def clone_policy(self, destination_org, policy, kwargs):
        source_org     = policy.split('/')[0]
        kwargs.method  = 'get'
        kwargs.names   = [kwargs.org_moid[source_org].moid]
        kwargs.uri     = kwargs.ezdata[self.type].intersight_uri
        kwargs         = isight.api('multi_org').calls(kwargs)
        policy_results = kwargs.results
        policy_names   = [e.Name for e in kwargs.results]
        policy_name    = policy.split('/')[1]
        create_policy  = True
        if policy_name in policy_names: create_policy = False
        if create_policy == True:
            key_list = intersight.clone_key_list(kwargs.ezdata[self.type].allOf[1].properties)
            indx     = next((index for (index, d) in enumerate(kwargs.policies[self.type]) if d['Name'] == policy_name), None)
            kwargs.original_index = indx
            api_body              = kwargs.policies[self.type][indx]
            for k in list(api_body.keys()):
                if not k in key_list: api_body.pop(k)
            api_body.Name         = policy_name
            api_body.ObjectType   = kwargs.ezdata[self.type].object_type
            api_body.Organization = {'Moid':kwargs.org_moids[destination_org].moid, 'ObjectType':'organization.Organization'}
            kwargs.bulk_list = []
            kwargs.bulk_list.append(api_body)
            #=============================================================================
            # POST Bulk Request
            #=============================================================================
            kwargs.uri         = kwargs.ezdata[self.type].intersight_uri
            kwargs             = isight.imm(self.type).bulk_request(kwargs)
            if re.search('port|vlan|vsan', self.type):
                if re.search('vlan|vsan', self.type): kwargs = intersight(f'{self.type}.{self.type}s').clone_children(destination_org, policy, kwargs)
                elif self.type == 'port':
                    for k,v in kwargs.ezdata[self.type].allOf[1].properties.items():
                        if 'port_' in k: kwargs = intersight(f'{self.type}.{k}').clone_children(destination_org, policy, kwargs)
                    #kwargs = intersight(f'{self.type}.{k}').clone_ports(destination_org, policy, kwargs)
        return kwargs

    #=========================================================================
    # Function: Build Server Profile Dict from Source
    #=========================================================================
    def domain_profiles_create_from_source(self, item, kwargs):
        pvars = DotMap(port_policies = [], vlan_policies = [], vsan_policies = [])
        kwargs.names = []
        for e in item.SwitchProfiles: kwargs.names.append(e.Moid)
        kwargs.method   = 'get'
        kwargs.uri      = kwargs.ezdata.domain.intersight_uri_switch
        kwargs          = isight.api('moid_filter').calls(kwargs)
        switch_profiles = kwargs.results
        for x in range(0,len(switch_profiles)):
            i = switch_profiles[x]
            if i.PolicyBucket:
                kwargs.method = 'get_by_moid'
                for e in i.PolicyBucket:
                    pkeys        = list(kwargs.policies.keys())
                    key_id       = [k for k, v in kwargs.ezdata.items() if v.object_type == e.ObjectType][0]
                    kwargs.pmoid = e.Moid
                    kwargs.uri   = kwargs.ezdata[key_id].intersight_uri
                    kwargs       = isight.api(key_id).calls(kwargs)
                    kwargs.isight[kwargs.org_names[kwargs.results.Organization.Moid]].policies[key_id][kwargs.results.Name] = kwargs.results.Moid
                    if not key_id in pkeys: kwargs.policies[key_id].append(kwargs.results)
                    if re.search('port|vlan|vsan', key_id):
                        pvars[f'{key_id}_policies'].append(f'{kwargs.org_names[kwargs.results.Organization.Moid]}/{kwargs.results.Name}')
                    elif x == 0: pvars[f'{key_id}_policy'] = f'{kwargs.org_names[kwargs.results.Organization.Moid]}/{kwargs.results.Name}'
        if item.Tags: pvars['tags'] = item.Tags
        kwargs.jdata      = kwargs.ezwizard.domain.properties.domain_policies
        kwargs.jdata.enum = [k for k in pvars.keys() if 'polic' in k]
        exclude_policies  = ezfunctions.variable_prompt(kwargs)
        if type(exclude_policies) == str: exclude_policies = [exclude_policies]
        for e in exclude_policies: pvars.pop(e)
        for k in pvars.keys():
            if kwargs.use_shared_org == True: org = kwargs.shared_org
            else: org = kwargs.org
            def org_check(org, policy):
                in_org = False
                if  org in policy: in_org = True
                return in_org
            ptype = (k.replace('_policy')).replace('_policies')
            if 'polic' in k:
                if 'policies' in k:
                    for x in range(0,len(pvars[k])):
                        in_org = org_check(pvars[k][x])
                        if in_org == False:
                            kwargs      = intersight(ptype).clone_policy(org, pvars[k][x], kwargs)
                            policy      = pvars[k][x].split('/')
                            pvars[k][x] = f'{org}/{policy[1]}'
                            pvars[k][x] = pvars[k][x].replace(f'{kwargs.org}/', '')
                else:
                    in_org = org_check(pvars[k])
                    if in_org == False:
                        kwargs   = intersight(ptype).clone_policy(org, pvars[k], kwargs)
                        policy   = pvars[k].split('/')
                        pvars[k] = f'{org}/{policy[1]}'
                        pvars[k] = pvars[k].replace(f'{kwargs.org}/', '')
        for e in list(pvars.keys()): kwargs.imm_dict.orgs[kwargs.org].wizard.domain[e] = pvars[e]
        # Return kwargs
        return kwargs

    #=========================================================================
    # Function: Domain Setup
    #=========================================================================
    def domain_setup(self, kwargs):
        setup_keys = list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.keys())
        if 'domain' in setup_keys:
            profile_setup_keys   = list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.keys())
        else: profile_setup_keys = []
        key_count = 0
        for e in ['model', 'moid', 'name', 'serial_numbers']:
            if e in profile_setup_keys: key_count += 1
        args = DotMap()
        if not key_count == 4:
            #=========================================================================
            # Obtain List of Physical Domains
            #=========================================================================
            kwargs.api_filter = "PlatformType in ('UCSFIISM')"
            kwargs.method     = 'get'
            kwargs.uri        = 'asset/DeviceRegistrations'
            kwargs            = isight.api('device_registrations').calls(kwargs)
            #=========================================================================
            # Prompt User for Physical Domain
            #=========================================================================
            domains      = kwargs.results
            domain_names = [e.DeviceHostname[0] for e in domains]
            domain_names.sort()
            kwargs.jdata         = deepcopy(kwargs.ezwizard.domain.properties.physical_domain)
            kwargs.jdata.default = domain_names[0]
            kwargs.jdata.enum    = domain_names
            phys_domain          = ezfunctions.variable_prompt(kwargs)
            indx  = next((index for (index, d) in enumerate(domains) if d['DeviceHostname'][0] == phys_domain), None)
            args.model          = domains[indx].Pid[0]
            args.moid           = domains[indx].Moid
            args.name           = domains[indx].DeviceHostname[0]
            args.serial_numbers = domains[indx].Serial
            for e in ['model', 'moid', 'name', 'serial_numbers']:
                kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[e] = args[e]
            #=========================================================================
            # Domain Profile name
            #=========================================================================
            kwargs.jdata             = deepcopy(kwargs.ezdata.abstract_profile.properties.name)
            kwargs.jdata.description = 'Domain Profile Name\n\n' + kwargs.jdata.description
            kwargs.jdata.default     = args.name
            args.name = ezfunctions.variable_prompt(kwargs)
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.name  = args.name
            #=========================================================================
            # Confirm Domain is Assigned to the correct Organization
            #=========================================================================
            kwargs.method = 'get_by_moid'
            kwargs.pmoid  = kwargs.org_moids[kwargs.org].moid
            kwargs.uri    = 'organization/Organizations'
            kwargs = isight.api(self.type).calls(kwargs)
            kwargs.names  = [e.Moid for e in kwargs.results.ResourceGroups]
            kwargs.method = 'get'
            kwargs.uri    = 'resource/Groups'
            kwargs = isight.api('resource_groups').calls(kwargs)
            if len(kwargs.names) > 1:
                names = [e.Name for e in kwargs.results]
                names.sort()
                kwargs.jdata   = deepcopy(kwargs.ezwizard.domain.properties.resource_group)
                kwargs.jdata.description = (kwargs.jdata.description.replace('ORG', kwargs.org)).replace('DOMAIN', args.name)
                resource_group = ezfunctions.variable_prompt(kwargs)
                indx = next((index for (index, d) in enumerate(kwargs.results) if d['Name'] == resource_group), None)
                rgroup = kwargs.results[indx]
            else: rgroup = kwargs.results[0]
            if not rgroup.Qualifier == 'Allow-All':
                if not args.moid in rgroup.Selectors[0].Selector:
                    flist = re.search(r'\(([\'a-z0-9, ]+)\)', rgroup.Selectors[0].Selector).group(1)
                    flist = [(e.replace("'", "")).replace(' ', '') for e in flist.split(',')]
                    flist.append(args.moid)
                    flist.sort()
                    flist = "', '".join(flist).strip("', '")
                    idict = rgroup.Selectors
                    idict[0].Selector = f"/api/v1/asset/DeviceRegistrations?$filter=(Moid in ('{flist}'))"
                    kwargs.api_body = {'Selectors':[e.toDict() for e in idict]}
                    kwargs.method   = 'patch'
                    kwargs.pmoid    = rgroup.Moid
                    kwargs = isight.api('resource_group').calls(kwargs)
                else: pcolor.Cyan(f'\n   Domain already assigned to Organization `{kwargs.org}` Resource Group `{rgroup.Name}`\n')
            intersight.create_yaml_files(kwargs)
            #=========================================================================
            # Domain Configuration Source - Clone/New
            #=========================================================================
            kwargs.jdata   = kwargs.ezwizard.domain.properties.domain_source
            profile_source = ezfunctions.variable_prompt(kwargs)
            if profile_source == 'Clone':
                domain_names.remove(phys_domain)
                kwargs.jdata         = kwargs.ezwizard.domain.properties.source_domain
                kwargs.jdata.default = domain_names[0]
                kwargs.jdata.enum    = domain_names
                source_domain        = ezfunctions.variable_prompt(kwargs)
                indx  = next((index for (index, d) in enumerate(domains) if d['DeviceHostname'][0] == source_domain), None)
                kwargs = intersight('domain').domain_profiles_create_from_source(domains[indx], kwargs)

        else:
            for e in ['model', 'moid', 'name', 'serial_numbers']:
                args[e] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[e]
        #=========================================================================
        # Loop through Policy List and Build Dictionaries
        #=========================================================================
        kwargs.profile_type = 'domain'
        if not 'vlan_policies' in profile_setup_keys: kwargs = questions.policies('vlan').vlan(kwargs)
        if not 'port_policies' in profile_setup_keys: kwargs = questions.policies('port').port(kwargs)
        policies    = ['network_connectivity_policy', 'ntp_policy', 'snmp_policy', 'syslog_policy', 'system_qos_policy']
        for e in policies:
            policy = (e.replace('_policies', '')).replace('_policy', '')
            if not e in profile_setup_keys: kwargs = eval(f'questions.policies(policy).{policy}(kwargs)')
        #=========================================================================
        # Build the Domain Profile Dictionary
        #=========================================================================
        domain_keys = list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.keys())
        policies.extend(['name', 'port_policies', 'serial_numbers', 'switch_control_policy', 'vlan_policies'])
        policies = sorted(policies)
        pvars = DotMap(action = 'Deploy')
        for e in policies:
            if e in domain_keys: pvars[e] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[e]
        kwargs.class_path = f'profiles,domain'
        kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=========================================================================
        # Loop through Policy List and Build Dictionaries for Chassis
        #=========================================================================
        if 'chassis' in setup_keys:
            profile_setup_keys   = list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.chassis.keys())
        else: profile_setup_keys = []
        kwargs.profile_type = 'chassis'
        if not 'imc_access' in profile_setup_keys: kwargs = eval(f'questions.policies(policy).{policy}(kwargs)')
        if kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.model == 'UCSX-S9108-100G':
            policies   = ['power_policy', 'thermal_policy']
        else: policies = ['imc_access_policy', 'power_policy', 'snmp_policy', 'thermal_policy']
        for e in policies:
            policy = e.replace('_policy', '')
            if not e in profile_setup_keys: kwargs = eval(f'questions.policies(policy).{policy}(kwargs)')
        kwargs = isight.imm.deploy(kwargs)
        return kwargs

    #=========================================================================
    # Function: Main Menu, Prompt User for Policy Elements
    #=========================================================================
    def ezimm(self, kwargs):
        idata = deepcopy(DotMap(dict(pair for d in kwargs.ezdata[self.type].allOf for pair in d.properties.items())))
        if kwargs.build_type == 'Machine':
            if re.search('ip|iqn|mac|wwnn|wwpn', self.type): pop_list = ['assignment_order', 'description', 'name', 'tags']
            for p in pop_list: idata.pop(p)
        ptype = kwargs.ezdata[self.type].intersight_type

        kwargs.configure_more = True
        if kwargs.imm_dict.orgs[kwargs.org][ptype].get(self.type):
            kwargs = questions.prompt_user.existing_object(ptype, self.type, kwargs)
        if kwargs.configure_more == True:
            ilist = []
            kwargs.loop_count = 0
            if kwargs.build_type == 'Machine': config_object = True
            else: config_object = questions.prompt_user.to_configure(self.type, ptype, kwargs)
            while config_object == True:
                idict = DotMap()
                for k, v in idata.items():
                    if re.search('boolean|integer|string', v.type):
                        idict[k] = questions.prompt_user.item(k, v, kwargs)
                    elif v.type == 'array':
                        kwargs.inner_count = 0
                        if k in v.required: config_inner = True
                        else: config_inner = questions.prompt_user.for_sub_item(k, kwargs)
                        while config_inner == True:
                            if not idict.get(k): idict[k] = []
                            edict = DotMap()
                            for a,b in v['items'].properties.items():
                                if re.search('boolean|integer|string', b.type) and a != 'size':
                                    edict[a] = questions.prompt_user.item(a, b, kwargs)
                            accept = questions.prompt_user.to_accept(k, edict, kwargs)
                            additional = questions.prompt_user.to_add(k, kwargs)
                            if accept == True: idict[k].append(edict)
                            if additional == False: config_inner = False
                            kwargs.inner_count += 1
                    elif v.type == 'object':
                        if k in v.required: config = True
                        else: config = questions.prompt_user.for_sub_item(k, kwargs)
                        while config == True:
                            edict = DotMap()
                            for a,b in v.properties.items():
                                if re.search('boolean|integer|string', b.type):
                                    edict[a] = questions.prompt_user.item(a, b, kwargs)
                            accept = questions.prompt_user.to_accept(k, edict, kwargs)
                            if accept == True: idict[k] = edict; config = False
                accept = questions.prompt_user.to_accept(self.type, idict, kwargs)
                additional = questions.prompt_user.to_add(self.type, kwargs)
                if accept == True: ilist.append(idict)
                if additional == False: config_object = False
                kwargs.loop_count += 1
            kwargs.imm_dict.orgs[kwargs.org][ptype][self.type] = ilist
        return kwargs

    #=========================================================================
    # Function: Main Menu, Operating System Installation
    #=========================================================================
    def operating_system_installation(self, kwargs):
        #=========================================================================
        # Prompt user for Boot Mode
        #=========================================================================
        if not kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            kwargs.jdata       = kwargs.ezwizard.server.properties.boot_volume
            kwargs.boot_volume = ezfunctions.variable_prompt(kwargs)
        #=========================================================================
        # Create or Import Profiles
        #=========================================================================
        if kwargs.profile_option == 'new':
            kwargs = intersight(self.type).server_profiles_create(kwargs)
        else:
            if not kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
                kwargs = intersight(self.type).server_profiles_existing(kwargs)
        intersight.create_yaml_files(kwargs)
        #=========================================================================
        # Get Identities
        #=========================================================================
        identity_check = True
        for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            if not (e.get('macs') and len(e.macs) > 0): identity_check = False
        if identity_check == False:
            kwargs = isight.api('wizard').build_server_identities(kwargs)
            intersight.create_yaml_files(kwargs)
        #=========================================================================
        # Get Installation Configuration Parameters
        #=========================================================================
        op_system = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems[0]
        if not kwargs.imm_dict.orgs[kwargs.org].wizard.setup.get('os_configuration'):
            kwargs = questions.os_install.sw_repo_os_cfg(op_system, kwargs)
            intersight.create_yaml_files(kwargs)
        if not kwargs.imm_dict.orgs[kwargs.org].wizard.setup.get('os_image'):
            kwargs = questions.os_install.sw_repo_os_image(op_system, kwargs)
            intersight.create_yaml_files(kwargs)
        if not kwargs.imm_dict.orgs[kwargs.org].wizard.setup.get('server_configuration_utility'):
            kwargs = questions.os_install.sw_repo_scu(kwargs)
            intersight.create_yaml_files(kwargs)
        answer_check = True
        for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            if not (e.get('answers') and len(e.answers) > 0): answer_check = False
        if answer_check == False:
            kwargs = intersight.os_configuration_answers(kwargs)
            intersight.create_yaml_files(kwargs)
        #=========================================================================
        # Deploy Server Profiles
        #=========================================================================
        if kwargs.profile_option == 'new':
            kwargs   = intersight(self.type).server_profiles_deploy(kwargs)
        #=========================================================================
        # Install Operating System
        #=========================================================================
        kwargs = isight.imm('os_install').os_install(kwargs)
        #=========================================================================
        # Return kwargs
        #=========================================================================
        return kwargs

    #=========================================================================
    # Function: OS Configuration Answers
    #=========================================================================
    def os_configuration_answers(kwargs):
        if type(kwargs.os_cfg_dict.Name) != str:
            kwargs.method      = 'get_by_moid'
            kwargs.pmoid       = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.os_configuration
            kwargs.uri         = 'os/ConfigurationFiles'
            kwargs             = isight.api('os_configuration').calls(kwargs)
            kwargs.os_cfg_dict = kwargs.results
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
            #=========================================================================
            # Function: Add Keys to Server Profile answers dict
            #=========================================================================
            def add_to_server_dict(variable, answer, kwargs):
                for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles: e.answers[variable] = answer
                return kwargs
            #=========================================================================
            # Process for Intersight defined OS Configuration
            #=========================================================================
            kwargs.server_profiles = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles
            answers  = [e.Type.Name for e in kwargs.os_cfg_dict.Placeholders]
            sprofile = kwargs.server_profiles[0]
            if 'shared' in kwargs.os_cfg_dict.Owners:
                #=========================================================================
                # Boot Parameters
                #=========================================================================
                for x in range(0,len(kwargs.server_profiles)):
                    boot_order = kwargs.server_profiles[x].boot_order
                    if '.answers.BootMode' in answers:
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.BootMode = boot_order.boot_mode
                    kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.SecureBoot = boot_order.enable_secure_boot
                if '.answers.BootMode' in answers: answers.remove('.answers.BootMode')
                if '.answers.SecureBoot' in answers: answers.remove('.answers.SecureBoot')
                #=========================================================================
                # Windows Edition and Product Key
                #=========================================================================
                if sprofile.os_vendor == 'Microsoft':
                    kwargs.jdata = kwargs.ezwizard.os_configuration.properties.windows_edition
                    kwargs.jdata.description.replace('REPLACE', sprofile.os_version.name)
                    edition      = ezfunctions.variable_prompt(kwargs)
                    kwargs       = add_to_server_dict('EditionString', edition, kwargs)
                    kwargs.jdata = kwargs.ezwizard.os_configuration.properties.windows_product_key
                    product_key  = ezfunctions.variable_prompt(kwargs)
                    kwargs       = add_to_server_dict('ProductKey', product_key, kwargs)
                    answers.remove('.answers.EditionString'); answers.remove('.answers.ProductKey')
                #=========================================================================
                # RootPassword
                #=========================================================================
                if '.answers.RootPassword' in answers:
                    pcolor.Cyan(f'\n{"-"*108}\n')
                    pcolor.Yellow(f'  The OS Install Requires a Root Password for Installation.  Checking System environment to see if it is already set.')
                    kwargs.jdata             = kwargs.ezdata.sensitive_variables.properties.root_password
                    if sprofile.os_vendor == 'Microsoft':
                        kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE Root', 'Windows Login')
                        kwargs.jdata.title = 'Windows Login Password'
                    else: kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', sprofile.os_vendor)
                    kwargs.sensitive_var = 'root_password'
                    kwargs               = ezfunctions.sensitive_var_value(kwargs)
                    kwargs               = add_to_server_dict('RootPassword', 'sensitive_root_password', kwargs)
                    if sprofile.os_vendor == 'Microsoft':
                        kwargs = add_to_server_dict('RootPassword', 'sensitive_root_password', kwargs)
                #=========================================================================
                # Interface for Installation Configuration
                #=========================================================================
                if len(kwargs.server_profiles[0].macs) > 1:
                    kwargs.jdata             = kwargs.ezwizard.os_configuration.properties.network_interface
                    kwargs.jdata.enum        = [f'MAC Address: {e.mac} Name: {e.name}' for e in kwargs.server_profiles[0].macs]
                    kwargs.jdata.default     = kwargs.jdata.enum[0]
                    kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', kwargs.server_profiles[0].name)
                    network_interface        = ezfunctions.variable_prompt(kwargs)
                    mregex                   = re.compile(r'MAC Address: ([0-9a-fA-F\:]+) Name')
                    match                    = mregex.search(network_interface)
                    mac                      = match.group(1)
                    indx                     = next((index for (index, d) in enumerate(kwargs.server_profiles[0].macs) if d['mac'] == mac), None)
                else: indx = 0
                #=========================================================================
                # Assign MAC Address/vNIC name to answers
                #=========================================================================
                for x in range(0,len(kwargs.server_profiles)):
                    if kwargs.server_profiles[x].os_vendor == 'Microsoft':
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.NetworkDevice   = kwargs.server_profiles[x].macs[indx].name
                    else: kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.NetworkDevice = kwargs.server_profiles[x].macs[indx].mac
                    kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.MACAddress = kwargs.server_profiles[x].macs[indx].mac
                    kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].install_interface  = kwargs.server_profiles[x].macs[indx].mac
                #=========================================================================
                # DHCP or static IP configuration
                #=========================================================================
                if '.answers.IpConfigType' in answers:
                    kwargs.jdata   = kwargs.ezwizard.os_configuration.properties.ip_config_type
                    ip_config_type = ezfunctions.variable_prompt(kwargs)
                    kwargs         = add_to_server_dict('IpConfigType', ip_config_type, kwargs)
                #=========================================================================
                # Static IP Configuration
                #=========================================================================
                if ip_config_type == 'static':
                    kwargs.jdata = kwargs.ezwizard.os_configuration.properties.ip_version
                    ip_version   = ezfunctions.variable_prompt(kwargs)
                    kwargs       = add_to_server_dict('IpVersion', ip_version, kwargs)
                    #=========================================================================
                    # Prompt for Domain, Gateway, Netmask/Prefix, and DNS
                    #=========================================================================
                    kwargs.jdata = kwargs.ezwizard.os_configuration.properties.domain_name
                    domain_name  = ezfunctions.variable_prompt(kwargs)
                    if re.search(r'^\.', domain_name): domain_name = domain_name[1:]
                    if '.answers.Vlanid' in answers:
                        kwargs.jdata = kwargs.ezwizard.os_configuration.properties.vlan_id
                        vlan_id = ezfunctions.variable_prompt(kwargs)
                        if len(vlan_id) > 0: kwargs = add_to_server_dict('Vlanid', vlan_id, kwargs)
                    for key in list(kwargs.ezdata[f'ip.ip{ip_version.lower()}_configuration'].properties.keys()):
                        kwargs.jdata = deepcopy(kwargs.ezdata[f'ip.ip{ip_version.lower()}_configuration'].properties[key])
                        if key == 'gateway': kwargs.jdata.description = 'Default Gateway for Network Configuration.'
                        if key == 'netmask': kwargs.jdata.description = 'Netmask for Network Configuration.'
                        if key == 'prefix':  kwargs.jdata.description = 'Prefix for Network Configuration.'
                        kwargs[key] = ezfunctions.variable_prompt(kwargs)
                        if re.search('gateway|netmask|prefix', key) and f'.answers.Ip{ip_version}Config.{key.capitalize()}' in answers:
                            for x in range(0,len(kwargs.server_profiles)):
                                kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers[f'Ip{ip_version}Config'][f'{key.capitalize()}'] = kwargs[key]
                        elif 'primary_dns' == key and '.answers.NameServer' in answers:
                            kwargs = add_to_server_dict('NameServer', kwargs[key], kwargs)
                        elif 'secondary_dns' == key and '.answers.AlternateNameServer' in answers:
                            kwargs = add_to_server_dict('AlternateNameServers', kwargs[key], kwargs)
                    #=========================================================================
                    # Prompt for Host FQDN and Server IP Address's
                    #=========================================================================
                    for x in range(0,len(kwargs.server_profiles)):
                        kwargs.jdata             = deepcopy(kwargs.ezwizard.os_configuration.properties.fqdn)
                        kwargs.jdata.default     = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].name + '.' + domain_name
                        kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', kwargs.server_profiles[x].name)
                        host_fqdn = ezfunctions.variable_prompt(kwargs)
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.FQDN     = host_fqdn
                        if kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].os_vendor == 'VMware':
                            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.Hostname   = host_fqdn
                        else: kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.Hostname = host_fqdn.split('.')[0]
                        kwargs.jdata             = kwargs.ezdata[f'ip.ip{ip_version.lower()}_configuration'].properties.gateway
                        kwargs.jdata.description = f'{host_fqdn} IP{ip_version.lower()} Address.'
                        kwargs.jdata.title       = f'IP{ip_version.lower()} Address'
                        if x > 0: kwargs.jdata.default = network_list[indx+1]
                        else:
                            if f'IP{ip_version.lower()}' == 'IPv4':
                                gateway = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.IpV4Config.Gateway
                                netmask = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.IpV4Config.Netmask
                                network_list = [str(address) for address in ipaddress.IPv4Network(address=f'{gateway}/{netmask}', strict=False)]
                            else:
                                gateway = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.IpV6Config.Gateway
                                prefix  = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.IpV4Config.Prefix
                                network_list = [str(address) for address in ipaddress.IPv6Network(address=f'{gateway}/{prefix}', strict=False)]
                            network_list.remove(gateway)
                            kwargs.jdata.default = network_list[3]
                        ip_address = ezfunctions.variable_prompt(kwargs)
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers[f'Ip{ip_version}Config'].IpAddress = ip_address
                        indx = network_list.index(ip_address)
                #=========================================================================
                # DHCP Configuration
                #=========================================================================
                else:
                    #=========================================================================
                    # Prompt for Host FQDN
                    #=========================================================================
                    for x in range(0,len(kwargs.server_profiles)):
                        kwargs.jdata             = kwargs.ezwizard.os_configuration.properties.fqdn
                        kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', kwargs.server_profiles[x].name)
                        if x == 0: kwargs.jdata.default = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].name + '.' + domain_name
                        else: kwargs.jdata.default = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].name + '.' + fqdn
                        host_fqdn = ezfunctions.variable_prompt(kwargs)
                        fqdn      = host_fqdn[len(host_fqdn.split('.')[0])+1:]
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.FQDN     = host_fqdn
                        kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.Hostname = host_fqdn.split('.')[0]
                #=========================================================================
                # Remove Answers and Validate nothing missed
                #=========================================================================
                for e in ['Ip##Config.Gateway', 'Ip##Config.IpAddress', 'Ip##Config.Netmask', 'Ip##Config.Prefix']:
                    for v in ['V4', 'V6']:
                        c = e.replace('##', v)
                        if f'.answers.{c}' in answers: answers.remove(f'.answers.{c}')
                for e in ['AlternateNameServer', 'FQDN', 'Hostname', 'IpConfigType', 'IpVersion', 'NameServer', 'LogonPassword',
                          'NetworkDevice', 'RootPassword', 'Vlanid',]:
                    if f'.answers.{e}' in answers: answers.remove(f'.answers.{e}')
                if '.internal.ServerManagementMode' in answers: answers.remove('.internal.ServerManagementMode')
                if '.MacAddress' in answers: answers.remove('.MacAddress')
                if len(answers) > 0:
                    pcolor.Yellow('  !!! ERROR !!!\n  Undefined Answers.')
                    for e in answers: pcolor.Yellow(f'  Answer: {e}')
                    pcolor.Red(f'  Exiting... (intersight-tools/classes/build.py Line 464)'); len(False); sys.exit(1)
            #=========================================================================
            # Process for User defined OS Configuration
            #=========================================================================
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
                    #=========================================================================
                    # Sensitive Variables
                    #=========================================================================
                    if adict.Type.Properties.Secure:
                        pcolor.Cyan(f'\n{"-"*108}\n')
                        pcolor.Yellow(f'  The OS Install Requires `{a}` for Installation.  Checking System environment to see if it is already set.')
                        kwargs.sensitive_var = f'undefined_{a}'
                        kwargs               = ezfunctions.sensitive_var_value(kwargs)
                        os.environ[a]        = kwargs.var_value
                        kwargs               = add_to_server_dict(a, f'sensitive_{a}', kwargs)
                    #=========================================================================
                    # All other Variables
                    #=========================================================================
                    elif 'shared_variable' in adict.Type.Description:
                        answer = ezfunctions.variable_prompt(kwargs)
                        kwargs = add_to_server_dict(a, answer, kwargs)
                    else:
                        for e in kwargs.server_profiles:
                            kwargs.jdata.description = adict.Type.Description + f'for Server Profile `{kwargs.server_profiles[e]}`.'
                            if x > 0: kwargs.jdata.default = answer
                            answer = ezfunctions.variable_prompt(kwargs)
                            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers[a] = answer
            #=========================================================================
            # Prompt User to Accept Configuration
            #=========================================================================
            idict = DotMap(answers = [])
            for x in range(0,len(kwargs.server_profiles)):
                answers = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers.toDict()
                kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].answers = DotMap(dict(sorted(answers.items())))
                server = kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x]
                idict.answers.append(dict(server_profile=server.name,answers=server.answers.toDict()))
            accept = questions.prompt_user.to_accept('os_configuration_answers', idict, kwargs)
            if accept == True: valid_answers = True
        # Return kwargs
        return kwargs

    #=========================================================================
    # Function: Server Profile Creation
    #=========================================================================
    def server_profiles_create(self, kwargs):
        #=========================================================================
        # Prompt User to Create Server Profiles
        #=========================================================================
        if not kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles:
            #if kwargs.imm_dict.orgs[kwargs.org].profile.server: kwargs.imm_dict.orgs[kwargs.org].pop('profile')
            kwargs = intersight(self.type).server_profiles_questions(kwargs)
            intersight.create_yaml_files(kwargs)
        #=========================================================================
        # Create Server Profile(s) from Inputs
        #=========================================================================
        if not kwargs.imm_dict.orgs[kwargs.org].profiles.get('server'):
            #=========================================================================
            # Create Profile Dictionary
            #=========================================================================
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
                pvars      = intersight(profile_type).server_profiles_create_from_source(source_results[indx], kwargs)
                for k, v in kwargs.server_profiles.items(): pvars.targets.append(dict(name = v.name, serial = k))
                # Add Profile Variables to imm_dict
                kwargs.class_path = f'profiles,server'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
            else:
                kwargs.org = original_org
                pvars = dict(
                    attach_template             = True,
                    target_platform             = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform,
                    targets                     = [dict(name = v.name, serial_number=k) for k, v in kwargs.server_profiles.items()],
                    ucs_server_profile_template = profile_source)
                # Add Profile Variables to imm_dict
                kwargs.class_path = f'profiles,server'
                kwargs = ezfunctions.ez_append(pvars, kwargs)
            intersight.create_yaml_files(kwargs)
        if kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_type == 'server_template':
            original_org   = kwargs.org
            profile_source = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_source
            profile_type   = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_type
            kwargs.org     = profile_source.split('/')[0]
            kwargs.method  = 'get'
            kwargs.names   = [profile_source.split('/')[1]]
            kwargs.uri     = kwargs.ezdata[profile_type].intersight_uri
            kwargs         = isight.api(profile_type).calls(kwargs)
            source_results = kwargs.results
            for e in kwargs.results: kwargs.isight[kwargs.org].profiles['server_template'][e.Name] = e.Moid
            # Create Template pvars
            indx  = next((index for (index, d) in enumerate(source_results) if d['Name'] == profile_source.split('/')[1]), None)
            kwargs.org = original_org
            pvars      = intersight(profile_type).server_profiles_create_from_source(source_results[indx], kwargs)
            kwargs.org = profile_source.split('/')[0]
            # Add Profile Variables to imm_dict
            kwargs.class_path = f'templates,server'
            kwargs            = ezfunctions.ez_append(pvars, kwargs)
            kwargs.org        = original_org
        #=========================================================================
        # Create Profile and remove Template from Wizard dictionary
        #=========================================================================
        kwargs.temp_templates = DotMap()
        kwargs = isight.imm('server').profiles(kwargs)
        for e in list(kwargs.imm_dict.orgs.keys()):
            if kwargs.imm_dict.orgs[e].get('templates'):
                kwargs.temp_templates[e].templates = kwargs.imm_dict.orgs[e].templates
                kwargs.imm_dict.orgs[e].pop('templates')
        #=========================================================================
        # Return kwargs
        #=========================================================================
        return kwargs

    #=========================================================================
    # Function: Build Server Profile Dict from Source
    #=========================================================================
    def server_profiles_create_from_source(self, item, kwargs):
        pvars = DotMap()
        if self.type == 'server_template':
            pvars['create_template'] = False
            pvars['name'] = item.Name
        else:
            pvars['action']  = 'No-op'
            pvars['targets'] = []
        pvars['target_platform'] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform
        if item.PolicyBucket:
            kwargs.method = 'get_by_moid'
            for e in item.PolicyBucket:
                key_id       = [k for k, v in kwargs.ezdata.items() if v.object_type == e.ObjectType][0]
                kwargs.pmoid = e.Moid
                kwargs.uri   = kwargs.ezdata[key_id].intersight_uri
                kwargs       = isight.api(key_id).calls(kwargs)
                pvars[f'{key_id}_policy'] = f'{kwargs.org_names[kwargs.results.Organization.Moid]}/{kwargs.results.Name}'
                pvars[f'{key_id}_policy'] = pvars[f'{key_id}_policy'].replace(f'{kwargs.org}/', '')
        if item.Tags: pvars['tags'] = item.Tags
        if item.UuidAddressType == 'POOL':
            kwargs.pmoid       = item.UuidPool.Moid
            kwargs.uri         = kwargs.ezdata.uuid.intersight_uri
            kwargs             = isight.api('uuid').calls(kwargs)
            pvars['uuid_pool'] = kwargs.results.Name
        pvars = DotMap(dict(sorted(pvars.toDict().items())))
        # Return pvars
        return pvars

    #=========================================================================
    # Function: Main Menu, Profile Deployment
    #=========================================================================
    def server_profiles_deploy(self, kwargs):
        #=========================================================================
        # Deploy Server Profiles in Intersight
        #=========================================================================
        for e in list(kwargs.imm_dict.orgs.keys()):
            if kwargs.temp_templates[e].get('templates'):
                kwargs.imm_dict.orgs[e].templates = kwargs.temp_templates[e].templates
            for x in range(0,len(kwargs.imm_dict.orgs[e].profiles.server)):
                kwargs.imm_dict.orgs[e].profiles.server[x].action = 'Deploy'
        intersight.create_yaml_files(kwargs)
        kwargs = isight.imm('server').profiles(kwargs)
        for e in list(kwargs.imm_dict.orgs.keys()):
            if kwargs.imm_dict.orgs[e].get('templates'):
                kwargs.temp_templates[e].templates = kwargs.imm_dict.orgs[e].templates
                kwargs.imm_dict.orgs[e].pop('templates')
        for x in range(0,len(kwargs.imm_dict.orgs[kwargs.org].profiles.server)):
            kwargs.imm_dict.orgs[kwargs.org].profiles.server[x].action = 'No-op'
        intersight.create_yaml_files(kwargs)
        #=========================================================================
        # Return kwargs
        #=========================================================================
        return kwargs

    #=========================================================================
    # Function: Prompt for existing Server Profiles to use
    #=========================================================================
    def server_profiles_existing(self, kwargs):
        #=========================================================================
        # Obtain Physical Servers
        #=========================================================================
        api_filter = f"PermissionResources.Moid eq '{kwargs.org_moids[kwargs.org].moid}' and ManagementMode eq "
        if self.type == 'FIAttached': kwargs.api_filter = api_filter + f"'Intersight'"
        else: kwargs.api_filter = api_filter + f"'IntersightStandalone'"
        kwargs.method     = 'get'
        kwargs.uri        = 'compute/PhysicalSummaries'
        kwargs            = isight.api('physical_servers').calls(kwargs)
        physical_servers  = kwargs.pmoids
        physical_results  = kwargs.results
        for k,v in physical_servers.items(): kwargs.physical_moids[v.moid] = DotMap(dict(v.toDict(), **dict(serial=k)))
        #=========================================================================
        # Obtain Server Profiles
        #=========================================================================
        phmoids = kwargs.physical_moids
        kwargs.api_filter = f"Organization.Moid eq '{kwargs.org_moids[kwargs.org].moid}' and TargetPlatform eq '{self.type}'"
        kwargs.method     = 'get'
        kwargs.uri        = 'server/Profiles'
        kwargs            = isight.api('servers').calls(kwargs)
        profile_results   = sorted(kwargs.results, key=lambda ele: ele.Name)
        templates         = []
        template_results  = []
        for e in profile_results:
            if type(e.SrcTemplate.Moid) == str: templates.append(e.SrcTemplate.Moid)
        if len(templates) > 0:
            kwargs.names     = templates
            kwargs.uri       = kwargs.ezdata.server_template.intersight_uri
            kwargs           = isight.api('moid_filter').calls(kwargs)
            template_results = kwargs.results
        plist = [f'Serial: {phmoids[e.AssociatedServer.Moid].serial} || Moid: {e.Moid} || Server Profile: {e.Name}' for e in profile_results if e.AssignedServer != None]
        #=========================================================================
        # Prompt user for Server Profiles
        #=========================================================================
        accept_profiles = False
        while accept_profiles == False:
            kwargs.jdata      = kwargs.ezwizard.setup.properties.server_profiles
            kwargs.jdata.enum = plist
            profiles          = ezfunctions.variable_prompt(kwargs)
            answer            = questions.prompt_user.to_accept('profiles', DotMap(profiles=profiles), kwargs)
            if answer == True: accept_profiles = True
        physical_compute = []
        pregex           = re.compile(r'Serial: ([A-Z0-9]+) \|\| Moid: ([a-z0-9]+) ')
        server_profiles  = []
        for e in profiles:
            pmatch = pregex.search(e)
            indx   = next((index for (index, d) in enumerate(physical_results) if d['Serial'] == pmatch.group(1)), None)
            physical_compute.append(physical_results[indx])
            indx   = next((index for (index, d) in enumerate(profile_results) if d['Moid'] == pmatch.group(2)), None)
            server_profiles.append(profile_results[indx])
            kwargs.temp_servers[pmatch.group(1)].name          = profile_results[indx].Name
            kwargs.temp_servers[pmatch.group(1)].os_vendor     = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems[0].vendor
            kwargs.temp_servers[pmatch.group(1)].os_version    = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems[0].version.toDict()
            kwargs.temp_servers[pmatch.group(1)].template      = ''
            kwargs.temp_servers[pmatch.group(1)].template_type = 'server_template'
            if profile_results[indx].SrcTemplate != None:
                tdex = next((index for (index, d) in enumerate(template_results) if d['Moid'] == profile_results[indx].SrcTemplate.Moid), None)
                torg = kwargs.org_names[template_results[tdex].Organization.Moid]
                if torg == kwargs.org: kwargs.temp_servers[pmatch.group(1)].template = template_results[tdex].Name
                else: kwargs.temp_servers[pmatch.group(1)].template = f'{torg}/{template_results[tdex].Name}'
        #=========================================================================
        # Build Server Profile Dictionaries
        #=========================================================================
        kwargs.results = physical_compute
        kwargs         = isight.api(self.type).build_compute_dictionary(kwargs)
        for k in list(kwargs.servers.keys()):
            kwargs.server_profiles[k] = DotMap(sorted(dict(kwargs.servers[k].toDict(), **kwargs.temp_servers[k].toDict()).items()))
        for k,v in kwargs.server_profiles.items():
            pvars = v.toDict()
            # Add Policy Variables to imm_dict
            kwargs.class_path = f'wizard,server_profiles'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=========================================================================
        # return kwargs
        #=========================================================================
        return kwargs

    #=========================================================================
    # Function: Server Profile Questions
    #=========================================================================
    def server_profiles_questions(self, kwargs):
        accept_profiles = False
        while accept_profiles == False:
            #=========================================================================
            # Obtain Physical Servers
            #=========================================================================
            api_filter = f"PermissionResources.Moid eq '{kwargs.org_moids[kwargs.org].moid}' and ManagementMode eq "
            if self.type == 'FIAttached': kwargs.api_filter = api_filter + f"'Intersight'"
            else: kwargs.api_filter = api_filter + f"'IntersightStandalone'"
            kwargs.method     = 'get'
            kwargs.uri        = 'compute/PhysicalSummaries'
            kwargs = isight.api('physical_servers').calls(kwargs)
            physical_servers = kwargs.pmoids
            physical_results = kwargs.results
            physical_compute = []
            #=========================================================================
            # Prompt user for Boot Mode and Profile Source
            #=========================================================================
            kwargs.jdata       = kwargs.ezwizard.server.properties.profile_source
            profile_type       = ezfunctions.variable_prompt(kwargs)
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_type = profile_type
            #=========================================================================
            # Get Existing Profiles or Templates
            #=========================================================================
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
            #=========================================================================
            # Prompt user for Profile Source
            #=========================================================================
            names = sorted([f'{kwargs.org_names[e.Organization.Moid]}/{e.Name}' for e in source_results])
            kwargs.jdata = DotMap(
                default     = names[0],
                enum        = names,
                description = 'Select the existing profile to use.',
                title       = 'Profile Source',
                type        = 'string')
            profile_source = ezfunctions.variable_prompt(kwargs)
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile_source = profile_source
            #=========================================================================
            # Prompt user for Profile Count
            #=========================================================================
            kwargs.jdata = kwargs.ezwizard.server.properties.profile_count
            if not 'intersight.com' in kwargs.args.intersight_fqdn: kwargs.jdata.maximum = 25
            pcount = int(ezfunctions.variable_prompt(kwargs))
            #=========================================================================
            # Remove Servers already assigned to profiles
            #=========================================================================
            physical_moids = DotMap()
            for k, v in physical_servers.items(): physical_moids[v.moid] = DotMap(dict(v.toDict(), **{'serial':k}))
            physical_servers = physical_servers.toDict()
            phys_keys = list(physical_moids.keys())
            for e in profile_results:
                if e.AssignedServer != None and e.AssignedServer.Moid in phys_keys:
                    physical_servers.pop(physical_moids[e.AssignedServer.Moid].serial)
            physical_servers = DotMap(physical_servers)
            #=========================================================================
            # Prompt user for Server Profile Data
            #=========================================================================
            assignment_map = physical_servers.toDict()
            cvt = inflect.engine()
            for x in range(0,pcount):
                server_list = []
                assignment_map = DotMap({k: v for k, v in sorted(assignment_map.items(), key=lambda ele: ele[1].name)})
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
                    pcolor.Red(f'\n{"-"*108}\n'); len(False); sys.exit(1)
            answer = questions.prompt_user.to_accept('profiles', kwargs.temp_servers, kwargs)
            if answer == True: accept_profiles = True
        #=========================================================================
        # Build Server Profile Dictionaries
        #=========================================================================
        kwargs.results = physical_compute
        kwargs         = isight.api(self.type).build_compute_dictionary(kwargs)
        for k in list(kwargs.servers.keys()):
            kwargs.server_profiles[k] = DotMap(sorted(dict(kwargs.servers[k].toDict(), **kwargs.temp_servers[k].toDict()).items()))
        for k,v in kwargs.server_profiles.items():
            pvars = v.toDict()
            # Add Policy Variables to imm_dict
            kwargs.class_path = f'wizard,server_profiles'
            kwargs = ezfunctions.ez_append(pvars, kwargs)
        #=========================================================================
        # return kwargs
        #=========================================================================
        return kwargs

    #=========================================================================
    # Function: Main Menu, Initial Wizard Questions
    #=========================================================================
    def setup(self, kwargs):
        #=========================================================================
        # Loop Thru Wizard Menu for Deployment
        #=========================================================================
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.deployment_type = kwargs.deployment_type
        setup_list = ['build_type', 'deployment_method', 'target_platform', 'assignment_method', 'operating_systems', 'discovery']
        if  kwargs.deployment_type == 'OSInstall':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.assignment_method = 'Serial'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.build_type        = 'Machine'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.deployment_method = 'Python'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery         = True
            for e in ['assignment_method', 'build_type', 'deployment_method', 'discovery']: setup_list.remove(e)
            for e in ['assignment_method', 'build_type', 'target_platform', 'discovery']:
                kwargs[e] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup[e]
        elif re.search('Domain', kwargs.deployment_type):
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.assignment_method = 'Serial'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.build_type        = 'Machine'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform   = 'domain'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery         = True
            for e in ['assignment_method', 'build_type', 'target_platform', 'operating_systems', 'discovery']: setup_list.remove(e)
            for e in ['assignment_method', 'build_type', 'target_platform', 'discovery']:
                kwargs[e] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup[e]
        elif re.search('FIAttached|Standalone', kwargs.deployment_type):
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery         = True
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform   = kwargs.deployment_type
            for e in ['discovery', 'target_platform']: setup_list.remove(e); kwargs[e] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup[e]
        elif kwargs.deployment_type == 'Individual':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.assignment_method = 'Serial'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.build_type        = 'Interactive'
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery         = False
            for e in ['assignment_method', 'build_type', 'discovery']: setup_list.remove(e); kwargs[e] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup[e]
        for e in setup_list:
            if not kwargs.imm_dict.orgs[kwargs.org].wizard.setup[e]: kwargs = eval(f'questions.main_menu.{e}(kwargs)')
            else: kwargs[e] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup[e]
        if re.search('Domain|FIAttached|Individual|Standalone', kwargs.deployment_type):
            if not 'name_prefix' in list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.keys()): kwargs = questions.main_menu.name_prefix(kwargs)
            if not 'name_suffix' in list(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.keys()): kwargs = questions.main_menu.name_suffix(kwargs)
            if kwargs.deployment_type == 'FIAttached': fix_list = ['pools', 'policies']
            else: fix_list = ['policies']
            for p in fix_list:
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
        if re.search('FIAttached|Standalone', kwargs.deployment_type): kwargs = questions.policies.build_policy_list(kwargs)
        if 'Individual' in kwargs.deployment_type:
            kwargs = questions.main_menu.individual_types(kwargs)
            kwargs = questions.main_menu.individual(kwargs)
        if re.search('FIAttached', kwargs.deployment_type): kwargs.ptypes = ['Pools', 'Policies', 'Profiles']
        elif re.search('Standalone', kwargs.deployment_type): kwargs.ptypes = ['Policies', 'Profiles']
        if re.search('FIAttached|Standalone', kwargs.deployment_type):
            if 'Pools' in kwargs.ptypes: kwargs.main_menu_list.extend(kwargs.pool_list)
            if 'Policies' in kwargs.ptypes: kwargs.main_menu_list.extend(kwargs.policy_list)
            if 'Profiles' in kwargs.ptypes:
                if kwargs.target_platform == 'Standalone': kwargs.main_menu_list.extend(['server', 'server_template'])
                else: kwargs.main_menu_list.extend(['chassis', 'domain', 'server', 'server_template'])
            if not 'Resource Pool' == kwargs.imm_dict.orgs[kwargs.org].wizard.assignment_method:
                if 'resource' in kwargs.main_menu_list: kwargs.main_menu_list.remove('resource')
        # Return kwargs
        return kwargs

    #=========================================================================
    # Function: Main Menu, Quick Start - Domain Wizard
    #=========================================================================
    def quick_start_domain(self, kwargs):

        # Return kwargs
        return kwargs