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
Testing against Guayadeque.
"""

from __future__ import absolute_import, print_function

import panflute.defs
import panflute.tests.mpris

import os.path


class Launcher (panflute.tests.mpris.Launcher):
    """
    Launcher for testing against Guayadeque.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.mpris.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                "Guayadeque")


class Runner (panflute.tests.mpris.Runner):
    """
    Runner for testing against Guayadeque.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.mpris.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests, "guayadeque")


    def prepare_single_mpris (self, prefix, user, password):
        self.rmdirs ("~/.guayadeque/")
        self.mkdir ("~/.guayadeque/")

        with open (os.path.expanduser ("~/.guayadeque/guayadeque.conf"), "w") as conf:
            # Don't prompt on close, and rescan the library
            print ("[General]", file = conf)
            print ("ShowCloseConfirm=0", file = conf)
            print ("UpdateLibOnStart=1", file = conf)
            # Library location
            print ("[LibPaths]", file = conf)
            print ("LibPath0={0}".format (panflute.defs.PKG_DATA_DIR), file = conf)
            # Playlist
            print ("[PlayList]", file = conf)
            for i in range (len (self.TONE_PATHS)):
                print ("PlayListSong{0}={1}".format (i, self.TONE_PATHS[i]), file = conf)

        path = os.path.join (prefix, "bin/guayadeque")
        child = self.run_command ([path])
        self.set_child (child)
