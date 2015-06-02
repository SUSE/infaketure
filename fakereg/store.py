#
# SQLite storage for rhnreg_ks
# Author: BOFH (bo@suse.de)
#

import sqlite3
import re
import os
import sys
from fakereg import cli_msg
from fakereg import ERROR
import pickle

try:
    from up2date_client import rhnreg
except Exception as error:
    cli_msg(ERROR, 'Package "{0}" seems not installed'.format("spacewalk-client-setup"))
    sys.exit(1)


class CMDBBaseProfile(object):
    """
    System base profile container that has all the data about fake system.
    """
    def __init__(self):
        self.sid = self.__sid = None
        self.name = None  # Profile name

    @property
    def sid(self):
        return self.__sid

    @sid.setter
    def sid(self, sid):
        """
        Set SID
        """
        self.__sid = re.sub(r"\D", "", str(sid))


class DBStorage(object):
    def __init__(self, path):
        self._path = path
        self.connection = None
        self.cursor = None

        self.init_queries = list()
        self.init_queries.append("CREATE TABLE hosts "
                                 "(id INTEGER PRIMARY KEY, SID CHAR(255), HOSTNAME CHAR(255), SID_XML BLOB)")
        self.init_queries.append("CREATE TABLE configs "
                                 "(id INTEGER PRIMARY KEY, hid INTEGER, BODY BLOB)")
        self.init_queries.append("CREATE TABLE hardware "
                                 "(id INTEGER PRIMARY KEY, hid INTEGER, BODY BLOB)")
        self.init_queries.append("CREATE TABLE credentials "
                                 "(HID INTEGER, S_BODY BLOB)")


    def open(self, new=False):
        """
        Init the database, if required.
        """
        if self.connection and self.cursor:
            return

        if new and os.path.exists(self._path):
            os.unlink(self._path)  # As simple as that

        self.connection = sqlite3.connect(self._path, timeout=1200.0)  # 20 minutes timeout
        self.connection.text_factory = str
        self.cursor = self.connection.cursor()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if self.cursor.fetchall():
            return

        self._run_init_queries()
        self.connection.commit()

    def _run_init_queries(self):
        """
        Initialization queries
        """
        for query in self.init_queries:
            self.cursor.execute(query)

    def purge(self):
        """
        Purge whole database.
        """
        if self.connection and self.cursor:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for table_name in self.cursor.fetchall():
                self.cursor.execute("DROP TABLE {0}".format(table_name[0]))
            self.connection.commit()
        self._run_init_queries()
        self.vacuum()

    def get_next_id(self, table, field="id"):
        """
        Get the max of the ID field.
        """
        self.cursor.execute("SELECT max({0}) FROM {1}".format(field, table))
        data = self.cursor.fetchall()
        return data and data[0][0] or 0

    def flush(self, table):
        """
        Flush the table.
        """
        self.cursor.execute("DELETE FROM " + table)
        self.connection.commit()

    def vacuum(self):
        """
        Vacuum the database.
        """
        self.cursor.execute("VACUUM")
        self.close()
        self.open()

    def close(self):
        """
        Close the database connection.
        """
        if self.cursor is not None and self.connection is not None:
            self.connection.close()
            self.cursor = self.connection = None


class DBOperations(DBStorage):
    """
    Operations over the database.
    """

    def get_host_profiles(self, host_id=None):
        """
        Return all hosts, or specific one.
        """
        data = list()
        if host_id:
            self.cursor.execute("SELECT ID, SID, HOSTNAME, SID_XML FROM HOSTS WHERE SID = ?", (host_id,))
        else:
            self.cursor.execute("SELECT ID, SID, HOSTNAME, SID_XML FROM HOSTS")

        for hid, sid, hostname, profile in self.cursor.fetchall():
            host = CMDBBaseProfile()
            host.id = hid
            host.sid = sid
            host.src = profile
            host.hostname = hostname
            host.packages = self.get_host_packages(sid)

            data.append(host)

        return data[0] if host_id is not None else data

    def get_host_config(self, host_id):
        """
        Get up2date configuration for the host by db ID.
        """
        self.cursor.execute("SELECT BODY FROM configs WHERE HID = ?", (host_id,))
        for cfg in self.cursor.fetchall():
            return eval(cfg[0])

    def get_host_login_info(self, host_id):
        """
        Get login info for the host.
        :param host_id:
        :return:
        """
        self.cursor.execute("SELECT S_BODY FROM CREDENTIALS WHERE HID = ?", (host_id,))
        for nfo in self.cursor.fetchall():
            return pickle.loads(nfo[0])

    def delete_host_by_id(self, host_id):
        """
        Delete host by id.
        """
        host = self.get_host_profiles(host_id=host_id)
        if not host:
            raise Exception("Unable to find host with SID '{0}'".format(host_id))

        self.cursor.execute("DELETE FROM HOSTS WHERE ID = ?", (host.id,))
        self.cursor.execute("DELETE FROM CONFIGS WHERE HID = ?", (host.id,))
        self.cursor.execute("DELETE FROM HARDWARE WHERE HID = ?", (host.id,))
        self.cursor.execute("DELETE FROM CREDENTIALS WHERE HID = ?", (host.id,))
        self.cursor.execute("DROP TABLE IF EXISTS SYS{0}PKG".format(host.id))

    def get_host_packages(self, host_id):
        """
        Return packages for a client.
        """
        pkgs = list()
        self.cursor.execute("SELECT ID, HID, NAME, EPOCH, VERSION, RELEASE, ARCH, INSTALLTIME "
                            "FROM {0}".format("SYS{0}PKG".format(host_id)))
        for db_pkg in self.cursor.fetchall():
            pkg_id, hid, name, epoch, version, release, arch, installtime = db_pkg
            pkgs.append({
                "__pkg_id": pkg_id, "__host_id": hid,
                "epoch": epoch, "version": version,
                "release": release, "arch": arch,
                "installtime": installtime, "name": name,
            })

        return pkgs

    def create_profile(self, profile):
        """
        Create profile for the system.
        If exists, remove previous.
        """
        host_id = self.get_next_id("hosts") + 1
        self.cursor.execute("INSERT INTO hosts (ID, SID, HOSTNAME, SID_XML) VALUES (?, ?, ?, ?)",
                            (host_id, profile.sid, profile.name, profile.src,))
        hardware_id = self.get_next_id("hardware") + 1
        self.cursor.execute("INSERT INTO hardware (ID, HID, BODY) VALUES (?, ?, ?)",
                            (hardware_id, host_id, str(profile.hardware),))
        cfg_id = self.get_next_id("configs") + 1
        self.cursor.execute("INSERT INTO configs (ID, HID, BODY) VALUES (?, ?, ?)",
                            (cfg_id, host_id, str(dict(rhnreg.cfg.items()))))

        # Credentials
        self.cursor.execute("INSERT INTO credentials (HID, S_BODY) VALUES (?, ?)",
                            (host_id, pickle.dumps(profile.login_info, 0),))

        # Packages
        table_name = "SYS{0}PKG".format(profile.sid)
        self.cursor.execute("DROP TABLE IF EXISTS {0}".format(table_name))
        self.cursor.execute("CREATE TABLE {0} (id INTEGER PRIMARY KEY, HID INTEGER, NAME CHAR(255), "
                            "EPOCH CHAR(255), VERSION CHAR(255), RELEASE CHAR(255), ARCH CHAR(255), "
                            "INSTALLTIME INTEGER)".format(table_name))
        idx = 0
        for pkg in profile.packages:
            self.cursor.execute("INSERT INTO {0} (ID, HID, NAME, EPOCH, VERSION, RELEASE, ARCH, INSTALLTIME) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)".format(table_name),
                                (idx, host_id, pkg.get("name", ""), pkg.get("epoch", ""), pkg.get("version", ""),
                                 pkg.get("release", ""), pkg.get("arch", ""), pkg.get("installtime", 0),))
            idx += 1

    def update_profile(self, profile):
        """
        Update profile data.
        """
        # XXX: Currently packages only
        pkg_table = "SYS{0}PKG".format(profile.sid)

        def _in(pkg, pkgs, field="name"):
            """
            Is pkg in pkgs by name.
            """
            for pkg_ in pkgs:
                if pkg[field] == pkg_[field]:
                    return pkg_
            return False

        def _diff(pkg, src_pkg, *fields):
            """
            Compare pkg against src_pkg by fields.
            """
            for field in fields:
                if pkg.get(field) != src_pkg.get(field):
                    return True
            return False

        # Login info credentials
        self.cursor.execute("UPDATE credentials SET S_BODY = ? WHERE HID = ?)",
                            (pickle.dumps(profile.login_info, 0), profile.sid,))

        current_packages = self.get_host_packages(profile.sid)
        # Remove packages that was uninstalled
        for pkg in current_packages:
            if not _in(pkg, profile.packages):
                # print "DELETE:", pkg["name"]
                self.cursor.execute("DELETE FROM {0} WHERE NAME = ?".format(pkg_table), (pkg['name'],))

        # Add packages that were installed
        for pkg in profile.packages:
            if not _in(pkg, current_packages):
                # print "ADD:", pkg["name"]
                idx = self.get_next_id(pkg_table) + 1
                self.cursor.execute("INSERT INTO {0} (ID, HID, NAME, EPOCH, VERSION, RELEASE, ARCH, INSTALLTIME) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)".format(pkg_table),
                                    (idx, 0, pkg.get("name", ""), pkg.get("epoch", ""), pkg.get("version", ""),
                                     pkg.get("release", ""), pkg.get("arch", ""), pkg.get("installtime", 0),))

        # Update packages that were changed
        for pkg in profile.packages:
            if _diff(pkg, _in(pkg, current_packages) or {}, "epoch", "version", "release", "arch"):
                # print "UPDATE:", pkg["name"]
                self.cursor.execute("UPDATE {0} SET EPOCH = ?, VERSION = ?, RELEASE = ?, ARCH = ? WHERE NAME = ?".format(pkg_table),
                                    (pkg["epoch"], pkg["version"], pkg["release"], pkg["arch"], pkg["name"]))
