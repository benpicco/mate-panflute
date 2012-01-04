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
The main window for the graphical tester.
"""

from __future__ import absolute_import, print_function

import panflute.defs
import panflute.tests.amarok
import panflute.tests.audacious
import panflute.tests.banshee
import panflute.tests.clementine
import panflute.tests.decibel
import panflute.tests.exaile
import panflute.tests.guayadeque
import panflute.tests.listen
import panflute.tests.muine
import panflute.tests.pithos
import panflute.tests.qmmp
import panflute.tests.quodlibet
import panflute.tests.rhythmbox
import panflute.tests.songbird
import panflute.tests.testcase
import panflute.tests.vlc

import cPickle
import dbus
from   gettext import gettext as _
import gobject
import gtk
import os.path
import sys
import threading
import traceback


class Tester (object):
    """
    The tester itself.
    """

    COL_NAME     = 0
    COL_VERSION  = 1
    COL_PREFIX   = 2
    COL_RESULT   = 3
    COL_DETAIL   = 4
    COL_COMMENT  = 5
    COL_USER     = 6
    COL_PASSWORD = 7

    MUTATORS = ["panflute_prefix", "run", "clear", "add", "remove", "player", "version", "prefix", "user", "password"]
    USER_DATA_DIR = os.getenv ("XDG_DATA_HOME", os.path.expanduser ("~/.local/share"))
    SAVE_DIR = os.path.join (USER_DATA_DIR, "panflute")
    SAVE_FILE = os.path.join (SAVE_DIR, "tester.dat")

    # Commented-out ones get loaded later on, since importing
    # their modules could fail due to missing dependencies
    PLAYERS = {
        "Amarok": panflute.tests.amarok,
        "Audacious": panflute.tests.audacious,
        "Banshee": panflute.tests.banshee,
        "Clementine": panflute.tests.clementine,
        "Decibel": panflute.tests.decibel,
        "Exaile": panflute.tests.exaile,
        "Guayadeque": panflute.tests.guayadeque,
        "Listen": panflute.tests.listen,
        # "MOC": panflute.tests.moc,
        # "MPD": panflute.tests.mpd,
        "Muine": panflute.tests.muine,
        "Pithos": panflute.tests.pithos,
        "Qmmp": panflute.tests.qmmp,
        "Quod Libet": panflute.tests.quodlibet,
        "Rhythmbox": panflute.tests.rhythmbox,
        "Songbird": panflute.tests.songbird,
        "VLC": panflute.tests.vlc,
        # "XMMS": panflute.tests.xmms,
        # "XMMS2": panflute.tests.xmms2
    }


    def __init__ (self, builder):
        self.__test_store = builder.get_object ("test_store")
        self.__builder = builder
        self.__bus = dbus.SessionBus ()

        status = builder.get_object ("status")
        self.__progress_id = status.get_context_id ("Test progress")

        self.__launchers = []

        self.__initialize_player_list ()
        self.__initialize_test_tree ()
        builder.connect_signals (self)


    def __initialize_player_list (self):
        """
        Populate the list of supported players.
        """

        player_store = self.__builder.get_object ("player_store")
        players = self.PLAYERS.keys ()
        players.sort ()
        for name in players:
            player_store.append ((name,))


    def __initialize_test_tree (self):
        """
        Populate the tree of tests.
        """

        self.__edit_iter = None

        view = self.__builder.get_object ("test_view")
        sel = view.get_selection ()
        sel.set_mode (gtk.SELECTION_MULTIPLE)
        sel.connect ("changed", self.__selection_changed_cb)

        self.__test_store.set_sort_func (self.COL_NAME, self.__sort_name_version_cb)

        self.__load ()


    def __add_player (self, config):
        """
        Add a player to the test tree.
        """

        player = self.__test_store.append (None,
                (config.name, config.version, config.prefix, "", "", config.comment, config.user, config.password))
        for test in panflute.tests.testcase.ALL_TESTS:
            testname = test.__class__.__name__
            if testname in config.results:
                result = config.results[testname].result
                detail = config.results[testname].detail
                comment = config.results[testname].comment
            else:
                result = ""
                detail = ""
                comment = ""
            self.__test_store.append (player, (testname, "", "", result, detail, comment, "", ""))
        return player


    def clear_clicked_cb (self, button):
        """
        Clear all selected test results.
        """

        test_view = self.__builder.get_object ("test_view")
        test_sel = test_view.get_selection ()

        parent = self.__test_store.get_iter_first ()
        while parent is not None:
            changed_something = False
            child = self.__test_store.iter_children (parent)
            while child is not None:
                result = self.__test_store.get_value (child, self.COL_RESULT)
                if result != "" and (test_sel.iter_is_selected (child) or test_sel.iter_is_selected (parent) or
                                     test_sel.count_selected_rows () == 0):
                    self.__test_store.set (child, self.COL_RESULT, "", self.COL_DETAIL, "")
                    changed_something = True
                child = self.__test_store.iter_next (child)
            if changed_something:
                self.__summarize_parent (parent)
            parent = self.__test_store.iter_next (parent)


    def run_clicked_cb (self, button):
        """
        Run all selected tests, or all of them if none are selected.
        """

        for name in self.MUTATORS:
            self.__builder.get_object (name).props.sensitive = False

        test_view = self.__builder.get_object ("test_view")
        test_sel = test_view.get_selection ()

        # Figure out what needs to be run.

        parent = self.__test_store.get_iter_first ()
        while parent is not None:
            test_names = []
            child = self.__test_store.iter_children (parent)
            while child is not None:
                name, result = self.__test_store.get (child, self.COL_NAME, self.COL_RESULT)
                if result == "" and (test_sel.iter_is_selected (child) or test_sel.iter_is_selected (parent) or
                                     test_sel.count_selected_rows () == 0):
                    test_names.append (name)
                child = self.__test_store.iter_next (child)
            if len (test_names) > 0:
                name, prefix, user, password = self.__test_store.get (parent,
                        self.COL_NAME, self.COL_PREFIX, self.COL_USER, self.COL_PASSWORD)
                self.__queue_launcher (name, parent, prefix, user, password, test_names)
            parent = self.__test_store.iter_next (parent)

        self.start_next_launcher ()


    def __queue_launcher (self, name, parent, prefix, user, password, test_names):
        """
        Create and queue up a Launcher to be used to run a set of tests
        against a particular configuration.
        """

        panflute_prefix = self.__builder.get_object ("panflute_prefix")
        launcher = self.PLAYERS[name].Launcher (panflute_prefix.get_filename (), prefix, user, password, test_names,
                                                self, parent)
        self.__launchers.append (launcher)


    def process_start (self, parent, test_name):
        """
        Display the fact that a test is starting.
        """

        player_name, player_version = self.__test_store.get (parent, self.COL_NAME, self.COL_VERSION)
        status = self.__builder.get_object ("status")
        status.push (self.__progress_id, "Testing {0} {1}: {2}".format (player_name, player_version, test_name))


    def process_result (self, parent, test_name, result, detail):
        """
        Display a test result.
        """

        status = self.__builder.get_object ("status")
        status.pop (self.__progress_id)

        child = self.__test_store.iter_children (parent)
        while child is not None:
            name = self.__test_store.get_value (child, self.COL_NAME)
            if name == test_name:
                self.__test_store.set (child, self.COL_RESULT, result, self.COL_DETAIL, detail)
                break
            child = self.__test_store.iter_next (child)
        self.__summarize_parent (parent)


    def __summarize_parent (self, parent):
        """
        Rebuild the summary results for a parent node.
        """

        overall = "PASS"

        child = self.__test_store.iter_children (parent)
        while child is not None:
            result = self.__test_store.get_value (child, self.COL_RESULT)
            if result == "FAIL":
                overall = "FAIL"
            elif overall != "FAIL" and result == "":
                overall = ""
            child = self.__test_store.iter_next (child)

        self.__test_store.set (parent, self.COL_RESULT, overall)


    def start_next_launcher (self):
        """
        Start the next launcher in the queue, or un-freeze the GUI if none are
        left.
        """

        if len (self.__launchers) > 0:
            launcher = self.__launchers[0]
            self.__launchers = self.__launchers[1:]
            launcher.start ()
        else:
            for name in self.MUTATORS:
                self.__builder.get_object (name).props.sensitive = True


    def abort_testing (self):
        """
        Give up on testing, on account of a fatal error in the subprocess.
        """

        status = self.__builder.get_object ("status")
        status.pop (self.__progress_id)

        self.__launchers = []
        for name in self.MUTATORS:
            self.__builder.get_object (name).props.sensitive = True

        parent = self.__builder.get_object ("main_window")
        dialog = gtk.MessageDialog (parent = parent,
                                    type = gtk.MESSAGE_ERROR,
                                    buttons = gtk.BUTTONS_CLOSE)
        dialog.set_title ("Subprocess crashed")
        dialog.set_markup ("Subprocess crashed; you will need to clean up manually before resuming testing.")
        dialog.run ()
        dialog.hide ()


    def __selection_changed_cb (self, sel):
        """
        Display the details for the currently selected test tree item.
        """

        model, paths = sel.get_selected_rows ()
        if len (paths) == 1:
            iter = model.get_iter (paths[0])
            if model.iter_has_child (iter):
                self.__edit_iter = iter
                name, version, prefix, user, password = model.get (iter,
                        self.COL_NAME, self.COL_VERSION, self.COL_PREFIX, self.COL_USER, self.COL_PASSWORD)
                self.__show_properties (name, version, prefix, user, password)
            else:
                self.__show_detail (model.get_value (iter, self.COL_DETAIL))
        else:
            self.__show_detail ("")


    def __show_properties (self, name, version, prefix, user, password):
        """
        Show properties for the item.
        """

        notebook = self.__builder.get_object ("notebook")
        player_store = self.__builder.get_object ("player_store")
        player_widget = self.__builder.get_object ("player")
        version_widget = self.__builder.get_object ("version")
        prefix_widget = self.__builder.get_object ("prefix")
        user_widget = self.__builder.get_object ("user")
        password_widget = self.__builder.get_object ("password")

        iter = player_store.get_iter_first ()
        while iter is not None:
            value = player_store.get_value (iter, 0)
            if value == name:
                break
            iter = player_store.iter_next (iter)
        if iter is not None:
            player_widget.set_active_iter (iter)
        else:
            player_widget.set_active (0)

        version_widget.set_text (version)
        prefix_widget.set_filename (prefix)
        user_widget.set_text (user)
        password_widget.set_text (password)
        notebook.set_current_page (1)


    def __show_detail (self, detail):
        """
        Show detail text for the item.
        """

        buffer = self.__builder.get_object ("detail_buffer")
        notebook = self.__builder.get_object ("notebook")

        buffer.set_text (detail)
        notebook.set_current_page (0)


    def begin_test_cb (self, task):
        """
        Called when the test thread begins a test task.
        """

        status = self.__builder.get_object ("status")
        status.push (self.__progress_id, _("Testing {player} {version}: {test}").format (
                player = task.player_name, version = task.player_version, test = task.test_name))


    def finish_test_cb (self, task, result, detail):
        """
        Called when the test thread finishes a test task.
        """

        self.__test_store.set (task.iter, self.COL_RESULT, result, self.COL_DETAIL, detail)

        status = self.__builder.get_object ("status")
        status.pop (self.__progress_id)


    def finish_all_tests_cb (self):
        """
        Called when the test thread finishes all test tasks.
        """

        self.__summarize ()
        for name in self.MUTATORS:
            self.__builder.get_object (name).props.sensitive = True


    def main_window_delete_event_cb (self, tester, event):
        """
        Close the program when the window closes.
        """

        self.__save ()
        gtk.main_quit ()


    def player_changed_cb (self, combo):
        """
        Update the selected test set with a different player.
        """

        iter = combo.get_active_iter ()
        model = combo.get_model ()
        value = model.get_value (iter, 0)

        self.__test_store.set (self.__edit_iter, self.COL_NAME, value)


    def version_changed_cb (self, entry):
        """
        Update the selected test set with a different version.
        """

        self.__test_store.set (self.__edit_iter, self.COL_VERSION, entry.get_text ())


    def prefix_file_set_cb (self, chooser):
        """
        Update the selected test set with a different installation prefix.
        """

        self.__test_store.set (self.__edit_iter, self.COL_PREFIX, chooser.get_filename ())


    def user_changed_cb (self, entry):
        """
        Update the selected test set with a different user.
        """

        self.__test_store.set (self.__edit_iter, self.COL_USER, entry.get_text ())


    def password_changed_cb (self, entry):
        """
        Update the selected test set with a different password.
        """

        self.__test_store.set (self.__edit_iter, self.COL_PASSWORD, entry.get_text ())


    def remove_clicked_cb (self, button):
        """
        Remove the selected players from the test tree.
        """

        test_view = self.__builder.get_object ("test_view")
        test_sel = test_view.get_selection ()

        model, paths = test_sel.get_selected_rows ()
        rows = []
        for path in paths:
            iter = model.get_iter (path)
            if not model.iter_has_child (iter):
                # Delete player configurations, not test lines
                parent = model.iter_parent (iter)
                path = model.get_path (parent)
            row = gtk.TreeRowReference (model, path)
            rows.append (row)

        for row in rows:
            if row.valid ():
                path = row.get_path ()
                iter = model.get_iter (path)
                model.remove (iter)


    def add_clicked_cb (self, button):
        """
        Add a new, blank player entry to the test tree.
        """

        players = self.PLAYERS.keys ()
        players.sort ()

        config = SavedConfig (players[0], "", "", "", "", "")
        iter = self.__add_player (config)
        view = self.__builder.get_object ("test_view")
        sel = view.get_selection ()
        sel.unselect_all ()
        sel.select_iter (iter)


    def __load (self):
        """
        Load the previously saved test configuration.
        """

        panflute_prefix = self.__builder.get_object ("panflute_prefix")

        try:
            with file (self.SAVE_FILE, "rb") as save_file:
                format_version = cPickle.load (save_file)
                panflute_prefix_path = cPickle.load (save_file)
                if panflute_prefix_path is not None:
                    panflute_prefix.set_filename (panflute_prefix_path)
                configs = cPickle.load (save_file)
            self.__test_store.clear ()
            for config in configs:
                self.__add_player (config)
            self.__summarize ()
        except IOError:
            # File did not exist, so start with nothing
            pass


    def __save (self):
        """
        Save the current test configuration.
        """

        panflute_prefix = self.__builder.get_object ("panflute_prefix")

        configs = []
        iter = self.__test_store.get_iter_first ()
        while iter is not None:
            name, version, prefix, comment, user, password = self.__test_store.get (iter,
                    self.COL_NAME, self.COL_VERSION, self.COL_PREFIX, self.COL_COMMENT, self.COL_USER, self.COL_PASSWORD)
            config = SavedConfig (name, version, prefix, comment, user, password)
            child = self.__test_store.iter_children (iter)
            while child is not None:
                name, result, detail, comment = self.__test_store.get (child,
                        self.COL_NAME, self.COL_RESULT, self.COL_DETAIL, self.COL_COMMENT)
                res = SavedResult (name, result, detail, comment)
                config.add_result (res)
                child = self.__test_store.iter_next (child)
            configs.append (config)
            iter = self.__test_store.iter_next (iter)

        try:
            os.makedirs (self.SAVE_DIR, 0700)
        except OSError:
            # Directory already existing is not a failure
            pass

        with file (self.SAVE_FILE, "wb") as save_file:
            cPickle.dump (0, save_file, 2)
            cPickle.dump (panflute_prefix.get_filename (), save_file, 2)
            cPickle.dump (configs, save_file, 2)


    def __summarize (self):
        """
        Aggregate the results of tests for each player configuration.
        """

        player = self.__test_store.get_iter_first ()
        while player is not None:
            untested = False
            failed = False

            test = self.__test_store.iter_children (player)
            while test is not None:
                result = self.__test_store.get_value (test, self.COL_RESULT)
                if result == "":
                    untested = True
                elif result == _("FAIL"):
                    failed = True
                test = self.__test_store.iter_next (test)
            
            if failed:
                summary = _("FAIL")
            elif untested:
                summary = ""
            else:
                summary = _("PASS")
            self.__test_store.set (player, self.COL_RESULT, summary)

            player = self.__test_store.iter_next (player)


    def __sort_name_version_cb (self, model, iter1, iter2):
        """
        Compare two rows by name and version number.
        """

        name1, version1 = model.get (iter1, self.COL_NAME, self.COL_VERSION)
        name2, version2 = model.get (iter2, self.COL_NAME, self.COL_VERSION)

        if name1 != name2:
            return cmp (name1, name2)

        if version1 is not None:
            pieces1 = version1.split (".")
        else:
            pieces1 = [0]

        if version2 is not None:
            pieces2 = version2.split (".")
        else:
            pieces2 = [0]

        for (piece1, piece2) in zip (pieces1, pieces2):
            if piece1 != piece2:
                try:
                    num1 = int (piece1)
                    num2 = int (piece2)
                    return cmp (num1, num2)
                except ValueError:
                    # numeric conversion failed; fall back to string
                    return cmp (piece1, piece2)
        return cmp (len (pieces1), len (pieces2))


    def comment_renderer_edited_cb (self, renderer, path, new_text):
        """
        Set the comment on something in the test tree.
        """

        iter = self.__test_store.get_iter (path)
        self.__test_store.set (iter, self.COL_COMMENT, new_text)


class SavedConfig (object):
    """
    Struct for holding the persistent information about a test configuration.
    """

    def __init__ (self, name, version, prefix, comment, user, password):
        self.name = name
        self.version = version
        self.prefix = prefix
        self.comment = comment
        self.user = user
        self.password = password
        self.results = {}


    def add_result (self, result):
        self.results[result.name] = result


class SavedResult (object):
    """
    Struct for holding the persistent information about an individual test.
    """

    def __init__ (self, name, result, detail, comment):
        self.name = name
        self.result = result
        self.detail = detail
        self.comment = comment


def create_tester ():
    """
    Create a Tester and return its main window.
    """

    builder = gtk.Builder ()
    builder.add_from_file (os.path.join (panflute.defs.PKG_DATA_DIR, "tester.ui"))

    tester = Tester (builder)
    return builder.get_object ("main_window")


try:
    import panflute.tests.moc as moc
    Tester.PLAYERS["MOC"] = moc
except Exception, e:
    print ("Failed to load MOC test module: {0}".format (e), file = sys.stderr)

try:
    import panflute.tests.mpd as mpd
    Tester.PLAYERS["MPD"] = mpd
except Exception, e:
    print ("Failed to load MPD test module: {0}".format (e), file = sys.stderr)

try:
    import panflute.tests.xmms as xmms
    Tester.PLAYERS["XMMS"] = xmms
except Exception, e:
    print ("Failed to load XMMS test module: {0}".format (e), file = sys.stderr)

try:
    import panflute.tests.xmms2 as xmms2
    Tester.PLAYERS["XMMS2"] = xmms2
except Exception, e:
    print ("Failed to load XMMS2 test module: {0}".format (e), file = sys.stderr)
