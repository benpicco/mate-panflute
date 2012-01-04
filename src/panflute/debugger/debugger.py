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
The main window for the graphical debugger.
"""

from __future__ import absolute_import

import panflute.mpris

import dbus
from   gettext import gettext as _
import gtk
import time


class Debugger (object):
    """
    The Debugger itself.
    """

    COL_NAME      = 0
    COL_SIGNALLED = 1
    COL_DIRECT    = 2
    COL_MASK      = 3

    COL_TIMESTAMP = 0
    COL_STOCK     = 1
    COL_CATEGORY  = 2
    COL_MESSAGE   = 3

    LOG_GENERAL = _("General")
    LOG_DBUS    = _("D-Bus")


    def __init__ (self, builder):
        self.__player_store = builder.get_object ("player_store")
        self.__event_store = builder.get_object ("event_store")
        self.__initialize_player_tree ()
        self.__initialize_log (builder)
        self.__initialize_dbus (builder)

        builder.connect_signals (self)


    def debugger_delete_event_cb (self, debugger, event):
        gtk.main_quit ()


    def __initialize_player_tree (self):
        """
        Put the basic structural elements in the player store.
        """

        position = self.__player_store.append (None, (_("Position"), "", "", 0))

        caps = self.__player_store.append (None, (_("Capabilities"), "", "", 0))
        self.__player_store.append (caps, ("CAN_GO_NEXT", "", "", panflute.mpris.CAN_GO_NEXT))
        self.__player_store.append (caps, ("CAN_GO_PREV", "", "", panflute.mpris.CAN_GO_PREV))
        self.__player_store.append (caps, ("CAN_PAUSE", "", "", panflute.mpris.CAN_PAUSE))
        self.__player_store.append (caps, ("CAN_PLAY", "", "", panflute.mpris.CAN_PLAY))
        self.__player_store.append (caps, ("CAN_SEEK", "", "", panflute.mpris.CAN_SEEK))
        self.__player_store.append (caps, ("CAN_PROVIDE_METADATA", "", "", panflute.mpris.CAN_PROVIDE_METADATA))
        self.__player_store.append (caps, ("CAN_HAS_TRACKLIST", "", "", panflute.mpris.CAN_HAS_TRACKLIST))

        status = self.__player_store.append (None, (_("Status"), "", "", 0))
        self.__player_store.append (status, (_("State"), "", "", panflute.mpris.STATUS_STATE))
        self.__player_store.append (status, (_("Order"), "", "", panflute.mpris.STATUS_ORDER))
        self.__player_store.append (status, (_("Next"), "", "", panflute.mpris.STATUS_NEXT))
        self.__player_store.append (status, (_("Future"), "", "", panflute.mpris.STATUS_FUTURE))

        track = self.__player_store.append (None, (_("Track"), "", "", 0))

        features = self.__player_store.append (None, (_("Features"), "", "", 0))

        self.__position_path = self.__player_store.get_path (position)
        self.__caps_path = self.__player_store.get_path (caps)
        self.__status_path = self.__player_store.get_path (status)
        self.__track_path = self.__player_store.get_path (track)
        self.__features_path = self.__player_store.get_path (features)


    def __initialize_log (self, builder):
        """
        Set up the event log.
        """

        column = builder.get_object ("timestamp_column")
        renderer = builder.get_object ("timestamp_renderer")
        column.set_cell_data_func (renderer, self.__render_timestamp, None)

        self.log_info (self.LOG_GENERAL, _("Started debugger"))


    def __render_timestamp (self, column, cell, model, iter, user_data):
        """
        Render a timestamp in a more readable form.
        """

        (raw,) = model.get (iter, self.COL_TIMESTAMP)
        local = time.localtime (raw)
        # To translators: Python strftime format string, e.g. 20-Jun-2010 14:24:59
        text = time.strftime (_("%d-%b-%Y %H:%M:%S"), local)
        cell.props.text = text


    def log (self, stock, category, message):
        """
        Add an event to the event log.
        """

        self.__event_store.append ((time.time (), stock, category, message))


    def log_info (self, category, message):
        """
        Add an informational event to the event log.
        """

        self.log (gtk.STOCK_DIALOG_INFO, category, message)


    def log_warning (self, category, message):
        """
        Add a warning event to the event log.
        """

        self.log (gtk.STOCK_DIALOG_WARNING, category, message)


    def log_error (self, category, message):
        """
        Add an error event to the event log.
        """

        self.log (gtk.STOCK_DIALOG_ERROR, category, message)


    def log_dbus_error (self, message):
        """
        Add a D-Bus error event to the event log.
        """

        self.log_error (self.LOG_DBUS, message)


    def __initialize_dbus (self, builder):
        """
        Set up D-Bus handlers and check for whether Panflute is running.
        """

        self.__refresh_button = builder.get_object ("player_refresh")
        self.__destroy_proxies ()

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.freedesktop.DBus", "/org/freedesktop/DBus")
        self.__bus = dbus.Interface (proxy, "org.freedesktop.DBus")

        self.__bus.connect_to_signal ("NameOwnerChanged", self.__name_owner_changed_cb,
                                      arg0 = "org.mpris.panflute")

        self.__bus.NameHasOwner ("org.mpris.panflute",
                                 reply_handler = self.__name_has_owner_cb,
                                 error_handler = self.log_dbus_error)


    def __create_proxies (self):
        """
        Create the D-Bus proxy objects.
        """

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.mpris.panflute", "/Player")
        self.__player = dbus.Interface (proxy, panflute.mpris.INTERFACE)
        self.__player_ex = dbus.Interface (proxy, "org.kuliniewicz.Panflute")

        self.__player.connect_to_signal ("CapsChange", self.__caps_change_cb)
        self.__player.connect_to_signal ("StatusChange", self.__status_change_cb)
        self.__player.connect_to_signal ("TrackChange", self.__track_change_cb)
        self.__player_ex.connect_to_signal ("PositionChange", self.__position_change_cb)

        self.__refresh_button.props.sensitive = True


    def __destroy_proxies (self):
        """
        Destroy the D-Bus proxy objects.
        """

        self.__refresh_button.props.sensitive = False
        self.__player = None
        self.__player_ex = None


    def __name_owner_changed_cb (self, name, old_owner, new_owner):
        """
        Called when Panflute appears or disappears from D-Bus.
        """

        if (new_owner != ""):
            self.log_info (self.LOG_DBUS, _("Connected to {0}").format (name))
            self.__create_proxies ()
            self.__direct_refresh ()
        else:
            self.log_info (self.LOG_DBUS, _("Disconnected from {0}").format (name))
            self.__destroy_proxies ()


    def __name_has_owner_cb (self, has_owner):
        """
        Called when the debugger initially checks for Panflute.
        """

        if has_owner:
            self.log_info (self.LOG_DBUS, _("Connected to {0}").format ("org.mpris.panflute"))
            self.__create_proxies ()
            self.__direct_refresh ()


    def player_refresh_clicked_cb (self, button):
        """
        Called when the Refresh button is clicked.
        """

        self.log_info (self.LOG_GENERAL, _("Manual refresh"))
        self.__direct_refresh ()


    def __direct_refresh (self):
        """
        Directly fetch the current status information from Panflute.
        """

        self.__player.GetCaps (reply_handler = self.__get_caps_cb,
                               error_handler = self.log_dbus_error)
        self.__player.GetStatus (reply_handler = self.__get_status_cb,
                                 error_handler = self.log_dbus_error)
        self.__player.GetMetadata (reply_handler = self.__get_metadata_cb,
                                   error_handler = self.log_dbus_error)
        self.__player.PositionGet (reply_handler = self.__position_get_cb,
                                   error_handler = self.log_dbus_error)
        self.__player_ex.GetFeatures (reply_handler = self.__get_features_cb,
                                      error_handler = self.log_dbus_error)


    def __get_caps_cb (self, caps):
        """
        Update the directly-fetched capabilities.
        """

        self.__display_caps (caps, self.COL_DIRECT)


    def __caps_change_cb (self, caps):
        """
        Update the signalled capabilities.
        """

        self.log_info (self.LOG_DBUS, _("Received {0} signal").format ("CapsChange"))
        self.__display_caps (caps, self.COL_SIGNALLED)


    def __display_caps (self, caps, column):
        """
        Update the capabilities in one column of the display.
        """

        parent = self.__player_store.get_iter (self.__caps_path)
        self.__player_store.set (parent, column, "0x{0:04x}".format (caps))

        child = self.__player_store.iter_children (parent)
        while child is not None:
            (mask,) = self.__player_store.get (child, self.COL_MASK)
            if caps & mask:
                value = _("Y")
            else:
                value = _("n")
            self.__player_store.set (child, column, value)
            child = self.__player_store.iter_next (child)


    def __get_status_cb (self, status):
        """
        Update the directly-fetched status.
        """

        self.__display_status (status, self.COL_DIRECT)


    def __status_change_cb (self, status):
        """
        Update the signalled status.
        """

        self.log_info (self.LOG_DBUS, _("Received {0} signal").format ("StatusChange"))
        self.__display_status (status, self.COL_SIGNALLED)


    def __display_status (self, status, column):
        """
        Update the status in one column of the display.
        """

        parent = self.__player_store.get_iter (self.__status_path)
        value = "({0}, {1}, {2}, {3})".format (status[panflute.mpris.STATUS_STATE],
                                               status[panflute.mpris.STATUS_ORDER],
                                               status[panflute.mpris.STATUS_NEXT],
                                               status[panflute.mpris.STATUS_FUTURE])
        self.__player_store.set (parent, column, value)

        child = self.__player_store.iter_children (parent)
        while child is not None:
            (mask,) = self.__player_store.get (child, self.COL_MASK)

            value_str = _("???")
            if mask == panflute.mpris.STATUS_STATE:
                if status[mask] == panflute.mpris.STATE_PLAYING:
                    value_str = _("Playing")
                elif status[mask] == panflute.mpris.STATE_PAUSED:
                    value_str = _("Paused")
                elif status[mask] == panflute.mpris.STATE_STOPPED:
                    value_str = _("Stopped")
            elif mask == panflute.mpris.STATUS_ORDER:
                if status[mask] == panflute.mpris.ORDER_LINEAR:
                    value_str = _("Linear")
                elif status[mask] == panflute.mpris.ORDER_RANDOM:
                    value_str = _("Random")
            elif mask == panflute.mpris.STATUS_NEXT:
                if status[mask] == panflute.mpris.NEXT_NEXT:
                    value_str = _("Next")
                elif status[mask] == panflute.mpris.NEXT_REPEAT:
                    value_str = _("Repeat")
            elif mask == panflute.mpris.STATUS_FUTURE:
                if status[mask] == panflute.mpris.FUTURE_STOP:
                    value_str = _("Stop")
                elif status[mask] == panflute.mpris.FUTURE_CONTINUE:
                    value_str = _("Continue")

            value = "{0} ({1})".format (status[mask], value_str)
            self.__player_store.set (child, column, value)
            child = self.__player_store.iter_next (child)


    def __get_metadata_cb (self, info):
        """
        Update the directly-fetched track information.
        """

        self.__display_track (info, self.COL_DIRECT)


    def __track_change_cb (self, info):
        """
        Update the signalled track information.
        """

        self.log_info (self.LOG_DBUS, _("Received {0} signal").format ("TrackChange"))
        self.__display_track (info, self.COL_SIGNALLED)


    def __display_track (self, info, column):
        """
        Update the track information in one column of the display.
        """

        parent = self.__player_store.get_iter (self.__track_path)

        child = self.__player_store.iter_children (parent)
        while child is not None:
            (key,) = self.__player_store.get (child, self.COL_NAME)
            if key in info:
                value = info[key]
                del info[key]
            else:
                value = None

            self.__player_store.set (child, column, self.__format_track_value (value))

            if self.__player_store.get (child, self.COL_SIGNALLED, self.COL_DIRECT) == (None,None):
                if not self.__player_store.remove (child):
                    child = None
            else:
                child = self.__player_store.iter_next (child)

        for key in info:
            child = self.__player_store.append (parent, (key, None, None, 0))
            self.__player_store.set (child, column, self.__format_track_value (info[key]))


    def __format_track_value (self, value):
        """
        Format a track information value for display.
        """

        if type (value) == dbus.String:
            return "\"{0}\"".format (value)
        else:
            return value


    def __position_get_cb (self, elapsed):
        """
        Update the direct-fetched elapsed time.
        """

        self.__display_position (elapsed, self.COL_DIRECT)


    def __position_change_cb (self, elapsed):
        """
        Update the signalled elapsed time.
        """

        self.log_info (self.LOG_DBUS, _("Received {0} signal").format ("PositionChange"))
        self.__display_position (elapsed, self.COL_SIGNALLED)


    def __display_position (self, elapsed, column):
        """
        Update the elapsed time in one column of the display.
        """

        node = self.__player_store.get_iter (self.__position_path)
        (seconds, milliseconds) = divmod (elapsed, 1000)
        (minutes, seconds) = divmod (seconds, 60)
        (hours, minutes) = divmod (minutes, 60)

        if hours > 0:
            # To translators: elapsed time, formatted as hours:minutes:seconds.milliseconds
            value = _("{hours:d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}").format (hours = hours,
                                                                                          minutes = minutes,
                                                                                          seconds = seconds,
                                                                                          milliseconds = milliseconds)
        else:
            # To translators: elapsed time, formatted as minutes:seconds.milliseconds
            value = _("{minutes:d}:{seconds:02d}.{milliseconds:03d}").format (minutes = minutes,
                                                                              seconds = seconds,
                                                                              milliseconds = milliseconds)

        self.__player_store.set (node, column, value)


    def __get_features_cb (self, features):
        """
        Update the listing of supported Player features.
        """

        parent = self.__player_store.get_iter (self.__features_path)
        child = self.__player_store.iter_children (parent)
        if child is not None:
            while self.__player_store.remove (child):
                pass    # child gets updated after each call to remove

        for feature in features:
            self.__player_store.append (parent, ("", "", feature, 0))
