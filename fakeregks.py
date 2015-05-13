#!/usr/bin/python
#
# Create a fake registrations in a bulk.
# Author: BOFH <bo@suse.de>
#

import sys
import os
import time
import getpass
from optparse import OptionParser
import random
import uuid
from xml.dom import minidom as dom
import multiprocessing

from fakereg import check
from fakereg import hostnames
from fakereg import store
from fakereg import spaceapi
from fakereg import loadproc
from fakereg import pcp

sys.path.append("/usr/share/rhn/")

from up2date_client import rhnreg
from up2date_client import hardware
from up2date_client import pkgUtils
from up2date_client import up2dateErrors
from suseRegister.info import getProductProfile as get_suse_product_profile


class CMDBProfile(store.CMDBBaseProfile):
    """
    System specific profile container that has all the data about fake system.
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
        store.CMDBBaseProfile.__init__(self)
        self.idx = idx
        self.params = dict()
        self.hostname = hostname
        self.id = self.hostname
        self.packages = pkgUtils.getInstalledPackageList(
            getArch=(rhnreg.cfg['supportsExtendedPackageProfile'] and 1 or 0))
        self.src = None
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
        self._pcp_metrics_path = None
        self._initialize()

        self.api = spaceapi.SpaceAPI("http://{0}/rpc/api".format(self.options.fqdn))
        rhnreg.cfg.set("serverURL", "https://{0}/XMLRPC".format(self.options.fqdn))
        rhnreg.getCaps()

        def _getProductProfile():
            '''
            Mocker. Needs to be saved to the SQLite!
            '''
            time.sleep(0.1)
            profile = get_suse_product_profile()
            profile['guid'] = uuid.uuid4().hex
            profile['secret'] = uuid.uuid4().hex

            return profile

        rhnreg.getProductProfile = _getProductProfile
        self.__processes = list()

    def start_process(self, process, join=False):
        """
        Start process and join it.
        """
        if not join:
            process.daemon = True
        process.start()

        if join:
            process.join()
        else:
            self.__processes.append(process)

    def wait_processes(self):
        """
        Wait until processes finished.
        """
        while True:
            p_buff = list()
            for process in self.__processes:
                if process.is_alive():
                    p_buff.append(process)
            self.__processes = p_buff[:]
            if not self.__processes:
                break

    def _initialize(self):
        """
        Initialize command line options.
        """
        _dbstore_file = os.path.join(os.path.abspath("."), "store.db")
        self._pcp_metrics_path = os.path.join(os.path.abspath("."), ".pcp-metrics")
        opt = OptionParser(version="Bloody Alpha, 0.1")
        opt.add_option("-m", "--manager-hostname", action="store", dest="fqdn",
                       help="Specify an activation key.")
        opt.add_option("-k", "--activation-key", action="store", dest="key",
                       help="Specify an activation key.")
        opt.add_option("-c", "--sslCACert", action="store", dest="cacert",
                       help="Specify a file to use as the ssl CA cert.")
        opt.add_option("-a", "--hosts-amount", action="store", dest="amount",
                       help="Specify an amount of fake hosts to be registered. Default 5.")
        opt.add_option("-b", "--base-name", action="store", dest="base",
                       help="Specify a base name for a fake hosts, so it will go incrementally, "
                            "like FAKE0, FAKE1 ... . By default random host names if cracklib is installed "
                            "or 'test' as base name.")
        opt.add_option("-d", "--database-file", action="store", dest="dbfile",
                       help="Specify a path to SQLite3 database. "
                            "Default is '{0}'.".format(_dbstore_file))
        opt.add_option("-t", "--pcp-metrics", action="store", dest="pcp_path",
                       help="Specify a path to PCP metrics dump. "
                            "Default is '{0}'.".format(self._pcp_metrics_path))
        opt.add_option("-l", "--simulate-scenario", action="store", dest="scenario",
                       help="Path to a scenario that simulates particular load.")
        opt.add_option("-r", "--refresh", action="store_true", dest="refresh",
                       help="Run rhn_check on registered systems.")
        opt.add_option("-v", "--verbose", action="store_true", dest="verbose",
                       help="Talk to me!")
        opt.add_option("-f", "--flush", action="store_true", dest="flush",
                       help="Flush all the systems on the SUSE Manager.")
        opt.add_option("-u", "--user", action="store", dest="user",
                       help="User ID for the administrator.")
        opt.add_option("-p", "--password", action="store", dest="password",
                       help="Password for the administrator.")

        self.options, self.args = opt.parse_args()

        # Check the required parameters
        if not self.options.fqdn or ((not self.options.refresh
                                      and not self.options.flush
                                      and not self.options.scenario)
                                     and (not self.options.key)):
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

        if self.options.pcp_path:
            self._pcp_metrics_path = self.options.pcp_path

        if self.options.verbose:
            self.verbose = True

        if self.options.flush:
            if not self.options.user or not self.options.password:
                raise VirtualRegistration.VRException(
                    "User and/or password must be given to authorise against SUSE Manager.")

        self.db = store.DBOperations(_dbstore_file)
        self.db.open()

    def scenario(self):
        """
        Run scenario.
        """
        # 1. Scenario is extracted from SUMA as its working load.
        # 2. Run scenario scheduling on SUMA server, refresh affected clients
        self.api.login(self.options.user, self.options.password)

        runner = loadproc.LoadScenarioCaller(loadproc.LoadScheduleProcessor(self.db, self.api))
        runner.load_scenario(self.options.scenario)

        pcp_cfg = {
            pcp.PCPConnector.CFG_HOST: self.options.fqdn,
            pcp.PCPConnector.CFG_USER: getpass.getuser(),
        }
        if "pcp.snapshot" in runner.config:
            pcp_cfg[pcp.PCPConnector.CFG_PATH] = runner.config["pcp.snapshot"]

        _pcp = pcp.PCPConnector(pcp_cfg)
        for cfg_key, cfg_value in runner.config.items():
            metric_prefix = "pcp.metric."
            if cfg_key.startswith(metric_prefix):
                _pcp.probes[cfg_key.replace(metric_prefix, "")] = cfg_value or None
        _pcp.start()
        runner.run(callback=self.refresh)
        _pcp.stop()
        self._save_pcp_metrics(_pcp)
        _pcp.cleanup()

    def _save_pcp_metrics(self, pcp):
        """
        Save PCP metrics.
        """
        metrics_path = os.path.join(self._pcp_metrics_path,
                                    self.options.fqdn,
                                    time.strftime("%Y%m%d-%H%M%S", time.localtime()))
        os.makedirs(metrics_path)
        for probe in sorted(pcp.probes.keys()):
            metrics = pcp.get_metrics(probe)

            data_fh = open(os.path.join(metrics_path, "{0}.data".format(probe)), "w")
            idx = 0
            data_fh.write("# Metrics for {0}\n".format(probe))
            for data in metrics.get("data"):
                data_fh.write("{pm_index}\t{pm_data}\n".format(pm_index=idx, pm_data=data))
                idx += 1
            data_fh.write("\n")
            data_fh.close()
            metrics.pop("data")

            descr_fh = open(os.path.join(metrics_path, "{0}.info".format(probe)), "w")
            for ds_key in sorted(metrics.keys()):
                descr_fh.write("{pm_key}:\t{pm_value}\n".format(pm_key=ds_key, pm_value=metrics.get(ds_key)))
            descr_fh.close()

    def main(self):
        """
        Main
        """
        if self.options.scenario:
            self.scenario()
        elif self.options.refresh:
            self.refresh()
        elif self.options.flush:
            self.flush()
        else:
            fh = hostnames.FakeNames(fqdn=True)
            for profile in self.db.get_host_profiles():
                fh.add_history(profile.hostname)
            idx_offset = self.db.get_next_id("hosts")
            for idx in range(vr.amount):
                self.start_process(multiprocessing.Process(target=self.register,
                                                           args=(CMDBProfile(fh(), idx=(idx + idx_offset)),)),
                                   join=True)
        self.wait_processes()
        self.db.vacuum()
        self.db.close()

    def _flush_host_by_sid(self, sid):
        """
        Delete one host in a sync.
        """
        try:
            self.api.system.delete_system_by_sid(sid)
            self.db.delete_host_by_id(sid)
            self.db.connection.commit()
        except Exception as ex:
            print "Error deleting host:", ex

    def flush(self, wipe=False):
        """
        Flush the SUSE Manager and reset the internal DB.
        """
        self.api.login(self.options.user, self.options.password)

        host_sids = ["ID-{0}".format(host.sid) for host in self.db.get_host_profiles()]
        # Flush hosts in SUMA
        systems = self.api.system.get_systems()
        for system in systems:
            if not wipe and system['sid'] in host_sids or wipe:
                if self.verbose:
                    print "Removing {0} ({1})".format(system['name'], system['sid'])
                self.start_process(multiprocessing.Process(target=self._flush_host_by_sid, args=(system['id'],)))
        if self.verbose and systems:
            print "Done"

    def refresh(self):
        """
        Refresh profiles by running rhn_check over them.
        """
        for profile in self.db.get_host_profiles():
            if self.verbose:
                print "Refreshing {0} ({1})".format(profile.hostname, profile.sid)

            # TODO: pass the entire profile instead of its pieces!
            cli = check.CheckCli(self.db.get_host_config(profile.id), profile.src, self.db, profile.sid, profile,
                                 hostname=profile.hostname)
            cli.verbose = self.verbose
            self.start_process(multiprocessing.Process(target=cli.main))

    def register(self, profile):
        """
        Register one system based on profile.
        """
        xmldata = XMLData()
        try:
            profile.src = rhnreg.registerSystem(token=self.options.key,
                                                profileName=profile.id,
                                                other=profile.params)
            xmldata.load(profile.src)
            profile.sid = xmldata.get_member('system_id')
            profile.name = xmldata.get_member('profile_name')
            self.db.create_profile(profile)
            self.db.connection.commit()
            print "Registered {0} with System ID {1}".format(xmldata.get_member('profile_name'),
                                                             xmldata.get_member('system_id'))
        except (up2dateErrors.AuthenticationTicketError,
                up2dateErrors.RhnUuidUniquenessError,
                up2dateErrors.CommunicationError,
                up2dateErrors.AuthenticationOrAccountCreationError), e:
            print "WARNING: Registration error: {0}".format(e.errmsg)
            return

        rhnreg.sendHardware(profile.src, profile.hardware)
        rhnreg.sendPackages(profile.src, profile.packages)
        rhnreg.sendVirtInfo(profile.src)
        rhnreg.startRhnsd()

        check.CheckCli(rhnreg.cfg, profile.src, self.db, profile.sid, profile, hostname=profile.hostname).main()


if __name__ == '__main__':
    try:
        vr = VirtualRegistration()
        vr.main()
    except VirtualRegistration.VRException as ex:
        print "Error:\n  {0}\n".format(ex)
    except Exception as ex:
        raise ex
