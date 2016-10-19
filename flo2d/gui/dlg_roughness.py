# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Flo2D
                                 A QGIS plugin
 FLO-2D tools for QGIS
                             -------------------
        begin                : 2016-08-28
        copyright            : (C) 2016 by Lutra Consulting for FLO-2D
        email                : info@lutraconsulting.co.uk
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 FLO-2D Preprocessor tools for QGIS.
"""
from qgis.core import *
from ..user_communication import UserCommunication
from .utils import load_ui

uiDialog, qtBaseClass = load_ui('roughness')


class RoughnessDialog(qtBaseClass, uiDialog):

    def __init__(self, con, iface, lyrs):
        qtBaseClass.__init__(self)
        uiDialog.__init__(self)
        self.iface = iface
        self.setupUi(self)
        self.uc = UserCommunication(iface, 'FLO-2D')
        self.con = con
        self.lyrs = lyrs

        # connections
        self.rlayer_cbo.currentIndexChanged.connect(self.populate_fields)
        self.populate_layers()

    def populate_layers(self):
        self.rlayer_cbo.clear()
        lyrs = [lyr.layer() for lyr in self.lyrs.root.findLayers()]
        for lyr in lyrs:
            if lyr.isValid() and lyr.type() == QgsMapLayer.VectorLayer and lyr.geometryType() == QGis.Polygon:
                self.rlayer_cbo.addItem(lyr.name(), lyr)
            else:
                pass
        self.populate_fields()

    def populate_fields(self):
        self.rfield_cbo.clear()
        cur_lyr = self.rlayer_cbo.itemData(self.rlayer_cbo.currentIndex())
        field_names = [field.name() for field in cur_lyr.pendingFields()]
        for fld in field_names:
            self.rfield_cbo.addItem(fld)
