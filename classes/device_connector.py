#!/usr/bin/env python3
"""Intersight Device Connector API access classes."""

#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import pcolor
    from dotmap import DotMap
    from time import sleep
    from xml.etree import ElementTree
    import re, requests, subprocess, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def requests_op(op, uri, header, ro_json, body):
    """perform op and retry on 5XX status errors"""
    for _ in range(10):
        if op == 'get': resp = requests.get(uri, verify=False, headers=header)
        elif op == 'put': resp = requests.put(uri, verify=False, headers=header, json=body)
        else:
            ro_json.ApiError = f"unsupported op {op}"
            break
        if re.match(r'2..', str(resp.status_code)):
            ro_json.pop('ApiError', None)
            if op == 'get':
                if isinstance(resp.json(), list): ro_json = DotMap(resp.json()[0])
                else: ro_json.ApiError = f"{op} {uri} {resp.status_code}"
            break
        else:
            ro_json.ApiError = f"{op} {uri} {resp.status_code}"
            if re.match(r'5..', str(resp.status_code)): sleep(1); continue
            else: break
    return ro_json


class device_connector(object):
    """Intersight Device Connector API superclass.
    Managed endpoint access information (hostname, username) and configuration data should be provided in the device dictionary parameter.
    """
    def __init__(self, device):
        self.logged_in = False
        self.auth_header = ''
        self.device = device
        if self.device.device_type == 'ucspe': hmethod = 'http'
        else: hmethod = 'https'
        self.connector_uri = f"{hmethod}://{self.device.hostname}/connector"
        self.systems_uri   = f"{self.connector_uri}/Systems"
        self.mgmt_if_uri   = f"{hmethod}://{self.device.hostname}/visore.html?f=class&q=mgmtIf"

    def get_status(self):
        """Check current connection status."""
        ro_json = DotMap(AdminState=False)
        # get admin, connection, and claim state
        ro_json = requests_op(op='get', uri=self.systems_uri, header=self.auth_header, ro_json=ro_json, body={})
        return ro_json

    def configure_connector(self):
        """Check current Admin state and enable the Device Connector if not currently enabled."""
        ro_json = DotMap(AdminState=False)
        for _ in range(4):
            ro_json = self.get_status()
            if ro_json.AdminState: break
            else:
                # enable the device connector
                ro_json = requests_op(
                    op='put', uri=self.systems_uri, header=self.auth_header, ro_json=ro_json,
                    body={'AdminState': True})
                if ro_json.get('ApiError'): break
        return ro_json

    def configure_access_mode(self, ro_json):
        """Configure the Device Connector access mode (ReadOnlyMode True/False)."""
        for _ in range(4):
            # device read_only setting is a bool (True/False)
            ro_json = requests_op(
                op='put', uri=self.systems_uri, header=self.auth_header, ro_json=ro_json,
                body={'ReadOnlyMode': self.device.read_only})
            if ro_json.get('ApiError'): break
            # confirm setting has been applied
            ro_json = self.get_status()
            if ro_json['ReadOnlyMode'] == self.device.read_only: break
        return ro_json

    def configure_dns(self, result):
        """Configure the DNS Settings if Connection State is DNSMisconfigured)."""
        if len(self.device.dns_servers) > 0:
            # setup defaults for DNS servers
            dns_servers = self.device.dns_servers
            dns_preferred = dns_servers[0]
            if len(dns_servers) > 1: dns_alternate = dns_servers[1]
            else: dns_alternate = ''
            for _ in range(4):
                xml_body = f"<configConfMo cookie=\"{self.xml_cookie}\" inHierarchical=\"false\" classId=\"mgmtIf\"/><inConfig><mgmtIf dn=\"sys/rack-unit-1/mgmt/if-1\" dnsPreferred=\"{dns_preferred}\" dnsAlternate=\"{dns_alternate}\"/></inConfig></configConfMo>"
                resp = requests.post(url=self.xml_uri, verify=False, data=xml_body)
                if re.match(r'2..', str(resp.status_code)):
                    xml_tree = ElementTree.fromstring(resp.content)
                    for child in xml_tree:
                        for subchild in child:
                            xdict = subchild.attrib
                            if xdict.get('dhcpEnable'):
                                result[self.device.hostname].dns_alternate  = xdict['dnsPreferred']
                                result[self.device.hostname].dns_preferred  = xdict['dnsAlternate']
                                result[self.device.hostname].changed = True
                    break
                else:
                    pcolor.Red(resp.status_code)
                    pcolor.Red('DNS Configuration Failed.  device_connector.py line 114')
            if not re.match(r'2..', str(resp.status_code)):
                result.ApiError = f"post {self.xml_uri} {resp.status_code} management interface."
        return result

    def configure_proxy(self, ro_json, result):
        """Configure the Device Connector proxy if proxy settings (hostname, port) were provided)."""
        # put proxy settings.  If no settings were provided the system settings are not changed
        if len(self.device.proxy_host) > 0 and len(self.device.proxy_port) > 0:
            # setup defaults for proxy settings
            if not self.device.get('proxy_password'): self.device.proxy_password = ''
            if not self.device.get('proxy_username'): self.device.proxy_username = ''
            proxy_payload = {
                'ProxyHost': self.device.proxy_host,
                'ProxyPassword': self.device.proxy_password,
                'ProxyPort': int(self.device.proxy_port),
                'ProxyType': 'Manual',
                'ProxyUsername': self.device.proxy_username,
            }
            proxy_uri = f"{self.connector_uri}/HttpProxies"
            for _ in range(4):
                # check current setting
                ro_json = requests_op(op='get', uri=proxy_uri, header=self.auth_header, ro_json=ro_json, body={})
                if ro_json.get('ApiError'): break
                if ro_json.ProxyHost == self.device.proxy_host and ro_json.ProxyPort == int(self.device.proxy_port): break
                else:
                    result[self.device.hostname].msg += f"#Setting proxy : {self.device.proxy_host} {self.device.proxy_port}\n"
                    ro_json = requests_op(op='put', uri=proxy_uri, header=self.auth_header, ro_json=ro_json, body=proxy_payload)
                    if ro_json.get('ApiError'): break
                    result[self.device.hostname].changed = True
            if not ro_json.get('ApiError'):
                # get updated status
                ro_json = self.get_status()
        return ro_json

    def get_claim_info(self, ro_json):
        """Get the Device ID and Claim Code from the Device Connector."""
        claim_resp = {}
        device_id = ''
        claim_code = ''
        # get device id and claim code
        id_uri = f"{self.connector_uri}/DeviceIdentifiers"
        ro_json = requests_op(op='get', uri=id_uri, header=self.auth_header, ro_json=ro_json, body={})
        if not ro_json.get('ApiError'):
            device_id = ro_json['Id']

            claim_uri = f"{self.connector_uri}/SecurityTokens"
            ro_json = requests_op(op='get', uri=claim_uri, header=self.auth_header, ro_json=ro_json, body={})
            if not ro_json.get('ApiError'): claim_code = ro_json['Token']
            else: claim_resp['ApiError'] = ro_json['ApiError']
        else: claim_resp['ApiError'] = ro_json['ApiError']
        return(claim_resp, device_id, claim_code)

    def management_interface(self, result):
        """Get Management Interface settings."""
        result[self.device.hostname].enable_dhcp      = 'no'
        result[self.device.hostname].enable_dhcp_dns  = 'no'
        result[self.device.hostname].enable_ipv6      = 'no'
        result[self.device.hostname].enable_ipv6_dhcp = 'no'
        for _ in range(4):
            xml_body = f"<configResolveClass cookie=\"{self.xml_cookie}\" inHierarchical=\"false\" classId=\"mgmtIf\"/>"
            resp = requests.post(url=self.xml_uri, verify=False, data=xml_body)
            if re.match(r'2..', str(resp.status_code)):
                xml_tree = ElementTree.fromstring(resp.content)
                for child in xml_tree:
                    for subchild in child:
                        xdict = subchild.attrib
                        if xdict.get('dhcpEnable'):
                            result[self.device.hostname].enable_dhcp      = xdict['dhcpEnable']
                            result[self.device.hostname].enable_dhcp_dns  = xdict['dnsUsingDhcp']
                            result[self.device.hostname].enable_ipv6      = xdict['v6extEnabled']
                            result[self.device.hostname].enable_ipv6_dhcp = xdict['v6dhcpEnable']
                break
        if not re.match(r'2..', str(resp.status_code)):
            result.ApiError = f"post {self.xml_uri} {resp.status_code} management interface."
        return result

class hx_device_connector(device_connector, object):
    """HyperFlex (HX) Device Connector subclass.
    HX REST API session cookie is used to authenticate Device Connector API access.
    """
    def __init__(self, device):
        super(hx_device_connector, self).__init__(device)
        # create HX REST API session
        # --------------------------------
        self.hx_rest_uri = f"https://{self.device.hostname}/aaa/v1/auth?grant_type=password"
        hx_rest_header = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        hx_rest_body = {
            'username': self.device.username,
            'password': self.device.password,
            'client_id': 'HxGuiClient',
            'client_secret': 'Sunnyvale',
            'redirect_uri': 'http://localhost:8080/aaa/redirect'
        }
        resp = requests.post(self.hx_rest_uri, verify=False, headers=hx_rest_header, json=hx_rest_body)
        if re.match(r'2..', str(resp.status_code)):
            ro_json = resp.json(); atoken = ro_json['access_token']; rtoken = ro_json['refresh_token']
            hx_cookie_str = f"test; tokenType=Basic; locale=en; refreshToken={rtoken}; token={atoken}"
            self.auth_header = {'Cookie': hx_cookie_str}
            self.logged_in = True

    def logout(self):
        """Logout of HX REST API session if currently logged in."""
        if self.logged_in:
            # logout TBD
            self.logged_in = False


class ucs_device_connector(device_connector, object):
    """UCS Manager (UCSM) Device Connector subclass.
    UCS XML API session cookie is used to authenticate Device Connector API access.
    """
    def __init__(self, device):
        super(ucs_device_connector, self).__init__(device)
        # XML API login and create session cookie
        # --------------------------------
        self.xml_uri = f"https://{self.device.hostname}/nuova"
        xml_body = f"<aaaLogin inName=\"{self.device.username}\" inPassword=\"{self.device.password}\"/>"
        resp = requests.post(self.xml_uri, verify=False, data=xml_body)
        if re.match(r'2..', str(resp.status_code)):
            xml_tree = ElementTree.fromstring(resp.content)
            if not xml_tree.attrib.get('outCookie'): return
            self.xml_cookie = xml_tree.attrib['outCookie']
            self.auth_header = {'ucsmcookie': f"ucsm-cookie={self.xml_cookie}"}
            self.logged_in = True

    def logout(self):
        """Logout of IMC/UCSM API session if currently logged in."""
        if self.logged_in:
            # XML API logout
            # --------------------------------
            if self.device.device_type == 'imc':
                xml_body = f"<aaaLogout cookie=\"{self.xml_cookie}\" inCookie=\"{self.xml_cookie}\"></aaaLogout>"
            else: xml_body = f"<aaaLogout inCookie=\"{self.xml_cookie}\"/>"
            requests.post(self.xml_uri, verify=False, data=xml_body)
            self.logged_in = False


class imc_device_connector(device_connector, object):
    """Integration Management Controller (IMC) Device Connector subclass.
    IMC web GUI (webgui) session cookie is used to authenticate Device Connector API access.
    """
    def __init__(self, device):
        super(imc_device_connector, self).__init__(device)
        # create IMC browser session (requires password generated by an outside utility)
        # imports for utility use are directly below so they are not required in non IMC environments
        # --------------------------------
        import get_data, os, platform, six
        import urllib.parse as URL
        password = six.b(self.device.password)
        system_type = platform.system()
        utils_extension = ''
        if system_type == 'Darwin': system_type = 'Mac'
        elif system_type == 'Windows': utils_extension = '.exe'
        utils_exe = f"{self.device.script_path}{os.sep}get_data{os.sep}{system_type}{os.sep}GetData{utils_extension}"
        try:
            user = self.device.username
            passphrase = subprocess.check_output([utils_exe, user])
            utils_password = get_data.E(passphrase, password)
            imc_login_str = f"user={URL.quote_plus(user)}&password={URL.quote_plus(utils_password.rstrip())}"
            imc_login_uri = f"https://{self.device.hostname}/data/login"
            referer = f"https://{self.device.hostname}/uiconnector/index.html"
            self.imc_header = {
                'Referer': referer,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            r = requests.post(imc_login_uri, verify=False, headers=self.imc_header, data=imc_login_str)
            if re.match(r'2..', str(r.status_code)):
                cookies = list(r.cookies.values())
                if cookies:
                    self.imc_session_cookie = cookies[0]
                    xml_tree = ElementTree.fromstring(r.content)
                    self.imc_session_id = xml_tree.find('sidValue').text
                    self.auth_header = {
                        'Cookie': f"sessionCookie={self.imc_session_cookie}",
                        'Referer': referer
                    }
                    self.logged_in = True
                else: pcolor.Cyan("Unable to login: ", imc_login_uri)
        except subprocess.CalledProcessError as sub_ret:
            pcolor.Cyan("Utils executable returns ", sub_ret.returncode, sub_ret.output)

    def logout(self):
        """Logout of IMC webgui session if currently logged in."""
        if self.logged_in:
            # IMC webgui session logout
            # --------------------------------
            self.imc_header['Cookie'] = f"sessionCookie={self.imc_session_cookie}"
            imc_logout_str = f"sessionID={self.imc_session_id}"
            imc_logout_uri = f"https://{self.device.hostname}/data/logout"
            requests.post(imc_logout_uri, verify=False, headers=self.imc_header, data=imc_logout_str)
            self.logged_in = False