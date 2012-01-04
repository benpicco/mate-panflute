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
Testing against Amarok.
"""

from __future__ import absolute_import, print_function

import panflute.defs
import panflute.tests.mpris

import os.path


class Launcher (panflute.tests.mpris.Launcher):
    """
    Launcher for testing against Amarok.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.mpris.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                "Amarok")

        # Amarok uses KDE's global module location system to find its plugins,
        # so environment variables need to point to the right places.

        self.augment_env_path ("KDEDIRS", prefix)


class Runner (panflute.tests.mpris.Runner):
    """
    Runner for testing against Amarok.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.mpris.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests, "amarok")


    def prepare_persistent (self):
        # Rebuild KDE's system configuration cache to point to the desired
        # version of Amarok.
        sycoca = self.run_command (["kbuildsycoca4", "--noincremental"])
        sycoca.wait ()


    def prepare_single_mpris (self, prefix, user, password):
        self.rmdirs ("~/.kde/share/apps/amarok")
        self.rmfile ("~/.kde/share/config/amarok-appletsrc")
        self.rmfile ("~/.kde/share/config/amarok_homerc")
        self.rmfile ("~/.kde/share/config/amarokrc")
        self.rmfile ("~/.kde/share/config/kwalletrc")

        self.mkdir ("~/.kde/share/config")

        # Disable Amarok's first-run dialog prompts.
        with open (os.path.expanduser ("~/.kde/share/config/amarokrc"), "w") as rc:
            print ("[General]", file = rc)
            print ("First Run=false", file = rc)
            print ("[Service_LastFm]", file = rc)
            print ("ignoreWallet=yes", file = rc)

        # Likewise, KDE Wallet gets started and has its own first-run dialogs.
        with open (os.path.expanduser ("~/.kde/share/config/kwalletrc"), "w") as rc:
            print ("[Wallet]", file = rc)
            print ("Enabled=false", file = rc)
            print ("First Use=false", file = rc)

        # Actually start Amarok.
        path = os.path.join (prefix, "bin/amarok")
        child = self.run_command ([path])
        self.set_child (child)
