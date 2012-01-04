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
Testing against Listen.
"""

from __future__ import absolute_import, print_function

import panflute.tests.runner

import dbus
import os
import os.path
import time


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing Listen.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "Listen")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing Listen.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)
        self.__listen = None


    def prepare_single (self, prefix, user, password):
        # Tell Listen where it can find the music files, and to rescan its
        # library on startup.

        self.rmdirs ("~/.config/listen")
        self.mkdir ("~/.config/listen")

        with open (os.path.expanduser ("~/.config/listen/config"), "w") as conf:
            print ("[library]", file = conf)
            print ("location = {0}".format (panflute.defs.PKG_DATA_DIR), file = conf)
            print ("startup_added = true", file = conf)

        path = os.path.join (prefix, "bin/listen")
        child = self.run_command ([path])
        self.set_child (child)

        self.wait_for ("org.mate.Listen", True)
        proxy = self.bus.get_object ("org.mate.Listen", "/org/mate/listen")
        self.__listen = dbus.Interface (proxy, "org.mate.Listen")

        self.__listen.enqueue (self.TONE_URIS)
        # Ugly hack, without which Listen will never start playing.
        time.sleep (2)
        self.__listen.next ()
        self.__listen.play_pause ()


    def cleanup_single (self):
        self.__listen.quit ()
        self.wait_for ("org.mate.Listen", False)
