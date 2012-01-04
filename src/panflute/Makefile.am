SUBDIRS = daemon applet debugger tests

panflutedir = $(pythondir)/panflute
panflute_PYTHON = 	\
	__init__.py	\
	mpris.py	\
	util.py

nodist_panflute_PYTHON =	\
	defs.py

defs.py: defs.py.in
	sed -e "s|@xPKGDATADIRx@|$(pkgdatadir)|" 	\
	    -e "s|@xDATADIRx@|$(datadir)|" 		\
	    $< >$@

BUILT_SOURCES = defs.py

EXTRA_DIST = defs.py.in.in

CLEANFILES = $(BUILT_SOURCES)
