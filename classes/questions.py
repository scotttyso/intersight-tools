#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, isight, pcolor
    from dotmap import DotMap
    import json, os, re, textwrap, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

# YAML Format Class
class yaml_dumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(yaml_dumper, self).increase_indent(flow, False)

#=================================================================
# Function: Prompt User with Existing Pools/Policies/Profiles
#=================================================================
def existing_object(ptype, item, kwargs):
    attributes = kwargs.imm_dict.orgs[kwargs.org][ptype][item]
    ptitle = ezfunctions.mod_pol_description((item.replace('_', ' ')).title())
    #==============================================
    # Show User Configuration
    #==============================================
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
            kwargs.uri = kwargs.ezdata[ptype].intersight_uri
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

#=================================================================
# Function: Prompt User for Pools/Policies/Profiles to Create
#=================================================================
def main_menu_individual(kwargs):
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

#=================================================================
# Function: Prompt User for Individual Types
#=================================================================
def main_menu_individual_types(kwargs):
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

#=================================================================
# Function: Prompt User for Intersight Organization
#=================================================================
def organization(kwargs):
    kwargs = isight.api('organization').all_organizations(kwargs)
    org_list = sorted(list(kwargs.org_moids.keys()), key=str.casefold)
    if not 'Profile' == kwargs.deployment_type: org_list.append('Create New')
    kwargs.jdata             = kwargs.ezdata.organization.allOf[1].properties.name
    kwargs.jdata.description = 'Select an Existing Organization or `Create New`, for the organization to apply these changes within.'
    kwargs.jdata.enum        = org_list
    kwargs.jdata.sort        = False
    kwargs.jdata.title       = 'Intersight Organization'
    kwargs.org               = ezfunctions.variable_prompt(kwargs)
    if kwargs.org == 'Create New':
        for e in ['description', 'name']:
            kwargs.jdata = kwargs.ezdata.organization.allOf[1].properties[e]
            if e == 'name': kwargs.jdata.default = 'example'
            kwargs[e]    = ezfunctions.variable_prompt(kwargs)
        kwargs.org    = kwargs.name
        kwargs.names  = [kwargs.org]
        kwargs.method = 'get'
        kwargs.uri    = kwargs.ezdata.resource_group.intersight_uri
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
        kwargs.uri    = kwargs.ezdata.organization.intersight_uri
        kwargs        = isight.api('organization').calls(kwargs)
        kwargs.org_moids[kwargs.org] = DotMap(moid = kwargs.pmoid)
    kwargs.imm_dict.orgs[kwargs.org].wizard.org = kwargs.org
    return kwargs

#=================================================================
# Function: Prompt User for Intersight Shared Organization
#=================================================================
def organization_shared(kwargs):
    kwargs.use_shared_org = False
    if kwargs.org != 'default':
        kwargs.jdata = DotMap(
            default     = True,
            description = '  A Shared Organization can be used to share policies to other organization.'\
                '  This can be helpful to reduce duplicate pools and policies for each organization.'\
                '  Would you like to configured a Shared Organization?',
            sort        = False,
            title       = 'Intersight Shared Organization',
            type        = 'boolean')
        kwargs.use_shared_org = ezfunctions.variable_prompt(kwargs)
    if kwargs.use_shared_org == True:
        kwargs      = isight.api('organization').all_organizations(kwargs)
        org_results = kwargs.results
        org_list = sorted([e.Name for e in org_results if e.get('SharedWithResources')], key=str.casefold)
        org_list.append('Create New')
        print(org_list)
        kwargs.jdata = DotMap(
            enum        = org_list,
            default     = org_list[0],
            description = 'Select an Existing Organization or `Create New`, for the shared Organization.',
            sort        = False,
            title       = 'Intersight Shared Organization',
            type        = 'string')
        shared_org = ezfunctions.variable_prompt(kwargs)
        if shared_org == 'Create New':
            for e in ['description', 'name']:
                kwargs.jdata = kwargs.ezdata.organization.allOf[1].properties[e]
                if e == 'name': kwargs.jdata.default = 'shared_org'
                kwargs[e]    = ezfunctions.variable_prompt(kwargs)
            kwargs.shared_org = kwargs.name
            org_list = sorted([e.Name for e in org_results if not e.get('SharedWithResources')], key=str.casefold)
            kwargs.jdata = DotMap(
                enum         = org_list,
                default      = org_list[0],
                description  = f'Select the Organization to Share pools/policies/templates from Organization {kwargs.shared_org}.',
                multi_select = True,
                title        = 'Intersight Shared Organization',
                type         = 'string')
            shared_sub_orgs = ezfunctions.variable_prompt(kwargs)
            kwargs.api_body = {"Description": kwargs.description, "Name": kwargs.shared_org, "ObjectType":"organization.Organization"}
            kwargs.method = 'post'
            kwargs.uri    = kwargs.ezdata.organization.intersight_uri
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
                print(org_results[indx].SharedWithResources)
                print(kwargs.org_moids[kwargs.org].moid)
                kwargs.build_skip = True
                kwargs.bulk_list  = []
                kwargs.bulk_list.append(
                    {"SharedResource":{"Moid": kwargs.org_moids[kwargs.shared_org].moid, "ObjectType":"organization.Organization"},
                     "SharedWithResource":{"Moid": kwargs.org_moids[kwargs.org].moid, "ObjectType":"organization.Organization"}})
                kwargs.uri    = 'iam/SharingRules'
                kwargs = isight.imm('sharing_rules').bulk_request(kwargs)
        kwargs.imm_dict.orgs[kwargs.org].wizard.shared_org = kwargs.shared_org
    else: kwargs.imm_dict.orgs[kwargs.org].wizard.pop('shared_org')
    return kwargs

#=================================================================
# Function: Prompt User to Load Previous Configurations
#=================================================================
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

#=================================================================
# Function: Prompt User for Fibre-Channel Port Mode
#=================================================================
def port_mode_fc(kwargs):
    kwargs.fc_converted_ports = []
    kwargs.port_modes         = []
    kwargs.ports_in_use       = []
    kwargs.port_modes         = []
    kwargs.jdata = DotMap(
        default     = True,
        description = f'Do you want to convert ports to Fibre-Channel Mode?',
        title       = 'FC Port Mode',
        type        = 'boolean')
    kwargs.fc_mode = ezfunctions.variable_prompt(kwargs)
    if kwargs.fc_mode == True:
        if len(kwargs.fc_ports) > 0:
            pcolor.Yellow(f'\n{"-"*51}\n\nPorts with FC Optics installed.')
            for e in kwargs.fc_ports: pcolor.Yellow(f'  * slot_id: {e.slot_id}, port_id: {e.port_id}, transceiver: {e.transceiver}')
        if kwargs.domain.type == 'UCS-FI-6536':
            kwargs.jdata   = kwargs.ezwizard.fabric.properties.port_mode_gen5
        else: kwargs.jdata = kwargs.ezwizard.fabric.properties.port_mode_gen4
        fc_ports = ezfunctions.variable_prompt(kwargs)
        x = fc_ports.split('-')
        kwargs.fc_ports = [int(x[0]),int(x[1])]
        for i in range(int(x[0]), int(x[1]) + 1):
            kwargs.ports_in_use.append(i)
            kwargs.fc_converted_ports.append(i)
        if kwargs.domain.type == 'UCS-FI-6536':
            port_modes = {'custom_mode':'BreakoutFibreChannel32G','port_list':kwargs.fc_ports,}
        else: port_modes = {'custom_mode':'FibreChannel','port_list':kwargs.fc_ports,}
    kwargs.port_modes.append(port_modes)
    # Return kwargs
    return kwargs

#=================================================================
# Function: Prompt User to Configure
#=================================================================
def prompt_user_for_sub_item(item, kwargs):
    kwargs.jdata = DotMap(
        default      = True,
        description  = f'Do You want to configure `{item}`?',
        title        = item,
        type         = 'boolean')
    answer = ezfunctions.variable_prompt(kwargs)
    return answer

#======================================================
# Function - Prompt user for Timezone
#======================================================
def prompt_user_for_timezone(kwargs):
    timezones    = kwargs.ezdata.ntp.allOf[1].properties.timezone.enum
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

#=================================================================
# Function: Prompt User to Accept Configuration
#=================================================================
def prompt_user_to_accept(item, idict, kwargs):
    pcolor.Green(f'\n{"-"*108}\n')
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

#=================================================================
# Function: Prompt User to Configure
#=================================================================
def promp_user_to_add(item, kwargs):
    kwargs.jdata = DotMap(
        default      = False,
        description  = f'Do You want to configure additional {item}?',
        title        = item,
        type         = 'boolean')
    answer = ezfunctions.variable_prompt(kwargs)
    return answer

#=================================================================
# Function: Prompt User to Configure
#=================================================================
def prompt_user_to_configure(item, ptype, kwargs):
    ptitle = ezfunctions.mod_pol_description((item.replace('_', ' ')).title())
    descr  = f'Do You want to configure {ptitle} {ptype.title()}s?'
    kwargs.jdata = DotMap(
        default      = True,
        description  = descr,
        title        = f'{ptitle} {ptype.title()}',
        type         = 'boolean')
    answer = ezfunctions.variable_prompt(kwargs)
    return answer

#=================================================================
# Function: Prompt User for Value
#=================================================================
def prompt_user_item(k, v, kwargs):
    kwargs.jdata = v
    kwargs.jdata.title = k
    answer = ezfunctions.variable_prompt(kwargs)
    return answer

#=================================================================
# Function: Main Menu, Prompt User for Deployment Type
#=================================================================
def setup_assignment_method(kwargs):
    description = 'Select the Method you will use to assign server profiles:\n'
    d1 = ' * Chassis/Slot:  Assign Server Profiles to Chassis/Slot.\n'
    d2 = ' * Resource Pool: Assign Server Profiles to Resource Pools.\n'
    d3 = ' * Serial:        Assign Server Profiles based on the Server Serial Number.'
    if kwargs.target_platform == 'FIAttached':
        description = description + d1 + d2 + d3
        enum_list   = ['Chassis/Slot', 'Resource Pool', 'Serial']
    else:
        description = description + d2 + d3
        enum_list   = ['Resource Pool', 'Serial']
    kwargs.jdata = DotMap(
        enum         = enum_list,
        default      = 'Serial',
        description  = description,
        title        = 'Deployment Type',
        type         = 'string')
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.assignment_method = ezfunctions.variable_prompt(kwargs)
    return kwargs

#=================================================================
# Function: Prompt User for Build Method
#=================================================================
def setup_build_type(kwargs):
    description = 'Choose the Automation Method.\n'\
    ' * Interactive: This Wizard will Prompt the User for all Pool, Policy, and Profile settings.\n'\
    ' * Machine: This Wizard will Discover the Inventory, and configure based on Best Practices, '\
        'only prompting for information unique to an environment.\n'
    kwargs.jdata = DotMap(
        enum         = ['Interactive', 'Machine'],
        default      = 'Machine',
        description  = description,
        title        = 'Automation Type',
        type         = 'string')
    kwargs.build_type = ezfunctions.variable_prompt(kwargs)
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.build_type = kwargs.build_type
    return kwargs

#=================================================================
# Function: Prompt User for Deployment Type: Python/Terraform
#=================================================================
def setup_deployment_method(kwargs):
    deployment_method = kwargs.args.deployment_method
    if deployment_method == None: deployment_method = ''
    if re.search('Python|Terraform', deployment_method): kwargs.imm_dict.orgs[kwargs.org].wizard.deployment_method = deployment_method
    else:
        description = 'Choose the Automation Language You want to use to deploy to Intersight.\n'\
        ' * Python: This Wizard will Create the YAML Files and Deploy to Intersight.\n'\
        ' * Terraform: This Wizard will only Create the YAML Files.  Terraform will be used to Manage Deployment and IaC.\n'
        kwargs.jdata = DotMap(
            enum         = ['Python', 'Terraform'],
            default      = 'Python',
            description  = description,
            title        = 'Automation Type',
            type         = 'string')
    kwargs.deployment_method = ezfunctions.variable_prompt(kwargs)
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.deployment_method = kwargs.deployment_method
    return kwargs

#=================================================================
# Function: Main Menu, Prompt User for Deployment Type
#=================================================================
def setup_deployment_type(kwargs):
    description = 'Select the Option to Perform:\n'\
    ' * FIAttached: Build Pools/Policies/Profiles for a Domain.\n'\
    ' * Standalone: Build Pools/Policies/Profiles for a Group of Standalone Servers.\n'\
    ' * Profile:    Deploy a Profile from an Existing Server Profile Template.\n'\
    ' * Individual: Select Individual Pools, Policies, Profiles to Build.\n'\
    ' * Deploy:     Skip Wizard and deploy configured from the YAML Files for Pools, Policies, and Profiles.\n'\
    ' * Exit:       Cancel the Wizard'
    kwargs.jdata = DotMap(
        enum         = ['FIAttached', 'Standalone', 'Profile', 'Individual', 'Deploy', 'Exit'],
        default      = 'FIAttached',
        description  = description,
        multi_select = False,
        sort         = False,
        title        = 'Deployment Type',
        type         = 'string')
    kwargs.deployment_type = ezfunctions.variable_prompt(kwargs)
    return kwargs

#=================================================================
# Function: Prompt User for Build Method
#=================================================================
def setup_discovery(kwargs):
    kwargs.jdata = DotMap(
        default      = False,
        description  = 'Is the Equipment Already Registered to Intersight?',
        title        = 'Discovery Status',
        type         = 'boolean')
    kwargs.discovery = ezfunctions.variable_prompt(kwargs)
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery = kwargs.discovery
    return kwargs

#=================================================================
# Function: Prompt User for Build Method
#=================================================================
def setup_name_prefix(kwargs):
    if not kwargs.imm_dict.orgs[kwargs.org].policies.get('name_prefix'):
        #==============================================
        # Prompt User for Name Prefix
        #==============================================
        kwargs.jdata = DotMap(
            description = f'Name Prefix to assign to Pools and Policies.',
            maxLength   = 32,
            minLength   = 0,
            optional    = True,
            pattern     = "^[a-zA-Z0-9_\\. :-]{0,32}$",
            title       = 'Name Prefix',
            type        = 'string')
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.name_prefix = ezfunctions.variable_prompt(kwargs)
    return kwargs

#=================================================================
# Function: Prompt User for Build Method
#=================================================================
def setup_name_suffix(kwargs):
    if not kwargs.imm_dict.orgs[kwargs.org].policies.get('name_suffix'):
        #==============================================
        # Prompt User for Name Prefix
        #==============================================
        kwargs.jdata = DotMap(
            description = f'Name Suffix to assign to Pools and Policies.',
            maxLength   = 32,
            minLength   = 0,
            optional    = True,
            pattern     = "^[a-zA-Z0-9_\\. :-]{0,32}$",
            title       = 'Name Suffix',
            type        = 'string')
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.name_suffix = ezfunctions.variable_prompt(kwargs)
    return kwargs

#=================================================================
# Function: Prompt User for Target Platform
#=================================================================
def setup_operating_systems(kwargs):
    kwargs.jdata = kwargs.ezwizard.server.properties.operating_system_vendor
    if kwargs.imm_dict.orgs[kwargs.org].wizard.deployment_type == 'Profile': kwargs.jdata.multi_select == False
    kwargs.operating_systems = ezfunctions.variable_prompt(kwargs)
    if type(kwargs.operating_systems) == str: kwargs.operating_systems = [kwargs.operating_systems]
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems = kwargs.operating_systems
    return kwargs

#=================================================================
# Function: Prompt User for Target Platform
#=================================================================
def setup_target_platform(kwargs):
    description = 'Select the Server Profile Target Platform.  Options are:\n'\
    ' * FIAttached: Build Pools/Policies/Profiles for a Domain.\n'\
    ' * Standalone: Build Pools/Policies/Profiles for Standalone Servers.\n'
    kwargs.jdata = DotMap(
        enum         = ['FIAttached', 'Standalone'],
        default      = 'FIAttached',
        description  = description,
        multi_select = False,
        sort         = False,
        title        = 'Type of Servers',
        type         = 'string')
    kwargs.target_platform = ezfunctions.variable_prompt(kwargs)
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform = kwargs.target_platform
    return kwargs
