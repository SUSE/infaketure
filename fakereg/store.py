#
# SQLite storage for rhnreg_ks
# Author: BOFH (bo@suse.de)
#

import sqlite3


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
        self.init_queries.append("CREATE TABLE packages "
                                 "(id INTEGER PRIMARY KEY, hid INTEGER, BODY BLOB)")

    def open(self, new=False):
        """
        Init the database, if required.
        """
        if self.connection and self.cursor:
            return

        if new and os.path.exists(self._path):
            os.unlink(self._path)  # As simple as that

        self.connection = sqlite3.connect(self._path)
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

    def get_all_hosts(self):
        """
        Return all hosts.
        """
        data = list()
        self.cursor.execute("SELECT ID, SID, HOSTNAME, SID_XML FROM HOSTS")
        for host_id, sid, hostname, profile in self.cursor.fetchall():
            host = type('class', (object,), {})
            host.id = host_id
            host.sid = sid
            host.profile = profile
            host.hostname = hostname

            data.append(host)

        return data

    def get_host_config(self, host_id):
        """
        Get up2date configuration for the host by db ID.
        """
        self.cursor.execute("SELECT BODY FROM configs WHERE HID = ?", (host_id,))
        for cfg in self.cursor.fetchall():
            return eval(cfg[0])

    def get_host_by_id(self, host_id):
        """
        Get host by an id.
        """
        self.cursor.execute("SELECT ID, SID, HOSTNAME, SID_XML FROM HOSTS WHERE SID = ?", ("ID-{0}".format(host_id),))
        for host_id, sid, hostname, profile in self.cursor.fetchall():
            host = type('class', (object,), {})
            host.id = host_id
            host.sid = sid
            host.profile = profile
            host.hostname = hostname
            return host

    def delete_host_by_id(self, host_id):
        """
        Delete host by id.
        """
        host = self.get_host_by_id(host_id)
        if not host:
            raise Exception("Unable to find host with SID '{0}'".format(host_id))

        self.cursor.execute("DELETE FROM HOSTS WHERE ID = ?", (host.id,))
        self.cursor.execute("DELETE FROM CONFIGS WHERE HID = ?", (host.id,))
        self.cursor.execute("DELETE FROM HARDWARE WHERE HID = ?", (host.id,))
        self.cursor.execute("DELETE FROM PACKAGES WHERE HID = ?", (host.id,))
