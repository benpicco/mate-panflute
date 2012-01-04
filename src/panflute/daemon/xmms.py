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
Interface translator for XMMS.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import gobject
import xmms.control


class Connector (panflute.daemon.connector.PollingConnector):
    """
    Connection manager for XMMS.
    """

    from panflute.util import log

    GONE_POLL_INTERVAL = 2000


    def __init__ (self):
        panflute.daemon.connector.PollingConnector.__init__ (self, "xmms", "XMMS")
        self.props.icon_name = "xmms"
        self.__gone_poll_source = None


    def root (self, **kwargs):
        return Root (**kwargs)


    def track_list (self, **kwargs):
        # TODO: Implement for real
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


    def try_connect (self):
        if xmms.control.is_running ():
            if self.__gone_poll_source is None:
                self.__gone_poll_source = gobject.timeout_add (self.GONE_POLL_INTERVAL, self.__gone_poll_cb)
            self.props.connected = True


    def __gone_poll_cb (self):
        """
        Check if the XMMS connection is gone.
        """

        if not xmms.control.is_running ():
            self.__gone_poll_source = None
            self.props.connected = False
            return False
        else:
            return True


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS object for XMMS.
    """

    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, "XMMS", **kwargs)


    def do_Quit (self):
        xmms.control.quit ()


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS object for XMMS.
    """

    from panflute.util import log

    POLL_INTERVAL = 1000


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetStatus", "GetMetadata",
                        "Next", "Prev", "Pause", "Stop", "Play",
                        "PositionGet", "PositionSet", "VolumeGet", "VolumeSet"]:
            self.register_feature (feature)

        self.__poll_everything_source = gobject.timeout_add (self.POLL_INTERVAL, self.__poll_everything_cb)
        self.__poll_everything_cb ()


    def remove_from_connection (self):
        if self.__poll_everything_source is not None:
            gobject.source_remove (self.__poll_everything_source)
            self.__poll_everything_source = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Next (self):
        xmms.control.playlist_next ()


    def do_Prev (self):
        xmms.control.playlist_prev ()


    def do_Pause (self):
        if self.cached_status.state == panflute.mpris.STATE_STOPPED:
            xmms.control.play ()
        else:
            xmms.control.pause ()


    def do_Stop (self):
        xmms.control.stop ()


    def do_Play (self):
        xmms.control.play ()


    def do_PositionGet (self):
        return xmms.control.get_output_time ()


    def do_PositionSet (self, position):
        xmms.control.jump_to_time (position)


    def do_VolumeGet (self):
        # XMMS returns -1 if it can't get the volume
        return max (0, xmms.control.get_main_volume ())


    def do_VolumeSet (self, volume):
        xmms.control.set_main_volume (volume)


    def __poll_everything_cb (self):
        """
        Poll for assorted status information.
        """

        if xmms.control.is_paused ():
            self.cached_status.state = panflute.mpris.STATE_PAUSED
        elif xmms.control.is_playing ():
            self.cached_status.state = panflute.mpris.STATE_PLAYING
        else:
            self.cached_status.state = panflute.mpris.STATE_STOPPED

        if self.cached_status.state == panflute.mpris.STATE_PLAYING:
            self.start_polling_for_time ()
        else:
            self.stop_polling_for_time ()

        if xmms.control.is_shuffle ():
            self.cached_status.order = panflute.mpris.ORDER_RANDOM
        else:
            self.cached_status.order = panflute.mpris.ORDER_LINEAR

        if xmms.control.is_repeat ():
            self.cached_status.future = panflute.mpris.FUTURE_CONTINUE
        else:
            self.cached_status.future = panflute.mpris.FUTURE_STOP

        playlist_length = xmms.control.get_playlist_length ()
        if playlist_length > 0:
            pos = xmms.control.get_playlist_pos ()
            metadata = {}

            location = xmms.control.get_playlist_file (pos)
            metadata["location"] = panflute.util.make_url (location)

            metadata["title"] = xmms.control.get_playlist_title (pos)

            time = xmms.control.get_playlist_time (pos)
            if time > 0:
                metadata["mtime"] = time
            else:
                metadata["mtime"] = 0
            metadata["time"] = metadata["mtime"] // 1000

            self.cached_metadata = metadata

            self.cached_caps.play = True
            self.cached_caps.pause = True
            self.cached_caps.provide_metadata = True

            sequential = (self.cached_status.future == panflute.mpris.FUTURE_STOP and
                          self.cached_status.order == panflute.mpris.ORDER_LINEAR)
            self.cached_caps.go_prev = (pos > 0 or not sequential)
            self.cached_caps.go_next = (pos < playlist_length - 1 or not sequential)
            self.cached_caps.seek = (time > 0)
        else:
            self.cached_metadata = {}
            self.cached_caps.all = panflute.mpris.CAN_DO_NOTHING

        return True
