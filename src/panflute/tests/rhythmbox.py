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
Testing against Rhythmbox.
"""

from __future__ import absolute_import

import panflute.tests.runner

import dbus
import mateconf
import os.path


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing Rhythmbox.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "Rhythmbox")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing Rhythmbox.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)

        self.__shell = None


    def prepare_single (self, prefix, user, password):
        self.rmdirs ("~/.local/share/rhythmbox")
        client = mateconf.client_get_default ()
        client.recursive_unset ("/apps/rhythmbox", 0)

        path = os.path.join (prefix, "bin/rhythmbox")
        child = self.run_command ([path])
        self.set_child (child)

        self.wait_for ("org.gnome.Rhythmbox", True)
        proxy = self.bus.get_object ("org.gnome.Rhythmbox", "/org/gnome/Rhythmbox/Shell")
        self.__shell = dbus.Interface (proxy, "org.gnome.Rhythmbox.Shell")

        for uri in self.TONE_URIS:
            self.__shell.loadURI (uri, 0)


    def cleanup_single (self):
        self.__shell.quit ()
        self.__shell = None
        self.wait_for ("org.gnome.Rhythmbox", False)
