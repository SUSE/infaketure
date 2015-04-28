#!/usr/bin/python
#
# An attempt to create a fake registration
# Author: BOFH <bo@suse.de>
#

import sys
import os
from optparse import Option
from optparse import OptionParser
import random
import uuid
from xml.dom import minidom as dom
import fakecheck

sys.path.append("/usr/share/rhn/")

from up2date_client import rhnreg
from up2date_client import hardware
from up2date_client import pkgUtils
from up2date_client import up2dateErrors
from up2date_client import rhncli
from suseRegister.info import getProductProfile as get_suse_product_profile


class CMDBProfile(object):
    """
    System profile container that has all the data about fake system.
    """

    class CPException(Exception):
        """
        CMDBProfile-specific exceptions.
        """

    def __init__(self, hostname, idx=0):
        """
        Constructor.

        Parameters
          idx:
             Index of the node. This is like "seed" to the random, to make distinct MAC, IPs etc.
        """
        self.idx = idx
        self.params = dict()
        self.hostname = hostname
        self.id = self.hostname
        self.packages = pkgUtils.getInstalledPackageList(getArch=(rhnreg.cfg['supportsExtendedPackageProfile'] and 1 or 0))

        self._gen_hardware()
        self._get_virtuid()

    def _get_virtuid(self):
        """
        Get virt UUID
        """
        (virt_uuid, virt_type) = rhnreg.get_virt_info()
        if virt_uuid is not None:
            self.params['virt_uuid'] = virt_uuid
            self.params['virt_type'] = virt_type

    def _gen_hardware(self):
        """
        Generate hardware information.
        """
        self.hardware = hardware.Hardware()
        self.primary_ip = self._gen_ip()
        for h in self.hardware:
            if h['class'] == 'NETINFO':
                h['hostname'] = self.hostname
                h['ipaddr'] = self.primary_ip
            elif h['class'] == 'NETINTERFACES':
                for k, v in h.items():
                    if k in ['class', 'lo']:
                        continue
                    if not v['ipaddr']:
                        v['hwaddr'] = self._gen_mac()
                        continue
                    v['ipaddr'] = self.primary_ip
                    v['hwaddr'] = self._gen_mac()
                    for ipv6addr in v['ipv6']:
                        if ipv6addr.get('addr'):
                            ipv6addr['addr'] = self._gen_ip(ipv6=True)


    def _gen_mac(self):
        """
        Generate a fake MAC address.
        """
        slots = hex(int(str(self.idx).zfill(4))).split("x")[-1].zfill(4)
        return "de:af:be:ef:{0}:{1}".format(*[slots[:2], slots[2:]])

    def _gen_ip(self, ipv6=False):
        """
        Generate random IP address.
        """
        adr = list()
        for x in range(ipv6 and 8 or 4):
            adr.append(random.randint(0xa, ipv6 and 0xffff or 0xff))

        return (ipv6 and ":" or ".").join([ipv6 and hex(e).split("x")[-1] or str(e) for e in adr])


class XMLData(object):
    """
    Parse SID data.
    """
    def __init__(self):
        self.dom = None
        self.members = None

    def load(self, src):
        self.dom = dom.parseString(src)
        self._get_members()

    def _get_members(self):
        self.members = dict()
        for member_node in self.dom.getElementsByTagName('member'):
            name = member_node.getElementsByTagName('name')[0].childNodes[0].nodeValue
            if member_node.getElementsByTagName('value')[0].getElementsByTagName('string'):
                self.members[name] = member_node.getElementsByTagName('string')[0].childNodes[0].nodeValue

    def get_member(self, name):
        """
        Get SID member.
        """
        return self.members.get(name) or 'N/A'


class VirtualRegistration(object):
    """
    Virtual registration.
    """

    class VRException(Exception):
        """
        VirtualRegistration-specific exceptions.
        """

    def __init__(self, serverfqdn):
        """
        Constructor.
        """
        self._initialize()

        rhnreg.cfg.set("serverURL", "https://{0}/XMLRPC".format(serverfqdn))
        rhnreg.getCaps()

        def _getProductProfile():
            '''
            Mocker. Needs to be saved to the SQLite!
            '''
            profile = get_suse_product_profile()
            profile['guid'] = uuid.uuid4().hex
            profile['secret'] = uuid.uuid4().hex

            return profile

        rhnreg.getProductProfile = _getProductProfile

    def _initialize(self):
        """
        Initialize command line options.
        """
        opt = OptionParser(version="Bloody Alpha, 0.1")
        opt.add_option("--activationkey", action="store", dest="key", help="Specify an activation key")
        opt.add_option("--sslCACert", action="store", dest="cacert", help="Specify a file to use as the ssl CA cert")

        self.options, self.args = opt.parse_args()

        # Check the required parameters
        if not self.options.key:
            sys.argv.append("-h")
            opt.parse_args()

        # Setup CA Cert
        if self.options.cacert:
            rhnreg.cfg.set("sslCACert", self.options.cacert)
        if not os.path.exists(rhnreg.cfg["sslCACert"]):
            raise VirtualRegistration.VRException(
                "SSL CA Certificate was not found at {0}".format(rhnreg.cfg["sslCACert"]))

    def register(self, profile):
        """
        Register one system based on profile.
        """
        sid = None
        xmldata = XMLData()
        rhnreg.cfg.set("systemIdPath", "/etc/sysconfig/rhn/systemid-{0}".format(profile.id))
        try:
            sid = rhnreg.registerSystem(token=self.options.key,
                                        profileName=profile.id,
                                        other=profile.params)
            xmldata.load(sid)
            print "Registered {0} with System ID {1}".format(xmldata.get_member('profile_name'),
                                                             xmldata.get_member('system_id'))
        except (up2dateErrors.AuthenticationTicketError,
                up2dateErrors.RhnUuidUniquenessError,
                up2dateErrors.CommunicationError,
                up2dateErrors.AuthenticationOrAccountCreationError), e:
            print "Registration error: {0}".format(e.errmsg)
            return

        rhnreg.sendHardware(sid, profile.hardware)
        rhnreg.sendPackages(sid, profile.packages)
        rhnreg.sendVirtInfo(sid)
        rhnreg.startRhnsd()

        fakecheck.CheckCli(rhnreg.cfg, sid).main()


if __name__ == '__main__':
    try:
        vr = VirtualRegistration("sumabench1.suse.de")
        for x in range(5):
            vr.register(CMDBProfile("zoo{0}.suse.de".format(x), idx=x))
    except VirtualRegistration.VRException as ex:
        print "Error:\n  {0}\n".format(ex)
    except Exception as ex:
        raise ex
