#
# Fun toy. Use cracklib to generate hostnames. :-)
# Author: BOFH (bo@suse.de)
#

import os
import string
import random
import re
import socket


class FakeNames(object):
    CRACKLIB = "/usr/share/cracklib"

    def __init__(self, fqdn=False):
        self._history = list()
        self._crack_dict = list()
        self._idx = 0
        if fqdn:
            self._domain = "." + ".".join(socket.getfqdn().split(".")[1:])
        else:
            self._domain = ""

        if os.path.exists(self.CRACKLIB):
            self._unpack_cracklib()
            self._stub = None
        else:
            self._stub = 'base'

    def _unpack_cracklib(self):
        """
        Unpack cracklib, if installed.
        """
        rnum = re.compile(r"\d")
        for line in os.popen("/usr/sbin/cracklib-unpacker {0}/pw_dict".format(self.CRACKLIB)):
            line = rnum.sub("", line).strip()
            if len(line) < 3 or len(line) > 12:
                continue
            self._crack_dict.append(line)

    def ubuntify(self):
        """
        Msidling with a rock-n-roll! \m/
        """
        choice = string.lowercase[random.randint(0, len(string.lowercase) - 1)]
        prefs = list()
        posts = list()
        for word in self._crack_dict:
            if word[0] == choice:
                if word[-1] == "y":
                    prefs.append(word)
                else:
                    posts.append(word)
        return prefs[random.randint(0, len(prefs) - 1)], posts[random.randint(0, len(posts) - 1)]


    def __call__(self, *args, **kwargs):
        """
        Generate a name.
        """
        pattern = "{0}-{1}"
        if self._stub:  # No crack lib around. :-(
            self._idx += 1
            return pattern.format(self._stub, self._idx - 1)

        # Yay!
        name = pattern.format(*self.ubuntify())
        if name in self._history:
            while name not in self._history:
                name = pattern.format(*self.ubuntify())
        self._history.append(name)

        return self._history[-1] + self._domain
