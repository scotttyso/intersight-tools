#======================================\n
# ICO Answers: Azure Stack HCI\n
#======================================\n
---\n
{{ $azurestack := .global.workflow.input.azurestack }}
{{ $intersight := .global.workflow.input.intersight }}
{{ $protocols := .global.workflow.input.protocols }}
{{ $windows_install := .global.workflow.input.windows_install }}
protocols:\n
{{ if index $protocols "dhcp_servers" }}
  dhcp_servers:\n
{{ range $i, $dhcps := $protocols.dhcp_servers }}
    - {{ $dhcps }}\n
{{ end }}
{{ else }}
  dhcp_servers: []\n
{{ end }}
{{ if index $protocols "dns_domains" }}
  dns_domains:\n
{{ range $i, $dnsdomains := $protocols.dns_domains }}
    - {{ $dnsdomains }}\n
{{ end }}
{{ else }}
  dns_domains: []\n
{{ end }}
{{ if index $protocols "dns_servers" }}
  dns_servers:\n
{{ range $i, $dnsservers := $protocols.dns_servers }}
    - {{ $dnsservers }}\n
{{ end }}
{{ else }}
  dns_servers: []\n
{{ end }}
  timezone: {{ if index $protocols "timezone" }}{{ $protocols.timezone }}{{ else }}Etc/GMT{{ end }}\n
{{ if index $protocols "ntp_servers" }}
  ntp_servers:\n
{{ range $i, $ntpservers := $protocols.ntp_servers }}
    - {{ $ntpservers }}\n
{{ end }}
{{ else }}
  ntp_servers: []\n
{{ end }}
azurestack:\n
  - active_directory:\n
      administrator: {{ if index $azurestack.active_directory "administrator" }}{{ $azurestack.active_directory.administrator }}{{ else }}administrator@example.com{{ end }}\n
      azurestack_admin: {{ if index $azurestack "azurestack_admin" }}{{ $azurestack.azurestack_admin }}{{ else }}hciadmin@example.com{{ end }}\n
      azurestack_ou: {{ if index $azurestack "azurestack_ou" }}{{ $azurestack.azurestack_ou }}{{ else }}AzureStack{{ end }}\n
      azurestack_prefix: {{ if index $azurestack "azurestack_prefix" }}{{ $azurestack.azurestack_prefix }}{{ else }}AzS{{ end }}\n
      domain: {{ if index $azurestack.active_directory "domain" }}{{ $azurestack.active_directory.domain }}{{ else }}example.com{{ end }}\n
    clusters:\n
{{ range $i, $cluster := $azurestack.clusters }}
      - name: {{ if index $cluster "name" }}{{ $cluster.name }}{{ else }}CLUSTER01{{ end }}\n
        members:\n
{{ range $e, $member := $cluster.members }}
          - cimc: {{ if index $member "cimc" }}{{ $member.cimc }}{{ else }}198.18.1.1{{ end }}\n
            hostname: {{ if index $member "hostname" }}{{ $member.hostname }}{{ end }}\n
{{ end }}
{{ end }}
    organization: {{ if index $azurestack.active_directory "organization" }}{{ $azurestack.active_directory.organization }}{{ else }}Example Company{{ end }}\n
{{ if eq $azurestack.config_witness true }}
file_share_witness:\n
  host: {{ if index $azurestack.file_share_witness "host" }}{{ $azurestack.file_share_witness.host }}{{ else }}''{{ end }}\n
  share_name: {{ if index $azurestack.file_share_witness "share_name" }}{{ $azurestack.file_share_witness.share_name }}{{ else }}''{{ end }}\n
  type: domain\n
{{ end }}
install_source: {{ if index .global.workflow.input "install_source" }}'{{ .global.workflow.input.install_source }}'{{ else }}intersight{{ end }}\n
{{ if eq .global.workflow.input.install_source "wds" }}
install_server:\n
  drivers_cd_mount: {{ if index .global.workflow.input "wds" }}'{{ .global.workflow.input.wds.drivers_cd_mount }}'{{ else }}'F:'{{ end }}\n
  hostname: {{ if index .global.workflow.input "wds" }}'{{ .global.workflow.input.wds.hostname }}'{{ else }}reminstall.example.com{{ end }}\n
  reminst_drive: {{ if index .global.workflow.input "wds" }}'{{ .global.workflow.input.wds.reminst_drive }}'{{ else }}'F:'{{ end }}\n
  reminst_share: {{ if index .global.workflow.input "wds" }}'{{ .global.workflow.input.wds.reminst_share }}'{{ else }}reminst{{ end }}\n
{{ else }}
os_install_image: {{ if index .global.workflow.input "iso_image" }}'{{ .global.workflow.input.iso_image }}'{{ else }}dummy123{{ end }}\n
server_configuration_utility: {{ if index .global.workflow.input "scu_image" }}'{{ .global.workflow.input.scu_image }}'{{ else }}dummy123{{ end }}\n
{{ end }}
windows_install:\n
  language_pack: {{ if index $windows_install "language_pack" }}'{{ $windows_install.language_pack }}'{{ else }}'English - United States'{{ end }}\n
  layered_driver: {{ if index $windows_install "layered_driver" }}'{{ $windows_install.layered_driver }}'{{ else }}'0'{{ end }}\n
{{ if eq .global.workflow.input.config_proxy true }}
proxy:\n
  url: {{ if index .global.workflow.input.proxy "url" }}{{ .global.workflow.input.proxy.url }}{{ else }}''{{ end }}\n
  username: {{ if index .global.workflow.input.proxy "username" }}{{ .global.workflow.input.proxy.username }}{{ else }}''{{ end }}\n
{{ end }}
imm_transition: {{ .global.workflow.input.imm_transition.hostname }}\n
intersight:\n
  - organization: {{ if index $intersight "organization" }}{{ $intersight.organization }}{{ end }}\n
    cimc_default: {{ if index $intersight "cimc_default" }}{{ $intersight.cimc_default }}{{ else }}false{{ end }}\n
    firmware: {{ if index $intersight "firmware" }}{{ $intersight.firmware }}{{ else }}4.2(3e){{ end }}\n
    policies:\n
      local_user: {{ if index $intersight.policies "local_user" }}{{ $intersight.policies.local_user }}{{ end }}\n
      prefix: {{ if index $intersight.policies "prefix" }}{{ $intersight.policies.prefix }}{{ end }}\n
      snmp:\n
        contact: {{ if index $intersight.policies.snmp "contact" }}{{ $intersight.policies.snmp.contact }}{{ else }}admin@example.com{{ end }}\n
        location: {{ if index $intersight.policies.snmp "location" }}{{ $intersight.policies.snmp.location }}{{ else }}Example Company{{ end }}\n
        username: {{ if index $intersight.policies.snmp "username" }}{{ $intersight.policies.snmp.username }}{{ else }}snmpadmin{{ end }}\n
{{ if index $intersight.policies.snmp "snmp_servers" }}
        servers:\n
{{ range $i, $snmp_servers := $intersight.policies.snmp.snmp_servers }}
          - {{ $snmp_servers }}\n
{{ end }}
{{ else }}
        servers: []\n
{{ end }}
      syslog:\n
{{ if index $intersight.policies "syslog_servers" }}
        servers:\n
{{ range $i, $syslog_servers := $intersight.policies.syslog_servers }}
          - {{ $syslog_servers }}\n
{{ end }}
{{ else }}
        servers: []\n
{{ end }}
nxos_configure: {{ if index .global.workflow.input "config_nxos" }}{{ .global.workflow.input.config_nxos }}{{ else }}false{{ end }}\n
{{ if eq .global.workflow.input.config_nxos true }}
nxos:\n
  - username: {{ if index .global.workflow.input.nxos "username" }}{{ .global.workflow.input.nxos.username }}{{ end }}\n
{{ if index .global.workflow.input.nxos "switches" }}
    switches:\n
{{ range $i, $switch := .global.workflow.input.nxos.switches }}
      - hostname: {{ if index $switch "hostname" }}{{ $switch.hostname }}{{ end }}\n
        breakout_speed: {{ if index $switch "breakout_speed" }}{{ $switch.breakout_speed }}{{ else }}25G{{ end }}\n
        switch_type: {{ if index $switch "switch_type" }}{{ $switch.switch_type }}{{ else }}network{{ end }}\n
{{ if index $switch "configure_vpc" }}
        vpc_config:\n
          domain_id: {{ if index $switch "vpc_domain_id" }}{{ $switch.vpc_domain_id }}{{ end }}\n
          keepalive_ip: {{ if index $switch "vpc_keepalive_ip" }}{{ $switch.vpc_keepalive_ip }}{{ end }}\n
{{ if index $switch "vpc_keepalive_ports" }}
          keepalive_ports:\n
{{ range $i, $vpc_keepalive_ports := $switch.vpc_keepalive_ports }}
            - {{ $vpc_keepalive_ports }}\n
{{ end }}
{{ else }}
          keepalive_ports: []\n
{{ end }}
{{ if index $switch "vpc_peer_ports" }}
          peer_ports:\n
{{ range $i, $vpc_peer_ports := $switch.vpc_peer_ports }}
            - {{ $vpc_peer_ports }}\n
{{ end }}
{{ else }}
          peer_ports: []\n
{{ end }}
{{ end }}
{{ end }}
{{ else }}
    switches: []\n
{{ end }}
{{ else }}
nxos: []\n
{{ end }}
{{ if index .global.workflow.input "vlans" }}
vlans:\n
{{ range $i, $vlan := .global.workflow.input.vlans }}
  - vlan_type: {{ if index $vlan "vlan_type" }}{{ $vlan.vlan_type }}{{ else }}vm{{ end }}\n
    vlan_id: {{ if index $vlan "vlan_id" }}{{ $vlan.vlan_id }}{{ end }}\n
    name: {{ if index $vlan "name" }}{{ $vlan.name }}{{ end }}\n
    network: {{ if index $vlan "network" }}{{ $vlan.network }}{{ end }}\n
    configure_l2: {{ if index $vlan "configure_l2" }}{{ $vlan.configure_l2 }}{{ else }}false{{ end }}\n
    configure_l3: {{ if index $vlan "configure_l3" }}{{ $vlan.configure_l3 }}{{ else }}false{{ end }}\n
    switch_type: {{ if index $vlan "switch_type" }}{{ $vlan.switch_type }}{{ end }}\n
    ranges:\n
      server: {{ if index $vlan "ranges_server" }}{{ $vlan.ranges_server }}{{ end }}\n
{{ end }}
{{ else }}
vlans: []\n
{{ end }}