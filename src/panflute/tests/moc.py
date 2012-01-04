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
Testing against MOC.
"""

from __future__ import absolute_import

import panflute.tests.runner

import gconf
import os.path


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing MOC.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "MOC")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing MOC.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)
        self.__path = None


    def prepare_single (self, prefix, user, password):
        # The daemon sets up a watch on the fifo in ~/.moc, and deleting the
        # directory screws that up, so just nuke the configs.

        self.mkdir ("~/.moc")
        self.rmfile ("~/.moc/playlist.m3u")
        self.rmfile ("~/.moc/pid")

        # Since the daemon will be invoking the MOC program, tell it where
        # the version of MOC being tested.

        self.__path = os.path.join (prefix, "bin/mocp")

        client = gconf.client_get_default ()
        client.set_string ("/apps/panflute/daemon/moc/command", self.__path)

        child = self.run_command ([self.__path, "--server"])
        self.set_child (child)

        other_child = self.run_command ([self.__path, "--append"] + self.TONE_PATHS)
        other_child.wait ()


    def cleanup_single (self):
        self.run_command ([self.__path, "--exit"])
        self.run_command (["killall", "mocp"])
