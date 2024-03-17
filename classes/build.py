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
    # Function: Domain Discovery
    #=================================================================
    def domain_discovery(self, kwargs):
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
        if len(kwargs.fc_ports) > 0:
            kwargs = questions.port_mode_fc(kwargs)
            kwargs.jdata = kwargs.ezdata.switch_control.allOf[1].properties.fc_switching_mode
            kwargs.jdata.description = 'Configure FC Switching Mode\n\n' + kwargs.jdata.description
            fc_sw_mode = ezfunctions.variable_prompt(kwargs)
            if fc_sw_mode == 'end-host':
                kwargs.jdata = DotMap(
                    default     = 'port_channel',
                    enum        = ['port_channel', 'uplink'],
                    description = f'Do you want to configure Port-Channel(s) or Uplink(s) for the FC Ports?',
                    title       = 'Uplink Type',
                    type        = 'string')
                fc_uplink_type  = ezfunctions.variable_prompt(kwargs)
            else: fc_uplink_type = 'uplink'
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
    def quick_start(self, kwargs):

        # Return kwargs
        return kwargs