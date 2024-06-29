#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, isight, pcolor, validating
    from copy import deepcopy
    from dotmap import DotMap
    import json, numpy, os, re, textwrap, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

# YAML Format Class
class yaml_dumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(yaml_dumper, self).increase_indent(flow, False)

#=============================================================================
# EZIMM Main Menu
#=============================================================================
class main_menu(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function: Prompt User for Assignment Method
    #=========================================================================
    def assignment_method(kwargs):
        kwargs.jdata = deepcopy(kwargs.ezwizard.setup.properties.assignment_method)
        if kwargs.target_platform == 'Standalone':
            kwargs.jdata.enum.pop('Chassis/Slot')
            kwargs.jdata.description.replace(' * Chassis/Slot:  Assign Server Profiles to Chassis/Slot.\n', '')
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.assignment_method = ezfunctions.variable_prompt(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Build Method
    #=========================================================================
    def build_type(kwargs):
        kwargs.jdata      = deepcopy(kwargs.ezwizard.setup.properties.build_type)
        kwargs.build_type = ezfunctions.variable_prompt(kwargs)
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.build_type = kwargs.build_type
        return kwargs

    #=========================================================================
    # Function: Prompt User for Discovery
    #=========================================================================
    def discovery(kwargs):
        kwargs.jdata     = deepcopy(kwargs.ezwizard.setup.properties.discovery)
        kwargs.discovery = ezfunctions.variable_prompt(kwargs)
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery = kwargs.discovery
        return kwargs

    #=========================================================================
    # Function: Prompt User for Deployment Type: Python/Terraform
    #=========================================================================
    def deployment_method(kwargs):
        if not re.search('Python|Terraform', kwargs.args.deployment_method):
            kwargs.jdata             = deepcopy(kwargs.ezwizard.setup.properties.deployment_method)
            kwargs.deployment_method = ezfunctions.variable_prompt(kwargs)
        else: kwargs.deployment_method = kwargs.args.deployment_method
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.deployment_method = kwargs.deployment_method
        return kwargs

    #=========================================================================
    # Function: Prompt User for Deployment Type
    #=========================================================================
    def deployment_type(kwargs):
        if not re.search('Convert|Deploy|Domain|Domain|Individual|OSInstall|Server', kwargs.args.deployment_type):
            kwargs.jdata           = deepcopy(kwargs.ezwizard.setup.properties.deployment_type)
            kwargs.deployment_type = ezfunctions.variable_prompt(kwargs)
        else: kwargs.deployment_type = kwargs.args.deployment_type
        return kwargs

    #=========================================================================
    # Function: Prompt User for Pools/Policies/Profiles to Create
    #=========================================================================
    def individual(kwargs):
        kwargs.main_menu_list = []
        for e in kwargs.ptypes:
            if 'Pools' in e: default = 'ip'; main_menu_list = kwargs.pool_list
            elif 'Policies' in e: default = 'bios'; main_menu_list = kwargs.policy_list
            elif 'Profiles' in e:
                default = 'server_template'
                if kwargs.target_platform == 'Standalone': main_menu_list = ['server', 'server_template']
                else: main_menu_list = ['chassis', 'domain', 'server', 'server_template']
            kwargs.jdata = DotMap(
                enum         = main_menu_list,
                default      = default,
                description  = f'Select the {e} to Apply to the Environment:',
                multi_select = True,
                sort         = False,
                title        = e,
                type         = 'string')
            kwargs.main_menu_list.extend(ezfunctions.variable_prompt(kwargs))
        return kwargs

    #=========================================================================
    # Function: Prompt User for Individual Types
    #=========================================================================
    def individual_types(kwargs):
        kwargs.jdata = DotMap(
            enum         = ['Pools', 'Policies', 'Profiles'],
            default      = 'Policies',
            description  = 'Choose the indidividual type(s) to create.',
            sort         = False,
            multi_select = True,
            title        = 'Individual Type(s)',
            type         = 'string')
        kwargs.ptypes = ezfunctions.variable_prompt(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Name Prefix
    #=========================================================================
    def name_prefix(kwargs):
        if not kwargs.imm_dict.orgs[kwargs.org].policies.get('name_prefix'):
            kwargs.jdata = deepcopy(kwargs.ezwizard.setup.properties.name_prefix)
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.name_prefix = ezfunctions.variable_prompt(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Name Suffix
    #=========================================================================
    def name_suffix(kwargs):
        if not kwargs.imm_dict.orgs[kwargs.org].policies.get('name_suffix'):
            kwargs.jdata = deepcopy(kwargs.ezwizard.setup.properties.name_suffix)
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.name_suffix = ezfunctions.variable_prompt(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Operating System Vendor
    #=========================================================================
    def operating_systems(kwargs):
        kwargs            = isight.software_repository('os_vendors').os_vendor_and_version(kwargs)
        kwargs.jdata      = deepcopy(kwargs.ezwizard.setup.properties.operating_system_vendor)
        kwargs.jdata.enum = sorted(list(kwargs.os_vendors.keys()))
        if kwargs.imm_dict.orgs[kwargs.org].wizard.deployment_type == 'OSInstall': kwargs.jdata.multi_select == False
        os_vendors = ezfunctions.variable_prompt(kwargs)
        if type(os_vendors) == str: os_vendors = [os_vendors]
        kwargs.operating_systems = []
        for e in os_vendors:
            dist_list = [e for k in list(kwargs.os_cfg_moids.keys()) for e in kwargs.os_cfg_moids[k].distributions]
            versions = sorted([k for k,v in kwargs.os_versions.items() if v.vendor_moid == kwargs.os_vendors[e].moid and v.moid in dist_list], reverse=True)
            kwargs.jdata             = deepcopy(kwargs.ezwizard.setup.properties.operating_system_version)
            kwargs.jdata.default     = versions[0]
            kwargs.jdata.description = (kwargs.jdata.description).replace('REPLACE', e)
            kwargs.jdata.enum        = versions
            kwargs.jdata.title       = (kwargs.jdata.title).replace('REPLACE', e)
            os_version               = ezfunctions.variable_prompt(kwargs)
            kwargs.operating_systems.append(DotMap(vendor=e,version=DotMap(moid=kwargs.os_versions[os_version].moid, name=os_version)))
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems = kwargs.operating_systems
        return kwargs

    #=========================================================================
    # Function: Prompt User to Load Previous Configurations
    #=========================================================================
    def previous_configuration(kwargs):
        dir_check = False; load_config = False
        if os.path.exists(kwargs.args.dir):
            for e in os.listdir(kwargs.args.dir):
                if re.search('^policies|pools|profiles|templates|wizard$', e): dir_check = True
            if dir_check == True and kwargs.args.load_config == False:
                kwargs.jdata = DotMap(
                    default     = True,
                    description = f'Import Configuration found in `{kwargs.args.dir}`',
                    title       = 'Load Existing Configuration(s)',
                    type        = 'boolean')
                load_config = ezfunctions.variable_prompt(kwargs)
                kwargs.args.load_config = True
            elif kwargs.args.load_config == True: load_config = True
            if load_config == True and kwargs.args.load_config == True:
                kwargs = DotMap(ezfunctions.load_previous_configurations(kwargs))
        return kwargs

    #=========================================================================
    # Function: Prompt User for Target Platform
    #=========================================================================
    def target_platform(kwargs):
        kwargs.jdata           = deepcopy(kwargs.ezwizard.setup.properties.target_platform)
        kwargs.target_platform = ezfunctions.variable_prompt(kwargs)
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform = kwargs.target_platform
        return kwargs

    # #=========================================================================
    # # Function: Prompt User for Target Platform
    # #=========================================================================
    # def target_platform(kwargs):
    #     kwargs.jdata           = deepcopy(kwargs.ezwizard.setup.properties.target_platform)
    #     kwargs.target_platform = ezfunctions.variable_prompt(kwargs)
    #     return kwargs

#=============================================================================
# EZIMM - Organizations
#=============================================================================
class orgs(object):
    #=========================================================================
    # Function: Prompt User for Intersight Organization
    #=========================================================================
    def organization(kwargs):
        org_list = sorted(list(kwargs.org_moids.keys()), key=str.casefold)
        if not kwargs.deployment_type == 'OSInstall': org_list.append('Create New')
        kwargs.jdata       = deepcopy(kwargs.ezdata.organization.allOf[1].properties.name)
        kwargs.jdata.enum  = org_list
        kwargs.jdata.sort  = False
        kwargs.jdata.title = 'Intersight Organization'
        if 'Create New' in org_list:
            kwargs.jdata.description   = 'Select an Existing Organization or `Create New`, for the organization to apply these changes within.'
        else: kwargs.jdata.description = 'Select an Existing Organization to apply these changes within.'
        kwargs.org = ezfunctions.variable_prompt(kwargs)
        wkeys = list(kwargs.imm_dict.orgs.keys())
        if not kwargs.org in wkeys: kwargs.imm_dict.orgs[kwargs.org].wizard.setup = DotMap()
        if kwargs.org == 'Create New':
            for e in ['description', 'name']:
                kwargs.jdata = deepcopy(kwargs.ezdata.organization.allOf[1].properties[e])
                if e == 'name': kwargs.jdata.default = 'example'
                kwargs[e]    = ezfunctions.variable_prompt(kwargs)
            kwargs.org    = kwargs.name
            kwargs.names  = [kwargs.org]
            kwargs.method = 'get'
            kwargs.uri    = deepcopy(kwargs.ezdata.resource_group.intersight_uri)
            kwargs = isight.api('resource_group').calls(kwargs)
            if not kwargs.pmoids.get(kwargs.org):
                kwargs.api_body = {"Description": kwargs.description, "Name":f'{kwargs.org}', "ObjectType":"resource.Group"}
                kwargs.method   = 'post'
                kwargs = isight.api('resource_group').calls(kwargs)
                rg_moid = kwargs.pmoid
            else: rg_moid = kwargs.pmoids[kwargs.org].moid
            kwargs.api_body = {
                "Description": kwargs.description, "Name":kwargs.org, "ObjectType":"organization.Organization",
                "ResourceGroups":[{"Moid": rg_moid, "ObjectType":"resource.Group"}]}
            kwargs.method = 'post'
            kwargs.uri    = deepcopy(kwargs.ezdata.organization.intersight_uri)
            kwargs        = isight.api('organization').calls(kwargs)
            kwargs.org_moids[kwargs.org] = DotMap(moid = kwargs.pmoid)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Intersight Shared Organization
    #=========================================================================
    def organization_shared(kwargs):
        kwargs.use_shared_org = False
        primary_org = kwargs.org
        if kwargs.org != 'default':
            kwargs.jdata = DotMap(
                default     = True,
                description = '  A Shared Organization can be used to share policies to other organization.'\
                    '  This can be helpful to reduce duplicate pools and policies for each organization.'\
                    f'  Would you like to configured a Shared Organization, or are you currently using a Shared Organization with `{kwargs.org}`?',
                sort        = False,
                title       = 'Intersight Shared Organization',
                type        = 'boolean')
            kwargs.use_shared_org = ezfunctions.variable_prompt(kwargs)
        if kwargs.use_shared_org == True:
            kwargs      = isight.api('organization').all_organizations(kwargs)
            org_results = kwargs.results
            org_list = sorted([e.Name for e in org_results if e.get('SharedWithResources')], key=str.casefold)
            if len(org_list) == 0: org_list.append('Create New')
            elif not kwargs.deployment_type == 'OSInstall': org_list.append('Create New')
            if 'Create New' in org_list: description = 'Select an Existing Organization or `Create New`, for the shared Organization.'
            else: description = 'Select an Existing Organization, for the shared Organization.'
            if len(org_list) > 1:
                kwargs.jdata = DotMap(
                    enum        = org_list,
                    default     = org_list[0],
                    description = description,
                    sort        = False,
                    title       = 'Intersight Shared Organization',
                    type        = 'string')
                shared_org = ezfunctions.variable_prompt(kwargs)
            else: shared_org = org_list[0]
            if shared_org == 'Create New':
                for e in ['description', 'name']:
                    kwargs.jdata = deepcopy(kwargs.ezdata.organization.allOf[1].properties[e])
                    if e == 'name': kwargs.jdata.default = 'shared_org'
                    kwargs[e]    = ezfunctions.variable_prompt(kwargs)
                kwargs.shared_org = kwargs.name
                org_list = sorted([e.Name for e in org_results if not e.get('SharedWithResources')], key=str.casefold)
                kwargs.jdata = DotMap(
                    enum         = org_list,
                    default      = org_list[0],
                    description  = f'Select the Organization(s) to Share pools/policies/templates from Organization {kwargs.shared_org}.',
                    multi_select = True,
                    title        = 'Intersight Shared Organization',
                    type         = 'string')
                shared_sub_orgs = ezfunctions.variable_prompt(kwargs)
                kwargs.api_body = {"Description": kwargs.description, "Name": kwargs.shared_org, "ObjectType":"organization.Organization"}
                kwargs.method = 'post'
                kwargs.uri    = deepcopy(kwargs.ezdata.organization.intersight_uri)
                kwargs = isight.api('organization').calls(kwargs)
                kwargs.org_moids[kwargs.shared_org] = DotMap(moid = kwargs.pmoid)
                kwargs.build_skip = True
                kwargs.bulk_list  = []
                for e in shared_sub_orgs:
                    kwargs.bulk_list.append(
                        {"SharedResource":{"Moid": kwargs.org_moids[kwargs.shared_org].moid, "ObjectType":"organization.Organization"},
                        "SharedWithResource":{"Moid": kwargs.org_moids[e].moid, "ObjectType":"organization.Organization"}})
                kwargs.uri    = 'iam/SharingRules'
                kwargs = isight.imm('sharing_rules').bulk_request(kwargs)
            else:
                kwargs.shared_org = shared_org
                indx = next((index for (index, d) in enumerate(org_results) if d['Name'] == shared_org), None)
                in_shared_orgs = False
                for e in org_results[indx].SharedWithResources:
                    if kwargs.org_moids[kwargs.org].moid == e.Moid: in_shared_orgs = True
                if in_shared_orgs == False:
                    kwargs.build_skip = True
                    kwargs.bulk_list  = []
                    kwargs.bulk_list.append(
                        {"SharedResource":{"Moid": kwargs.org_moids[kwargs.shared_org].moid, "ObjectType":"organization.Organization"},
                        "SharedWithResource":{"Moid": kwargs.org_moids[kwargs.org].moid, "ObjectType":"organization.Organization"}})
                    kwargs.uri    = 'iam/SharingRules'
                    kwargs = isight.imm('sharing_rules').bulk_request(kwargs)
            kwargs.org = primary_org
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.shared_org = kwargs.shared_org
        else: kwargs.imm_dict.orgs[kwargs.org].wizard.setup.pop('shared_org')
        return kwargs

#=============================================================================
# EZIMM - Operating System Installation
#=============================================================================
class os_install(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function: Prompt User for OS Image
    #=========================================================================
    def sw_repo_os_cfg(op_system, kwargs):
        if not kwargs.get('os_cfg_results'): kwargs  = isight.software_repository('cfg').os_configuration(kwargs)
        elist = []; os_configuration = []
        for e in kwargs.os_cfg_results:
            if op_system.version.moid in [f.Moid for f in e.Distributions]:
                if 'shared' in e.Owners:
                    elist.append(f'Location: Intersight || Name: {e.Name} || Moid: {e.Moid}')
                else: elist.append(f'Location: {e.Source.LocationLink} || Name: {e.Name} || Moid: {e.Moid}')
                os_configuration.append(e)
        elist.append('Upload a New OS Configuration File')
        if len(elist) > 1:
            kwargs.jdata         = deepcopy(kwargs.ezwizard.setup.properties.sw_repo_os_cfg)
            kwargs.jdata.default = elist[0]
            kwargs.jdata.enum    = elist
            answer = ezfunctions.variable_prompt(kwargs)
            if 'Upload' in answer: os_cfg = os_install.sw_repo_os_cfg_add(op_system, kwargs)
            else:
                regex  = re.compile(r'Location: (.*) \|\| Name: (.*) \|\| Moid: (.*)$')
                match  = regex.search(answer)
                cfg    = DotMap(location = match.group(1), name = match.group(2), moid = match.group(3))
                indx   = next((index for (index, d) in enumerate(os_configuration) if d['Moid'] == cfg.moid), None)
                os_cfg = os_configuration[indx]
        elif len(elist) == 1: os_cfg = os_install.sw_repo_os_cfg_add(op_system, kwargs)
        else:
            pcolor.Red(f'\n{"-"*108}\n')
            pcolor.Red(f'  !!!ERROR!!! No Operating System Configuration File found in Intersight Organization `{kwargs.org}` to support Vendor: '\
                    f'`{op_system.vendor}` Version: `{op_system.version.name}`.')
            pcolor.Red(f'  Exiting...  intersight-tools/classes/isight.py line 507')
            pcolor.Red(f'\n{"-"*108}\n'); sys.exit(1)
        #=====================================================================
        # Test Repository URL and Return kwargs
        #=====================================================================
        kwargs.os_cfg_dict = os_cfg
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.os_configuration = os_cfg.Moid
        for x in range(0,len(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles)):
            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].os_configuration = os_cfg.Moid
        return kwargs

    #=========================================================================
    # Function: Prompt User for OS Image
    #=========================================================================
    def sw_repo_os_cfg_add(op_system, kwargs):
        sensitive_list = []
        #=====================================================================
        # Prompt User for Operating System Language
        #=====================================================================
        #valid = False
        #while valid == False:
        #    valid_confirm = False
        #    while valid_confirm == False:
        #        azs_languages = kwargs.ezwizard.setup.properties.azure_stack_hci_languages.enum
        #        win_languages = [DotMap(e) for e in json.load(open(os.path.join(kwargs.script_path, 'variables', 'windowsLocals.json'), 'r'))]
        #        kwargs.jdata  = deepcopy(kwargs.ezwizard.setup.properties.operating_system_language)
        #        for e in azs_languages:
        #            for l in win_languages:
        #                if e in l.language:
        #                    kwargs.jdata.enum.append(l.language)
        #        answer                   = ezfunctions.variable_prompt(kwargs)
        #        kwargs.jdata             = deepcopy(kwargs.ezwizard.setup.properties.sw_repo_os_cfg_add)
        #        kwargs.jdata.description = f'{answer}\n Please Confirm the selected Language.'
        #        confirm                  = ezfunctions.variable_prompt(kwargs)
        #        if confirm == True: valid_confirm = True
        #    if os.path.isfile(answer): valid = True
        windows_language = DotMap(language_pack = 'English - United States', layered_driver = 0)
        kwargs = ezfunctions.windows_languages(windows_language, kwargs)
        sensitive_list.extend(['local_administrator_password', 'azure_stack_lcm_password'])
        for e in sensitive_list:
            kwargs.sensitive_var = e
            kwargs = ezfunctions.sensitive_var_value(kwargs)
            kwargs[e] = kwargs.var_value
        #=====================================================================
        # Prompt User for Operating System Configuration File Path
        #=====================================================================
        valid = False
        while valid == False:
            valid_confirm = False
            while valid_confirm == False:
                kwargs.jdata             = deepcopy(kwargs.ezwizard.setup.properties.sw_repo_os_cfg_add)
                kwargs.jdata.default     = os.path.join(kwargs.script_path, 'examples', 'azure_stack_hci', '22H3', 'AzureStackHCIIntersight.xml')
                answer                   = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata             = deepcopy(kwargs.ezwizard.setup.properties.sw_repo_os_cfg_add_confirm)
                kwargs.jdata.description = f'"{answer}"\n-\n\n Please Confirm the Path above is Correct.'
                confirm                  = ezfunctions.variable_prompt(kwargs)
                if confirm == True: valid_confirm = True
            if os.path.isfile(answer): valid = True
        pcolor.LightPurple(f'\n{"-"*108}\n')
        #=====================================================================
        # Upload the Operating System Configuration File
        #=====================================================================
        vsplist       = (op_system.version.name.split(' '))
        version       = f'{vsplist[0]}{vsplist[2]}'
        ctemplate     = answer.split(os.sep)[-1]
        template_name = version + '-' + ctemplate.split('_')[0]
        kwargs.os_config_template = template_name
        if not kwargs.distributions.get(version):
            kwargs.api_filter = f"Version eq '{op_system.version.name}'"
            kwargs.build_skip = True
            kwargs.method     = 'get'
            kwargs.uri        = 'hcl/OperatingSystems'
            kwargs            = isight.api('hcl_operating_system').calls(kwargs)
            kwargs.distributions[version].moid = kwargs.results[0].Moid
        kwargs.distribution_moid = kwargs.distributions[version].moid
        file_content = (open(os.path.join(answer), 'r')).read()
        for e in ['LayeredDriver:layered_driver', 'UILanguageFallback:secondary_language']:
            elist = e.split(':')
            rstring = '%s<%s>{{ .%s }}</%s>\n' % (" "*12, elist[0], elist[1], elist[0])
            if kwargs.language[elist[1]] == '': file_content = file_content.replace(rstring, '')
        kwargs.file_content = file_content
        kwargs.api_body     = ezfunctions.os_configuration_file(kwargs)
        kwargs.method       = 'post'
        kwargs.uri          = 'os/ConfigurationFiles'
        kwargs              = isight.api('os_configuration').calls(kwargs)
        kwargs.os_cfg_moids[template_name] = DotMap(moid = kwargs.pmoid)
        kwargs.os_cfg_moid = kwargs.os_cfg_moids[template_name].moid
        #=====================================================================
        # Return kwargs
        #=====================================================================
        return kwargs.results

    #=========================================================================
    # Function: Prompt User for OS Image
    #=========================================================================
    def sw_repo_os_image(op_system, kwargs):
        kwargs    = isight.software_repository('osi').os_images(kwargs)
        elist     = []
        os_images = []
        for e in kwargs.os_image_results:
            if e.Vendor == op_system.vendor and e.Version == op_system.version.name:
                elist.append(f'Location: {e.Source.LocationLink} || Name: {e.Name} || Moid: {e.Moid}')
                os_images.append(deepcopy(e))
        use_image = False
        while use_image == False:
            if len(elist) > 1:
                    kwargs.jdata         = deepcopy(kwargs.ezwizard.setup.properties.sw_repo_os_image)
                    kwargs.jdata.default = elist[0]
                    kwargs.jdata.enum    = elist
                    answer   = ezfunctions.variable_prompt(kwargs)
                    regex    = re.compile(r'Location: (.*) \|\| Name: (.*) \|\| Moid: ([a-z0-9]+)$')
                    match    = regex.search(answer)
                    sw       = DotMap(location = match.group(1), name = match.group(2), moid = match.group(3))
                    indx     = next((index for (index, d) in enumerate(os_images) if d['Moid'] == sw.moid), None)
                    os_image = os_images[indx]
            elif len(elist) == 1: os_image = os_images[0]
            else:
                pcolor.Red(f'\n{"-"*108}\n')
                pcolor.Red(f'  !!!ERROR!!! No Operating System Image Found in Intersight Organization `{kwargs.org}` to support Vendor: `{op_system.vendor}`.')
                pcolor.Red(f'  Exiting...  intersight-tools/classes/isight.py line 549')
                pcolor.Red(f'\n{"-"*108}\n'); sys.exit(1)
            if not 'Custom-Cisco' in os_image.Source.LocationLink and op_system.vendor == 'VMware':
                iso = os_image.Source.LocationLink.split('/')
                pcolor.Yellow(f'Confirm Image before proceeding: `{iso[-1]}`')
                kwargs.jdata = deepcopy(kwargs.ezwizard.setup.properties.sw_repo_os_image_confirm)
                answer = ezfunctions.variable_prompt(kwargs)
                if answer == True: use_image = True
            else: use_image = True
        #=====================================================================
        # Test Repository URL and Return kwargs
        #=====================================================================
        url = os_image.Source.LocationLink
        if kwargs.args.repository_check_skip == False: ezfunctions.test_repository_url(url)
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.os_image = os_image.Moid
        for x in range(0,len(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles)):
            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].os_image = os_image.Moid
        return kwargs

    #=========================================================================
    # Function: Prompt User for Server Configuration Utility
    #=========================================================================
    def sw_repo_scu(kwargs):
        elist         = []
        kwargs        = isight.software_repository('scu').scu(kwargs)
        kwargs.models = list(numpy.unique(numpy.array([e.model for e in kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles])))
        for e in kwargs.scu_results:
            elist.append(f'Location: {e.Source.LocationLink} || Version: {e.Version} || Name: {e.Name} || Supported Models: {", ".join(e.SupportedModels)} || Moid: {e.Moid}')
        def print_error(kwargs):
            models = ", ".join(kwargs.models)
            pcolor.Red(f'\n{"-"*108}\n')
            pcolor.Red(f'  !!!ERROR!!! No Server Configuration Utility Image Found in Intersight Organization `{kwargs.org}` to support Models: {models}.  Exiting....')
            pcolor.Red(f'  Exiting...  (intersight-tools/classes/isight.py line 564)')
            pcolor.Red(f'\n{"-"*108}\n'); sys.exit(1)
        models = True
        scu    = []
        if len(elist) > 1:
            kwargs.jdata         = deepcopy(kwargs.ezwizard.setup.properties.sw_repo_scu)
            kwargs.jdata.default = elist[0]
            kwargs.jdata.enum    = elist
            answer = ezfunctions.variable_prompt(kwargs)
            regex  = re.compile(r'Location: (.*) \|\| Version: (.*) \|\| Name: (.*) \|\| .* Moid: ([a-z0-9]+)$')
            match  = regex.search(answer)
            sw     = DotMap(location = match.group(1), version = match.group(2), name = match.group(3), moid=match.group(4))
            indx   = next((index for (index, d) in enumerate(kwargs.scu_results) if d['Moid'] == sw.moid), None)
            for d in kwargs.models:
                if not d in kwargs.scu_results[indx].SupportedModels: models = False
            if models == True: scu = kwargs.scu_results[indx]
        elif len(elist) == 1:
            for d in kwargs.models:
                if not d in kwargs.scu_results[0].SupportedModels: models = False
            if models == True: scu = kwargs.scu_results[0]
        else: print_error(kwargs)
        if len(scu) == 0: print_error(kwargs)
        #=====================================================================
        # Test Repository URL and Return kwargs
        #=====================================================================
        url = scu.Source.LocationLink
        if kwargs.args.repository_check_skip == False: ezfunctions.test_repository_url(url)
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server_configuration_utility = scu.Moid
        for x in range(0,len(kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles)):
            kwargs.imm_dict.orgs[kwargs.org].wizard.server_profiles[x].scu = scu.Moid
        return kwargs

#=============================================================================
# Build IMM Policies
#=============================================================================
class policies(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function: Prompt User to Add Policy to IMM Dictionary
    #=========================================================================
    def add_to_imm_dict(self, pvars, kwargs):
        policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
        accept       = prompt_user(self.type).to_accept(f'the {policy_title} Policy', pvars, kwargs)
        if accept == True:
            kwargs.class_path = f'policies,{self.type}'
            kwargs            = ezfunctions.ez_append(pvars, kwargs)
            if kwargs.use_shared_org == True:  kwargs.policy_name = f'{kwargs.shared_org}/{pvars.name}'
            else: kwargs.policy_name = pvars.name
            policy_accept = True
        else: ezfunctions.message_starting_over(self.type)
        return policy_accept, kwargs

    #=========================================================================
    # Function: Announcement
    #=========================================================================
    def announcement(self, kwargs):
        policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
        if   kwargs.profile_type == 'chassis':  name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.chassis.name
        elif kwargs.profile_type == 'domain':   name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.name
        elif kwargs.profile_type == 'server':   name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server.name
        elif kwargs.profile_type == 'template': name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template.name
        for e in kwargs.ezdata.ezimm_class.properties.policies.enum:
            if self.type in kwargs.ezdata.ezimm_class.properties[e].enum: yaml_file = e
        pcolor.LightPurple(f'\n{"-"*108}\n')
        pcolor.Cyan(f'  The next group of questions will be for configuring a(n) `{policy_title}` Policy to attach to {kwargs.profile_type} profile '\
                    f'`{name}`.  The wizard will ask for input and confirm the policy inputs before proceeding to the next policy.\n')
        pcolor.Cyan(f'  This wizard will save the configuration for the `{self.type}` policy to the following file:')
        pcolor.Yellow(f'    - {os.path.join(kwargs.args.dir, "policies", f"{yaml_file}.yaml")}')
        input(f'\n Press Enter to Continue: ')
        return kwargs

    #=========================================================================
    # Function: Build Pool/Policy List(s)
    #=========================================================================
    def build_policy_list(kwargs):
        kwargs.policy_list = []; kwargs.pool_list = []
        for k, v in kwargs.ezdata.items():
            if v.intersight_type == 'pool' and not '.' in k: kwargs.pool_list.append(k)
            elif v.intersight_type == 'policy':
                if kwargs.target_platform == 'FIAttached':
                    if not '.' in k and ('chassis' in v.target_platforms or 'FIAttached' in v.target_platforms):  kwargs.policy_list.append(k)
                elif kwargs.target_platform == 'chassis':
                    if not '.' in k and 'chassis' in v.target_platforms:  kwargs.policy_list.append(k)
                elif kwargs.target_platform == 'domain':
                    if not '.' in k and 'domain' in v.target_platforms:  kwargs.policy_list.append(k)
                else:
                    if 'Standalone' in v.target_platforms and not '.' in k: kwargs.policy_list.append(k)
        return kwargs

    #=========================================================================
    # Function: Create YAML Files
    #=========================================================================
    def create_yaml_files(kwargs):
        orgs   = list(kwargs.org_moids.keys())
        kwargs = ezfunctions.remove_duplicates(orgs, ['policies', 'wizard'], kwargs)
        ezfunctions.create_yaml(orgs, kwargs)

    #=========================================================================
    # Function: Prompt User for Ethernet Network Control Policy Settings
    #=========================================================================
    def ethernet_network_control(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata              = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default      = 'both-cdp-lldp'
                pvars.name                = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata              = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.cdp_enable)
                kwargs.jdata.description  = 'Do you want to Enable CDP for this policy?'
                pvars.cdp_enable          = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata              = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.lldp_enable_receive)
                kwargs.jdata.description  = 'Do you want to Enable LLDP for this policy?'
                pvars.lldp_enable_receive = ezfunctions.variable_prompt(kwargs)
                if pvars.lldp_enable_recieve == True: pvars.lldp_enable_transmit
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                pvars, kwargs = policies(self.type).optional_attributes(pvars, kwargs)
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Ethernet Network Group Policy Settings
    #=========================================================================
    def ethernet_network_group(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            if type(kwargs.vlan_policy) == str: vlan_policy = kwargs.vlan_policy
            else: vlan_policy = policies('vlan').vlan(kwargs)
            kwargs = policies.vlan_ranges(vlan_policy, kwargs)
            vlans  = kwargs.vlans, vlan_range = kwargs.vlan_range
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata         = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'eth-grp'
                pvars.name           = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata         = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.allowed_vlans)
                pvars.allowed_vlans  = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata         = deepcopy(kwargs.ezwizard[self.type].properties.configure_native_vlan)
                configure_native     = ezfunctions.variable_prompt(kwargs)
                if configure_native == True:
                    kwargs.jdata      = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.native_vlan)
                    pvars.native_vlan = int(ezfunctions.variable_prompt(kwargs))
                vlan_full   = ezfunctions.vlan_list_full(pvars.allowed_vlans)
                if not pvars.native_vlan in vlan_full:
                    vlan_full.append(pvars.native_vlan); vlan_full = sorted(vlan_full)
                skip_prompt = False
                valid_vlans = validating.vlan_list(vlan_full)
                if valid_vlans == False: skip_prompt = True; break
                pcolor.Yellow('')
                for e in vlan_full:
                    if not e in vlans:
                        pcolor.Yellow(f'  * !!! ERROR !!! - VLAN `{e}` is not in the VLAN Policy.  VLAN Policy VLANS are: `{vlan_range}`')
                        skip_prompt = True; break
                pcolor.Yellow('')
                if valid_vlans == False: skip_prompt = True; break
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                if skip_prompt == True: pass
                else: policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Flow Control Policy Settings
    #=========================================================================
    def flow_control(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata         = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'flow-ctrl'
                pvars.name           = ezfunctions.variable_prompt(kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                pvars, kwargs = policies(self.type).optional_attributes(pvars, kwargs)
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for IMC Access Policy Settings
    #=========================================================================
    def imc_access(self, kwargs):
        def inband_vlan(pvars, kwargs):
            kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.inband_vlan_id)
            pvars.inband_vlan_id = ezfunctions.variable_prompt(kwargs)
            return pvars
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'kvm'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezwizard[self.type].properties.mgmt_types)
                mgmt_types   = ezfunctions.variable_prompt(kwargs)
                for e in mgmt_types:
                    ptitle = (e.replace('_', ' ')).title()
                    pcolor.Yellow(f'\n\n  ** IP Pool for {ptitle}  **')
                    pvars[f'{e}_ip_pool'] = pools('ip').ip(kwargs)
                    if e == 'inband':
                        pvars = inband_vlan(pvars, kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        if kwargs.profile_type == 'chassis':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.chassis[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'server':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server[f'{self.type}_policy'] = kwargs.policy_name
        else: kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template[f'{self.type}_policy'] = kwargs.policy_name
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Link Aggregation Policy Settings
    #=========================================================================
    def link_aggregation(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata              = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default      = 'link-agg'
                pvars.name                = ezfunctions.variable_prompt(kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                pvars, kwargs = policies(self.type).optional_attributes(pvars, kwargs)
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Link Control Policy Settings
    #=========================================================================
    def link_control(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata         = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'link-ctrl'
                pvars.name           = ezfunctions.variable_prompt(kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                pvars, kwargs = policies(self.type).optional_attributes(pvars, kwargs)
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Network Connectivity Policy Settings
    #=========================================================================
    def network_connectivity(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'dns'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezwizard.policies.properties.ip_protocols)
                kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', 'the network connectivity (DNS) policy')
                ip_protocols = ezfunctions.variable_prompt(kwargs)
                dns_from_dhcp = False
                if re.search('server|template', kwargs.profile_type):
                    kwargs.jdata = deepcopy(kwargs.ezwizard[self.type].properties.dns_from_dhcp)
                    dns_from_dhcp = ezfunctions.variable_prompt(kwargs)
                    if dns_from_dhcp == True:
                        for p in ip_protocols: pvars[f'obtain_{p.lower()}_dns_from_dhcp'] = True
                        kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.enable_dynamic_dns)
                        dynamic_dns = ezfunctions.variable_prompt(kwargs)
                        if dynamic_dns == True:
                            pvars.enable_dynamic_dns = dynamic_dns
                            kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.update_domain)
                            pvars.update_domain = ezfunctions.variable_prompt(kwargs)
                if dns_from_dhcp == False:
                    for protocol in ip_protocols:
                        p = protocol.replace('IP', '')
                        kwargs.jdata = deepcopy(kwargs.ezdata[f'ip.{protocol.lower()}_configuration'].properties.primary_dns)
                        primary      = ezfunctions.variable_prompt(kwargs)
                        dns_servers  = [primary]
                        kwargs.jdata = deepcopy(kwargs.ezdata[f'ip.{protocol.lower()}_configuration'].properties.secondary_dns)
                        kwargs.jdata.optional = True
                        secondary    = ezfunctions.variable_prompt(kwargs)
                        if len(secondary) > 0: dns_servers.append(secondary)
                        pvars[f'dns_servers_{p}'] = dns_servers
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        if kwargs.profile_type == 'domain':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'server':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server[f'{self.type}_policy'] = kwargs.policy_name
        else: kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template[f'{self.type}_policy'] = kwargs.policy_name
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for NTP Policy Settings
    #=========================================================================
    def ntp(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'ntp'
                name = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.ntp_servers['items'])
                kwargs.jdata.description = kwargs.jdata.description + '  You can Add up to 4 NTP Servers.'
                ntp_servers = []
                for x in range (0,4):
                    if x >= 1: kwargs.jdata.optional = True
                    ntp_server = ezfunctions.variable_prompt(kwargs)
                    if len(ntp_server) > 0: ntp_servers.append(ntp_server)
                    else: break
                timezone = prompt_user.for_timezone(kwargs)
                pvars.name   = name; pvars.ntp_servers = ntp_servers; pvars.timezone = timezone
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        if kwargs.profile_type == 'domain':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'server':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server[f'{self.type}_policy'] = kwargs.policy_name
        else: kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template[f'{self.type}_policy'] = kwargs.policy_name
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Ask user if they want to attach the policy
    #=========================================================================
    def optional(self, kwargs):
        policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
        if   kwargs.profile_type == 'chassis':  name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.chassis.name
        elif kwargs.profile_type == 'domain':   name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.name
        elif kwargs.profile_type == 'server':   name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server.name
        elif kwargs.profile_type == 'template': name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template.name
        if name == kwargs.type_dotmap:
            if kwargs.profile_type == 'template': name = 'Template'
            else: name = f'{kwargs.profile_type} profile'.title()
        kwargs.jdata = DotMap(
            description = f'Do you want to add a(n) `{policy_title}` to `{name}`:',
            default = True, title = f'{policy_title} Policy', type = 'boolean')
        optional_answer = ezfunctions.variable_prompt(kwargs)
        return optional_answer

    #=========================================================================
    # Function: Prompt User for Optional Arguments
    #=========================================================================
    def optional_attributes(self, pvars, kwargs):
        if '.' in self.type: ppolicy = self.type.split('.')[1]
        else: ppolicy = self.type
        policy_title             = ezfunctions.mod_pol_description((ppolicy.replace('_', ' ')).capitalize())
        if   self.type == 'power' and kwargs.profile_type == 'chassis':
            kwargs.jdata   = deepcopy(kwargs.ezwizard[self.type].properties.chassis_optional_attributes)
        elif self.type == 'power':
            kwargs.jdata   = deepcopy(kwargs.ezwizard[self.type].properties.server_optional_attributes)
        else: kwargs.jdata = deepcopy(kwargs.ezwizard[self.type].properties.optional_attributes)
        kwargs.jdata.description = (kwargs.jdata.description).replace('REPLACE', policy_title)
        kwargs.jdata.title       = (kwargs.jdata.title).replace('REPLACE', policy_title)
        attributes = ezfunctions.variable_prompt(kwargs)
        for attr in attributes:
            if '.' in self.type:
                kwargs.jdata   = deepcopy(kwargs.ezdata[self.type].properties[attr])
            else: kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties[attr])
            pvars[attr]  = ezfunctions.variable_prompt(kwargs)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for New or Existing Policy
    #=========================================================================
    def policy_select(self, kwargs):
        kwargs.names  = [kwargs.org_moids[kwargs.org].moid]
        if kwargs.use_shared_org == True: kwargs.names.append(kwargs.org_moids[kwargs.shared_org].moid)
        kwargs.method = 'get'
        kwargs.uri    = deepcopy(kwargs.ezdata[self.type].intersight_uri)
        kwargs        = isight.api('multi_org').calls(kwargs)
        policy_keys   = sorted([f'{kwargs.org_names[e.Organization.Moid]}/{e.Name}' for e in kwargs.results])
        for e in kwargs.results: kwargs.isight[kwargs.org_names[e.Organization.Moid]].policies[self.type][e.Name] = e.Moid
        org_keys = list(kwargs.org_moids.keys())
        for org in org_keys:
            pkeys = list(kwargs.imm_dict.orgs[org].policies.keys())
            if self.type in pkeys:
                for e in kwargs.imm_dict.orgs[org].policies[self.type]: policy_keys.append(f'{org}/{e.name}')
        policy_keys = sorted(list(numpy.unique(numpy.array(policy_keys))))
        if len(policy_keys) > 0:
            policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
            kwargs.jdata = deepcopy(kwargs.ezwizard.policies.properties.policy)
            kwargs.jdata.description = (
                kwargs.jdata.description.replace('REPLACE', policy_title)).replace('PROFILE_TYPE', (kwargs.profile_type).capitalize())
            kwargs.jdata.title = kwargs.jdata.title.replace('REPLACE', policy_title)
            if type(kwargs.ignore_create_new) == bool and kwargs.ignore_create_new == True: pass
            else: policy_keys.append('Create New')
            kwargs.jdata.default = policy_keys[0]
            kwargs.jdata.enum    = policy_keys
            kwargs.jdata.sort    = False
            policy_name = ezfunctions.variable_prompt(kwargs)
            policy_name = policy_name.replace(f'{kwargs.org}/', '')
        else: policy_name = 'Create New'
        return policy_name

    #=========================================================================
    # Function: Prompt User for Port Policy Settings
    #=========================================================================
    def port(self, kwargs):
        args = DotMap()
        for e in ['A', 'B']:
            pcolor.Yellow(f'\n\n ** Fabric {e} Port Policy **')
            args[f'fabric_{e.lower()}'].name = policies(self.type).policy_select(kwargs)
            if args[f'fabric_{e.lower()}'].name == 'Create New': break
        if args.fabric_a.name == 'Create New' or args.fabric_b.name == 'Create New':
            policies(self.type).announcement(kwargs)
            kwargs.available_ports    = []
            kwargs.fc_converted_ports = []
            kwargs.domain = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain
            if   kwargs.domain.model == 'UCS-FI-6536':     kwargs.available_ports = [x for x in range(1,37)]
            elif kwargs.domain.model == 'UCS-FI-6454':     kwargs.available_ports = [x for x in range(1,55)]
            elif kwargs.domain.model == 'UCS-FI-64108':    kwargs.available_ports = [x for x in range(1,109)]
            elif kwargs.domain.model == 'UCSX-S9108-100G': kwargs.available_ports = [x for x in range(1,9)]
            policy_accept = False
            while policy_accept == False:
                #=====================================================================
                # Query for Physical Ports with Optics Installed
                #=====================================================================
                domain_moid  = kwargs.domain.moid
                port_results = DotMap()
                for e in ['ether', 'fc']:
                    kwargs.api_filter = f"RegisteredDevice.Moid eq '{domain_moid}'"
                    kwargs.build_skip = True
                    kwargs.method     = 'get'
                    kwargs.uri        = f'{e}/PhysicalPorts'
                    kwargs = isight.api('physical_ports').calls(kwargs)
                    port_results[f'{e}'] = kwargs.results
                kwargs.eth_ports = []; kwargs.fc_ports = []
                for i in ['ether', 'fc']:
                    for e in port_results[i]:
                        if ('FC' in e.TransceiverType or 'sfp' in e.TransceiverType) and e.SwitchId == 'A':
                            kwargs.fc_ports.append(DotMap(breakout_port_id = e.AggregatePortId, moid = e.Moid, port_id = e.PortId,
                                                          slot_id = e.SlotId, transceiver = e.TransceiverType))
                        elif i == 'ether' and e.SwitchId == 'A':
                            kwargs.eth_ports.append(DotMap(breakout_port_id = e.AggregatePortId, moid = e.Moid, port_id = e.PortId,
                                                           slot_id = e.SlotId, transceiver = e.TransceiverType))
                        elif i == 'fc' and e.OperState == 'up' and e.SwitchId == 'A':
                            kwargs.fc_ports.append(DotMap(breakout_port_id = e.AggregatePortId, moid = e.Moid, port_id = e.PortId,
                                                           slot_id = e.SlotId, transceiver = 'sfp'))
                        elif i == 'fc' and e.SwitchId == 'A':
                            kwargs.fc_ports.append(DotMap(breakout_port_id = e.AggregatePortId, moid = e.Moid, port_id = e.PortId,
                                                           slot_id = e.SlotId, transceiver = 'unknown'))
                    kwargs = policies.port_map(i.replace('er', ''), kwargs)
                #=====================================================================
                # Switch Control Policy
                #=====================================================================
                if type(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control_policy) != str:
                    pcolor.Yellow('\n\n  ** Preparing Switch Control Policy for Port Configuration/VSAN Policy if required **')
                    if type(kwargs.sw_policy) != str: kwargs.sw_policy = policies('switch_control').policy_select(kwargs)
                    if kwargs.sw_policy != 'Create New':
                        if '/' in kwargs.sw_policy: policy = kwargs.sw_policy.split('/')[1]
                        else: policy = kwargs.sw_policy
                        kwargs = isight.api_get(False, [kwargs.sw_policy], 'switch_control', kwargs)
                        indx = next((index for (index, d) in enumerate(kwargs.results) if d['Name'] == policy), None)
                        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.name              = kwargs.sw_policy
                        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.policy            = kwargs.sw_policy
                        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.switching_mode_fc = kwargs.results[indx].FcSwitchingMode
                        policies.create_yaml_files(kwargs)
                    else:
                        pcolor.Yellow('\n\n  ** Switch Control Policy Name **')
                        kwargs.jdata         = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                        kwargs.jdata.default = f'sw-ctrl'
                        name                 = ezfunctions.variable_prompt(kwargs)
                        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.name              = name
                        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.policy            = name
                        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.switching_mode_fc = kwargs.results[indx].FcSwitchingMode
                #=====================================================================
                # Configure Fibre-Channel if FC Optics Found
                #=====================================================================
                domain_name = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.name
                port_names = [f'{domain_name}-{e}' for e in ['A', 'B']]
                if kwargs.use_shared_org == True: org = kwargs.shared_org
                else: org = kwargs.org
                indx = next((index for (index, d) in enumerate(kwargs.imm_dict.orgs[org].policies.port) if d['names'] == port_names), None)
                if indx == None:
                    idict_keys = list(kwargs.imm_dict.orgs[org].policies.keys())
                    if not 'port' in idict_keys: kwargs.imm_dict.orgs[org].policies.port = []
                    elif type(kwargs.imm_dict.orgs[org].policies.port) != list:
                        kwargs.imm_dict.orgs[org].policies.port = []
                    kwargs.imm_dict.orgs[org].policies.port.append(DotMap(names = port_names))
                    indx = next((index for (index, d) in enumerate(kwargs.imm_dict.orgs[org].policies.port) if d['names'] == port_names), None)
                pvars = deepcopy(kwargs.imm_dict.orgs[org].policies.port[indx])
                pkeys = list(pvars.keys())
                if len(kwargs.fc_ports) > 0:
                    if not 'port_modes' in pkeys:
                        kwargs.jdata   = deepcopy(kwargs.ezwizard.port.properties.convert_unified)
                        kwargs.fc_mode = ezfunctions.variable_prompt(kwargs)
                    else: kwargs.fc_mode = True
                    if kwargs.fc_mode == True:
                        if kwargs.sw_policy == 'Create New':
                            #=====================================================================
                            # FC Switching Mode for Switch Control Policy
                            #=====================================================================
                            kwargs.jdata             = deepcopy(kwargs.ezdata.switch_control.allOf[1].properties.switching_mode_fc)
                            kwargs.jdata.description = 'Switch Control Policy FC Switching Mode\n\n' + kwargs.jdata.description
                            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.switching_mode_fc = ezfunctions.variable_prompt(kwargs)
                        #=====================================================================
                        # VSAN Policy
                        #=====================================================================
                        if type(kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.vsan_list) != list:
                            kwargs = policies('vsan').vsan(kwargs)
                        #=====================================================================
                        # Port Mode Conversion
                        #=====================================================================
                        if not 'port_modes' in pkeys:
                            pvars, kwargs = policies('port_modes').port_modes(pvars, kwargs)
                            kwargs.imm_dict.orgs[org].policies.port[indx].port_modes = pvars.port_modes
                            policies.create_yaml_files(kwargs)
                        for x in range(pvars.port_modes[0].port_list[0], pvars.port_modes[0].port_list[1]+1):
                            kwargs.available_ports.remove(x)
                            if re.search('UCS-FI-6536|UCSX-S9108-100G', kwargs.domain.model):
                                for b in range(1,5): kwargs.fc_converted_ports.append(f'fc1/{x}/{b}')
                            else: kwargs.fc_converted_ports.append(f'fc1/{x}')
                        #=====================================================================
                        # Loop Thru Fibre-Channel Uplink Types
                        #=====================================================================
                        kwargs.jdata = deepcopy(kwargs.ezwizard.port.properties.uplink_types_fcp)
                        if kwargs.imm_dict.orgs[org].wizard.setup.domain.switch_control.switching_mode_fc == 'end-host':
                            kwargs.jdata.enum.remove('port_role_fc_storage'); kwargs.jdata.pop('multi_select')
                        uplink_types = ezfunctions.variable_prompt(kwargs)
                        if type(uplink_types) == str: uplink_types = [uplink_types]
                        for e in uplink_types:
                            if not e in pkeys:
                                pvars, kwargs = eval(f'policies(f"port.{e}").{e}(pvars, kwargs)')
                                kwargs.imm_dict.orgs[org].policies.port[indx][e] = pvars[e]
                                policies.create_yaml_files(kwargs)
                #=====================================================================
                # Configure Breakout Ports
                #=====================================================================
                kwargs.available_ports = [f'eth1/{e}' for e in kwargs.available_ports]
                kwargs.jdata = deepcopy(kwargs.ezwizard.port.properties.breakout_ports)
                eth_breakout = ezfunctions.variable_prompt(kwargs)
                if eth_breakout == True:
                    if not 'breakout_ports' in pkeys:
                        pvars, kwargs = policies('port_breakouts').port_eth_breakouts(kwargs)
                        kwargs.imm_dict.orgs[org].policies.port[indx].breakout_ports = pvars.port_modes
                        policies.create_yaml_files(kwargs)
                #=====================================================================
                # Loop Thru Ethernet Uplink Types
                #=====================================================================
                kwargs.jdata = deepcopy(kwargs.ezwizard.port.properties.uplink_types_eth)
                uplink_types = ezfunctions.variable_prompt(kwargs)
                for e in uplink_types:
                    if not e in pkeys:
                        pvars, kwargs = eval(f'policies(f"port.{e}").{e}(pvars, kwargs)')
                        kwargs.imm_dict.orgs[org].policies.port[indx][e] = pvars[e]
                        policies.create_yaml_files(kwargs)
                #=====================================================================
                # Configure Server Ports
                #=====================================================================
                ddict = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain
                if ddict.model != 'UCSX-S9108-100G':
                    if not 'port_role_servers' in pkeys:
                        pvars, kwargs = policies('port.port_role_servers').port_role_servers(pvars, kwargs)
                        kwargs.imm_dict.orgs[org].policies.port[indx].port_role_servers = pvars['port_role_servers']
                        policies.create_yaml_files(kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                if kwargs.use_shared_org == True: policy_names = [f'{kwargs.shared_org}/{e}' for e in pvars.names]
                else: policy_names = pvars.names
                policy_accept = True
                #=====================================================================
                # Add Switch Control Policy to Dict if Required
                #=====================================================================
                kwargs = policies('switch_control').switch_control(kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policies'] = policy_names
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Fibre-Channel Uplink Port-Channels
    #=========================================================================
    def port_available_format(port_type, kwargs):
        pmap = kwargs[f'{port_type}_map']
        ports = []
        if port_type == 'eth': psource = kwargs.available_ports
        else: psource = kwargs.fc_converted_ports
        eth_map = kwargs['eth_map']
        pmap_keys = list(pmap.keys())
        for e in psource:
            if e in pmap_keys: ports.append(f'{pmap[e].interface}, Transceiver: {pmap[e].transceiver}')
            else:
                ename = e.replace('fc', 'eth'); fc_int = eth_map[ename].interface.replace('eth', 'fc')
                ports.append(f'{fc_int}, Transceiver: {eth_map[ename].transceiver}')
        return ports

    #=========================================================================
    # Function: Prompt User for Fibre-Channel Port Mode
    #=========================================================================
    def port_eth_breakouts(self, pvars, kwargs):
        if not pvars.port_modes: pvars.port_modes = []
        sub_accept = False
        while sub_accept == False:
            model = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.model
            if   model == 'UCS-FI-6454':  port_list = [f'eth1/{x}' for x in range(49,55)]
            elif model == 'UCS-FI-64108': port_list = [f'eth1/{x}' for x in range(97,109)]
            else: port_list = [f'eth1/{x}' for x in range(kwargs.available_ports[0],kwargs.available_ports[-1]+1)]
            kwargs.jdata         = deepcopy(kwargs.ezwizard.port.properties.breakout_port_list)
            ports                = ezfunctions.variable_prompt(kwargs)
            kwargs.jdata         = deepcopy(kwargs.ezdata[f'port.port_modes'].properties.custom_mode)
            kwargs.jdata.default = 'BreakoutEthernet25G'
            kwargs.jdata.enum    = [e for e in kwargs.jdata.enum if 'BreakoutEther' in e]
            breakout_speed       = ezfunctions.variable_prompt(kwargs)
            edict                = DotMap(custom_mode = breakout_speed, port_list = ports)
            #=====================================================================
            # Prompt User to Accept the Policy
            #=====================================================================
            accept = prompt_user('the Port Breakout Mode Port').to_accept('the Port Breakout Mode', edict, kwargs)
            if accept == True:
                ilength = len(kwargs.eth_ports)
                for e in port_list:
                    kwargs.available_ports.remove(e)
                    if   ilength > 90 and e < 10:  port_id = f'00{e}'
                    elif ilength > 90 and e < 100: port_id = f'0{e}'
                    elif ilength > 90 and e > 99:  port_id = f'{e}'
                    elif e < 10: port_id = f'0{e}'
                    else: port_id = e
                    indx = next((index for (index, d) in enumerate(kwargs.eth_ports) if d['port_id'] == e), None)
                    pmap = kwargs.eth_ports[indx]
                    for b in range(1,5):
                        kwargs.available_ports.append(f'eth1/{e}/{b}')
                        kwargs.eth_map[f'eth1/{e}/{b}'] = DotMap(interface = f'eth1/{port_id}/{b}', transceiver = pmap.transceiver)
                    pvars.port_modes.append(DotMap(custom_mode = edict.custom_mode, port_list = [e, e]))
                additional = prompt_user(self.type).to_configure_additional(False, kwargs)
                if additional == False: sub_accept = True
            else: ezfunctions.message_starting_over(self.type)
        kwargs.available_ports = sorted(kwargs.available_ports)
        kwargs.eth_map = DotMap(sorted(kwargs.eth_map.items(), key=lambda ele: ele[1].interface))
        # Return kwargs
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Appliance Port-Channels
    #=========================================================================
    def port_channel_appliances(self, pvars, kwargs):
        pvars, kwargs = policies(self.type).port_channel_ethernet_uplinks(pvars, kwargs)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Fibre-Channel Uplink Port-Channels
    #=========================================================================
    def port_channel_ethernet_uplinks(self, pvars, kwargs):
        port_policy        = (self.type).replace('port.', '')
        pvars[port_policy] = []
        sub_accept         = False
        while sub_accept == False:
            edict  = DotMap(interfaces = [])
            #=====================================================================
            # Prompt User for: admin_speed, interfaces, pc_ids, and vsan_ids
            #=====================================================================
            policy_title      = ezfunctions.mod_pol_description((port_policy.replace('_', ' ')).capitalize())
            kwargs.jdata      = deepcopy(kwargs.ezdata[self.type].properties.admin_speed)
            edict.admin_speed = ezfunctions.variable_prompt(kwargs)
            if port_policy == 'port_channel_appliances':
                kwargs.jdata   = deepcopy(kwargs.ezdata[self.type].properties.mode)
                edict.mode     = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata   = deepcopy(kwargs.ezdata[self.type].properties.priority)
                edict.priority = ezfunctions.variable_prompt(kwargs)
            kwargs.jdata             = deepcopy(kwargs.ezwizard.port.properties.port_channel_interfaces)
            kwargs.jdata.description = (kwargs.jdata.description).replace('REPLACE', policy_title)
            kwargs.jdata.enum        = policies.port_available_format('eth', kwargs)
            interfaces = ezfunctions.variable_prompt(kwargs)
            interfaces = [((re.search(r'((eth|fc)\d/[\d]{1,3}(/\d)?),', e).group(1).replace('/0', '/')).replace('/0', '/')) for e in interfaces]
            edict, pc_ids        = policies.port_channel_interfaces(edict, interfaces)
            kwargs.jdata         = deepcopy(kwargs.ezwizard.port.properties.port_channel_ids)
            kwargs.jdata.default = pc_ids
            edict.pc_ids         = (ezfunctions.variable_prompt(kwargs)).split(',')
            edict.pc_ids         = list(numpy.unique(numpy.array(edict.pc_ids)))
            edict.pc_ids         = [int(e) for e in edict.pc_ids]
            #=====================================================================
            # Prompt User for: Policies to Attach to the Port-Channel
            #=====================================================================
            kwargs.jdata             = deepcopy(kwargs.ezwizard.port.properties.port_channel_policies)
            kwargs.jdata.description = (kwargs.jdata.description).replace('REPLACE', policy_title)
            kwargs.jdata.title       = (kwargs.jdata.title).replace('REPLACE', policy_title)
            if   port_policy == 'port_channel_appliances':   kwargs.jdata.enum = ['link_aggregation']
            elif port_policy == 'port_channel_fcoe_uplinks': kwargs.jdata.enum = ['link_aggregation', 'link_control']
            port_policies = ezfunctions.variable_prompt(kwargs)
            if type(port_policies) == str: port_policies = [port_policies]
            if port_policy == 'port_channel_appliances': port_policies.extend(['ethernet_network_control', 'ethernet_network_group'])
            port_policies = sorted(port_policies)
            for e in port_policies:
                kwargs   = eval(f'policies(f"{e}").{e}(kwargs)')
                edict[f'{e}_policy'] = kwargs.policy_name
            edict = DotMap(sorted(edict.items()))
            #=====================================================================
            # Prompt User to Accept the Policy
            #=====================================================================
            accept = prompt_user(f'the {policy_title} Port').to_accept(f'the {policy_title}', edict, kwargs)
            if accept == True:
                for e in interfaces: kwargs.available_ports.remove(e)
                pvars[port_policy].append(edict)
                additional = prompt_user(port_policy).to_configure_additional(False, kwargs)
                if additional == False: sub_accept = True
            else: ezfunctions.message_starting_over(port_policy)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Fibre-Channel Uplink Port-Channels
    #=========================================================================
    def port_channel_fc_uplinks(self, pvars, kwargs):
        port_policy        = (self.type).replace('port.', '')
        pvars[port_policy] = []
        sub_accept         = False
        while sub_accept == False:
            edict  = DotMap(interfaces = [])
            #=====================================================================
            # Prompt User for: admin_speed, interfaces, pc_ids, and vsan_ids
            #=====================================================================
            kwargs.jdata         = deepcopy(kwargs.ezdata[self.type].properties.admin_speed)
            edict.admin_speed    = ezfunctions.variable_prompt(kwargs)
            kwargs.jdata         = deepcopy(kwargs.ezwizard.port.properties.port_channel_fc_interfaces)
            kwargs.jdata.enum    = policies.port_available_format('fc', kwargs)
            interfaces = ezfunctions.variable_prompt(kwargs)
            interfaces = [((re.search(r'((eth|fc)\d/[\d]{1,3}(/\d)?),', e).group(1).replace('/0', '/')).replace('/0', '/')) for e in interfaces]
            edict, pc_ids        = policies.port_channel_interfaces(edict, interfaces)
            kwargs.jdata         = deepcopy(kwargs.ezwizard.port.properties.port_channel_ids)
            kwargs.jdata.default = pc_ids
            edict.pc_ids         = (ezfunctions.variable_prompt(kwargs)).split(',')
            edict.pc_ids         = list(numpy.unique(numpy.array(edict.pc_ids)))
            edict.pc_ids         = [int(e) for e in edict.pc_ids]
            edict.vsan_ids = []
            for e in ['A', 'B']:
                kwargs.jdata      = deepcopy(kwargs.ezwizard.port.properties.vsan_id)
                kwargs.jdata.enum = [
                    str(d.vsan_id) for d in kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.vsan_list if d.fabric == e or d.fabric == 'shared']
                kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', e)
                kwargs.jdata.title       = kwargs.jdata.title.replace('REPLACE', e)
                if len(kwargs.jdata.enum) > 1:
                    edict.vsan_ids.append(int(ezfunctions.variable_prompt(kwargs)))
                else: edict.vsan_ids.append(kwargs.jdata.enum[0])
            edict.vsan_ids = list(numpy.unique(numpy.array(edict.vsan_ids)))
            edict.vsan_ids = [int(e) for e in edict.vsan_ids]
            edict = DotMap(sorted(edict.items()))
            #=====================================================================
            # Prompt User to Accept the Policy
            #=====================================================================
            accept = prompt_user(f'the FC Port-Channel Port').to_accept('the FC Port-Channel', edict, kwargs)
            if accept == True:
                for e in interfaces: kwargs.fc_converted_ports.remove(e)
                pvars[port_policy].append(edict)
                additional = prompt_user(port_policy).to_configure_additional(False, kwargs)
                if additional == False: sub_accept = True
            else: ezfunctions.message_starting_over(port_policy)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for FCOE Uplink Port-Channels
    #=========================================================================
    def port_channel_fcoe_uplinks(self, pvars, kwargs):
        pvars, kwargs = policies(self.type).port_channel_ethernet_uplinks(pvars, kwargs)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Port-Channel Interface Dictionary
    #=========================================================================
    def port_channel_interfaces(edict, interfaces):
        icount = 0
        for e in interfaces:
            x = e.split('/'); icount += 1
            x[0] = int((x[0].replace('fc', '')).replace('eth', ''))
            x[1] = int(x[1])
            if len(x) == 2:
                if icount == 1: pc_ids = f'{x[1]}'
                if x[0] == 1: edict.interfaces.append(DotMap(port_id = x[1]))
                else: edict.interfaces.append(DotMap(port_id = x[1], slot_id = x[0]))
            else:
                x[2] = int(x[2])
                if icount == 1: pc_ids = f'{x[1]}{x[2]}'
                if x[0] == 1: edict.interfaces.append(DotMap(breakout_port_id = x[2], port_id = x[1]))
                else: edict.interfaces.append(DotMap(breakout_port_id = x[2], port_id = x[1], slot_id = x[0]))
        return edict, pc_ids

    #=========================================================================
    # Function: Build Port Map for Ports
    #=========================================================================
    def port_map(port_type, kwargs):
        ilength = len(kwargs[f'{port_type}_ports'])
        for i in kwargs[f'{port_type}_ports']:
            intf = port_type
            if   ilength > 90 and i.port_id < 10:  port_id = f'00{i.port_id}'
            elif ilength > 90 and i.port_id < 100: port_id = f'0{i.port_id}'
            elif ilength > 90 and i.port_id > 99:  port_id = f'{i.port_id}'
            elif i.port_id < 10: port_id = f'0{i.port_id}'
            else: port_id = i.port_id
            if i.breakout_port_id == 0:
                kwargs[f'{port_type}_map'][f'{intf}{i.slot_id}/{i.port_id}'] = DotMap(interface = f'{intf}{i.slot_id}/{port_id}', transceiver = i.transceiver)
            else: kwargs[f'{port_type}_map'][f'{intf}{i.slot_id}/{i.breakout_port_id}/{i.port_id}'] = DotMap(
                    interface = f'{intf}{i.slot_id}/{i.breakout_port_id}/{port_id}', transceiver = i.transceiver)
        kwargs[f'{port_type}_map'] = DotMap(sorted(kwargs[f'{port_type}_map'].items(), key=lambda ele: ele[1].interface))
        return kwargs

    #=========================================================================
    # Function: Prompt User for Fibre-Channel Port Mode
    #=========================================================================
    def port_modes(self, pvars, kwargs):
        sub_accept = False
        while sub_accept == False:
            pcolor.Yellow(f'\n{"-"*51}\n\nPorts with FC Optics installed.')
            for e in kwargs.fcp_ports: pcolor.Yellow(f'  * slot_id: {e.slot_id}, port_id: {e.port_id}, transceiver: {e.transceiver}')
            model = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.model
            model = (((model.replace('UCSX-S', '').replace('-100G', '')).replace('64108', '6400')).replace('6454', '6400')).replace('UCS-FI-', '')
            kwargs.jdata = deepcopy(kwargs.ezwizard.port.properties[f'port_mode_{model}'])
            fc_ports = ezfunctions.variable_prompt(kwargs)
            p1, p2 = fc_ports.split('-'); p1 = int(p1); p2 = int(p2)
            if re.search('UCS-FI-6536|UCSX-S9108-100G', kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.model):
                kwargs.jdata         = deepcopy(kwargs.ezdata[f'port.port_modes'].properties.custom_mode)
                kwargs.jdata.default = 'BreakoutFibreChannel32G'
                kwargs.jdata.enum    = [e for e in kwargs.jdata.enum if 'BreakoutFibre' in e]
                breakout_speed       = ezfunctions.variable_prompt(kwargs)
                edict                = DotMap(custom_mode = breakout_speed, port_list = [p1,p2])
            else: edict = DotMap(custom_mode = 'FibreChannel',port_list = [p1,p2])
            #=====================================================================
            # Prompt User to Accept the Policy
            #=====================================================================
            accept = prompt_user('the Port Mode Port').to_accept('Port Mode', edict, kwargs)
            if accept == True:
                pvars.port_modes = [edict]
                sub_accept = True
            else: ezfunctions.message_starting_over(self.type)
        # Return kwargs
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Appliance Ports
    #=========================================================================
    def port_role_appliances(self, pvars, kwargs):
        pvars, kwargs = policies(self.type).port_role_ethernet_uplinks(pvars, kwargs)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Ethernet Uplink(s)
    #=========================================================================
    def port_role_ethernet_uplinks(self, pvars, kwargs):
        port_policy        = (self.type).replace('port.', '')
        pvars[port_policy] = []
        sub_accept         = False
        while sub_accept == False:
            edict  = DotMap(interfaces = [])
            #=====================================================================
            # Prompt User for: admin_speed, interfaces, pc_ids, and vsan_ids
            #=====================================================================
            policy_title      = ezfunctions.mod_pol_description((port_policy.replace('_', ' ')).capitalize())
            kwargs.jdata      = deepcopy(kwargs.ezdata[self.type].properties.admin_speed)
            edict.admin_speed = ezfunctions.variable_prompt(kwargs)
            kwargs.jdata      = deepcopy(kwargs.ezdata[self.type].properties.fec)
            edict.fec         = ezfunctions.variable_prompt(kwargs)
            if port_policy == 'port_role_appliances':
                kwargs.jdata   = deepcopy(kwargs.ezdata[self.type].properties.mode)
                edict.mode     = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata   = deepcopy(kwargs.ezdata[self.type].properties.priority)
                edict.priority = ezfunctions.variable_prompt(kwargs)
            kwargs.jdata             = deepcopy(kwargs.ezwizard.port.properties.fc_uplink_interfaces)
            kwargs.jdata.description = (kwargs.jdata.description).replace('REPLACE', policy_title)
            kwargs.jdata.enum        = policies.port_available_format('eth', kwargs)
            interfaces       = ezfunctions.variable_prompt(kwargs)
            edict.interfaces = [((re.search(r'((eth|fc)\d/[\d]{1,3}(/\d)?),', e).group(1).replace('/0', '/')).replace('/0', '/')) for e in interfaces]
            intf_map         = policies.port_role_interfaces(edict.interfaces)
            #=====================================================================
            # Prompt User for: Policies to Attach to the Port(s)
            #=====================================================================
            port_policies = []
            if not port_policy == 'port_role_appliances':
                kwargs.jdata             = deepcopy(kwargs.ezwizard.port.properties.port_role_policies)
                kwargs.jdata.description = (kwargs.jdata.description).replace('REPLACE', policy_title)
                kwargs.jdata.title       = (kwargs.jdata.title).replace('REPLACE', policy_title)
                if port_policy == 'port_role_fcoe_uplinks': kwargs.jdata.enum = ['link_control']
                port_policies = ezfunctions.variable_prompt(kwargs)
            if type(port_policies) == str: port_policies = [port_policies]
            if port_policy == 'port_role_appliances': port_policies.extend(['ethernet_network_control', 'ethernet_network_group'])
            port_policies = sorted(port_policies)
            for e in port_policies:
                kwargs   = eval(f'policies(f"{e}").{e}(kwargs)')
                edict[e] = kwargs.policy_name
            #=====================================================================
            # Prompt User to Accept the Policy
            #=====================================================================
            accept = prompt_user(f'the {policy_title} Port').to_accept(f'the {policy_title}', edict, kwargs)
            if accept == True:
                for e in edict.interfaces: kwargs.available_ports.remove(e)
                edict.pop('interfaces')
                for e in list(intf_map.keys()):
                    for x in list(intf_map[e].aggregates.keys()):
                        port_list = ezfunctions.vlan_list_format(intf_map[e].aggregates[x])
                        edict.breakout_port_id = x; edict.port_list = port_list; edict.slot_id = e
                        if e == 1: edict.pop('slot_id')
                        if x == 0: edict.pop('breakout_port_id')
                        edict = DotMap(sorted(edict.items()))
                        pvars[port_policy].append(edict)
                additional = prompt_user(port_policy).to_configure_additional(False, kwargs)
                if additional == False: sub_accept = True
            else: ezfunctions.message_starting_over(port_policy)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Fibre-Channel Storage Ports
    #=========================================================================
    def port_role_fc_storage(self, pvars, kwargs):
        pvars, kwargs = policies(self.type).port_role_fc_uplinks(pvars, kwargs)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Fibre-Channel Uplink Ports
    #=========================================================================
    def port_role_fc_uplinks(self, pvars, kwargs):
        port_policy        = (self.type).replace('port.', '')
        pvars[port_policy] = []
        sub_accept         = False
        while sub_accept == False:
            edict  = DotMap(interfaces = [])
            #=====================================================================
            # Prompt User for: admin_speed, interfaces, pc_ids, and vsan_ids
            #=====================================================================
            kwargs.jdata      = deepcopy(kwargs.ezdata[self.type].properties.admin_speed)
            edict.admin_speed = ezfunctions.variable_prompt(kwargs)
            kwargs.jdata      = deepcopy(kwargs.ezwizard.port.properties.fc_uplink_interfaces)
            kwargs.jdata.enum = policies.port_available_format('fc', kwargs)
            interfaces        = ezfunctions.variable_prompt(kwargs)
            edict.interfaces  = [((re.search(r'((eth|fc)\d/[\d]{1,3}(/\d)?),', e).group(1).replace('/0', '/')).replace('/0', '/')) for e in interfaces]
            intf_map          = policies.port_role_interfaces(edict.interfaces)
            edict.vsan_ids = []
            for e in ['A', 'B']:
                kwargs.jdata      = deepcopy(kwargs.ezwizard.port.properties.vsan_id)
                kwargs.jdata.enum = [
                    str(d.vsan_id) for d in kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.vsan_list if d.fabric == e or d.fabric == 'shared']
                kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', e)
                kwargs.jdata.title       = kwargs.jdata.title.replace('REPLACE', e)
                if len(kwargs.jdata.enum) > 1:
                    edict.vsan_ids.append(int(ezfunctions.variable_prompt(kwargs)))
                else: edict.vsan_ids.append(kwargs.jdata.enum[0])
            edict.vsan_ids = list(numpy.unique(numpy.array(edict.vsan_ids)))
            edict.vsan_ids = [int(e) for e in edict.vsan_ids]
            edict = DotMap(sorted(edict.items()))
            #=====================================================================
            # Prompt User to Accept the Policy
            #=====================================================================
            policy_title = ezfunctions.mod_pol_description((port_policy.replace('_', ' ')).capitalize())
            accept = prompt_user(f'the {policy_title} Port').to_accept(f'the {policy_title}', edict, kwargs)
            if accept == True:
                for e in edict.interfaces: kwargs.fc_converted_ports.remove(e)
                for e in list(intf_map.keys()):
                    for x in list(intf_map[e].aggregates.keys()):
                        port_list = ezfunctions.vlan_list_format(intf_map[e].aggregates[x])
                        pdict     = DotMap(admin_speed = edict.admin_speed, breakout_port_id = x, port_list = port_list, slot_id = e, vsan_ids = edict.vsan_ids)
                        if e == 1: pdict.pop('slot_id')
                        if x == 0: pdict.pop('breakout_port_id')
                        pvars[port_policy].append(pdict)
                additional = prompt_user(port_policy).to_configure_additional(False, kwargs)
                if additional == False: sub_accept = True
            else: ezfunctions.message_starting_over(port_policy)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for FCOE Uplink Ports
    #=========================================================================
    def port_role_fcoe_uplinks(self, pvars, kwargs):
        pvars, kwargs = policies(self.type).port_role_ethernet_uplinks(pvars, kwargs)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Fibre-Channel Uplink Ports
    #=========================================================================
    def port_role_interfaces(interfaces):
        intf_map = DotMap()
        for e in interfaces:
            x = e.split('/')
            x[0] = int((x[0].replace('fc', '')).replace('eth', ''))
            ikeys = list(intf_map[x[0]].aggregates.keys())
            if len(x) == 3:
                if not x[1] in ikeys: intf_map[x[0]].aggregates[x[1]] = []
                intf_map[x[0]].aggregates[x[1]].append(x[2])
            else:
                if not 0 in ikeys: intf_map[x[0]].aggregates[0] = []
                intf_map[x[0]].aggregates[0].append(x[1])
        return intf_map

    #=========================================================================
    # Function: Prompt User for Ethernet Uplink(s)
    #=========================================================================
    def port_role_servers(self, pvars, kwargs):
        port_policy        = (self.type).replace('port.', '')
        pvars[port_policy] = []
        sub_accept         = False
        while sub_accept == False:
            edict  = DotMap()
            #=====================================================================
            # Prompt User for: admin_speed, interfaces, pc_ids, and vsan_ids
            #=====================================================================
            policy_title = ezfunctions.mod_pol_description((port_policy.replace('_', ' ')).capitalize())
            kwargs.jdata = deepcopy(kwargs.ezwizard.port.properties.connected_devices)
            if kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.model == 'UCSX-S9108-100G': kwargs.jdata.optional = True
            connected_devices = ezfunctions.variable_prompt(kwargs)
            for device_type in connected_devices:
                if not edict.get(device_type): edict[device_type].interfaces = []
                pcolor.Yellow(f'\n\n  ** Optional Attributes for {policy_title} - {device_type}.  **')
                edict, kwargs            = policies(self.type).optional_attributes(edict, kwargs)
                kwargs.jdata             = deepcopy(kwargs.ezwizard.port.properties.connected_count)
                kwargs.jdata.description = (kwargs.jdata.description).replace('REPLACE', device_type)
                kwargs.jdata.title       = (kwargs.jdata.title).replace('REPLACE', device_type)
                device_count             = ezfunctions.variable_prompt(kwargs)
                edict[device_type].count = device_count
                for i in range(1, device_count + 1):
                    kwargs.jdata             = deepcopy(kwargs.ezwizard.port.properties.server_interfaces)
                    kwargs.jdata.description = ((kwargs.jdata.description).replace('REPLACE', device_type)).replace('IDENTITY', str(i))
                    kwargs.jdata.title       = ((kwargs.jdata.title).replace('REPLACE', device_type)).replace('IDENTITY', str(i))
                    kwargs.jdata.enum        = policies.port_available_format('eth', kwargs)
                    interfaces = ezfunctions.variable_prompt(kwargs)
                    interfaces = [((re.search(r'((eth|fc)\d/[\d]{1,3}(/\d)?),', e).group(1).replace('/0', '/')).replace('/0', '/')) for e in interfaces]
                    edict[device_type][i].interface_map = policies.port_role_interfaces(interfaces)
                    edict[device_type].interfaces.extend(interfaces)
            sports = DotMap()
            sports.server_ports = []
            ekeys = list(edict.keys())
            for e in ['Chassis', 'RackServer']:
                if e in ekeys:
                    for x in range(0, edict[e].count + 1):
                        for s in list(edict[e][x].interface_map.keys()):
                            for agg in list(edict[e][x].interface_map[s].aggregates.keys()):
                                sdict = DotMap()
                                for d in kwargs.ezwizard[self.type].properties.optional_attributes.enum:
                                    if d in ekeys: sdict[d] = edict[d]
                                port_list = [int(i) for i in edict[e][x].interface_map[s].aggregates[agg]]
                                port_list = ezfunctions.vlan_list_format(port_list)
                                sdict.connected_device_type = e; sdict.breakout_port_id = agg; sdict.device_number = x
                                sdict.port_list = port_list; sdict.slot_id = s
                                if s == 1:   sdict.pop('slot_id')
                                if agg == 0: sdict.pop('breakout_port_id')
                                sdict = DotMap(sorted(sdict.items()))
                                sports.server_ports.append(sdict)
            #=====================================================================
            # Prompt User to Accept the Policy
            #=====================================================================
            accept = prompt_user(f'the {policy_title} Port').to_accept(f'the {policy_title}', sports, kwargs)
            if accept == True:
                ekeys = list(edict.keys())
                for e in ['Chassis', 'RackServer']:
                    if e in ekeys:
                        for d in edict[e].interfaces: kwargs.available_ports.remove(d)
                        edict[e].pop('interfaces')
                pvars[port_policy] = sports.server_ports
                sub_accept = True
            else: ezfunctions.message_starting_over(port_policy)
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for Power Policy Settings
    #=========================================================================
    def power(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                if kwargs.profile_type == 'chassis': kwargs.jdata.default = 'chassis'
                else: kwargs.jdata.default = 'server'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.power_redundancy)
                pvars.power_redundancy = ezfunctions.variable_prompt(kwargs)
                if kwargs.profile_type == 'server':
                    kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.power_restore)
                    pvars.power_restore = ezfunctions.variable_prompt(kwargs)
                kwargs = policies('power').optional_attributes(kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        if kwargs.profile_type == 'chassis':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.chassis[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'server':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server[f'{self.type}_policy'] = kwargs.policy_name
        else: kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template[f'{self.type}_policy'] = kwargs.policy_name
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for SNMP Policy Settings
    #=========================================================================
    def snmp(self, kwargs):
        optional_answer = policies(self.type).optional(kwargs)
        if optional_answer == True: kwargs.policy_name = policies(self.type).policy_select(kwargs)
        else: kwargs.policy_name = 'skip_policy'
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'snmp'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                for e in ['system_contact', 'system_location', 'snmp_port']:
                    kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                    pvars[e] = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezwizard.snmp.properties.snmp_version)
                snmp_version = ezfunctions.variable_prompt(kwargs)
                if snmp_version == 'V2':
                    pass
                pvars.remote_logging = []
                pcolor.Yellow(f'\n\n ** You Can Configure Up to two Remote Syslog Servers **')
                #=====================================================================
                # Function: Remote Syslog Servers
                #=====================================================================
                sub_count = 0
                sub_loop = True
                while sub_loop == True:
                    sub_confirm = False
                    while sub_confirm == False:
                        accept = False
                        if sub_count == 2: sub_confirm = True; sub_loop = False; break
                        edict = DotMap()
                        for e in ['hostname', 'minimum_severity', 'port', 'protocol']:
                            kwargs.jdata = deepcopy(kwargs.ezdata['syslog.remote_logging'].properties[e])
                            if e == 'hostname' and sub_count >= 1: kwargs.jdata.optional = True
                            edict[e] = ezfunctions.variable_prompt(kwargs)
                            if edict[e] == '': sub_confirm = True; sub_loop = False; break
                        if sub_confirm == False:
                            accept = prompt_user(f'Remote Syslog server settings for the Syslog').to_accept('Remote Syslog', edict, kwargs)
                        if accept == True:
                            pvars.remote_logging.append(edict)
                            sub_count += 1
                            sub_confirm = True
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        if kwargs.profile_type == 'chassis':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.chassis[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'domain':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'server':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server[f'{self.type}_policy'] = kwargs.policy_name
        else: kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template[f'{self.type}_policy'] = kwargs.policy_name
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Switch Control Policy Settings
    #=========================================================================
    def switch_control(self, kwargs):
        #=====================================================================
        # Switch Control Policy
        #=====================================================================
        if kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.policy == 'Create New':
            sw_ctrl = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control
            pvars   = DotMap(name = sw_ctrl.name, switching_mode_ethernet = 'end-host', switching_mode_fc = sw_ctrl.switching_mode_fc,
                             vlan_port_count_optimization = True)
            if kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.reserved_vlan != 3915:
                pvars.reserved_vlan_start_id = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.reserved_vlan
            pvars             = DotMap(sorted(pvars.items()))
            kwargs.class_path = f'policies,{self.type}'
            kwargs            = ezfunctions.ez_append(pvars, kwargs)
            if kwargs.use_shared_org == True:  policy_name = f'{kwargs.shared_org}/{pvars.name}'
            else: policy_name = pvars.name
            #=====================================================================
            # Add Policy to Dictionaries, Update YAML and Return kwargs
            #=====================================================================
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policy'] = policy_name
            policies.create_yaml_files(kwargs)
        else:
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policy'
                                                                 ] = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.policy
            policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for System QoS Policy Settings
    #=========================================================================
    def system_qos(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'system-qos'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.jumbo_mtu)
                kwargs.jdata.description = 'Do you have Jumbo MTU Configured in your Network Environment?'
                pvars.jumbo_mtu = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.configure_recommended_classes)
                kwargs.jdata.description = 'Do you want to enable the Bronze, Gold, Platinum, and Silver QoS Classes/Priorities for queueing in the environment?'
                kwargs.jdata.title       = 'QoS Classes'
                qos_classes = ezfunctions.variable_prompt(kwargs)
                if qos_classes == True: pvars.configure_recommended_classes = True
                else: pvars.configure_default_classes = True
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policy'] = kwargs.policy_name
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Syslog Policy Settings
    #=========================================================================
    def syslog(self, kwargs):
        optional_answer = policies(self.type).optional(kwargs)
        if optional_answer == True: kwargs.policy_name = policies(self.type).policy_select(kwargs)
        else: kwargs.policy_name = 'skip_policy'
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'syslog'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezdata['syslog.local_logging'].properties.minimum_severity)
                pvars.local_logging.minimum_severity = ezfunctions.variable_prompt(kwargs)
                pvars.remote_logging = []
                pcolor.Yellow(f'\n\n ** You Can Configure Up to two Remote Syslog Servers **')
                #=====================================================================
                # Function: Remote Syslog Servers
                #=====================================================================
                sub_count = 0
                sub_loop = True
                while sub_loop == True:
                    sub_confirm = False
                    while sub_confirm == False:
                        accept = False
                        if sub_count == 2: sub_confirm = True; sub_loop = False; break
                        edict = DotMap()
                        for e in ['hostname', 'minimum_severity', 'port', 'protocol']:
                            kwargs.jdata = deepcopy(kwargs.ezdata['syslog.remote_logging'].properties[e])
                            if e == 'hostname' and sub_count >= 1: kwargs.jdata.optional = True
                            edict[e] = ezfunctions.variable_prompt(kwargs)
                            if edict[e] == '': sub_confirm = True; sub_loop = False; break
                        if sub_confirm == False:
                            accept = prompt_user(f'Remote Syslog server settings for the Syslog').to_accept('Remote Syslog', edict, kwargs)
                        if accept == True:
                            pvars.remote_logging.append(edict)
                            sub_count += 1
                            sub_confirm = True
                        elif sub_confirm == True and sub_loop == False: pass
                        else: ezfunctions.message_starting_over('remote_logging')
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        if kwargs.profile_type == 'chassis':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.chassis[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'domain':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'server':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server[f'{self.type}_policy'] = kwargs.policy_name
        else: kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template[f'{self.type}_policy'] = kwargs.policy_name
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Thermal Policy Settings
    #=========================================================================
    def thermal(self, kwargs):
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            policy_accept = False
            while policy_accept == False:
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'chassis'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties.fan_control_mode)
                pvars.fan_control_mode = ezfunctions.variable_prompt(kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        if kwargs.profile_type == 'chassis':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.chassis[f'{self.type}_policy'] = kwargs.policy_name
        elif kwargs.profile_type == 'server':
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.server[f'{self.type}_policy'] = kwargs.policy_name
        else: kwargs.imm_dict.orgs[kwargs.org].wizard.setup.template[f'{self.type}_policy'] = kwargs.policy_name
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for VLAN Policy Settings
    #=========================================================================
    def vlan(self, kwargs):
        #=====================================================================
        # Function: Inner Loop for Multicast Policy
        #=====================================================================
        def multicast(kwargs):
            inner_accept = False
            while inner_accept == False:
                pvars = DotMap()
                pcolor.Yellow('\n\n  * Multicast Policy Settings.  *')
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'mcast'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                kwargs = policies('multicast').optional_attributes(kwargs)
                inner_accept, kwargs = policies('multicast').add_to_imm_dict(pvars, kwargs)
            if kwargs.use_shared_org == True:  kwargs.multicast_policy = f'{kwargs.shared_org}/{pvars.name}'
            else: kwargs.multicast_policy = pvars.name
            return kwargs
        #=====================================================================
        # Function: VLAN Policy Loop
        #=====================================================================
        kwargs.reserved_vlan = 3915
        kwargs.policy_name = policies(self.type).policy_select(kwargs)
        if kwargs.policy_name == 'Create New':
            policies(self.type).announcement(kwargs)
            pcolor.Yellow('\n\n  * A Multicast Policy is required for the VLAN Policy.')
            mcast_name = policies('multicast').policy_select(kwargs)
            if mcast_name == 'Create New': kwargs = multicast(kwargs)
            else: kwargs.multicast_policy = mcast_name
            policy_accept = False
            while policy_accept == False:
                pcolor.Yellow('\n\n  * Now Starting the VLAN Policy Settings.  *')
                pvars = DotMap()
                kwargs.jdata = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                kwargs.jdata.default = 'vlans'
                pvars.name   = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata = deepcopy(kwargs.ezdata['vlan.vlans'].properties.auto_allow_on_uplinks)
                kwargs.jdata.description = kwargs.jdata.description.replace('Default is `false`.  ', '')
                kwargs.jdata.default     = True
                kwargs.auto_allow        = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata             = deepcopy(kwargs.ezwizard.vlan.properties.native_vlan)
                kwargs.native_vlan       = int(ezfunctions.variable_prompt(kwargs))
                pvars.vlans              = []
                pcolor.Cyan('\n  We will now start to configure the VLANs.  You can configure one VLAN at a time or as VLAN ranges.')
                pcolor.Cyan('  When Finished with the VLANs that you want to configure press enter on the name field to stop the loop.')
                input('\n Press Enter to Continue: ')
                if not kwargs.native_vlan == 1:
                    kwargs.jdata = deepcopy(kwargs.ezdata['vlan.vlans'].allOf[1].properties.name)
                    kwargs.jdata.description = 'Name for the Native VLAN?'
                    name = ezfunctions.variable_prompt(kwargs)
                    pvars.vlans.append(DotMap(
                        auto_allow_on_uplinks = True, multicast_policy = kwargs.multicast_policy, name = name,
                        native_vlan = True, vlan_list = str(kwargs.native_vlan)))
                #=====================================================================
                # VLAN Policy - VLANs Function
                #=====================================================================
                pvars, kwargs = policies('vlan.vlans').vlans(pvars, kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                policy_accept, kwargs = policies(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policies'] = [kwargs.policy_name]
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.reserved_vlan = kwargs.reserved_vlan
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Get List of VLANs from VLAN Policy
    #=========================================================================
    def vlan_ranges(vlan_policy, kwargs):
        #=====================================================================
        # Get VLAN Policy Attributes
        #=====================================================================
        vlans = []
        if '/' in vlan_policy: org_name, vlan_policy = vlan_policy.split('/')
        else: org_name = kwargs.org
        indx = next((index for (index, d) in enumerate(kwargs.imm_dict.orgs[org_name].policies.vlan) if d['name'] == vlan_policy), None)
        if indx == None:
            names             = [f'{org_name}/{vlan_policy}']
            kwargs            = isight.api_get(False, names, 'vlan', kwargs)
            kwargs.api_filter = f"EthNetworkPolicy.Moid eq '{kwargs.isight[org_name].policies.vlan[vlan_policy]}'"
            kwargs.uri        = deepcopy(kwargs.ezdata['vlan.vlans'].intersight_uri)
            kwargs            = isight.api('vlan.vlans').calls(kwargs)
            for e in kwargs.results: vlans.append(e.VlanId)
        else:
            for e in kwargs.imm_dict.orgs[org_name].policies.vlan[indx].vlans: vlans.extend(ezfunctions.vlan_list_full(e.vlan_list))
        kwargs.vlans = sorted(vlans)
        kwargs.vlan_range = ezfunctions.vlan_list_format(vlans)
        return kwargs

    #=========================================================================
    # Function: Prompt User for VLANs to attach to VLAN Policy Settings
    #=========================================================================
    def vlans(self, pvars, kwargs):
        #=====================================================================
        # Function: VLAN Policy VLANs Loop
        #=====================================================================
        vlan_count = 0
        vlans_loop = True
        while vlans_loop == True:
            vlan_confirm = False
            while vlan_confirm == False:
                reserved_vlans = []
                for x in range(kwargs.reserved_vlan, kwargs.reserved_vlan+129): reserved_vlans.append(x)
                reserved_list = ezfunctions.vlan_list_format(reserved_vlans)
                kwargs.jdata = deepcopy(kwargs.ezdata['vlan.vlans'].properties.name)
                kwargs.jdata.description = 'Enter a Name/Prefix for the VLAN or VLAN Range.'
                if vlan_count >= 1: kwargs.jdata.optional = True
                name = ezfunctions.variable_prompt(kwargs)
                if name == '': vlan_confirm = True; vlans_loop = False; break
                kwargs.jdata = deepcopy(kwargs.ezdata['vlan.vlans'].properties.vlan_list)
                vlans = ezfunctions.variable_prompt(kwargs)
                vlan_full = ezfunctions.vlan_list_full(vlans)
                overlap_check = False
                skip_prompt   = False
                valid_vlans = validating.vlan_list(vlan_full)
                if valid_vlans == False: skip_prompt = True; break
                while overlap_check == False:
                    overlap = False
                    for e in vlan_full:
                        if e in reserved_vlans:
                            pcolor.Yellow(f'\n\n!!! Warning !!!.  Overlapping VLAN `{e}` with the System Reserved VLAN Ids: `{reserved_list}`.\n\n')
                            kwargs.jdata = deepcopy(kwargs.ezwizard.setup.properties.discovery)
                            kwargs.jdata.description = 'Do you want to change the Reserved VLAN Range?'
                            kwargs.jdata.title = 'Reserved VLAN Range'
                            answer = ezfunctions.variable_prompt(kwargs)
                            if answer == True:
                                kwargs.jdata = deepcopy(kwargs.ezdata.switch_control.allOf[1].properties.reserved_vlan_start_id)
                                kwargs.reserved_vlan = int(ezfunctions.variable_prompt(kwargs))
                                overlap = True
                            else: skip_prompt = True; overlap_check = True; break
                    if overlap == False: overlap_check = True
                if skip_prompt == True: accept = False
                elif kwargs.reserved_vlan == 3915:
                    accept = prompt_user('vlans for the VLAN').to_accept('VLANs', DotMap(name = name, vlan_list = vlans), kwargs)
                else: accept = prompt_user('vlans for the VLAN').to_accept(
                    'VLANs', DotMap(reserved_vlan_start_id = kwargs.reserved_vlan, name = name, vlan_list = vlans), kwargs)
                if accept == True:
                    if kwargs.native_vlan in vlan_full: vlan_full.remove(kwargs.native_vlan)
                    if 1 in vlan_full: vlan_full.remove(1)
                    vlan_list = ezfunctions.vlan_list_format(vlan_full)
                    if kwargs.auto_allow == True:
                        pvars.vlans.append(DotMap(
                            auto_allow_on_uplinks = True, multicast_policy=kwargs.multicast_policy, name = name, vlan_list = vlan_list))
                    else: pvars.vlans.append(DotMap(multicast_policy=kwargs.multicast_policy, name = name, vlan_list = vlan_list))
                    vlan_count += 1
                    vlan_confirm = True
                else: ezfunctions.message_starting_over('vlans')
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for VSAN Policy Settings
    #=========================================================================
    def vsan(self, kwargs):
        #=====================================================================
        # Get VLAN Policy Attributes
        #=====================================================================
        vlan_policy = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.vlan_policies[0]
        kwargs      = policies.vlan_ranges(vlan_policy, kwargs)
        #=====================================================================
        # Begin VSAN Policy Loop
        #=====================================================================
        pcolor.Yellow('\n\n  ** Configuring VSAN Policy for Port Policy Consumption **')
        policies(self.type).announcement(kwargs)
        args = DotMap()
        lcount = 0
        for e in ['A', 'B']: args[f'fabric_{e.lower()}'].name == 'Create New'
        for e in ['A', 'B']:
            pcolor.Yellow(f'\n\n ** Fabric {e} VSAN Policy **')
            if lcount == 1: kwargs.ignore_create_new = True
            args[f'fabric_{e.lower()}'].name = policies(self.type).policy_select(kwargs)
            if args[f'fabric_{e.lower()}'].name == 'Create New': break
            lcount += 1
        kwargs.ignore_create_new = False
        if args.fabric_a.name != 'Create New':
            names = [args[f'fabric_{e.lower()}'].name for e in ['A', 'B'] if args[f'fabric_{e.lower()}'].name != 'Create New']
            parent_moids = DotMap()
            for e in names:
                if not '/' in e: e = f'{kwargs.org}/{e}'
                parent_moids[kwargs.isight[e.split('/')[0]].policies.vsan[e.split('/')[1]]] = e
            vsan_list     = []
            vsan_policies = [args[f'fabric_{e.lower()}'].name for e in ['A', 'B'] if args[f'fabric_{e.lower()}'].name != 'Create New']
            kwargs.method = 'get'
            kwargs.names  = list(parent_moids.keys())
            kwargs.parent = 'FcNetworkPolicy'
            kwargs.uri    = kwargs.ezdata['vsan.vsans'].intersight_uri
            kwargs        = isight.api('parent_moids').calls(kwargs)
            for e in kwargs.results:
                parent = parent_moids[e.FcNetworkPolicy.Moid].replace(f'{kwargs.org}/', '')
                if   parent == args.fabric_a.name: fabric = 'A'
                elif parent == args.fabric_b.name: fabric = 'B'
                else: fabric = 'shared'
                vsan_list.append(DotMap(
                    fcoe_vlan_id = e.FcoeVlan, name = e.Name, fabric = fabric, vsan_id = e.VsanId, vsan_policy = parent, vsan_scope = e.VsanScope))
            vsan_list = sorted(vsan_list, key=lambda ele: ele.name)
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.vsan_list     = vsan_list
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.vsan_policies = vsan_policies
            policies.create_yaml_files(kwargs)
        elif args.fabric_a.name == 'Create New':
            #=====================================================================
            # VSAN Policy - VSANs Function
            #=====================================================================
            args, kwargs = policies('vsan.vsans').vsans(args, kwargs)
            #=====================================================================
            # Determine if VSAN Policy is Unique per Fabric
            #=====================================================================
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.vsan_list = args.vsans
            kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policies'] = []
            if 'A' in kwargs.vsan_fabrics: fabric_list = ['A', 'B']
            else: fabric_list = ['Shared']
            for e in fabric_list:
                policy_accept = False
                while policy_accept == False:
                    pvars = DotMap()
                    pcolor.Yellow(f'\n\n ** {e} Fabric VSAN Policy Name **')
                    kwargs.jdata         = deepcopy(kwargs.ezdata.abstract_policy.properties.name)
                    kwargs.jdata.default = f'fabric-{e.lower()}'
                    pvars.name           = ezfunctions.variable_prompt(kwargs)
                    #=====================================================================
                    # Prompt User to Accept the Policy
                    #=====================================================================
                    accept = prompt_user(self.type).to_accept(f'the  `{e}` Fabric VSAN Policy', pvars, kwargs)
                    if accept == True:
                        pvars.vsans = []
                        for vsan in args.vsans:
                            if vsan.fabric == e or vsan.fabric == 'shared':
                                d = deepcopy(vsan); d.pop('fabric'); pvars.vsans.append(d)
                        pvars = DotMap(sorted(pvars.items()))
                        kwargs.class_path = f'policies,{self.type}'
                        kwargs            = ezfunctions.ez_append(pvars, kwargs)
                        if kwargs.use_shared_org == True:  policy_name = f'{kwargs.shared_org}/{pvars.name}'
                        else: policy_name = pvars.name
                        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain[f'{self.type}_policies'].append(policy_name)
                        policy_accept = True
            #=====================================================================
            # Add Policy to Dictionaries, Update YAML and Return kwargs
            #=====================================================================
            policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for VSANs to attach to VSAN Policy Settings
    #=========================================================================
    def vsans(self, args, kwargs):
        #=====================================================================
        # Get VLAN Policy Attributes
        #=====================================================================
        vlan_policy = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.vlan_policies[0]
        kwargs      = policies.vlan_ranges(vlan_policy, kwargs)
        vlans       = kwargs.vlans
        vlan_range  = kwargs.vlan_range
        #=====================================================================
        # Begin VSANs Loop
        #=====================================================================
        pcolor.Cyan(f'\n  We will now start to configure the VSANs.')
        pcolor.Cyan('  In Most environments with Cisco MDS SAN Switches you will have a different VSAN per Fabric.')
        pcolor.Cyan('  In a Brocade based SAN Fabric it will be VSAN 1 for both Fabrics.')
        pcolor.Cyan('  You May also have multiple VSANs per Fabric as well.')
        pcolor.Cyan('  When Finished with the VSANs that you want to configure press enter on the `vsan_id` field to stop the loop.')
        input('\n Press Enter to Continue: ')
        #=====================================================================
        # Function: VSAN Policy VSANs Loop
        #=====================================================================
        args.vsans          = []
        kwargs.vsan_fabrics = []
        vsan_count          = 1
        vsan_confirm        = False
        while vsan_confirm == False:
            kwargs.reserved_vlan = kwargs.imm_dict.orgs[kwargs.org].wizard.setup.profile.reserved_vlan
            reserved_vlans = []
            for x in range(kwargs.reserved_vlan, kwargs.reserved_vlan+129): reserved_vlans.append(x)
            reserved_list = ezfunctions.vlan_list_format(reserved_vlans)
            kwargs.jdata = deepcopy(kwargs.ezdata['vsan.vsans'].properties.vsan_id)
            kwargs.jdata.description = f'Enter the VSAN Identifier for this VSAN on Fabric {e}?'
            if vsan_count >= 2: kwargs.jdata.optional = True
            vsan_id = ezfunctions.variable_prompt(kwargs)
            if vsan_id == '': vsan_confirm = True; break
            else: vsan_id = int(vsan_id)
            fcoe_vlan = vsan_id
            overlap_check = False
            while overlap_check == False:
                if fcoe_vlan in vlans:
                    pcolor.Yellow(
                        f'\n\n  !!! Warning !!!.  Need Unique VLAN Id for FCOE as `{vsan_id}` overlaps with VLAN Policy VLANs: `{vlan_range}`')
                    kwargs.jdata = deepcopy(kwargs.ezdata['vsan.vsans'].properties.fcoe_vlan_id)
                    fcoe_vlan = int(ezfunctions.variable_prompt(kwargs))
                if fcoe_vlan in reserved_vlans:
                    pcolor.Yellow(f'\n\n!!! Warning !!!.  Overlapping VLAN `{fcoe_vlan}` with the System Reserved VLAN Ids: `{reserved_list}`.\n\n')
                    kwargs.jdata = deepcopy(kwargs.ezwizard.setup.properties.discovery)
                    kwargs.jdata.description = 'Do you want to change the Reserved VLAN Range?'
                    kwargs.jdata.title = 'Reserved VLAN Range'
                    answer = ezfunctions.variable_prompt(kwargs)
                    if answer == True:
                        kwargs.jdata         = deepcopy(kwargs.ezdata.switch_control.allOf[1].properties.reserved_vlan_start_id)
                        kwargs.reserved_vlan = int(ezfunctions.variable_prompt(kwargs))
                    else:
                        kwargs.jdata = deepcopy(kwargs.ezdata['vsan.vsans'].properties.fcoe_vlan_id)
                        fcoe_vlan    = int(ezfunctions.variable_prompt(kwargs))
                if fcoe_vlan in vlans or fcoe_vlan in reserved_vlans: pass
                else: overlap_check = True
            kwargs.jdata             = deepcopy(kwargs.ezdata['vsan.vsans'].properties.name)
            kwargs.jdata.description = f'Enter a Name for VSAN `{vsan_id}`.'
            kwargs.jdata.default     = f'VSAN{str(vsan_id).zfill(4)}'
            name                     = ezfunctions.variable_prompt(kwargs)
            kwargs.jdata             = deepcopy(kwargs.ezwizard.vsan.properties.fabric)
            kwargs.jdata.description = kwargs.jdata.description.replace('REPLACE', vsan_id)
            if vsan_count % 2 == 0: kwargs.jdata.default = 'B'
            vsan_fabric = ezfunctions.variable_prompt(kwargs)
            if not vsan_fabric in kwargs.vsan_fabrics: kwargs.vsan_fabrics.append(vsan_fabric)
            edict = DotMap(fcoe_vlan_id = fcoe_vlan, name = name, vsan_id = vsan_id)
            if kwargs.imm_dict.orgs[kwargs.org].wizard.setup.domain.switch_control.switching_mode_fc == 'switch':
                edict.vsan_scope = 'Common'
            edict = DotMap(sorted(edict.items()))
            accept = prompt_user(f'VSANs for VSAN').to_accept('VSANs', edict, kwargs)
            if accept == True:
                args.vsans.append(edict)
                vsan_count += 1
            else: ezfunctions.message_starting_over('vsans')
        return args, kwargs

#=============================================================================
# Build IMM Pools
#=============================================================================
class pools(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function: Prompt User to Add Pool to IMM Dictionary
    #=========================================================================
    def add_to_imm_dict(self, pvars, kwargs):
        pool_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
        accept       = prompt_user(self.type).to_accept(f'the {pool_title} Policy', pvars, kwargs)
        if accept == True:
            kwargs.class_path = f'policies,{self.type}'
            kwargs            = ezfunctions.ez_append(pvars, kwargs)
            if kwargs.use_shared_org == True:  kwargs.pool_name = f'{kwargs.shared_org}/{pvars.name}'
            else: kwargs.pool_name = pvars.name
            pool_accept = True
        else: ezfunctions.message_starting_over(self.type)
        return pool_accept, kwargs

    #=========================================================================
    # Function: Prompt User for Flow Control Policy Settings
    #=========================================================================
    def ip(self, kwargs):
        kwargs.pool_name = pools(self.type).pool_select(kwargs)
        if kwargs.pool_name == 'Create New':
            policies(self.type).announcement(kwargs)
            pool_accept = False
            while pool_accept == False:
                pvars = DotMap()
                kwargs.jdata         = deepcopy(kwargs.ezdata.abstract_pool.properties.name)
                kwargs.jdata.default = 'ip'
                pvars.name           = ezfunctions.variable_prompt(kwargs)
                kwargs.jdata         = deepcopy(kwargs.ezwizard.pools.properties.ip_protocols)
                ip_protocols         = ezfunctions.variable_prompt(kwargs)
                for protocol in ip_protocols:
                    pvars, kwargs = pools(f'ip.{protocol.lower()}_blocks').ip_blocks(protocol, pvars, kwargs)
                #=====================================================================
                # Prompt User to Accept the Policy
                #=====================================================================
                pool_accept, kwargs = pools(self.type).add_to_imm_dict(pvars, kwargs)
        #=====================================================================
        # Add Policy to Dictionaries, Update YAML and Return kwargs
        #=====================================================================
        policies.create_yaml_files(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User for Flow Control Policy Settings
    #=========================================================================
    def ip_blocks(self, protocol, pvars, kwargs):
        p = protocol.lower()
        pcolor.Yellow(f'\n\n You can enter multiple {protocol} blocks.  When finished press enter on the `from` field with no value.')
        if 'v4' in protocol: attr_list = ['from', 'to', 'gateway', 'netmask', 'primary_dns', 'secondary_dns']
        else: attr_list = ['from', 'to', 'gateway', 'prefix', 'primary_dns', 'secondary_dns']
        count                = 0
        pvars[f'{p}_blocks'] = []
        block_accept         = False
        while block_accept == False:
            edict = DotMap()
            for e in attr_list:
                kwargs.jdata = deepcopy(kwargs.ezdata[self.type].allOf[1].properties[e])
                if count >= 1 and e == 'from': kwargs.jdata.optional = True
                edict[e] = ezfunctions.variable_prompt(kwargs)
                count += 1
            #=====================================================================
            # Prompt User to Accept the Policy
            #=====================================================================
            accept = prompt_user(f'the {protocol} Block IP').to_accept(f'the {protocol}', edict, kwargs)
            if accept == True: pvars[f'{p}_blocks'].append(edict); block_accept = True
            else: ezfunctions.message_starting_over(f'{protocol} Block')
        #=====================================================================
        # Return pvars and kwargs
        #=====================================================================
        return pvars, kwargs

    #=========================================================================
    # Function: Prompt User for New or Existing Pool
    #=========================================================================
    def pool_select(self, kwargs):
        kwargs.names  = [kwargs.org_moids[kwargs.org].moid]
        if kwargs.use_shared_org == True: kwargs.names.append(kwargs.org_moids[kwargs.shared_org].moid)
        kwargs.method = 'get'
        kwargs.uri    = deepcopy(kwargs.ezdata[self.type].intersight_uri)
        kwargs        = isight.api('multi_org').calls(kwargs)
        pool_keys     = sorted([f'{kwargs.org_names[e.Organization.Moid]}/{e.Name}' for e in kwargs.results])
        for e in kwargs.results: kwargs.isight[kwargs.org_names[e.Organization.Moid]].pools[self.type][e.Name] = e.Moid
        org_keys = list(kwargs.org_moids.keys())
        for org in org_keys:
            pkeys = list(kwargs.imm_dict.orgs[org].pools.keys())
            if self.type in pkeys:
                for e in kwargs.imm_dict.orgs[org].pools[self.type]: pool_keys.append(f'{org}/{e.name}')
        pool_keys = sorted(list(numpy.unique(numpy.array(pool_keys))))
        if len(pool_keys) > 0:
            pool_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
            kwargs.jdata = deepcopy(kwargs.ezwizard.pools.properties.pool)
            kwargs.jdata.description = (
                kwargs.jdata.description.replace('REPLACE', pool_title)).replace('PROFILE_TYPE', (kwargs.profile_type).capitalize())
            kwargs.jdata.title = kwargs.jdata.title.replace('REPLACE', pool_title)
            if type(kwargs.ignore_create_new) == bool and kwargs.ignore_create_new == True: pass
            else: pool_keys.append('Create New')
            kwargs.jdata.default = pool_keys[0]
            kwargs.jdata.enum    = pool_keys
            kwargs.jdata.sort    = False
            pool_name = ezfunctions.variable_prompt(kwargs)
            pool_name = pool_name.replace(f'{kwargs.org}/', '')
        else: pool_name = 'Create New'
        return pool_name


#=============================================================================
# Build IMM Profiles
#=============================================================================
class profiles(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function: Create YAML Files
    #=========================================================================
    def create_yaml_files(kwargs):
        orgs   = list(kwargs.org_moids.keys())
        kwargs = ezfunctions.remove_duplicates(orgs, ['profiles', 'wizard'], kwargs)
        ezfunctions.create_yaml(orgs, kwargs)

    #=========================================================================
    # Function: Prompt User for Target Platform
    #=========================================================================
    def profile_type(kwargs):
        kwargs.jdata           = deepcopy(kwargs.ezwizard.setup.properties.profile_type)
        kwargs.target_platform = ezfunctions.variable_prompt(kwargs)
        return kwargs

#=============================================================================
# Shared Questions/General Questions
#=============================================================================
class prompt_user(object):
    def __init__(self, type):
        self.type = type

    #=========================================================================
    # Function: Prompt User with Existing Pools/Policies/Profiles
    #=========================================================================
    def existing_object(ptype, item, kwargs):
        attributes = kwargs.imm_dict.orgs[kwargs.org][ptype][item]
        ptitle = ezfunctions.mod_pol_description((item.replace('_', ' ')).title())
        #=====================================================================
        # Show User Configuration
        #=====================================================================
        pcolor.Green(f'\n{"-"*108}\n  Found Existing Configuration:\n')
        pcolor.Green(textwrap.indent(yaml.dump(attributes, Dumper=yaml_dumper, default_flow_style=False), " "*3, predicate=None))
        pcolor.Green(f'\n{"-"*108}\n')
        kwargs.jdata = DotMap(
            default     = False,
            description = f'Do you want to Delete Any of these?',
            title       = 'Delete Policies',
            type        = 'boolean')
        del_objects = ezfunctions.variable_prompt(kwargs)
        if del_objects == True:
            kwargs.jdata = DotMap(
                enum        = [e.name for e in kwargs.imm_dict.orgs[kwargs.org][ptype][item]],
                description = f'Select the Options you want to Delete:',
                optional    = True,
                multi_select= True,
                title       = 'Delete Objects',
                type        = 'string')
            delete_objects = ezfunctions.variable_prompt(kwargs)
            for e in delete_objects:
                idict = [i for i in kwargs.imm_dict.orgs[kwargs.org][ptype][item] if not (i.name == e)]
                kwargs.imm_dict.orgs[kwargs.org][ptype][item] = idict
                kwargs.jdata = DotMap(
                    default     = False,
                    description = f'Do you want to Delete `{e}` from Intersight as well?',
                    title       = f'Delete {e}',
                    type        = 'boolean')
                del_int = ezfunctions.variable_prompt(kwargs)
                if del_int == True:
                    kwargs.uri = deepcopy(kwargs.ezdata[ptype].intersight_uri)
                    kwargs = isight.api_get(False, [e], ptype, kwargs)
                    if len(kwargs.results) > 0:
                        kwargs.method = 'delete'
                        kwargs = isight.api(ptype).calls(kwargs)
                    else:
                        pcolor.Red(f"\n{'-'*108}\n")
                        pcolor.Red(f'  !!! ERROR !!!!\n  Did not find {ptitle}: `{e}` in Intersight')
                        pcolor.Red(f"\n{'-'*108}\n")
        kwargs.jdata = DotMap(
            default     = True,
            description = f'Do you want to configure additional {ptitle} {ptype.title()}s?',
            title       = 'Config',
            type        = 'boolean')
        kwargs.configure_more = ezfunctions.variable_prompt(kwargs)
        return kwargs

    #=========================================================================
    # Function: Prompt User to Configure
    #=========================================================================
    def for_sub_item(item, kwargs):
        kwargs.jdata = DotMap(
            default      = True,
            description  = f'Do You want to configure `{item}`?',
            title        = item,
            type         = 'boolean')
        answer = ezfunctions.variable_prompt(kwargs)
        return answer

    #=========================================================================
    # Function - Prompt user for Timezone
    #=========================================================================
    def for_timezone(kwargs):
        timezones    = deepcopy(kwargs.ezdata.ntp.allOf[1].properties.timezone.enum)
        tz_regions   = list(set([e.split('/')[0] for e in timezones]))
        kwargs.jdata = DotMap(
            default     = sorted(tz_regions)[0],
            description = f'Select the Timezone Region.',
            enum        = sorted(tz_regions),
            title       = f'Timezone Region')
        tz_region       = ezfunctions.variable_prompt(kwargs)
        region_tzs      = [e.split('/')[1] for e in timezones if tz_region in e]
        kwargs.jdata = DotMap(
            default     = sorted(region_tzs)[0],
            description = f'Select the Timezone within the Region.',
            enum        = sorted(region_tzs),
            title       = f'Timezone')
        answer = f'{tz_region}/{ezfunctions.variable_prompt(kwargs)}'
        return answer

    #=========================================================================
    # Function: Prompt User to Accept Configuration
    #=========================================================================
    def to_accept(self, item, idict, kwargs):
        if re.search('^ip|iqn|mac|resource|uuid|wwnn|wwpn$', self.type): ptitle = f'{self.type} pool'
        elif re.search(r'(profiles|templates)\.(chasssis|domain|server|switch)', self.type):
            p2, p1 = self.type.split('.')
            ptitle = f'{p1} {p2[:-1]}'
        elif re.search(r'FIAttached|Standalone', self.type): ptitle = 'server profile'
        else: ptitle = f'{self.type} policy'
        ptitle = ezfunctions.mod_pol_description((ptitle.replace('_', ' ')).title())
        pcolor.Green(f'\n{"-"*108}\n\n  {ptitle}\n')
        yfile = open('yaml.txt', 'w')
        yfile.write(yaml.dump(idict.toDict(), Dumper=yaml_dumper, default_flow_style=False))
        yfile.close()
        yfile = open('yaml.txt', 'r')
        for line in yfile: pcolor.Green(f'{" "*3}{line.rstrip()}')
        yfile.close()
        os.remove('yaml.txt')
        pcolor.Green(f'\n{"-"*108}\n')
        kwargs.jdata = DotMap(
            default      = True,
            description  = f'Do You want to accept the above configuration for {item}?',
            title        = f'Accept',
            type         = 'boolean')
        answer = ezfunctions.variable_prompt(kwargs)
        return answer

    #=========================================================================
    # Function: Prompt User to Configure
    #=========================================================================
    def to_add(item, kwargs):
        kwargs.jdata = DotMap(
            default      = False,
            description  = f'Do You want to configure additional {item}?',
            title        = item,
            type         = 'boolean')
        answer = ezfunctions.variable_prompt(kwargs)
        return answer

    #=========================================================================
    # Function: Prompt User to Configure
    #=========================================================================
    def to_configure(item, ptype, kwargs):
        ptitle = ezfunctions.mod_pol_description((item.replace('_', ' ')).title())
        descr  = f'Do You want to configure {ptitle} {ptype.title()}s?'
        kwargs.jdata = DotMap(
            default      = True,
            description  = descr,
            title        = f'{ptitle} {ptype.title()}',
            type         = 'boolean')
        answer = ezfunctions.variable_prompt(kwargs)
        return answer

    #=========================================================================
    # Function: Prompt User to Configure Additional Instances
    #=========================================================================
    def to_configure_additional(self, default, kwargs):
        policy_title = ezfunctions.mod_pol_description((self.type.replace('_', ' ')).capitalize())
        kwargs.jdata = DotMap(
            default      = default,
            description  = f'Do You want to configure additional {policy_title}(s)?',
            title        = f'Configure Additional',
            type         = 'boolean')
        answer = ezfunctions.variable_prompt(kwargs)
        return answer

    #=========================================================================
    # Function: Prompt User for Value
    #=========================================================================
    def item(k, v, kwargs):
        kwargs.jdata = v
        kwargs.jdata.title = k
        answer = ezfunctions.variable_prompt(kwargs)
        return answer
