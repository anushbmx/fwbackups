#! /usr/bin/python
# -*- coding: utf-8 -*-
#  Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010 Stewart Adam
#  Parts Copyright (C) Thomas Leonard (from ROX-lib2)
#  This file is part of fwbackups.

#  fwbackups is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.

#  fwbackups is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU General Public License
#  along with fwbackups; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""
Puts it all together.
"""
import os
import re
import sys
import time
import types

from fwbackups.const import *
from fwbackups.i18n import _, encode

if sys.platform.startswith('win'):
  os.environ["PATH"] += ";%s" % os.path.join(INSTALL_DIR, "gtkfiles", "bin")
  os.environ["PATH"] += ";%s" % os.path.join(INSTALL_DIR, "gtkfiles", "addon")
  sys.path.insert(0, os.path.join(INSTALL_DIR, "pythonmodules"))
  sys.path.insert(1, os.path.join(INSTALL_DIR, "pythonmodules", "gtk-2.0"))

try:
  import gtk
  import gobject
except:
  print _("An error occurred while importing gtk/gobject.")
  print _("Please make sure you have a valid GTK+ Runtime Environment.")
  sys.exit(1)

#--
import fwbackups
from fwbackups import interface
from fwbackups import widgets

def reportBug(etype=None, evalue=None, tb=None):
  """Report a bug dialog"""
  import traceback
  c = interface.Controller(os.path.join(INSTALL_DIR, 'BugReport.glade'), 'bugreport')
  if not etype and not evalue and not tb:
    (etype, evalue, tb) = sys.exc_info()
  tracebackText = ''.join(traceback.format_exception(etype, evalue, tb))
  reportWindow = widgets.bugReport(c.ui.bugreport, c.ui.bugreportTextview, None, tracebackText)
  response = reportWindow.runAndDestroy()
  if response == gtk.RESPONSE_OK:
    filename = widgets.saveFilename(c.ui.bugreport)
    if not filename:
      sys.exit(1)
    if fwbackups.CheckPerms(filename):
      import datetime
      fh = open(filename, 'w')
      fh.write(_('fwbackups bug report written saved at %s') % datetime.datetime.today().strftime('%I:%M %p on %Y-%m-%d\n'))
      fh.write(tracebackText)
      fh.close()
      sys.exit(1)
    else:
      print _('Could not write bug report due to insufficient permissions.')
      sys.exit(1)
  elif response == gtk.RESPONSE_CLOSE:
    sys.exit(1)
  print '%s: %s' % (etype, evalue)

sys.excepthook = reportBug
# This causes hangs on exit in OS X
#gobject.threads_init()
try:
  import Crypto
except:
  raise fwbackups.fwbackupsError(_('Please install pycrypto (python-crypto)'))
try:
  import paramiko
except:
  raise fwbackups.fwbackupsError(_('Please install paramiko (python-paramiko)'))

from fwbackups import fwlogger
from fwbackups import config
from fwbackups import cron
from fwbackups import shutil_modded
from fwbackups.operations import *

def busyCursor(mainwin,insensitive=False):
  """Set busy cursor in mainwin and make it insensitive if selected"""
  mainwin.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
  if insensitive:
    mainwin.set_sensitive(False)
  doGtkEvents()

def normalCursor(mainwin):
  """Set Normal cursor in mainwin and make it sensitive"""
  mainwin.window.set_cursor(None)
  mainwin.set_sensitive(True)
  doGtkEvents()

def doGtkEvents():
  """Process gtk events"""
  while gtk.events_pending():
    gtk.main_iteration()
  time.sleep(0.01)

def getSelectedItems(widget):
  """Get selected items from icon/tree view"""
  try:
    model = widget.get_model()
    selected = widget.get_selected_items()
    return selected
  except:
    return False

def set_text_markup(widget, text):
  """Sets text of a gtk.Label and sets use_markup=True"""
  widget.set_text(text)
  widget.set_use_markup(True)

class fwbackupsApp(interface.Controller):
  """The class which contains the interface callbacks"""
  def __init__(self, verbose=0, minimized=False):
    """Initialize a new instance."""
    interface.Controller.__init__(self, os.path.join(INSTALL_DIR, 'fwbackups.glade'), 'main')
    self.verbose = verbose
    self.runSetup(minimized=minimized)

  def _setDefaults(self):
    """Setup default values"""
    if USER != 'root':
      self.ui.backupset4DiskInfoToFileCheck.set_active(False)
      self.ui.backupset4DiskInfoToFileCheck.set_sensitive(False)
      self.ui.main3DiskInfoToFileCheck.set_active(False)
      self.ui.main3DiskInfoToFileCheck.set_sensitive(False)
      self.ui.backupset5NiceScale.get_adjustment().set_all(0, 0, 19, 1, 5, 0)
      self.ui.main3NiceScale.get_adjustment().set_all(0, 0, 19, 1, 5, 0)
    if MSWINDOWS:
      self.ui.preferencesWindowsFrame.set_sensitive(True)
      self.ui.backupset5NiceScale.set_value(0.0)
      self.ui.backupset5NiceScale.set_sensitive(False)
      self.ui.main3NiceScale.set_value(0.0)
      self.ui.main3NiceScale.set_sensitive(False)

      self.ui.backupset5ExcludesTextview.get_buffer().set_text('')
      self.ui.backupset5ExcludesTextview.set_sensitive(False)
      self.ui.main3ExcludesTextview.get_buffer().set_text('')
      self.ui.main3ExcludesTextview.set_sensitive(False)

      self.ui.backupset4PkgListsToFileCheck.set_active(False)
      self.ui.backupset4PkgListsToFileCheck.set_sensitive(False)
      self.ui.main3PkgListsToFileCheck.set_active(False)
      self.ui.main3PkgListsToFileCheck.set_sensitive(False)

      self.ui.backupset4DiskInfoToFileCheck.set_active(False)
      self.ui.backupset4DiskInfoToFileCheck.set_sensitive(False)
      self.ui.main3DiskInfoToFileCheck.set_active(False)
      self.ui.main3DiskInfoToFileCheck.set_sensitive(False)

      self.ui.backupset4BackupHiddenCheck.set_active(True)
      self.ui.backupset4BackupHiddenCheck.set_sensitive(False)
      self.ui.main3BackupHiddenCheck.set_active(True)
      self.ui.main3BackupHiddenCheck.set_sensitive(False)

      self.ui.backupset4IncrementalCheck.set_sensitive(False)

      self.ui.backupset4FollowLinksCheck.set_active(True)
      self.ui.backupset4FollowLinksCheck.set_sensitive(False)
      self.ui.main3FollowLinksCheck.set_active(True)
      self.ui.main3FollowLinksCheck.set_sensitive(False)

      self.ui.backupset4SparseCheck.set_active(False)
      self.ui.backupset4SparseCheck.set_sensitive(False)
      self.ui.main3SparseCheck.set_active(False)
      self.ui.main3SparseCheck.set_sensitive(False)

    # Default to page 0..
    self.ui.mainControlNotebook.set_current_page(0)
    self.ui.backupsetControlNotebook.set_current_page(0)
    self.ui.main3ControlNotebook.set_current_page(0)
    self.ui.restoreControlNotebook.set_current_page(0)
    self.ui.main3DestinationTypeNotebook.set_current_page(0)
    self.ui.restore1SourceTypeNotebook.set_current_page(0)
    # Don't show tabs...
    self.ui.mainControlNotebook.set_show_tabs(False)
    self.ui.mainControlNotebook.set_show_tabs(False)
    self.ui.main3ControlNotebook.set_show_tabs(False)
    self.ui.restoreControlNotebook.set_show_tabs(False)
    self.ui.backupset2DestinationTypeNotebook.set_show_tabs(False)
    self.ui.main3DestinationTypeNotebook.set_show_tabs(False)
    self.ui.restore1SourceTypeNotebook.set_show_tabs(False)
    # Default fields...
    self.ui.backupset4IncrementalCheck.set_active(False)
    self.ui.restore1SourceTypeCombobox.set_active(0)
    self.ui.backupset2DestinationTypeCombobox.set_active(0)
    self.ui.backupset2HidePasswordCheck.set_active(True)
    self.ui.main3HidePasswordCheck.set_active(True)
    self.ui.WelcomeLabel.set_text(_('Welcome, %s!'  % USER))
    # done in main3Refresh() #self.ui.main3DestinationTypeCombobox.set_active(0)
    # Default Labels...
    set_text_markup(self.ui.aboutVersionLabel, '<span size="xx-large" weight="bold">fwbackups %s</span>' % fwbackups.__version__)
    self.setStatus(_('Idle'))
    self.main2IconviewSetup()
    self.main3TabSetup()
    self.restoreSetup()
    # Default progressbars...
    self.main2BackupProgress.progressbar.set_text(_('Click \'Backup Set Now\' to begin'))
    self.main3BackupProgress.progressbar.set_text(_('Click \'Start Backup\' to begin'))
    self.ui.restore2RestorationProgress.set_text(_('Click \'Start Restore\' to begin'))
    # refresh main3
    self.main3Refresh()

  def setStatus(self, status):
    """Set all status labels and tray icon"""
    set_text_markup(self.ui.main2StatusLabel, status)
    set_text_markup(self.ui.main3StatusLabel, status)
    set_text_markup(self.ui.restore2StatusLabel, status)
    textOnly = self.ui.main2StatusLabel.get_text()
    if hasattr(self, 'trayicon'):
      self.trayicon.set_tooltip('fwbackups - %s' % textOnly)

  def updateSplash(self, fraction, text):
    """Update the splash screen"""
    self.ui.splashProgress.set_fraction(float(fraction))
    percent = int(fraction * 100.0)
    #self.ui.splashProgress.set_text('%s%% complete: %s' % (percent, text))
    set_text_markup(self.ui.label444, _('<span size="small">%s%% complete: %s</span>' % (percent, text)))
    while gtk.events_pending():
      gtk.main_iteration()
    time.sleep(0.1)

  def runSetup(self, widget=None, event=None, minimized=False):
    """Runs when splash is shown"""
    # let's pretend we're doing something so we can't quit as we start
    self.operationInProgress = True
    # transient windows
    self.ui.about.set_transient_for(self.ui.main)
    self.ui.preferences.set_transient_for(self.ui.main)
    self.ui.backupset.set_transient_for(self.ui.main)
    self.ui.restore.set_transient_for(self.ui.main)
    if MSWINDOWS:
      appIcon = os.path.join(INSTALL_DIR, 'fwbackups.ico')
    else:
      appIcon = os.path.join(INSTALL_DIR, 'fwbackups.png')
    if os.path.exists(appIcon):
      self.ui.splashIconImage.set_from_file(appIcon)
      self.ui.aboutProgramImage.set_from_file(appIcon)
    self.updateSplash(0.0, _('Checking permissions'))
    self.ui.splash.show()
    doGtkEvents()
    # Step 1: Setup the configuration directory
    try:
      config._setupConf()
    except config.ConfigError, error:
      self.displayInfo(self.ui.splash,
                       _("Could not setup the fwbackups configuration folder"),
                       _("The following error occured: %s" % error))
      sys.exit(1)
    # Step 2: Setup the logger
    self.updateSplash(0.2, _('Setting up the logger and user preferences'))
    try:
      prefs = config.PrefsConf(create=True)
    except config.ValidationError, error:
      print _("Validation error: %s") % error
      response = self.displayConfirm(self.ui.splash, _("Preferences could not be read"), _("The preferences file may be corrupted and could not be read by fwbackups. Would you like to initialize a new one from the default values? If not, fwbackups will exit."))
      if response == gtk.RESPONSE_YES:
        # check if file already exists
        prefsBack = '%s.bak' % PREFSLOC
        if os.path.isfile(prefsBack):
          os.remove(prefsBack)
        # save a backup copy
        os.rename(PREFSLOC, prefsBack)
        # initialize a fresh config
        prefs = config.PrefsConf(create=True)
      else:
        sys.exit(0)
    try:
      self.logger = fwlogger.getLogger()
      # default to info log level
      level = fwlogger.L_INFO
      if self.verbose >= 1:
        # one -v used: print to console
        self.logger.setPrintToo(True)
      if self.verbose >= 2 or int(prefs.get('Preferences', 'AlwaysShowDebug')) == 1:
        # two -v used: use debug log level instead
        level = fwlogger.L_DEBUG
      self.logger.setLevel(level)
      self.logger.connect(self.updateLogViewer)
      # Log size...
      self.updateSplash(0.4, _('Populating the log viewer'))
      self._checkLogSize()
      self.logconsole = widgets.TextViewConsole(self.ui.LogViewerTextview)
    except Exception, error:
      self.displayInfo(self.ui.splash,
                       _("Could not setup the logger"),
                       _("The following error occured: %s" % error))
      sys.exit(1)
    # Step 3: See what's available and what's not
    self.action = None
    try:
      import pynotify
      pynotify.init('fwbackups')
      self.NOTIFY_AVAIL = True
    except ImportError:
      self.NOTIFY_AVAIL = False
      self.logger.logmsg('DEBUG', _('pynotify was not found. Notifcations will not be displayed unless notify-python/pynotify is installed.'))
    # render icons: about dialog
    if MSWINDOWS:
      appIcon = os.path.join(INSTALL_DIR, 'fwbackups.ico')
    else:
      appIcon = os.path.join(INSTALL_DIR, 'fwbackups.png')
    if os.path.exists(appIcon):
      gtk.window_set_default_icon_from_file(appIcon)
    self.updateSplash(0.6, 'Loading widgets')
    self.statusbar = widgets.StatusBar(self.ui.statusbar1)
    self.ExportView1 = widgets.ExportView(self.ui.ExportTreeview, self.statusbar, self.ui)
    # Tray icon - check for PyGTK 2.10+
    if not hasattr(gtk, 'StatusIcon'):
      prefs.set('Preferences', 'ShowTrayIcon', 0)
      prefs.set('Preferences', 'MinimizeTrayClose', 0)
      prefs.set('Preferences', 'StartMinimized', 0)
      self.ui.preferencesShowTrayIconCheck.set_active(False)
      self.ui.preferencesShowTrayIconCheck.set_sensitive(False)
      self.ui.preferencesMinimizeTrayCloseCheck.set_active(False)
      self.ui.preferencesMinimizeTrayCloseCheck.set_sensitive(False)
      self.ui.preferencesStartMinimizedCheck.set_active(False)
      self.ui.preferencesStartMinimizedCheck.set_sensitive(False)
    else:
      # PyGTK 2.10+ installed, gtk.StatusIcon exists
      if prefs.getboolean('Preferences', 'ShowTrayIcon') or minimized:
        self._setupTrayIcon()
        self.trayicon.set_visible(True)
    self._setDefaults()
    self.updateSplash(0.8, _('Cleaning after previous versions'))
    # Clean up, clean up, everybody do your share...
    if os.path.exists('/etc/crontab') and fwbackups.CheckPermsRead('/etc/crontab'):
      fh = open('/etc/crontab', 'r')
      crontab = fh.read()
      if re.search('.*fwbackups.*', crontab):
        if int(prefs.get('Preferences', 'DontShowMe_OldVerWarn')) == 0:
          dontShowMe = self.displayInfo(self.ui.main, _("Previous installation of fwbackups 1.42.x or older detected"), _("Because of certain major changes in fwbackups, your configuration must be imported manually. To do this, run fwbackups as the root user and select <i>File > Import</i> from the menu to import your old configuration.\nIf this action is not completed, the backups from version 1.42.x <b>will not run automatically</b>.\n<i>Tip: The 1.42.x configuration was stored in /etc/fwbackups</i>."), dontShowMe=True)
          if dontShowMe:
            prefs.set('Preferences', 'DontShowMe_OldVerWarn', 1)
      if UID == 0:
        try:
          shutil_modded.copy('/etc/crontab', '/etc/crontab.fwbk')
        except Exception, error:
          self.displayInfo(self.ui.main, _("A backup of /etc/crontab could not be created"), _("You may wish to edit /etc/crontab manually and remove any fwbackups-related lines."))
          self.logger.logmsg('ERROR', _("Could not create a backup of /etc/crontab; refusing to clean up."))
        try:
          if re.search('.*fwbackups.*', crontab):
            self.logger.logmsg('INFO', _('Cleaning up /etc/crontab from previous installation of fwbackups'))
            p = re.compile('.*fwbackups.*')
            newcrontab = p.sub('', crontab)
            fh.close()
            fh = open('/etc/crontab', 'w')
            fh.write(newcrontab)
        except Exception, error:
          shutil.copy("/etc/crontab.fwbk", "/etc/crontab")
          os.remove("/etc/crontab.fwbk")
          message = _("fwbackups was unable to clean up the system crontab: %s. You may wish to edit /etc/crontab manually and remove any fwbackups-related lines.") % error
          self.displayInfo(self.ui.main, _("Cleanup of the system crontab failed"), message)
          self.logger.logmsg('ERROR', message)
    self.updateSplash(1, _('Ready!'))
    time.sleep(0.5)
    # Welcome...
    self.operationInProgress = False
    self.logger.logmsg('INFO', _('fwbackups administrator started'))
    if DARWIN:
      import igemacintegration
      # Use OS X native menubar
      igemacintegration.ige_mac_menu_set_menu_bar(self.ui.menubar1)
      self.ui.menubar1.hide()
      # Connect the key handler
      igemacintegration.ige_mac_menu_connect_window_key_handler(self.ui.main)
      # Move the Quit menu button
      igemacintegration.ige_mac_menu_set_quit_menu_item(self.ui.quit1)
      self.ui.quit1.hide()
      # Same for About
      group = igemacintegration.ige_mac_menu_add_app_menu_group()
      igemacintegration.ige_mac_menu_add_app_menu_item(group, self.ui.about1, None)
      # and preferences too
      group = igemacintegration.ige_mac_menu_add_app_menu_group()
      igemacintegration.ige_mac_menu_add_app_menu_item(group, self.ui.preferences1, None)
      self.ui.preferences1.hide()
      self.ui.separator1.hide()
      # Use OS X dock
      dock = igemacintegration.MacDock()
      dock.connect('quit-activate', self.main_close)
      appIcon = os.path.join(INSTALL_DIR, 'fwbackups.png')
      if os.path.exists(appIcon):
        pix = gtk.gdk.pixbuf_new_from_file(appIcon)
        dock.set_icon_from_pixbuf(pix)
    # only if both are true, ie both say open normally
    if not prefs.getboolean('Preferences', 'StartMinimized') and not minimized:
      self.ui.main.show()
    self.ui.splash.hide()

  def _checkLogSize(self):
    """Check the log size, clear if needed"""
    statsize = int(os.stat(LOGLOC)[6])
    if statsize >= 1048577:
      #1048576B is 1MB.
      size = '%s KB' % (statsize / 1024)
      response = self.displayConfirm(self.ui.splash, _("Would you like to clean up the log file?"), _("The log file is becoming large (%s). Would you like to clear it? This will permanently remove all entries from the log.") % size)
      if response == gtk.RESPONSE_YES:
        logfh = open(LOGLOC, 'w')
        logfh.write('')
        logfh.close()

  def _setupTrayIcon(self):
    """Sets up the tray icon"""
    prefs = config.PrefsConf()
    if MSWINDOWS:
      appIcon = os.path.join(INSTALL_DIR, 'fwbackups.ico')
    else:
      appIcon = os.path.join(INSTALL_DIR, 'fwbackups.png')
    if os.path.exists(appIcon):
      pix = gtk.gdk.pixbuf_new_from_file(appIcon)
      self.trayicon = gtk.status_icon_new_from_pixbuf(pix)
    else:
      self.trayicon = gtk.status_icon_new_from_stock(gtk.STOCK_COPY)
    self.trayicon.connect("popup_menu", self._Popup)
    self.trayicon.connect("activate", self._clicked)
    # now set the status of the checkmarks...
    self.ui.display_notifications1.set_active(prefs.getboolean('Preferences', 'ShowNotifications'))
    self.ui.minimize_to_tray_on_close1.set_active(prefs.getboolean('Preferences', 'MinimizeTrayClose'))

  def _clicked(self, status):
    """Handles when gtk.StatusIcon `status' is clicked."""
    # use me for other actions on click
    if self.ui.main.get_property('visible'):
      self.ui.main.hide()
      self.ui.show_administrator1.set_active(False)
    else:
      self.ui.main.show()
      self.ui.show_administrator1.set_active(True)
    #self.ui.TrayMenu1.show()

  def _Popup(self, status, button, time):
    """Popup the menu at the right position"""
    #--
    def menu_pos(menu):
      width, height, orientation = gtk.status_icon_position_menu(menu, self.trayicon)
      return width, height, orientation
    #--
    if MSWINDOWS or DARWIN:
      self.ui.TrayMenu1.popup(None, None, None, button, time)
    else:
      self.ui.TrayMenu1.popup(None, None, menu_pos, button, time)
    self.ui.TrayMenu1.show()

  def displayInfo(self, parent, primaryText, secondaryText, dontShowMe=False):
    """Wrapper for displaying the confirm dialog"""
    if dontShowMe:
      dontShowMe = self.ui.infoDiaDontShowMeCheck
    dialog = widgets.InfoDia(self.ui.info_dia, parent, self.ui.infoDiaLabel, primaryText, secondaryText, dontShowMe)
    dialog.run()
    if dontShowMe:
      showMe = dontShowMe.get_active()
      dialog.destroy()
      return showMe
    else:
      dialog.destroy()
      return


  def displayError(self, parent, primaryText, secondaryText):
    """Wrapper for displaying the confirm dialog"""
    dialog = widgets.ErrorDia(self.ui.error_dia, parent, self.ui.errorDiaLabel, primaryText, secondaryText)
    dialog.run()
    dialog.destroy()

  def displayWarning(self, parent, primaryText, secondaryText, dontShowMe=False):
    """Wrapper for displaying the confirm dialog"""
    if dontShowMe:
      dontShowMe = self.ui.warningDiaDontShowMeCheck
    dialog = widgets.WarningDia(self.ui.warning_dia, parent, self.ui.warningDiaLabel, primaryText, secondaryText, dontShowMe)
    dialog.run()
    if dontShowMe:
      showMe = dontShowMe.get_active()
      dialog.destroy()
      return showMe
    else:
      dialog.destroy()
      return

  def displayConfirm(self, parent, primaryText, secondaryText, dontShowMe=False):
    """Wrapper for displaying the confirm dialog"""
    if dontShowMe:
      dontShowMe = self.ui.confirmDiaDontShowMeCheck
    dialog = widgets.ConfirmDia(self.ui.confirm_dia, parent, self.ui.confirmDiaLabel, primaryText, secondaryText, dontShowMe)
    response = dialog.run()
    if dontShowMe:
      showMe = dontShowMe.get_active()
      dialog.destroy()
      return response, showMe
    else:
      dialog.destroy()
      return response

  ###
  ### TRAY ICON ###
  ###

  def on_show_administrator1_activate(self, widget, event=None):
    """Hide/show the main window"""
    if self.ui.show_administrator1.get_active():
      self.ui.main.show()
    else:
      self.ui.main.hide()

  def on_minimize_to_tray_on_close1_activate(self, widget, event=None):
    """Minimize to tray on close?"""
    self.ui.preferencesMinimizeTrayCloseCheck.set_active(self.ui.minimize_to_tray_on_close1.get_active())

  def on_display_notifications1_activate(self, widget, event=None):
    """Set display notifications from tray icon"""
    self.ui.preferencesShowNotificationsCheck.set_active(self.ui.display_notifications1.get_active())

  def on_preferences2_activate(self, widget, event=None):
    """Hides the tray icon until it displays a notification again"""
    self.on_preferences1_activate(None)

  def on_quit2_activate(self, widget):
    """Quit"""
    return self.main_close(widget)

  ###
  ### WRAPPERS ###
  ###

  def trayNotify(self, summary, body, timeout=-1):
    """Display a notification attached to the tray icon if applicable"""
    # see /usr/share/doc/python-notify/examples for API
    #n.set_urgency(pynotify.URGENCY_NORMAL)
    #n.set_timeout(pynotify.EXPIRES_NEVER)
    #n.add_action("clicked","Button text", callback_function, None)
    #def callback_function(notification=None, action=None, data=None):
    #  pass
    # -1 == pynotify.EXPIRES_DEFAULT
    # 0 == pynotify.EXPIRES_NEVER
    if not self.NOTIFY_AVAIL:
      return
    try:
      import pynotify
      notify = pynotify.Notification(summary, body)
      # icon
      pix = self.ui.main.render_icon(gtk.STOCK_COPY, gtk.ICON_SIZE_DIALOG)
      notify.set_icon_from_pixbuf(pix)
      # location
      if hasattr(self, 'trayicon'):
        tray = self.trayicon
        if tray.get_visible():
          notify.set_property('status-icon', tray)
      # timeout?
      if timeout != 0:
        notify.set_timeout(int(timeout) * 1000)

      # finally, show it
      notify.show()
    except Exception, error:
      self.logger.logmsg('DEBUG', _('Could not create notification: %s' % error))

  def _toggleLocked(self, bool, keepSensitive=[]):
    """Toggle locking in the UI"""
    for widget in   [self.ui.BackupSetsRadioTool, self.ui.backup_sets1,
                     self.ui.OneTimeRadioTool, self.ui.one_time_backup1,
                     self.ui.RestoreToolButton, self.ui.restore1,
                     self.ui.backupset, self.ui.restore,
                     self.ui.main2VButtonBox, self.ui.main3VButtonBox,
                     self.ui.main2Iconview,
                     self.ui.new_set1,
                     self.ui.import_sets1,
                     self.ui.export_sets1]:
      widget.set_sensitive(not bool)
    for widget in keepSensitive:
      widget.set_sensitive(True)
    for widget in [self.ui.edit_set1,
                   self.ui.duplicate_set1,
                   self.ui.remove_set1]:
      widget.set_sensitive(False)

  def help(self):
    """Open the online user manual"""
    import webbrowser
    webbrowser.open_new('http://downloads.diffingo.com/fwbackups/docs/%s-html' % fwbackups.__version__)

  def hide(self, widget, event=None):
    """Wrapper for closing a window non-destructively"""
    widget.hide()
    return True # don't kill the window after we call hide()

  def regenerateCrontab(self):
    """Regenerates the crontab"""
    self.logger.logmsg('DEBUG', _('Regenerating crontab'))
    self.statusbar.newmessage(_('Please wait... Regenerating crontab'), 10)
    doGtkEvents()
    # Purge existing fwbackups entries from the crontab
    originalCronLines = cron.read()
    fwbackupCronLines = cron.clean_fwbackups_entries()
    # Generate the new fwbackups entries
    files = os.listdir(SETLOC)
    files.sort()
    for file in files:
      if file.endswith('.conf') and file != 'temporary_config.conf':
        from ConfigParser import NoOptionError
        try:
          setConf = config.BackupSetConf(os.path.join(SETLOC, file))
        except (config.ConfigError, NoOptionError):
          self.displayError(self.ui.main, _("Could not parse the configuration for set '%s'") % os.path.splitext(file)[0],
            _("The set configuration file '%s' failed to validate, so it may not be properly scheduled. Other sets are unaffected by this error." % file))
          continue
        setName = setConf.getSetName()
        entry = setConf.getCronLineText()
        try:
          crontabLine = cron.crontabLine(*entry)
          if not crontabLine.is_parsable():
            raise cron.CronError(_("Internal error: generated entry for set '%s' was not parsable. Please submit a bug report.") % setName)
          fwbackupCronLines.append(crontabLine)
        except Exception, error:
          self.displayError(self.ui.main, _("Could not schedule automated backups for set '%s'") % setName,
            _("fwbackups could not regenerate a crontab entry because an error occured:\n") + \
            _("%(a)s\n\nThe crontab entry associated with the error was:\n%(b)s") % {'a': error, 'b': entry})
          continue
        # After all is done, log an message
        self.logger.logmsg('DEBUG', _("Saving set `%s' to the crontab") % setName)
    try:
      # Write the new crontab
      cron.write(fwbackupCronLines)
    except cron.ValidationError:
      raise
    except Exception, error:
      self.logger.logmsg('WARNING', _("Unable to write new crontab: %s" % str(error)))
      self.displayError(self.ui.main, _("Unable to save backup schedule to crontab"), _("There was an error saving the new backup schedule. A backup will be restored, however this may cause a discrepancy between the set settings and the actual backup schedule.\n\nIf you see this message, please report a bug against fwbackups."))
      # Restore backup
      try:
        cron.write(originalCronLines)
        self.logger.logmsg('INFO', _("A backup of the crontab was restored; the backup schedule may be different than the settings in the GUI."))
      except:
        self.logger.logmsg('WARNING', _("A backup of the crontab could not be restored"))
      

  def main_close_traywrapper(self, widget, event=None):
    """Quit, but check if we should minimize first."""
    prefs = config.PrefsConf()
    if prefs.getboolean('Preferences', 'MinimizeTrayClose'):
      self.ui.main.hide()
      return True
    else:
      return self.main_close()

  def main_close(self, widget=None, event=None):
    """Wrapper for quitting"""
    if self.operationInProgress:
      response = self.displayConfirm(self.ui.main,
                                     _("fwbackups is working"),
                                     _("An operation is currently in progress. Would you like to cancel it and quit anyways?"))
      if response == gtk.RESPONSE_YES:
        self.statusbar.newmessage(_('Please wait... Canceling operations'), 10)
        try:
          self.backupHandle.cancelOperation()
        except:
          try:
            self.restoreHandle.cancelOperation()
          except:
            pass
      else:
        return True
    # This will attempt to kill any dead Paramiko threads
    import threading
    if len(threading.enumerate()) > 1:
      self.logger.logmsg('INFO', _('fwbackups detected more than one alive threads!'))
    for thread in threading.enumerate()[1:]:
      if type(thread) == paramiko.Transport:
        # Thread is a Paramiko transport -- close it down.
        thread.close()
        self.logger.logmsg('INFO', _('Closed dead Paramiko thread: %s') % str(thread))
      else:
        # FIXME: Figure out how to kill other thread types. For now, just log.
        self.logger.logmsg('CRITICAL', _('Could not close thread %s!') % str(thread))
        self.logger.logmsg('CRITICAL', _('Please submit a bug report and include this message.'))
    # Bugfix for GTK+ on Win32: A ghost tray icon remains after app exits
    # Workaround: Hide the tray icon before quitting the GTK mainloop
    if hasattr(self, 'trayicon'):
      self.trayicon.set_visible(False)
    # Save set configurations schedule
    try:
      self.regenerateCrontab()
    except cron.ValidationError:
      self.displayError(self.ui.backupset, _("Could not save backup schedule"), _("fwbackups was unable to save the backup scheduling information to the crontab. If you are using manual times entry in one of your sets, please verify that all five fields are using the correct syntax."))
    # Shutdown logging & quit the GTK mainloop
    self.logger.logmsg('INFO', _('fwbackups administrator closed'))
    fwlogger.shutdown()
    try:
      gtk.main_quit()
    except RuntimeError, msg:
      pass
    return False # we want it to kill the window


  # FIXME: When this is run for restore, we should check for write permissions.
  def testConnection(self, parent, progress, host, username, password, port, path):
    """Test connection settings"""
    from fwbackups import sftp
    import socket
    progress.set_pulse_step(0.02)
    progress.startPulse()
    progress.set_text(_('Creating thread'))
    self.logger.logmsg('DEBUG', _('testConnection(): Creating thread'))
    thread = fwbackups.runFuncAsThread(sftp.testConnection, host, username, password, port, path)
    while thread.retval == None:
      progress.set_text(_('Attempting to connect'))
      doGtkEvents()
    progress.stopPulse()
    progress.set_text('')
    self.logger.logmsg('DEBUG', _('testConnection(): Thread returning with retval %s' % str(thread.retval)))
    if thread.retval == True:
      self.displayInfo(parent, _("Success!"), _("fwbackups was able to connect and authenticate on '%s'.") % host)
    elif type(thread.exception) == IOError:
      self.displayInfo(parent, _("Remote destination is not usable"), _("The folder '%(a)s' on '%(b)s' either does not exist or it is not a folder. Please verify your settings and try again.") % {'a': path, 'b': host})
    elif type(thread.exception) == paramiko.AuthenticationException:
      self.displayInfo(parent, _("Authentication failed"), _("A connection to '%s' was established, but authentication failed. Please verify the username and password and try again.") % host)
    elif type(thread.exception) == socket.gaierror or type(thread.exception) == socket.error:
      self.displayInfo(parent, _("A connection to '%s' could not be established") % host, _("Error %(a)s: %(b)s") % {'a': type(thread.exception), 'b': str(thread.exception)})
    elif type(thread.exception) == socket.timeout:
      self.displayInfo(parent, _("The server '%s' is not responding") % host, _("Please verify your settings and try again."))
    elif type(thread.exception) == paramiko.SSHException:
      self.displayInfo(parent, _("A connection to '%s' could not be established") % host, _("Error: %s. Please verify your settings and try again.") % str(thread.exception))
    else:
      self.displayInfo(parent, _("Unexpected error"), thread.traceback)
  ###
  ### MENUS ###
  ###

  ### FILE MENU
  def on_new_set1_activate(self, widget):
    """New Set entry in menu"""
    self.on_main2NewSetButton_clicked(widget)

  def on_import_sets1_activate(self, widget):
    """Import Set entry in menu"""
    fileDialog = widgets.PathDia(self.ui.path_dia, _('Select file(s)'), self.ui.main,
                                 gtk.FILE_CHOOSER_ACTION_OPEN, ffilter=['*.conf','Configuration files (*.conf)'],
                                 multiple=False)
    response = fileDialog.run()
    if response == gtk.RESPONSE_OK:
      oldSetPaths = [path.decode('utf-8') for path in fileDialog.get_filenames()]
      for oldSetPath in oldSetPaths:
        # Attempt to use the original set name
        oldSetName = os.path.basename(os.path.splitext(oldsetpath)[0])
        setName = oldSetName
        setPath = os.path.join(SETLOC, "%s.conf" % setName)
        # If original set name exists, append a number
        if os.path.exists(os.path.join(SETLOC, "%s.conf" % setName)):
          counter = 1
          while True:
            setName = "%s%s" % (oldSetName, counter)
            setPath = os.path.join(SETLOC, "%s.conf" % setname)
            if os.path.exists(setPath):
              counter += 1
            else:
              break
              os.path.join(SETLOC, "%s.conf" % setname)
        # Load the old set configuration
        oldSetConf = config.ConfigFile(oldSetPath)
        if "General" not in oldSetConf.sections():
          # Very old configuration file. New sections/structure will be created
          setConf = config.BackupSetConf(setPath, True)
          paths = []
          # Parse the paths section from the pre-1.43.0 config file
          for path in oldSetConf.options("paths"):
            paths.append(oldSetConf.get("paths", path))
          if oldSetConf.get("prefs", "autotar"):
            paths.append("/etc")
          options = {}
          options["PkgListsToFile"] = int(oldSetConf.get('prefs', 'autorpm'))
          options["OldToKeep"] = int(oldSetConf.get('prefs', 'tokeep'))
          if UID == 0: # this can only be done if the user is root
            options["DiskInfoToFile"] = int(oldSetConf.get('prefs', 'autodiskinfo'))
          # Save the options to the new/imported backup set configuration
          setConf.save(paths, options, {}, mergeDefaults=True)
        else:
          # The new, post-1.43 config type. The below is in case .conf is in the
          # set name, as well as the filename
          shutil_modded.copy(oldSetPath, setPath)
          # This imports and validates the configuration automatically
          setConf = config.BackupSetConf(setPath)
      # Now that all sets have been imported, regenerate the crontab to schedule
      # the new backup sets.
      self.regenerateCrontab()
    fileDialog.destroy()
    self.main2IconviewRefresh()

  def _exportSet(self, model, path, iter, dest):
    """Exports a set. Arguments are standard for a liststore.foreach,
      except dest...
      dest: The destination to export to
   """
    if model.get_value(iter, 0):
      setName = model.get_value(iter, 1)
      setPath = os.path.join(SETLOC, "%s.conf" % setName)
      destSetPath = os.path.join(dest, os.path.basename(setPath))
      if os.path.exists(destSetPath):
        response = self.displayConfirm(self.ui.export_dia, _("File Exists"),
                                    _("'%s.conf' already exists! Would you like to overwrite it?") % setName)
        if response == gtk.RESPONSE_OK:
          os.remove(destSetPath)
        else:
          return
      shutil_modded.copy(setPath, destSetPath)
      self.logger.logmsg('INFO', _('Exported set `%(a)s\' to `%(b)s\'' % {'a': setName, 'b': dest}))

  def on_export_sets1_activate(self, widget):
    """Export Sets entry in menu"""
    self.ExportView1.refresh()
    exportDialog = widgets.GenericDia(self.ui.export_dia, _('Export Sets'), self.ui.main)
    self.ui.ExportFileChooserButton.set_current_folder(USERHOME)
    response = exportDialog.run()
    runLoop = True
    while runLoop:
      if response == gtk.RESPONSE_HELP:
        self.help()
      elif response == gtk.RESPONSE_OK:
        destination = self.ui.ExportFileChooserButton.get_filename()
        self.ExportView1.liststore.foreach(self._exportSet, destination)
        self.displayInfo(self.ui.export_dia, _('Sets exported'), _('The selected sets were exported successfully.'))
        break
      elif response == gtk.RESPONSE_CANCEL or response == gtk.RESPONSE_DELETE_EVENT:
        break
      response = exportDialog.run()
    exportDialog.destroy()

  def on_quit1_activate(self, widget):
    """Quit entry in menu"""
    return self.main_close(widget)

  ### EDIT MENU
  def on_edit_set1_activate(self, widget):
    """Edit Set entry in menu"""
    self.on_main2EditSetButton_clicked(None)

  def on_remove_set1_activate(self, widget):
    """Remove Set entry in menu"""
    self.on_main2RemoveSetButton_clicked(None)

  def on_duplicate_set1_activate(self, widget):
    """Duplicate Set entry in menu"""
    try:
      selected = getSelectedItems(self.ui.main2Iconview)[0]
      iterator = self.ui.main2Iconview.get_model().get_iter(selected)
      setName = self.ui.main2Iconview.get_model().get_value(iterator, 0)
      setPath = os.path.join(SETLOC, "%s.conf" % setName)
    except IndexError:
      self.displayWarning(self.ui.main, _('No set has been selected'), _('You must select a set to duplicate.'))
      return
    setConf = config.BackupSetConf(setPath)
    newSetName = setName
    while True:
      newSetName += _("_copy")
      newSetPath = os.path.join(SETLOC, "%s.conf" % newSetName)
      if not os.path.exists(newSetPath):
        break
    shutil_modded.copy(setPath, newSetPath)
    self.regenerateCrontab()
    self.main2IconviewRefresh()

  ### VIEW MENU

  # Switch tabs...  # Switch tabs...  # Switch tabs...
  """It's the same thing over and over so I'll explain here.
    There are the menu callbacks under the View menu to switch to the
    various tabs. Each function is essentially  doing 'When I'm toggled,
    check if I'm sensitive.
     > If yes, switch me to the correct tab.
     > If no, do nothing as I shouldn't be switching!
 """
  def on_overview1_activate(self, widget):
    if self.ui.OverviewRadioTool.get_property('sensitive') == 1:
      self.ui.mainControlNotebook.set_current_page(0)
      self.ui.OverviewRadioTool.set_active(True)
      return True
    else:
      return False
  def on_user_backup_sets1_activate(self, widget):
    if self.ui.BackupSetsRadioTool.get_property('sensitive') == 1:
      self.ui.mainControlNotebook.set_current_page(1)
      self.ui.BackupSetsRadioTool.set_active(True)
      return True
    else:
      return False
  def on_one_time_backup1_activate(self, widget):
    if self.ui.OneTimeRadioTool.get_property('sensitive') == 1:
      self.ui.mainControlNotebook.set_current_page(2)
      self.ui.OneTimeRadioTool.set_active(True)
      return True
    else:
      return False
  def on_log1_activate(self, widget):
    if self.ui.LogViewRadioTool.get_property('sensitive') == 1:
      self.ui.mainControlNotebook.set_current_page(3)
      self.ui.LogViewRadioTool.set_active(True)
      return True
    else:
      return False

  def on_RestoreToolButton_clicked(self, widget):
    """Show restore window"""
    self.ui.restoreControlNotebook.set_current_page(0)
    self.ui.restore1SourceTypeCombobox.set_active(0)
    self.ui.restore1ArchiveEntry.set_text('')
    self.ui.restore1FolderEntry.set_text('')
    self.ui.restore1DestinationEntry.set_text(USERHOME)
    self.ui.restore1HostEntry.set_text('')
    self.ui.restore1UsernameEntry.set_text('')
    self.ui.restore1PasswordEntry.set_text('')
    self.ui.restore1PortSpin.set_value(22.0)
    self.ui.restore1PathEntry.set_text('')
    self.ui.restore.show()
    self.ui.restore1SetNameCombobox.set_active(0)
    self.ui.restore1SetDateCombobox.set_active(0)

  def on_restore1_activate(self, widget):
    """Show restore window"""
    self.on_RestoreToolButton_clicked(widget)

  """It's the same thing over and over so I'll explain here.
    There are the toolbar button callbacks to switch to the various tabs.
 """
  def on_OverviewRadioTool_clicked(self, widget):
    self.ui.mainControlNotebook.set_current_page(0)
  def on_BackupSetsRadioTool_clicked(self, widget):
    self.ui.mainControlNotebook.set_current_page(1)
  def on_OneTimeRadioTool_clicked(self, widget):
    self.ui.mainControlNotebook.set_current_page(2)
  def on_LogViewRadioTool_clicked(self, widget):
    self.ui.mainControlNotebook.set_current_page(3)
  # /Switch tabs...  # /Switch tabs...  # /Switch tabs...

  def on_preferences1_activate(self, widget, event=None):
    """Shows preferences"""
    prefs = config.PrefsConf()
    self.ui.preferences.show()
    # HKCU\Software\Microsoft\Windows\CurrentVersion\Run
    # HKCU\Software\Microsoft\Windows NT\CurrentVersion\Winlogon\Userinit
    # HKCU\Software\Microsoft\Windows NT\CurrentVersion\Windows\{Run,Load}
    self.ui.preferencesShowTrayIconCheck.set_active(prefs.getboolean('Preferences', 'ShowTrayIcon'))
    self.ui.preferencesMinimizeTrayCloseCheck.set_active(prefs.getboolean('Preferences', 'MinimizeTrayClose'))
    self.ui.preferencesStartMinimizedCheck.set_active(prefs.getboolean('Preferences', 'StartMinimized'))
    self.ui.preferencesShowNotificationsCheck.set_active(prefs.getboolean('Preferences', 'ShowNotifications'))
    if MSWINDOWS:
      import _winreg
      k = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run")
      try:
        _winreg.QueryValueEx(k, 'fwbackups')
        exists = True
      except:
        exists = False
    elif LINUX:
      exists = os.path.exists('%s/.config/autostart/fwbackups-autostart.desktop' % USERHOME)
    elif DARWIN: # FIXME: Figure out autostart on OS X
      exists = False
    self.ui.preferencesSessionStartupCheck.set_active(exists)
    self.ui.preferencesAlwaysShowDebugCheck.set_active(prefs.getboolean('Preferences', 'AlwaysShowDebug'))
    self.ui.preferencesMinimizeTrayCloseCheck.set_active(prefs.getboolean('Preferences', 'MinimizeTrayClose'))
    if MSWINDOWS:
      self.ui.preferencesPycronEntry.set_text(prefs.get('Preferences', 'pycronLoc'))

  ### HELP MENU
  def on_about1_activate(self, widget):
    """Help > About"""
    self.ui.aboutControlNotebook.set_current_page(0)
    self.ui.about.show()

  def on_help1_activate(self, widget):
    """Help > Help"""
    self.help()

  def on_check_for_updates1_activate(self, widget):
    """Help > Check for Updates"""
    import webbrowser
    webbrowser.open_new("http://www.diffingo.com/update.php?product=fwbackups&version=%s" % fwbackups.__version__)


  ###
  ### PREFERENCES ###
  ###

  # FIXME: This can be optimized
  def on_preferencesShowTrayIconCheck_toggled(self, widget):
    """Show tray icon check"""
    prefs = config.PrefsConf()
    # Tray icon
    if self.ui.preferencesShowTrayIconCheck.get_active():
      prefs.set('Preferences', 'ShowTrayIcon', 1)
      if hasattr(self, 'trayicon'):
        self.trayicon.set_visible(True)
      else:
        self._setupTrayIcon()
    else:
      prefs.set('Preferences', 'ShowTrayIcon', 0)
      if hasattr(self, 'trayicon'):
        self.trayicon.set_visible(False)

  def on_preferencesMinimizeTrayCloseCheck_toggled(self, widget):
    """Minimize to tray on close?"""
    prefs = config.PrefsConf()
    # Tray icon
    if self.ui.preferencesMinimizeTrayCloseCheck.get_active():
      prefs.set('Preferences', 'MinimizeTrayClose', 1)
      self.ui.minimize_to_tray_on_close1.set_active(True)
    else:
      prefs.set('Preferences', 'MinimizeTrayClose', 0)
      self.ui.minimize_to_tray_on_close1.set_active(False)

  def on_preferencesStartMinimizedCheck_toggled(self, widget):
    """Start minimized?"""
    prefs = config.PrefsConf()
    # Tray icon
    if self.ui.preferencesStartMinimizedCheck.get_active():
      prefs.set('Preferences', 'StartMinimized', 1)
    else:
      prefs.set('Preferences', 'StartMinimized', 0)

  def on_preferencesShowNotificationsCheck_toggled(self, widget):
    """Show notifications check"""
    prefs = config.PrefsConf()
    # Notifications
    if self.ui.preferencesShowNotificationsCheck.get_active():
      prefs.set('Preferences', 'ShowNotifications', 1)
      self.ui.display_notifications1.set_active(True)
    else:
      prefs.set('Preferences', 'ShowNotifications', 0)
      self.ui.display_notifications1.set_active(False)

  def on_preferencesSessionStartupCheck_clicked(self, widget):
    """Start fwbackups when we login"""
    if self.ui.preferencesSessionStartupCheck.get_active(): #add
      if MSWINDOWS:
        import _winreg
        k = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run")
        _winreg.SetValueEx(k, 'fwbackups', 0, _winreg.REG_SZ, '"%s" --start-minimized' % os.path.join(INSTALL_DIR, 'fwbackups-runapp.pyw'))
        _winreg.CloseKey(k)
      else:
        shutil_modded.copy('%s/fwbackups-autostart.desktop' % INSTALL_DIR, '%s/.config/autostart' % USERHOME)
    else: #remove
      if MSWINDOWS:
        import _winreg
        try:
          k = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run")
          _winreg.DeleteValue(k, 'fwbackups')
          _winreg.CloseKey(k)
        except:
          self.logger.logmsg('DEBUG', _('Could not remove fwbackup\'s session autostart regkey: %s' % error))
      else:
        try:
          os.remove('%s/.config/autostart/fwbackups-autostart.desktop' % USERHOME)
        except Exception, error:
          self.logger.logmsg('DEBUG', _('Could not remove fwbackup\'s session autostart file: %s' % error))

  def on_preferencesAlwaysShowDebugCheck_toggled(self, widget):
    """Set always debug"""
    prefs = config.PrefsConf()
    # Notifications
    if self.ui.preferencesAlwaysShowDebugCheck.get_active():
      prefs.set('Preferences', 'AlwaysShowDebug', 1)
      self.logger.setLevel(fwlogger.L_DEBUG)
    else:
      prefs.set('Preferences', 'AlwaysShowDebug', 0)
      self.logger.setLevel(fwlogger.L_INFO)

  def on_preferencesResetDontShowMeButton_clicked(self, widget, event=None):
    """Resets all "Don't show me again" messages"""
    prefs = config.PrefsConf()
    for option in prefs.getPreferences().keys():
      if option.lower().startswith('dontshowme_'):
        prefs.set('Preferences', option, 0)
        self.logger.logmsg('DEBUG', _('Resetting preference \'%(a)s\' to 0' % {'a' : option}))

  def on_preferencesPycronBrowseButton_clicked(self, widget):
    """Open the file browser"""
    prefs = config.PrefsConf()
    fileDialog = widgets.PathDia(self.ui.path_dia, _('Select a Folder'), self.ui.main,
                                 gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                 multiple=False)
    response = fileDialog.run()
    if response == gtk.RESPONSE_OK:
      pycronInstallDir = fileDialog.get_filenames()[0]
      self.ui.preferencesPycronEntry.set_text(pycronInstallDir)
    fileDialog.destroy()

  def on_preferencesCloseButton_clicked(self, widget):
    """Close the preferences window"""
    if MSWINDOWS:
      pycronLoc = self.ui.preferencesPycronEntry.get_text().decode('utf-8')
      if not pycronLoc:
        self.displayInfo(self.ui.preferences,
                              _('Missing information'),
                              _('Please enter a Pycron installation directory.'))
        return
      if not os.path.exists('%s/pycron.cfg' % pycronLoc) and not os.path.exists('%s/pycron.cfg.sample' % pycronLoc):
        self.displayInfo(self.ui.preferences,
                              _('Configuration not found'),
                              _('The pycron configuration file was not found in ' + \
                                'the directory entered. Please ensure that pycron ' + \
                                'is installed in the selected installation folder ' + \
                                'and that it contains either a pycron configuration file ' + \
                                'or the sample pycron configuration.'))
        return
      else:
        prefs = config.PrefsConf()
        prefs.set('Preferences', 'pycronLoc', pycronLoc)
    self.ui.preferences.hide()


  ###
  ### ABOUT WINDOW ###
  ###


  def on_aboutCloseButton_clicked(self, widget):
    """Close button for About"""
    self.hide(self.ui.about)

  def on_aboutWebsiteButton_clicked(self, widget):
    import webbrowser
    webbrowser.open_new('http://www.diffingo.com/opensource')


  ###
  ### BACKUPSET WINDOW ###
  ###


  def on_backupset2LocalFolderEntry_changed(self, widget):
    """Called when the set destination entry changes.
        Check the permissions when the set destination change."""
    self._checkDestPerms(widget.get_text().decode('utf-8'), self.ui.backupset2FolderPermissionImage)

  def on_backupset2HidePasswordCheck_toggled(self, widget):
    """Should we display plaintext passwords instead of circles?"""
    self.ui.backupset2PasswordEntry.set_visibility(not widget.get_active())

  ### TAB 1: PATHS
  def on_backupset1PathsTreeview_row_activated(self, widget, path, column):
    """Double click on backupset1PathsTreeview"""
    self.backupset1PathView.editPath()

  def on_backupset1AddFolderButton_clicked(self, widget):
    """Add path"""
    self.backupset1PathView.addFolder()

  def on_backupset1AddFileButton_clicked(self, widget):
    """Add file"""
    self.backupset1PathView.addFile()

  def on_backupset1RemoveButton_clicked(self, widget):
    """Remove path"""
    self.backupset1PathView.removePath()

  ### TAB 2: DESTINATION
  def on_backupset2DestinationTypeCombobox_changed(self, widget):
    """Destination type changed"""
    active = widget.get_active()
    self.ui.backupset2DestinationTypeNotebook.set_current_page(active)
    tables = [self.ui.backupset2DestinationTypeTable0, self.ui.backupset2DestinationTypeTable1]
    for i in tables:
      i.set_sensitive(False)
    tables[active].set_sensitive(True)

    # disable incremental for remote
    if active == 1:
      self.ui.backupset4IncrementalCheck.set_active(False)
      self.ui.backupset4IncrementalCheck.set_sensitive(False)
    elif not MSWINDOWS:
      self.ui.backupset4IncrementalCheck.set_sensitive(True)

  def on_backupset2FolderBrowseButton_clicked(self, widget):
    """Open the file browser to choose a folder"""
    fileDialog = widgets.PathDia(self.ui.path_dia, _('Select a Folder'), self.ui.backupset,
                                 gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                 multiple=False)
    response = fileDialog.run()
    if response == gtk.RESPONSE_OK:
      destination = fileDialog.get_filenames()[0]
      self.ui.backupset2LocalFolderEntry.set_text(destination)
    fileDialog.destroy()

  def on_backupset2TestSettingsButton_clicked(self, widget):
    """Test the remote settings"""
    host = self.ui.backupset2HostEntry.get_text()
    username = self.ui.backupset2UsernameEntry.get_text()
    password = self.ui.backupset2PasswordEntry.get_text()
    port = self.ui.backupset2PortSpin.get_value_as_int()
    folder = self.ui.backupset2RemoteFolderEntry.get_text().decode('utf-8')
    if not (host and username and port and folder):
      self.displayInfo(self.ui.backupset, _("Missing information"), _("Please complete the host, username, folder and port fields."))
      return False
    self.testConnection(self.ui.backupset, self.backupset2TestSettingsProgress, host, username, password, port, folder)

  ### TAB 3: TIMES
  # Time: Only/At
  def on_MonthOnlyBox_changed(self, widget):
    """Box changed; Set the right radiobutton"""
    self.ui.MonthOnly.set_active(True)
  def on_DaysWeekOnlyBox_changed(self, widget):
    """Box changed; Set the right radiobutton"""
    self.ui.DaysWeekOnly.set_active(True)
  def on_HoursAtBox_changed(self, widget):
    """Box changed; Set the right radiobutton"""
    self.ui.HoursAt.set_active(True)
  def on_MinutesOnlyScale_change_value(self, widget, scroll, value):
    """Scale changed; Set the right radiobutton"""
    self.ui.MinutesAt.set_active(True)
  # Time: Range (1)
  def on_MonthFromBox1_changed(self, widget):
    """Box changed; Set the right radiobutton"""
    self.ui.MonthFrom.set_active(True)
  def on_DaysWeekFromBox1_changed(self, widget):
    """Box changed; Set the right radiobutton"""
    self.ui.DaysWeekFrom.set_active(True)
  # Time: Range (2)
  def on_MonthFromBox2_changed(self, widget):
    """Box changed; Set the right radiobutton"""
    self.ui.MonthFrom.set_active(True)
  def on_DaysWeekFromBox2_changed(self, widget):
    """Box changed; Set the right radiobutton"""
    self.ui.DaysWeekFrom.set_active(True)

  def on_backupset3EasyConfigExpander_activate(self, widget):
    """Easy time config toggled: Reverse expanders"""
    self.ui.backupset3EasyConfigTable.set_sensitive(not self.ui.backupset3EasyConfigTable.get_property('sensitive'))
    self.ui.backupset3ManualConfigTable.set_sensitive(not self.ui.backupset3ManualConfigTable.get_property('sensitive'))
    time.sleep(0.2)
    self.ui.backupset3ManualConfigExpander.set_expanded(not self.ui.backupset3ManualConfigExpander.get_expanded())

  def on_backupset3ManualConfigExpander_activate(self, widget):
    """Manual time config toggled: Reverse expanders"""
    self.ui.backupset3EasyConfigTable.set_sensitive(not self.ui.backupset3EasyConfigTable.get_property('sensitive'))
    self.ui.backupset3ManualConfigTable.set_sensitive(not self.ui.backupset3ManualConfigTable.get_property('sensitive'))
    time.sleep(0.2)
    self.ui.backupset3EasyConfigExpander.set_expanded(not self.ui.backupset3EasyConfigExpander.get_expanded())

  ### TAB 4: OPTIONS
  def on_backupset4EngineRadio1_toggled(self, widget):
    if self.ui.backupset4EngineRadio1.get_active():
      self.ui.backupset4CompressCheck.set_sensitive(True)
    else:
      self.ui.backupset4CompressCheck.set_sensitive(False)
      self.ui.backupset4CompressCheck.set_active(False)
    
  
  def on_backupset4EngineRadio2_toggled(self, widget):
    """Set the sensibility of Incremental"""
    if self.ui.backupset4EngineRadio2.get_active() and not MSWINDOWS and \
       self.ui.backupset2DestinationTypeCombobox.get_active() != 1:
      self.ui.backupset4IncrementalCheck.set_sensitive(True)
    else:
      self.ui.backupset4IncrementalCheck.set_sensitive(False)
      self.ui.backupset4IncrementalCheck.set_active(False)

  def on_backupset4IncrementalCheck_toggled(self, widget):
    """To Keep must be 0"""
    if self.ui.backupset4IncrementalCheck.get_active():
      self.ui.backupset4OldToKeepSpin.set_value(0.0)
      self.ui.backupset4OldToKeepSpin.set_sensitive(False)
    else:
      self.ui.backupset4OldToKeepSpin.set_sensitive(True)
  
  def on_backupset4CompressCheck_toggled(self, widget):
    """Unset the compression combo if not selected"""
    if self.ui.backupset4CompressCheck.get_active():
      self.ui.backupset4CompressCombo.set_sensitive(True)
    else:
      self.ui.backupset4CompressCombo.set_active(-1)
      self.ui.backupset4CompressCombo.set_sensitive(False)
  

  ###
  ### MAIN WINDOW ###
  ###


  ### TAB 2: SETS
  def on_main2Iconview_item_activated(self, widget, event):
    """Double click on main2Iconview"""
    self.on_main2EditSetButton_clicked(None)

  def on_OneTimeTreeview_row_activated(self, widget, path, column):
    """Double click on OneTimeTreeview"""
    self.main3PathView.editPath()

  def on_main2NewSetButton_clicked(self, widget):
    """New Set button in main"""
    tempConfPath = os.path.join(SETLOC, "temporary_config.conf")
    if os.path.exists(tempConfPath):
      try:
        os.remove(tempConfPath)
      except:
        pass
    setConf = config.BackupSetConf(tempConfPath, True)
    self.restoreSetSettingsToUI(setConf)
    self.action = 'editingSet;temporary_config'
    self._toggleLocked(True, [self.ui.BackupSetsRadioTool, self.ui.backup_sets1, self.ui.backupset])
    self.ui.backupset.show()
    self.ui.backupset1NameEntry.set_text('')

  def on_main2EditSetButton_clicked(self, widget):
    """Edit Set button in main"""
    try:
      selected = getSelectedItems(self.ui.main2Iconview)[0]
      model = self.ui.main2Iconview.get_model()
      iterator = model.get_iter(selected)
      setName = model.get_value(iterator, 0)
      setPath = os.path.join(SETLOC, "%s.conf" % setName)
    except:
      self.displayWarning(self.ui.main, _('No set has been selected'), _('You must select a set to edit.'))
      return
    self.action = 'editingSet;%s' % setName
    self._toggleLocked(True, [self.ui.BackupSetsRadioTool, self.ui.backup_sets1, self.ui.backupset])
    self.ui.backupset.show()
    setConf = config.BackupSetConf(setPath)
    self.restoreSetSettingsToUI(setConf)


  def on_main2RemoveSetButton_clicked(self, widget):
    """Removes a set."""
    try:
      model = self.ui.main2Iconview.get_model()
      selected = getSelectedItems(self.ui.main2Iconview)[0]
      iterator = model.get_iter(selected)
      setName = model.get_value(iterator, 0)
      setPath = os.path.join(SETLOC, "%s.conf" % setName)
    except IndexError:
      self.displayWarning(self.ui.main, _('No set has been selected'), _('You must select a set to remove.'))
      return
    response = self.displayConfirm(self.ui.main, _("Delete backup set '%s'?") % setName, _("This action will permanently delete the backup set configuration. This action does not delete any existing backups or files."))
    if response == gtk.RESPONSE_NO:
      return
    elif response == gtk.RESPONSE_YES:
      setConf = config.BackupSetConf(setPath)
      try:
        os.remove(setPath)
      except OSError, error:
        message = _('An error occured while removing set `%(a)s\':\n%(b)s' % {'a': setName, 'b': error })
        self.displayError(self.ui.main, _("Could not remove backup set '%s'") % setName, message)
        self.logger.logmsg('ERROR', message)
        self.main2IconviewRefresh()
        return
      try:
        self.regenerateCrontab()
      except Exception, error:
        message = _('An error occured while removing set `%(a)s\':\n%(b)s' % {'a': setName, 'b': error })
        self.displayError(self.ui.main, _("Could not remove the automated backup schedule for set '%s'"), message)
        self.logger.logmsg('ERROR', message)
        self.main2IconviewRefresh()
        return
      message = _('Removing set `%s\'') % setName
      self.statusbar.newmessage(message, 3)
      self.logger.logmsg('DEBUG', message)
      self.main2IconviewRefresh()

  def on_main2Iconview_selection_changed(self, widget):
    """Selection changed, update sensitive widgets!"""
    try:
      selected = getSelectedItems(widget)
    except Exception, error:
      self.displayInfo(self.ui.main, _("Unexpected error"), _("An unexpected error occured while attempting to obtain the selected set:\n%s" % error))
      self.main2IconviewRefresh()
      selected = False
    if selected == False or len(selected) <= 0:
      self.ui.edit_set1.set_sensitive(False)
      self.ui.remove_set1.set_sensitive(False)
      self.ui.duplicate_set1.set_sensitive(False)
    elif selected:
      self.ui.edit_set1.set_sensitive(True)
      self.ui.remove_set1.set_sensitive(True)
      self.ui.duplicate_set1.set_sensitive(True)
    else:
      self.ui.edit_set1.set_sensitive(False)
      self.ui.remove_set1.set_sensitive(False)
      self.ui.duplicate_set1.set_sensitive(False)

  def on_main2BackupSetNowButton_clicked(self, widget):
    """Backup now button in main"""
    self.startSetBackup()

  def on_main2FinishBackupButton_clicked(self, widget):
    """Finish the backup"""
    self.operationInProgress = False
    self.main2BackupProgress.set_fraction(0.0)
    self._toggleLocked(False)
    for widget in [self.ui.new_set1, self.ui.import_sets1, self.ui.export_sets1]:
      widget.set_sensitive(True)
    self.main2BackupProgress.set_text(_('Click \'Backup Set Now\' to begin'))
    self.setStatus(_('Idle'))
    self.ui.main2FinishBackupButton.hide()
    self.ui.main2CancelBackupButton.show()
    self.ui.main2CancelBackupButton.set_sensitive(False)
    self.main2IconviewRefresh()

  def on_main2CancelBackupButton_clicked(self, widget):
    """Cancel set backup button in main"""
    self.cancelSetBackup()

  def on_main2RestoreSetButton_clicked(self, widget):
    """Restore button in main"""
    try:
      selected = self.ui.main2Iconview.get_selected_items()[0]
      iterator = self.ui.main2Iconview.get_model().get_iter(selected)
      setName = self.ui.main2Iconview.get_model().get_value(iterator, 0)
    except IndexError:
      self.displayWarning(self.ui.main, _('No set has been selected'), _('You must select a set to restore.'))
      return
    self.on_RestoreToolButton_clicked(None)
    self._setRestoreSetName(setName)

  ### TAB 3: ONE-TIME BACKUP

  def on_main3AddFolderButton_clicked(self, widget):
    """Add path in One-time backup"""
    self.main3PathView.addFolder()
  def on_main3AddFileButton_clicked(self, widget):
    """Add file in One-time backup"""
    self.main3PathView.addFile()
  def on_main3RemoveButton_clicked(self, widget):
    """Remove path in One-time backup"""
    self.main3PathView.removePath()

  def on_main3HidePasswordCheck_toggled(self, widget):
    """Should we display plaintext passwords instead of circles?"""
    self.ui.main3PasswordEntry.set_visibility(not widget.get_active())
  
  def on_main3EngineRadio1_toggled(self, widget):
    if self.ui.main3EngineRadio1.get_active():
      self.ui.main3CompressCheck.set_sensitive(True)
    else:
      self.ui.main3CompressCheck.set_sensitive(False)
      self.ui.main3CompressCheck.set_active(False)
  
  def on_main3CompressCheck_toggled(self, widget):
    """Unset the compression combo if not selected"""
    if self.ui.main3CompressCheck.get_active():
      self.ui.main3CompressCombo.set_sensitive(True)
    else:
      self.ui.main3CompressCombo.set_active(-1)
      self.ui.main3CompressCombo.set_sensitive(False)
      

  def on_main3NextButton_clicked(self, widget):
    """Next button on One Time backup"""
    currentPage = self.ui.main3ControlNotebook.get_current_page()
    if currentPage == 1: # switching 3rd > 4th (last configurable page)
      active = self.ui.main3DestinationTypeCombobox.get_active()
      if active == 0: # local
        if not self.ui.main3LocalFolderEntry.get_text():
          self.displayInfo(self.ui.main, _('Missing information'), _('Please fill in the Folder field.'))
          return
      elif active == 1: # remote
        if not self.ui.main3HostEntry.get_text() or not self.ui.main3UsernameEntry.get_text()\
        or not self.ui.main3PortSpin.get_value_as_int() or not self.ui.main3RemoteFolderEntry.get_text():
          self.displayInfo(self.ui.main, _('Missing information'), _('Please fill in the Host, Username, Port and Folder fields.'))
          return
      self.ui.main3NextButton.hide()
      self.ui.main3StartBackupButton.show()
    self.ui.main3ControlNotebook.set_current_page(currentPage + 1)
    self.ui.main3BackButton.show()
    self.ui.main3BackButton.set_sensitive(True)

  def on_main3BackButton_clicked(self, widget):
    """Back button on One Time backup"""
    currentPage = self.ui.main3ControlNotebook.get_current_page()
    self.ui.main3ControlNotebook.set_current_page(currentPage - 1)
    if currentPage == 2: # switching last > 3rd
      self.ui.main3StartBackupButton.hide()
      self.ui.main3NextButton.show()
    elif currentPage == 1: # switching 2nd > 1st
      self.ui.main3BackButton.set_sensitive(False)
    self.ui.main3NextButton.show()
    self.ui.main3StartBackupButton.hide()

  def on_main3FinishButton_clicked(self, widget):
    """Finish the one time backup"""
    self.operationInProgress = False
    self.main3Refresh()
    self.ui.main3ControlNotebook.set_current_page(0)
    self.ui.main3BackButton.set_sensitive(False)
    self.ui.main3FinishButton.hide()
    self.ui.main3StartBackupButton.hide()
    self.ui.main3BackButton.show()
    self.ui.main3NextButton.show()
    self.ui.main3HidePasswordCheck.set_active(True)
    self.ui.main3PkgListsToFileCheck.set_active(False)
    self.ui.main3PkgListsToFileCheck.set_sensitive(False)
    self.ui.main3DiskInfoToFileCheck.set_active(False)
    self.ui.main3DiskInfoToFileCheck.set_sensitive(False)
    self.ui.main3PortSpin.set_value(22.0)
    self._toggleLocked(False)
    self.setStatus(_('Idle'))

  def on_main3StartBackupButton_clicked(self, widget):
    """Start one-time backup on Main"""
    self.ui.main3ControlNotebook.set_current_page(3)
    self.ui.main3StartBackupButton.hide()
    self.ui.main3BackButton.hide()
    self.ui.main3FinishButton.show()
    self.ui.main3FinishButton.set_sensitive(False)
    self.ui.main3CancelBackupButton.set_sensitive(True)
    self.startOneTimeBackup()
    self.ui.main3FinishButton.set_sensitive(True)

  def on_main3CancelBackupButton_clicked(self, widget):
    """Cancel one-time backup on Main"""
    self.cancelOneTimeBackup()

  def on_main3HidePasswordCheck_toggled(self, widget):
    """Should we display plaintext passwords instead of circles?"""
    self.ui.main3PasswordEntry.set_visibility(not widget.get_active())

  def on_main3DestinationTypeCombobox_changed(self, widget):
    """Destination type changed"""
    active = widget.get_active()
    self.ui.main3DestinationTypeNotebook.set_current_page(active)
    tables = [self.ui.main3DestinationTypeTable0, self.ui.main3DestinationTypeTable1]
    for i in tables:
      i.set_sensitive(False)
    tables[active].set_sensitive(True)

  def on_main3LocalFolderEntry_changed(self, widget):
    """Called when the one-time destination's entry changes.
        Checks the permissions when the onetime destination changed."""
    self._checkDestPerms(widget.get_text().decode('utf-8'), self.ui.main3FolderPermissionImage)

  def on_main3FolderBrowseButton_clicked(self, widget):
    """Open the file browser to choose a folder"""
    fileDialog = widgets.PathDia(self.ui.path_dia, _('Select a Folder'), self.ui.main,
                                 gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                 multiple=False)
    response = fileDialog.run()
    if response == gtk.RESPONSE_OK:
      destination = fileDialog.get_filenames()[0]
      self.ui.main3LocalFolderEntry.set_text(destination)
    fileDialog.destroy()

  def on_main3TestSettingsButton_clicked(self, widget):
    """Test the remote settings"""
    host = self.ui.main3HostEntry.get_text()
    username = self.ui.main3UsernameEntry.get_text()
    password = self.ui.main3PasswordEntry.get_text()
    port = self.ui.main3PortSpin.get_value_as_int()
    folder = self.ui.main3RemoteFolderEntry.get_text().decode('utf-8')
    if not (host and username and port and folder):
      self.displayInfo(self.ui.main, _('Missing information'), _('Please complete all of the host, username, folder and port fields.'))
      return False
    self.testConnection(self.ui.main, self.main3TestSettingsProgress, host, username, password, port, folder)

  ### TAB 4: LOGGER

  def updateLogViewer(self, severity, message):
    """Add a message to the log viewer"""
    # idle_add because this is called from logger, in ANOTHER THREAD.
    gobject.idle_add(self.logconsole.write_log_line, message)

  def on_LogViewerRefreshButton_clicked(self, widget):
    """Refresh log viewer"""
    self.logconsole.clear()
    self.logconsole.goBottom()

  def on_LogViewerClearButton_clicked(self, widget):
    """Clear the log"""
    def clearlog():
      """Does the actual log clearing"""
      overwrite = open(LOGLOC, 'w')
      overwrite.write('')
      overwrite.close()
      self.logconsole.clear()
      self.logger.logmsg('INFO', _('Log cleared'))

    prefs = config.PrefsConf()
    if int(prefs.get('Preferences', 'DontShowMe_ClearLog')) == 1:
      return clearlog()
    response, dontShowMe = self.displayConfirm(self.ui.main, _("Clear the old log entries?"),
                                       _("This action will permanently remove all log entries."),
                                       dontShowMe=True)
    if response == gtk.RESPONSE_YES:
      if dontShowMe:
        prefs.set('Preferences', 'DontShowMe_ClearLog', 1)
      else:
        prefs.set('Preferences', 'DontShowMe_ClearLog', 0)
      clearlog()

  def on_LogViewerSaveToFileButton_clicked(self, widget):
    """Save log to file"""
    saveFilename = widgets.saveFilename(self.ui.main)
    if saveFilename:
      saveto = open(saveFilename, 'w')
      readfrom = open(LOGLOC, 'r')
      saveto.write(readfrom.read())
      readfrom.close()
      saveto.close()
      self.logger.logmsg('DEBUG', _("Log saved to file `%s'") % saveFilename)


  ### RESTORE WINDOW ###

  def on_restore1SourceTypeCombobox_changed(self, widget):
    """Source type changed: Change sensitivity"""
    active = widget.get_active()
    if active == 4:
      active = 3
    self.ui.restore1SourceTypeNotebook.set_current_page(active)
    tables = [self.ui.restore1SourceTypeTable0, self.ui.restore1SourceTypeTable1, \
             self.ui.restore1SourceTypeTable2, self.ui.restore1SourceTypeTable3]
    for i in tables:
      i.set_sensitive(False)
    tables[active].set_sensitive(True)

  def _checkDestPerms(self, path, image):
    if fwbackups.CheckPerms(path, mustExist=True):
      image.set_from_stock(gtk.STOCK_YES, gtk.ICON_SIZE_BUTTON)
      pass
    else:
      image.set_from_stock(gtk.STOCK_NO, gtk.ICON_SIZE_BUTTON)

  def _setRestoreSetName(self, setName):
    """Set the box choices based on setname"""
    model = self.ui.restore1SetNameCombobox.get_model()
    iter = model.get_iter_first()
    offset = 0
    while iter:
      if model.get_value(iter, 0) == setName:
        break
      iter = model.iter_next(iter)
      offset += 1
    self.ui.restore1SetNameCombobox.set_active_iter(iter)
    self._populateDates(setName)

  def getRemoteBackupDates(self, setConfig):
    """Retrieves a list of backups for backup set 'setName'"""
    from fwbackups import sftp
    import socket
    host = setConfig.get('Options', 'RemoteHost')
    username = setConfig.get('Options', 'RemoteUsername')
    password = setConfig.get('Options', 'RemotePassword').decode('base64')
    port = setConfig.get('Options', 'RemotePort')
    destination = setConfig.get('Options', 'RemoteFolder')
    client, sftpClient = sftp.connect(host, username, password, port)
    try:
      listing = sftpClient.listdir(destination)
      return listing
    finally:
      sftpClient.close()
      client.close()

  def _populateDates(self, setName):
    """Populates restore1SetDateCombobox with the appropriate backup date entries"""
    model = self.ui.restore1SetDateCombobox.get_model()
    model.clear()
    setPath = os.path.join(SETLOC, "%s.conf" % setName)
    setConfig = config.BackupSetConf(setPath)
    if setConfig.get('Options', 'DestinationType') == 'remote (ssh)':
      self.ui.restore1SourceTypeCombobox.set_sensitive(False)
      self.ui.restore1SetDateCombobox.set_sensitive(False)
      model.append(["Connecting to server, please wait..."])
      self.ui.restore1SetDateCombobox.set_active(0)
      thread = fwbackups.runFuncAsThread(self.getRemoteBackupDates, setConfig)
      while thread.retval == None:
        doGtkEvents()
      model.clear()
      # Default to None (see 'if listing == None' check later)
      listing = None
      # Check return value
      if type(thread.retval) == list:
        listing = thread.retval
      elif type(thread.exception) in [IOError, OSError]:
        self.displayInfo(self.ui.restore, _("Previous backups could not be found"),
          _("The destination folder for set '%s' was not found.") % setName)
      elif type(thread.exception) == paramiko.AuthenticationException:
        self.displayInfo(self.ui.restore, _("Authentication failed"),
          _("fwbackups was unable to authenticate on the remote server. Please verify the username and password for set '%s' and try again.") % setName)
      elif type(thread.exception) == socket.gaierror or type(thread.exception) == socket.error:
        self.displayInfo(self.ui.restore, _("Connection failed"),
          _("A connection to the server could not be established:\nError %(a)s: %(b)s\nPlease verify your settings and try again.") % {'a': type(thread.exception), 'b': str(thread.exception)})
      elif type(thread.exception) == socket.timeout:
        self.displayInfo(self.ui.restore, _("Remote server is not responding"),
          _("Please verify your settings and try again."))
      elif type(thread.exception) == paramiko.SSHException:
        self.displayInfo(self.ui.restore, _("Connection failed"),
          _("A connection to the server could not be established because an error occurred: %s\nPlease verify your settings and try again.") % str(thread.exception))
      else:
        self.displayInfo(self.ui.restore, _('Unexpected error'), thread.traceback)
      # Restore sensitivity to the widgets
      self.ui.restore1SourceTypeCombobox.set_sensitive(True)
      self.ui.restore1SetDateCombobox.set_sensitive(True)
      # If an error occurred and a listing could not be obtained, return
      if listing == None:
        return
    else:
      try:
        destination = setConfig.get('Options', 'Destination')
        listing = os.listdir(destination)
      except OSError, error:
        self.logger.logmsg("WARNING", _("Error obtaining file listing in destination %(a)s:\n%(b)s") % {'a': destination, 'b': error})
        self.displayError(self.ui.restore, _("Could not get a list of old backups for set '%s'" % setName), _("If the destination is on removable media such as an external hard disk, please attach it and try again."))
        return
    listing.sort() # [oldest, older, old, new, newest]
    listing.reverse() # make newest first
    backupDates = []
    for i in listing:
      # fmt: Backup-SetName from Backup-Setname-2009-03-22_20-46[.tar[.gz|.bz2]]
      if i.startswith('%s-%s-' % (_('Backup'), setName)):
        backupDates.append(i)
    if backupDates == []:
      model.append([_('No backups found')])
    for i in backupDates:
      if i.endswith('tar.gz'):
        engine = 'tar.gz'
      elif i.endswith('tar.bz2'):
        engine = 'tar.bz2'
      elif i.endswith('.tar'):
        engine = 'tar'
      else: # rsync
        engine = 'rsync'
      date = '-'.join(i.split('-')[2:]).split('.')[0] # returns year-month-day
      # Can't use this below - the engine can change while we still have the
      # old engine's backup folders/archives still.
      #engine = setConf.get('Options', 'Engine')
      model.append(['%s - %s' % (date, engine)])
    self.ui.restore1SetDateCombobox.set_active(0)

  def on_restore1SetNameCombobox_changed(self, widget):
    activeText = self.ui.restore1SetNameCombobox.get_active_text()
    if activeText == None:
      return
    self._populateDates(activeText)

  def on_restore1TestSettingsButton_clicked(self, widget):
    """Test the remote settings"""
    host = self.ui.restore1HostEntry.get_text()
    username = self.ui.restore1UsernameEntry.get_text()
    password = self.ui.restore1PasswordEntry.get_text()
    port = self.ui.restore1PortSpin.get_value_as_int()
    path = self.ui.restore1PathEntry.get_text().decode('utf-8')
    if not (host and username and port and path):
      self.displayInfo(self.ui.main, _('Missing information'), _('Please complete all of the host, username, folder and port fields.'))
      return False
    if self.ui.restore1SourceTypeCombobox.get_active() == 3:
      self.testConnection(self.ui.restore, self.restore1TestSettingsProgress, host, username, password, port, path)
    else:
      self.testConnection(self.ui.restore, self.restore1TestSettingsProgress, host, username, password, port, path)

  def saveRestoreConfiguration(self, restoreConf, setConfig=None):
    """Save all the information to a .conf file"""
    # Generate the options dictionary
    options = {}
    active = self.ui.restore1SourceTypeCombobox.get_active()
    options["Destination"] = self.ui.restore1DestinationEntry.get_text().decode('utf-8')
    # Default remote settings
    options["RemoteHost"] = ''
    options["RemotePort"] = 22
    options["RemoteUsername"] = ''
    options["RemotePassword"] = ''
    options["RemoteSource"] = ''
    if active == 0: # set
      sourceType = 'set'
      date = ' - '.join(self.ui.restore1SetDateCombobox.get_active_text().split(' - ')[:-1])
      # Can't use this for calculating 'path' since we could backup with tar,
      # then change to tar.gz this would return tar.gz, when the extension
      # needs to be tar... so we use this_engine above which is specific to
      # this backup
      #engine = setConfig.get('Options', 'Engine')
      this_engine = self.ui.restore1SetDateCombobox.get_active_text().split(' - ')[-1]
      if this_engine == 'rsync':
        backupName = '%s-%s-%s' % (_('Backup'), setConfig.getSetName(), date)
      else:
        # At the moment restore on Python 2.4 is not implemented; tarfile.extractall() doesn't exist.
        if sys.version_info[0] == 2 and sys.version_info[1] == 4:
          self.displayError(self.ui.restore, _("Automated restore not supported"), _("This backup set cannot be automatically restored because restoration of Archive backups has not been implemented for systems with Python 2.4. Please see the user guide for details on manual restoration."))
          return False
        backupName = '%s-%s-%s.%s' % (_('Backup'), setConfig.getSetName(), date, this_engine)
      if setConfig.get('Options', 'DestinationType') == 'remote (ssh)':
        options["RemoteHost"] = setConfig.get('Options', 'RemoteHost')
        options["RemoteUsername"] = setConfig.get('Options', 'RemoteUsername')
        options["RemotePassword"] = setConfig.get('Options', 'RemotePassword')
        options["RemotePort"] = setConfig.get('Options', 'RemotePort')
        remoteDestination = setConfig.get('Options', 'RemoteFolder')
        options["RemoteSource"] = os.path.join(remoteDestination, backupName)
        # RemoteSource is transferred to Destination before restoring begins
        options["Source"] = os.path.join(options["Destination"], backupName)
      else:
        localDestination = setConfig.get('Options', 'Destination')
        options["Source"] = os.path.join(localDestination, backupName)
    elif active == 1: # local archive
      # At the moment restore on Python 2.4 is not implemented; tarfile.extractall() doesn't exist.
      if sys.version_info[0] == 2 and sys.version_info[1] == 4:
        self.displayError(self.ui.restore, _("Automated restore not supported"), _("This backup set cannot be automatically restored because restoration of Archive backups has not been implemented for systems with Python 2.4. Please see the user guide for details on manual restoration."))
        return False
      sourceType = 'local archive'
      options["Source"] = self.ui.restore1ArchiveEntry.get_text().decode('utf-8')
    elif active == 2: # local folder
      sourceType = 'local folder'
      options["Source"] = self.ui.restore1FolderEntry.get_text().decode('utf-8')
    elif active == 3: # remote archive
      # At the moment restore on Python 2.4 is not implemented; tarfile.extractall() doesn't exist.
      if sys.version_info[0] == 2 and sys.version_info[1] == 4:
        self.displayError(self.ui.restore, _("Automated restore not supported"), _("This backup set cannot be automatically restored because restoration of Archive backups has not been implemented for systems with Python 2.4. Please see the user guide for details on manual restoration."))
        return False
      sourceType = 'remote archive (SSH)'
      options["RemoteHost"] = self.ui.restore1HostEntry.get_text()
      options["RemoteUsername"] = self.ui.restore1UsernameEntry.get_text()
      options["RemotePassword"] = self.ui.restore1PasswordEntry.get_text().encode("base64")
      options["RemotePort"] = self.ui.restore1PortSpin.get_value_as_int()
      options["RemoteSource"] = self.ui.restore1PathEntry.get_text().decode('utf-8')
      # RemoteSource is transferred to Destination before restoring begins
      options["Source"] = os.path.join(options["Destination"], os.path.basename(options["RemoteSource"]))
    elif active == 4: # remote folder
      sourceType = 'remote folder (SSH)'
      options["RemoteHost"] = self.ui.restore1HostEntry.get_text()
      options["RemoteUsername"] = self.ui.restore1UsernameEntry.get_text()
      options["RemotePassword"] = self.ui.restore1PasswordEntry.get_text().encode("base64")
      options["RemotePort"] = self.ui.restore1PortSpin.get_value_as_int()
      options["RemoteSource"] = self.ui.restore1PathEntry.get_text().decode('utf-8')
      # RemoteSource is transferred to Destination before restoring begins
      options["Source"] = os.path.join(options["Destination"], os.path.basename(options["RemoteSource"]))
    # Finally, save all information
    options["SourceType"] = sourceType
    restoreConf.save(options)
    return True

  def on_restoreStartButton_clicked(self, widget):
    source = ''
    active = self.ui.restore1SourceTypeCombobox.get_active()
    restoreConfig = config.RestoreConf(RESTORELOC, True)
    if active == 0: # Set backup
      if self.ui.restore1SetDateCombobox.get_active() == None:
        self.displayInfo(self.ui.restore, _('Missing information'), _('Please select a backup date.'))
        return False
      setModel = self.ui.restore1SetNameCombobox.get_model()
      setActiveIter = self.ui.restore1SetNameCombobox.get_active_iter()
      setName = setModel.get_value(setActiveIter, 0)
      setPath = os.path.join(SETLOC, "%s.conf" % setName)
      setConfig = config.BackupSetConf(setPath)
      # We can't start a restore if there are no set dates
      if self.ui.restore1SetDateCombobox.get_active_text() == _("No backups found"):
        self.displayError(self.ui.restore, _("No backups found"), _("The backup set '%s' does not have any stored backups yet! Choose another set, or alternatively choose a different restore source.") % setName)
        return False
      if not self.saveRestoreConfiguration(restoreConfig, setConfig):
        return False
    elif active == 1: # Local archive
      filename = self.ui.restore1ArchiveEntry.get_text()
      if not filename:
        self.displayInfo(self.ui.main, _('Restore source'), _('Please enter the location of the local archive.'))
        return False
      elif not filename.endswith('.tar') and not filename.endswith('.tar.gz') and not filename.endswith('.tar.bz2'):
        self.displayInfo(self.ui.restore, _('Wrong file type'),
                         _('The file you selected is not a supported archive.\n' + \
                         'Supported archives types are tar with no, gzip or bzip2 compression.'))
        return False
      if not self.saveRestoreConfiguration(restoreConfig):
        return False
    elif active == 2: # local folder
      if not self.ui.restore1FolderEntry.get_text():
        self.displayInfo(self.ui.main, _('Restore source'), _('Please enter the location of the local folder.'))
        return False
      if not self.saveRestoreConfiguration(restoreConfig):
        return False
    elif active == 3: # remote archive
      host = self.ui.restore1HostEntry.get_text()
      username = self.ui.restore1UsernameEntry.get_text()
      port = self.ui.restore1PortSpin.get_value_as_int()
      path = self.ui.restore1PathEntry.get_text().decode('utf-8')
      if not (host and username and port and path):
        self.displayInfo(self.ui.main, _('Missing information'), _('Please complete all of the host, username, folder and port fields.'))
        return False
      if not self.saveRestoreConfiguration(restoreConfig):
        return False

    # finally...
    self.ui.restoreFinishButton.set_sensitive(False)
    self.ui.restoreFinishButton.show()
    self.ui.restoreStartButton.hide()
    self.ui.restoreCloseButton.hide()
    self.startRestore()

  def on_restore2CancelRestoreButton_clicked(self, widget):
    """Cancel set backup button in restore"""
    self.cancelRestore()

  def on_restoreCloseButton_clicked(self, widget):
    """Cancel the restore window - Close window"""
    self.on_restoreFinishButton_clicked(widget)

  def on_restoreFinishButton_clicked(self, widget):
    """Finish the restore"""
    self._toggleLocked(False, [self.ui.restore])
    for widget in [self.ui.new_set1, self.ui.import_sets1, self.ui.export_sets1]:
      widget.set_sensitive(True)
    self.operationInProgress = False
    self.ui.restoreStartButton.show()
    self.ui.restoreCloseButton.show()
    self.ui.restoreFinishButton.hide()
    self.ui.restore.hide()
    self.setStatus(_('Idle'))

  def on_restore1HidePasswordCheck_toggled(self, widget):
    """Should we display plaintext passwords instead of circles?"""
    self.ui.restore1PasswordEntry.set_visibility(not widget.get_active())

  def on_restore1DestinationEntry_changed(self, widget):
    self._checkDestPerms(widget.get_text().decode('utf-8'), self.ui.restore1DestinationPermissionImage)

  def on_restore1BrowseButton_clicked(self, widget):
    """Open the file browser to choose a folder"""
    fileDialog = widgets.PathDia(self.ui.path_dia, _('Select a Folder'), self.ui.restore,
                                 gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                 multiple=False)
    response = fileDialog.run()
    if response == gtk.RESPONSE_OK:
      destination = fileDialog.get_filenames()[0]
      self.ui.restore1DestinationEntry.set_text(destination)
    fileDialog.destroy()

  def on_restore1ArchiveBrowseButton_clicked(self, widget):
    """Open the file browser to choose a folder"""
    fileDialog = widgets.PathDia(self.ui.path_dia, _('Select a Folder'), self.ui.restore,
                                 gtk.FILE_CHOOSER_ACTION_OPEN,
                                 multiple=False)
    response = fileDialog.run()
    if response == gtk.RESPONSE_OK:
      destination = fileDialog.get_filenames()[0]
      self.ui.restore1ArchiveEntry.set_text(destination)
    fileDialog.destroy()

  def on_restore1FolderBrowseButton_clicked(self, widget):
    """Open the file browser to choose a folder"""
    fileDialog = widgets.PathDia(self.ui.path_dia, _('Select a Folder'), self.ui.restore,
                                 gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                 multiple=False)
    response = fileDialog.run()
    if response == gtk.RESPONSE_OK:
      destination = fileDialog.get_filenames()[0]
      self.ui.restore1FolderEntry.set_text(destination)
    fileDialog.destroy()

  # ***********************************************************************

  def _checkExistingOrNone(self, name, parent, entry):
    """Check if a filename exists, or if none is set."""
    if name == None or name == '':
      self.displayInfo(self.ui.backupset, _("Invalid set name"), _("Please enter a set name."))
      return False
    if name == 'temporary_config':
      self.displayInfo(self.ui.backupset, _("Invalid set name"), _("'temporary_name' is a reserved name. Please choose another name for the set."))
      return False
    if os.path.exists(os.path.join(SETLOC, "%s.conf" % name)):
      response = self.displayConfirm(self.ui.backupset,
                                         _("Overwrite settings for set '%s'?") % name,
                                         _("This will overwrite the stored settings with the current ones. Are you sure you want to continue?"))
      if response == gtk.RESPONSE_NO:
        return False
    return name

  def _setDefaultTimes(self):
    """Set the default times (no manual, everything @ 12:00"""
    self.ui.ManualMinuteEntry.set_text('')
    self.ui.ManualHourEntry.set_text('')
    self.ui.ManualDaysOfMonthEntry.set_text('')
    self.ui.ManualMonthEntry.set_text('')
    self.ui.ManualDaysOfWeekEntry.set_text('')

    self.ui.MonthOnlyBox.set_active(0)
    self.ui.MonthFromBox1.set_active(0)
    self.ui.MonthFromBox2.set_active(0)

    self.ui.DaysWeekOnlyBox.set_active(0)
    self.ui.DaysWeekFromBox1.set_active(0)
    self.ui.DaysWeekFromBox2.set_active(0)

    self.ui.HoursAtBox.set_active(0)

    self.ui.MonthAll.set_active(True)
    self.ui.DaysWeekAll.set_active(True)
    self.ui.MonthAll.set_active(True)
    self.ui.HoursAt.set_active(True)
    self.ui.HoursAtBox.set_active(0)
    self.ui.MinutesAt.set_active(True)
    self.ui.MinutesAtScale.set_value(0.0)
    self.ui.backupset3EasyConfigExpander.set_expanded(True)
    self.ui.backupset3ManualConfigExpander.set_expanded(False)
    self.ui.backupset3EasyConfigTable.set_sensitive(True)
    self.ui.backupset3ManualConfigTable.set_sensitive(False)

  def _backupsetDefaults(self):
    """Clean up for display"""
    self.ui.backupsetControlNotebook.set_current_page(0)
    self.ui.backupset2DestinationTypeNotebook.set_current_page(0)
    self.ui.backupset2HidePasswordCheck.set_active(True)
    self._setDefaultTimes()

  def restoreSetSettingsToUI(self, setConf):
    """Restore all the information from a .conf file"""
    self.ui.backupset1NameEntry.set_text(setConf.getSetName())
    # Restore times
    # FIXME: If this fails, we should set defaults instead of halting
    self._backupsetDefaults()
    self.backupset1PathView.refresh(setConf)
    t = setConf.get('Times', 'Custom')
    l = setConf.get('Times', 'Entry').split(' ')
    if t.strip() == 'False': # easy config used
      self.ui.backupset3EasyConfigExpander.set_expanded(True)
      self.ui.backupset3ManualConfigExpander.set_expanded(False)
      self.ui.backupset3EasyConfigTable.set_sensitive(True)
      self.ui.backupset3ManualConfigTable.set_sensitive(False)
      if l[0] == '*': # Minute
        self.ui.MinutesAll.set_active(True)
      else:
        self.ui.MinutesAt.set_active(True)
        self.ui.MinutesAtScale.set_value(float(l[0]))
      # Hour
      if l[1] == '*':
        self.ui.HoursAll.set_active(True)
      else:
        self.ui.HoursAt.set_active(True)
        self.ui.HoursAtBox.set_active(int(l[1]))
      # l[2] **Days of month would go here
      # Months
      t = l[3].split('-')
      if l[3] == '*':
        self.ui.MonthAll.set_active(True)
      elif len(t) == 1: # only one month
        self.ui.MonthOnly.set_active(True)
        self.ui.MonthOnlyBox.set_active(int(l[3]) - 1)
      elif len(t) == 3: # 2x range of months
        self.ui.MonthFrom.set_active(True)
        self.ui.MonthFromBox1.set_active(int(t[1].split(',')[1]) - 1)
        self.ui.MonthFromBox2.set_active(int(t[1].split(',')[0]) - 1)
      else: # range of months
        self.ui.MonthFrom.set_active(True)
        self.ui.MonthFromBox1.set_active(int(t[0]) - 1)
        self.ui.MonthFromBox2.set_active(int(t[1]) - 1)
      # Day of Week
      t = l[4].split('-')
      if l[4] == '*':
        self.ui.DaysWeekAll.set_active(True)
      elif len(t) == 1: # only one day
        self.ui.DaysWeekOnly.set_active(True)
        self.ui.DaysWeekOnlyBox.set_active(int(l[4]))
      elif len(t) == 3: # 2x range of days
        self.ui.DaysWeekFrom.set_active(True)
        self.ui.DaysWeekFromBox1.set_active(int(t[1].split(',')[1]))
        self.ui.DaysWeekFromBox2.set_active(int(t[1].split(',')[0]))
      else: # range of days
        self.ui.DaysWeekFrom.set_active(True)
        self.ui.DaysWeekFromBox1.set_active(int(t[0]))
        self.ui.DaysWeekFromBox2.set_active(int(t[1]))
    else: # fill the manual fields
      self.ui.backupset3EasyConfigExpander.set_expanded(False)
      self.ui.backupset3ManualConfigExpander.set_expanded(True)
      self.ui.backupset3EasyConfigTable.set_sensitive(False)
      self.ui.backupset3ManualConfigTable.set_sensitive(True)
      try:
        self.ui.ManualMinuteEntry.set_text(l[0])
        self.ui.ManualHourEntry.set_text(l[1])
        self.ui.ManualDaysOfMonthEntry.set_text(l[2])
        self.ui.ManualMonthEntry.set_text(l[3])
        self.ui.ManualDaysOfWeekEntry.set_text(l[4])
      except IndexError: # list isn't long enough - something's gone horrible wrong.
        self.displayInfo(self.ui.backupset,
                              _("Error parsing configuration file"),
                              _("fwbackups will using the default times instead."))
        self._setDefaultTimes()
    # Restore destination
    t = setConf.get('Options', 'DestinationType')
    if t == 'local':
      # stupid hack because the combobox may not change but
      # the notebook is reset in setdefaults
      self.ui.backupset2DestinationTypeCombobox.set_active(1)
      self.ui.backupset2DestinationTypeCombobox.set_active(0)
    elif t == 'remote (ssh)':
      self.ui.backupset2DestinationTypeCombobox.set_active(0)
      self.ui.backupset2DestinationTypeCombobox.set_active(1)
    else:
      raise fwbackups.fwbackupsError(_('Unknown destination type `%s\'' % t))
    self.ui.backupset2HostEntry.set_text(setConf.get('Options', 'RemoteHost'))
    self.ui.backupset2PortSpin.set_value(float(setConf.get('Options', 'RemotePort') or 22))
    self.ui.backupset2UsernameEntry.set_text(setConf.get('Options', 'RemoteUsername'))
    self.ui.backupset2PasswordEntry.set_text(setConf.get('Options', 'RemotePassword').decode('base64'))
    self.ui.backupset2RemoteFolderEntry.set_text(setConf.get('Options', 'RemoteFolder'))
    t = setConf.get('Options', 'Destination')
    self.ui.backupset2LocalFolderEntry.set_text(t)
    self._checkDestPerms(t, self.ui.backupset2FolderPermissionImage)
    # Restore options
    t = setConf.get('Options', 'Enabled')
    if t == '1':
      self.ui.backupset4EnableCheck.set_active(True)
    else:
      self.ui.backupset4EnableCheck.set_active(False)
    t = setConf.get('Options', 'Recursive')
    if t == '1':
      self.ui.backupset4RecursiveCheck.set_active(True)
    else:
      self.ui.backupset4RecursiveCheck.set_active(False)
    t = setConf.get('Options', 'PkgListsToFile')
    if t == '1':
      self.ui.backupset4PkgListsToFileCheck.set_active(True)
    else:
      self.ui.backupset4PkgListsToFileCheck.set_active(False)
    t = setConf.get('Options', 'DiskInfoToFile')
    if t == '1':
      self.ui.backupset4DiskInfoToFileCheck.set_active(True)
    else:
      self.ui.backupset4DiskInfoToFileCheck.set_active(False)
    t = setConf.get('Options', 'BackupHidden')
    if t == '1':
      self.ui.backupset4BackupHiddenCheck.set_active(True)
    else:
      self.ui.backupset4BackupHiddenCheck.set_active(False)
    t = setConf.get('Options', 'Sparse')
    if t == '1':
      self.ui.backupset4SparseCheck.set_active(True)
    else:
      self.ui.backupset4SparseCheck.set_active(False)
    t = setConf.get('Options', 'FollowLinks')
    if t == '1':
      self.ui.backupset4FollowLinksCheck.set_active(True)
    else:
      self.ui.backupset4FollowLinksCheck.set_active(False)
    # The following options may be enabled depending on the engine selection
    # We don't want any UI leftovers from the last time we opened a set, so
    # disable them now and re-enable them later if applicable.
    self.ui.backupset4IncrementalCheck.set_active(False)
    self.ui.backupset4CompressCheck.set_active(False)
    self.ui.backupset4CompressCheck.emit('toggled') # unsets the combobox
    # Check the engine types
    t = setConf.get('Options', 'Engine')
    if t == "tar":
      self.ui.backupset4EngineRadio1.set_active(True)
    elif t == "rsync":
      self.ui.backupset4EngineRadio2.set_active(True)
      y = setConf.get('Options', 'Incremental')
      if y == '1' and not MSWINDOWS:
        self.ui.backupset4IncrementalCheck.set_active(True)
    elif t == "tar.gz":
      self.ui.backupset4EngineRadio1.set_active(True)
      self.ui.backupset4CompressCheck.set_active(True)
      self.ui.backupset4CompressCombo.set_active(0);
    elif t == "tar.bz2":
      self.ui.backupset4EngineRadio1.set_active(True)
      self.ui.backupset4CompressCheck.set_active(True)
      self.ui.backupset4CompressCombo.set_active(1);
    # This ensures that incremental is at the proper sensitivity even if rsync
    # wasn't clicked on/off
    self.ui.backupset4EngineRadio2.emit('toggled')
    self.ui.backupset4OldToKeepSpin.set_value(float(setConf.get('Options', 'OldToKeep')))
    # Advanced entries
    self.ui.backupset5NiceScale.set_value(float(setConf.get('Options', 'Nice')))
    self.ui.backupset5CommandBeforeEntry.set_text(setConf.get('Options', 'CommandBefore'))
    self.ui.backupset5CommandAfterEntry.set_text(setConf.get('Options', 'CommandAfter'))
    self.ui.backupset5ExcludesTextview.get_buffer().set_text(setConf.get('Options', 'Excludes'))
    # finally: disable what should be disabled
    if MSWINDOWS:
      self.ui.backupset4PkgListsToFileCheck.set_active(False)
      self.ui.backupset4PkgListsToFileCheck.set_sensitive(False)
      self.ui.backupset4DiskInfoToFileCheck.set_active(False)
      self.ui.backupset4DiskInfoToFileCheck.set_sensitive(False)

  def saveSetConfiguration(self, setConf):
    """Save all the information to a .conf file, add to crontab"""
    # Generate a list of paths
    paths = []
    treeiter = self.backupset1PathView.liststore.get_iter_first()
    while treeiter:
      # UI requires we store UTF-8 encoded strings, so we must decode from UTF-8
      path = self.backupset1PathView.liststore.get_value(treeiter, 1)
      paths.append(path.decode('utf-8'))
      treeiter = self.backupset1PathView.liststore.iter_next(treeiter)
    # Configure the Times dict
    times = {}
    origEntry = setConf.get('Times', 'Entry').split(' ')
    if self.ui.backupset3EasyConfigExpander.get_expanded():
      # Easy configuration, must generate the crontab line manually
      times["Custom"] = False
      entry = []
      # Order of appends must be same as crontab
      # Minutes
      if self.ui.MinutesAll.get_active():
        entry.append('*')
      if self.ui.MinutesAt.get_active():
        entry.append(str(int(self.ui.MinutesAtScale.get_value())))
      # Hours
      if self.ui.HoursAll.get_active():
        entry.append('*')
      if self.ui.HoursAt.get_active():
        entry.append(str(self.ui.HoursAtBox.get_active()))
      # Days of month
      entry.append('*')
      # Months
      if self.ui.MonthAll.get_active():
        entry.append('*')
      elif self.ui.MonthOnly.get_active():
        entry.append(str(self.ui.MonthOnlyBox.get_active() + 1))
      elif self.ui.MonthFrom.get_active():
        from1 = int(self.ui.MonthFromBox1.get_active()) + 1
        from2 = int(self.ui.MonthFromBox2.get_active()) + 1
        if from1 > from2:
          entry.append('1-%i,%i-12' % (from2, from1))
        else:
          entry.append('%i-%i' % (from1, from2))
      # Days of week
      if self.ui.DaysWeekAll.get_active():
        entry.append('*')
      if self.ui.DaysWeekOnly.get_active():
        entry.append(str(self.ui.DaysWeekOnlyBox.get_active()))
      if self.ui.DaysWeekFrom.get_active():
        from1 = int(self.ui.DaysWeekFromBox1.get_active())
        from2 = int(self.ui.DaysWeekFromBox2.get_active())
        if from1 > from2:
          entry.append('0-%i,%i-7' % (from2, from1))
        else:
          entry.append('%i-%i' % (from1, from2))
    else:
      # Custom format, do not validate
      times["Custom"] = True
      entry = []
      entry.append(self.ui.ManualMinuteEntry.get_text().strip())
      entry.append(self.ui.ManualHourEntry.get_text())
      entry.append(self.ui.ManualDaysOfMonthEntry.get_text().strip())
      entry.append(self.ui.ManualMonthEntry.get_text().strip())
      entry.append(self.ui.ManualDaysOfWeekEntry.get_text().strip())
    times["Entry"] =  ' '.join(entry)
    # Configure the Options dict
    options = {}
    # Destination
    t = self.ui.backupset2DestinationTypeCombobox.get_active()
    if t == 0:
      dtype = 'local'
    elif t == 1:
      dtype = 'remote (ssh)'
    options["DestinationType"] = dtype
    options["RemoteHost"] = self.ui.backupset2HostEntry.get_text()
    options["RemoteUsername"] = self.ui.backupset2UsernameEntry.get_text()
    options["RemotePassword"] = self.ui.backupset2PasswordEntry.get_text().encode('base64')
    options["RemotePort"] = self.ui.backupset2PortSpin.get_value_as_int()
    options["RemoteFolder"] = self.ui.backupset2RemoteFolderEntry.get_text().decode('utf-8')
    options["Destination"] = self.ui.backupset2LocalFolderEntry.get_text().decode('utf-8')
    # Save options
    options["Enabled"] = int(self.ui.backupset4EnableCheck.get_active())
    options["Recursive"] = int(self.ui.backupset4RecursiveCheck.get_active())
    options["PkgListsToFile"] = int(self.ui.backupset4PkgListsToFileCheck.get_active())
    options["DiskInfoToFile"] = int(self.ui.backupset4DiskInfoToFileCheck.get_active())
    options["BackupHidden"] = int(self.ui.backupset4BackupHiddenCheck.get_active())
    options["Sparse"] = int(self.ui.backupset4SparseCheck.get_active())
    options["FollowLinks"] = int(self.ui.backupset4FollowLinksCheck.get_active())
    options["Incremental"] = int(self.ui.backupset4IncrementalCheck.get_active())
    if self.ui.backupset4EngineRadio1.get_active():
      engine = 'tar'
      # did we enable compression?
      if self.ui.backupset4CompressCheck.get_active():
        active = self.ui.backupset4CompressCombo.get_active()
        if active == 0:
          engine += '.gz'
        elif active == 1:
          engine += '.bz2'
    elif self.ui.backupset4EngineRadio2.get_active():
      engine = 'rsync'
    options["Engine"] = engine
    options["CommandBefore"] = self.ui.backupset5CommandBeforeEntry.get_text().decode('utf-8')
    options["CommandAfter"] = self.ui.backupset5CommandAfterEntry.get_text().decode('utf-8')
    options["OldToKeep"] = self.ui.backupset4OldToKeepSpin.get_value()
    start, end = self.ui.backupset5ExcludesTextview.get_buffer().get_bounds()
    options["Excludes"] = self.ui.backupset5ExcludesTextview.get_buffer().get_text(start, end)
    nice = int(self.ui.backupset5NiceScale.get_value())
    options["Nice"] = nice
    # Incase they copied configs with a niceness preset, reset it to 0
    # so the backup doesn't fail before it starts.
    if UID != 0 and nice < 0:
      options["Nice"] = 0
    # Finally, save all the information
    setConf.save(paths, options, times)
    try:
      self.regenerateCrontab()
    except cron.ValidationError:
      raise
    except Exception, error:
      self.displayInfo(self.ui.backupset,
                       _("Error creating the automated backup schedules"),
                       _('The crontab could not be written because an error occured:\n%s') % error)
      return

  def main2IconviewSetup(self):
    """Setup the backupset window for use"""
    self.main2BackupProgress = widgets.ProgressBar(self.ui.main2BackupProgress)
    self.main3TestSettingsProgress = widgets.ProgressBar(self.ui.main3TestSettingsProgress)
    self.backupset2TestSettingsProgress = widgets.ProgressBar(self.ui.backupset2TestSettingsProgress)
    self.restore1TestSettingsProgress = widgets.ProgressBar(self.ui.restore1TestSettingsProgress)
    self.backupset1PathView = widgets.PathView(self.ui.backupset1PathsTreeview, self.statusbar, self.ui, self.ui.backupset)
    self.ui.main2Iconview.set_model(gtk.ListStore(gobject.TYPE_STRING, gtk.gdk.Pixbuf))
    # Setup Iconview
    self.ui.main2Iconview.set_reorderable(False)
    self.ui.main2Iconview.set_text_column(0)
    self.ui.main2Iconview.set_pixbuf_column(1)
    self.ui.main2Iconview.set_item_width(110)
    self.ui.main2Iconview.set_row_spacing(10)
    self.ui.main2Iconview.set_column_spacing(20)
    self.icon = self.ui.backupset.render_icon(gtk.STOCK_DIRECTORY, gtk.ICON_SIZE_DIALOG)
    # Keep things clean...
    self.main2IconviewRefresh()

  def main3TabSetup(self):
    """Setup the OneTime tab for use"""
    self.main3BackupProgress = widgets.ProgressBar(self.ui.main3BackupProgress)
    self.main3PathView = widgets.PathView(self.ui.main3Treeview, self.statusbar, self.ui, self.ui.main)
    # Keep things clean...
    self.main3Refresh()

  def restoreSetup(self):
    """Setup the OneTime tab for use"""
    self.restore2RestorationProgress = widgets.ProgressBar(self.ui.restore2RestorationProgress)

  def _loadSets(self):
    """Load all set .conf files"""
    loaded_count = 0
    self.logger.logmsg('DEBUG', _('Parsing configuration files'))
    for root, dirs, files in os.walk(SETLOC):
      files.sort()
      for name in files:
        if name.endswith('.conf') and not name.startswith('.conf') and not name == 'temporary_config.conf':
          self.ui.main2Iconview.get_model().append([name.split('.conf')[0], self.icon])
          self.ui.restore1SetNameCombobox.get_model().append([name.split('.conf')[0]])
          loaded_count += 1
        else:
          self.logger.logmsg('WARNING', _('Refusing to parse file `%s\': configuration files must end in `.conf\'') % name)
    self.ui.TotalSetsLabel.set_text(str(loaded_count))
    self.ui.TotalSetsLabel.set_use_markup(True)

  def _clearSets(self):
    """Clear all sets from the view"""
    self.ui.main2Iconview.get_model().clear()
    self.ui.restore1SetNameCombobox.get_model().clear()

  def main2IconviewRefresh(self):
    """Refresh sets"""
    self._clearSets()
    self._loadSets()

  def main3Refresh(self):
    """Clear paths"""
    self.ui.main3Treeview.get_model().clear()
    self.ui.main3LocalFolderEntry.set_text(USERHOME)
    self.ui.main3DestinationTypeCombobox.set_active(0)
    self.ui.main3EngineRadio1.set_active(True)
    self.ui.main3CompressCheck.set_active(False)

  def on_backupsetApplyButton_clicked(self, widget):
    """Apply changes to backupset"""
    active = self.ui.backupset2DestinationTypeCombobox.get_active()
    if active == 0: # local
      if not self.ui.backupset2LocalFolderEntry.get_text():
        self.displayInfo(self.ui.main, _('Missing information'), _('Please fill in the Folder field.'))
        return
    elif active == 1: # remote
      if not self.ui.backupset2HostEntry.get_text() or not self.ui.backupset2UsernameEntry.get_text()\
      or not self.ui.backupset2PortSpin.get_value_as_int() or not self.ui.backupset2RemoteFolderEntry.get_text():
        self.displayInfo(self.ui.backupset, _('Missing information'), _('Please fill in the Host, Username, Port and Folder fields.'))
        return
    newName = self._checkExistingOrNone(self.ui.backupset1NameEntry.get_text(),
                                        self.ui.backupset,
                                        self.ui.backupset1NameEntry)
    if newName == False:
      return
    newPath = os.path.join(SETLOC, "%s.conf" % newName)
    setConf = config.BackupSetConf(newPath, True)
    # editing a set - check if we need to rename
    if self.action != None:
      action, name = self.action.split(';')
      if name != newName:
        self.action = '%s;%s' % (action, newName)
        namepath = os.path.join(SETLOC, "%s.conf" % name)
        if os.path.isfile(namepath):
          try:
            os.remove(namepath)
            self.logger.logmsg('DEBUG', _("Renaming set `%(a)s' to `%(b)s" % {'a': name, 'b': newName}))
          except IOError, error:
            self.logger.logmsg('DEBUG', _("Renaming set `%(a)s' to `%(b)s failed: %(c)s" % {'a': name, 'b': newName, 'c': error}))
            self.displayInfo(self.ui.backupset, _("Could not rename set '%(a)s' to '%(b)s'") % {'a': name, 'b': newName}, str(error))
    # Attempt to save the new set configuration
    try:
      self.saveSetConfiguration(setConf)
      settingsNeedRevision = False
      if self.action == None: # creating a set
        message = _('Creating set `%s\'' % newName)
        self.statusbar.newmessage(message, 3)
        self.logger.logmsg('DEBUG', message)
      else: # editing a set
        message = _('Saving changes to set `%s\'' % newName)
        self.statusbar.newmessage(message, 3)
        self.logger.logmsg('DEBUG', message)
    except cron.ValidationError:
      self.displayError(self.ui.backupset, _("Could not save backup schedule"), _("Your set configuration changes were saved, but fwbackups was unable to save the backup scheduling information to the crontab. If you are using manual times entry, please verify that all five fields are using the correct syntax."))
      settingsNeedRevision = True
    # See if user needs to revise settings first
    if settingsNeedRevision:
      return False
    self.action = None
    self.ui.backupset.hide()
    self._toggleLocked(False)
    self.main2IconviewRefresh()

  def on_backupsetCancelButton_clicked(self, widget):
    """Cancel - Run and hide!"""
    tempConfigPath = os.path.join(SETLOC, "temporary_config.conf")
    if os.path.exists(tempConfigPath):
      try:
        os.remove(tempConfigPath)
      except IOError:
        pass
    self.ui.backupset.hide()
    self._toggleLocked(False)

  def on_backupsetHelpButton_clicked(self, widget):
    """Open help/docs"""
    self.help()

  def startSetBackup(self):
    """Start a set backup"""
    def updateProgress(self):
      """Updates the statusbar"""
      if self.updateReturn:
          status, current, total, currentName = self.backupHandle.getProgress()
      else:
        return
      if status not in [backup.STATUS_INITIALIZING, backup.STATUS_EXECING_USER_COMMAND, backup.STATUS_CLEANING_OLD]:
        self.main2BackupProgress.set_fraction(float(current - 1)/float(total))
      # There is a current filename
      if status == backup.STATUS_BACKING_UP and currentName not in [None, '', '\n']:
        self.main2BackupProgress.set_text(_('[%(a)i/%(b)i] Backing up: %(c)s') % {'a': current, 'b': total, 'c': os.path.basename(currentName).strip('\n')})
      # There is no current filename
      elif status == backup.STATUS_BACKING_UP and not currentName:
        self.main2BackupProgress.set_text(_('[%(a)i/%(b)i] Backing up files... Please wait') % {'a': current, 'b': total})
      elif status == backup.STATUS_CLEANING_OLD:
        self.main2BackupProgress.set_text(_('Cleaning old backups'))
      elif status == backup.STATUS_SENDING_TO_REMOTE:
        self.main2BackupProgress.set_text(_('Sending files to remote server'))
      elif status == backup.STATUS_EXECING_USER_COMMAND:
        self.main2BackupProgress.set_text(_('Executing user command'))
      return self.updateReturn

    try:
      selected = self.ui.main2Iconview.get_selected_items()[0]
      iterator = self.ui.main2Iconview.get_model().get_iter(selected)
      name = self.ui.main2Iconview.get_model().get_value(iterator, 0)
    except IndexError:
      self.displayWarning(self.ui.main, _('No set has been selected'), _('You must select to initiate a manual set backup.'))
      return
    self.ui.mainControlNotebook.set_current_page(1)
    self.ui.BackupSetsRadioTool.set_active(True)
    prefs = config.PrefsConf()
    self.operationInProgress = True
    self.setStatus(_('Initializing'))
    if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
      self.trayNotify(_('Status'), _('Starting a set backup operation of \'%(a)s\'' % {'a': name}), 5)
    self._toggleLocked(True, [self.ui.BackupSetsRadioTool, self.ui.backup_sets1])
    self.main2BackupProgress.startPulse()
    self.main2BackupProgress.set_text(_('Please wait...'))
    try:
      self.backupHandle = backup.SetBackupOperation(os.path.join(SETLOC, "%s.conf" % name))
      self.backupThread = fwbackups.runFuncAsThread(self.backupHandle.start)
      self.ui.main2CancelBackupButton.show()
      self.ui.main2CancelBackupButton.set_sensitive(True)
      self.setStatus(_('Working'))
      self.updateReturn = True
      self.main2BackupProgress.stopPulse()
      updateProgress(self)
      updateTimeout = gobject.timeout_add(1000, updateProgress, self)
      while self.backupThread.retval == None:
        doGtkEvents()
      # thread returned
      self.logger.logmsg('DEBUG', _('Thread returned with retval %s' % self.backupThread.retval))
      # -1 indicates a syntax error or other bug in the backup code
      # False indicates a detectable problem during the backup. In this case,
      # the error has already been logged.
      if self.backupThread.retval == -1:
        self.logger.logmsg('WARNING', _('There was an error while performing the backup!'))
        self.logger.logmsg('ERROR', self.backupThread.traceback)
    except Exception, error:
      self.operationInProgress = False
      self.setStatus(_('<span color="Red">Error</span>'))
      message = _("An error occurred while initializing the backup operation: %s" % error)
      self.updateReturn = False
      self.main2BackupProgress.stopPulse()
      self.main2BackupProgress.set_text('')
      self.displayInfo(self.ui.main, _("Error initializing backup"), message)
      self.logger.logmsg('DEBUG', message)
      self.ui.main2CancelBackupButton.hide()
      self.ui.main2FinishBackupButton.show()
      return False
    updateProgress(self)
    self.updateReturn = False
    self.main2BackupProgress.set_fraction(1.0)
    if self.backupThread.retval == True:
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('Finished the automatic backup operation of set `%(a)s\'' % {'a': name}), 5)
      self.setStatus(_('<span color="dark green">Operation complete</span>'))
    elif self.backupThread.retval == -1 or self.backupThread.retval == False: # error
      self.setStatus(_('<span color="Red">Error</span>'))
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('An error occured while performing the automatic backup operation of set `%(a)s\'' % {'a': name}), 5)
    else:
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('The automatic backup operation of set `%(a)s\' was cancelled' % {'a': name}), 5)
      self.setStatus(_('<span color="red">Operation cancelled</span>'))
      self.main2BackupProgress.set_text(_('Operation cancelled'))
    self.ui.main2CancelBackupButton.hide()
    self.ui.main2FinishBackupButton.show()
    del(self.backupThread)
    del(self.backupHandle)
    self.operationInProgress = False


  def cancelSetBackup(self):
    self.updateReturn = False
    self.backupHandle.cancelOperation()
    self.main2BackupProgress.set_text(_('Please wait...'))
    self.setStatus(_('Cancelling...'))


  # ----------------------------------------------------------
  # ----------------------------------------------------------
  # ----------------------------------------------------------


  def saveOneTimeConfiguration(self, oneTimeConf):
    """Save all the information to a .conf file"""
    # Generate a list of paths
    paths = []
    treeiter = self.main3PathView.liststore.get_iter_first()
    while treeiter:
      # UI requires we store UTF-8 encoded strings, so we must decode from UTF-8
      path = self.main3PathView.liststore.get_value(treeiter, 1)
      paths.append(path.decode('utf-8'))
      treeiter = self.main3PathView.liststore.iter_next(treeiter)
    # Configure the Options dict
    options = {}
    # Destination
    t = self.ui.main3DestinationTypeCombobox.get_active()
    if t == 0:
      dtype = 'local'
    elif t == 1:
      dtype = 'remote (ssh)'
    options["DestinationType"] = dtype
    options["RemoteHost"] = self.ui.main3HostEntry.get_text()
    options["RemoteUsername"] = self.ui.main3UsernameEntry.get_text()
    options["RemotePassword"] = self.ui.main3PasswordEntry.get_text().encode('base64')
    options["RemotePort"] = self.ui.main3PortSpin.get_value_as_int()
    options["RemoteFolder"] = self.ui.main3RemoteFolderEntry.get_text().decode('utf-8')
    options["Destination"] = self.ui.main3LocalFolderEntry.get_text().decode('utf-8')
    options["Recursive"] = int(self.ui.main3RecursiveCheck.get_active())
    options["PkgListsToFile"] = int(self.ui.main3PkgListsToFileCheck.get_active())
    options["DiskInfoToFile"] = int(self.ui.main3DiskInfoToFileCheck.get_active())
    options["BackupHidden"] = int(self.ui.main3BackupHiddenCheck.get_active())
    options["Sparse"] = int(self.ui.main3SparseCheck.get_active())
    options["FollowLinks"] = int(self.ui.main3FollowLinksCheck.get_active())
    # no incremental for one-time
    options["Incremental"] = 0
    if self.ui.main3EngineRadio1.get_active():
      engine = 'tar'
      # did we enable compression?
      if self.ui.main3CompressCheck.get_active():
        active = self.ui.main3CompressCombo.get_active()
        if active == 0:
          engine += '.gz'
        elif active == 1:
          engine += '.bz2'
    elif self.ui.main3EngineRadio2.get_active():
      engine = 'rsync'
    options["Engine"] = engine
    start, end = self.ui.main3ExcludesTextview.get_buffer().get_bounds()
    options["Excludes"] = self.ui.main3ExcludesTextview.get_buffer().get_text(start, end)
    nice = int(self.ui.main3NiceScale.get_value())
    options["Nice"] = nice
    # Incase they copied configs with a niceness preset, reset it to 0
    # so the backup doesn't fail before it starts.
    if UID != 0 and nice < 0:
      options["Nice"] = 0
    oneTimeConf.save(paths, options)


  def startOneTimeBackup(self):
    """Start a set backup"""
    def updateProgress(self):
      """Updates the statusbar"""
      if self.updateReturn:
          status, current, total, currentName = self.backupHandle.getProgress()
      else:
        return
      if status not in [backup.STATUS_INITIALIZING, backup.STATUS_EXECING_USER_COMMAND, backup.STATUS_CLEANING_OLD]:
        self.main3BackupProgress.set_fraction(float(current - 1)/float(total))
      # There is a current filename
      if status == backup.STATUS_BACKING_UP and currentName not in [None, '', '\n']:
        self.main3BackupProgress.set_text(_('[%(a)i/%(b)i] Backing up: %(c)s') % {'a': current, 'b': total, 'c': os.path.basename(currentName).strip('\n')})
      # There is no current filename
      elif status == backup.STATUS_BACKING_UP and not currentName:
        self.main3BackupProgress.set_text(_('[%(a)i/%(b)i] Backing up files... Please wait') % {'a': current, 'b': total})
      elif status == backup.STATUS_CLEANING_OLD:
        self.main3BackupProgress.set_text(_('Cleaning old backups'))
      elif status == backup.STATUS_SENDING_TO_REMOTE:
        self.main3BackupProgress.set_text(_('Sending files to remote server'))
      elif status == backup.STATUS_EXECING_USER_COMMAND:
        self.main3BackupProgress.set_text(_('Executing user command'))
      return self.updateReturn

    oneTimeConfig = config.OneTimeConf(ONETIMELOC, True)
    self.saveOneTimeConfiguration(oneTimeConfig)
    self.ui.main3ControlNotebook.set_current_page(3)
    self.ui.OneTimeRadioTool.set_active(True)
    prefs = config.PrefsConf()
    self.operationInProgress = True
    self.setStatus(_('Initializing'))
    if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
      self.trayNotify(_('Status'), _('Starting a one-time backup operation'))
    self._toggleLocked(True, [self.ui.OneTimeRadioTool, self.ui.one_time_backup1])
    self.main3BackupProgress.startPulse()
    self.main3BackupProgress.set_text(_('Please wait...'))
    try:
      self.backupHandle = backup.OneTimeBackupOperation(ONETIMELOC, self.logger)
      self.backupThread = fwbackups.runFuncAsThread(self.backupHandle.start)
      self.setStatus(_('Working'))
      self.updateReturn = True
      self.main3BackupProgress.stopPulse()
      updateProgress(self)
      updateTimeout = gobject.timeout_add(1000, updateProgress, self)
      while self.backupThread.retval == None:
        doGtkEvents()
      # thread returned
      self.logger.logmsg('DEBUG', _('Thread returned with retval %s' % self.backupThread.retval))
      # -1 indicates a syntax error or other bug in the backup code
      # False indicates a detectable problem during the backup. In this case,
      # the error has already been logged.
      if self.backupThread.retval == -1:
        self.logger.logmsg('WARNING', _('There was an error while performing the backup!'))
        self.logger.logmsg('ERROR', self.backupThread.traceback)
    except Exception, error:
      self.operationInProgress = False
      self.setStatus(_('<span color="Red">Error</span>'))
      self.updateReturn = False
      self.main3BackupProgress.stopPulse()
      self.main3BackupProgress.set_text('')
      message = _("An error occurred while initializing the backup operation: %s" % error)
      self.displayInfo(self.ui.main, _("Error initializing backup"), message)
      self.logger.logmsg('DEBUG', message)
      self.ui.main3FinishButton.show()
      self.ui.main3FinishButton.set_sensitive(True)
      self.ui.main3CancelBackupButton.set_sensitive(False)
      return False
    updateProgress(self)
    self.updateReturn = False
    self.main3BackupProgress.set_fraction(1.0)
    if self.backupThread.retval == True:
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('Finished the one-time backup operation'))
      self.setStatus(_('<span color="dark green">Operation complete</span>'))
    elif self.backupThread.retval == -1 or self.backupThread.retval == False: # error
      self.setStatus(_('<span color="Red">Error</span>'))
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('An error occured while performing the one-time backup operation'), 5)
      # just incase we have leftover stuff running
      self.backupHandle.cancelOperation()
    else:
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('The one-time backup operation was cancelled'))
      self.setStatus(_('<span color="red">Operation cancelled</span>'))
      self.main3BackupProgress.set_text(_('Operation cancelled'))
    self.ui.main3FinishButton.show()
    self.ui.main3FinishButton.set_sensitive(True)
    self.ui.main3CancelBackupButton.set_sensitive(False)
    del(self.backupThread)
    del(self.backupHandle)
    self.operationInProgress = False

  def cancelOneTimeBackup(self):
    self.updateReturn = False
    self.backupHandle.cancelOperation()
    self.main3BackupProgress.set_text(_('Please wait...'))
    self.setStatus(_('Cancelling...'))

  def startRestore(self):
    """Start a set backup"""
    def updateProgress(self):
      """Updates the statusbar"""
      if self.updateReturn == True:
          status, current, total, currentName = self.restoreHandle.getProgress()
      else:
        return
      if status == restore.STATUS_RECEIVING_FROM_REMOTE: # no "current file" yet
        self.restore2RestorationProgress.set_text(_('Receiving files from remote server'))
      elif status == restore.STATUS_RESTORING: # we have a 'current file'
        self.restore2RestorationProgress.set_text(_('Restoring: %s') % os.path.basename(currentName))
      return self.updateReturn

    self.ui.restoreControlNotebook.set_current_page(1)
    prefs = config.PrefsConf()
    self.operationInProgress = True
    self.setStatus(_('Initializing'))
    if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
      self.trayNotify(_('Status'), _('Starting a restore operation'), 5)
    self._toggleLocked(True, [self.ui.restore])
    self.restore2RestorationProgress.startPulse()
    self.restore2RestorationProgress.set_text(_('Please wait...'))
    try:
      self.restoreHandle = restore.RestoreOperation(RESTORELOC, self.logger)
      self.restoreThread = fwbackups.runFuncAsThread(self.restoreHandle.start)
      self.ui.restore2CancelRestoreButton.set_sensitive(True)
      self.setStatus(_('Working'))
      self.updateReturn = True
      self.restore2RestorationProgress.startPulse()
      updateProgress(self)
      updateTimeout = gobject.timeout_add(1000, updateProgress, self)
      while self.restoreThread.retval == None:
        doGtkEvents()
      # thread returned
      self.logger.logmsg('DEBUG', _('Thread returned with retval %s' % self.restoreThread.retval))
      if self.restoreThread.retval == -1:
        self.logger.logmsg('WARNING', _('There was an error while performing the restore! Enable debug messages for more information.'))
        self.logger.logmsg('DEBUG', self.restoreThread.traceback)
    except Exception, error:
      self.operationInProgress = False
      self.setStatus(_('<span color="Red">Error</span>'))
      self.updateReturn = False
      self.restore2RestorationProgress.stopPulse()
      message = _("An error occurred while initializing the restore operation: %s" % error)
      self.displayInfo(self.ui.main, _("Error initializing restore operation"), message)
      self.logger.logmsg('DEBUG', message)
      self.ui.restoreFinishButton.set_sensitive(True)
      self.ui.restore2CancelRestoreButton.set_sensitive(False)
      return False
    updateProgress(self)
    self.updateReturn = False
    self.restore2RestorationProgress.set_text('')
    self.restore2RestorationProgress.stopPulse()
    self.restore2RestorationProgress.set_fraction(1.0)
    if self.restoreThread.retval == True:
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('Finished the restore operation'))
      self.setStatus(_('<span color="dark green">Operation complete</span>'))
      self.restore2RestorationProgress.set_text('')
    elif self.restoreThread.retval == -1 or self.restoreThread.retval == False: # error
      self.setStatus(_('<span color="Red">Error</span>'))
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('An error occured while performing the restore operation'), 5)
      # just incase we have leftover stuff running
      self.restoreHandle.cancelOperation()
    else:
      if int(prefs.get('Preferences', 'ShowNotifications')) == 1:
        self.trayNotify(_('Status'), _('The restore operation was cancelled'))
      self.setStatus(_('<span color="red">Operation cancelled</span>'))
      self.restore2RestorationProgress.set_text(_('Operation cancelled'))
    self.ui.restoreFinishButton.set_sensitive(True)
    self.ui.restore2CancelRestoreButton.set_sensitive(False)
    del(self.restoreThread)
    del(self.restoreHandle)
    self.operationInProgress = False

  def cancelRestore(self):
    self.updateReturn = False
    self.restoreHandle.cancelOperation()
    self.restore2RestorationProgress.set_text(_('Please wait...'))
    self.setStatus(_('Cancelling...'))

  # ***********************************************************************

# Only if we're in main execution
if __name__ == "__main__":
  verbose = False
  minimized = False
  from optparse import OptionParser
  parser = OptionParser(prog="fwbackups", version="fwbackups %s" % fwbackups.__version__)
  # Customize our help text for the pre-created options
  parser.get_option("--version").help = _("Show this program's version and exit")
  parser.get_option("--help").help = _("Show this help message and exit")
  # Add custom options
  parser.add_option("-v", "--verbose", action="count", dest="verbose", default=0, help=_("print log messages to the terminal. Use this option twice"))
  parser.add_option("--start-minimized", action="store_true", dest="start_minimized", default=False, help=_("start GUI minimized in the system tray"))
  (options, rest_args) = parser.parse_args()

  try:
    # Startup the application and call the gtk event loop
    MainApp = fwbackupsApp(options.verbose, options.start_minimized)
    gtk.main()
  except KeyboardInterrupt:
    # ctrl+c?
    MainApp.main_close(None)
