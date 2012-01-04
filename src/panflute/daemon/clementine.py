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
Interface translator for Clementine.
"""

from __future__ import absolute_import

import panflute.daemon.passthrough
import panflute.mpris

import dbus


class Connector (panflute.daemon.passthrough.Connector):
    """
    Connection manager for Clementine.
    """

    def __init__ (self):
        panflute.daemon.passthrough.Connector.__init__ (self, "clementine", "Clementine",
                                                        "clementine")
        self.props.icon_name = "application-x-clementine"


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.passthrough.Player):
    """
    Player interface for Clementine.
    """

    def __init__ (self, **kwargs):
        panflute.daemon.passthrough.Player.__init__ (self, "clementine", False, **kwargs)

        # Clementine 0.5.3 (and others?) send signals from the wrong MPRIS object.

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.mpris.clementine", "/TrackList")
        tracklist = dbus.Interface (proxy, panflute.mpris.INTERFACE)

        self.__extra_handlers = [
            tracklist.connect_to_signal ("TrackChange", self.do_TrackChange),
            tracklist.connect_to_signal ("StatusChange", self.do_StatusChange),
            tracklist.connect_to_signal ("CapsChange", self.do_CapsChange)
        ]


    def remote_from_connection (self):
        for handler in self.__extra_handlers:
            handler.remove ()
        self.__extra_handlers = []

        panflute.daemon.passthrough.Player.remove_from_connection (self)


    def _normalize_metadata (self, metadata):
        # Clementine (0.5.3) always reports mtime as zero
        if metadata is not None:
            if "time" in metadata and metadata.get ("mtime", 0) == 0:
                metadata["mtime"] = metadata["time"] * 1000

        return panflute.daemon.passthrough.Player._normalize_metadata (self, metadata)


    def do_StatusChange (self, status):
        # Clementine (0.5.3) signals Stopped when playback first starts
        if status[panflute.mpris.STATUS_STATE] == panflute.mpris.STATE_STOPPED:
            status = self._player.GetStatus ()
        return panflute.daemon.passthrough.Player.do_StatusChange (self, status)
