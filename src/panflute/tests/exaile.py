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
Testing against Exaile.
"""

from __future__ import absolute_import, print_function

import panflute.mpris
import panflute.tests.runner

import dbus
import os
import os.path
import time


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing Exaile.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "Exaile")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing Exaile.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)


    def prepare_single (self, prefix, user, password):
        self.rmdirs ("~/.config/exaile")
        self.rmdirs ("~/.local/share/exaile")
        self.mkdir ("~/.config/exaile")
        self.mkdir ("~/.local/share/exaile")

        # Make sure Exaile can find the plugins -- Exaile 0.3.0.x has trouble
        # finding the right directory.
        os.symlink (os.path.join (prefix, "share/exaile/plugins"),
                    os.path.expanduser ("~/.local/share/exaile/plugins"))

        with open (os.path.expanduser ("~/.config/exaile/settings.ini"), "w") as settings:
            print ("[plugins]", file = settings)
            print ("enabled = L: ['mpris']", file = settings)

        path = os.path.join (prefix, "bin/exaile")
        child = self.run_command ([path])
        self.set_child (child)

        self.wait_for ("org.exaile.Exaile", True)
        proxy = self.bus.get_object ("org.exaile.Exaile", "/org/exaile/Exaile")
        exaile = dbus.Interface (proxy, "org.exaile.Exaile")

        proxy = self.bus.get_object ("org.exaile.Exaile", "/Player")
        player = dbus.Interface (proxy, panflute.mpris.INTERFACE)

        # Manipulating the collection is difficult, but we can queue up
        # files without them being in the collection.

        time.sleep (3)      # make sure the GUI has finished loading

        # Enqueue throws an exception, so use PlayFile instead
        for path in self.TONE_PATHS:
            exaile.PlayFile (path)
        player.Prev ()
        player.Prev ()
        player.Stop ()


    def cleanup_single (self):
        self.run_command (["killall", "exaile"])
        self.wait_for ("org.exaile.Exaile", False)
