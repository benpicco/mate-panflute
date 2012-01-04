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
Interface translator for VLC.

Little more than a simple passthrough.
"""

from __future__ import absolute_import

import panflute.daemon.passthrough
import panflute.mpris

import gobject


class Connector (panflute.daemon.passthrough.Connector):
    """
    Connection manager for VLC.
    """

    def __init__ (self):
        panflute.daemon.passthrough.Connector.__init__ (self, "vlc", "VLC",
                                                        "vlc")
        self.props.icon_name = "vlc"


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.passthrough.Player):
    """
    Player interface for VLC.

    Tries harder to fetch album art, since VLC doesn't always include it in
    the TrackChanged signal.  Also works around VLC 1.0.x's failure to always
    send signals when it should.
    """

    from panflute.util import log

    ART_FETCH_DELAY = 3000
    POLL_WORKAROUND_INTERVAL = 1000


    def __init__ (self, **kwargs):
        panflute.daemon.passthrough.Player.__init__ (self, "vlc", True, **kwargs)

        # VLC 1.0.x doesn't report status changed reliably, so poll for them
        self.__poll_workaround_source = gobject.timeout_add (self.POLL_WORKAROUND_INTERVAL,
                                                             self.__poll_workaround_cb)


    def remove_from_connection (self):
        if self.__poll_workaround_source is not None:
            gobject.source_remove (self.__poll_workaround_source)
            self.__poll_workaround_source = None

        panflute.daemon.passthrough.Player.remove_from_connection (self)


    def do_TrackChange (self, metadata):
        if metadata is not None and metadata.has_key ("location") and not metadata.has_key ("arturl"):
            gobject.timeout_add (self.ART_FETCH_DELAY, self.__check_for_art)
        panflute.daemon.passthrough.Player.do_TrackChange (self, metadata)


    def __check_for_art (self):
        """
        Fetch the current metadata and report a change if there's now art
        available.
        """

        self.log.debug ("Checking for delayed art")
        new_metadata = self.do_GetMetadata ()
        if new_metadata.has_key ("arturl"):
            self.do_TrackChange (new_metadata)


    def _normalize_metadata (self, metadata):
        """
        Compensate for how VLC uses "title" for the stream name and "nowplaying"
        for the song currently being streamed.
        """

        if metadata is not None:
            if metadata.has_key ("nowplaying"):
                metadata["album"] = metadata["title"]
                metadata["title"] = metadata["nowplaying"]
                del metadata["nowplaying"]

        return panflute.daemon.passthrough.Player._normalize_metadata (self, metadata)


    def __poll_workaround_cb (self):
        """
        Poll for things that VLC 1.0.x doesn't reliably signal.
        """

        self._player.GetCaps (reply_handler = self.__get_caps_cb,
                              error_handler = self.log.warn)
        self._player.GetStatus (reply_handler = self.__get_status_cb,
                                error_handler = self.log.warn)
        self._player.GetMetadata (reply_handler = self.__get_metadata_cb,
                                  error_handler = self.log.warn)
        return True


    def __get_caps_cb (self, caps):
        """
        Update the capabilities cache.
        """

        # VLC 1.0.x doesn't reliably report pausability when first playing.
        modifier = 0
        if self.cached_metadata.get ("time", 0) > 0:
            modifier = panflute.mpris.CAN_PAUSE

        self.cached_caps.all = caps | modifier


    def __get_status_cb (self, status):
        """
        Update the status cache.
        """

        self.cached_status = status


    def __get_metadata_cb (self, metadata = None):
        """
        Update the metadata cache.
        """

        if metadata is not None:
            self.cached_metadata = self._normalize_metadata (metadata)
        else:
            self.cached_metadata = {}
