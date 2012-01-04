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
Interface translator for Qmmp.
"""

from __future__ import absolute_import

import panflute.daemon.passthrough


class Connector (panflute.daemon.passthrough.Connector):
    """
    Connection manager for Qmmp.
    """

    def __init__ (self):
        panflute.daemon.passthrough.Connector.__init__ (self, "qmmp", "Qmmp",
                                                        "qmmp")
        self.props.icon_name = "qmmp"


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.passthrough.Player):
    """
    Player interface for Qmmp.
    """

    from panflute.util import log

    def __init__ (self, **kwargs):
        panflute.daemon.passthrough.Player.__init__ (self, "qmmp", False, **kwargs)


    def do_PositionGet (self):
        # Discard bogus results that Qmmp reports when playback starts.
        elapsed = panflute.daemon.passthrough.Player.do_PositionGet (self)
        if elapsed < 0:
            return 0
        else:
            return elapsed


    def _normalize_metadata (self, metadata):
        # Ignore the bogus metadata reported when there's no current song.
        if "location" in metadata and metadata["location"] == "file://":
            return {}

        return panflute.daemon.passthrough.Player._normalize_metadata (self, metadata)
