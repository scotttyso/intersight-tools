#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, lansan, pools, pcolor, validating
    from copy import deepcopy
    from dotmap import DotMap
    import base64, json, os, re, textwrap, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

class yaml_dumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(yaml_dumper, self).increase_indent(flow, False)

class policies(object):
    def __init__(self, name_prefix, org, type):
        self.name_prefix = name_prefix
        self.org = org
        self.type = type

    #==============================================
    # Adapter Configuration Policy Module
    #==============================================
    def adapter_configuration(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'adapter'
        org            = self.org
        policy_type    = 'Adapter Configuration Policy'
        yaml_file      = 'ethernet'
        while configure_loop == False:
            pcolor.Cyan(f'\n-------------------------------------------------------------------------------------------\n')
            pcolor.Cyan(f'  An {policy_type} configures the Ethernet and Fibre-Channel settings for the ')
            pcolor.Cyan(f'  Virtual Interface Card (VIC) adapter.\n')
            pcolor.Cyan(f'  This wizard will save the configuration for this section to the following file:')
            pcolor.Cyan(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            pcolor.Cyan(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure an {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.adapter.FcSettings.allOf[1].properties
                    #==============================================
                    # Prompt User for FIP Enabled
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.FipEnabled)
                    kwargs.jData.description = 'If Selected, then FCoE Initialization Protocol (FIP) mode is enabled.'\
                        ' FIP mode ensures that the adapter is compatible with current FCoE standards.'
                    kwargs.jData.varInput = f'Do you want to Enable FIP on the VIC?'
                    kwargs.jData.varName  = 'FIP Enabled'
                    polVars.enable_fip = ezfunctions.varBoolLoop(**kwargs)
                    #==============================================
                    # Prompt User for LLDP Enabled
                    #==============================================
                    jsonVars = jsonData.adapter.EthSettings.allOf[1].properties
                    kwargs.jData = deepcopy(jsonVars.LldpEnabled)
                    kwargs.jData.description = 'If Selected, then Link Layer Discovery Protocol (LLDP) enables all'\
                        ' the Data Center Bridging Capability Exchange protocol (DCBX) functionality, which '\
                        'includes FCoE, priority based flow control.'
                    kwargs.jData.varInput = f'Do you want to Enable LLDP on the VIC?'
                    kwargs.jData.varName  = 'LLDP Enabled'
                    polVars.enable_lldp = ezfunctions.varBoolLoop(**kwargs)
                    #==============================================
                    # Prompt User for Port-Channel Settings
                    #==============================================
                    jsonVars = jsonData.adapter.PortChannelSettings.allOf[1].properties
                    kwargs.jData = deepcopy(jsonVars.Enabled)
                    kwargs.jData.varInput = f'Do you want to Enable Port-Channel on the VIC?'
                    kwargs.jData.varName  = 'Port-Channel Settings'
                    polVars.enable_port_channel = ezfunctions.varBoolLoop(**kwargs)

                    jsonVars = jsonData.adapter.DceInterfaceSettings.allOf[1].properties
                    intList = [1, 2, 3, 4]
                    polVars.dce_interface_settings = {'dce_interface_fec_modes':[]}
                    for x in intList:
                        #==============================================
                        # Prompt User for FEC Mode
                        #==============================================
                        kwargs.jData = deepcopy(jsonVars.FecMode)
                        kwargs.jData.varType = f'DCE Interface {x} FEC Mode'
                        polVars.dce_interface_settings.dce_interface_fec_modes.append(
                            ezfunctions.variablesFromAPI(**kwargs)
                        )
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,adapter_configuration'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # BIOS Policy Module
    #==============================================
    def bios(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        ezData         = kwargs.ezData
        name_prefix    = self.name_prefix
        org            = self.org
        policy_type    = 'BIOS Policy'
        yaml_file      = 'compute'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  {policy_type} Policies:  To simplify your work, this wizard will use {policy_type}')
            print(f'  Templates that are pre-configured.  You can add custom {policy_type} policy')
            print(f'  configuration to the {yaml_file}.yaml file at your descretion.')
            print(f'  That will not be covered by this wizard as the focus of the wizard is on simplicity.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure a {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Get API Data
                    #==============================================
                    polVars = {}
                    kwargs.multi_select = False
                    #==============================================
                    # Prompt User for BIOS Template Name
                    #==============================================
                    jsonVars = ezData.ezimm.allOf[1].properties.policies.bios.Policy
                    kwargs.jData = deepcopy(jsonVars.templates)
                    kwargs.jData.varType = 'BIOS Template'
                    polVars.bios_template = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    if not name_prefix == '': name = '{}-{}'.format(name_prefix, polVars.bios_template)
                    else: name = polVars.bios_template
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,bios'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'Y')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Boot Order Policy Module
    #==============================================
    def boot_order(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        ezData         = kwargs.ezData
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'boot'
        org            = self.org
        policy_type    = 'Boot Order Policy'
        target_platform= kwargs.target_platform
        yaml_file      = 'compute'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} configures the linear ordering of devices and enables you to change ')
            print(f'  the boot order and boot mode. You can also add multiple devices under various device types,')
            print(f'  rearrange the boot order, and set parameters for each boot device type.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure a {policy_type}.  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    kwargs.name         = polVars.name
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.boot.PrecisionPolicy.allOf[1].properties
                    #==============================================
                    # Prompt User for Boot Mode
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.ConfiguredBootMode)
                    kwargs.jData.update({'varType': 'Configured Boot Mode'})
                    polVars.boot_mode = ezfunctions.variablesFromAPI(**kwargs)
                    if polVars.boot_mode == 'Uefi':
                        #==============================================
                        # Prompt User to Enable Secure Boot
                        #==============================================
                        kwargs.jData = deepcopy(jsonVars.EnforceUefiSecureBoot)
                        kwargs.jData.update({'default': False, 'varName': 'Uefi SecureBoot'})
                        kwargs.jData.varInput = f'Do you want to Enforce Uefi Secure Boot?'
                        polVars.enable_secure_boot = ezfunctions.varBoolLoop(**kwargs)
                    else: polVars.enable_secure_boot = False
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(f'  Configure boot device(s). The configuration options vary with boot device types.')
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    polVars.boot_devices = []
                    inner_loop_count = 1
                    sub_loop = False
                    while sub_loop == False:
                        question = input(f'\nWould you like to configure a Boot Device?  Enter "Y" or "N" [Y]: ')
                        if question == '' or question == 'Y':
                            valid_sub = False
                            while valid_sub == False:
                                #==============================================
                                # Prompt User for Boot Device Type
                                #==============================================
                                jsonVars = jsonData.boot.DeviceBase.allOf[1].properties
                                kwargs.jData = deepcopy(jsonVars.ClassId)
                                kwargs.jData.default     = 'boot.LocalDisk'
                                kwargs.jData.description = 'Select the Type of Boot Device to configure.'
                                kwargs.jData.varType     = 'Boot Device Class ID'
                                objectType = ezfunctions.variablesFromAPI(**kwargs)
                                #==============================================
                                # Prompt User for Boot Device Name
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.Name)
                                kwargs.jData.default  = objectType.split('.')[1].lower()
                                kwargs.jData.maximum  = 30
                                kwargs.jData.minimum  = 1
                                kwargs.jData.varInput = 'Boot Device Name:'
                                kwargs.jData.varName  = 'Boot Device Name'
                                device_name = ezfunctions.varStringLoop(**kwargs)
                                boot_device = {"name":device_name, "object_type":objectType}
                                #==============================================
                                # Get Boot Device API Data
                                #==============================================
                                if not re.search('boot.(LocalCdd|UefiShell)', objectType):
                                    jsonVars = jsonData[objectType].allOf[1].properties
                                #==============================================
                                # Prompt User for Slot
                                #==============================================
                                if objectType == 'boot.LocalDisk':
                                    ezVars = ezData.ezimm.allOf[1].properties.policies.boot.PrecisionPolicy
                                    kwargs.jData = deepcopy(jsonVars.Slot)
                                    kwargs.jData.default = ezVars.boot.Localdisk.default
                                    kwargs.jData.enum = ezVars.boot.Localdisk[target_platform]
                                    kwargs.jData.varType = 'Slot'
                                    Slot = ezfunctions.variablesFromAPI(**kwargs)
                                    if re.search('^[0-9]+$', Slot):
                                        kwargs.jData = DotMap()
                                        kwargs.jData.default     =  1
                                        kwargs.jData.description = 'Slot Number between 1 and 205.'
                                        kwargs.jData.pattern     = '[0-9]+'
                                        kwargs.jData.maximum     = 205
                                        kwargs.jData.minimum     = 1
                                        kwargs.jData.varInput    = 'Slot ID of the Localdisk:'
                                        kwargs.jData.varName     = 'Slot'
                                        Slot = ezfunctions.varNumberLoop(**kwargs)
                                    boot_device.update({'slot':Slot})
                                if objectType == 'boot.Pxe':
                                    #==============================================
                                    # Prompt User for IP Type
                                    #==============================================
                                    kwargs.jData = deepcopy(jsonVars.IpType)
                                    kwargs.jData.varType = 'IP Type'
                                    IpType = ezfunctions.variablesFromAPI(**kwargs)
                                    if not IpType == 'None': boot_device.update({'ip_type':IpType})
                                    #==============================================
                                    # Prompt User for Interface Source
                                    #==============================================
                                    kwargs.jData = deepcopy(jsonVars.InterfaceSource)
                                    kwargs.jData.varType = 'Interface Source'
                                    InterfaceSource = ezfunctions.variablesFromAPI(**kwargs)
                                    if not InterfaceSource == 'name':
                                        boot_device.update({'interface_source':InterfaceSource})
                                if objectType == 'boot.Iscsi' or (objectType == 'boot.Pxe' and InterfaceSource == 'name'):
                                    #==============================================
                                    # Prompt User with LAN Connectivity Policies
                                    #==============================================
                                    kwargs.allow_opt_out = False
                                    kwargs.policy = 'policies.lan_connectivity.lan_connectivity_policy'
                                    kwargs = policy_select_loop(self, **kwargs)
                                    lan_connectivity_policy = kwargs.lan_connectivity_policy
                                    vnicNames = []
                                    for item in kwargs.imm_dict.orgs[org].policies.lan_connectivity:
                                        if item.name == lan_connectivity_policy:
                                            for i in item.vnics:
                                                vnicNames.append(i.names)
                                            vnicNames = [i for s in vnicNames for i in s]
                                            #==============================================
                                            # Prompt User to Select vNIC Name
                                            #==============================================
                                            kwargs.jData = DotMap()
                                            kwargs.jData.description = 'LAN Connectivity vNIC Names.'
                                            kwargs.jData.enum = sorted(vnicNames)
                                            kwargs.jData.varType = 'vNIC Names'
                                            vnicName = ezfunctions.variablesFromAPI(**kwargs)
                                            for i in item.vnics:
                                                if vnicName in i.names:
                                                    if i.get('placement_slot_ids'):
                                                        for x in range(len(i.names)):
                                                            if i.names[x] == vnicName:
                                                                if len(i.placement_slot_ids) == 2:
                                                                    Slot = i.placement_slot_ids[x]
                                                                else: i.placement_slot_ids[0]
                                                    else: Slot = 'MLOM'
                                    # Assign Interface Name and Slot
                                    boot_device.update({'interface_name':vnicName})
                                    if not Slot == 'MLOM': boot_device.update({'slot':Slot})
                                #==============================================
                                # Prompt User for MAC Address
                                #==============================================
                                if objectType == 'boot.Pxe' and InterfaceSource == 'mac':
                                    kwargs.jData = deepcopy(jsonVars.MacAddress)
                                    kwargs.jData.varInput = 'The MAC Address of the adapter on the underlying Virtual NIC:'
                                    kwargs.jData.varName  = 'Mac Address'
                                    boot_device.update({'mac_address':ezfunctions.varStringLoop(**kwargs)})
                                #==============================================
                                # Prompt User for Port ID
                                #==============================================
                                if objectType == 'boot.Iscsi' or (objectType == 'boot.Pxe' and InterfaceSource == 'port'):
                                    kwargs.jData = deepcopy(jsonVars.Port)
                                    if objectType == 'boot.Iscsi':
                                        kwargs.jData.varInput = 'What is The Port ID of the Adapter?\n'\
                                            'Supported values are 0 to 255:'
                                    else:
                                        kwargs.jData.varInput = 'What is The Port ID of the adapter on the underlying'\
                                            ' Virtual NIC?\nSupported values are -1 to 255:'
                                    kwargs.jData.varName  = 'Port'
                                    boot_device.update({'port':ezfunctions.varNumberLoop(**kwargs)})
                                if re.fullmatch('boot\.(PchStorage|San|SdCard)', objectType):
                                    #==============================================
                                    # Prompt User for LUN Id
                                    #==============================================
                                    kwargs.jData = deepcopy(jsonVars.Lun)
                                    kwargs.jData.varInput = 'LUN Identifier:'
                                    kwargs.jData.varName = 'LUN ID'
                                    boot_device.update({'lun':ezfunctions.varNumberLoop(**kwargs)})
                                if objectType == 'boot.San':
                                    #==============================================
                                    # Prompt User for SAN Connectivity Policy
                                    #==============================================
                                    kwargs.allow_opt_out = False
                                    kwargs.policy = 'policies.san_connectivity.san_connectivity_policy'
                                    kwargs = policy_select_loop(self, **kwargs)
                                    vnicNames = []
                                    for i in kwargs.imm_dict.orgs[org].policies.san_connectivity:
                                        if item.name == kwargs.san_connectivity_policy:
                                            for i in item.vhbas:
                                                vnicNames.append(i.names)
                                            vnicNames = [i for s in vnicNames for i in s]
                                            #==============================================
                                            # Prompt User for vHBA Name
                                            #==============================================
                                            scPolicy = kwargs.san_connectivity_policy
                                            kwargs.jData = DotMap()
                                            kwargs.jData.description = f'{scPolicy} : vHBA(s).'
                                            kwargs.jData.enum = sorted(vnicNames)
                                            kwargs.jData.varType = 'vHBA Names'
                                            vnicName = ezfunctions.variablesFromAPI(**kwargs)
                                            for i in item.vhbas:
                                                if vnicName in i.names:
                                                    if i.get('placement_slot_ids'):
                                                        for x in range(len(i.names)):
                                                            if i.names[x] == vnicName:
                                                                if len(i.placement_slot_ids) == 2:
                                                                    Slot = i.placement_slot_ids[x]
                                                                else: i.placement_slot_ids[0]
                                                    else: Slot = 'MLOM'
                                    # Assign Interface Name and Slot
                                    boot_device.update({'interface_name':vnicName})
                                    if not Slot == 'MLOM': boot_device.update({'slot':Slot})
                                    #==============================================
                                    # Prompt User for WWPN
                                    #==============================================
                                    kwargs.jData = deepcopy(jsonVars.Wwpn)
                                    kwargs.jData.varInput = 'WWPN of the Target Appliance:'
                                    kwargs.jData.varName = 'WWPN'
                                    boot_device.update({'target_wwpn':ezfunctions.varStringLoop(**kwargs)})
                                #==============================================
                                # SubType -> SdCard, Usb, VirtualMedia
                                #==============================================
                                if re.fullmatch('boot\.(SdCard|Usb|VirtualMedia)', objectType):
                                    kwargs.jData = deepcopy(jsonVars.Subtype)
                                    kwargs.jData.varType = 'Sub type'
                                    boot_device.update({'subtype':ezfunctions.variablesFromAPI(**kwargs)})
                                #==============================================
                                # Print Policy and Prompt User to Accept
                                #==============================================
                                print(f'\n{"-"*108}\n')
                                print(textwrap.indent(yaml.dump(boot_device, Dumper=yaml_dumper, default_flow_style=False
                                ), ' '*4, predicate=None))
                                print(f'{"-"*108}\n')
                                valid_confirm = False
                                while valid_confirm == False:
                                    confirm_config = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                                    pol_type = 'Boot Device'
                                    if confirm_config == 'Y' or confirm_config == '':
                                        polVars.boot_devices.append(boot_device)
                                        valid_exit = False
                                        while valid_exit == False:
                                            if inner_loop_count < 3:
                                                loop_exit, sub_loop = ezfunctions.exit_default(pol_type, 'Y')
                                            else: loop_exit, sub_loop = ezfunctions.exit_default(pol_type, 'N')
                                            if loop_exit == False: inner_loop_count += 1; valid_confirm = True; valid_exit = True
                                            elif loop_exit == True: valid_confirm = True; valid_sub = True; valid_exit = True
                                    elif confirm_config == 'N':
                                        ezfunctions.message_starting_over(pol_type)
                                        valid_confirm = True
                                    else: ezfunctions.message_invalid_y_or_n('short')
                        elif question == 'N': sub_loop = True
                        else: ezfunctions.message_invalid_y_or_n('short')
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,boot_order'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Certificate Management Policy Module
    #==============================================
    def certificate_management(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'cert'
        org            = self.org
        policy_type    = 'Certificate Management Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} Allows you to specify the certificate and private key-pair ')
            print(f'  details for an external certificate.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            loop_count = 1
            configure = input(f'Do You Want to Configure a {policy_type}.  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    jsonVars = jsonData.certificatemanagement.CertificateBase.allOf[1].properties
                    kwargs.multi_select = False
                    #==============================================
                    # Prompt User for Certificate
                    #==============================================
                    kwargs.multi_line_input = True
                    kwargs.description = jsonVars.Certificate.description
                    kwargs.Variable = f'base64_certificate_{loop_count}'
                    kwargs = ezfunctions.sensitive_var_value(jsonData, **kwargs)
                    polVars.certificate = loop_count
                    #==============================================
                    # Base64 Encode the Certificate
                    #==============================================
                    base64Cert = base64.b64encode(str.encode(kwargs.var_value)).decode()
                    print('base64 encoded:')
                    print(base64Cert)
                    TF_VAR = f'base64_certificate_{loop_count}'
                    os.environ[TF_VAR] = base64Cert
                    #==============================================
                    # Prompt User for Private Key
                    #==============================================
                    kwargs.multi_line_input = True
                    kwargs.description = jsonVars.Privatekey.description
                    kwargs.Variable = f'base64_private_key_{loop_count}'
                    kwargs = ezfunctions.sensitive_var_value(jsonData, **kwargs)
                    polVars.private_key = loop_count
                    #==============================================
                    # Base64 Encode the Private Key
                    #==============================================
                    base64Key = base64.b64encode(str.encode(kwargs.var_value)).decode()
                    print('base64 encoded:')
                    print(base64Key)
                    TF_VAR = f'base64_certificate_{loop_count}'
                    os.environ[TF_VAR] = base64Key
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,certificate_management'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            loop_count += 1
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Device Connector Policy Module
    #==============================================
    def device_connector(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'devcon'
        org            = self.org
        policy_type    = 'Device Connector Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} lets you choose the Configuration from Intersight only option to control ')
            print(f'  configuration changes allowed from Cisco IMC. The Configuration from Intersight only ')
            print(f'  option is enabled by default. You will observe the following changes when you deploy the ')
            print(f'  Device Connector policy in Intersight:')
            print(f'  * Validation tasks will fail:')
            print(f'    - If Intersight Read-only mode is enabled in the claimed device.')
            print(f'    - If the firmware version of the Standalone C-Series Servers is lower than 4.0(1).')
            print(f'  * If Intersight Read-only mode is enabled, firmware upgrades will be successful only when ')
            print(f'    performed from Intersight. Firmware upgrade performed locally from Cisco IMC will fail.')
            print(f'  * IPMI over LAN privileges will be reset to read-only level if Configuration from ')
            print(f'    Intersight only is enabled through the Device Connector policy, or if the same ')
            print(f'    configuration is enabled in the Device Connector in Cisco IMC.\n\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure a {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.deviceconnector.Policy.allOf[1].properties
                    #==============================================
                    # Prompt User for Configuration Lockout
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.LockoutEnabled)
                    kwargs.jData.default  = False
                    kwargs.jData.varInput = f'Do you want to lock down Configuration to Intersight only?'
                    kwargs.jData.varName  = 'Lockout Enabled'
                    polVars.configuration_lockout = ezfunctions.varBoolLoop(**kwargs)
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,device_connector'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Firmware - UCS Domain Module
    #==============================================
    def firmware_ucs_domain(self, **kwargs):
        polVars = {}
        polVars.header = 'UCS Domain Profile Variables'
        polVars.initial_write = True
        polVars.org = self.org
        polVars.policy_type = 'UCS Domain Profile'
        polVars.template_file = 'template_open.jinja2'
        polVars.template_type = 'ntp_policies'
        valid = False
        while valid == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'   UCS Version of Software to Deploy...')
            if os.path.isfile('ucs_version.txt'):
                version_file = open('ucs_version.txt', 'r')
                versions = []
                for line in version_file:
                    line = line.strip()
                    versions.append(line)
                for i, v in enumerate(versions):
                    i += 1
                    if i < 10:
                        print(f'     {i}. {v}')
                    else:
                        print(f'    {i}. {v}')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            ucs_version = input('Enter the Index Number for the Version of Software to Run: ')
            for i, v in enumerate(versions):
                i += 1
                if int(ucs_version) == i:
                    ucs_domain_version = v
                    valid = True
            if valid == False:
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(f'  Error!! Invalid Selection.  Please Select a valid Index from the List.')
                print(f'\n-------------------------------------------------------------------------------------------\n')
            version_file.close()

    #==============================================
    # IMC Access Policy Module
    #==============================================
    def imc_access(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'imc'
        org            = self.org
        policy_type    = 'IMC Access Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  You will need to configure an IMC Access Policy in order to Assign the VLAN and IPs to ')
            print(f'  the Servers for KVM Access.  At this time only inband access is supported in IMM mode.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            loop_count = 0
            policy_loop = False
            while policy_loop == False:
                #==============================================
                # Prompt User for Name and Description
                #==============================================
                polVars = {}
                if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                else: name = f'{name_suffix}'
                polVars.name        = ezfunctions.policy_name(name, policy_type)
                kwargs.name         = polVars.name
                polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                #==============================================
                # Get API Data
                #==============================================
                kwargs.multi_select == True
                jsonVars = jsonData.access.Policy.allOf[1].properties
                #==============================================
                # Prompt User for IMC Access Type(s)
                #==============================================
                kwargs.jData = deepcopy(jsonVars.ConfigurationType)
                kwargs.jData.default = 'inband'
                kwargs.jData.enum    = ['inband', 'out_of_band']
                kwargs.jData.varType = 'IMC Access Type'
                imcBand = ezfunctions.variablesFromAPI(**kwargs)
                kwargs.multi_select == False
                #==============================================
                # Loop through Inband and Out-of-Band
                #==============================================
                for i in imcBand:
                    kwargs.allow_opt_out = False
                    kwargs.optional_message = f'* Select the IP Pool for {i}'
                    kwargs.policy = f'pools.ip.{i}_ip_pool'
                    ptype = kwargs.policy.split('.')[2]
                    kwargs = policy_select_loop(self, **kwargs)
                    kwargs.pop('optional_message')
                    polVars[ptype] = kwargs[ptype]
                    if i == 'inband':
                        valid = False
                        while valid == False:
                            #==============================================
                            # Prompt User for Inband VLAN Id
                            #==============================================
                            kwargs.jData = DotMap()
                            kwargs.jData.default     = 4
                            kwargs.jData.description = 'Inband VLAN Identifier'
                            kwargs.jData.maximum     = 4094
                            kwargs.jData.minimum     = 4
                            kwargs.jData.varInput    = 'Enter the VLAN ID for the Inband VLAN.'
                            kwargs.jData.varName     = 'Inband VLAN ID'
                            inband_vlan_id = ezfunctions.varNumberLoop(**kwargs)
                            #==============================================
                            # Prompt User for VLAN Policy Source
                            #==============================================
                            kwargs.policy = f'policies.vlan.vlan_policy'
                            kwargs = policy_select_loop(self, **kwargs)
                            vlan_list = []
                            for item in kwargs.imm_dict.orgs[org].policies.vlan:
                                if item.name == kwargs.vlan_policy:
                                    for i in item.vlans:
                                        vlan_list.append(i.vlan_list)
                            vlan_convert = ''
                            for vlan in vlan_list:
                                vlan_convert = vlan_convert + ',' + str(vlan)
                            vlan_list = ezfunctions.vlan_list_full(vlan_convert)
                            valid = ezfunctions.validate_vlan_in_policy(vlan_list, inband_vlan_id)
                        polVars.inband_vlan_id = inband_vlan_id
                #==============================================
                # Prompt User to Enable IPv4
                #==============================================
                jsonVars = jsonData.access.AddressType.allOf[1].properties
                kwargs.jData = deepcopy(jsonVars.EnableIpV4)
                kwargs.jData.varInput = f'Do you want to enable IPv4 for this Policy?'
                kwargs.jData.varName  = 'Enable IPv4'
                polVars.ipv4_address_configuration = ezfunctions.varBoolLoop(**kwargs)
                #==============================================
                # Prompt User to Enable IPv6
                #==============================================
                kwargs.jData = deepcopy(jsonVars.EnableIpV6)
                kwargs.jData.varInput = f'Do you want to enable IPv6 for this Policy?'
                kwargs.jData.varName  = 'Enable IPv6'
                polVars.ipv6_address_configuration = ezfunctions.varBoolLoop(**kwargs)
                #==============================================
                # Print Policy and Prompt User to Accept
                #==============================================
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                print(f'-------------------------------------------------------------------------------------------\n')
                valid_confirm = False
                while valid_confirm == False:
                    confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                    if confirm_policy == 'Y' or confirm_policy == '':
                        #==============================================
                        # Add Policy Variables to imm_dict
                        #==============================================
                        kwargs.class_path = 'policies,imc_access'
                        kwargs = ezfunctions.ez_append(polVars, **kwargs)
                        #==============================================
                        # Create Additional Policy or Exit Loop
                        #==============================================
                        configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                        valid_confirm = True
                    elif confirm_policy == 'N':
                        ezfunctions.message_starting_over(policy_type)
                        valid_confirm = True
                    else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # IPMI over LAN Policy Module
    #==============================================
    def ipmi_over_lan(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'ipmi'
        org            = self.org
        policy_type    = 'IPMI over LAN Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  An {policy_type} will configure IPMI over LAN access on a Server Profile.  This policy')
            print(f'  allows you to determine whether IPMI commands can be sent directly to the server, using ')
            print(f'  the IP address.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure an {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.ipmioverlan.Policy.allOf[1].properties
                    #==============================================
                    # Prompt User for IPMI Encryption
                    #==============================================
                    kwargs.jData = DotMap()
                    kwargs.jData.default     = True
                    kwargs.jData.description = 'Encrypt IPMI over LAN.'
                    kwargs.jData.varInput    = f'Do you want to encrypt IPMI over LAN Traffic?'
                    kwargs.jData.varName     = 'Encrypt IPMI over LAN'
                    encrypt_traffic = ezfunctions.varBoolLoop(**kwargs)
                    if encrypt_traffic == True:
                        kwargs.Variable = 'ipmi_key'
                        kwargs = ezfunctions.sensitive_var_value(**kwargs)
                    #==============================================
                    # Prompt User for IPMI Priviledge
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.Privilege)
                    kwargs.jData.varType = 'IPMI Privilege'
                    polVars.privilege = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,ipmi_over_lan'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # LDAP Policy Module
    #==============================================
    def ldap(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        ezData         = kwargs.ezData
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'ldap'
        org            = self.org
        policy_type    = 'LDAP Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  An {policy_type} stores and maintains directory information in a network. When LDAP is ')
            print(f'  enabled in the Cisco IMC, user authentication and role authorization is performed by the ')
            print(f'  LDAP server for user accounts not found in the local user database. You can enable and ')
            print(f'  configure LDAP, and configure LDAP servers and LDAP groups.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure an {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                loop_count = 1
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    polVars.enable_ldap = True
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.iam.LdapBaseProperties.allOf[1].properties
                    #==============================================
                    # Prompt User for LDAP Base Domain Name
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.Domain)
                    kwargs.jData.default     = 'example.com'
                    kwargs.jData.description = 'The LDAP Base domain that all users must be in.'
                    kwargs.jData.minimum     = 1
                    kwargs.jData.varInput    = 'What is your LDAP Base Domain?'
                    kwargs.jData.varName     = 'LDAP Base Domain'
                    domain = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for LDAP Base DN
                    #==============================================
                    base_dn_var = 'DC=%s' % (',DC='.join(domain.split('.')))
                    kwargs.jData = deepcopy(jsonVars.BaseDn)
                    kwargs.jData.default  = base_dn_var
                    kwargs.jData.minimum  = 1
                    kwargs.jData.pattern  = '^[[dD][cC]\\=[a-zA-Z0-9\\-]+,]+[[dD][cC]\\=[a-zA-Z0-9\\-]+]$'
                    kwargs.jData.varInput = 'What is your Base Distinguished Name?'\
                        '  An example would be "dc=example,dc=com".'
                    kwargs.jData.varName  = 'LDAP Base DN'
                    base_dn = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for LDAP Timeout
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.Timeout)
                    kwargs.jData.varInput = 'What is the LDAP Authentication Timeout?  Range is 0 to 180.'
                    kwargs.jData.varName  = 'LDAP Timeout'
                    base_timeout = ezfunctions.varNumberLoop(**kwargs)
                    polVars.base_settings = {'base_dn':base_dn, 'domain':domain, 'timeout':base_timeout}
                    #==============================================
                    # Prompt User for LDAP Bind Method
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.BindMethod)
                    kwargs.jData.varType = 'LDAP Bind Method'
                    bind_method = ezfunctions.variablesFromAPI(**kwargs)

                    if bind_method == 'ConfiguredCredentials':
                        #==============================================
                        # Prompt User for LDAP Bind DN
                        #==============================================
                        kwargs.jData = DotMap()
                        kwargs.jData.description = 'Username for the LDAP Bind Distinguished Name.'
                        kwargs.jData.pattern     = '^[\\S]+$'
                        kwargs.jData.varInput    = 'What is the username you want to use for authentication?'
                        kwargs.jData.varName     = 'LDAP Bind Username'
                        varUser = ezfunctions.varStringLoop(**kwargs)
                        kwargs.jData.description = 'Organizational Unit for the LDAP Bind Distinguished Name.'
                        kwargs.jData.pattern     = '^[\\S]+$'
                        kwargs.jData.varInput    = f'What is the Organizational Unit for {varUser}?'
                        kwargs.jData.varName     = 'LDAP Bind Organizational Unit'
                        varOU = ezfunctions.varStringLoop(**kwargs)
                        varOU = input(f'What is the Organizational Unit for {varUser}? ')
                        kwargs.jData = deepcopy(jsonVars.BindDn)
                        kwargs.jData.default  = f'CN={varUser},OU={varOU},{base_dn}'
                        kwargs.jData.pattern  = f'^[cC][nN]\\=.*{base_dn}$'
                        kwargs.jData.varInput = 'What is your Bind Distinguished Name?'
                        kwargs.jData.varName  = 'LDAP Bind DN'
                        bind_dn = ezfunctions.varStringLoop(**kwargs)
                        #==============================================
                        # Prompt User for LDAP Binding Password
                        #==============================================
                        kwargs.Variable = 'binding_parameters_password'
                        kwargs = ezfunctions.sensitive_var_value(**kwargs)
                        polVars.binding_parameters = {'bind_dn':bind_dn, 'bind_method':bind_method}
                    else: polVars.binding_parameters = {'bind_method':bind_method}
                    #==============================================
                    # Prompt User for LDAP Encryption
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(f'  Secure LDAP is not supported but LDAP encryption is.')
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    kwargs.jData = deepcopy(jsonVars.EnableEncryption)
                    kwargs.jData.default  = True
                    kwargs.jData.varInput = f'Do you want to encrypt all information sent to the LDAP server(s)?'
                    kwargs.jData.varName  = 'LDAP Encryption'
                    polVars.enable_encryption = ezfunctions.varBoolLoop(**kwargs)
                    #==============================================
                    # Prompt User for Group Authorization
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.EnableGroupAuthorization)
                    kwargs.jData.default  = True
                    kwargs.jData.varInput = f'Do you want to enable Group Authorization?'
                    kwargs.jData.varName  = 'Group Authorization'
                    polVars.enable_group_authorization = ezfunctions.varBoolLoop(**kwargs)
                    #==============================================
                    # Prompt User for Nested Group Search Depth
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.NestedGroupSearchDepth)
                    kwargs.jData.default  = 128
                    kwargs.jData.varInput = 'What is the Search depth to look for a nested LDAP group in an'\
                        ' LDAP group map?  Range is 1 to 128.'
                    kwargs.jData.varName  = 'Nested Group Search Depth'
                    polVars.nested_group_search_depth = ezfunctions.varNumberLoop(**kwargs)
                    #==============================================
                    # Prompt User for LDAP Attribute
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(f'  An LDAP attribute that contains the role and locale information for the user. This ')
                    print(f'  property is always a name:value pair. The system queries the user record for the value ')
                    print(f'  that matches this attribute name.')
                    print(f'  The LDAP attribute can use an existing LDAP attribute that is mapped to the Cisco IMC user')
                    print(f'  roles and locales, or can modify the schema such that a new LDAP attribute can be created.')
                    print(f'  For example, CiscoAvPair.')
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    kwargs.jData = deepcopy(jsonVars.Attribute)
                    kwargs.jData.default  = 'CiscoAvPair'
                    kwargs.jData.varInput = 'What is the Attribute to use for the LDAP Search?'
                    kwargs.jData.varName  = 'Attribute'
                    varAttribute = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for LDAP Filter
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(f'  This field must match the configured attribute in the schema on the LDAP server.')
                    print(f'  By default, this field displays sAMAccountName.')
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    kwargs.jData = deepcopy(jsonVars.Filter)
                    kwargs.jData.default  = 'sAMAccountName'
                    kwargs.jData.varInput = 'What is the Filter to use for matching the username?'
                    kwargs.jData.varName  = 'Filter'
                    varFilter = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for LDAP Group Attribute
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(f'  This field must match the configured attribute in the schema on the LDAP server.')
                    print(f'  By default, this field displays memberOf.')
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    kwargs.jData = deepcopy(jsonVars.GroupAttribute)
                    kwargs.jData.default  = 'memberOf'
                    kwargs.jData.varInput = 'What is the Group Attribute to use for matching the Group Names?'
                    kwargs.jData.varName  = 'Group Attribute'
                    varGroupAttribute = ezfunctions.varStringLoop(**kwargs)
                    polVars.search_parameters = {
                        'attribute':varAttribute, 'filter':varFilter,
                        'group_attribute':varGroupAttribute
                    }
                    #================================================
                    # Prompt User for LDAP User Search Precedence
                    #================================================
                    jsonVars = jsonData.iam.LdapPolicy.allOf[1].properties
                    kwargs.jData = deepcopy(jsonVars.UserSearchPrecedence)
                    kwargs.jData.varType = 'User Search Precedence'
                    polVars.user_search_precedence = ezfunctions.variablesFromAPI(**kwargs)
                    #================================================
                    # Prompt User for LDAP Server Discovery from DNS
                    #================================================
                    kwargs.jData = deepcopy(jsonVars.EnableDns)
                    kwargs.jData.default     = False
                    kwargs.jData.description = 'This Section gives you the option to query DNS for LDAP Server'\
                        ' information isntead of defining the LDAP Servers.'
                    kwargs.jData.varInput    = f'Do you want to use DNS for LDAP Server discovery?'
                    kwargs.jData.varName     = 'DNS Server Discovery'
                    ldap_from_dns = ezfunctions.varBoolLoop(**kwargs)
                    if ldap_from_dns == True:
                        #================================================
                        # Prompt User for LDAP DNS Domain Source
                        #================================================
                        jsonVars = jsonData.iam.LdapDnsParameters.allOf[1].properties
                        polVars.varType = 'Domain Source'
                        varSource = ezfunctions.variablesFromAPI(**kwargs)
                        #================================================
                        # Prompt User for LDAP DNS Domain Source
                        #================================================
                        if not varSource == 'Extracted':
                            kwargs.jData = deepcopy(jsonVars.SearchDomain)
                            kwargs.jData.varInput = 'What is the Search Domain?'
                            kwargs.jData.varName  = 'Search Domain'
                            SearchDomain = ezfunctions.varStringLoop(**kwargs)
                            kwargs.jData = deepcopy(jsonVars.SearchForest)
                            kwargs.jData.varInput = 'What is the Search Forest?'
                            kwargs.jData.varName  = 'Search Forest'
                            SearchForest = ezfunctions.varStringLoop(**kwargs)
                            polVars.ldap_From_dns = {
                                'enable':True, 'search_domain':SearchDomain,
                                'search_forest':SearchForest, 'source':varSource
                            }
                        else: polVars.ldap_From_dns = {'enable':True, 'source':varSource}
                    #==============================================
                    # Prompt User for LDAP Groups
                    #==============================================
                    polVars.ldap_groups = []
                    inner_loop_count = 1
                    sub_loop = False
                    while sub_loop == False:
                        question = input(f'\nWould you like to configure LDAP Group(s)?  Enter "Y" or "N" [Y]: ')
                        if question == '' or question == 'Y':
                            valid_sub = False
                            while valid_sub == False:
                                jsonVars = jsonData.iam.LdapGroup.allOf[1].properties
                                #================================================
                                # Prompt User for LDAP Group Name
                                #================================================
                                kwargs.jData = deepcopy(jsonVars.Name)
                                kwargs.jData.varInput = 'What is the Group you would like to add from LDAP?'
                                kwargs.jData.varName  = 'LDAP Group'
                                varGroup = ezfunctions.varStringLoop(**kwargs)
                                #================================================
                                # Prompt User for LDAP Group Role
                                #================================================
                                jsonVars = ezData.ezimm.allOf[1].properties.policies.iam.LdapPolicy
                                kwargs.jData = deepcopy(jsonVars.role)
                                kwargs.jData.varType = 'Group Role'
                                role = ezfunctions.variablesFromAPI(**kwargs)
                                ldap_group = {'name':varGroup,'role':role}
                                #==============================================
                                # Print Policy and Prompt User to Accept
                                #==============================================
                                print(f'\n{"-"*108}\n')
                                print(textwrap.indent(yaml.dump(ldap_group, Dumper=yaml_dumper, default_flow_style=False
                                ), ' '*4, predicate=None))
                                print(f'{"-"*108}\n')
                                valid_confirm = False
                                while valid_confirm == False:
                                    confirm_config = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                                    if confirm_config == 'Y' or confirm_config == '':
                                        pol_type = 'LDAP Group'
                                        polVars.ldap_groups.append(ldap_group)
                                        #==============================================
                                        # Create Additional Policy or Exit Loop
                                        #==============================================
                                        valid_exit = False
                                        while valid_exit == False:
                                            loop_exit, sub_loop = ezfunctions.exit_default(pol_type, 'N')
                                            if loop_exit == False: inner_loop_count += 1; valid_confirm = True; valid_exit = True
                                            elif loop_exit == True: valid_confirm = True; valid_sub = True; valid_exit = True
                                    elif confirm_config == 'N':
                                        ezfunctions.message_starting_over(pol_type)
                                        valid_confirm = True
                                    else: ezfunctions.message_invalid_y_or_n('short')
                        elif question == 'N': sub_loop = True
                        else: ezfunctions.message_invalid_y_or_n('short')
                    #==============================================
                    # Prompt User for LDAP Providers/Servers
                    #==============================================
                    polVars.ldap_servers = []
                    inner_loop_count = 1
                    sub_loop = False
                    while sub_loop == False:
                        question = input(f'\nWould you like to configure LDAP Server(s)?  Enter "Y" or "N" [Y]: ')
                        if question == '' or question == 'Y':
                            valid_sub = False
                            while valid_sub == False:
                                jsonVars = jsonData.iam.LdapProvider.allOf[1].properties
                                #================================================
                                # Prompt User for LDAP Provider/Server
                                #================================================
                                kwargs.jData = deepcopy(jsonVars.Server)
                                kwargs.jData.pattern  = '^[\\S]+$'
                                kwargs.jData.varInput = 'What is the Hostname/IP of the LDAP Server?'
                                kwargs.jData.varName  = 'LDAP Server Address'
                                kwargs.jData.varType  = 'hostname'
                                varServer = ezfunctions.varStringLoop(**kwargs)
                                #================================================
                                # Prompt User for LDAP Provider Port
                                #================================================
                                if polVars.enable_encryption == True: xPort = 636
                                else: xPort = 389
                                kwargs.jData = deepcopy(jsonVars.Port)
                                kwargs.jData.default  = xPort
                                kwargs.jData.varInput = f'What is Port for {varServer}?'
                                kwargs.jData.varName  = 'LDAP Port'
                                varPort = ezfunctions.varNumberLoop(**kwargs)
                                ldap_server = {'port':varPort, 'server':varServer}
                                #==============================================
                                # Print Policy and Prompt User to Accept
                                #==============================================
                                print(f'\n{"-"*108}\n')
                                print(textwrap.indent(yaml.dump(ldap_server, Dumper=yaml_dumper, default_flow_style=False
                                ), ' '*4, predicate=None))
                                print(f'{"-"*108}\n')
                                valid_confirm = False
                                while valid_confirm == False:
                                    confirm_config = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                                    if confirm_config == 'Y' or confirm_config == '':
                                        polVars.ldap_servers.append(ldap_server)
                                        pol_type = 'LDAP Server'
                                        #==============================================
                                        # Create Additional Policy or Exit Loop
                                        #==============================================
                                        valid_exit = False
                                        while valid_exit == False:
                                            loop_exit, sub_loop = ezfunctions.exit_default(pol_type, 'N')
                                            if loop_exit == False: inner_loop_count += 1; valid_confirm = True; valid_exit = True
                                            elif loop_exit == True: valid_confirm = True; valid_sub = True; valid_exit = True
                                    elif confirm_config == 'N':
                                        ezfunctions.message_starting_over(pol_type)
                                        valid_confirm = True
                                    else: ezfunctions.message_invalid_y_or_n('short')
                        elif question == 'N': sub_loop = True
                        else: ezfunctions.message_invalid_y_or_n('short')
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,ldap'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Local User Policy Module
    #==============================================
    def local_user(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'users'
        org            = self.org
        policy_type    = 'Local User Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} will configure servers with Local Users for KVM Access.  This Policy ')
            print(f'  is not required to standup a server but is a good practice for day 2 support.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure a {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                loop_count = 1
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    polVars.password_properties = {}
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.iam.EndPointPasswordProperties.allOf[1].properties
                    #==============================================
                    # Prompt User for Always Send Password
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.ForceSendPassword)
                    kwargs.jData.varInput = f'Do you want Intersight to Always send the user password with policy updates?'
                    kwargs.jData.varName  = 'Force Send Password'
                    polVars.password_properties.always_send_user_password = ezfunctions.varBoolLoop(**kwargs)
                    #==============================================
                    # Prompt User for Enforce Strong Password
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.EnforceStrongPassword)
                    kwargs.jData.varInput = f'Do you want to Enforce Strong Passwords?'
                    kwargs.jData.varName  = 'Enforce Strong Password'
                    polVars.password_properties.enforce_strong_password = ezfunctions.varBoolLoop(**kwargs)
                    kwargs.enforce_strong_password = polVars.password_properties.enforce_strong_password
                    #==============================================
                    # Prompt User for Password Expiry
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.EnablePasswordExpiry)
                    kwargs.jData.default  = True
                    kwargs.jData.varInput = f'Do you want to Enable password Expiry on the Endpoint?'
                    kwargs.jData.varName  = 'Enable Password Expiry'
                    polVars.password_properties.enable_password_expiry = ezfunctions.varBoolLoop(**kwargs)

                    if polVars.password_properties.enable_password_expiry == True:
                        #==============================================
                        # Prompt User for Grace Period
                        #==============================================
                        kwargs.jData = deepcopy(jsonVars.GracePeriod)
                        kwargs.jData.description = 'Grace Period, in days, after the password is expired '\
                                'that a user can continue to use their expired password.'\
                                'The allowed grace period is between 0 to 5 days.  With 0 being no grace period.'
                        kwargs.jData.varInput = 'How many days would you like to set for the Grace Period?'
                        kwargs.jData.varName  = 'Grace Period'
                        polVars.password_properties.grace_period = ezfunctions.varNumberLoop(**kwargs)
                        #==============================================
                        # Prompt User for Notification Period
                        #==============================================
                        kwargs.jData = deepcopy(jsonVars.NotificationPeriod)
                        kwargs.jData.description = 'Notification Period - Number of days, between 0 to 15 '\
                                '(0 being disabled), that a user is notified to change their password before it expires.'
                        kwargs.jData.varInput = 'How many days would you like to set for the Notification Period?'
                        kwargs.jData.varName  = 'Notification Period'
                        polVars.password_properties.notification_period = ezfunctions.varNumberLoop(**kwargs)
                        #==============================================
                        # Prompt User for Password Expiry Duration
                        #==============================================
                        valid = False
                        while valid == False:
                            kwargs.jData = deepcopy(jsonVars.PasswordExpiryDuration)
                            kwargs.jData.description = 'Note: When Password Expiry is Enabled, Password Expiry '\
                                    'Duration sets the duration of time, (in days), a password may be valid.  '\
                                    'The password expiry duration must be greater than '\
                                    'notification period + grace period.  Range is 1-3650.'
                            kwargs.jData.varInput = 'How many days would you like to set for the Password Expiry Duration?'
                            kwargs.jData.varName  = 'Password Expiry Duration'
                            polVars.password_properties.password_expiry_duration = ezfunctions.varNumberLoop(**kwargs)
                            x = int(polVars.password_properties.grace_period)
                            y = int(polVars.password_properties.notification_period)
                            z = int(polVars.password_properties.password_expiry_duration)
                            if z > (x + y): valid = True
                            else:
                                print(f'\n-------------------------------------------------------------------------------------------\n')
                                print(f'  Error!! The Value of Password Expiry Duration must be greater than Grace Period +')
                                print(f'  Notification Period.  {z} is not greater than [{x} + {y}]')
                                print(f'\n-------------------------------------------------------------------------------------------\n')
                        #==============================================
                        # Prompt User for Password History
                        #==============================================
                        kwargs.jData = deepcopy(jsonVars.PasswordHistory)
                        kwargs.jData.default  = 0
                        kwargs.jData.varInput = 'How many passwords would you like to store for a user?  Range is 0 to 5.'
                        kwargs.jData.varName  = 'Password History'
                        polVars.password_properties.password_history = ezfunctions.varNumberLoop(**kwargs)
                    #==============================================
                    # Prompt User for Local Users
                    #==============================================
                    user_loop = False
                    while user_loop == False:
                        question = input(f'Would you like to configure Local user(s)?  Enter "Y" or "N" [Y]: ')
                        if question == '' or question == 'Y':
                            kwargs = ezfunctions.local_users_function(**kwargs)
                            polVars.local_users = kwargs.local_users
                            user_loop = True
                        elif question == 'N': user_loop = True
                        else: ezfunctions.message_invalid_y_or_n('short')
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,local_user'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Network Connectivity Policy Module
    #==============================================
    def network_connectivity(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'dns'
        org            = self.org
        policy_type    = 'Network Connectivity Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  It is strongly recommended to have a Network Connectivity (DNS) Policy for the')
            print(f'  UCS Domain Profile.  Without it, DNS resolution will fail.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            policy_loop = False
            while policy_loop == False:
                #==============================================
                # Prompt User for Name and Description
                #==============================================
                polVars = {}
                if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                else: name = f'{name_suffix}'
                polVars.name        = ezfunctions.policy_name(name, policy_type)
                polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                #==============================================
                # Get API Data
                #==============================================
                kwargs.multi_select = False
                jsonVars = jsonData.ippool.IpV4Config.allOf[1].properties
                polVars.dns_servers_v4 = []; polVars.dns_servers_v6 = []
                #==============================================
                # Prompt User for Primary DNS Server
                #==============================================
                kwargs.jData = deepcopy(jsonVars.PrimaryDns)
                kwargs.jData.default  = '208.67.220.220'
                kwargs.jData.varInput = f'IPv4 Primary DNS Server.'
                kwargs.jData.varName  = f'Primary DNS Server'
                polVars.dns_servers_v4.append(ezfunctions.varStringLoop(**kwargs))
                #==============================================
                # Prompt User for Secondary DNS Server
                #==============================================
                kwargs.jData = deepcopy(jsonVars.SecondaryDns)
                kwargs.jData.varInput = f'IPv4 Secondary DNS Server.  [press enter to skip]:'
                kwargs.jData.varName  = f'Secondary DNS Server'
                alternate_ipv4_dns_server = ezfunctions.varStringLoop(**kwargs)
                if not alternate_ipv4_dns_server == '':
                    polVars.dns_servers_v4.append(alternate_ipv4_dns_server)
                #==============================================
                # Prompt User for IPv6 DNS
                #==============================================
                kwargs.jData = DotMap()
                kwargs.jData.default     = False
                kwargs.jData.description = 'Enable IPv6 DNS Lookup.'
                kwargs.jData.varInput = f'Do you want to Configure IPv6 DNS?'
                kwargs.jData.varName  = 'IPv6 DNS'
                polVars.enable_ipv6 = ezfunctions.varBoolLoop(**kwargs)
                if polVars.enable_ipv6 == True:
                    jsonVars = jsonData.ippool.IpV6Config.allOf[1].properties
                    #==============================================
                    # Prompt User for Primary DNS Server
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SecondaryDns)
                    kwargs.jData.default  = '2620:119:53::53'
                    kwargs.jData.varInput = f'IPv6 Primary DNS Server.'
                    kwargs.jData.varName  = f'Primary DNS Server'
                    polVars.dns_servers_v6.append(ezfunctions.varStringLoop(**kwargs))
                    #==============================================
                    # Prompt User for Secondary DNS Server
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SecondaryDns)
                    kwargs.jData.varInput = f'IPv6 Secondary DNS Server.  [press enter to skip]:'
                    kwargs.jData.varName  = f'Secondary DNS Server'
                    alternate_ipv6_dns_server = ezfunctions.varStringLoop(**kwargs)
                    if not alternate_ipv6_dns_server == '': polVars.dns_server_v6.append(alternate_ipv6_dns_server)
                    else: polVars.dns_servers_v6.append('::')
                else: polVars.dns_servers_v6 = ['::', '::']
                #==============================================
                # Print Policy and Prompt User to Accept
                #==============================================
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                print(f'-------------------------------------------------------------------------------------------\n')
                valid_confirm = False
                while valid_confirm == False:
                    confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                    if confirm_policy == 'Y' or confirm_policy == '':
                        #==============================================
                        # Add Policy Variables to imm_dict
                        #==============================================
                        kwargs.class_path = 'policies,network_connectivity'
                        kwargs = ezfunctions.ez_append(polVars, **kwargs)
                        #==============================================
                        # Create Additional Policy or Exit Loop
                        #==============================================
                        configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                        valid_confirm = True
                    elif confirm_policy == 'N':
                        ezfunctions.message_starting_over(policy_type)
                        valid_confirm = True
                    else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # NTP Policy Module
    #==============================================
    def ntp(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'ntp'
        org            = self.org
        policy_type    = 'NTP Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  It is strongly recommended to configure an NTP Policy for the UCS Domain Profile.')
            print(f'  Without an NTP Policy Events can be incorrectly timestamped and Intersight ')
            print(f'  Communication, as an example, could be interrupted with Certificate Validation\n')
            print(f'  checks, as an example.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            policy_loop = False
            while policy_loop == False:
                #==============================================
                # Prompt User for Name and Description
                #==============================================
                polVars = {}
                if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                else: name = f'{name_suffix}'
                polVars.name        = ezfunctions.policy_name(name, policy_type)
                polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                #==============================================
                # Prompt User for NTP Servers
                #==============================================
                primary_ntp = ezfunctions.ntp_primary()
                alternate_ntp = ezfunctions.ntp_alternate()
                polVars.enabled = True
                polVars.ntp_servers = [primary_ntp]
                if not alternate_ntp == '': polVars.ntp_servers.append(alternate_ntp)
                #==============================================
                # Format TimeZone Data
                #==============================================
                kwargs.multi_select = False
                jsonVars = jsonData.appliance.SystemInfo.allOf[1].properties.TimeZone.enum
                tz_regions = []
                for i in jsonVars:
                    tz_region = i.split('/')[0]
                    if not tz_region in tz_regions: tz_regions.append(tz_region)
                tz_regions = sorted(tz_regions)
                #==============================================
                # Prompt User for Time Region
                #==============================================
                kwargs.jData = DotMap()
                kwargs.jData.default     = 'America'
                kwargs.jData.description = 'Timezone Regions...'
                kwargs.jData.enum        = tz_regions
                kwargs.jData.varType     = 'Time Region'
                time_region = ezfunctions.variablesFromAPI(**kwargs)
                #==============================================
                # Prompt User for Time Zone
                #==============================================
                region_tzs = []
                for item in jsonVars:
                    if time_region in item:
                        region_tzs.append(item)
                kwargs.jData = DotMap()
                kwargs.jData.description = 'Region Timezones...'
                kwargs.jData.enum        = sorted(region_tzs)
                kwargs.jData.varType     = 'Region Timezones'
                polVars.timezone = ezfunctions.variablesFromAPI(**kwargs)
                #==============================================
                # Print Policy and Prompt User to Accept
                #==============================================
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                print(f'-------------------------------------------------------------------------------------------\n')
                valid_confirm = False
                while valid_confirm == False:
                    confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                    if confirm_policy == 'Y' or confirm_policy == '':
                        #==============================================
                        # Add Policy Variables to imm_dict
                        #==============================================
                        kwargs.class_path = 'policies,ntp'
                        kwargs = ezfunctions.ez_append(polVars, **kwargs)
                        #==============================================
                        # Create Additional Policy or Exit Loop
                        #==============================================
                        configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                        valid_confirm = True
                    elif confirm_policy == 'N':
                        ezfunctions.message_starting_over(policy_type)
                        valid_confirm = True
                    else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Persistent Memory Policy Module
    #==============================================
    def persistent_memory(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'pmem'
        org            = self.org
        policy_type    = 'Persistent Memory Policy'
        yaml_file      = 'compute'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} allows the configuration of security, Goals, and ')
            print(f'  Namespaces of Persistent Memory Modules:')
            print(f'  - Goal - Used to configure volatile memory and regions in all the PMem Modules connected ')
            print(f'    to all the sockets of the server. Intersight supports only the creation and modification')
            print(f'    of a Goal as part of the Persistent Memory policy. Some data loss occurs when a Goal is')
            print(f'    modified during the creation or modification of a Persistent Memory Policy.')
            print(f'  - Namespaces - Used to partition a region mapped to a specific socket or a PMem Module on a')
            print(f'    socket.  Intersight supports only the creation and deletion of Namespaces as part of the ')
            print(f'    Persistent Memory Policy. Modifying a Namespace is not supported. Some data loss occurs ')
            print(f'    when a Namespace is created or deleted during the creation of a Persistent Memory policy.')
            print(f'    It is important to consider the memory performance guidelines and population rules of ')
            print(f'    the Persistent Memory Modules before they are installed or replaced, and the policy is ')
            print(f'    deployed. The population guidelines for the PMem Modules can be divided into the  ')
            print(f'    following categories, based on the number of CPU sockets:')
            print(f'    * Dual CPU for UCS B200 M6, C220 M6, C240 M6, and xC210 M6 servers')
            print(f'    * Dual CPU for UCS C220 M5, C240 M5, and B200 M5 servers')
            print(f'    * Dual CPU for UCS S3260 M5 servers')
            print(f'    * Quad CPU for UCS C480 M5 and B480 M5 servers')
            print(f'  - Security - Used to configure the secure passphrase for all the persistent memory modules.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure a {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.memory.PersistentMemoryPolicy.allOf[1].properties
                    #==============================================
                    # Prompt User for Management Mode
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.ManagementMode)
                    kwargs.jData.varType = 'Management Mode'
                    polVars.management_mode = ezfunctions.variablesFromAPI(**kwargs)

                    if polVars.management_mode == 'configured-from-intersight':
                        #==============================================
                        # Prompt User for Secure Passphrase
                        #==============================================
                        kwargs.jData = DotMap()
                        kwargs.jData.default     = True
                        kwargs.jData.description = 'A Secure passphrase will enable the protection of data on'\
                            ' the persistent memory modules.'
                        kwargs.jData.varInput = f'Do you want to enable a secure passphrase?'
                        kwargs.jData.varName  = 'Persistent Memory Secure Passphrase'
                        encrypt_memory = ezfunctions.varBoolLoop(**kwargs)
                        if encrypt_memory == True:
                            kwargs.Variable = 'secure_passphrase'
                            kwargs = ezfunctions.sensitive_var_value(**kwargs)
                        print(f'\n-------------------------------------------------------------------------------------------\n')
                        print(f'  The percentage of volatile memory required for goal creation.')
                        print(f'  The actual volatile and persistent memory size allocated to the region may differ with')
                        print(f'  the given percentage.')
                        print(f'\n-------------------------------------------------------------------------------------------\n')
                        #==============================================
                        # Prompt User for Memory Mode Percentage
                        #==============================================
                        jsonVars = jsonData.memory.PersistentMemoryGoal.allOf[1].properties
                        kwargs.jData = deepcopy(jsonVars.MemoryModePercentage)
                        kwargs.jData.default  = 0
                        kwargs.jData.varInput = 'What is the Percentage of Volatile Memory to assign to this Policy?'
                        kwargs.jData.varName  = 'Memory Mode Percentage'
                        polVars.memory_mode_percentage = ezfunctions.varNumberLoop(**kwargs)
                        #==============================================
                        # Prompt User for Persistent Memory Type
                        #==============================================
                        kwargs.jData = deepcopy(jsonVars.PersistentMemoryType)
                        kwargs.jData.varType = 'Persistent Memory Type'
                        polVars.persistent_memory_type = ezfunctions.variablesFromAPI(**kwargs)
                        jsonVars = jsonData.memory.PersistentMemoryPolicy.allOf[1].properties
                        #==============================================
                        # Prompt User for Namespace Retention
                        #==============================================
                        kwargs.jData = deepcopy(jsonVars.RetainNamespaces)
                        kwargs.jData.description = 'This Flag will enable or Disable the retention of Namespaces'\
                            ' between Server Profile association and dissassociation.'
                        kwargs.jData.varInput = f'Do you want to Retain Namespaces?'
                        kwargs.jData.varName  = 'Namespace Retention'
                        polVars.retain_namespaces = ezfunctions.varBoolLoop(**kwargs)
                        polVars.namespaces = []
                        print(f'\n-------------------------------------------------------------------------------------------\n')
                        print(f'  Namespace is a partition made in one or more Persistent Memory Regions. You can create a')
                        print(f'  namespace in Raw or Block mode.')
                        print(f'\n-------------------------------------------------------------------------------------------\n')
                        namespace_configure = input(f'Do You Want to Configure a namespace?  Enter "Y" or "N" [Y]: ')
                        if namespace_configure == 'Y' or namespace_configure == '':
                            sub_loop = False
                            while sub_loop == False:
                                #==============================================
                                # Prompt User for Logical Namespace Name
                                #==============================================
                                jsonVars = jsonData.memory.PersistentMemoryLogicalNamespace.allOf[1].properties
                                kwargs.jData = deepcopy(jsonVars.Name)
                                kwargs.jData.varInput = 'What is the Name for this Namespace?'
                                kwargs.jData.varName  = 'Logical Namespace Name'
                                namespace_name = ezfunctions.varStringLoop(**kwargs)
                                #==============================================
                                # Prompt User for Logical Namespace Capacity
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.Capacity)
                                kwargs.jData.default  = 1024
                                kwargs.jData.varInput = 'What is the Capacity to assign to this Namespace?'\
                                    '  Range is 1-9223372036854775807'
                                kwargs.jData.varName  = 'Logical Namespace Capacity'
                                capacity = ezfunctions.varNumberLoop(**kwargs)
                                #==============================================
                                # Prompt User for Logical Namespace Mode
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.Mode)
                                kwargs.jData.varType = 'Logical Namespace Mode'
                                mode = ezfunctions.variablesFromAPI(**kwargs)
                                #==============================================
                                # Prompt User for Logical Namespace Socket Id
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.SocketId)
                                kwargs.jData.varType = 'Logical Namespace Socket Id'
                                socket_id = ezfunctions.variablesFromAPI(**kwargs)
                                #====================================================
                                # Prompt User for Logical Namespace Socket Memory Id
                                #====================================================
                                if polVars.persistent_memory_type == 'app-direct-non-interleaved':
                                    kwargs.jData = deepcopy(jsonVars.SocketMemoryId)
                                    kwargs.jData.default = '2'
                                    kwargs.jData.enum.pop('Not Applicable')
                                    kwargs.jData.varType = 'Socket Memory Id'
                                    socket_memory_id = ezfunctions.variablesFromAPI(**kwargs)
                                else: socket_memory_id = 'Not Applicable'
                                namespace = {
                                    'capacity':capacity, 'mode':mode, 'name':namespace_name,
                                    'socket_id':socket_id, 'socket_memory_id':socket_memory_id
                                }
                                #==============================================
                                # Print Policy and Prompt User to Accept
                                #==============================================
                                print(f'\n{"-"*108}\n')
                                print(textwrap.indent(yaml.dump(namespace, Dumper=yaml_dumper, default_flow_style=False
                                ), ' '*4, predicate=None))
                                print(f'{"-"*108}\n')
                                valid_confirm = False
                                while valid_confirm == False:
                                    confirm_namespace = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                                    if confirm_namespace == 'Y' or confirm_namespace == '':
                                        pol_type = 'Namespace'
                                        polVars.namespaces.append(namespace)
                                        #==============================================
                                        # Create Additional Policy or Exit Loop
                                        #==============================================
                                        valid_exit = False
                                        while valid_exit == False:
                                            sub_exit, sub_loop = ezfunctions.exit_default(pol_type, 'N')
                                            if sub_exit == False: valid_confirm = True; valid_exit = True
                                            elif sub_exit == True: valid_confirm = True; valid_exit = True
                                    elif confirm_namespace == 'N':
                                        ezfunctions.message_starting_over(pol_type)
                                        valid_confirm = True
                                    else: ezfunctions.message_invalid_y_or_n('short')
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,persistent_memory'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Port Policy Module
    #==============================================
    def port(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        org            = self.org
        policy_type    = 'Port Policy'
        yaml_file      = 'port'
        while configure_loop == False:
            port_type_list = [
                'Appliance Port-Channels:port_channel_appliances',
                'Appliance Ports:port_role_appliances',
                'Ethernet Uplink Port-Channels:port_channel_ethernet_uplinks',
                'Ethernet Uplinks:port_role_ethernet_uplinks',
                'FCoE Uplink Port-Channels:port_channel_fcoe_uplinks',
                'FCoE Uplinks:port_role_fcoe_uplinks',
                'FC Storage:port_role_fc_storage',
                'FC Uplink Port-Channels:port_channel_fc_uplinks',
                'FC Uplinks:port_role_fc_uplinks',
                'Server Ports:port_role_servers',
            ]
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} is used to configure the ports for a UCS Domain Profile.  This includes:')
            print(f'   - Unified Ports - Ports to convert to Fibre-Channel Mode.')
            for i in port_type_list:
                print(f'   - {i.split(":")[0]}')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            policy_loop = False
            while policy_loop == False:
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(f'   NOTE: The wizard will create a Port Policy for Fabric A and Fabric B')
                print(f'\n-------------------------------------------------------------------------------------------\n')
                #==============================================
                # Prompt User for Domain Profile
                #==============================================
                kwargs.name = 'Port Policy'
                kwargs.allow_opt_out = False
                kwargs.policy = 'profiles.domain.domain_profile'
                kwargs = policy_select_loop(self, **kwargs)
                name = kwargs.domain_profile
                polVars = {}
                polVars.names = [f'{name}-a', f'{name}-b']
                polVars.description = ezfunctions.policy_descr(name, policy_type)
                kwargs.name_prefix = self.name_prefix
                kwargs.name = name
                #==============================================
                # Get API Data
                #==============================================
                kwargs.multi_select = False
                jsonVars = jsonData.fabric.PortPolicy.allOf[1].properties
                #==============================================
                # Prompt User for FI Device Model
                #==============================================
                kwargs.jData = deepcopy(jsonVars.DeviceModel)
                kwargs.jData.varType = 'Device Model'
                polVars.device_model = ezfunctions.variablesFromAPI(**kwargs)
                kwargs.device_model = polVars.device_model
                #==============================================
                # Prompt User for Fibre-Channel Configuration
                #==============================================
                kwargs = port_modes(**kwargs)
                #==============================================
                # Prompt User for Appliance Port-Channel(s)
                #==============================================
                for i in port_type_list:
                    kwargs.portDict = []
                    kwargs.port_type = i.split(':')[0]
                    if 'fc' in i.split(':')[1]:
                        if len(kwargs.fc_converted_ports) > 0: kwargs = port_list_fc(self, **kwargs)
                    else: kwargs = port_list_eth(self, **kwargs)
                    kwargs[i.split(':')[1]] = deepcopy(kwargs.portDict)
                #==============================================
                # Build Port Policy Dictionary
                #==============================================
                port_type = ['port_channel', 'port_role']
                port_type_list = ['appliances', 'ethernet_uplinks', 'fcoe_uplinks']
                for item in port_type:
                    for i in port_type_list:
                        if len(kwargs[f'{item}_{i}']) > 0:
                            polVars.update({f'{item}_{i}': deepcopy(kwargs[f'{item}_{i}'])})
                if len(kwargs.port_role_servers) > 0:
                    polVars.update({'port_role_servers': deepcopy(kwargs.port_role_servers)})
                if len(kwargs.fc_converted_ports) > 0:
                    if len(kwargs.port_modes) > 0:
                        polVars.update({'port_modes': kwargs.port_modes})
                    if len(kwargs.port_channel_fc_uplinks) > 0:
                        polVars.update({'port_channel_fc_uplinks': deepcopy(kwargs.port_channel_fc_uplinks)})
                    port_type_list = ['fc_storage', 'fc_uplinks']
                    for i in port_type_list:
                        if len(kwargs[f'port_role_{i}']) > 0:
                            polVars.update({f'port_role_{i}': deepcopy(kwargs[f'port_role_{i}'])})
                #==============================================
                # Print Policy and Prompt User to Accept
                #==============================================
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                print(f'-------------------------------------------------------------------------------------------\n')
                valid_confirm = False
                while valid_confirm == False:
                    confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                    if confirm_policy == 'Y' or confirm_policy == '':
                        #==============================================
                        # Add Policy Variables to imm_dict
                        #==============================================
                        kwargs.class_path = 'policies,port'
                        kwargs = ezfunctions.ez_append(polVars, **kwargs)
                        #==============================================
                        # Create Additional Policy or Exit Loop
                        #==============================================
                        configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                        valid_confirm = True
                    elif confirm_policy == 'N':
                        ezfunctions.message_starting_over(policy_type)
                        valid_confirm = True
                    else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Power Policy Module
    #==============================================
    def power(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        ezData         = kwargs.ezData
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        org            = self.org
        policy_type    = 'Power Policy'
        yaml_file      = 'environment'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} will configure the Power Redundancy Policies for Chassis and Servers.')
            print(f'  For Servers it will configure the Power Restore State.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            loop_count = 1
            policy_loop = False
            while policy_loop == False:
                #==============================================
                # Get API Data
                #==============================================
                polVars = {}
                kwargs.multi_select = False
                jsonVars = ezData.ezimm.allOf[1].properties.policies.power.Policy
                #==============================================
                # Prompt User for System Type
                #==============================================
                kwargs.jData = deepcopy(jsonVars.systemType)
                kwargs.jData.varType = 'System Type'
                system_type = ezfunctions.variablesFromAPI(**kwargs)
                #==============================================
                # Prompt User for Name and Description
                #==============================================
                if not name_prefix == '': name = '%s-%s' % (name_prefix, system_type)
                else: name = system_type
                polVars.name        = ezfunctions.policy_name(name, policy_type)
                polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)

                jsonVars = jsonData.power.Policy.allOf[1].properties
                if system_type == '9508':
                    #==============================================
                    # Prompt User for Power Allocation
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.AllocatedBudget)
                    kwargs.jData.default  = 8400
                    kwargs.jData.maximum  = 16800
                    kwargs.jData.minimum  = 2800
                    kwargs.jData.varInput = 'What is the Power Budget you would like to Apply?\n'\
                        '  This should be a value between 2800 Watts and 16800 Watts.'
                    kwargs.jData.varName  = 'Power Allocation'
                    polVars.power_allocation = ezfunctions.varNumberLoop(**kwargs)
                    #==============================================
                    # Prompt User for Dynamic Rebalancing
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.DynamicRebalancing)
                    kwargs.jData.varType = 'Dynamic Power Rebalancing'
                    polVars.dynamic_power_rebalancing = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for Power Save Mode
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.PowerSaveMode)
                    kwargs.jData.varType = 'Power Save Mode'
                    polVars.power_save_mode = ezfunctions.variablesFromAPI(**kwargs)
                if system_type == 'Server':
                    #==============================================
                    # Prompt User for Power Priority
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.PowerPriority)
                    kwargs.jData.varType = 'Power Priority'
                    polVars.power_priority = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for Power Profiling
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.PowerProfiling)
                    kwargs.jData.varType = 'Power Profiling'
                    polVars.power_profiling = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for Power Restore
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.PowerRestoreState)
                    kwargs.jData.default = 'LastState'
                    kwargs.jData.varType = 'Power Restore'
                    polVars.power_restore = ezfunctions.variablesFromAPI(**kwargs)
                #==============================================
                # Prompt User for Power Redundancy Mode
                #==============================================
                kwargs.jData = deepcopy(jsonVars.RedundancyMode)
                if system_type == '5108': kwargs.jData.popList = ['N+2']
                elif system_type == 'Server': kwargs.jData.popList = ['N+1','N+2']
                kwargs.jData.varType = 'Power Redundancy Mode'
                polVars.power_redundancy = ezfunctions.variablesFromAPI(**kwargs)
                #==============================================
                # Print Policy and Prompt User to Accept
                #==============================================
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                print(f'-------------------------------------------------------------------------------------------\n')
                valid_confirm = False
                while valid_confirm == False:
                    confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                    if confirm_policy == 'Y' or confirm_policy == '':
                        #==============================================
                        # Add Policy Variables to imm_dict
                        #==============================================
                        kwargs.class_path = 'policies,power'
                        kwargs = ezfunctions.ez_append(polVars, **kwargs)
                        #==============================================
                        # Create Additional Policy or Exit Loop
                        #==============================================
                        if loop_count < 3:
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'Y')
                        else: configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                        loop_count += 1
                        valid_confirm = True
                    elif confirm_policy == 'N':
                        ezfunctions.message_starting_over(policy_type)
                        valid_confirm = True
                    else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # SD Card Policy Module
    #==============================================
    def sd_card(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        ezData         = kwargs.ezData
        name_prefix    = self.name_prefix
        name_suffix    = 'sdcard'
        org            = self.org
        policy_type    = 'SD Card Policy'
        yaml_file      = 'storage'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  SD Card Policy')
            print(f'  * When two cards are present in the Cisco FlexFlash controller and the Operating System is \n')
            print(f'    chosen in the SD card policy, the configured OS partition is mirrored. If only a single\n')
            print(f'    card is available in the Cisco FlexFlash controller, the configured OS partition is \n')
            print(f'    non-RAID. The utility partitions are always set as non-RAID.\n')
            print(f'  * IMPORTANT NOTES:\n')
            print(f'    - This policy is currently not supported on M6 servers.\n')
            print(f'    - You can enable up to two utility virtual drives on M5 servers, and any number of\n')
            print(f'      supported utility virtual drives on M4 servers.\n')
            print(f'    - Diagnostics is supported only for the M5 servers.\n')
            print(f'    - UserPartition drives can be renamed only on the M4 servers.\n')
            print(f'    - FlexFlash configuration is not supported on C460 M4 servers.\n')
            print(f'    - For the Operating System+Utility mode, the M4 servers require two FlexFlash cards, and\n')
            print(f'      the M5 servers require at least 1 FlexFlash + 1 FlexUtil card.\n')
            print(f'  storage capacity of a virtual drive, and configure the M.2 RAID controllers.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            #==============================================
            # Get API Data
            #==============================================
            kwargs.multi_select = False
            #==============================================
            # Prompt for Generation of UCS Servers
            #==============================================
            jsonVars = ezData.ezimm.allOf[1].properties.policies.server.Generation
            kwargs.jData = deepcopy(jsonVars.systemType)
            kwargs.jData.varType = 'Generation of UCS Server'
            ucs_generation = ezfunctions.variablesFromAPI(**kwargs)
            if re.search('M(4|5)', ucs_generation):
                configure = input(f'Do You Want to Configure a {policy_type}?  Enter "Y" or "N" [Y]: ')
            else: configure == 'N'
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    pcount = 0
                    #==============================================
                    # Enable Operating System Partition
                    #==============================================
                    kwargs.jData = DotMap()
                    kwargs.jData.default     = True
                    kwargs.jData.description = 'Flag to Enable the Operating System Partition.'
                    kwargs.jData.varInput    = f'Do you want to enable the Operating System Partition?'
                    kwargs.jData.varName     = 'Operating System Partition'
                    polVars.enable_os = ezfunctions.varBoolLoop(**kwargs)
                    if polVars.enable_os == True: pcount += 1
                    #==============================================
                    # Enable Host Upgrade Utility (HUU) Partition
                    #==============================================
                    kwargs.jData = DotMap()
                    kwargs.jData.default     = False
                    kwargs.jData.description = 'Flag to Enable the Host Upgrade Utility (HUU) Partition.'
                    kwargs.jData.varInput    = f'Do you want to enable the Host Upgrade Utility (HUU) Partition?'
                    kwargs.jData.varName     = 'HUU Partition'
                    polVars.enable_huu = ezfunctions.varBoolLoop(**kwargs)
                    if polVars.enable_huu == True: pcount += 1
                    #==============================================
                    # Enable Drivers Utility Partition
                    #==============================================
                    if ucs_generation == 'M5' and pcount > 1: skip = True
                    else: skip = False
                    if skip == False:
                        kwargs.jData = DotMap()
                        kwargs.jData.default     = False
                        kwargs.jData.description = 'Flag to Enable the Drivers Utility Partition.'
                        kwargs.jData.varInput    = f'Do you want to enable the Drivers Utility Partition?'
                        kwargs.jData.varName     = 'Drivers Utility Partition'
                        polVars.enable_drivers = ezfunctions.varBoolLoop(**kwargs)
                        if polVars.enable_drivers == True: pcount += 1
                    #==============================================
                    # Prompt User to Enable Diagnostics Partition
                    #==============================================
                    if ucs_generation == 'M5' and pcount < 2:
                        kwargs.jData = DotMap()
                        kwargs.jData.default     = False
                        kwargs.jData.description = 'Flag to Enable the Diagnostics Utility Partition.'
                        kwargs.jData.varInput    = f'Do you want to enable the Diagnostics Utility Partition?'
                        kwargs.jData.varName     = 'Diagnostics Partition'
                        polVars.enable_diagnostics = ezfunctions.varBoolLoop(**kwargs)
                    #=====================================================
                    # Enable Server Configuration Utility (SCU) Partition
                    #=====================================================
                    if ucs_generation == 'M5' and pcount > 1: skip = True
                    else: skip = False
                    if skip == False:
                        kwargs.jData = DotMap()
                        kwargs.jData.default     = False
                        kwargs.jData.description = 'Flag to Enable the Server Configuration Utility (SCU) Partition.'
                        kwargs.jData.varInput    = f'Do you want to enable the Server Configuration Utility (SCU) Partition?'
                        kwargs.jData.varName     = 'SCU Partition'
                        polVars.enable_drivers = ezfunctions.varBoolLoop(**kwargs)
                        if polVars.enable_drivers == True: pcount += 1
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,sd_card'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Serial over LAN Policy Module
    #==============================================
    def serial_over_lan(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'sol'
        org            = self.org
        policy_type    = 'Serial over LAN Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} will configure the Server to allow access to the Communications Port over')
            print(f'  Ethernet.  Settings include:')
            print(f'   - Baud Rate')
            print(f'   - COM Port')
            print(f'   - SSH Port\n')
            print(f'  This Policy is not required to standup a server but is a good practice for day 2 support.')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure a {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.sol.Policy.allOf[1].properties
                    #==============================================
                    # Prompt User for Baud Rate
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.BaudRate)
                    kwargs.jData.default = 115200
                    kwargs.jData.varType = 'Baud Rate'
                    polVars.baud_rate = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for Com Port
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.ComPort)
                    kwargs.jData.varType = 'Com Port'
                    polVars.com_port = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for SSH Port
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SshPort)
                    kwargs.jData.varInput = 'What is the SSH Port you would like to assign?  Range is 1024-65535.'
                    kwargs.jData.varName  = 'SSH Port'
                    polVars.ssh_port = ezfunctions.varNumberLoop(**kwargs)
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,serial_over_lan'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('short')
        # Return kwargs
        return kwargs

    #==============================================
    # SMTP Policy Module
    #==============================================
    def smtp(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'smtp'
        org            = self.org
        policy_type    = 'SMTP Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  An {policy_type} sends server faults as email alerts to the configured SMTP server.')
            print(f'  You can specify the preferred settings for outgoing communication and select the fault ')
            print(f'  severity level to report and the mail recipients.\n\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure an {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.smtp.Policy.allOf[1].properties
                    #==============================================
                    # Prompt User for SMTP Server
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SmtpServer)
                    kwargs.jData.pattern  = '^\\S$'
                    kwargs.jData.varInput = 'What is the SMTP Server Address?'
                    kwargs.jData.varName  = 'SMTP Server Address'
                    kwargs.jData.varType  = 'hostname'
                    polVars.smtp_server_address = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for SMTP Port
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SmtpPort)
                    kwargs.jData.varInput = 'What is the SMTP Port?  Range is 1-65535.'
                    kwargs.jData.varName  = 'SMTP Port'
                    polVars.smtp_port = ezfunctions.varNumberLoop(**kwargs)
                    #==============================================
                    # Prompt User for Minimum Severity
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.MinSeverity)
                    kwargs.jData.varType = 'Minimum Severity'
                    polVars.minimum_severity = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for Sender Email Address
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SenderEmail)
                    kwargs.jData.varInput = 'What is the SMTP Alert Sender Address?'
                    kwargs.jData.varName  = 'Sender Email'
                    polVars.smtp_alert_sender_address = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for SMTP Recipients
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SmtpRecipients.items)
                    kwargs.jData.varInput = 'Enter the List of comma seperated Email Addresses to Recieve Alerts?'
                    kwargs.jData.varName  = 'SMTP Recipients'
                    kwargs.jData.varType  = 'list'
                    polVars.mail_alert_recipients = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,smtp'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # SNMP Policy Module
    #==============================================
    def snmp(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'snmp'
        org            = self.org
        policy_type    = 'SNMP Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  An {policy_type} will configure chassis, domains, and servers with SNMP parameters.')
            print(f'  This Policy is not required to standup a server but is a good practice for day 2 support.')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure an {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                loop_count = 1
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.snmp.Policy.allOf[1].properties
                    #==============================================
                    # Prompt User for SNMP Port
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SnmpPort)
                    kwargs.jData.varInput = 'Enter the Port to Assign to this SNMP Policy.'
                    kwargs.jData.varName  = 'SNMP Port'
                    kwargs.jData.varType  = 'SnmpPort'
                    polVars.port = ezfunctions.varNumberLoop(**kwargs)
                    #==============================================
                    # Prompt User for SNMP Contact
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SysContact)
                    kwargs.jData.pattern  = '.*'
                    kwargs.jData.varInput = 'SNMP System Contact:'
                    kwargs.jData.varName  = 'System Contact'
                    polVars.system_contact = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for SNMP Location
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.SysLocation)
                    kwargs.jData.pattern  = '.*'
                    kwargs.jData.varInput = 'What is the SNMP Location?'
                    kwargs.jData.varName  = 'System Location'
                    polVars.system_location = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for SNMP Access Community String
                    #==============================================
                    polVars.access_community_string = ''
                    kwargs.jData = DotMap()
                    kwargs.jData.default     = False
                    kwargs.jData.description = 'Configure SNMP Community Access'
                    kwargs.jData.varInput    = f'Would you like to configure an SNMP Access Community String?'
                    kwargs.jData.varName     = 'SNMP Community Access'
                    configure_snmp_access = ezfunctions.varBoolLoop(**kwargs)
                    if configure_snmp_access == True:
                        kwargs.Variable = f'access_community_string_{loop_count}'
                        kwargs = ezfunctions.sensitive_var_value(jsonData, **kwargs)
                        polVars.access_community_string = loop_count
                    if not polVars.access_community_string == '':
                        polVars.description = jsonVars.CommunityAccess.description
                        polVars.jsonVars = sorted(jsonVars.CommunityAccess.enum)
                        polVars.defaultVar = jsonVars.CommunityAccess.default
                        polVars.varType    = 'Community Access'
                        polVars.community_access = ezfunctions.variablesFromAPI(**kwargs)
                    else: polVars.pop('access_community_string')
                    #==============================================
                    # Prompt User for SNMP Trap Community String
                    #==============================================
                    polVars.trap_community_string = ''
                    kwargs.jData = DotMap()
                    kwargs.jData.default     = False
                    kwargs.jData.description = 'Configure SNMP Trap Community String'
                    kwargs.jData.varInput    = f'Would you like to configure an SNMP Trap Community String?'
                    kwargs.jData.varName     = 'SNMP Trap Community String'
                    configure_trap_community_string = ezfunctions.varBoolLoop(**kwargs)
                    if configure_trap_community_string == True:
                        kwargs.Variable = f'trap_community_string_{loop_count}'
                        kwargs = ezfunctions.sensitive_var_value(jsonData, **kwargs)
                        polVars[f'trap_community_string = loop_count']
                    if polVars.trap_community_string == '': polVars.pop('trap_community_string')
                    #==============================================
                    # Prompt User for SNMP Engine Identifier
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.EngineId)
                    kwargs.jData.default     = False
                    kwargs.jData.description = jsonVars.EngineId.description + \
                        '\nNote: By default this is derived from the BMC serial number.'
                    kwargs.jData.varInput    = f'Would you like to configure a Unique string to identify the device'\
                        ' for administration purposes?'
                    kwargs.jData.varName     = 'SNMP Trap Community String'
                    configure_snmp_engine_id = ezfunctions.varBoolLoop(**kwargs)
                    if configure_snmp_engine_id == True:
                        kwargs.jData = deepcopy(jsonVars.EngineId)
                        kwargs.jData.minimum  = 1
                        kwargs.jData.varInput = 'What is the SNMP Engine Id?'
                        kwargs.jData.varName  = 'SNMP Engine Id'
                        polVars.snmp_engine_input_id = ezfunctions.varStringLoop(**kwargs)
                    #==============================================
                    # Prompt User for SNMP Users
                    #==============================================
                    kwargs.jData = DotMap()
                    kwargs.jData.default     = True
                    kwargs.jData.description = 'Configure SNMP Users'
                    kwargs.jData.varInput    = f'Would you like to configure SNMPv3 User(s)?'
                    kwargs.jData.varName     = 'SNMP Users'
                    configure_snmp_users = ezfunctions.varBoolLoop(**kwargs)
                    if configure_snmp_users == True:
                        kwargs = ezfunctions.snmp_users(**kwargs)
                        polVars.snmp_users = kwargs.snmp_users
                    #==============================================
                    # Prompt User for SNMP Trap Destinations
                    #==============================================
                    kwargs.jData = DotMap()
                    kwargs.jData.default     = True
                    kwargs.jData.description = 'Configure SNMP Trap Destinations'
                    kwargs.jData.varInput    = f'Would you like to configure SNMP Trap Destination(s)?'
                    kwargs.jData.varName     = 'SNMP Trap Destinations'
                    configure_snmp_traps = ezfunctions.varBoolLoop(**kwargs)
                    if configure_snmp_traps == True:
                        kwargs = ezfunctions.snmp_trap_servers(**kwargs)
                        polVars.snmp_traps = kwargs.snmp_traps
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,snmp'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # SSH Policy Module
    #==============================================
    def ssh(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'ssh'
        org            = self.org
        policy_type    = 'SSH Policy'
        yaml_file      = 'storage'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  An {policy_type} enables an SSH client to make a secure, encrypted connection. You can ')
            print(f'  create one or more SSH policies that contain a specific grouping of SSH properties for a ')
            print(f'  server or a set of servers.\n\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure an {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.ssh.Policy.allOf[1].properties
                    #==============================================
                    # Prompt User for SSH Port
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.Port)
                    kwargs.jData.varInput    = 'What is the SSH Port?'
                    kwargs.jData.varName     = 'SSH Port'
                    polVars.ssh_port = ezfunctions.varNumberLoop(**kwargs)
                    #==============================================
                    # Prompt User for SSH Timeout
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.Timeout)
                    kwargs.jData.varInput    = 'What value do you want to set for the SSH Timeout?'
                    kwargs.jData.varName     = 'SSH Timeout'
                    polVars.ssh_timeout = ezfunctions.varNumberLoop(**kwargs)
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,ssh'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #========================================
    # Storage Policy Module
    #========================================
    def storage(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'storage'
        org            = self.org
        policy_type    = 'Storage Policy'
        yaml_file      = 'storage'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} allows you to create drive groups, virtual drives, configure the ')
            print(f'  storage capacity of a virtual drive, and configure the M.2 RAID controllers.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure a {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                loop_count = 1
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.storage.StoragePolicy.allOf[1].properties
                    #==============================================
                    # Prompt User for Global Hot Spares
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.GlobalHotSpares)
                    kwargs.jData.maximum  = 128
                    kwargs.jData.varInput = 'Specify the disks that are to be used as hot spares, globally,'\
                        ' for all the Drive Groups. \n[press enter to skip]:'
                    kwargs.jData.varName = 'Global Hot Spares'
                    polVars.global_hot_spares = ezfunctions.varStringLoop(**kwargs)
                    if polVars.global_hot_spares == '': polVars.pop('global_hot_spares')
                    #==============================================
                    # Prompt User for Unused Disks State
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.UnusedDisksState)
                    kwargs.jData.varType = 'Unused Disks State'
                    polVars.unused_disks_state = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for Using JBODs for VD Creation
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.UseJbodForVdCreation)
                    kwargs.jData.default  = False
                    kwargs.jData.varInput = f'Do you want to Use JBOD drives for Virtual Drive creation?'
                    kwargs.jData.varName  = 'Use Jbod For Vd Creation'
                    polVars.use_jbod_for_vd_creation = ezfunctions.varBoolLoop(**kwargs)
                    #==============================================
                    # Prompt User to Configure Virtual Drives
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.GlobalHotSpares)
                    kwargs.jData.default = False
                    kwargs.jData.description = 'Drive Group Configuration - Enable to add RAID drive groups that'\
                        ' can be used to create virtual drives.  You can also specify the Global Hot Spares information.'
                    kwargs.jData.varInput = f'Do you want to Configure Drive Groups?'
                    kwargs.jData.varName = 'Drive Groups'
                    driveGroups = ezfunctions.varBoolLoop(**kwargs)
                    # If True configure Drive Groups
                    if driveGroups == True:
                        polVars.drive_groups = []
                        inner_loop_count = 1
                        drive_group = []
                        drive_group_loop = False
                        while drive_group_loop == False:
                            drive_group = {'manual_drive_group':[]}
                            mdg = {}
                            jsonVars = jsonData.storage.DriveGroup.allOf[1].properties
                            #==============================================
                            # Prompt User for Drive Group Name
                            #==============================================
                            kwargs.jData = deepcopy(jsonVars.Name)
                            kwargs.jData.default = f'dg{inner_loop_count - 1}'
                            kwargs.jData.varInput = f'Enter the Drive Group Name.'
                            kwargs.jData.varName = 'Drive Group Name'
                            drive_group.name = ezfunctions.varStringLoop(**kwargs)
                            #==============================================
                            # Prompt User for Drive Group Raid Level
                            #==============================================
                            kwargs.jData = deepcopy(jsonVars.RaidLevel)
                            kwargs.jData.default = 'Raid1'
                            kwargs.jData.varType = 'Raid Level'
                            RaidLevel = ezfunctions.variablesFromAPI(**kwargs)
                            drive_group.raid_level = RaidLevel
                            # If Raid Level is anything other than Raid0 ask for Hot Spares
                            if not RaidLevel == 'Raid0':
                                #==============================================
                                # Prompt User for Dedicated Hot Spares
                                #==============================================
                                jsonVars = jsonData.storage.ManualDriveGroup.allOf[1].properties
                                kwargs.jData = deepcopy(jsonVars.DedicatedHotSpares)
                                kwargs.jData.varInput = 'Enter the Drives to add as Dedicated Hot Spares '\
                                    '[press enter to skip]:'
                                kwargs.jData.varName = 'Dedicated Hot Spares'
                                mdg.dedicated_hot_spares = ezfunctions.varStringLoop(**kwargs)
                                if mdg.dedicated_hot_spares == '': mdg.pop('dedicated_hot_spares')
                            # Configure Span Slots
                            SpanSlots = []
                            # If Raid is 10, 50 or 60 allow multiple Span Slots
                            if re.fullmatch('^Raid(10|50|60)$', RaidLevel):
                                #==============================================
                                # Prompt User for Drive Group Span Groups
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.SpanGroups)
                                kwargs.jData.default     = 2
                                kwargs.jData.description = jsonVars.SpanGroups.items.description
                                kwargs.jData.enum        = [2, 4, 6, 8]
                                kwargs.jData.varType     = 'Span Groups'
                                SpanGroups = ezfunctions.variablesFromAPI(**kwargs)
                                if SpanGroups == 2: SpanGroups = [0, 1]
                                elif SpanGroups == 4: SpanGroups = [0, 1, 2, 3]
                                elif SpanGroups == 6: SpanGroups = [0, 1, 2, 3, 4, 5]
                                elif SpanGroups == 8: SpanGroups = [0, 1, 2, 3, 4, 5, 6, 7]
                                for span in SpanGroups:
                                    #==============================================
                                    # Prompt User for Span Group Drive Slots
                                    #==============================================
                                    jsonVars = jsonData.storage.SpanDrives.allOf[1].properties
                                    kwargs.jData = deepcopy(jsonVars.Slots)
                                    if re.fullmatch('^Raid10$', RaidLevel):
                                        kwargs.jData.default = f'{(inner_loop_count * 2) - 1}-{(inner_loop_count * 2)}'
                                    elif re.fullmatch('^Raid50$', RaidLevel):
                                        kwargs.jData.default = f'{(inner_loop_count * 3) - 2}-{(inner_loop_count * 3)}'
                                    elif re.fullmatch('^Raid60$', RaidLevel):
                                        kwargs.jData.default = f'{(inner_loop_count * 4) - 3}-{(inner_loop_count * 4)}'
                                    kwargs.jData.varInput = f'Enter the Drive Slots for Drive Array Span {span}.'
                                    kwargs.jData.varName = 'Drive Slots'
                                    SpanSlots.append({'slots':ezfunctions.varStringLoop(**kwargs)})
                            elif re.fullmatch('^Raid(0|1|5|6)$', RaidLevel):
                                #==============================================
                                # Prompt User for Span Group Drive Slots
                                #==============================================
                                jsonVars = jsonData.storage.SpanDrives.allOf[1].properties
                                kwargs.jData = deepcopy(jsonVars.Slots)
                                if re.fullmatch('^Raid(0|1)$', RaidLevel):
                                    kwargs.jData.default = f'{(inner_loop_count * 2) - 1}-{(inner_loop_count * 2)}'
                                elif re.fullmatch('^Raid5$', RaidLevel):
                                    kwargs.jData.default = f'{(inner_loop_count * 3) - 2}-{(inner_loop_count * 3)}'
                                elif re.fullmatch('^Raid6$', RaidLevel):
                                    kwargs.jData.default = f'{(inner_loop_count * 4) - 3}-{(inner_loop_count * 4)}'
                                kwargs.jData.varInput = f'Enter the Drive Slots for Drive Array Span 0.'
                                kwargs.jData.varName = 'Drive Slots'
                                SpanSlots.append({'slots':ezfunctions.varStringLoop(**kwargs)})
                            mdg.drive_array_spans = SpanSlots
                            drive_group.manual_drive_group.append(mdg)
                            virtualDrives = []
                            sub_loop_count = 0
                            sub_loop = False
                            while sub_loop == False:
                                jsonVars = jsonData.storage.VirtualDriveConfiguration.allOf[1].properties
                                #==============================================
                                # Prompt User for Virtual Drive Name
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.Name)
                                kwargs.jData.default  = f'vd{sub_loop_count}'
                                kwargs.jData.minimum  = 1
                                kwargs.jData.varInput = 'Enter the name of the Virtual Drive.'
                                kwargs.jData.varName  = 'Virtual Drive Name'
                                vdrive = {'name':ezfunctions.varStringLoop(**kwargs)}
                                vd_name = vdrive.name
                                #==============================================
                                # Prompt User for Expand to Available
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.ExpandToAvailable)
                                kwargs.jData.default = True
                                kwargs.jData.varInput = f'Do you want to expand to all the space available'\
                                    ' in the Virtual Drive?'
                                kwargs.jData.varName = 'Expand To Available'
                                vdrive.expand_to_available = ezfunctions.varBoolLoop(**kwargs)
                                # If Expand to Available is Disabled obtain Virtual Drive disk size
                                if vdrive.expand_to_available == False:
                                    #==============================================
                                    # Prompt User for Virtual Drive Size
                                    #==============================================
                                    kwargs.jData = deepcopy(jsonVars.Size)
                                    kwargs.jData.default =  240
                                    kwargs.jData.minimum = 64
                                    kwargs.jData.maximum = 9999999999
                                    kwargs.jData.varInput = 'What is the Size for this Virtual Drive?'
                                    kwargs.jData.varName = 'Size'
                                    vdrive.size = ezfunctions.varNumberLoop(**kwargs)
                                #==============================================
                                # Determine if it is a Boot Drive
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.BootDrive)
                                kwargs.jData.default = True
                                kwargs.jData.varInput = f'Do you want to configure {vd_name} as a boot drive?'
                                kwargs.jData.varName = 'Boot Drive'
                                vdrive.boot_drive = ezfunctions.varBoolLoop(**kwargs)
                                #==============================================
                                # Prompt User for Virtual Drive Policies
                                #==============================================
                                jsonVars = jsonData.storage.VirtualDrivePolicy.allOf[1].properties
                                vd_policies = ['Access.Policy', 'Drive.Cache', 'Read.Policy', 'Strip.Size', 'Write.Policy']
                                for i in vd_policies:
                                    ptype = i.replace('.', '')
                                    vtype = i.replace('.', ' ')
                                    vdpolicy = i.replace('.', '_').lower()
                                    kwargs.jData = deepcopy(jsonVars[f'{ptype}'])
                                    kwargs.jData.varType = f'{vtype}'
                                    vdrive[vdpolicy] = ezfunctions.variablesFromAPI(**kwargs)
                                    if vdrive[vdpolicy] == 'Default': vdrive.pop(vdpolicy)
                                    elif vdrive[vdpolicy] == 64: vdrive.pop(vdpolicy)
                                #==============================================
                                # Print Policy and Prompt User to Accept
                                #==============================================
                                print(f'\n{"-"*108}\n')
                                print(textwrap.indent(yaml.dump(vdrive, Dumper=yaml_dumper, default_flow_style=False
                                ), " "*4, predicate=None))
                                print(f'{"-"*108}\n')
                                pol_type = 'Virtual Drive Configuration'
                                valid_confirm = False
                                while valid_confirm == False:
                                    confirm_v = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                                    if confirm_v == 'Y' or confirm_v == '':
                                        virtualDrives.append(vdrive)
                                        #==============================================
                                        # Create Additional Policy or Exit Loop
                                        #==============================================
                                        valid_exit = False
                                        while valid_exit == False:
                                            loop_exit, sub_loop = ezfunctions.exit_default(pol_type, 'N')
                                            if loop_exit == False: inner_loop_count += 1; valid_confirm = True; valid_exit = True
                                            elif loop_exit == True: valid_confirm = True; valid_exit = True
                                    elif confirm_v == 'N':
                                        ezfunctions.message_starting_over(pol_type)
                                        valid_confirm = True
                                    else: ezfunctions.message_invalid_y_or_n('short')
                            drive_group.update({'virtual_drives':virtualDrives})
                            #==============================================
                            # Print Policy and Prompt User to Accept
                            #==============================================
                            print(f'\n{"-"*108}\n')
                            print(textwrap.indent(yaml.dump(drive_group, Dumper=yaml_dumper, default_flow_style=False
                            ), " "*4, predicate=None))
                            print(f'{"-"*108}\n')
                            pol_type = 'Drive Group Configuration'
                            valid_confirm = False
                            while valid_confirm == False:
                                confirm_v = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                                if confirm_v == 'Y' or confirm_v == '':
                                    polVars.drive_groups.append(drive_group)
                                    #==============================================
                                    # Create Additional Policy or Exit Loop
                                    #==============================================
                                    valid_exit = False
                                    while valid_exit == False:
                                        loop_exit, drive_group_loop = ezfunctions.exit_default(pol_type, 'N')
                                        if loop_exit == False: inner_loop_count += 1; valid_confirm = True; valid_exit = True
                                        elif loop_exit == True: valid_confirm = True; valid_exit = True
                                elif confirm_v == 'N':
                                    ezfunctions.message_starting_over(pol_type)
                                    valid_confirm = True
                                else: ezfunctions.message_invalid_y_or_n('short')
                    #==============================================
                    # Prompt User for M2 Virtual Drive
                    #==============================================
                    jsonVars = jsonData.storage.StoragePolicy.allOf[1].properties
                    kwargs.jData = deepcopy(jsonVars.M2VirtualDrive)
                    if polVars.get('drive_groups'): kwargs.jData.default = False
                    else: kwargs.jData.default = True
                    kwargs.jData.varInput = f'Do you want to Enable the M.2 Virtual Drive Configuration?'
                    kwargs.jData.varName = 'M.2 Virtual Drive'
                    M2VirtualDrive = ezfunctions.varBoolLoop(**kwargs)
                    if M2VirtualDrive == True:
                        jsonVars = jsonData.storage.M2VirtualDriveConfig.allOf[1].properties
                        #==============================================
                        # Prompt User for Controller Slot
                        #==============================================
                        kwargs.jData = deepcopy(jsonVars.ControllerSlot)
                        kwargs.jData.default = 'MSTOR-RAID-1'
                        kwargs.jData.varType = 'Controller Slot'
                        ControllerSlot = ezfunctions.variablesFromAPI(**kwargs)
                        polVars.m2_configuration = [{'controller_slot':ControllerSlot, 'enable':True}]
                    #==============================================
                    # Prompt User for Single Drive Raid Config
                    #==============================================
                    kwargs.jData = DotMap()
                    kwargs.jData.default = False
                    kwargs.jData.description = 'Enable to create RAID0 virtual drives on each physical drive..'
                    kwargs.jData.varInput = f"Do you want to Configure Single Drive RAID's?"
                    kwargs.jData.varName = 'Single Drive RAID'
                    singledriveRaid = ezfunctions.varBoolLoop(**kwargs)
                    if singledriveRaid == True:
                        single_drive_loop = False
                        while single_drive_loop == False:
                            #==============================================
                            # Prompt User for Single Drive Raid Slots
                            #==============================================
                            jsonVars = jsonData.storage.R0Drive.allOf[1].properties
                            kwargs.jData = deepcopy(jsonVars.DriveSlots)
                            kwargs.jData.default = f'1-2'
                            kwargs.jData.varInput = f'Enter the Drive Slots for Drive Array Span 0.'
                            kwargs.jData.varName = 'Drive Slots'
                            DriveSlots = ezfunctions.varStringLoop(**kwargs)
                            # Obtain the Virtual Drive Policies
                            jsonVars = jsonData.storage.VirtualDrivePolicy.allOf[1].properties
                            #==============================================
                            # Prompt User for Virtual Drive Policies
                            #==============================================
                            vd_policies = ['Access.Policy', 'Drive.Cache', 'Read.Policy', 'Strip.Size', 'Write.Policy']
                            sdrc = {}
                            for i in vd_policies:
                                ptype = i.replace('.', '')
                                vtype = i.replace('.', ' ')
                                vdpolicy = i.replace('.', '_').lower()
                                kwargs.jData = deepcopy(jsonVars[ptype])
                                kwargs.jData.varType = f'{vtype}'
                                sdrc[vdpolicy] = ezfunctions.variablesFromAPI(**kwargs)
                                if sdrc[vdpolicy] == 'Default': sdrc.pop(vdpolicy)
                                elif sdrc[vdpolicy] == 64: sdrc.pop(vdpolicy)
                            polVars.single_drive_raid_configuration = sdrc
                            polVars.single_drive_raid_configuration.update({'slots':DriveSlots})
                            #==============================================
                            # Print Policy and Prompt User to Accept
                            #==============================================
                            print(f'\n{"-"*108}\n')
                            print(textwrap.indent(yaml.dump(polVars.single_drive_raid_configuration, Dumper=yaml_dumper, default_flow_style=False), " "*4, predicate=None))
                            print(f'{"-"*108}\n')
                            valid_confirm = False
                            while valid_confirm == False:
                                confirm_v = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                                if confirm_v == 'Y' or confirm_v == '':
                                    single_drive_loop = True
                                    valid_confirm = True
                                    valid_exit = True
                                elif confirm_v == 'N':
                                    pol_type = 'Single Drive RAID Configuration'
                                    ezfunctions.message_starting_over(pol_type)
                                    valid_confirm = True
                                else: ezfunctions.message_invalid_y_or_n('short')
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,storage'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Syslog Policy Module
    #==============================================
    def syslog(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'syslog'
        org            = self.org
        policy_type    = 'Syslog Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} will configure domain and servers with remote syslog servers.')
            print(f'  You can configure up to two Remote Syslog Servers.')
            print(f'  This Policy is not required to standup a server but is a good practice for day 2 support.')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            configure = input(f'Do You Want to Configure a {policy_type}?  Enter "Y" or "N" [Y]: ')
            if configure == 'Y' or configure == '':
                policy_loop = False
                while policy_loop == False:
                    #==============================================
                    # Prompt User for Name and Description
                    #==============================================
                    polVars = {}
                    if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                    else: name = f'{name_suffix}'
                    polVars.name        = ezfunctions.policy_name(name, policy_type)
                    polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                    #==============================================
                    # Get API Data
                    #==============================================
                    kwargs.multi_select = False
                    jsonVars = jsonData.syslog.LocalClientBase.allOf[1].properties
                    #==============================================
                    # Prompt User for Local Minimum Severity
                    #==============================================
                    kwargs.jData = deepcopy(jsonVars.MinSeverity)
                    kwargs.jData.varType = 'Syslog Local Minimum Severity'
                    polVars.local_min_severity = ezfunctions.variablesFromAPI(**kwargs)
                    #==============================================
                    # Prompt User for Syslog Servers
                    #==============================================
                    kwargs = ezfunctions.syslog_servers(**kwargs)
                    polVars.remote_logging = kwargs.remote_logging
                    #==============================================
                    # Print Policy and Prompt User to Accept
                    #==============================================
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                        if confirm_policy == 'Y' or confirm_policy == '':
                            #==============================================
                            # Add Policy Variables to imm_dict
                            #==============================================
                            kwargs.class_path = 'policies,syslog'
                            kwargs = ezfunctions.ez_append(polVars, **kwargs)
                            #==============================================
                            # Create Additional Policy or Exit Loop
                            #==============================================
                            configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                            valid_confirm = True
                        elif confirm_policy == 'N':
                            ezfunctions.message_starting_over(policy_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif configure == 'N': configure_loop = True
            else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Thermal Policy Module
    #==============================================
    def thermal(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        ezData         = kwargs.ezData
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        org            = self.org
        policy_type    = 'Thermal Policy'
        yaml_file      = 'environment'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} will configure the Cooling/FAN Policy for Chassis.  We recommend ')
            print(f'  Balanced for a 5108 and Acoustic for a 9508 Chassis, as of this writing.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            policy_loop = False
            while policy_loop == False:
                polVars = {}
                #==============================================
                # Get API Data
                #==============================================
                kwargs.multi_select = False
                jsonVars = ezData.ezimm.allOf[1].properties.policies.thermal.Policy
                #==============================================
                # Prompt User for Chassis Type
                #==============================================
                kwargs.jData = deepcopy(jsonVars.chassisType)
                kwargs.jData.varType = 'Chassis Type'
                chassis_type = ezfunctions.variablesFromAPI(**kwargs)
                #==============================================
                # Prompt User for Name and Description
                #==============================================
                if not name_prefix == '': name = '%s-%s' % (name_prefix, chassis_type)
                else: name = chassis_type
                polVars.name        = ezfunctions.policy_name(name, policy_type)
                polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                #==============================================
                # Prompt User for Fan Control Mode
                #==============================================
                jsonVars = jsonData.thermal.Policy.allOf[1].properties
                kwargs.jData = deepcopy(jsonVars.FanControlMode)
                if chassis_type == '5108':
                    kwargs.jData.popList = ['Acoustic', 'HighPower', 'MaximumPower']
                kwargs.jData.varType = 'Fan Control Mode'
                polVars.fan_control_mode = ezfunctions.variablesFromAPI(**kwargs)
                #==============================================
                # Print Policy and Prompt User to Accept
                #==============================================
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                print(f'-------------------------------------------------------------------------------------------\n')
                valid_confirm = False
                while valid_confirm == False:
                    confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                    if confirm_policy == 'Y' or confirm_policy == '':
                        #==============================================
                        # Add Policy Variables to imm_dict
                        #==============================================
                        kwargs.class_path = 'policies,thermal'
                        kwargs = ezfunctions.ez_append(polVars, **kwargs)
                        #==============================================
                        # Create Additional Policy or Exit Loop
                        #==============================================
                        configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                        valid_confirm = True
                    elif confirm_policy == 'N':
                        ezfunctions.message_starting_over(policy_type)
                        valid_confirm = True
                    else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Provider and Variables Module
    #==============================================
    def variables(self, **kwargs):
        baseRepo      = kwargs.args.dir
        ezData        = kwargs.ezData
        policy_type   = 'variables'
        polVars = {}
        polVars.endpoint = kwargs.args.endpoint
        polVars.tags = [
            {'key': "Module", 'value': "terraform-intersight-easy-imm"},
            {'key': "Version", 'value': f"{ezData.version}"}
        ]
        # Write Policies to Template File
        kwargs.template_file = '%s.j2' % (policy_type)
        kwargs.dest_file = f'{policy_type}.auto.tfvars'
        ezfunctions.write_to_repo_folder(polVars, **kwargs)

        policy_type = 'provider'
        polVars = {
            'intersight_provider_version': kwargs.latest_versions.intersight_provider_version,
            'terraform_version': kwargs.latest_versions.terraform_version,
            'utils_provider_version': kwargs.latest_versions.utils_provider_version
        }
        # Write Policies to Template File
        kwargs.template_file = '%s.j2' % (policy_type)
        kwargs.dest_file = f'{policy_type}.tf'
        ezfunctions.write_to_repo_folder(polVars, **kwargs)
        ezfunctions.terraform_fmt(os.path.join(baseRepo))

    #==============================================
    # Virtual KVM Policy Module
    #==============================================
    def virtual_kvm(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'vkvm'
        org            = self.org
        policy_type    = 'Virtual KVM Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} will configure the Server for KVM access.  Settings include:')
            print(f'   - Local Server Video - If enabled, displays KVM on any monitor attached to the server.')
            print(f'   - Video Encryption - encrypts all video information sent through KVM.')
            print(f'   - Remote Port - The port used for KVM communication. Range is 1 to 65535.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            policy_loop = False
            while policy_loop == False:
                #==============================================
                # Prompt User for Name and Description
                #==============================================
                polVars = {}
                if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                else: name = f'{name_suffix}'
                polVars.name        = ezfunctions.policy_name(name, policy_type)
                polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                #==============================================
                # Get API Data
                #==============================================
                kwargs.multi_select = False
                jsonVars = jsonData.kvm.Policy.allOf[1].properties
                #==============================================
                # Prompt User for Tunneled KVM
                #==============================================
                kwargs.jData = deepcopy(jsonVars.TunneledKvmEnabled)
                kwargs.jData.default = False
                kwargs.jData.description = jsonVars.TunneledKvmEnabled.description + \
                    '\n* Note: Make sure to Enable Virtual Tunneled KVM Launch and Configuration under:'\
                    '\n  Setttings > Settings > Security & Privacy.'
                kwargs.jData.varInput = f'Do you want to allow Tunneled vKVM?'
                kwargs.jData.varName  = 'Allow Tunneled vKVM'
                polVars.allow_tunneled_vkvm = ezfunctions.varBoolLoop(**kwargs)
                #==============================================
                # Prompt User for Enable Local Server Video
                #==============================================
                kwargs.jData = deepcopy(jsonVars.EnableLocalServerVideo)
                kwargs.jData.default  = True
                kwargs.jData.varInput = f'Do you want to Display KVM on Monitors attached to the Server?'
                kwargs.jData.varName  = 'Enable Local Server Video'
                polVars.enable_local_server_video = ezfunctions.varBoolLoop(**kwargs)
                polVars.enable_video_encryption = True
                #==============================================
                # Prompt User for Port to Use for vKVM
                #==============================================
                kwargs.jData = deepcopy(jsonVars.RemotePort)
                kwargs.jData.varInput = 'What is the Port you would like to Assign for Remote Access?'\
                    '  This should be a value between 1024-65535.'
                kwargs.jData.varName = 'Remote Port'
                kwargs.jData.minimum = 1024
                polVars.remote_port = ezfunctions.varNumberLoop(**kwargs)
                #==============================================
                # Print Policy and Prompt User to Accept
                #==============================================
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                print(f'-------------------------------------------------------------------------------------------\n')
                valid_confirm = False
                while valid_confirm == False:
                    confirm_policy = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                    if confirm_policy == 'Y' or confirm_policy == '':
                        #==============================================
                        # Add Policy Variables to imm_dict
                        #==============================================
                        kwargs.class_path = 'policies,virtual_kvm'
                        kwargs = ezfunctions.ez_append(polVars, **kwargs)
                        #==============================================
                        # Create Additional Policy or Exit Loop
                        #==============================================
                        configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                        valid_confirm = True
                    elif confirm_policy == 'N':
                        ezfunctions.message_starting_over(policy_type)
                        valid_confirm = True
                    else: ezfunctions.message_invalid_y_or_n('long')
        # Return kwargs
        return kwargs

    #==============================================
    # Virtual Media Policy Policy Module
    #==============================================
    def virtual_media(self, **kwargs):
        baseRepo       = kwargs.args.dir
        configure_loop = False
        ezData         = kwargs.ezData
        jsonData       = kwargs.jsonData
        name_prefix    = self.name_prefix
        name_suffix    = 'vmedia'
        org            = self.org
        policy_type    = 'Virtual Media Policy'
        yaml_file      = 'management'
        while configure_loop == False:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  A {policy_type} enables you to install an operating system on the server using the ')
            print(f'  KVM console and virtual media, mount files to the host from a remote file share, and ')
            print(f'  enable virtual media encryption. You can create one or more virtual media policies, which ')
            print(f'  could contain virtual media mappings for different OS images, and configure up to two ')
            print(f'  virtual media mappings, one for ISO files through CDD and the other for IMG files ')
            print(f'  through HDD.\n')
            print(f'  This wizard will save the configuration for this section to the following file:')
            print(f'  - {os.path.join(baseRepo, org, self.type, yaml_file)}.yaml')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            loop_count = 1
            policy_loop = False
            while policy_loop == False:
                #==============================================
                # Prompt User for Name and Description
                #==============================================
                polVars = {}
                if not name_prefix == '': name = f'{name_prefix}-{name_suffix}'
                else: name = f'{name_suffix}'
                polVars.name        = ezfunctions.policy_name(name, policy_type)
                polVars.description = ezfunctions.policy_descr(polVars.name, policy_type)
                #==============================================
                # Get API Data
                #==============================================
                kwargs.multi_select = False
                jsonVars = jsonData.vmedia.Policy.allOf[1].properties
                #==============================================
                # Prompt User for Low Power USB
                #==============================================
                kwargs.jData = deepcopy(jsonVars.LowPowerUsb)
                kwargs.jData.default  = True
                kwargs.jData.varInput = 'Do you want to Enable Low Power USB?'
                kwargs.jData.varName  = 'Low Power USB'
                polVars.enable_low_power_usb = ezfunctions.varBoolLoop(**kwargs)
                polVars.enable_virtual_media_encryption = True
                #==============================================
                # Prompt User for Virtual Media Mappings
                #==============================================
                polVars.add_virtual_media = []
                inner_loop_count = 1
                sub_loop = False
                while sub_loop == False:
                    kwargs.jData = deepcopy(jsonVars.Mappings.items)
                    kwargs.jData.default  = True
                    kwargs.jData.varInput = 'Would you like to add vMedia Mappings for images?'
                    kwargs.jData.varName  = 'vMedia Mappings'
                    question = ezfunctions.varBoolLoop(**kwargs)
                    if question == True:
                        valid_sub = False
                        while valid_sub == False:
                            jsonVars = jsonData.vmedia.Mapping.allOf[1].properties
                            #==============================================
                            # Prompt User for vMedia Mount Protocol
                            #==============================================
                            kwargs.jData = deepcopy(jsonVars.MountProtocol)
                            kwargs.jData.varType = 'vMedia Mount Protocol'
                            Protocol = ezfunctions.variablesFromAPI(**kwargs)
                            #==============================================
                            # Prompt User for vMedia Mount Name
                            #==============================================
                            kwargs.jData = deepcopy(jsonVars.VolumeName)
                            kwargs.jData.default = f'{Protocol}-map'
                            kwargs.jData.varInput = 'What is the Name for the Virtual Media Mount?'
                            kwargs.jData.varType  = 'vMedia Name'
                            vName = ezfunctions.varStringLoop(**kwargs)
                            #==============================================
                            # Prompt User for vMedia Device Type
                            #==============================================
                            kwargs.jData = deepcopy(jsonVars.DeviceType)
                            kwargs.jData.varType = 'vMedia Device Type'
                            deviceType = ezfunctions.variablesFromAPI(**kwargs)
                            if Protocol == 'cifs':
                                #==============================================
                                # Prompt User for vMedia Device Type
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.AuthenticationProtocol)
                                kwargs.jData.varType = 'CIFS Authentication Protocol'
                                authProtocol = ezfunctions.variablesFromAPI(**kwargs)
                            #==============================================
                            # Prompt User for Remote File Location
                            #==============================================
                            valid = False
                            while valid == False:
                                kwargs.jData = deepcopy(jsonVars.RemoteFile)
                                kwargs.jData.varInput = 'What is the Remote file Location?'
                                kwargs.jData.varName  = 'Remote file Location'
                                kwargs.jData.varType  = 'url'
                                file_location = ezfunctions.varStringLoop(**kwargs)
                                if deviceType == 'cdd':
                                    if re.search('\.iso$', file_location): valid = True
                                    else: validating.error_file_location('Remote File Location', file_location)
                                elif deviceType == 'hdd':
                                    if re.search('\.img$', file_location): valid = True
                                    else: validating.error_file_location('Remote File Location', file_location)
                            if not Protocol == 'nfs':
                                #==============================================
                                # Prompt User for Mount Username
                                #==============================================
                                kwargs.jData = deepcopy(jsonVars.Username)
                                kwargs.jData.pattern  = '^[\\S]+$'
                                kwargs.jData.varInput = 'What is the Username you would like to configure for'\
                                    ' Authentication?  [press enter to skip]:'
                                kwargs.jData.varName  = 'Username'
                                Username = ezfunctions.varStringLoop(**kwargs)
                                if not Username == '':
                                    #==============================================
                                    # Prompt User for Mount Password
                                    #==============================================
                                    kwargs.Variable = f'vmedia_password_{inner_loop_count}'
                                    kwargs = ezfunctions.sensitive_var_value(**kwargs)
                            else: Username = ''
                            #==============================================
                            # Prompt User for Mount Options
                            #==============================================
                            kwargs.jData = deepcopy(jsonVars.MountOptions)
                            kwargs.jData.default  = False
                            kwargs.jData.varInput = 'Would you like to assign any mount options?'
                            kwargs.jData.varName  = 'Mount Options'
                            assignOptions = ezfunctions.varBoolLoop(**kwargs)
                            if assignOptions == True:
                                kwargs.multi_select = True
                                jsonVars = ezData.ezimm.allOf[1].properties.policies.vmedia.Mapping
                                if Protocol == 'cifs': kwargs.jData = deepcopy(jsonVars.cifs.mountOptions)
                                elif Protocol == 'nfs': kwargs.jData = deepcopy(jsonVars.nfs.mountOptions)
                                else: kwargs.jData = deepcopy(jsonVars.http.mountOptions)
                                kwargs.jData.varType = 'Mount Options'
                                mount_loop = ezfunctions.variablesFromAPI(**kwargs)
                                kwargs.multi_select = False
                                mount_output = []
                                for x in mount_loop: mount_output.append(x)
                                for x in mount_loop:
                                    if x == 'port':
                                        #==============================================
                                        # Prompt User for NFS Port
                                        #==============================================
                                        kwargs.jData = deepcopy(jsonVars.nfs.Port)
                                        kwargs.jData.varInput = 'What Port would you like to assign?'
                                        kwargs.jData.varName  = 'NFS Port'
                                        Question = ezfunctions.varNumberLoop(**kwargs)
                                        port = f'port={Question}'
                                        mount_output.remove(x); mount_output.append(port)
                                    elif x == 'retry':
                                        #==============================================
                                        # Prompt User for NFS Retry Count
                                        #==============================================
                                        kwargs.jData = deepcopy(jsonVars.nfs.Retry)
                                        kwargs.jData.varInput     = 'What Retry would you like to assign?'
                                        kwargs.jData.varName      = 'NFS Retry'
                                        Question = ezfunctions.varNumberLoop(**kwargs)
                                        retry = f'retry={Question}'
                                        mount_output.remove(x); mount_output.append(retry)
                                    elif x == 'timeo':
                                        #==============================================
                                        # Prompt User for NFS Timeout
                                        #==============================================
                                        kwargs.jData = deepcopy(jsonVars.nfs.Timeout)
                                        kwargs.jData.varInput     = 'What Timeout (timeo) would you like to assign?'
                                        kwargs.jData.varName      = 'NFS Timeout'
                                        Question = ezfunctions.varNumberLoop(**kwargs)
                                        timeo = f'timeo={Question}'
                                        mount_output.remove(x); mount_output.append(timeo)
                                    elif re.search('(rsize|wsize)', x):
                                        #==============================================
                                        # Prompt User for NFS Read/Write Size
                                        #==============================================
                                        valid = False
                                        while valid == False:
                                            kwargs.jData = deepcopy(jsonVars.nfs.Size)
                                            kwargs.jData.description  = f'NFS {x} Size'
                                            kwargs.jData.varInput     = f'What is the value of {x} you want to assign?'
                                            kwargs.jData.varName      = f'NFS {x}'
                                            Question = ezfunctions.varNumberLoop(**kwargs)
                                            if int(Question) % 1024 == 0: valid = True
                                            else:
                                                print(f'\n{"-"*108}\n')
                                                print(f'  {x} should be a divisable by 1024 and be between 1024 and 1048576')
                                                print(f'\n{"-"*108}\n')
                                        xValue = '%s=%s' % (x, Question)
                                        mount_output.remove(x); mount_output.append(xValue)
                                    elif x == 'vers':
                                        #==============================================
                                        # Prompt User for Version
                                        #==============================================
                                        kwargs.jData = DotMap()
                                        kwargs.jData.default = '3.0'
                                        kwargs.jData.description  = 'Mount Option Version'
                                        if Protocol == 'cifs':  kwargs.jData.enum = ['1.0', '2.0', '2.1', '3.0']
                                        elif Protocol == 'nfs': kwargs.jData.enum = ['3.0', '4.0']
                                        kwargs.jData.varType = f'{Protocol} Version'
                                        Question = ezfunctions.variablesFromAPI(**kwargs)
                                        vers = f'vers={Question}'
                                        mount_output.remove(x)
                                        mount_output.append(vers)
                                mount_options = mount_output.sort()
                                mount_options = ','.join(mount_output)
                            else: mount_options = ''
                            #==============================================
                            # Create vMedia Mapping Dictionary
                            #==============================================
                            vmedia_map = {
                                'device_type':deviceType, 'file_location':file_location, 'name':vName, 'protocol':Protocol
                            }
                            if not mount_options == '': vmedia_map.update({'mount_options':mount_options})
                            if not Username == '': vmedia_map.update({'password':inner_loop_count, 'username':Username})
                            if Protocol == 'cifs': vmedia_map.update({'authentication_protocol':authProtocol})
                            #==============================================
                            # Print Policy and Prompt User to Accept
                            #==============================================
                            print(f'\n{"-"*108}\n')
                            print(textwrap.indent(yaml.dump(vmedia_map, Dumper=yaml_dumper, default_flow_style=False
                            ), ' '*4, predicate=None))
                            print(f'{"-"*108}\n')
                            valid_confirm = False
                            while valid_confirm == False:
                                confirm_config = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                                if confirm_config == 'Y' or confirm_config == '':
                                    polVars.add_virtual_media.append(vmedia_map)
                                    pol_type = 'Virtual Media'
                                    valid_exit = False
                                    while valid_exit == False:
                                        loop_exit, sub_loop = ezfunctions.exit_default(policy_type, 'N')
                                        if loop_exit == False: inner_loop_count += 1; valid_exit = True; valid_confirm = True
                                        elif loop_exit == True: valid_confirm = True; valid_sub = True; valid_exit = True
                                elif confirm_config == 'N':
                                    pol_type = 'Virtual Media Configuration'
                                    ezfunctions.message_starting_over(pol_type)
                                    valid_confirm = True
                                else: ezfunctions.message_invalid_y_or_n('short')
                    elif question == False: sub_loop = True
                #==============================================
                # Print Policy and Prompt User to Accept
                #==============================================
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(textwrap.indent(yaml.dump(polVars, Dumper=yaml_dumper, default_flow_style=False), ' '*4, predicate=None))
                print(f'-------------------------------------------------------------------------------------------\n')
                valid_confirm = False
                while valid_confirm == False:
                    confirm_policy = input('Do you want to accept the above configuration?  Enter "Y" or "N" [Y]: ')
                    if confirm_policy == 'Y' or confirm_policy == '':
                        #==============================================
                        # Add Policy Variables to imm_dict
                        #==============================================
                        kwargs.class_path = 'policies,virtual_media'
                        kwargs = ezfunctions.ez_append(polVars, **kwargs)
                        #==============================================
                        # Create Additional Policy or Exit Loop
                        #==============================================
                        configure_loop, policy_loop = ezfunctions.exit_default(policy_type, 'N')
                        valid_confirm = True
                    elif confirm_policy == 'N':
                        ezfunctions.message_starting_over(policy_type)
                        valid_confirm = True
                    else: ezfunctions.message_invalid_y_or_n('short')
        # Return kwargs
        return kwargs

#==============================================
# Select Policy Function
#==============================================
def policy_select_loop(self, **kwargs):
    ezData = kwargs.ezData
    policy = kwargs.policy
    name   = kwargs.name
    name_prefix = self.name_prefix
    org = kwargs.org
    loop_valid = False
    while loop_valid == False:
        create_policy = True
        kwargs.inner_policy = policy.split('.')[1]
        kwargs.inner_type   = policy.split('.')[0]
        kwargs.inner_var    = policy.split('.')[2]
        inner_policy = kwargs.inner_policy
        inner_type   = kwargs.inner_type
        inner_var    = kwargs.inner_var
        kwargs = ezfunctions.policies_parse(inner_type, inner_policy, **kwargs)
        if not len(kwargs.policies[kwargs.inner_policy]) > 0:
            valid = False
            while valid == False:
                policy_description = ezfunctions.mod_pol_description(inner_var)
                print(f'\n-------------------------------------------------------------------------------------------\n')
                print(f'   There was no {policy_description} found.')
                print(f'\n-------------------------------------------------------------------------------------------\n')
                if kwargs.allow_opt_out == True:
                    Question = input(f'Do you want to create a(n) {policy_description}?  Enter "Y" or "N" [Y]: ')
                    if Question == '' or Question == 'Y': create_policy = True; valid = True
                    elif Question == 'N': create_policy = False; valid = True; return kwargs
                else: create_policy = True; valid = True
        else:
            kwargs.name = name
            kwargs = ezfunctions.choose_policy(inner_policy, **kwargs)
            if kwargs.policy == 'create_policy': create_policy = True
            elif kwargs.policy == '' and kwargs.allow_opt_out == True:
                loop_valid = True
                create_policy = False
                kwargs[kwargs.inner_var] = ''
                return kwargs
            elif not kwargs.policy == '':
                loop_valid = True
                create_policy = False
                kwargs[kwargs.inner_var] = kwargs.policy
                return kwargs
        # Simple Loop to show name_prefix in Use
        ncount = 0
        if ncount == 5: print(name_prefix)
        # Create Policy if Option was Selected
        if create_policy == True:
            print(f'\n-------------------------------------------------------------------------------------------\n')
            print(f'  Starting module to create {policy_description} in Organization {org}')
            print(f'\n-------------------------------------------------------------------------------------------\n')
            list_lansan = ezData.ezimm.allOf[1].properties.list_lansan.enum
            list_policies = ezData.ezimm.allOf[1].properties.list_policies.enum
            list_profiles = ['ucs_server_profiles', 'ucs_server_profile_templates']
            if re.search('pool$', inner_var):
                kwargs = eval(f'pools.pools(name_prefix, org, inner_type).{inner_policy}(**kwargs)')
            elif inner_policy in list_lansan:
                kwargs = eval(f'lansan.policies(name_prefix, org, inner_type).{inner_policy}(**kwargs)')
            elif inner_policy in list_policies:
                kwargs = eval(f'policies(name_prefix, org, inner_type).{inner_policy}(**kwargs)')
            elif inner_policy in list_profiles:
                kwargs = eval(f'profiles(name_prefix, org, inner_type).{inner_policy}(**kwargs)')
    # Return kwargs
    return kwargs

#==============================================
# Ethernet Port Policy Function
#==============================================
def port_list_eth(self, **kwargs):
    device_model       = kwargs.device_model
    jsonData           = kwargs.jsonData
    kwargs.portDict = []
    port_count         = 1
    port_type          = kwargs.port_type
    ports_in_use       = kwargs.ports_in_use
    if  len(kwargs.fc_converted_ports) > 0: fc_count = len(kwargs.fc_converted_ports)
    else: fc_count = 0
    if   kwargs.device_model == 'UCS-FI-64108': uplinks = ezfunctions.vlan_list_full('99-108')
    elif kwargs.device_model == 'UCS-FI-6536': uplinks = ezfunctions.vlan_list_full('1-36')
    else: uplinks = ezfunctions.vlan_list_full('49-54')
    uplink_list = uplinks
    for item in ports_in_use:
        for i in uplink_list:
            if int(item) == int(i): uplinks.remove(i)
    if   port_type == 'Appliance Port-Channels' and device_model == 'UCS-FI-64108': portx = f'{uplinks[-4]},{uplinks[-1]}'
    elif port_type == 'Appliance Port-Channels' and device_model == 'UCS-FI-6536' : portx = f'{uplinks[1]},{uplinks[0]}'
    elif port_type == 'Appliance Port-Channels': portx = f'{uplinks[-2]},{uplinks[-1]}'
    elif port_type == 'Ethernet Uplink Port-Channels' and device_model == 'UCS-FI-64108': portx = f'{uplinks[-4]},{uplinks[-1]}'
    elif port_type == 'Ethernet Uplink Port-Channels' and device_model == 'UCS-FI-6536' : portx =f'{uplinks[1]},{uplinks[0]}'
    elif port_type == 'Ethernet Uplink Port-Channels': portx = f'{uplinks[-2]},{uplinks[-1]}'
    elif port_type == 'FCoE Uplink Port-Channels' and device_model == 'UCS-FI-64108': portx = f'{uplinks[-4]},{uplinks[-1]}'
    elif port_type == 'FCoE Uplink Port-Channels' and device_model == 'UCS-FI-6536' : portx = f'{uplinks[1]},{uplinks[0]}'
    elif port_type == 'FCoE Uplink Port-Channels': portx = f'{uplinks[-2]},{uplinks[-1]}'
    elif port_type == 'Appliance Ports' and device_model == 'UCS-FI-64108': portx = f'{uplinks[-1]}'
    elif port_type == 'Appliance Ports' and device_model == 'UCS-FI-6536' : portx = f'{uplinks[0]}'
    elif port_type == 'Appliance Ports': portx = f'{uplinks[-1]}'
    elif port_type == 'Ethernet Uplinks' and device_model == 'UCS-FI-64108': portx = f'{uplinks[-1]}'
    elif port_type == 'Ethernet Uplinks' and device_model == 'UCS-FI-6536' : portx = f'{uplinks[0]}'
    elif port_type == 'Ethernet Uplinks': portx = f'{uplinks[-1]}'
    elif port_type == 'FCoE Uplinks' and device_model == 'UCS-FI-64108': portx = f'{uplinks[-1]}'
    elif port_type == 'FCoE Uplinks' and device_model == 'UCS-FI-6536' : portx = f'{uplinks[0]}'
    elif port_type == 'FCoE Uplinks': portx = f'{uplinks[-1]}'
    elif port_type == 'Server Ports' and device_model == 'UCS-FI-64108': portx = f'{fc_count + 1}-36'
    elif port_type == 'Server Ports' and device_model == 'UCS-FI-6536' : portx = f'{uplinks[0]}-32'
    elif port_type == 'Server Ports': portx = f'{fc_count + 1}-18'
    if re.search('(Ethernet Uplink Port-Channel|Server Ports)', kwargs.port_type): default_answer = 'Y'
    else: default_answer = 'N'
    valid = False
    while valid == False:
        if kwargs.port_type == 'Server Ports':
            question = input(f'Do you want to configure {port_type}?  Enter "Y" or "N" [{default_answer}]: ')
        else: question = input(f'Do you want to configure an {port_type}?  Enter "Y" or "N" [{default_answer}]: ')
        if question == 'Y' or (default_answer == 'Y' and question == ''):
            configure_valid = False
            while configure_valid == False:
                print(f'\n------------------------------------------------------\n')
                print(f'  The Port List can be in the format of:')
                print(f'     5 - Single Port')
                print(f'     5-10 - Range of Ports')
                print(f'     5,11,12,13,14,15 - List of Ports')
                print(f'     5-10,20-30 - Ranges and Lists of Ports')
                print(f'\n------------------------------------------------------\n')
                port_list = input(f'Please enter the list of ports you want to add to the {port_type}?  [{portx}]: ')
                if port_list == '': port_list = portx
                if re.search(r'(^\d+$|^\d+,{1,48}\d+$|^(\d+[\-,\d+]+){1,48}\d+$)', port_list):
                    original_port_list = port_list
                    ports_expanded = ezfunctions.vlan_list_full(port_list)
                    port_list = []
                    for x in ports_expanded: port_list.append(int(x))
                    port_overlap_count = 0
                    port_overlap = []
                    for x in ports_in_use:
                        for y in port_list:
                            if int(x) == int(y):
                                port_overlap_count += 1
                                port_overlap.append(x)
                    if port_overlap_count == 0:
                        if   kwargs.device_model == 'UCS-FI-64108': max_port = 108
                        elif kwargs.device_model == 'UCS-FI-6536': max_port = 36
                        else: max_port = 54
                        if kwargs.fc_mode == 'Y': min_port = int(kwargs.fc_ports[1]) + 1
                        else: min_port = 1
                        for port in port_list:
                            valid_ports = validating.number_in_range('Port Range', port, min_port, max_port)
                            if valid_ports == False: break
                        if valid_ports == True:
                            # Prompt User for the Admin Speed of the Port
                            if not kwargs.port_type == 'Server Ports':
                                kwargs.multi_select = False
                                jsonVars = jsonData.fabric.TransceiverRole.allOf[1].properties
                                kwargs.jData = deepcopy(jsonVars.AdminSpeed)
                                kwargs.jData.dontsort = True
                                kwargs.jData.varType = 'Admin Speed'
                                admin_speed = ezfunctions.variablesFromAPI(**kwargs)
                            if re.search('^(Appliance|(Ethernet|FCoE) Uplink)$', port_type):
                                # Prompt User for the FEC Mode of the Port
                                kwargs.jData = deepcopy(jsonVars.AdminSpeed)
                                kwargs.jData.varType = 'Fec Mode'
                                fec = ezfunctions.variablesFromAPI(**kwargs)
                            if re.search('(Appliance)', port_type):
                                # Prompt User for the Mode of the Port
                                jsonVars = jsonData.fabric.AppliancePcRole.allOf[1].properties
                                kwargs.jData = deepcopy(jsonVars.Mode)
                                kwargs.jData.varType = 'Mode'
                                mode = ezfunctions.variablesFromAPI(**kwargs)

                                kwargs.jData = deepcopy(jsonVars.Priority)
                                kwargs.jData.varType = 'Priority'
                                priority = ezfunctions.variablesFromAPI(**kwargs)
                            # Prompt User for the
                            policy_list = []
                            if re.search('(Appliance|FCoE)', port_type):
                                policy_list.extend(policies.ethernet_network_control.ethernet_network_control_policy)
                            if re.search('(Appliance|Ethernet)', port_type):
                                policy_list.extend(policies.ethernet_network_group.ethernet_network_group_policy)
                            if re.search('(Ethernet|FCoE)', port_type):
                                policy_list.extend(policies.link_aggregation.link_aggregation_policy)
                            if re.search('Ethernet Uplink', port_type):
                                policy_list.extend([
                                    'policies.flow_control.flow_control_policy', 'policies.link_control.link_control_policy'
                                ])
                            kwargs.allow_opt_out = False
                            if not kwargs.port_type == 'Server Ports':
                                for i in policy_list:
                                    kwargs.policy = i
                                    kwargs = policy_select_loop(self, **kwargs)
                            interfaces = []
                            pc_id = port_list[0]
                            for i in port_list: interfaces.append({'port_id':i})
                            if port_type == 'Appliance Port-Channels':
                                port_config = {
                                    'admin_speed':admin_speed,
                                    'ethernet_network_control_policy':kwargs.ethernet_network_control_policy,
                                    'ethernet_network_group_policy':kwargs.ethernet_network_group_policy,
                                    'interfaces':interfaces, 'mode':mode, 'pc_ids':[pc_id, pc_id], 'priority':priority
                                }
                            elif port_type == 'Ethernet Uplink Port-Channels':
                                port_config = {
                                    'admin_speed':admin_speed,
                                    'ethernet_network_group_policy':kwargs.ethernet_network_group_policy,
                                    'flow_control_policy':kwargs.flow_control_policy,
                                    'interfaces':interfaces, 'link_aggregation_policy':kwargs.link_aggregation_policy,
                                    'link_control_policy':kwargs.link_control_policy, 'pc_ids':[pc_id, pc_id]
                                }
                            elif port_type == 'FCoE Uplink Port-Channels':
                                port_config = {
                                    'admin_speed':admin_speed, 'interfaces':interfaces,
                                    'link_aggregation_policy':kwargs.link_aggregation_policy,
                                    'link_control_policy':kwargs.link_control_policy,
                                    'pc_ids':[pc_id, pc_id]
                                }
                            elif port_type == 'Appliance Ports':
                                port_config = {
                                    'admin_speed':admin_speed,
                                    'ethernet_network_control_policy':kwargs.ethernet_network_control_policy,
                                    'ethernet_network_group_policy':kwargs.ethernet_network_group_policy,
                                    'fec':fec, 'mode':mode, 'port_list':original_port_list, 'priority':priority
                                }
                            elif port_type == 'Ethernet Uplinks':
                                port_config = {
                                    'admin_speed':admin_speed,
                                    'ethernet_network_group_policy':kwargs.ethernet_network_group_policy,
                                    'fec':fec, 'flow_control_policy':kwargs.flow_control_policy,
                                    'link_control_policy':kwargs.link_control_policy, 'port_list':original_port_list
                                }
                            elif port_type == 'FCoE Uplinks':
                                port_config = {
                                    'admin_speed':admin_speed, 'fec':fec,
                                    'link_control_policy':kwargs.link_control_policy,
                                    'port_list':original_port_list
                                }
                            elif port_type == 'Server Ports': port_config = {'port_list':original_port_list}
                            print(f'\n-------------------------------------------------------------------------------------------\n')
                            print(textwrap.indent(yaml.dump({port_type:port_config}, Dumper=yaml_dumper, default_flow_style=False
                            ), " "*4, predicate=None))
                            print(f'-------------------------------------------------------------------------------------------\n')
                            valid_confirm = False
                            while valid_confirm == False:
                                confirm_port = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                                if confirm_port == 'Y' or confirm_port == '':
                                    kwargs.portDict.append(port_config)
                                    for i in port_list:
                                        kwargs.ports_in_use.append(i)

                                    valid_exit = False
                                    while valid_exit == False:
                                        port_exit = input(f'Would You like to Configure another {port_type}?  Enter "Y" or "N" [N]: ')
                                        if port_exit == 'Y':
                                            port_count += 1
                                            valid_confirm = True
                                            valid_exit = True
                                        elif port_exit == 'N' or port_exit == '':
                                            configure_valid = True
                                            valid = True
                                            valid_confirm = True
                                            valid_exit = True
                                        else: ezfunctions.message_invalid_y_or_n('short')
                                elif confirm_port == 'N':
                                    ezfunctions.message_starting_over(port_type)
                                    valid_confirm = True
                                else: ezfunctions.message_invalid_y_or_n('short')
                    else:
                        print(f'\n-------------------------------------------------------------------------------------------\n')
                        print(f'  Error!! The following Ports are already in use: {port_overlap}.')
                        print(f'\n-------------------------------------------------------------------------------------------\n')
                else:
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(f'  Error!! Invalid Port Range.  A port Range should be in the format 49-50 for example.')
                    print(f'  The following port range is invalid: "{port_list}"')
                    print(f'\n-------------------------------------------------------------------------------------------\n')

        elif question == 'N'  or (default_answer == 'N' and question == ''): valid = True
        else: ezfunctions.message_invalid_y_or_n('short')
    # Return kwargs
    return kwargs
    
#==============================================
# Fibre-Channel Port Policy Function
#==============================================
def port_list_fc(self, **kwargs):
    jsonData  = kwargs.jsonData
    org       = kwargs.org
    port_type = kwargs.port_type
    fill_pattern_descr = 'For Cisco UCS 6400 Series fabric interconnect, if the FC uplink speed is 8 Gbps, set the '\
        'fill pattern as IDLE on the uplink switch. If the fill pattern is not set as Idle, FC '\
        'uplinks operating at 8 Gbps might go to an errDisabled state, lose SYNC intermittently, or '\
        'notice errors or bad packets.  For speeds greater than 8 Gbps we recommend Idle.  Below '\
        'is a configuration example on MDS to match this setting:\n\n'\
        'mds(config-if)# switchport fill-pattern IDLE speed 8000\n'\
        'mds(config-if)# show port internal inf interface fc1/1 | grep FILL\n'\
        '  FC_PORT_CAP_FILL_PATTERN_8G_CHANGE_CAPABLE (1)\n'\
        'mds(config-if)# show run int fc1/16 | incl fill\n\n'\
        'interface fc1/16\n'\
        '  switchport fill-pattern IDLE speed 8000\n\n'\
        'mds(config-if)#\n'

    if port_type == 'FC Uplink Port-Channels': default_answer = 'Y'
    else: default_answer = 'N'
    port_count = 1
    if len(kwargs.fc_converted_ports) > 0: configure_fc = True
    else: configure_fc = False
    if configure_fc == True:
        valid = False
        while valid == False:
            question = input(f'Do you want to configure a {port_type}?  Enter "Y" or "N" [{default_answer}]: ')
            if question == 'Y' or (default_answer == 'Y' and question == ''):
                configure_valid = False
                while configure_valid == False:
                    port_list = kwargs.fc_converted_ports
                    kwargs.jdata = DotMap(
                        default = port_list[0], enum = port_list, multi_select = True, title = 'Unified Port',
                        description = f'    Port(s) for {port_type}.\n')
                    port_list = ezfunctions.variable_prompt(kwargs)

                    # Prompt User for the Admin Speed of the Port
                    kwargs.multi_select = False
                    jsonVars = jsonData.fabric.FcUplinkPcRole.allOf[1].properties
                    kwargs.jData = deepcopy(jsonVars.AdminSpeed)
                    kwargs.jData.enum.remove('Auto')
                    kwargs.jData.default = kwargs.jData.enum[2]
                    kwargs.jData.dontsort = True
                    kwargs.jData.varType = 'Admin Speed'
                    admin_speed = ezfunctions.variablesFromAPI(**kwargs)

                    # Prompt User for the Fill Pattern of the Port
                    if not port_type == 'Fibre-Channel Storage':
                        if admin_speed == '8Gbps':
                            varDesc = fill_pattern_descr
                            print(f'\n-------------------------------------------------------------------------------------------\n')
                            if '\n' in varDesc:
                                varDesc = varDesc.split('\n')
                                for line in varDesc:
                                    if '*' in line: print(textwrap.fill(f'{line}',width=88, subsequent_indent='    '))
                                    else: print(textwrap.fill(f'{line}',88))
                            else: print(textwrap.fill(f'{varDesc}',88))
                        fill_pattern = 'Idle'

                    vsans = {}
                    fabrics = ['Fabric_A', 'Fabric_B']
                    for fabric in fabrics:
                        print(f'\n-------------------------------------------------------------------------------------------\n')
                        print(f'  Please Select the VSAN Policy for {fabric}')
                        kwargs.allow_opt_out = False
                        kwargs.policy = 'policies.vsan.vsan_policy'
                        kwargs = policy_select_loop(self, **kwargs)
                        print(kwargs.vsan_policy)
                        vsan_list = []
                        for i in kwargs.imm_dict.orgs[org].policies.vsan:
                            if i.name == kwargs.vsan_policy:
                                for e in i.vsans: vsan_list.append(e.vsan_id)
                        if port_type == 'FC Uplink Port-Channels': fc_type = 'Port-Channel'
                        elif port_type == 'FC Storage': fc_type = 'Storage Port'
                        else: fc_type = 'Uplink Port'
                        kwargs.jdata = DotMap(
                            default = vsan_list[0], enum = vsan_list, multi_select = False, title = 'VSAN',
                            description = f'    VSAN for the Fibre-Channel {fc_type} Port.\n')
                        vsan_x = ezfunctions.variable_prompt(kwargs)
                        for vs in vsan_x: vsan = vs
                        vsans.update({fabric:vsan})
                    if port_type == 'FC Uplink Port-Channels':
                        interfaces = []
                        for i in port_list: interfaces.append({'port_id':i})
                        pc_id = port_list[0]
                        port_config = {
                            'admin_speed':admin_speed, 'fill_pattern':fill_pattern, 'interfaces':interfaces,
                            'pc_ids':[pc_id, pc_id], 'vsan_ids':[vsans.get("Fabric_A"), vsans.get("Fabric_B")]
                        }
                    elif port_type == 'Fibre-Channel Storage':
                        port_list = '%s' % (port_list[0])
                        port_config = {
                            'admin_speed':admin_speed, 'port_id':port_list, 'slot_id':1,
                            'vsan_ids':[vsans.get("Fabric_A"), vsans.get("Fabric_B")]
                        }
                    else:
                        port_list = '%s' % (port_list[0])
                        port_config = {
                            'admin_speed':admin_speed, 'fill_pattern':fill_pattern, 'port_id':port_list,
                            'slot_id':1, 'vsan_id':[vsans.get("Fabric_A"), vsans.get("Fabric_B")]
                        }
                    print(f'\n-------------------------------------------------------------------------------------------\n')
                    print(textwrap.indent(yaml.dump({port_type:port_config}, Dumper=yaml_dumper, default_flow_style=False
                    ), " "*4, predicate=None))
                    print(f'-------------------------------------------------------------------------------------------\n')
                    valid_confirm = False
                    while valid_confirm == False:
                        confirm_port = input('Do you want to accept the configuration above?  Enter "Y" or "N" [Y]: ')
                        if confirm_port == 'Y' or confirm_port == '':
                            kwargs.portDict.append(port_config)
                            if not kwargs.get('fc_ports_in_use'):
                                kwargs.fc_ports_in_use = []
                            for i in port_list: kwargs.fc_ports_in_use.append(i)
                            valid_exit = False
                            while valid_exit == False:
                                port_exit = input(f'Would You like to Configure another {port_type}?  Enter "Y" or "N" [N]: ')
                                if port_exit == 'Y':
                                    port_count += 1
                                    valid_confirm = True
                                    valid_exit = True
                                elif port_exit == 'N' or port_exit == '':
                                    configure_valid = True
                                    valid = True
                                    valid_confirm = True
                                    valid_exit = True
                                else: ezfunctions.message_invalid_y_or_n('short')
                        elif confirm_port == 'N':
                            ezfunctions.message_starting_over(port_type)
                            valid_confirm = True
                        else: ezfunctions.message_invalid_y_or_n('short')
            elif question == 'N' or (default_answer == 'N' and question == ''): valid = True
            else: ezfunctions.message_invalid_y_or_n('short')
    # Return kwargs
    return kwargs

#==============================================
# Port Mode Port Policy Function
#==============================================
def port_modes(kwargs):
    fc_converted_ports = []
    port_modes         = []
    ports_in_use       = []
    kwargs.port_modes  = []
    kwargs.jdata = DotMap(
        default     = False,
        description = f'Do you want to convert ports to Fibre-Channel Mode?',
        title       = 'FC Port Mode',
        type        = 'boolean')
    fc_mode = ezfunctions.variable_prompt(kwargs)
    if fc_mode == True:
        pcolor.Yellow('Ports with FC Optics installed.')
        for e in kwargs.fc_ports:
            pcolor.Yellow(f'  * PortId: {e.port}, optic: {e.optic}')
        if kwargs.domain.type == 'UCS-FI-6536':
            kwargs.jdata   = kwargs.ezwizard.port.properties.port_mode_gen5
        else: kwargs.jdata = kwargs.ezwizard.port.properties.port_mode_gen4
        fc_ports = ezfunctions.variable_prompt(**kwargs)
        x = fc_ports.split('-')
        fc_ports = [int(x[0]),int(x[1])]
        for i in range(int(x[0]), int(x[1]) + 1):
            ports_in_use.append(i)
            fc_converted_ports.append(i)
        if kwargs.device_model == 'UCS-FI-6536':
            port_modes = {'custom_mode':'BreakoutFibreChannel32G','port_list':fc_ports,}
        else: port_modes = {'custom_mode':'FibreChannel','port_list':fc_ports,}
    kwargs.fc_converted_ports = fc_converted_ports
    kwargs.fc_mode  = fc_mode
    kwargs.fc_ports = fc_ports
    kwargs.port_modes.append(port_modes)
    kwargs.ports_in_use = ports_in_use
    # Return kwargs
    return kwargs
