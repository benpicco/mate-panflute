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
Testing against XMMS.
"""

from __future__ import absolute_import

import panflute.tests.runner

import os.path
import time
import xmms.control


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing XMMS.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "XMMS")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing XMMS.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)


    def prepare_single (self, prefix, user, password):
        self.rmdirs ("~/.xmms")

        path = os.path.join (prefix, "bin/xmms")
        child = self.run_command ([path])
        self.set_child (child)

        time.sleep (3)

        for uri in self.TONE_URIS:
            xmms.control.playlist_add_url_string (uri)


    def cleanup_single (self):
        xmms.control.quit ()
