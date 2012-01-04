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

from __future__ import absolute_import

import panflute.tests.runner

import dbus
import mateconf
import os.path


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing Muine.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "Muine")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing Muine.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)


    def prepare_single (self, prefix, user, password):
        self.rmdirs ("~/.mate2/muine")

        client = mateconf.client_get_default ()
        client.recursive_unset ("/apps/muine", 0)

        path = os.path.join (prefix, "bin/muine")
        child = self.run_command ([path])
        self.set_child (child)

        self.wait_for ("org.mate.Muine", True)
        proxy = self.bus.get_object ("org.mate.Muine", "/org/mate/Muine/Player")
        self.__muine = dbus.Interface (proxy, "org.mate.Muine.Player")

        for path in self.TONE_PATHS:
            self.__muine.QueueFile (path)


    def cleanup_single (self):
        try:
            self.__muine.Quit ()
        except dbus.DBusException, e:
            # Not a problem if the player didn't reply before quitting.
            if e.get_dbus_name () != "org.freedesktop.DBus.Error.NoReply":
                raise e

        self.__muine = None
        self.wait_for ("org.mate.Muine", False)
