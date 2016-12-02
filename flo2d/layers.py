# -*- coding: utf-8 -*-

# FLO-2D Preprocessor tools for QGIS
# Copyright © 2016 Lutra Consulting for FLO-2D

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version

import os
from collections import OrderedDict

from PyQt4.QtCore import QObject
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QColor
from qgis.core import (
    QgsProject,
    QgsMapLayerRegistry,
    QgsFeatureRequest,
    QgsVectorLayer,
    QgsRectangle,
    QgsLayerTreeGroup
)

from qgis.gui import QgsRubberBand

from utils import is_number, get_file_path
from errors import Flo2dLayerInvalid, Flo2dNotString, Flo2dLayerNotFound, Flo2dError
from user_communication import UserCommunication


class Layers(QObject):
    """
    Class for managing project layers: load, add to layers tree
    """

    def __init__(self, iface):
        super(Layers, self).__init__()
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.root = QgsProject.instance().layerTreeRoot()
        self.rb = None
        self.uc = UserCommunication(iface, 'FLO-2D')
        self.gutils = None
        self.lyrs_to_repaint = []
        self.data = OrderedDict([
            ('user_bc_points', {
                'name': 'Boundary Condition Points',
                'sgroup': 'User Layers',
                'styles': ['user_bc_points.qml'],
                'attrs_edit_widgets': {
                    'type': {'name': 'ValueMap',
                             'config': {u'Outflow': u'outflow', u'Inflow': u'inflow', u'Rain': u'rain'}}
                },
                'module': ['all'],
                'readonly': False
            }),
            ('user_levee_points', {
                'name': 'Levee Points',
                'sgroup': 'User Layers',
                'styles': ['user_levee_points.qml'],
                'attrs_edit_widgets': {},
                'module': ['levees'],
                'readonly': False
            }),
            ('user_centerline', {
                'name': 'River Centerline',
                'sgroup': 'User Layers',
                'styles': ['centerline.qml'],
                'attrs_edit_widgets': {},
                'module': ['chan'],
                'readonly': False
            }),
            ('user_xsections', {
                'name': 'Cross-sections',
                'sgroup': 'User Layers',
                'styles': ['user_xs.qml'],
                'attrs_edit_widgets': {},
                'module': ['chan'],
                'readonly': False,
                'attrs_defaults': {'type': "'R'"} # use also double quotes for strings: "'R'"
            }),
            ('user_streets', {
                'name': 'Street Lines',
                'sgroup': 'User Layers',
                'styles': ['user_line.qml'],
                'attrs_edit_widgets': {},
                'module': ['streets'],
                'readonly': False
            }),
            ('user_bc_lines', {
                'name': 'Boundary Condition Lines',
                'sgroup': 'User Layers',
                'styles': ['user_bc_lines.qml'],
                'attrs_edit_widgets': {
                    'type': {'name': 'ValueMap',
                             'config': {u'Outflow': u'outflow', u'Inflow': u'inflow', u'Rain': u'rain'}}
                },
                'module': ['all'],
                'readonly': False
            }),
            ('user_levee_lines', {
                'name': 'Levee Lines',
                'sgroup': 'User Layers',
                'styles': ['user_levee_lines.qml'],
                'attrs_edit_widgets': {},
                'module': ['levees'],
                'readonly': False
            }),
            ('user_bc_polygons', {
                'name': 'Boundary Condition Polygons',
                'sgroup': 'User Layers',
                'styles': ['user_bc_polygons.qml'],
                'attrs_edit_widgets': {
                    'type': {'name': 'ValueMap',
                             'config': {u'Outflow': u'outflow', u'Inflow': u'inflow', u'Rain': u'rain'}}
                },
                'module': ['all'],
                'readonly': False
            }),
            ('user_levee_polygons', {
                'name': 'Levee Polygons',
                'sgroup': 'User Layers',
                'styles': ['user_levee_polygons.qml'],
                'attrs_edit_widgets': {},
                'module': ['levees'],
                'readonly': False
            }),
            ('user_model_boundary', {
                'name': 'Computational Domain',
                'sgroup': 'User Layers',
                'styles': ['model_boundary.qml'],
                'attrs_edit_widgets': {},
                'module': ['all'],
                'readonly': False
            }),
            ('user_1d_domain', {
                'name': '1D Domain',
                'sgroup': 'User Layers',
                'styles': ['1d_domain.qml'],
                'attrs_edit_widgets': {},
                'module': ['all'],
                'readonly': False
            }),
            ('user_roughness', {
                'name': 'Roughness',
                'sgroup': 'User Layers',
                'styles': ['user_roughness.qml'],
                'attrs_edit_widgets': {},
                'module': ['all'],
                'readonly': False
            }),
            ('user_elevation_polygons', {
                'name': 'Grid Elevation',
                'sgroup': 'User Layers',
                'styles': ['user_elevation_polygons.qml'],
                'attrs_edit_widgets': {},
                'module': ['all'],
                'readonly': False
            }),
            ('blocked_areas', {
                'name': 'Blocked areas',
                'sgroup': 'User Layers',
                'styles': ['blocked_areas.qml'],
                'attrs_edit_widgets': {
                    'calc_arf': {'name': 'CheckBox', 'config': {u'CheckedState': 1, u'UncheckedState': 0}},
                    'calc_wrf': {'name': 'CheckBox', 'config': {u'CheckedState': 1, u'UncheckedState': 0}}
                },
                'module': ['redfac'],
                'readonly': False,
                'attrs_defaults': {'calc_arf': '1', 'calc_wrf': '1'}  #
            }),
            ('mult_areas', {
                'name': 'Multiple Channel Areas',
                'sgroup': 'User Layers',
                'styles': ['mult_areas.qml'],
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('rain_arf_areas', {
                'name': 'Rain ARF Areas',
                'sgroup': 'User Layers',
                'styles': ['rain_arf_areas.qml'],
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('tolspatial', {
                'name': 'Tolerance Areas',
                'sgroup': 'User Layers',
                'styles': ['tolspatial.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),

            ('breach', {
                'name': 'Breach Locations',
                'sgroup': 'Schematic Layers',
                'styles': ['breach.qml'],
                'attrs_edit_widgets': {},
                'module': ['breach'],
                'readonly': False
            }),
            ('levee_data', {
                'name': 'Levees',
                'sgroup': 'Schematic Layers',
                'styles': ['levee.qml'],
                'attrs_edit_widgets': {},
                'module': ['levees'],
                'readonly': True
            }),
            ('struct', {
                'name': 'Structures',
                'sgroup': 'Schematic Layers',
                'styles': ['struc.qml'],
                'attrs_edit_widgets': {},
                'module': ['struct'],
                'readonly': True
            }),
            ('street_seg', {
                'name': 'Streets',
                'sgroup': 'Schematic Layers',
                'styles': ['street.qml'],
                'attrs_edit_widgets': {},
                'module': ['struct'],
                'readonly': True
            }),
            ('chan', {
                'name': 'Channel segments (left bank)',
                'sgroup': 'Schematic Layers',
                'styles': ['chan.qml'],
                'attrs_edit_widgets': {},
                'module': ['chan'],
                'readonly': True
            }),
            ('chan_elems', {
                'name': 'Cross sections',
                'sgroup': 'Schematic Layers',
                'styles': ['chan_elems.qml'],
                'attrs_edit_widgets': {},
                'visible': True,
                'module': ['chan'],
                'readonly': True
            }),
            ('fpxsec', {
                'name': 'Floodplain cross-sections',
                'sgroup': 'Schematic Layers',
                'styles': ['fpxsec.qml'],
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('chan_confluences', {
                'name': 'Channel confluences',
                'sgroup': 'Schematic Layers',
                'styles': ['chan_confluences.qml'],
                'attrs_edit_widgets': {
                    'type': {'name': 'ValueMap', 'config': {u'Tributary': 0, u'Main': 1}}
                },
                'readonly': True
            }),
            ('all_schem_bc', {
                'name': 'BC cells',
                'sgroup': 'Schematic Layers',
                'styles': ['all_schem_bc.qml'],
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('grid', {
                'name': 'Grid',
                'sgroup': 'Schematic Layers',
                'styles': ['grid.qml'],
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('blocked_cells', {
                'name': 'ARF_WRF',
                'sgroup': 'Schematic Layers',
                'styles': ['arfwrf.qml'],
                'attrs_edit_widgets': {},
                'readonly': True
            }),

            ('reservoirs', {
                'name': 'Reservoirs',
                'sgroup': 'Schematic Layers',
                'styles': ['reservoirs.qml'],
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('fpfroude', {
                'name': 'Froude numbers for grid elems',
                'sgroup': 'User Layers',
                'styles': ['fpfroude.qml'],
                'attrs_edit_widgets': {},
                'readonly': False
            }),

            ('sed_supply_areas', {
                'name': 'Supply Areas',
                'sgroup': 'Sediment Transport',
                'styles': ['sed_supply_areas.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('sed_group_areas', {
                'name': 'Group Areas',
                'sgroup': 'Sediment Transport',
                'styles': ['sed_group_areas.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('sed_rigid_areas', {
                'name': 'Rigid Bed Areas',
                'sgroup': 'Sediment Transport',
                'styles': ['sed_rigid_areas.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('mud_areas', {
                'name': 'Mud Areas',
                'sgroup': 'Sediment Transport',
                'styles': ['mud_areas.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('sed_groups', {
                'name': 'Sediment Groups',
                'sgroup': 'Sediment Transport Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('sed_group_cells', {
                'name': 'Group Cells',
                'sgroup': 'Sediment Transport Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': True
            }),
            ('sed_supply_cells', {
                'name': 'Supply Cells',
                'sgroup': 'Sediment Transport Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': True
            }),
            ('sed_rigid_cells', {
                'name': 'Rigid Bed Cells',
                'sgroup': 'Sediment Transport Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': True
            }),
            ('mud_cells', {
                'name': 'Mud Cells',
                'sgroup': 'Sediment Transport Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': True
            }),
            ('infil_areas_green', {
                'name': 'Areas Green Ampt',
                'sgroup': 'Infiltration layers',
                'styles': ['infil_areas.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('infil_areas_scs', {
                'name': 'Areas SCS',
                'sgroup': 'Infiltration layers',
                'styles': ['infil_areas.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('infil_areas_horton', {
                'name': 'Areas Horton',
                'sgroup': 'Infiltration layers',
                'styles': ['infil_areas.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            })
            ,
            ('infil_areas_chan', {
                'name': 'Areas for Channels',
                'sgroup': 'Infiltration layers',
                'styles': ['infil_areas.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('swmmflo', {
                'name': 'SD Inlets',
                'sgroup': 'Storm Drain',
                'styles': ['swmmflo.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('swmmoutf', {
                'name': 'SD Outlets',
                'sgroup': 'Storm Drain',
                'styles': ['swmmoutf.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('swmmflort', {
                'name': 'Rating tables',
                'sgroup': 'Storm Drain',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('swmmflort_data', {
                'name': 'Rating Tables Data',
                'sgroup': 'Storm Drain',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),

            ('tolspatial_cells', {
                'name': 'Tolerance Cells',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('wstime', {
                'name': 'Water Surface in Time',
                'sgroup': 'Calibration Data',
                'styles': ['wstime.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('wsurf', {
                'name': 'Water Surface',
                'sgroup': 'Calibration Data',
                'styles': ['wsurf.qml'],
                'attrs_edit_widgets': {},
                'visible': False,
                'readonly': False
            }),
            ('cont', {
                'name': 'Control',
                'sgroup': "Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('inflow', {
                'name': 'Inflow',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {
                    'ident': {'name': 'ValueMap', 'config': {u'Channel': u'C', u'Floodplain': u'F'}},
                    'inoutfc': {'name': 'ValueMap', 'config': {u'Inflow': 0, u'Outflow': 1}}
                },
                'readonly': False
            }),
            ('outflow', {
                'name': 'Outflow',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('inflow_cells', {
                'name': 'Inflow Cells',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('outflow_cells', {
                'name': 'Outflow Cells',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('qh_params', {
                'name': 'QH Parameters',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('qh_params_data', {
                'name': 'QH Parameters Data',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('qh_table', {
                'name': 'QH Tables',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('qh_table_data', {
                'name': 'QH Tables Data',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('inflow_time_series', {
                'name': 'Inflow Time Series',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('inflow_time_series_data', {
                'name': 'Inflow Time Series Data',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('outflow_time_series', {
                'name': 'Outflow Time Series',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('outflow_time_series_data', {
                'name': 'Outflow Time Series Data',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('rain_time_series', {
                'name': 'Rain Time Series',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('rain_time_series_data', {
                'name': 'Rain Time Series Data',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('rain', {
                'name': 'Rain',
                'sgroup': 'Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('rain_arf_cells', {
                'name': 'Rain ARF Cells',
                'sgroup': "Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('noexchange_chan_elems', {
                'name': 'No-exchange Channel Elements',
                'sgroup': "Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('fpxsec_cells', {
                'name': 'Floodplain cross-sections cells',
                'sgroup': "Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('fpfroude_cells', {
                'name': 'Froude numbers for grid elems',
                'sgroup': "Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('evapor', {
                'name': 'Evaporation',
                'sgroup': 'Evaporation Tables',
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('evapor_hourly', {
                'name': 'Hourly data',
                'sgroup': "Evaporation Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('evapor_monthly', {
                'name': 'Monthly data',
                'sgroup': "Evaporation Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': False
            }),
            ('infil_cells_green', {
                'name': 'Cells Green Ampt',
                'sgroup': "Infiltration Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('infil_cells_scs', {
                'name': 'Cells SCS',
                'sgroup': "Infiltration Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('infil_cells_horton', {
                'name': 'Cells Horton',
                'sgroup': "Infiltration Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            }),
            ('infil_chan_elems', {
                'name': 'Channel elements',
                'sgroup': "Infiltration Tables",
                'styles': None,
                'attrs_edit_widgets': {},
                'readonly': True
            })
        ])
        # set QGIS layer (qlyr) to None for each table
        for lyr in self.data:
            self.data[lyr]['qlyr'] = None

    def load_layer(self, table, uri, group, name, subgroup=None, style=None, visible=True, readonly=False, provider='ogr'):
        # check if the layer is already loaded
        lyr_exists = self.layer_exists_in_group(uri, group)
        if not lyr_exists:
            vlayer = QgsVectorLayer(uri, name, provider)
            if not vlayer.isValid():
                msg = 'Unable to load layer {}'.format(name)
                raise Flo2dLayerInvalid(msg)
            QgsMapLayerRegistry.instance().addMapLayer(vlayer, False)
            # get target tree group
            if subgroup:
                grp = self.get_subgroup(group, subgroup)
                if not subgroup == 'User Layers' and not subgroup == 'Schematic Layers':
                    grp.setExpanded(False)
                else:
                    pass
            else:
                grp = self.get_group(group)
            # add layer to the tree group
            tree_lyr = grp.addLayer(vlayer)
        else:
            tree_lyr = self.get_layer_tree_item(lyr_exists)
            self.update_layer_extents(tree_lyr.layer())
        self.data[table]['qlyr'] = tree_lyr.layer()

        # set visibility
        if visible:
            vis = Qt.Checked
        else:
            vis = Qt.Unchecked
        tree_lyr.setVisible(vis)
        tree_lyr.setExpanded(False)

        # set style
        if style:
            style_path = get_file_path("styles", style)
            if os.path.isfile(style_path):
                err_msg, res = self.data[table]['qlyr'].loadNamedStyle(style_path)
                if not res:
                    msg = 'Unable to load style for layer {}.\n{}'.format(name, err_msg)
                    raise Flo2dError(msg)
            else:
                raise Flo2dError('Unable to load style file {}'.format(style_path))

        # check if the layer should be 'readonly'
        if readonly:
            try:
                # check if the signal is already connected
                self.data[table]['qlyr'].beforeEditingStarted.disconnect(self.warn_readonly)
            except TypeError:
                pass
            self.data[table]['qlyr'].beforeEditingStarted.connect(self.warn_readonly)
        else:
            pass

        return self.data[table]['qlyr'].id()

    def warn_readonly(self):
        self.uc.bar_warn('Warning:\nAll changes to this layer can be overwriten by changes in the user layer.')

    def enter_edit_mode(self, table_name, default_attr_exp=None):
        if not self.group:
            msg = 'Connect to a GeoPackage!'
            self.uc.bar_warn(msg)
            return None
        try:
            lyr = self.data[table_name]['qlyr']
            self.iface.setActiveLayer(lyr)
            if not default_attr_exp:
                for idx in lyr.pendingAllAttributesList():
                    lyr.setDefaultValueExpression(idx, '')
            else:
                for attr, exp in default_attr_exp.iteritems():
                    idx = lyr.fieldNameIndex(attr)
                    lyr.setDefaultValueExpression(idx, exp)
            lyr.startEditing()
            self.iface.actionAddFeature().trigger()
            return True
        except:
            msg = 'Could\'n start edit mode for table {}. Is it loaded into QGIS project?'.format(table_name)
            self.uc.bar_warn(msg)
            return None

    def any_lyr_in_edit(self, *table_name_list):
        """Return True if any layer from the table list is in edit mode"""
        in_edit_mode = False
        if not table_name_list:
            return None
        for t in table_name_list:
            if self.data[t]['qlyr'].isEditable():
                in_edit_mode = True
        return in_edit_mode

    def save_lyrs_edits(self, *table_name_list):
        """Save changes to each layer if it is in edit mode"""
        in_edit_mode = False
        if not table_name_list:
            return None
        for t in table_name_list:
            if self.data[t]['qlyr'].isEditable():
                in_edit_mode = True
                try:
                    lyr = self.data[t]['qlyr']
                    lyr.commitChanges()
                except:
                    msg = 'Could\'n save changes for table {}.'.format(t)
                    self.uc.bar_warn(msg)
        return in_edit_mode

    def rollback_lyrs_edits(self, *table_name_list):
        """Save changes to each layer if it is in edit mode"""
        in_edit_mode = False
        if not table_name_list:
            return None
        for t in table_name_list:
            if self.data[t]['qlyr'].isEditable():
                in_edit_mode = True
                try:
                    lyr = self.data[t]['qlyr']
                    lyr.rollBack()
                except:
                    msg = 'Could\'n rollback changes for table {}.'.format(t)
                    self.uc.bar_warn(msg)
        return in_edit_mode

    def get_layer_tree_item(self, layer_id):
        if layer_id:
            layeritem = self.root.findLayer(layer_id)
            if not layeritem:
                msg = 'Layer {} doesn\'t exist in the layers tree.'.format(layer_id)
                raise Flo2dLayerNotFound(msg)
            return layeritem
        else:
            raise Flo2dLayerNotFound('Layer id not specified')

    def get_layer_by_name(self, name, group=None):
        if group:
            gr = self.get_group(group, create=False)
        else:
            gr = self.root
        layeritem = None
        if gr and name:
            layers = QgsMapLayerRegistry.instance().mapLayersByName(name)

            for layer in layers:
                layeritem = gr.findLayer(layer.id())
                if not layeritem:
                    continue
                else:
                    return layeritem
        else:
            pass
        return layeritem

    def list_group_vlayers(self, group=None, only_visible=True, skip_views=False):
        if not group:
            grp = self.root
        else:
            grp = self.get_group(group, create=False)
        views_list = []
        l = []
        if grp:
            for lyr in grp.findLayers():
                if lyr.layer().type() == 0 and lyr.layer().geometryType() < 3:
                    if skip_views and lyr.layer().name() in views_list:
                        continue
                    else:
                        if only_visible and not lyr.isVisible():
                            continue
                        else:
                            l.append(lyr.layer())
        else:
            pass
        return l

    def list_group_rlayers(self, group=None):
        if not group:
            grp = self.root
        else:
            grp = self.get_group(group, create=False)
        l = []
        if grp:
            for lyr in grp.findLayers():
                if lyr.layer().type() == 1:
                    l.append(lyr.layer())
        else:
            pass
        return l

    def repaint_layers(self):
        for lyr in self.lyrs_to_repaint:
            lyr.triggerRepaint()
        self.lyrs_to_repaint = []

    def connect_lyrs_reload(self, layer1, layer2):
        """Reload layer1 and update its extent when layer2 modifications are saved"""
        layer2.editingStopped.connect(layer1.reload)

    def new_group(self, name):
        if isinstance(name, (str, unicode)):
            self.root.addGroup(name)
        else:
            raise Flo2dNotString('{} is not a string or unicode'.format(repr(name)))

    def new_subgroup(self, group, subgroup):
        grp = self.root.findGroup(group)
        grp.addGroup(subgroup)

    def remove_group_by_name(self, name):
        grp = self.root.findGroup(name)
        if grp:
            self.root.removeChildNode(grp)

    def get_group(self, name, create=True):
        grp = self.root.findGroup(name)
        if not grp and create:
            grp = self.root.addGroup(name)
        return grp

    def get_subgroup(self, group, subgroup, create=True):
        grp = self.get_group(group, create=create)
        subgrp = grp.findGroup(subgroup)
        if not subgrp and create:
            subgrp = grp.addGroup(subgroup)
        return subgrp

    def get_flo2d_groups(self):
        all_groups = self.iface.legendInterface().groups()
        f2d_groups = []
        for g in all_groups:
            if g.startswith('FLO-2D_'):
                tg = self.get_group(g, create=False)
                f2d_groups.append(tg)
        return f2d_groups

    def get_group_subgroups(self, group_name):
        children = self.get_group(group_name, create=False).children()
        sgroups = []
        for ch in children:
            if type(ch) == QgsLayerTreeGroup:
                sgroups.append(ch)
        return sgroups

    def expand_all_flo2d_groups(self):
        f2d_groups = self.get_flo2d_groups()
        for gr in f2d_groups:
            gr.setExpanded(True)

    def collapse_all_flo2d_groups(self):
        f2d_groups = self.get_flo2d_groups()
        for gr in f2d_groups:
            gr.setExpanded(False)

    def expand_flo2d_group(self, group_name):
        group = self.get_group(group_name, create=False)
        if group:
            group.setExpanded(True)
            first_lyr = self.get_layer_by_name('Computational Domain', group=group_name).layer()
            if first_lyr:
                self.iface.legendInterface().setCurrentLayer(first_lyr)
        else:
            pass

    def collapse_all_flo2d_subgroups(self, group):
        for sgr in self.get_group_subgroups(group):
            sgr.setExpanded(False)

    def collapse_flo2d_subgroup(self, group_name, subgroup_name):
        sg = self.get_subgroup(group_name, subgroup_name, create=False)
        if sg:
            sg.setExpanded(False)

    def expand_flo2d_subgroup(self, group_name, subgroup_name):
        sg = self.get_subgroup(group_name, subgroup_name, create=False)
        if sg:
            sg.setExpanded(True)

    def collapse_group_layers(self, group_name):
        group = self.get_group(group_name, create=False)

    def clear_legend_selection(self):
        sel_lyrs = self.iface.legendInterface().selectedLayers()
        if sel_lyrs:
            self.iface.legendInterface().setCurrentLayer(sel_lyrs[0])

    def layer_exists_in_group(self, uri, group=None):
        grp = self.root.findGroup(group) if group is not None else self.root
        if grp:
            for lyr in grp.findLayers():
                if lyr.layer().dataProvider().dataSourceUri() == uri:
                    return lyr.layer().id()
        return None

    @staticmethod
    def get_layer_table_name(layer):
        t = layer.dataProvider().dataSourceUri().split('=')[1]
        if t:
            return t
        else:
            return None

    def update_layer_extents(self, layer):
        # check if it is a spatial table
        t = self.get_layer_table_name(layer)
        sql = '''SELECT table_name FROM gpkg_contents WHERE table_name=? AND data_type = 'features'; '''
        try:
            is_spatial = self.gutils.execute(sql, (t,)).fetchone()[0]
        except:
            return
        if is_spatial:
            self.gutils.update_layer_extents(t)
            # why, oh why this is not working.... ?
            # layer.reload()
            # layer.updateExtents()
            sql = '''SELECT min_x, min_y, max_x, max_y FROM gpkg_contents WHERE table_name=?;'''
            min_x, min_y, max_x, max_y = self.gutils.execute(sql, (t,)).fetchone()
            try:
                # works if min & max not null
                layer.setExtent(QgsRectangle(min_x, min_y, max_x, max_y))
            except:
                return
        else:
            pass

    @staticmethod
    def remove_layer_by_name(name):
        layers = QgsMapLayerRegistry.instance().mapLayersByName(name)
        for layer in layers:
            QgsMapLayerRegistry.instance().removeMapLayer(layer.id())

    @staticmethod
    def remove_layer(layer_id):
        # do nothing if layer id does not exists
        QgsMapLayerRegistry.instance().removeMapLayer(layer_id)

    @staticmethod
    def is_str(name):
        if isinstance(name, (str, unicode)):
            return True
        else:
            msg = '{} is of type {}, not a string or unicode'.format(repr(name), type(name))
            raise Flo2dNotString(msg)

    def load_all_layers(self, gutils):
        self.gutils = gutils
        self.clear_legend_selection()
        group = 'FLO-2D_{}'.format(os.path.basename(self.gutils.path).replace('.gpkg', ''))
        self.collapse_all_flo2d_groups()
        self.group = group
        for lyr in self.data:
            data = self.data[lyr]
            if data['styles']:
                lstyle = data['styles'][0]
            else:
                lstyle = None
            uri = self.gutils.path + '|layername={}'.format(lyr)
            try:
                lyr_is_on = data['visible']
            except:
                lyr_is_on = True
            lyr_id = self.load_layer(
                lyr,
                uri,
                group,
                data['name'],
                style=lstyle,
                subgroup=data['sgroup'],
                visible=lyr_is_on,
                readonly=data['readonly']
            )
            l = self.get_layer_tree_item(lyr_id).layer()
            if lyr == 'blocked_cells':
                self.update_style_blocked(lyr_id)
            if data['attrs_edit_widgets']:
                c = l.editFormConfig()
                for attr, widget_data in data['attrs_edit_widgets'].iteritems():
                    attr_idx = l.fieldNameIndex(attr)
                    c.setWidgetType(attr_idx, widget_data['name'])
                    c.setWidgetConfig(attr_idx, widget_data['config'])
            else:
                pass # no attributes edit widgets config
            # set attributes default value, if any
            try:
                dvs = data['attrs_defaults']
            except:
                dvs = None
            if dvs:
                for attr, val in dvs.iteritems():
                    idx = l.fieldNameIndex(attr)
                    l.setDefaultValueExpression(idx, val)
            else:
                pass
        self.expand_flo2d_group(group)
        self.collapse_all_flo2d_subgroups(group)
        self.expand_flo2d_subgroup(group, 'User Layers')

    def update_style_blocked(self, lyr_id):
        cst = self.gutils.get_cont_par('CELLSIZE')
        if is_number(cst) and not cst == '':
            cs = float(cst)
        else:
            return
        # update geometry gen definitions for WRFs
        s = cs * 0.35
        dir_lines = {
            1: (-s/2.414, s, s/2.414, s),
            2: (s, s/2.414, s, -s/2.414),
            3: (s/2.414, -s, -s/2.414, -s),
            4: (-s, -s/2.414, -s, s/2.414),
            5: (s/2.414, s, s, s/2.414),
            6: (s, -s/2.414, s/2.414, -s),
            7: (-s/2.414, -s, -s, -s/2.414),
            8: (-s, s/2.414, -s/2.414, s)
        }
        lyr = self.get_layer_tree_item(lyr_id).layer()
        sym = lyr.rendererV2().symbol()
        for nr in range(1, sym.symbolLayerCount()):
            exp = 'make_line(translate(centroid($geometry), {}, {}), translate(centroid($geometry), {}, {}))'
            sym.symbolLayer(nr).setGeometryExpression(exp.format(*dir_lines[nr]))
        # ARF
        exp_arf = '''make_polygon( make_line(translate( $geometry , -{0}, {0}),
                                             translate($geometry, {0}, {0}),
                                             translate($geometry, {0}, -{0}),
                                             translate($geometry, -{0}, -{0}),
                                             translate($geometry, -{0}, {0})))'''.format(cs * 0.5)
        sym.symbolLayer(0).setGeometryExpression(exp_arf)

    def show_feat_rubber(self, lyr_id, fid, color=QColor(255, 0, 0)):
        lyr = self.get_layer_tree_item(lyr_id).layer()
        gt = lyr.geometryType()
        self.clear_rubber()
        self.rb = QgsRubberBand(self.canvas, gt)
        color.setAlpha(255)
        self.rb.setColor(color)
        self.rb.setFillColor(color)
        fill_color = color
        if gt == 2:
            fill_color.setAlpha(100)
            self.rb.setFillColor(fill_color)
        self.rb.setWidth(3)
        feat = lyr.getFeatures(QgsFeatureRequest(fid)).next()
        self.rb.setToGeometry(feat.geometry(), lyr)

    def clear_rubber(self):
        if self.rb:
            for i in range(3):
                self.rb.reset(i)

    def zoom_to_all(self):
        if self.gutils.is_table_empty('grid'):
            return
        else:
            self.gutils.update_layer_extents('grid')
            grid = self.get_layer_by_name('Grid', self.group)
            extent = grid.layer().extent()
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()

    def save_edits_and_proceed(self, layer_name):
        """If the layer is in edit mode, ask users for saving changes and proceeding."""
        l = self.get_layer_by_name(layer_name, group=self.group).layer()
        if l.isEditable():
            # ask user for saving changes
            q = '{} layer is in edit mode. Save changes and proceed?'.format(layer_name)
            if self.uc.question(q):
                l.commitChanges()
                return True
            else:
                self.uc.bar_info('Action cancelled', dur=3)
                return False
        else:
            return True
