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
Testing against Audacious.
"""

from __future__ import absolute_import

import panflute.tests.mpris

import os.path


class Launcher (panflute.tests.mpris.Launcher):
    """
    Launcher for testing against Audacious.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.mpris.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                "Audacious")


class Runner (panflute.tests.mpris.Runner):
    """
    Runner for testing against Audacious.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.mpris.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests, "audacious")


    def prepare_single_mpris (self, prefix, user, password):
        self.rmdirs ("~/.config/audacious")
        self.rmdirs ("~/.local/share/audacious")

        path = os.path.join (prefix, "bin/audacious")
        child = self.run_command ([path])
        self.set_child (child)
