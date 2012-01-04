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
MPRIS constants useful for both clients and servers.
"""

from __future__ import absolute_import

INTERFACE = "org.freedesktop.MediaPlayer"

# Status tuple constants and indexes.

STATUS_STATE  = 0
STATUS_ORDER  = 1
STATUS_NEXT   = 2
STATUS_FUTURE = 3

STATE_MIN = 0
STATE_PLAYING = 0
STATE_PAUSED = 1
STATE_STOPPED = 2
STATE_MAX = 2

ORDER_MIN = 0
ORDER_LINEAR = 0
ORDER_RANDOM = 1
ORDER_MAX = 1

NEXT_MIN = 0
NEXT_NEXT = 0
NEXT_REPEAT = 1
NEXT_MAX = 1

FUTURE_MIN = 0
FUTURE_STOP = 0
FUTURE_CONTINUE = 1
FUTURE_MAX = 1

# Capability flags

CAN_DO_NOTHING       = 0
CAN_GO_NEXT          = 1 << 0
CAN_GO_PREV          = 1 << 1
CAN_PAUSE            = 1 << 2
CAN_PLAY             = 1 << 3
CAN_SEEK             = 1 << 4
CAN_PROVIDE_METADATA = 1 << 5
CAN_HAS_TRACKLIST    = 1 << 6

CAPABILITY_MASK = 0x7f

# Volume bounds

VOLUME_MIN = 0
VOLUME_MAX = 100
