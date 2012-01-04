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
Testing against generic MPRIS-based players.
"""

from __future__ import absolute_import

import panflute.mpris
import panflute.tests.runner

import dbus


class Launcher (panflute.tests.runner.Launcher):
    """
    Launcher for testing MPRIS-based players.
    """

    pass


class Runner (panflute.tests.runner.Runner):
    """
    Runner for testing MPRIS-based players.
    """

    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests, mpris_name):
        panflute.tests.runner.Runner.__init__ (self, main_loop, daemon_prefix, prefix, user, password, tests)
        self.__mpris_name = "org.mpris.{0}".format (mpris_name)


    def prepare_single (self, prefix, user, password):
        self.prepare_single_mpris (prefix, user, password)

        self.wait_for (self.__mpris_name, True)

        proxy = self.bus.get_object (self.__mpris_name, "/TrackList")
        track_list = dbus.Interface (proxy, panflute.mpris.INTERFACE)

        for uri in self.TONE_URIS:
            track_list.AddTrack (uri, False)
        if track_list.GetLength () == 0:
            # Some players (e.g. Decibel) don't actually accept URLs
            for path in self.TONE_PATHS:
                track_list.AddTrack (path, False)

    def prepare_single_mpris (self, prefix, user, password):
        """
        Implemented by subclasses to actually start the player, leaving any
        post-start setup to the base class.
        """

        raise NotImplementedError


    def cleanup_single (self):
        proxy = self.bus.get_object (self.__mpris_name, "/")
        root = dbus.Interface (proxy, panflute.mpris.INTERFACE)

        try:
            root.Quit ()
        except dbus.DBusException, e:
            # Not a problem if the player didn't reply before quitting.
            if e.get_dbus_name () != "org.freedesktop.DBus.Error.NoReply":
                raise e
        self.wait_for (self.__mpris_name, False)
