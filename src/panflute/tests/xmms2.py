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
Testing against XMMS2.
"""

from __future__ import absolute_import

import panflute.tests.runner

import os
import os.path
import sys
import xmmsclient


class Launcher (panflute.tests.runner.Launcher):
    """
    Launch a subprocess for running a series of tests against the same
    player configuration.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data):
        panflute.tests.runner.Launcher.__init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data,
                                                 "XMMS2")

        # The XMMS2 Python client library and server versions *must* be
        # matched, or else *both* may hang indefinitely.  Munge the
        # environment to ensure this happens, and to make sure the XMMS2
        # server binaries can find their libraries.

        libs = os.path.join (prefix, "lib")
        python_version = ".".join (sys.version.split (".", 2)[0:2])
        python_libs = os.path.join (prefix, "lib/python{0}/site-packages".format (python_version))

        self.augment_env_path ("LD_LIBRARY_PATH", libs)
        self.augment_env_path ("PYTHONPATH", python_libs)


class Runner (panflute.tests.runner.Runner):
    """
    Runs a series of tests against a player configuration.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)

        self.__xmms = None


    def prepare_single (self, prefix, user, password):
        """
        Perform setup before each test.
        """

        self.rmdirs ("~/.config/xmms2")

        command = os.path.join (prefix, "bin/xmms2-launcher")
        launcher = self.run_command ([command])
        launcher.wait ()

        self.__xmms = xmmsclient.XMMS ("Panflute-Tester")
        self.__xmms.connect (os.getenv ("XMMS_PATH"))

        result = self.__xmms.playlist_clear ()
        result.wait ()

        for uri in self.TONE_URIS:
            result = self.__xmms.playlist_add_url (uri)
            result.wait ()


    def cleanup_single (self):
        """
        Perform cleanup after each test.
        """

        result = self.__xmms.quit ()
        result.wait ()
