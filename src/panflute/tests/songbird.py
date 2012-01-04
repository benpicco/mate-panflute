#! /usr/bin/env python

# Panflute
# Copyright (C) 2010 Paul Kuliniewicz <paul@kuliniewicz.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02111-1301, USA.

"""
Testing against Songbird.
"""

from __future__ import absolute_import, print_function

import panflute.tests.mpris

import hashlib
import os
import os.path
import urllib2
import zipfile


class Launcher (panflute.tests.mpris.Launcher):
    """
    Launcher for testing against Songbird.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.mpris.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                "Songbird")

        # Songbird doesn't play nicely with other libraries on the system,
        # but this works around that.

        self.set_env ("LD_BIND_NOW", "1")


class Runner (panflute.tests.mpris.Runner):
    """
    Runner for testing against Songbird.
    """

    ADDON_UUID = "{0a067f25-b5fa-4530-9396-fc7088a05415}"
    ADDON_HASH = "18f85e512db6b2094646876b3e18240546db00f4773cd6f883d75c6cb4021d7c"
    ADDON_URL = "http://addons.songbirdnest.com/xpis/4818?source=download"
    ADDON_PATH = os.path.expanduser ("~/.local/share/panflute/Mpris-0.1.10.xpi")

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.mpris.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests, "songbird")


    def prepare_persistent (self):
        # Download the add-on that provides MPRIS support, if it hasn't been
        # downloaded already.

        if not os.access (self.ADDON_PATH, os.F_OK):
            xpi = urllib2.urlopen (self.ADDON_URL)
            xpi_data = xpi.read ()
            xpi.close ()

            digest = hashlib.sha256 (xpi_data).hexdigest ()
            if digest != self.ADDON_HASH:
                raise TestError
            with open (self.ADDON_PATH, "wb") as xpi_file:
                xpi_file.write (xpi_data)


    def prepare_single_mpris (self, prefix, user, password):
        ext_dir = os.path.expanduser ("~/.songbird2/abcdefgh.default/extensions/{0}".format (self.ADDON_UUID))
        self.rmdirs ("~/.songbird2")
        self.mkdir (ext_dir)

        # The MPRIS extension itself, previous downloaded and verified.
        xpi_file = zipfile.ZipFile (self.ADDON_PATH, "r")
        xpi_file.extractall (ext_dir)
        xpi_file.close ()
        with open (os.path.expanduser ("~/.songbird2/abcdefgh.default/extensions.ini"), "w") as ext_ini:
            print ("[ExtensionDirs]", file = ext_ini)
            print ("Extension0={0}".format (ext_dir), file = ext_ini)

        # Enable the extension and disable Songbird's first-run nags.
        with open (os.path.expanduser ("~/.songbird2/abcdefgh.default/prefs.js"), "w") as prefs:
            print ('user_pref("songbird.firstrun.check.0.3", true);', file = prefs)
            print ('user_pref("songbird.firstrun.do_scan_directory", true);', file = prefs)
            print ('user_pref("songbird.firstrun.scan_directory_path", "{0}");'.format (panflute.defs.PKG_DATA_DIR),
                    file = prefs)
            print ('user_pref("songbird.firstrun.tabs.restore", true);', file = prefs)
            print ('user_pref("songbird.firstrun.update-once", true);', file = prefs)
            print ('user_pref("extensions.enabledItems", "{0}:0.1.10");'.format (self.ADDON_UUID), file = prefs)

        # And tell Songbird where this profile can be found.
        with open (os.path.expanduser ("~/.songbird2/profiles.ini"), "w") as prof_ini:
            print ("[General]", file = prof_ini)
            print ("StartWithLastProfile=1", file = prof_ini)
            print ("[Profile0]", file = prof_ini)
            print ("Name=default", file = prof_ini)
            print ("IsRelative=1", file = prof_ini)
            print ("Path=abcdefgh.default", file = prof_ini)

        # Finally, actually run the program.
        path = os.path.join (prefix, "songbird")
        child = self.run_command ([path])
        self.set_child (child)
