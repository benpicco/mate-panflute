pkgdata_DATA = debugger.ui		\
	       panflute.svg		\
	       panflute-set-star.svg	\
	       panflute-unset-star.svg	\
	       preferences.ui		\
	       test220.ogg		\
	       test440.ogg		\
	       test660.ogg		\
	       tester.ui

serverdir       = $(libdir)/bonobo/servers
server_in_files = GNOME_Panflute_Applet.server.in
server_DATA     = $(server_in_files:.server.in=.server)

%.server.in: %.server.in.in
	sed -e "s|\@LIBEXECDIR\@|$(libexecdir)|" $< | sed -e "s|\@PKGDATADIR\@|$(pkgdatadir)|" >$@

@INTLTOOL_SERVER_RULE@

schemasdir       = @GCONF_SCHEMA_FILE_DIR@
schemas_in_files = panflute.schemas.in
schemas_DATA     = $(schemas_in_files:.schemas.in=.schemas)

@INTLTOOL_SCHEMAS_RULE@

servicedir = $(datadir)/dbus-1/services
service_in_files = org.kuliniewicz.Panflute.service.in		\
		   org.mpris.panflute.service.in
service_DATA = $(service_in_files:.service.in=.service)

%.service: %.service.in
	sed -e "s|\@BINDIR\@|$(bindir)|" $< >$@

uidir   = $(datadir)/gnome-2.0/ui
ui_DATA = GNOME_Panflute_Applet.xml

EXTRA_DIST = $(pkgdata_DATA) 					\
	     $(server_in_files:.server.in=.server.in.in) 	\
	     $(schemas_in_files) 				\
	     $(service_in_files)				\
	     $(ui_DATA)

CLEANFILES = $(server_in_files) 	\
	     $(server_DATA) 		\
	     $(schemas_DATA) 		\
	     $(service_DATA)

if GCONF_SCHEMAS_INSTALL
install-data-local:
	GCONF_CONFIG_SOURCE=$(GCONF_SCHEMA_CONFIG_SOURCE) $(GCONFTOOL) --makefile-install-rule $(schemas_DATA) ;
endif
