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
Testing against VLC.
"""

from __future__ import absolute_import, print_function

import panflute.tests.mpris

import os.path


class Launcher (panflute.tests.mpris.Launcher):
    """
    Launcher for testing against VLC.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.mpris.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                "VLC")


class Runner (panflute.tests.mpris.Runner):
    """
    Runner for testing against VLC.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.mpris.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests, "vlc")


    def prepare_single_mpris (self, prefix, user, password):
        self.rmdirs ("~/.config/vlc")
        self.rmdirs ("~/.local/share/vlc")
        self.mkdir ("~/.config/vlc")

        with open (os.path.expanduser ("~/.config/vlc/vlcrc"), "w") as rc:
            # Turn off "connect to Internet?" prompt at startup
            print ("[qt4]", file = rc)
            print ("qt-privacy-ask=0", file = rc)
            # Enable D-Bus interface
            print ("[main]", file = rc)
            print ("control=dbus", file = rc)

        path = os.path.join (prefix, "bin/vlc")
        child = self.run_command ([path])
        self.set_child (child)
