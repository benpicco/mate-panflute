#! /usr/bin/env python

# Panflute
# Copyright (C) 2009 Paul Kuliniewicz <paul@kuliniewicz.org>
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
Interface translator for Songbird.
"""

from __future__ import absolute_import

import panflute.daemon.passthrough
import panflute.mpris

import dbus


class Connector (panflute.daemon.passthrough.Connector):
    """
    Connection manager for Songbird.
    """

    def __init__ (self):
        panflute.daemon.passthrough.Connector.__init__ (self, "songbird", "Songbird",
                                                        "songbird")
        self.props.icon_name = "songbird"

    def player (self, **kwargs):
        return Player (self.__name, **kwargs)


class Player (panflute.daemon.passthrough.Player):
    """
    Player interface for Songbird.
    """

    from panflute.util import log


    def __init__ (self, name, **kwargs):
        panflute.daemon.passthrough.Player.__init__ (self, name, False, **kwargs)
        self.register_feature ("SetMetadata")
        self.register_feature ("SetMetadata:rating")


    def do_SetMetadata (self, name, value):
        self._player.SetMetadata (name, str (value),
                                  reply_handler = self.__refresh_metadata,
                                  error_handler = self.log.warn)


    def __refresh_metadata (self):
        """
        Force a refresh of the metadata after it's been changed.

        Also has the nice side effect of getting Songbird to refresh its own
        display of the song's metadata.
        """

        metadata = self.do_GetMetadata ()
        self.do_TrackChange (metadata)
