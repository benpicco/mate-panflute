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
Interface translator for Audacious.

This is *almost* a passthrough, except that Audacious deviates from the
MPRIS spec in status reporting -- GetStatus or StatusChange may only
report an int (state code) instead of the full four-tuple.
"""

from __future__ import absolute_import

import panflute.daemon.passthrough
import panflute.mpris

import dbus


class Connector (panflute.daemon.passthrough.Connector):
    """
    Connection manager for Audacious.
    """

    def __init__ (self):
        panflute.daemon.passthrough.Connector.__init__ (self, "audacious", "Audacious",
                                                        "audacious")
        self.props.icon_name = "audacious"


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.passthrough.Player):
    """
    Player interface for Audacious.

    Responsible for fixing Audacious's deviation from the MPRIS spec.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        panflute.daemon.passthrough.Player.__init__ (self, "audacious", True, **kwargs)


    def do_PositionChange (self, position):
        """
        Audacious 2.1 doesn't signal when playback stops, so if the
        position has become zero, check the status manually.
        """

        panflute.daemon.passthrough.Player.do_PositionChange (self, position)
        if position == 0:
            status = self.do_GetStatus ()
            if status[panflute.mpris.STATUS_STATE] == panflute.mpris.STATE_STOPPED:
                self.log.debug ("Manually reporting Audacious has stopped")
                self.do_StatusChange (status)


    def do_GetStatus (self):
        status = panflute.daemon.passthrough.Player.do_GetStatus (self)
        return self.__fix_status (status)


    def _get_status_cb (self, status):
        # Override of the base class's callback for the inital call to GetStatus.
        good = self.__fix_status (status)
        panflute.daemon.passthrough.Player._get_status_cb (self, good)


    def do_StatusChange (self, status):
        # Just to make things more annoying, the StatusChange signals that
        # Audacious 2.1 sends are completely bogus.  If one of those is
        # detected, ignore the signal and call GetStatus, which returns
        # sane values.

        good = self.__fix_status (status)
        if good[panflute.mpris.STATUS_STATE] > panflute.mpris.STATE_MAX:
            self.log.debug ("ignoring bogus StatusChange of {0}".format (status))
            self._player.GetStatus (reply_handler = self.do_StatusChange,
                                    error_handler = self.log.warn)
        else:
            panflute.daemon.passthrough.Player.do_StatusChange (self, good)


    def __fix_status (self, status):
        """
        Convert a noncompliant status value to a compliant one.
        """

        self.log.debug ("status to fix: {0} (type {1})".format (status, type (status)))

        if type (status) == dbus.Struct or type (status) == tuple:
            return status
        else:
            # TODO: Try to get the real values for the other three
            return (status, panflute.mpris.ORDER_LINEAR, panflute.mpris.NEXT_NEXT, panflute.mpris.FUTURE_CONTINUE)


    def _normalize_metadata (self, metadata):
        """
        Fix how older versions of Audacious misreport the URI of the song.
        """

        if metadata is not None:
            if metadata.has_key ("URI") and not metadata.has_key ("location"):
                metadata["location"] = metadata["URI"]

        return panflute.daemon.passthrough.Player._normalize_metadata (self, metadata)
