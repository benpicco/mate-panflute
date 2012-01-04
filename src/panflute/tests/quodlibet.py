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
Testing against Quod Libet.
"""

from __future__ import absolute_import, print_function

import panflute.defs
import panflute.tests.runner

import os.path


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing Quod Libet.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "Quod Libet")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing Quod Libet.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)
        self.__child = None


    def prepare_single (self, prefix, user, password):
        self.rmdirs ("~/.quodlibet")
        self.mkdir ("~/.quodlibet")

        with open (os.path.expanduser ("~/.quodlibet/config"), "w") as config:
            print ("[settings]", file = config)
            print ("scan = {0}".format (panflute.defs.PKG_DATA_DIR), file = config)
            print ("", file = config)
            print ("[browsers]", file = config)
            print ("query_text = panflute", file = config)

        path = os.path.join (prefix, "quodlibet.py")
        self.__quodlibet = self.run_command ([path])
        self.set_child (self.__quodlibet)

        self.wait_for ("net.sacredchao.QuodLibet", True)


    def cleanup_single (self):
        self.__quodlibet.terminate ()
        self.__quodlibet = None
        self.wait_for ("net.sacredchao.QuodLibet", False)
