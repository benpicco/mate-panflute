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
Interface translator for Guayadeque.
"""

from __future__ import absolute_import

import panflute.daemon.passthrough


class Connector (panflute.daemon.passthrough.Connector):
    """
    Connection manager for Guayadeque.
    """

    def __init__ (self):
        panflute.daemon.passthrough.Connector.__init__ (self, "guayadeque", "Guayadeque",
                                                        "guayadeque")
        self.props.icon_name = "guayadeque"


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.passthrough.Player):
    """
    Player interface for Guayadeque.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        panflute.daemon.passthrough.Player.__init__ (self, "guayadeque", False, **kwargs)


    def do_Pause (self):
        """
        Guayadeque's Pause method doesn't un-pause, but Play will.
        """

        self._player.GetStatus (reply_handler = self.__get_status_pause_cb,
                                error_handler = self.log.warn)


    def __get_status_pause_cb (self, status):
        """
        Invoke Play or Pause, depending on the current playback state.
        """

        if status[panflute.mpris.STATUS_STATE] == panflute.mpris.STATE_PLAYING:
            self._player.Pause (reply_handler = lambda: None,
                                error_handler = self.log.warn)
        else:
            self._player.Play (reply_handler = lambda: None,
                               error_handler = self.log.warn)


    def _normalize_metadata (self, metadata):
        """
        Convert Guayadeque's reporting of lots of empty fields for a no-song
        condition to the standard representation.
        """

        if metadata is not None and metadata.get ("location", "file://") == "file://":
            return {}
        else:
            return panflute.daemon.passthrough.Player._normalize_metadata (self, metadata)
