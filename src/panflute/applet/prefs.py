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
Preferences dialog for the Panflute GNOME panel applet.
"""

from __future__ import absolute_import

import panflute.defs

import dbus
import functools
import gconf
import gtk
import os.path

def create_preferences_dialog (conf, layout):
    """
    Create a new preferences dialog and return it.
    """

    builder = gtk.Builder ()
    builder.add_from_file (os.path.join (panflute.defs.PKG_DATA_DIR, "preferences.ui"))

    state = Preferences (builder, conf, layout)
    builder.connect_signals (state)

    return builder.get_object ("preferences")


class Preferences (object):
    """
    Object that manages the state of the Preferences dialog produced by
    gtk.Builder.
    """

    from panflute.util import log

    LAY_COL_INTERNAL_NAME = 0
    LAY_COL_DISPLAY_NAME = 1
    LAY_COL_VISIBLE = 2

    CONN_COL_INTERNAL_NAME = 0
    CONN_COL_DISPLAY_NAME = 1

    # Creation and destruction

    def __init__ (self, builder, conf, layout):
        self.__builder = builder
        self.__conf = conf
        self.__layout = layout
        self.__ignore_model_updates = False

        for field in ["title", "artist", "album", "track_number", "genre", "duration", "year"]:
            self.__setattr__ ("metadata_add_{0}_activate_cb".format (field),
                              functools.partial (self.metadata_add_field_activate_cb, field))

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.kuliniewicz.Panflute", "/connectors", follow_name_owner_changes = True)
        self.__connector_manager = dbus.Interface (proxy, "org.kuliniewicz.Panflute.Manager")

        proxy = bus.get_object ("org.kuliniewicz.Panflute", "/connectors/preferred", follow_name_owner_changes = True)
        self.__preferred = dbus.Interface (proxy, "org.kuliniewicz.Panflute.Connector")

        proxy = bus.get_object ("org.freedesktop.DBus", "/org/freedesktop/DBus")
        bus_obj = dbus.Interface (proxy, "org.freedesktop.DBus")

        self.__dbus_handlers = [
            bus_obj.connect_to_signal ("NameOwnerChanged", self.__name_owner_changed_cb,
                                       arg0 = "org.kuliniewicz.Panflute"),
            self.__connector_manager.connect_to_signal ("PreferredChanged", self.__preferred_changed_cb)
        ]

        self.__gconf_handlers = [
            conf.connect_bool ("show_remaining_time", self.__gconf_show_remaining_time_changed_cb, call_now = True),
            conf.connect_bool ("show_notifications", self.__gconf_show_notifications_changed_cb, call_now = True)
        ]

        (first_row, second_row) = layout.props.layout
        for internal_name in first_row + second_row:
            self.__gconf_handlers.append (conf.connect_bool ("show_{0}".format (internal_name),
                                                             functools.partial (self.__update_widget_visibility, internal_name)))

        self.__layout_handlers = [
            layout.connect ("notify::layout", lambda layout, pspec: self.__load_layout ())
        ]

        # No good way to do this from Glade 3, so...
        sel = self.__builder.get_object ("layout_view").get_selection ()
        sel.connect ("changed", self.__layout_selection_changed_cb)

        self.__load_layout ()
        self.__load_metadata ()
        self.__load_players ()


    def preferences_destroy_cb (self, dialog):
        """
        Clean up when the preferences dialog is destroyed.
        """

        for handler in self.__dbus_handlers:
            handler.remove ()
        self.__dbus_handlers = []

        for handler in self.__gconf_handlers:
            self.__conf.disconnect (handler)
        self.__gconf_handlers = []

        for handler in self.__layout_handlers:
            self.__layout.handler_disconnect (handler)
        self.__layout_handlers = []


    # show_remaining_time


    def time_elapsed_toggled_cb (self, toggle_button):
        """
        Update GConf with the new show_remaining_time setting, if the radio
        button for Elapsed was set.
        """

        if toggle_button.get_active ():
            self.__conf.set_bool ("show_remaining_time", False)


    def time_remaining_toggled_cb (self, toggle_button):
        """
        Update GConf with the new show_remaining_time setting, if the radio
        button for Remaining was set.
        """

        if toggle_button.get_active ():
            self.__conf.set_bool ("show_remaining_time", True)


    def __gconf_show_remaining_time_changed_cb (self, value):
        """
        Update the dialog with the new show_remaining_time setting in GConf.
        """

        if value:
            self.__builder.get_object ("time_remaining").set_active (True)
        else:
            self.__builder.get_object ("time_elapsed").set_active (True)


    # show_notifications


    def show_notifications_toggled_cb (self, toggle_button):
        """
        Update GConf with the new show_notifications setting.
        """

        self.__conf.set_bool ("show_notifications", toggle_button.get_active ())


    def __gconf_show_notifications_changed_cb (self, value):
        """
        Update the dialog with the new show_notifications setting in GConf.
        """

        self.__builder.get_object ("show_notifications").set_active (value)


    # widget_order and show_[widget]


    def layout_visible_renderer_toggled_cb (self, renderer, path):
        """
        Toggle the check box for a widget's visibility and propagate the
        change to GConf.
        """

        model = self.__builder.get_object ("layout_store")
        if model[path][self.LAY_COL_INTERNAL_NAME] != self.__layout.ROW_DIVIDER:
            new_visibility = not model[path][self.LAY_COL_VISIBLE]

            self.log.debug ("Setting {0} visibility to {1}".format (model[path][self.LAY_COL_INTERNAL_NAME], new_visibility))

            model[path][self.LAY_COL_VISIBLE] = new_visibility
            self.__conf.set_bool ("show_{0}".format (model[path][self.LAY_COL_INTERNAL_NAME]), new_visibility)


    def layout_top_clicked_cb (self, button):
        """
        Move the selected widget to the top of the list.
        """

        sel = self.__builder.get_object ("layout_view").get_selection ()
        model, iter = sel.get_selected ()
        if iter is not None:
            model.move_after (iter, None)
            self.__layout_selection_changed_cb (sel)


    def layout_bottom_clicked_cb (self, button):
        """
        Move the selected widget to the bottom of the list.
        """

        sel = self.__builder.get_object ("layout_view").get_selection ()
        model, iter = sel.get_selected ()
        if iter is not None:
            model.move_before (iter, None)
            self.__layout_selection_changed_cb (sel)


    def layout_up_clicked_cb (self, button):
        """
        Move the selected widget up one row in the list.
        """

        sel = self.__builder.get_object ("layout_view").get_selection ()
        model, iter = sel.get_selected ()
        if iter is not None:
            # Annoying, there's no iter_prev...
            (index,) = model.get_path (iter)
            if index > 0:
                prev = model.get_iter ((index - 1,))
                model.swap (iter, prev)
                self.__layout_selection_changed_cb (sel)


    def layout_down_clicked_cb (self, button):
        """
        Move the selected widget down one row in the list.
        """

        sel = self.__builder.get_object ("layout_view").get_selection ()
        model, iter = sel.get_selected ()
        if iter is not None:
            next = model.iter_next (iter)
            if next is not None:
                model.swap (iter, next)
                self.__layout_selection_changed_cb (sel)


    def layout_swap_clicked_cb (self, button):
        """
        Swap the contents of the two conceptual rows in the layout.
        """

        order = self.__get_internal_order ()
        sep = order.index (self.__layout.ROW_DIVIDER)
        swapped = order[sep + 1 :] + [self.__layout.ROW_DIVIDER] + order[: sep]
        self.__conf.set_string_list ("widget_order", swapped)


    def __layout_selection_changed_cb (self, sel):
        """
        Enable or disable the layout buttons according to the selection.
        """

        model, iter = sel.get_selected ()
        if iter is not None:
            is_first = (model.get_path (iter) == (0,))
            is_last = (model.iter_next (iter) is None)
        else:
            is_first = True
            is_last = True

        self.__builder.get_object ("layout_top").props.sensitive = not is_first
        self.__builder.get_object ("layout_up").props.sensitive = not is_first
        self.__builder.get_object ("layout_down").props.sensitive = not is_last
        self.__builder.get_object ("layout_bottom").props.sensitive = not is_last


    def layout_store_rows_reordered_cb (self, model, path, iter, new_order):
        """
        Update GConf with the new requested widget order.

        This gets called when the reordering buttons are used; swapping
        rows is considered a reordering.
        """

        if not self.__ignore_model_updates:
            self.log.debug ("Rows reordered: {0}".format (path))
            self.__push_order_to_gconf ()


    def layout_store_row_inserted_cb (self, model, path, iter):
        """
        Do nothing except print a debug message.
        """

        if not self.__ignore_model_updates:
            self.log.debug ("Row inserted: {0}".format (path))


    def layout_store_row_deleted_cb (self, model, path):
        """
        Update GConf with the new requested widget order.

        When the default drag-and-drop-to-reorder behavior happens, the view
        inserts a copy of the row(s) in the new position before deleting the
        old row(s).  So, pushing the change to the LayoutManager only when
        we get the row-deleted signal does what we want.
        """

        if not self.__ignore_model_updates:
            self.log.debug ("Row deleted: {0}".format (path))
            self.__push_order_to_gconf ()


    def __push_order_to_gconf (self):
        """
        Update GConf with the new requested widget order.
        """

        self.__conf.set_string_list ("widget_order", self.__get_internal_order ())


    def __load_layout (self):
        """
        Populate the layout model with the currently defined widget layout,
        discarding whatever might be there currently.
        """

        # Avoid replacing the model contents if there's no real change, which
        # happens if this dialog was what made the change in GConf to begin
        # with.

        new_order = self.__get_manager_order ()
        if new_order != self.__get_internal_order ():
            try:
                self.__ignore_model_updates = True
                model = self.__builder.get_object ("layout_store")
                model.clear ()

                for internal_name in new_order:
                    display_name = self.__layout.get_display_name (internal_name)
                    if internal_name != self.__layout.ROW_DIVIDER:
                        visible = self.__conf.get_bool ("show_{0}".format (internal_name))
                    else:
                        visible = True
                    model.append ((internal_name, display_name, visible))
            finally:
                self.__ignore_model_updates = False


    def __get_manager_order (self):
        """
        Get the widget order currently stored in the layout manager.
        """

        first_row, second_row = self.__layout.props.layout
        return first_row + [self.__layout.ROW_DIVIDER] + second_row


    def __get_internal_order (self):
        """
        Get the widget order as currently listed in the model.
        """

        order = []
        def append (model, path, iter):
            order.append (model[iter][self.LAY_COL_INTERNAL_NAME])
        self.__builder.get_object ("layout_store").foreach (append)
        return order


    def __update_widget_visibility (self, internal_name, visible):
        """
        Update the visibility check box for a widget when its status in GConf
        changes.
        """

        # XXX: Is it worth it to make finding the correct row faster?

        def update (model, path, iter):
            if model.get_value (iter, self.LAY_COL_INTERNAL_NAME) == internal_name:
                model.set_value (iter, self.LAY_COL_VISIBLE, visible)
        self.__builder.get_object ("layout_store").foreach (update)


    # the daemon's preferred_player


    def __load_players (self):
        """
        Populate the combo box with the list of available players.
        """

        self.__connector_manager.DescribeConnectors (reply_handler = self.__describe_connectors_cb,
                                                     error_handler = self.log.warn)


    def __describe_connectors_cb (self, connectors):
        """
        Update the combo box with the current list of available players.
        """

        model = self.__builder.get_object ("connector_store")
        model.clear ()

        for internal_name in connectors:
            display_name = connectors[internal_name]["display_name"]
            icon_name = connectors[internal_name].get ("icon_name", "")
            model.append ((internal_name, display_name, icon_name))
        model.set_sort_column_id (self.CONN_COL_DISPLAY_NAME, gtk.SORT_ASCENDING)

        self.__preferred.GetInternalName (reply_handler = self.__get_internal_name_cb,
                                          error_handler = self.log.warn)


    def __get_internal_name_cb (self, internal_name):
        """
        Select the currently preferred player in the combo box.
        """

        # XXX: Is it worth it to make finding the correct row faster?

        def check (model, path, iter):
            if model.get_value (iter, self.CONN_COL_INTERNAL_NAME) == internal_name:
                self.__builder.get_object ("preferred_player").set_active_iter (iter)
        self.__builder.get_object ("connector_store").foreach (check)


    def __name_owner_changed_cb (self, name, old_owner, new_owner):
        """
        When the Panflute daemon object has a new owner, reload the list of
        available players.
        """

        if new_owner != "":
            self.__load_players ()


    def __preferred_changed_cb (self):
        """
        When the daemon reports a change in the preferred player, update the
        combo box selection accordingly.
        """

        self.__preferred.GetInternalName (reply_handler = self.__get_internal_name_cb,
                                          error_handler = self.log.warn)


    def preferred_player_changed_cb (self, preferred):
        """
        Update the daemon's GConf setting with the newly selected preferred
        player.
        """

        model = preferred.get_model ()
        iter = preferred.get_active_iter ()

        client = gconf.client_get_default ()
        client.set_string ("/apps/panflute/daemon/preferred_player", model[iter][self.CONN_COL_INTERNAL_NAME])


    # contents of the metadata scroller


    def __load_metadata (self):
        """
        Load the GConf setting for the metadata into the text buffer.
        """

        buffer = self.__builder.get_object ("metadata_buffer")
        strings = self.__conf.get_string_list ("metadata_lines")
        buffer.set_text ("\n".join (strings))


    def metadata_buffer_changed_cb (self, buffer):
        """
        Update GConf with the new metadata format strings.
        """

        begin, end = buffer.get_bounds ()
        text = buffer.get_text (begin, end)
        strings = text.split ("\n")
        self.__conf.set_string_list ("metadata_lines", strings)


    def metadata_add_clicked_cb (self, button):
        """
        Prompt for a metadata field to insert.
        """

        menu = self.__builder.get_object ("metadata_popup_menu")
        if menu.get_attach_widget () != button:
            menu.attach_to_widget (button, None)
        menu.popup (None, None, None, 0, gtk.get_current_event_time ())


    def metadata_add_field_activate_cb (self, name, item):
        """
        Insert the field specified in the menu item's name into the metadata
        format buffer.
        """

        buffer = self.__builder.get_object ("metadata_buffer")
        buffer.insert_at_cursor ("{{{0}}}".format (name))


    def metadata_default_clicked_cb (self, button):
        """
        Restore the metadata buffer to its default value.
        """

        client = gconf.client_get_default ()
        schema = client.get_schema ("/schemas/apps/panflute/applet/prefs/metadata_lines")
        default = schema.get_default_value ()
        strings = [v.get_string () for v in default.get_list ()]

        buffer = self.__builder.get_object ("metadata_buffer")
        buffer.set_text ("\n".join (strings))
