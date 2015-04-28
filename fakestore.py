#
# SQLite storage for rhnreg_ks
# Author: BOFH (bo@suse.de)
#

import sqlite3


class DBStorage(object):
    def __new__(cls, *args, **kwargs):
        """
        Singleton.
        """
        if not cls.__instance:
            cls.__instance = super(DBHandle, cls).__new__(cls, *args, **kwargs)
        return cls.__instance

    def __init__(self, path):
        self._path = path
        self.connection = None
        self.cursor = None

        self.init_queries = list()
        self.init_queries.append("CREATE TABLE hosts "
                                 "(id INTEGER PRIMARY KEY, SID CHAR(255), DATA TEXT)")
        self.init_queries.append("CREATE TABLE configs "
                                 "(id INTEGER PRIMARY KEY, hid INTEGER, DATA TEXT)")

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

    def flush(self, table):
        """
        Flush the table.
        """
        self.cursor.execute("DELETE FROM " + table)
        self.connection.commit()

    def close(self):
        """
        Close the database connection.
        """
        if self.cursor is not None and self.connection is not None:
            self.connection.close()
            self.cursor = self.connection = None
