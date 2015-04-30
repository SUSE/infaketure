#!/usr/bin/python
#
# Create a fake registrations in a bulk.
# Author: BOFH <bo@suse.de>
#

import sys
import os
from optparse import Option
from optparse import OptionParser
import random
import uuid
from xml.dom import minidom as dom
from fakereg import check
from fakereg import hostnames
from fakereg import store
from fakereg import spaceapi

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
        return str(self.members.get(name)) or 'N/A'


class VirtualRegistration(object):
    """
    Virtual registration.
    """

    class VRException(Exception):
        """
        VirtualRegistration-specific exceptions.
        """

    def __init__(self):
        """
        Constructor.
        """
        self.verbose = False
        self._initialize()

        self.api = spaceapi.SpaceAPI("http://{0}/rpc/api".format(self.options.fqdn))
        rhnreg.cfg.set("serverURL", "https://{0}/XMLRPC".format(self.options.fqdn))
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
        _dbstore_file = os.path.join(os.path.abspath("."), "store.db")
        opt = OptionParser(version="Bloody Alpha, 0.1")
        opt.add_option("-m", "--manager-hostname", action="store", dest="fqdn",
                       help="Specify an activation key")
        opt.add_option("-k", "--activation-key", action="store", dest="key",
                       help="Specify an activation key")
        opt.add_option("-c", "--sslCACert", action="store", dest="cacert",
                       help="Specify a file to use as the ssl CA cert")
        opt.add_option("-a", "--hosts-amount", action="store", dest="amount",
                       help="Specify an amount of fake hosts to be registered. Default 5.")
        opt.add_option("-b", "--base-name", action="store", dest="base",
                       help="Specify a base name for a fake hosts, so it will go incrementally, "
                            "like FAKE0, FAKE1 ... . By default random host names if cracklib is installed "
                            "or 'test' as base name.")
        opt.add_option("-d", "--database-file", action="store", dest="dbfile",
                       help="Specify a path to SQLite3 database. "
                            "Default is '{0}'.".format(_dbstore_file))
        opt.add_option("-r", "--refresh", action="store_true", dest="refresh",
                       help="Run rhn_check on registered systems.")
        opt.add_option("-v", "--verbose", action="store_true", dest="verbose",
                       help="Talk to me!")
        opt.add_option("-f", "--flush", action="store_true", dest="flush",
                       help="Flush all the systems on the SUSE Manager.")
        opt.add_option("-u", "--user", action="store", dest="user",
                       help="User ID for the administrator.")
        opt.add_option("-p", "--password", action="store", dest="password",
                       help="Password for the administrator")

        self.options, self.args = opt.parse_args()

        # Check the required parameters
        if (not self.options.refresh and not self.options.flush) \
                and (not self.options.key or not self.options.fqdn):
            sys.argv.append("-h")
            opt.parse_args()

        # Setup CA Cert
        if self.options.cacert:
            rhnreg.cfg.set("sslCACert", self.options.cacert)
        if not os.path.exists(rhnreg.cfg["sslCACert"]):
            raise VirtualRegistration.VRException(
                "SSL CA Certificate was not found at {0}".format(rhnreg.cfg["sslCACert"]))

        try:
            self.amount = int(self.options.amount and self.options.amount or "5")
        except Exception as error:
            raise VirtualRegistration.VRException("Wrong amount of fake hosts: {0}".format(self.options.amount))

        if self.options.dbfile:
            _dbstore_file = self.options.dbfile

        if self.options.verbose:
            self.verbose = True

        if self.options.flush:
            if not self.options.user or not self.options.password:
                raise VirtualRegistration.VRException(
                    "User and/or password must be given to authorise against SUSE Manager.")

        self.db = store.DBOperations(_dbstore_file)
        self.db.open()

    def main(self):
        """
        Main
        """
        if self.options.refresh:
            self.refresh()
        elif self.options.flush:
            self.flush()
        else:
            for idx in range(vr.amount):
                vr.register(CMDBProfile(fh(), idx=idx))

        vr.db.close()

    def flush(self, wipe=False):
        """
        Flush the SUSE Manager and reset the internal DB.
        """
        self.api.login(self.options.user, self.options.password)

        host_sids = [host.sid for host in self.db.get_all_hosts()]
        # Flush hosts in SUMA
        systems = self.api.system.get_systems()
        for system in systems:
            if not wipe and system['sid'] in host_sids or wipe:
                if self.verbose:
                    print "Removing {0} ({1})".format(system['name'], system['sid'])
                self.api.system.delete_system_by_sid(system['id'])
        if self.verbose and systems:
            print "Done"

        # Flush local database
        if systems:
            if self.verbose:
                print "Purging the database."
            self.db.purge()
            if self.verbose:
                print "Done"
        else:
            if self.verbose:
                print "No systems found."

    def refresh(self):
        """
        Refresh profiles by running rhn_check over them.
        """
        for host in self.db.get_all_hosts():
            if self.verbose:
                print "Refreshing {0} ({1})".format(host.hostname, host.sid)
            cli = check.CheckCli(self.db.get_host_config(host.id), host.profile, hostname=host.hostname)
            cli.verbose = self.verbose
            cli.main()

    def register(self, profile):
        """
        Register one system based on profile.
        """
        sid = None
        xmldata = XMLData()
        try:
            sid = rhnreg.registerSystem(token=self.options.key,
                                        profileName=profile.id,
                                        other=profile.params)
            xmldata.load(sid)
            print "Registered {0} with System ID {1}".format(xmldata.get_member('profile_name'),
                                                             xmldata.get_member('system_id'))
            host_id = self.db.get_next_id("hosts") + 1
            self.db.cursor.execute("INSERT INTO hosts (ID, SID, HOSTNAME, SID_XML) VALUES (?, ?, ?, ?)",
                                   (host_id, xmldata.get_member("system_id"), xmldata.get_member("profile_name"), sid,))
            hardware_id = self.db.get_next_id("hardware") + 1
            self.db.cursor.execute("INSERT INTO hardware (ID, HID, BODY) VALUES (?, ?, ?)",
                                   (hardware_id, host_id, str(profile.hardware),))
            cfg_id = self.db.get_next_id("configs") + 1
            self.db.cursor.execute("INSERT INTO configs (ID, HID, BODY) VALUES (?, ?, ?)",
                                   (cfg_id, host_id, str(dict(rhnreg.cfg.items()))))
            packages_id = self.db.get_next_id("configs") + 1
            self.db.cursor.execute("INSERT INTO packages (ID, HID, BODY) VALUES (?, ?, ?)",
                                   (packages_id, host_id, str(profile.packages)))
            self.db.connection.commit()
        except (up2dateErrors.AuthenticationTicketError,
                up2dateErrors.RhnUuidUniquenessError,
                up2dateErrors.CommunicationError,
                up2dateErrors.AuthenticationOrAccountCreationError), e:
            print "WARNING: Registration error: {0}".format(e.errmsg)
            return

        rhnreg.sendHardware(sid, profile.hardware)
        rhnreg.sendPackages(sid, profile.packages)
        rhnreg.sendVirtInfo(sid)
        rhnreg.startRhnsd()

        check.CheckCli(rhnreg.cfg, sid, hostname=xmldata.get_member('profile_name')).main()


if __name__ == '__main__':
    #try:
    if 1:
        fh = hostnames.FakeNames(fqdn=True)
        vr = VirtualRegistration()
        vr.main()
    #except VirtualRegistration.VRException as ex:
    #    print "Error:\n  {0}\n".format(ex)
    #except Exception as ex:
    #    raise ex
