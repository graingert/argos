# -*- coding: utf-8 -*-

# This file is part of Argos.
# 
# Argos is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Argos is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Argos. If not, see <http://www.gnu.org/licenses/>.

""" RTI attributes inspector. 
"""
import logging

from libargos.qt import QtGui
from libargos.repo.detailpanes import DetailTablePane
from libargos.widgets.constants import COL_ELEM_TYPE_WIDTH

logger = logging.getLogger(__name__)



class AttributesPane(DetailTablePane):
    """ Shows the attributes of the selected repo tree item
    """
    _label = "Attributes"
    
    HEADERS = ["Name", "Value", "Type"]
    (COL_ATTR_NAME, COL_VALUE, COL_ELEM_TYPE) = range(len(HEADERS))
    
    def __init__(self, repoTreeView, parent=None):
        super(AttributesPane, self).__init__(repoTreeView, parent=parent)
        self.table.setWordWrap(True)
        self.table.addHeaderContextMenu(enabled = {'Name': False, 'Value': False}, 
                                        checked = {'Type': False}) 
    
        tableHeader = self.table.horizontalHeader()
        tableHeader.resizeSection(self.COL_ATTR_NAME, 125)
        tableHeader.resizeSection(self.COL_VALUE, 150)  
        tableHeader.resizeSection(self.COL_ELEM_TYPE, COL_ELEM_TYPE_WIDTH)          

        
    def _drawContents(self, currentRti=None):
        """ Draws the attributes of the currentRTI
        """
        #logger.debug("drawContents: {}".format(currentRti))
        table = self.table
        table.setUpdatesEnabled(False)
        try:
            table.clearContents()
            verticalHeader = table.verticalHeader()
            verticalHeader.setResizeMode(QtGui.QHeaderView.Fixed)

            attributes = currentRti.attributes if currentRti is not None else {}
            table.setRowCount(len(attributes))
            
            for row, (attrName, attrValue) in enumerate(sorted(attributes.items())):
                try: # a number
                    attrStr = "{:g}".format(attrValue)
                except RuntimeError:
                    # Structured types give infinite recursion if printed as string.
                    # Seems a bug: https://github.com/numpy/numpy/issues/385
                    attrStr = repr(attrValue)
                except Exception:
                    attrStr = unicode(attrValue)
                
                try: 
                    type_str = type(attrValue).__name__
                except Exception as ex:
                    logger.exception(ex)
                    type_str = "<???>"

                nameItem = QtGui.QTableWidgetItem(attrName)
                nameItem.setToolTip(attrName)
                table.setItem(row, self.COL_ATTR_NAME, nameItem)
                valItem = QtGui.QTableWidgetItem(attrStr)
                valItem.setToolTip(attrStr)
                table.setItem(row, self.COL_VALUE, valItem)
                table.setItem(row, self.COL_ELEM_TYPE, QtGui.QTableWidgetItem(type_str))
                table.resizeRowToContents(row)
    
            verticalHeader.setResizeMode(QtGui.QHeaderView.ResizeToContents)

        finally:
            table.setUpdatesEnabled(True)
        
        
        
        