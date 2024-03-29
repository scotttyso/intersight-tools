#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, isight, pcolor
    from copy import deepcopy
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
    kwargs.jdata       = kwargs.ezdata.organization.allOf[1].properties.name
    kwargs.jdata.enum  = org_list
    kwargs.jdata.sort  = False
    kwargs.jdata.title = 'Intersight Organization'
    if 'Create New' in org_list:
        kwargs.jdata.description   = 'Select an Existing Organization or `Create New`, for the organization to apply these changes within.'
    else: kwargs.jdata.description = 'Select an Existing Organization to apply these changes within.'
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
    kwargs.jdata = kwargs.ezwizard.setup.properties.assignment_method
    if kwargs.target_platform == 'Standalone':
        kwargs.jdata.enum.pop('Chassis/Slot')
        kwargs.jdata.description.replace(' * Chassis/Slot:  Assign Server Profiles to Chassis/Slot.\n', '')
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.assignment_method = ezfunctions.variable_prompt(kwargs)
    return kwargs

#=================================================================
# Function: Prompt User for Build Method
#=================================================================
def setup_build_type(kwargs):
    kwargs.jdata      = kwargs.ezwizard.setup.properties.build_type
    kwargs.build_type = ezfunctions.variable_prompt(kwargs)
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.build_type = kwargs.build_type
    return kwargs

#=================================================================
# Function: Prompt User for Deployment Type: Python/Terraform
#=================================================================
def setup_deployment_method(kwargs):
    if not re.search('Python|Terraform', kwargs.args.deployment_method):
        kwargs.jdata             = kwargs.ezwizard.setup.properties.deployment_method
        kwargs.deployment_method = ezfunctions.variable_prompt(kwargs)
    else: kwargs.deployment_method = kwargs.args.deployment_method
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.deployment_method = kwargs.deployment_method
    return kwargs

#=================================================================
# Function: Main Menu, Prompt User for Deployment Type
#=================================================================
def setup_deployment_type(kwargs):
    if not re.search('FIAttached|Standalone|Profile|Individual|Deploy', kwargs.args.deployment_type):
        kwargs.jdata           = kwargs.ezwizard.setup.properties.deployment_type
        kwargs.deployment_type = ezfunctions.variable_prompt(kwargs)
    else: kwargs.deployment_type = kwargs.args.deployment_type
    return kwargs

#=================================================================
# Function: Prompt User for Discovery
#=================================================================
def setup_discovery(kwargs):
    kwargs.jdata     = kwargs.ezwizard.setup.properties.discovery
    kwargs.discovery = ezfunctions.variable_prompt(kwargs)
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.discovery = kwargs.discovery
    return kwargs

#=================================================================
# Function: Prompt User for Name Prefix
#=================================================================
def setup_name_prefix(kwargs):
    if not kwargs.imm_dict.orgs[kwargs.org].policies.get('name_prefix'):
        kwargs.jdata = kwargs.ezwizard.setup.properties.name_prefix
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.name_prefix = ezfunctions.variable_prompt(kwargs)
    return kwargs

#=================================================================
# Function: Prompt User for Name Suffix
#=================================================================
def setup_name_suffix(kwargs):
    if not kwargs.imm_dict.orgs[kwargs.org].policies.get('name_suffix'):
        kwargs.jdata = kwargs.ezwizard.setup.properties.name_suffix
        kwargs.imm_dict.orgs[kwargs.org].wizard.setup.name_suffix = ezfunctions.variable_prompt(kwargs)
    return kwargs

#=================================================================
# Function: Prompt User for Operating System Vendor
#=================================================================
def setup_operating_systems(kwargs):
    kwargs            = isight.software_repository('os_vendors').os_vendor_and_version(kwargs)
    kwargs.jdata      = kwargs.ezwizard.setup.properties.operating_system_vendor
    kwargs.jdata.enum = sorted(list(kwargs.os_vendors.keys()))
    if kwargs.imm_dict.orgs[kwargs.org].wizard.deployment_type == 'Profile': kwargs.jdata.multi_select == False
    os_vendors = ezfunctions.variable_prompt(kwargs)
    if type(os_vendors) == str: os_vendors = [os_vendors]
    kwargs.operating_systems = []
    for e in os_vendors:
        dist_list = [e for k in list(kwargs.os_cfg_moids.keys()) for e in kwargs.os_cfg_moids[k].distributions]
        versions = sorted([k for k,v in kwargs.os_versions.items() if v.vendor_moid == kwargs.os_vendors[e].moid and v.moid in dist_list], reverse=True)
        kwargs.jdata             = kwargs.ezwizard.setup.properties.operating_system_version
        kwargs.jdata.default     = versions[0]
        kwargs.jdata.description = (kwargs.jdata.description).replace('REPLACE', e)
        kwargs.jdata.enum        = versions
        kwargs.jdata.title       = (kwargs.jdata.title).replace('REPLACE', e)
        os_version               = ezfunctions.variable_prompt(kwargs)
        kwargs.operating_systems.append(DotMap(vendor=e,version=DotMap(moid=kwargs.os_versions[os_version].moid, name=os_version)))
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.operating_systems = kwargs.operating_systems
    return kwargs

#=================================================================
# Function: Prompt User for Target Platform
#=================================================================
def setup_target_platform(kwargs):
    kwargs.jdata           = kwargs.ezwizard.setup.properties.target_platform
    kwargs.target_platform = ezfunctions.variable_prompt(kwargs)
    kwargs.imm_dict.orgs[kwargs.org].wizard.setup.target_platform = kwargs.target_platform
    return kwargs

#=================================================================
# Function: Prompt User for OS Image
#=================================================================
def sw_repo_os_cfg(os, kwargs):
    if not kwargs.get('os_cfg_results'): kwargs  = isight.software_repository('cfg').os_configuration(kwargs)
    elist   = []; os_cfg = []
    for e in kwargs.os_cfg_results:
        if os.version.moid in [f.Moid for f in e.Distributions]:
            if 'shared' in e.Owners:
                elist.append(f'Location: Intersight || Name: {e.Name} || Moid: {e.Moid}')
            else: elist.append(f'Location: {e.Source.LocationLink} || Name: {e.Name} || Moid: {e.Moid}')
            os_cfg.append(e)
    if len(elist) > 1:
        kwargs.jdata         = kwargs.ezwizard.setup.properties.sw_repo_os_image
        kwargs.jdata.default = elist[0]
        kwargs.jdata.enum    = elist
        answer               = ezfunctions.variable_prompt(kwargs)
        regex                = re.compile(r'Location: (.*) \|\| Name: (.*) \|\| Moid: (.*)$')
        match                = regex.search(answer)
        sw                   = DotMap(location = match.group(1), name = match.group(2), moid = match.group(3))
        indx                 = next((index for (index, d) in enumerate(os_cfg) if d['Moid'] == sw.moid), None)
        kwargs.os_cfg        = os_cfg[indx]
    elif len(elist) == 1: kwargs.os_cfg = os_cfg[0]
    else:
        pcolor.Red(f'\n{"-"*108}\n')
        pcolor.Red(f'  !!!ERROR!!! No Operating System Configuration File found in Intersight Organization `{kwargs.org}` to support Vendor: `{os.vendor}` Version: `{os.version.name}`.  Exiting...')
        pcolor.Red(f'\n{"-"*108}\n'); sys.exit(1)
    rows = []
    for e in kwargs.os_cfg.Placeholders:
        rows.append([f'Label: {e.Type.Label}', f'Name: {e.Type.Name}', f'Sensitive: {e.Type.Properties.Secure}', f'Required: {e.Type.Required}'])
    cwidth = max(len(word) for row in rows for word in row) + 2
    prows = []
    for row in rows:
        prows.append("".join(word.ljust(cwidth) for word in row))
    prows.sort()
    for row in prows:
        print(row)
    #print(json.dumps(kwargs.os_cfg, indent=4))
    exit()
    return kwargs

#=================================================================
# Function: Prompt User for OS Image
#=================================================================
def sw_repo_os_image(os, kwargs):
    kwargs = isight.software_repository('osi').os_images(kwargs)
    #kwargs.osi_moids = sorted(kwargs.osi_moids, key=lambda item: item['Version'], reverse=True)
    elist = []
    osi_moids = []
    for e in kwargs.osi_moids:
        if e.Vendor == os.vendor and e.Version == os.version.name:
            elist.append(f'Location: {e.Source.LocationLink} || Name: {e.Name} || Moid: {e.Moid}')
            osi_moids.append(deepcopy(e))
    if len(kwargs.jdata.enum) > 1:
        kwargs.jdata         = kwargs.ezwizard.setup.properties.sw_repo_os_image
        kwargs.jdata.default = elist[0]
        kwargs.jdata.enum    = elist
        answer               = ezfunctions.variable_prompt(kwargs)
        regex                = re.compile(r'Location: (.*) \|\| Name: (.*)$ \|\| Moid: (.*)$')
        match                = regex.search(answer)
        sw                   = DotMap(location = match.group(1), name = match.group(2), moid = match.group(3))
        indx                 = next((index for (index, d) in enumerate(kwargs.scu_moids) if d['Moid'] == sw.moid), None)
        kwargs.os_image      = osi_moids[indx]
    elif len(kwargs.jdata.enum) == 1: kwargs.os_image = osi_moids[0]
    else:
        pcolor.Red(f'\n{"-"*108}\n')
        pcolor.Red(f'  !!!ERROR!!! No Operating System Image Found in Intersight Organization `{kwargs.org}` to support Vendor: `{os.vendor}`.')
        pcolor.Red(f'  Exiting...')
        pcolor.Red(f'\n{"-"*108}\n'); sys.exit(1)
    return kwargs

#=================================================================
# Function: Prompt User for Server Configuration Utility
#=================================================================
def sw_repo_scu(kwargs):
    elist  = []
    kwargs = isight.software_repository('scu').scu(kwargs)
    models = ", ".join(kwargs.models)
    for e in kwargs.scu_moids:
        elist.append(f'Location: {e.Source.LocationLink} || Version: {e.Version} || Name: {e.Name} || Supported Models: {", ".join(e.SupportedModels)} || Moid: {e.Moid}')
    def print_error(kwargs):
        pcolor.Red(f'\n{"-"*108}\n')
        pcolor.Red(f'  !!!ERROR!!! No Server Configuration Utility Image Found in Intersight Organization `{kwargs.org}` to support Models: {models}.  Exiting....')
        pcolor.Red(f'  Exiting...')
        pcolor.Red(f'\n{"-"*108}\n'); sys.exit(1)
    kwargs.scu = []
    if len(elist) > 1:
        kwargs.jdata         = kwargs.ezwizard.setup.properties.sw_repo_scu
        kwargs.jdata.default = elist[0]
        kwargs.jdata.enum    = elist
        answer = ezfunctions.variable_prompt(kwargs)
        regex  = re.compile(r'Location: (.*) \|\| Version: (.*) \|\| Name: (.*) \|\| .* Moid: ([a-z0-9]+)$')
        match  = regex.search(answer)
        sw = DotMap(location = match.group(1), version = match.group(2), name = match.group(3), moid=match.group(4))
        indx = next((index for (index, d) in enumerate(kwargs.scu_moids) if d['Moid'] == sw.moid), None)
        models = True
        for d in kwargs.models:
            if not d in kwargs.scu_moids[indx]: models = False
        if models == True: kwargs.scu = e
    elif len(elist) == 1:
        for d in kwargs.models:
            if not d in kwargs.scu_moids[0]: models = False
        if models == True: kwargs.scu = e
        kwargs.scu == kwargs.scu_moids[0]
    else: print_error(kwargs)
    if len(kwargs.scu) == 0: print_error(kwargs)
    return kwargs

