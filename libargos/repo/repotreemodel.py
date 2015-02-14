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

""" Data repository functionality
"""
import logging
from libargos.qt import QtCore
from libargos.qt.editabletreemodel import BaseTreeModel
from libargos.info import DEBUGGING
from libargos.utils.cls import type_name
from libargos.repo.filesytemrti import detectRtiFromFileName


logger = logging.getLogger(__name__)

class RepoTreeModel(BaseTreeModel):
    """ The main entry point of all the data
    
        Maintains a list of open files and offers a QAbstractItemModel for read-only access of
        the data with QTreeViews.
    """
    HEADERS = ["name", "shape", "is open", "tree item", "type", "elem type", "file name"]
    (COL_NODE_NAME, COL_SHAPE, COL_IS_OPEN, 
     COL_RTI_TYPE, COL_TYPE, COL_ELEM_TYPE, 
     COL_FILE_NAME) = range(len(HEADERS))
    
    def __init__(self, parent=None):
        """ Constructor
        """
        super(RepoTreeModel, self).__init__(parent=parent)
        self._isEditable = False
        
    
    def _itemValueForColumn(self, treeItem, column):
        """ Returns the value of the item given the column number.
            :rtype: string
        """
        if column == self.COL_NODE_NAME:
            return treeItem.nodeName
        elif column == self.COL_SHAPE:
            return " x ".join(str(elem) for elem in treeItem.arrayShape)
        elif column == self.COL_IS_OPEN:
            return str(treeItem.isOpen)
        elif column == self.COL_RTI_TYPE:
            return type_name(treeItem)
        elif column == self.COL_TYPE:
            return treeItem.typeName
        elif column == self.COL_ELEM_TYPE:
            return treeItem.elementTypeName
        elif column == self.COL_FILE_NAME:
            return treeItem.fileName if hasattr(treeItem, 'fileName') else ''
        else:
            raise ValueError("Invalid column: {}".format(column))
            

    def _setItemValueForColumn(self, treeItem, column, value):
        """ Sets the value in the item, of the item given the column number.
            It returns True for success, otherwise False.
        """
        assert False, "not operational"
        if column == 1:
            treeItem.value = value
            return True
        else:
            if DEBUGGING:
                raise IndexError("Invalid column number: {}".format(column))
            return False
        
        
    def canFetchMore(self, parentIndex):
        """ Returns true if there is more data available for parent; otherwise returns false.
        """
        parentItem = self.getItem(parentIndex)
        if not parentItem:
            return False
        
        return parentItem.canFetchChildren()
        
        
    def fetchMore(self, parentIndex):
        """ Fetches any available data for the items with the parent specified by the parent index.
        """
        parentItem = self.getItem(parentIndex)
        if not parentItem:
            return
        
        if not parentItem.canFetchChildren():
            return
        
        # TODO: implement InsertItems to optimize?
        for childItem in parentItem.fetchChildren(): 
            self.insertItem(childItem, parentIndex=parentIndex)
    
        # Check that Rti implementation correctly sets _canFetchChildren    
        assert not parentItem.canFetchChildren(), \
            "not all children fetched: {}".format(parentItem)
    

    def findFileRtiIndex(self, childIndex):
        """ Traverses the tree upwards from the item at childIndex until the tree 
            item is found that represents the file the item at childIndex 
        """        
        parentIndex = childIndex.parent()
        if not parentIndex.isValid():
            return childIndex
        else:
            parentItem = self.getItem(parentIndex)
            childItem = self.getItem(childIndex)
            if parentItem.fileName == childItem.fileName:
                return self.findFileRtiIndex(parentIndex)
            else:
                return childIndex

        
    def reloadFileAtIndex(self, itemIndex):
        """ Finds the repo tree item that holds the file of the current item and reloads it.
            Reloading is done by removing the repo tree item and inserting a new one.
        """        
        fileRtiParentIndex = itemIndex.parent()
        fileRti = self.getItem(itemIndex)
        fileName = fileRti.fileName
        rtiClass = type(fileRti)
        position = fileRti.childNumber()
        
        # Delete old RTI and Insert a new one instead.
        self.deleteItemByIndex(itemIndex) # this will close the items resources.
        return self.loadFile(fileName, rtiClass, position=position, parentIndex=fileRtiParentIndex)


    def loadFile(self, fileName, rtiClass=None, 
                 position=None, parentIndex=QtCore.QModelIndex()):
        """ Loads a file in the repository as a repo tree item of class rtiClass. 
            Autodetects the RTI type if rtiClass is None.
            If position is None the child will be appended as the last child of the parent.
            Returns the index of the newly inserted RTI
        """
        logger.info("Loading data from: {!r}".format(fileName))
        if rtiClass is None:
            rtiClass = detectRtiFromFileName(fileName)
            
        repoTreeItem = rtiClass.createFromFileName(fileName)
        assert repoTreeItem.parentItem is None, "repoTreeItem {!r}".format(repoTreeItem)
        return self.insertItem(repoTreeItem, position=position, parentIndex=parentIndex)
    
    
def createGlobalRepositoryFunction():
    """ Closure to create the RepoTreeModel singleton
    """
    globRepo = RepoTreeModel()
    
    def accessGlobalRepo():
        return globRepo
    
    return accessGlobalRepo

# This is actually a function definition, not a constant
#pylint: disable=C0103

getGlobalRepository = createGlobalRepositoryFunction()
getGlobalRepository.__doc__ = "Function that returns the RepoTreeModel common to all windows"
