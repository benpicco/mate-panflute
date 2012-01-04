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
Testing against Banshee.
"""

from __future__ import absolute_import, print_function

import panflute.defs
import panflute.tests.runner

import mateconf
import os.path
import sys


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing Banshee.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "Banshee")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing Banshee.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)


    def prepare_single (self, prefix, user, password):
        # No good way to load specific files into Banshee's database, so point
        # the music collection to our directory and tell Banshee to watch for
        # changes.

        print ("Banshee directories", file = sys.stderr)
        self.rmdirs ("~/.config/banshee-1")
        self.mkdir ("~/.config/banshee-1/addin-db-001")
        print ("Banshee config file", file = sys.stderr)
        with open (os.path.expanduser ("~/.config/banshee-1/addin-db-001/config.xml"), "w") as conf:
            print ("<Configuration>", file = conf)
            print ("  <AddinStatus>", file = conf)
            print ("    <Addin id=\"Banshee.LibraryWatcher,1.0\" enabled=\"True\"/>", file = conf)
            print ("  </AddinStatus>", file = conf)
            print ("</Configuration>", file = conf)

        print ("Banshee MateConf", file = sys.stderr)
        client = mateconf.client_get_default ()
        client.recursive_unset ("/apps/banshee-1", 0)
        client.set_string ("/apps/banshee-1/sources/_music_library_source_-_library/library-location",
                           panflute.defs.PKG_DATA_DIR)

        print ("Banshee launch", file = sys.stderr)
        path = os.path.join (prefix, "bin/banshee-1")
        child = self.run_command ([path])
        self.set_child (child)

        print ("Banshee wait", file = sys.stderr)
        self.wait_for ("org.bansheeproject.Banshee", True)


    def cleanup_single (self):
        # The banshee-1 script forks, and there's no reliable way to tell it to
        # quit via D-Bus, so go for the brute-force approach.
        self.run_command (["killall", "banshee-1"])
        self.wait_for ("org.bansheeproject.Banshee", False)
