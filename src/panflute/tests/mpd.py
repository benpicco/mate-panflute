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
Execution context for testing against MPD.
"""

from __future__ import absolute_import, print_function

import panflute.defs
import panflute.tests.runner

import mpd
import os.path
import socket
import time


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing MPD.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "MPD")


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing MPD.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)


    def prepare_single (self, prefix, user, password):
        self.rmdirs ("~/.mpd")
        self.mkdir ("~/.mpd")

        with open (os.path.expanduser ("~/.mpd/mpd.conf"), "w") as conf:
            print ("music_directory \"{0}\"".format (panflute.defs.PKG_DATA_DIR), file = conf)
            print ("db_file \"~/.mpd/database\"", file = conf)
            print ("audio_output {", file = conf)
            print ("\ttype \"alsa\"", file = conf)
            print ("\tname \"Compatibility with Ubuntu\"", file = conf)
            print ("\tdevice \"pulse\"", file = conf)
            print ("\tmixer_control \"Master\"", file = conf)
            print ("}", file = conf)

        path = os.path.join (prefix, "bin/mpd")
        child = self.run_command ([path])
        self.set_child (child)

        client = self.__connect ()
        if client is not None:
            for path in self.TONE_PATHS:
                filename = path.split ("/")[-1]
                client.add (filename)
            client.close ()
        else:
            raise panflute.tests.runner.TestError ()


    def cleanup_single (self):
        self.run_command (["killall", "mpd"])


    def __connect (self):
        """
        Try to establish a direct connection to the MPD daemon.
        """

        client = mpd.MPDClient ()
        tries = 10
        while tries > 0:
            try:
                client.connect ("localhost", 6600)
                return client
            except socket.error:
                tries = tries - 1
                time.sleep (1)
        return None
