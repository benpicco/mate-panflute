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
Testing against Decibel.
"""

from __future__ import absolute_import, print_function

import panflute.tests.mpris

import cPickle
import os.path


class Launcher (panflute.tests.mpris.Launcher):
    """
    Launcher for testing against Decibel.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.mpris.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                "Decibel")


class Runner (panflute.tests.mpris.Runner):
    """
    Runner for testing against Decibel.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.mpris.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests, "dap")


    def prepare_single_mpris (self, prefix, user, password):
        self.rmdirs ("~/.config/decibel-audio-player")
        self.mkdir ("~/.config/decibel-audio-player")

        # Create enough of a config file to prevent Decibel from opening up
        # a first-time config dialog.
        obj = { '__main___first-time': False }
        with open (os.path.expanduser ("~/.config/decibel-audio-player/prefs.txt"), "w") as prefs:
            cPickle.dump (obj, prefs)

        # Start Decibel
        path = os.path.join (prefix, "bin/decibel-audio-player")
        child = self.run_command ([path])
        self.set_child (child)
