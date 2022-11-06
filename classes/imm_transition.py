#!/usr/bin/env python3
import ezfunctions
import copy
import ipaddress
import jinja2
import pkg_resources
import re

ucs_template_path = pkg_resources.resource_filename('imm_transition', '../templates/')

class imm_transition(object):
    def __init__(self, json_data, type):
        self.json_data = json_data
        self.templateLoader = jinja2.FileSystemLoader(
            searchpath=(ucs_template_path + '%s/') % (type))
        self.templateEnv = jinja2.Environment(loader=self.templateLoader)
        self.polVars = {}
        self.type = type
        self.orgs = []
        for item in json_data["config"]["orgs"]:
            for k, v in item.items():
                if k == 'name':
                    self.orgs.append(v)

    def return_orgs(self):
        orgs = self.orgs
        return orgs

    def bios_policies(self):
        header = 'BIOS Policy Variables'
        initial_policy = True
        template_type = 'bios_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def boot_order_policies(self):
        header = 'Boot Order Policy Variables'
        initial_policy = True
        template_type = 'boot_order_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ethernet_adapter_policies(self):
        header = 'Ethernet Adapter Policy Variables'
        initial_policy = True
        template_type = 'ethernet_adapter_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ethernet_network_control_policies(self):
        header = 'Ethernet Network Control Policy Variables'
        initial_policy = True
        template_type = 'ethernet_network_control_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ethernet_network_group_policies(self):
        header = 'Ethernet Network Group Policy Variables'
        initial_policy = True
        template_type = 'ethernet_network_group_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ethernet_network_policies(self):
        header = 'Ethernet Network Policy Variables'
        initial_policy = True
        template_type = 'ethernet_network_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ethernet_qos_policies(self):
        header = 'Ethernet QoS Policy Variables'
        initial_policy = True
        template_type = 'ethernet_qos_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def fibre_channel_adapter_policies(self):
        header = 'Fibre-Channel Adapter Policy Variables'
        initial_policy = True
        template_type = 'fibre_channel_adapter_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def fibre_channel_network_policies(self):
        header = 'Fibre-Channel Network Policy Variables'
        initial_policy = True
        template_type = 'fibre_channel_network_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def fibre_channel_qos_policies(self):
        header = 'Fibre-Channel QoS Policy Variables'
        initial_policy = True
        template_type = 'fibre_channel_qos_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def flow_control_policies(self):
        header = 'Flow Control Policy Variables'
        initial_policy = True
        template_type = 'flow_control_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def imc_access_policies(self):
        header = 'IMC Access Policiy Variables'
        initial_policy = True
        template_type = 'imc_access_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ip_pools(self):
        header = 'IP Pool Variables'
        initial_policy = True
        template_type = 'ip_pools'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ipmi_over_lan_policies(self):
        header = 'IPMI over LAN Policy Variables'
        initial_policy = True
        template_type = 'ipmi_over_lan_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def iqn_pools(self):
        header = 'IQN Pool Variables'
        initial_policy = True
        template_type = 'iqn_pools'
        policy_loop_standard(self, header, initial_policy, template_type)

    def iscsi_adapter_policies(self):
        header = 'iSCSI Adapter Policy Variables'
        initial_policy = True
        template_type = 'iscsi_adapter_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def iscsi_boot_policies(self):
        header = 'iSCSI Boot Policy Variables'
        initial_policy = True
        template_type = 'iscsi_boot_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def iscsi_static_target_policies(self):
        header = 'iSCSI Static Target Policy Variables'
        initial_policy = True
        template_type = 'iscsi_static_target_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def lan_connectivity_policies(self):
        header = 'LAN Connectivity Policy Variables'
        initial_policy = True
        template_type = 'lan_connectivity_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def link_aggregation_policies(self):
        header = 'Link Aggregation Policy Variables'
        initial_policy = True
        template_type = 'link_aggregation_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def link_control_policies(self):
        header = 'Link Control Policy Variables'
        initial_policy = True
        template_type = 'link_control_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def mac_pools(self):
        header = 'MAC Pool Variables'
        initial_policy = True
        template_type = 'mac_pools'
        policy_loop_standard(self, header, initial_policy, template_type)

    def multicast_policies(self):
        header = 'Multicast Policy Variables'
        initial_policy = True
        template_type = 'multicast_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def network_connectivity_policies(self):
        header = 'Network Connectivity (DNS) Policy Variables'
        initial_policy = True
        template_type = 'network_connectivity_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ntp_policies(self):
        header = 'NTP Policy Variables'
        initial_policy = True
        template_type = 'ntp_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def port_policies(self):
        header = 'Port Policy Variables'
        initial_policy = True
        template_type = 'port_policies'

        # Set the org_count to 0 for the First Organization
        org_count = 0

        # Loop through the orgs discovered by the Class
        for org in self.orgs:

            # Pull in Variables from Class
            polVars = self.polVars
            polVars["org"] = org

            # Define the Template Source
            polVars["header"] = header
            polVars["template_type"] = template_type
            template_file = "template_open.jinja2"
            template = self.templateEnv.get_template(template_file)

            # Process the template
            dest_dir = '%s' % (self.type)
            dest_file = '%s.auto.tfvars' % (template_type)
            if initial_policy == True:
                write_method = 'w'
            else:
                write_method = 'a'
            ezfunctions.process_method(write_method, dest_dir, dest_file, template, **polVars)

            # Define the Template Source
            template_file = '%s.jinja2' % (template_type)
            template = self.templateEnv.get_template(template_file)

            if template_type in self.json_data["config"]["orgs"][org_count]:
                for item in self.json_data["config"]["orgs"][org_count][template_type]:
                    # Reset polVars to Default for each Loop
                    polVars = {}
                    polVars["org"] = org

                    # Define the Template Source
                    polVars["header"] = header
                    for k, v in item.items():
                        if re.search(r'(_port_channels)', k):
                            polVars[k] = []
                            attribute_list = {}
                            for i in v:
                                interface_list = []
                                for key, value in i.items():
                                    attribute_list.update({key: value})

                                attribute_list = dict(sorted(attribute_list.items()))
                                xdeep = copy.deepcopy(attribute_list)
                                polVars[k].append(xdeep)

                        elif re.search(r'(server_ports)', k):
                            aggr_ids = []
                            ports_count = 0
                            polVars[k] = []
                            slot_ids = []
                            for i in v:
                                for key, value in i.items():
                                    if key == 'aggr_id':
                                        aggr_ids.append(value)
                                    if key == 'slot_id':
                                        slot_ids.append(value)
                            aggr_ids = list(set(aggr_ids))
                            slot_ids = list(set(slot_ids))
                            if len(aggr_ids) or len(slot_ids) > 1:
                                for i in v:
                                    attribute_list = {}
                                    port_list = []
                                    for key, value in i.items():
                                        if key == 'aggr_id':
                                            attribute_list.update({'breakout_port_id': value})
                                        elif key == 'port_id':
                                            port_list.append(value)
                                        else:
                                            attribute_list.update({'slot_id': value})
                                    attribute_list.update({'key_id': ports_count})
                                    attribute_list.update({'port_list': port_list})
                                    attribute_list = dict(sorted(attribute_list.items()))
                                    xdeep = copy.deepcopy(attribute_list)
                                    polVars[k].append(xdeep)
                                    ports_count += 1
                            else:
                                attribute_list = {}
                                port_list = []
                                for i in v:
                                    for key, value in i.items():
                                        if key == 'aggr_id':
                                            attribute_list.update({'aggr_id': value})
                                        elif key == 'port_id':
                                            port_list.append(value)
                                        elif key == 'slot_id':
                                            attribute_list.update({'slot_id': value})
                                attribute_list.update({'key_id': ports_count})
                                ports_count += 1
                                port_list = ",".join("{0}".format(n) for n in port_list)
                                attribute_list.update({'port_list': port_list})
                                attribute_list = dict(sorted(attribute_list.items()))
                                xdeep = copy.deepcopy(attribute_list)
                                polVars[k].append(xdeep)
                            # print(k, polVars[k])
                        elif re.search(r'(san_unified_ports)', k):
                            for key, value in v.items():
                                if key == 'port_id_start':
                                    begin = value
                                elif key == 'port_id_end':
                                    end = value
                                elif key == 'slot_id':
                                    slot_id = value
                            polVars["port_modes"] = {'port_list': [begin, end], 'slot_id': slot_id}
                        elif re.search(r'(_ports)$', k):
                            ports_count = 0
                            polVars[k] = []
                            attribute_list = {}
                            for i in v:
                                for key, value in i.items():
                                    attribute_list.update({key: value})
                                attribute_list.update({'key_id': ports_count})
                                attribute_list = dict(sorted(attribute_list.items()))
                                xdeep = copy.deepcopy(attribute_list)
                                polVars[k].append(xdeep)
                                ports_count += 1
                        else:
                            polVars[k] = v
                    if 'appliance_port_channels' in polVars:
                        polVars["port_channel_appliances"] = polVars["appliance_port_channels"]
                        del polVars["appliance_port_channels"]
                    if 'lan_port_channels' in polVars:
                        polVars["port_channel_ethernet_uplinks"] = polVars["lan_port_channels"]
                        del polVars["lan_port_channels"]
                    if 'san_port_channels' in polVars:
                        polVars["port_channel_fc_uplinks"] = polVars["san_port_channels"]
                        del polVars["san_port_channels"]
                    if 'fcoe_port_channels' in polVars:
                        polVars["port_channel_fcoe_uplinks"] = polVars["fcoe_port_channels"]
                        del polVars["fcoe_port_channels"]
                    if 'appliance_ports' in polVars:
                        polVars["port_role_appliances"] = polVars["appliance_ports"]
                        del polVars["appliance_ports"]
                    if 'lan_uplink_ports' in polVars:
                        polVars["port_role_ethernet_uplinks"] = polVars["lan_uplink_ports"]
                        del polVars["lan_uplink_ports"]
                    if 'storage_ports' in polVars:
                        polVars["port_role_fc_storage"] = polVars["storage_ports"]
                        del polVars["storage_ports"]
                    if 'san_uplink_ports' in polVars:
                        polVars["port_role_fc_uplinks"] = polVars["san_uplink_ports"]
                        del polVars["san_uplink_ports"]
                    if 'fcoe_uplink_ports' in polVars:
                        polVars["port_role_fcoe_uplinks"] = polVars["fcoe_uplink_ports"]
                        del polVars["fcoe_uplink_ports"]
                    if 'server_ports' in polVars:
                        polVars["port_role_servers"] = polVars["server_ports"]
                        del polVars["server_ports"]

                    polVars = dict(sorted(polVars.items()))
                    # print(polVars)

                    # Process the template
                    dest_dir = '%s' % (self.type)
                    dest_file = '%s.auto.tfvars' % (template_type)
                    ezfunctions.process_method('a', dest_dir, dest_file, template, **polVars)

            # Define the Template Source
            template_file = "template_close.jinja2"
            template = self.templateEnv.get_template(template_file)

            # Process the template
            dest_dir = '%s' % (self.type)
            dest_file = '%s.auto.tfvars' % (template_type)
            ezfunctions.process_method('a', dest_dir, dest_file, template, **polVars)

            # Increment the org_count for the next Organization Loop
            org_count += 1

    def power_policies(self):
        header = 'Power Policy Variables'
        initial_policy = True
        template_type = 'power_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def san_connectivity_policies(self):
        header = 'SAN Connectivity Policy Variables'
        initial_policy = True
        template_type = 'san_connectivity_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def sd_card_policies(self):
        header = 'SD Card Policy Variables'
        initial_policy = True
        template_type = 'sd_card_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def serial_over_lan_policies(self):
        header = 'Serial over LAN Policy Variables'
        initial_policy = True
        template_type = 'serial_over_lan_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def snmp_policies(self):
        header = 'SNMP Policy Variables'
        initial_policy = True
        template_type = 'snmp_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def storage_policies(self):
        header = 'Storage Policy Variables'
        initial_policy = True
        template_type = 'storage_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def switch_control_policies(self):
        header = 'Switch Control Policy Variables'
        initial_policy = True
        template_type = 'switch_control_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def syslog_policies(self):
        header = 'Syslog Policy Variables'
        initial_policy = True
        template_type = 'syslog_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def system_qos_policies(self):
        header = 'System QoS Policy Variables'
        initial_policy = True
        template_type = 'system_qos_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def thermal_policies(self):
        header = 'Thermal Policy Variables'
        initial_policy = True
        template_type = 'thermal_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ucs_chassis_profiles(self):
        header = 'UCS Chassis Profile Variables'
        initial_policy = True
        template_type = 'ucs_chassis_profiles'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ucs_domain_profiles(self):
        header = 'UCS Domain Profile Variables'
        initial_policy = True
        template_type = 'ucs_domain_profiles'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ucs_server_profiles(self):
        header = 'UCS Server Profile Variables'
        initial_policy = True
        template_type = 'ucs_server_profiles'
        policy_loop_standard(self, header, initial_policy, template_type)

    def ucs_server_profile_templates(self):
        header = 'UCS Server Profile Template Variables'
        initial_policy = True
        template_type = 'ucs_server_profile_templates'
        policy_loop_standard(self, header, initial_policy, template_type)

    def virtual_kvm_policies(self):
        header = 'Virtual KVM Policy Variables'
        initial_policy = True
        template_type = 'virtual_kvm_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def virtual_media_policies(self):
        header = 'Virtual Media Policy Variables'
        initial_policy = True
        template_type = 'virtual_media_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def vlan_policies(self):
        header = 'VLAN Policy Variables'
        initial_policy = True
        template_type = 'vlan_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def vsan_policies(self):
        header = 'VSAN Policy Variables'
        initial_policy = True
        template_type = 'vsan_policies'
        policy_loop_standard(self, header, initial_policy, template_type)

    def uuid_pools(self):
        header = 'UUID Pool Variables'
        initial_policy = True
        template_type = 'uuid_pools'
        policy_loop_standard(self, header, initial_policy, template_type)

    def wwnn_pools(self):
        header = 'Fibre-Channel WWNN Pool Variables'
        initial_policy = True
        template_type = 'wwnn_pools'
        policy_loop_standard(self, header, initial_policy, template_type)

    def wwpn_pools(self):
        header = 'Fibre-Channel WWPN Pool Variables'
        initial_policy = True
        template_type = 'wwpn_pools'
        policy_loop_standard(self, header, initial_policy, template_type)

def policy_loop_standard(self, header, initial_policy, template_type):
    # Set the org_count to 0 for the First Organization
    org_count = 0

    # Loop through the orgs discovered by the Class
    for org in self.orgs:

        # Pull in Variables from Class
        polVars = self.polVars
        polVars["org"] = org

        # Define the Template Source
        polVars["header"] = header
        polVars["template_type"] = template_type
        template_file = "template_open.jinja2"
        template = self.templateEnv.get_template(template_file)


        # Process the template
        dest_dir = '%s' % (self.type)
        dest_file = '%s.auto.tfvars' % (template_type)
        if initial_policy == True:
            write_method = 'w'
        else:
            write_method = 'a'
        ezfunctions.process_method(write_method, dest_dir, dest_file, template, **polVars)

        # Define the Template Source
        template_file = '%s.jinja2' % (template_type)
        template = self.templateEnv.get_template(template_file)

        if template_type == 'boot_order_policies':
            imm_template_type = 'boot_policies'
        else:
            imm_template_type = template_type
        if imm_template_type in self.json_data["config"]["orgs"][org_count]:
            for item in self.json_data["config"]["orgs"][org_count][imm_template_type]:
                # Reset polVars to Default for each Loop
                polVars = {}
                polVars["org"] = org

                # Define the Template Source
                polVars["header"] = header

                # Loop Through Json Items to Create polVars Blocks
                if template_type == 'bios_policies':
                    for k, v in item.items():
                        if (k == 'name' or k == 'descr' or k == 'tags'):
                            polVars[k] = v

                    polVars["bios_settings"] = {}
                    for k, v in item.items():
                        if not (k == 'name' or k == 'descr' or k == 'tags'):
                            polVars["bios_settings"][k] = v
                elif template_type == 'system_qos_policies':
                    for k, v in item.items():
                        if (k == 'name' or k == 'descr' or k == 'tags'):
                            polVars[k] = v

                    polVars["classes"] = [{},{},{},{},{},{}]
                    for key, value in item.items():
                        if key == 'classes':
                            class_count = 0
                            for i in value:
                                for k, v in i.items():
                                    polVars["classes"][class_count][k] = v
                                class_count += 1
                else:
                    for k, v in item.items():
                        polVars[k] = v

                if template_type == 'ip_pools':
                    if 'ipv4_blocks' in polVars:
                        index_count = 0
                        for i in polVars["ipv4_blocks"]:
                             index_count += 1
                        for r in range(0,index_count):
                            if 'to' in polVars["ipv4_blocks"][r]:
                                polVars["ipv4_blocks"][r]["size"] = int(
                                    ipaddress.IPv4Address(polVars["ipv4_blocks"][r]["to"])
                                    ) - int(ipaddress.IPv4Address(polVars["ipv4_blocks"][r]["from"])) + 1
                                ipv4_to = polVars["ipv4_blocks"][r]['to']
                                polVars["ipv4_blocks"][r].pop('to')
                                polVars["ipv4_blocks"][r]['to'] = ipv4_to

                    if 'ipv6_blocks' in polVars:
                        index_count = 0
                        for i in polVars["ipv6_blocks"]:
                             index_count += 1
                        for r in range(0,index_count):
                            if 'to' in polVars["ipv6_blocks"][r]:
                                polVars["ipv6_blocks"][r]["size"] = int(
                                    ipaddress.IPv6Address(polVars["ipv6_blocks"][r]["to"])
                                    ) - int(ipaddress.IPv6Address(polVars["ipv6_blocks"][r]["from"])) + 1
                                ipv6_to = polVars["ipv6_blocks"][r]['to']
                                polVars["ipv6_blocks"][r].pop('to')
                                polVars["ipv6_blocks"][r]['to'] = ipv6_to
                elif template_type == 'iqn_pools':
                    if 'iqn_blocks' in polVars:
                        index_count = 0
                        for i in polVars["iqn_blocks"]:
                             index_count += 1
                        for r in range(0,index_count):
                            if 'to' in polVars["iqn_blocks"][r]:
                                polVars["iqn_blocks"][r]["size"] = int(
                                    polVars["iqn_blocks"][r]["to"]
                                    ) - int(polVars["iqn_blocks"][r]["from"]) + 1
                                iqn_to = polVars["iqn_blocks"][r]["to"]
                                polVars["iqn_blocks"][r].pop('to')
                                polVars["iqn_blocks"][r]["to"] = iqn_to
                elif template_type == 'mac_pools':
                    if 'mac_blocks' in polVars:
                        index_count = 0
                        for i in polVars["mac_blocks"]:
                             index_count += 1
                        for r in range(0,index_count):
                            if 'to' in polVars["mac_blocks"][r]:
                                int_from = int(polVars["mac_blocks"][r]["from"].replace(':', ''), 16)
                                int_to = int(polVars["mac_blocks"][r]["to"].replace(':', ''), 16)
                                polVars["mac_blocks"][r]["size"] = int_to - int_from + 1
                                mac_to = polVars["mac_blocks"][r]["to"]
                                polVars["mac_blocks"][r].pop('to')
                                polVars["mac_blocks"][r]["to"] = mac_to
                elif template_type == 'system_qos_policies':
                    total_weight = 0
                    for r in range(0,6):
                        if polVars["classes"][r]["state"] == 'Enabled':
                            total_weight += int(polVars["classes"][r]["weight"])
                    for r in range(0,6):
                        if polVars["classes"][r]["state"] == 'Enabled':
                            x = ((int(polVars["classes"][r]["weight"]) / total_weight) * 100)
                            polVars["classes"][r]["bandwidth_percent"] = str(x).split('.')[0]
                        else:
                            polVars["classes"][r]["bandwidth_percent"] = 0
                elif template_type == 'uuid_pools':
                    if 'uuid_blocks' in polVars:
                        index_count = 0
                        for i in polVars["uuid_blocks"]:
                             index_count += 1
                        for r in range(0,index_count):
                            if 'to' in polVars["uuid_blocks"][r]:
                                if re.search('[a-zA-Z]', polVars["uuid_blocks"][r]["from"].split('-')[1]) or re.search('[a-zA-Z]', polVars["uuid_blocks"][r]["to"].split('-')[1]):
                                    int_from = int(polVars["uuid_blocks"][r]["from"].split('-')[1], 16)
                                    int_to = int(polVars["uuid_blocks"][r]["to"].split('-')[1], 16)
                                else:
                                    int_from = int(polVars["uuid_blocks"][r]["from"].split('-')[1])
                                    int_to = int(polVars["uuid_blocks"][r]["to"].split('-')[1])
                                polVars["uuid_blocks"][r]["size"] = int_to - int_from + 1
                                uuid_to = polVars["uuid_blocks"][r]["to"]
                                polVars["uuid_blocks"][r].pop('to')
                                polVars["uuid_blocks"][r]["to"] = uuid_to
                elif template_type == 'wwnn_pools':
                    if 'wwnn_blocks' in polVars:
                        index_count = 0
                        for i in polVars["wwnn_blocks"]:
                             index_count += 1
                        for r in range(0,index_count):
                            if 'to' in polVars["wwnn_blocks"][r]:
                                int_from = int(polVars["wwnn_blocks"][r]["from"].replace(':', ''), 16)
                                int_to = int(polVars["wwnn_blocks"][r]["to"].replace(':', ''), 16)
                                polVars["wwnn_blocks"][r]["size"] = int_to - int_from + 1
                                wwxn_to = polVars["wwnn_blocks"][r]["to"]
                                polVars["wwnn_blocks"][r].pop('to')
                                polVars["wwnn_blocks"][r]["to"] = wwxn_to
                elif template_type == 'wwpn_pools':
                    if 'wwpn_blocks' in polVars:
                        index_count = 0
                        for i in polVars["wwpn_blocks"]:
                             index_count += 1
                        for r in range(0,index_count):
                            if 'to' in polVars["wwpn_blocks"][r]:
                                int_from = int(polVars["wwpn_blocks"][r]["from"].replace(':', ''), 16)
                                int_to = int(polVars["wwpn_blocks"][r]["to"].replace(':', ''), 16)
                                polVars["wwpn_blocks"][r]["size"] = int_to - int_from + 1
                                wwxn_to = polVars["wwpn_blocks"][r]["to"]
                                polVars["wwpn_blocks"][r].pop('to')
                                polVars["wwpn_blocks"][r]["to"] = wwxn_to
                # Process the template
                dest_dir = '%s' % (self.type)
                dest_file = '%s.auto.tfvars' % (template_type)
                ezfunctions.process_method('a', dest_dir, dest_file, template, **polVars)

        # Define the Template Source
        template_file = "template_close.jinja2"
        template = self.templateEnv.get_template(template_file)

        # Process the template
        dest_dir = '%s' % (self.type)
        dest_file = '%s.auto.tfvars' % (template_type)
        ezfunctions.process_method('a', dest_dir, dest_file, template, **polVars)

        # Increment the org_count for the next Organization Loop
        org_count += 1
