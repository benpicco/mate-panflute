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
Testing against Pithos.
"""

from __future__ import absolute_import, print_function

import panflute.tests.runner

import dbus
import os.path
import time


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing Pithos.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "Pithos")

        # Make sure Pithos can find its libraries.
        self.augment_env_path ("PYTHONPATH", os.path.join (prefix, "lib/python2.6/site-packages"))


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing Pithos.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)


    def prepare_single (self, prefix, user, password):
        self.rmfile ("~/.config/pithos.ini")
        self.mkdir ("~/.config")

        with open (os.path.expanduser ("~/.config/pithos.ini"), "w") as ini:
            print ("username={0}".format (user), file = ini)
            print ("password={0}".format (password), file = ini)

        path = os.path.join (prefix, "bin/pithos")
        self.__pithos = self.run_command ([path])
        self.set_child (self.__pithos)

        self.wait_for ("net.kevinmehall.Pithos", True)
        proxy = self.bus.get_object ("net.kevinmehall.Pithos", "/net/kevinmehall/Pithos")
        pithos = dbus.Interface (proxy, "net.kevinmehall.Pithos")

        # Pithos starts off playing right away, which the tests don't expect.
        time.sleep (3)
        pithos.PlayPause ()


    def cleanup_single (self):
        try:
            self.__pithos.terminate ()
        except OSError, e:
            pass
        self.wait_for ("net.kevinmehall.Pithos", False)
