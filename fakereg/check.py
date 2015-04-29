#!/usr/bin/python
#
# Python client for checking periodically for posted actions
# on the Spacewalk servers.
#
# Copyright (c) 2000--2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the
# OpenSSL library under certain conditions as described in each
# individual source file, and distribute linked combinations
# including the two.
# You must obey the GNU General Public License in all respects
# for all of the code used other than OpenSSL.  If you modify
# file(s) with this exception, you may extend this exception to your
# version of the file(s), but you are not obligated to do so.  If you
# do not wish to do so, delete this exception statement from your
# version.  If you delete this exception statement from all source
# files in the program, then also delete it here.
import os
import sys
import socket
import socket
import time
import httplib
import urllib2
import xmlrpclib
import urlparse

from OpenSSL import SSL
sys.path.append("/usr/share/rhn/")
sys.modules['sgmlop'] = None

from up2date_client import getMethod
from up2date_client import up2dateErrors
from up2date_client import up2dateAuth
from up2date_client import up2dateLog
from up2date_client import up2dateUtils
from up2date_client import config
from up2date_client import rpcServer
from up2date_client import clientCaps
from up2date_client import capabilities
from up2date_client import rhncli, rhnserver

from fakereg import actions

from rhn import rhnLockfile
from rhn import rpclib
del sys.modules['sgmlop']

log = up2dateLog.initLog()

# action version we understand
ACTION_VERSION = 2

# lock file to check if we're disabled at the server's request
DISABLE_FILE = "/etc/sysconfig/rhn/disable"

# Actions that will run each time we execute.
LOCAL_ACTIONS = [("packages.checkNeedUpdate", ("rhnsd=1",))]


class CheckCli(rhncli.RhnCli):

    def __init__(self, cfg, sid, hostname=None):
        self.cfg = cfg
        self.rhns_ca_cert = self.cfg['sslCACert']
        self.server = None
        self.options = list()
        self.args = list()
        self.sid = sid
        self.hostname = hostname and hostname.split(".")[0] or None

    def initialize(self):
        pass

    def main(self):
        """
        Process all the actions we have in the queue.
        """
        CheckCli.__check_instance_lock()
        CheckCli.__check_rhn_disabled()
        CheckCli.__check_has_system_id()

        self.server = self.get_server()

        CheckCli.__update_system_id()

        self.__run_remote_actions()
        CheckCli.__run_local_actions()

        s = rhnserver.RhnServer()
        if s.capabilities.hasCapability('staging_content', 1) and self.cfg['stagingContent'] != 0:
            self.__check_future_actions()

    def __get_action(self, status_report):
        try:
            return self.server.queue.get(self.sid, ACTION_VERSION, status_report)
        except Exception as ex:
            print "Action execution error:", ex

    def __query_future_actions(self, time_window):
        try:
            return self.server.queue.get_future_actions(self.sid, time_window)
        except Exception as ex:
            print "Future actions error:", ex

    def __fetch_future_action(self, action):
        """
        Fetch one specific action from rhnParent
        """

    def __check_future_actions(self):
        """ Retrieve scheduled actions and cache them if possible """
        time_window = self.cfg['stagingContentWindow'] or 24;
        actions = self.__query_future_actions(time_window)
        for action in actions:
            self.handle_action(action, cache_only=1)

    def __run_remote_actions(self):
        # the list of caps the client needs
        caps = capabilities.Capabilities()

        sysname, nodename, release, version, machine = os.uname()
        status_report = {
            'uname': (sysname, (self.hostname and self.hostname or nodename), release, version, machine),
            'uptime': [0, 0],  # Just rebooted
        }

        action = self.__get_action(status_report)
        while action:
            self.__verify_server_capabilities(caps)
            if self.is_valid_action(action):
                self.handle_action(action)
            else:
                print "Action '{0}' is invalid".format(str(action))

            action = self.__get_action(status_report)

    def __verify_server_capabilities(self, caps):
        response_headers = self.server.get_response_headers()
        caps.populate(response_headers)
        try:
            caps.validate()
        except up2dateErrors.ServerCapabilityError, e:
            print e

    def __parse_action_data(self, action):
        """ Parse action data and returns (method, params) """
        data = action['action']
        parser, decoder = xmlrpclib.getparser()
        parser.feed(data.encode("utf-8"))
        parser.close()
        params = decoder.close()
        method = decoder.getmethodname()

        return method, params

    def submit_response(self, action_id, status, message, data):
        """ Submit a response for an action_id. """

        # get a new server object with fresh headers
        self.server = self.get_server()

        try:
            return self.server.queue.submit(self.sid, action_id, status, message, data)
        except Exception as ex:
            print ex

        return None

    def handle_action(self, action, cache_only=None):
        """
        Wrapper handler for the action we're asked to do.
        """
        log.log_debug("handle_action", action)
        log.log_debug("handle_action actionid = %s, version = %s" % (action['id'], action['version']))

        (method, params) = self.__parse_action_data(action)
        (status, message, data) = CheckCli.__run_action(method, params, {'cache_only': cache_only})

        if not cache_only:
            log.log_debug("Sending back response", (status, message, data))
            self.submit_response(action['id'], status, message, data)
        else:
            print "Response was not sent!"

    def is_valid_action(self, action):
        log.log_debug("check_action", action)

        # be very paranoid of what we get back
        if type(action) != type({}):
            print "Got unparseable action response from server"

        for key in ['id', 'version', 'action']:
            if not action.has_key(key):
                print "Got invalid response - missing '%s'" % key
        try:
            ver = int(action['version'])
        except ValueError:
            ver = -1
        if ver > ACTION_VERSION or ver < 0:
            print "Got unknown action version %d" % ver
            print action
            # the -99 here is kind of magic
            self.submit_response(action["id"], xmlrpclib.Fault(-99, "Can not handle this version"))
            return False
        return True

    @staticmethod
    def __update_system_id():
        try:
            up2dateAuth.maybeUpdateVersion()
        except up2dateErrors.CommunicationError, e:
            print e

    @staticmethod
    def __run_local_actions():
        """
        Hit any actions that we want to always run.

        If we want to run any actions everytime rhnsd runs rhn_check,
        we can add them to the list LOCAL_ACTIONS
        """
        for method_params in LOCAL_ACTIONS:
            method = method_params[0]
            params = method_params[1]
            (status, message, data) = CheckCli.__run_action(method, params)
            log.log_debug("local action status: ", (status, message, data))

    @staticmethod
    def __do_call(method, params, kwargs={}):
        retval = actions.Dispatcher(method)(*params, **kwargs)
        if method == "reboot.reboot":
            # Make sure SUMA accepts the reboot
            print "\tINFO: Reboot scheduled. Pausing for a few seconds..."
            time.sleep(6)
        else:
            # Debug
            print "Call: '{0}', return: {1}".format(method, retval)

        return retval

    @staticmethod
    def __run_action(method, params, kwargs={}):
        try:
            status, message, data = CheckCli.__do_call(method, params, kwargs)
        except Exception as ex:
            log.log_exception(*sys.exc_info())
            status, message, data = 6, "Unhandled exception had occurred", {}

        return status, message, data

    @staticmethod
    def __check_instance_lock():
        """
        Is called by a real rhn_check. Here does nothing.
        """

    @staticmethod
    def __check_has_system_id():
        """
        Is called by a real rhn_check. Here does nothing.
        """

    @staticmethod
    def __check_rhn_disabled():
        """
        Is called by a real rhn_check. Here does nothing.
        """

    def get_server(self, refreshCallback=None, serverOverride=None, timeout=None):
        """
        Moved from rpcServer.
        """
        ca = self.cfg["sslCACert"]
        if isinstance(ca, basestring):
            ca = [ca]

        rhns_ca_certs = ca or ["/usr/share/rhn/RHNS-CA-CERT"]
        if self.cfg["enableProxy"]:
            proxy_host = config.getProxySetting()
        else:
            proxy_host = None

        if not serverOverride:
            server_urls = config.getServerlURL()
        else:
            server_urls = serverOverride
        server_list = rpcServer.ServerList(server_urls)

        proxy_user = None
        proxy_password = None
        if self.cfg["enableProxyAuth"]:
            proxy_user = self.cfg["proxyUser"] or None
            proxy_password = self.cfg["proxyPassword"] or None

        lang = None
        for env in 'LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG':
            if os.environ.has_key(env):
                if not os.environ[env]:
                    # sometimes unset
                    continue
                lang = os.environ[env].split(':')[0]
                lang = lang.split('.')[0]
                break

        retry_server = rpcServer.RetryServer(server_list.server(),
            refreshCallback=refreshCallback,
            proxy=proxy_host,
            username=proxy_user,
            password=proxy_password,
            timeout=timeout)
        retry_server.addServerList(server_list)
        retry_server.add_header("X-Up2date-Version", up2dateUtils.version())

        if lang:
            retry_server.setlang(lang)

        # require RHNS-CA-CERT file to be able to authenticate the SSL connections
        need_ca = [True for i in retry_server.serverList.serverList if urlparse.urlparse(i)[0] == 'https']
        if need_ca:
            for rhns_ca_cert in rhns_ca_certs:
                if not os.access(rhns_ca_cert, os.R_OK):
                    msg = "%s: %s" % ("ERROR: can not find RHNS CA file", rhns_ca_cert)
                    log.log_me("%s" % msg)
                    raise up2dateErrors.SSLCertificateFileNotFound(msg)

                # force the validation of the SSL cert
                retry_server.add_trusted_cert(rhns_ca_cert)

        clientCaps.loadLocalCaps()

        # send up the capabality info
        header_list = clientCaps.caps.headerFormat()
        for (headerName, value) in header_list:
            retry_server.add_header(headerName, value)

        return retry_server
