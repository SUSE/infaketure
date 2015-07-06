#!/usr/bin/python
#
# Create a fake registrations in a bulk.
# Author: BOFH <bo@suse.de>
#

import sys
import os
import time
import datetime
import getpass
from optparse import OptionParser
import random
import uuid
from xml.dom import minidom as dom
import multiprocessing
import shutil
import difflib

from infaketure import check
from infaketure import hostnames
from infaketure import store
from infaketure import spaceapi
from infaketure import loadproc
from infaketure.pcp import pcpconn
from infaketure import procpool
from infaketure.cmdbmeta import HardwareInfo
from infaketure.cmdbmeta import SoftwareInfo

sys.path.append("/usr/share/rhn/")

from up2date_client import rhnreg
from up2date_client import hardware
from up2date_client import pkgUtils
from up2date_client import up2dateErrors
from suseRegister.info import getProductProfile as get_suse_product_profile
from up2date_client import rhnserver


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


class Infaketure(object):
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
        self.procpool = procpool.Pool()
        self.verbose = False
        self._pcp_metrics_path = None

        if self._initialize():
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

    def _initialize(self):
        """
        Initialize command line options.
        """
        _dbstore_file = os.path.join(os.path.abspath("."), "store.db")
        self._pcp_metrics_path = os.path.join(os.path.abspath("."), ".pcp-metrics")
        opt = OptionParser(version="Bloody Alpha, 0.1")
        opt.add_option("-m", "--manager-hostname", action="store", dest="fqdn",
                       help="SUSE Manager hostname.")
        opt.add_option("-o", "--monitor-hostname", action="store", dest="monitor",
                       help="Alternative PCP monitoring host.")
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
        opt.add_option("-e", "--database-file", action="store", dest="dbfile",
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
        opt.add_option("-d", "--diff", action="store", dest="diff",
                       help="Diff between a two space separated paths of saved sessions: source destination")

        self.options, self.args = opt.parse_args()

        if self.options.diff:
            # argparse allows space-separated values, but is
            # not available on Python 2.6 which is still in use.
            f_idx = sys.argv.index(self.options.diff)
            if len(sys.argv) > f_idx + 1:
                self.options.diff = sorted([self.options.diff, sys.argv[f_idx + 1]])
            else:
                raise Infaketure.VRException("Should be two saved sessions paths specified")
            return False

        # Check the required parameters
        if not self.options.fqdn or ((not self.options.refresh
                                      and not self.options.flush
                                      and not self.options.scenario)
                                     and (not self.options.key)):
            sys.argv.append("-h")

        self.options, self.args = opt.parse_args()

        # Setup CA Cert
        if self.options.cacert:
            rhnreg.cfg.set("sslCACert", self.options.cacert)
        if not os.path.exists(rhnreg.cfg["sslCACert"]):
            raise Infaketure.VRException(
                "SSL CA Certificate was not found at {0}".format(rhnreg.cfg["sslCACert"]))

        try:
            self.amount = int(self.options.amount and self.options.amount or "5")
        except Exception as error:
            raise Infaketure.VRException("Wrong amount of fake hosts: {0}".format(self.options.amount))

        if self.options.dbfile:
            _dbstore_file = self.options.dbfile

        if self.options.pcp_path:
            self._pcp_metrics_path = self.options.pcp_path

        if self.options.verbose:
            self.verbose = True

        if self.options.flush:
            if not self.options.user or not self.options.password:
                raise Infaketure.VRException(
                    "User and/or password must be given to authorise against SUSE Manager.")

        self.db = store.DBOperations(_dbstore_file)
        self.db.open()

        return True

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
            pcpconn.PCPConnector.CFG_HOST: self.options.fqdn,
            pcpconn.PCPConnector.CFG_USER: getpass.getuser(),
        }
        if self.options.monitor:
            pcp_cfg[pcpconn.PCPConnector.CFG_LOGGER_HOST] = self.options.monitor

        if "pcp.snapshot" in runner.config:
            pcp_cfg[pcpconn.PCPConnector.CFG_PATH] = runner.config["pcp.snapshot"]

        _pcp = pcpconn.PCPConnector(pcp_cfg)
        for cfg_key, cfg_value in runner.config.items():
            metric_prefix = "pcp.metric."
            if cfg_key.startswith(metric_prefix):
                _pcp.probes[cfg_key.replace(metric_prefix, "")] = cfg_value or None
        _pcp.start()
        s_twc = runner.run(callback=self.refresh)
        _pcp.stop()

        # Save the results
        session_id = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        self._save_pcp_metrics(session_id, _pcp)
        self._save_cmdb_metadata(session_id)
        self._save_scenario(session_id)
        self._save_twc(session_id, s_twc)
        self._save_db_metadata(session_id)

        _pcp.cleanup()

    def _save_db_metadata(self, session_id):
        """
        Describe the database of the registered systems.
        """
        # TODO: This pathfinding and its creation is a subject for later refactoring
        conf_path = os.path.join(self._pcp_metrics_path, self.options.fqdn, session_id, "conf")
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)
        db_meta_h = open(os.path.join(conf_path, "db-meta.conf"), "w")
        db_meta_h.write("# Number of registered hosts\n"
                        "registered hosts = {0}\n".format(len(self.db.get_host_profiles())))
        db_meta_h.close()

    def _save_scenario(self, session_id):
        """
        Copy current scenario to the session configuration for archive purposes and further comparisons.
        """
        conf_path = os.path.join(self._pcp_metrics_path, self.options.fqdn, session_id, "conf")
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)
        shutil.copy(self.options.scenario, os.path.join(conf_path, "scenario.conf"))

    def _time_unix2iso8601(self, ticks):
        """
        Convert Unix ticks to the ISO-8601 time.
        """
        t_snp = time.localtime(ticks)
        return datetime.datetime(t_snp.tm_year, t_snp.tm_mday, t_snp.tm_hour,
                                 t_snp.tm_hour, t_snp.tm_min, t_snp.tm_sec).isoformat(' ')

    def _save_twc(self, session_id, s_twc):
        """
        Save total wall clock.
        """
        conf_path = os.path.join(self._pcp_metrics_path, self.options.fqdn, session_id, "conf")
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)

        ticks_start, ticks_end = s_twc
        s_twc_fh = open(os.path.join(conf_path, "clock.txt"), "w")
        s_twc_fh.write("Start:\n      Unix: {s_tcs}\n  ISO 8601: {s_iso}\n\nEnd:\n      Unix: {e_tcs}\n"
                       "  ISO 8601: {e_iso}\n\nDuration:\n   Seconds: {d_tcs}\n".format(
                           s_tcs=int(round(ticks_start)),
                           s_iso=self._time_unix2iso8601(ticks_start),
                           e_tcs=int(round(ticks_end)),
                           e_iso=self._time_unix2iso8601(ticks_end),
                           d_tcs=round(ticks_end - ticks_start, 2)))
        s_twc_fh.close()

    def _save_cmdb_metadata(self, session_id):
        """
        Save CMDB metadata of the tester client host and the tested SUMA installation.
        """
        conf_path = os.path.join(self._pcp_metrics_path, self.options.fqdn, session_id, "conf")
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)

        # Get software
        for doc_file, sft_pks in (('client-software.txt', SoftwareInfo('localhost').get_pkg_info('python-*')),
                                  ('server-software.txt', SoftwareInfo(self.options.fqdn, user=getpass.getuser())
                                      .get_pkg_info('postgres*', 'java*'))):
            doc_file = open(os.path.join(conf_path, doc_file), 'w')
            for pkg_name in sorted(sft_pks.keys()):
                doc_file.write("{name}:\n  Vendor:  \"{vendor}\"\n".format(
                    name=pkg_name, vendor=sft_pks.get(pkg_name).get('vendor')))
                doc_file.write("  Version: {version}\n  Release: {release}\n\n".format(
                    version=sft_pks.get(pkg_name).get('version'),
                    release=sft_pks.get(pkg_name).get('release')))
            doc_file.close()

        # Get hardware
        for doc_file, hw_nfo in (('client-hardware.txt', HardwareInfo('localhost')),
                                 ('server-hardware.txt', HardwareInfo(self.options.fqdn, user=getpass.getuser()))):
            doc_file = open(os.path.join(conf_path, doc_file), 'w')
            doc_file.write("CPU\n===\n\n{cpu}\n\n\nMemory\n======\n\n{memory}\n\n\n"
                           "Disks\n=====\n\n{disks}\n\n\nDisk Space\n==========\n\n"
                           "{dsp}\n\n\n".format(cpu=hw_nfo.get_cpu(),
                                                memory=hw_nfo.get_memory(),
                                                disks=hw_nfo.get_disk_drives(),
                                                dsp=hw_nfo.get_disk_space()))
            doc_file.close()

    def _save_pcp_metrics(self, session_id, pcp):
        """
        Save PCP metrics.
        """
        metrics_path = os.path.join(self._pcp_metrics_path, self.options.fqdn, session_id, 'data')
        if not os.path.exists(metrics_path):
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

        return session_id

    def diff(self, session_1, session_2):
        """
        Display full diff between two sessions.
        """
        session_1 = os.path.join(session_1, "conf")
        session_2 = os.path.join(session_2, "conf")
        if not os.path.exists(session_1) or not os.path.exists(session_2):
            raise Infaketure.VRException("Sessions cannot be found. Please make sure both paths are correct")

        conf_map = (
            ('Client Hardware', 'client-hardware.txt'),
            ('Client Software', 'client-software.txt'),
            ('Server Hardware', 'server-hardware.txt'),
            ('Server Software', 'server-software.txt'),
            ('Total Wall Clock', 'clock.txt'),
        )

        print "_" * 80
        for s_title, s_file in conf_map:
            print "\n\n{title}\n{u_title}\n".format(title=s_title, u_title=("#" * len(s_title)))
            print ''.join(difflib.ndiff(open(os.path.join(session_1, s_file)).readlines(),
                                        open(os.path.join(session_2, s_file)).readlines())),
        print "_" * 80
        print

    def main(self):
        """
        Main
        """
        if self.options.diff:
            session_1, session_2 = self.options.diff
            return self.diff(session_1, session_2)
        elif self.options.scenario:
            self.scenario()
        elif self.options.refresh:
            self.refresh()
        elif self.options.flush:
            self.flush()
        else:
            fh = hostnames.FakeNames(fqdn=True)
            for profile in self.db.get_host_profiles():
                fh.add_history(profile.hostname)
            idx_offset = self.db.get_next_id("hosts") - 1
            for idx in range(vr.amount):
                self.procpool.run(multiprocessing.Process(
                    target=self.register, args=(CMDBProfile(fh(), idx=(idx + idx_offset)),)), join=True)
        self.procpool.join()
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
        batch = 0
        for system in systems:
            if not wipe and system['sid'] in host_sids or wipe:
                if self.verbose:
                    print "Removing {0} ({1})".format(system['name'], system['sid'])
                self.procpool.run(multiprocessing.Process(target=self._flush_host_by_sid, args=(system['id'],)))
                batch += 1
            if batch == 30:
                self.procpool.join()
                print "Removed {0} machines".format(batch)
                batch = 0
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
            self.procpool.run(multiprocessing.Process(target=cli.main))

    def register(self, profile):
        """
        Register one system based on profile.
        """
        xmldata = XMLData()
        try:
            profile.src = rhnreg.registerSystem(token=self.options.key,
                                                profileName=profile.id,
                                                other=profile.params)
            profile.login_info = rhnserver.RhnServer().up2date.login(profile.src)
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
        vr = Infaketure()
        vr.main()
    except Infaketure.VRException as ex:
        print "Error:\n  {0}\n".format(ex)
    except Exception as ex:
        raise ex
