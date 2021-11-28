# -*- coding: utf-8 -*-

# FLO-2D Preprocessor tools for QGIS

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version

from ..utils import is_true
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsFeatureRequest
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QApplication, QTableWidgetItem, QDialogButtonBox
from .ui_utils import load_ui, set_icon, center_canvas, zoom
from ..geopackage_utils import GeoPackageUtils
from ..user_communication import UserCommunication

uiDialog, qtBaseClass = load_ui("pumps")
class PumpsDialog(qtBaseClass, uiDialog):
    def __init__(self, iface, lyrs):
        qtBaseClass.__init__(self)
        uiDialog.__init__(self)
        self.iface = iface
        self.lyrs = lyrs
        self.setupUi(self)
        self.uc = UserCommunication(iface, "FLO-2D")
        self.con = None
        self.gutils = None

        set_icon(self.find_pump_btn, "eye-svgrepo-com.svg")
        set_icon(self.zoom_in_pump_btn, "zoom_in.svg")
        set_icon(self.zoom_out_pump_btn, "zoom_out.svg")  

        self.find_pump_btn.clicked.connect(self.find_pump)
        self.zoom_in_pump_btn.clicked.connect(self.zoom_in_pump)
        self.zoom_out_pump_btn.clicked.connect(self.zoom_out_pump)
        
        set_icon(self.show_curve_btn, "show_cont_table.svg")
        set_icon(self.add_curve_btn, "add_bc_data.svg")
        set_icon(self.remove_curve_btn, "mActionDeleteSelected.svg")
        set_icon(self.rename_curve_btn, "change_name.svg")        
        
        self.pumps_buttonBox.button(QDialogButtonBox.Save).setText("Save to 'Storm Drain Pumps' User Layer")
        self.pump_name_cbo.currentIndexChanged.connect(self.fill_individual_controls_with_current_pump_in_table)
        
        self.pumps_buttonBox.accepted.connect(self.save_pumps)

        self.pump_curve_cbo.currentIndexChanged.connect(self.pump_curve_cbo_currentIndexChanged)
        self.pump_init_status_cbo.currentIndexChanged.connect(self.pump_init_status_cbo_currentIndexChanged)
        self.startup_depth_dbox.valueChanged.connect(self.startup_depth_dbox_valueChanged)
        self.shutoff_depth_dbox.valueChanged.connect(self.shutoff_depth_dbox_valueChanged)

        self.on_off = ("ON","OFF")
        
        self.setup_connection()
        self.grid_lyr = self.lyrs.data["grid"]["qlyr"]
        self.pumps_lyr = self.lyrs.data["user_swmm_pumps"]["qlyr"]
        self.populate_pumps()

        self.pumps_tblw.cellClicked.connect(self.pumps_tblw_cell_clicked)
        self.pumps_tblw.verticalHeader().sectionClicked.connect(self.onVerticalSectionClicked)

    def setup_connection(self):
        con = self.iface.f2d["con"]
        if con is None:
            return
        else:
            self.con = con
            self.gutils = GeoPackageUtils(self.con, self.iface)

    def populate_pumps(self):
        qry = """SELECT fid,
                        pump_name,
                        pump_inlet, 
                        pump_outlet,
                        pump_curve,
                        pump_init_status,
                        pump_startup_depth,
                        pump_shutoff_depth
                FROM user_swmm_pumps;"""

        try:
            rows = self.gutils.execute(qry).fetchall()
            self.pumps_tblw.setRowCount(0)
            for row_number, row_data in enumerate(rows): 
                self.pumps_tblw.insertRow(row_number)
                for column, data in enumerate(row_data):
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, data)  # item gets value of data (as QTableWidgetItem Class)

                    
                    if column == 1:  
                        # Fill the list of pump names:
                        self.pump_name_cbo.addItem(data, row_data[0])
                    if column == 4:  
                        # Fill the list of curve names:  
                        self.pump_curve_cbo.addItem(data, row_data[4])

                    # Fill all text boxes with data of first feature of query (first element in table user_swmm_pumps):
                    if row_number == 0:
                        if column == 2:
                            self.from_node_txt.setText(str(data))

                        elif column == 3:
                            self.to_node_txt.setText(str(data))

                        elif column == 4:           
                            index = self.pump_curve_cbo.findText(data)
                            if index == -1:
                                index = 0
                            self.pump_curve_cbo.setCurrentIndex(index)
                            
                        elif column == 5:           
                            index = self.pump_init_status_cbo.findText(data)
                            if index == -1:
                                index = 0
                            self.pump_init_status_cbo.setCurrentIndex(index)
                            
                        elif column == 6:
                            self.startup_depth_dbox.setValue(data)

                        elif column == 7:
                            self.shutoff_depth_dbox.setValue(data)

                    if column > 0:  # Omit fid number (in column = 0)
                        if column == 1 or column == 2 or column == 3:
                            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                        self.pumps_tblw.setItem(row_number, column - 1, item)
                        
            self.highlight_pump(self.pump_name_cbo.currentText())                        

        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.uc.show_error("ERROR 251121.0705: assignment of value from pumps users layer failed!.\n", e)




    """
    Events for changes in values of widgets: 
    
    """

    def startup_depth_dbox_valueChanged(self):
        self.box_valueChanged(self.startup_depth_dbox, 5)

    def shutoff_depth_dbox_valueChanged(self):
        self.box_valueChanged(self.shutoff_depth_dbox, 6)

    """
    General routines for changes in widgets:
    
    """

    def box_valueChanged(self, widget, col):
        row = self.pump_name_cbo.currentIndex()
        item = QTableWidgetItem()
        item.setData(Qt.EditRole, widget.value())
        self.pumps_tblw.setItem(row, col, item)

    def checkbox_valueChanged(self, widget, col):
        row = self.pump_name_cbo.currentIndex()
        item = QTableWidgetItem()
        self.pumps_tblw.setItem(row, col, item)
        self.pumps_tblw.item(row, col).setText("True" if widget.isChecked() else "False")

    def combo_valueChanged(self, widget, col):
        row = self.pump_name_cbo.currentIndex()
        item = QTableWidgetItem()
        data = widget.currentText()
        item.setData(Qt.EditRole, data)
        self.pumps_tblw.setItem(row, col, item)

    def pump_curve_cbo_currentIndexChanged(self):
        self.combo_valueChanged(self.pump_curve_cbo, 3)        

    def pump_init_status_cbo_currentIndexChanged(self):
        self.combo_valueChanged(self.pump_init_status_cbo, 4)        

    def pumps_tblw_cell_clicked(self, row, column):
        try:
            # self.blockSignals(True)
            self.pump_name_cbo.blockSignals(True)
            self.pump_name_cbo.setCurrentIndex(row)
            self.pump_name_cbo.blockSignals(False)

            self.from_node_txt.setText(self.pumps_tblw.item(row, 1).text())
            self.to_node_txt.setText(self.pumps_tblw.item(row, 2).text())
            
            curve = self.pumps_tblw.item(row, 3).text()            
            index = self.pump_curve_cbo.findText(curve)
            if index == -1:
                index = 0
            self.pump_curve_cbo.setCurrentIndex(index)

            status = self.pumps_tblw.item(row, 4).text()
            if status.isdigit():
                index = int(status) - 1
                index = 1 if index > 1 else 0 if index < 0 else index
            else:
                index = 0 if status == "ON" else 1
            self.pump_init_status_cbo.setCurrentIndex(index)            

            self.startup_depth_dbox.setValue(float(self.pumps_tblw.item(row, 5).text()))
            self.shutoff_depth_dbox.setValue(float(self.pumps_tblw.item(row, 6).text()))
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.uc.show_error("ERROR 261121.0707: assignment of value failed!.\n", e)

    def onVerticalSectionClicked(self, logicalIndex):
        self.pumps_tblw_cell_clicked(logicalIndex, 0)

    def fill_individual_controls_with_current_pump_in_table(self):
        try:
            # highlight row in table:
            row = self.pump_name_cbo.currentIndex()
            self.pumps_tblw.selectRow(row)

            # load controls (text boxes, etc.) with selected row in table:
            item = QTableWidgetItem()

            item = self.pumps_tblw.item(row, 1)
            if item is not None:
                self.from_node_txt.setText(str(item.text()))

            item = self.pumps_tblw.item(row, 2)
            if item is not None:
                self.to_node_txt.setText(str(item.text()))
                
            self.highlight_pump(self.pump_name_cbo.currentText()) 
          
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.uc.show_error("ERROR 200618.0631: assignment of value failed!.\n", e)

    def find_pump(self):
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if self.grid_lyr is not None:
                if self.grid_lyr:
                    pump = self.pump_to_find_le.text()
                    if pump != "":
                        indx = self.pump_name_cbo.findText(pump)
                        if  indx != -1:
                            self.pump_name_cbo.setCurrentIndex(indx)
                        else:
                            self.uc.bar_warn("WARNING 091121.0746: pump '" + str(pump) + "' not found.")
                    else:
                        self.uc.bar_warn("WARNING  091121.0747: pump '" + str(pump) + "' not found.")
        except ValueError:
            self.uc.bar_warn("WARNING  091121.0748: pump '" + str(pump) + "' not forund.")
            pass
        finally:
            QApplication.restoreOverrideCursor()

    def highlight_pump(self, pump):
        try:
            if self.pumps_lyr is not None:
                if pump != "":
                    fid = self.gutils.execute("SELECT fid FROM user_swmm_pumps WHERE pump_name = ?;", (pump,)).fetchone()
                    self.lyrs.show_feat_rubber(self.pumps_lyr.id(), fid[0], QColor(Qt.yellow))
                    feat = next(self.pumps_lyr.getFeatures(QgsFeatureRequest(fid[0])))
                    x, y = feat.geometry().centroid().asPoint()
                    self.lyrs.zoom_to_all()
                    center_canvas(self.iface, x, y)
                    zoom(self.iface, 0.45)
                else:
                    self.uc.bar_warn("WARNING 251121.1139: pump '" + str(pump) + "' not found.")
                    self.lyrs.clear_rubber()
        except ValueError:
            self.uc.bar_warn("WARNING 251121.1134: pump '" + str(pump) + "' is not valid.")
            self.lyrs.clear_rubber()
            pass

    def zoom_in_pump(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        conduit = self.pump_name_cbo.currentText()
        fid = self.gutils.execute("SELECT fid FROM user_swmm_pumps WHERE pump_name = ?;", (conduit,)).fetchone()
        self.lyrs.show_feat_rubber(self.pumps_lyr.id(), fid[0], QColor(Qt.yellow))
        feat = next(self.pumps_lyr.getFeatures(QgsFeatureRequest(fid[0])))
        x, y = feat.geometry().centroid().asPoint()
        center_canvas(self.iface, x, y)
        zoom(self.iface, 0.4)
        QApplication.restoreOverrideCursor()

    def zoom_out_pump(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        conduit = self.pump_name_cbo.currentText()
        fid = self.gutils.execute("SELECT fid FROM user_swmm_pumps WHERE pump_name = ?;", (conduit,)).fetchone()
        self.lyrs.show_feat_rubber(self.pumps_lyr.id(), fid[0], QColor(Qt.yellow))
        feat = next(self.pumps_lyr.getFeatures(QgsFeatureRequest(fid[0])))
        x, y = feat.geometry().centroid().asPoint()
        center_canvas(self.iface, x, y)
        zoom(self.iface, -0.4)
        QApplication.restoreOverrideCursor()

    def save_pumps(self):
        """
        Save changes of user_swmm_pumps layer.
        """
        # self.save_attrs()
        update_qry = """
                        UPDATE user_swmm_pumps
                        SET
                           pump_name  = ?,
                           pump_inlet  = ?, 
                           pump_outlet  = ?,
                           pump_curve  = ?,
                           pump_init_status  = ?,
                           pump_startup_depth  = ?,
                           pump_shutoff_depth  = ?                           
                        WHERE fid = ?;"""

        for row in range(0, self.pumps_tblw.rowCount()):
            item = QTableWidgetItem()
            # fid = row + 1
            fid = self.pump_name_cbo.itemData(row)

            item = self.pumps_tblw.item(row, 0)
            if item is not None:
                pump_name = str(item.text())

            item = self.pumps_tblw.item(row, 1)
            if item is not None:
                pump_inlet = str(item.text())

            item = self.pumps_tblw.item(row, 2)
            if item is not None:
                pump_outlet = str(item.text())

            item = self.pumps_tblw.item(row, 3)
            if item is not None:
                pump_curve = str(item.text())

            item = self.pumps_tblw.item(row, 4)
            if item is not None:
                status = str(item.text())
                pump_init_status = status if status in ["ON", "OFF"] else "OFF"

            item = self.pumps_tblw.item(row, 5)
            if item is not None:
                pump_startup_depth = str(item.text())

            item = self.pumps_tblw.item(row, 6)
            if item is not None:
                pump_shutoff_depth = str(item.text())

            self.gutils.execute(
                update_qry,
                (
                    pump_name ,
                    pump_inlet, 
                    pump_outlet,
                    pump_curve,
                    pump_init_status,
                    pump_startup_depth,
                    pump_shutoff_depth,  
                    fid,
                ),
            )
