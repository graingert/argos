
import logging

from libargos.utils.cls import StringType, check_class, check_is_a_string

logger = logging.getLogger(__name__)

class BaseTreeItem(object):
    """ Base class for storing item data in a tree form. Each tree item represents a row
        in the BaseTreeModel (QAbstractItemModel). 
        
        The tree items have no notion of which field is stored in which column. This is implemented
        in BaseTreeModel._itemValueForColumn
    """
    def __init__(self, nodeName):
        """ Constructor
        
            :param nodeName: short name describing this node. Is used to construct the nodePath.
                Currently we don't check for uniqueness in the children but this may change.
        """
        check_class(nodeName, StringType, allow_none=False)
        assert nodeName, "Node name may not be empty"
        self._nodeName = str(nodeName)
        self._parentItem = None
        self._childItems = [] # the fetched children
        self._nodePath = self._constructNodePath()        

    def finalize(self):
        """ Can be used to cleanup resources. Should be called explicitly.
            Finalizes its children before closing itself
        """
        for child in self.childItems:
            child.finalize()
    
    def __str__(self):
        return "<{}: {}>".format(type(self).__name__, self.nodePath)
        
    def __repr__(self):
        return ("<{}: {!r}, children:[{}]>".
                format(type(self).__name__, self.nodePath, 
                       ', '.join([repr(child) for child in self.childItems])))
    
    @property
    def decoration(self):
        """ An optional decoration (e.g. icon). 
            The default implementation returns None (no decoration).
        """
        return None
    
    @property
    def nodeName(self):
        """ The node name. Is used to construct the nodePath"""
        return self._nodeName

    @nodeName.setter
    def nodeName(self, nodeName):
        """ The node name. Is used to construct the nodePath"""
        assert '/' not in nodeName, "nodeName may not contain slashes"
        self._nodeName = nodeName
        self._recursiveSetNodePath(self._constructNodePath())

    def _constructNodePath(self):
        """ Recursively prepends the parents nodeName to the path until the root node is reached."""
        if self.parentItem is None:
            return '' # invisible root node; is not included in the path
        else:
            return self.parentItem.nodePath + '/' + self.nodeName
    
    @property
    def nodePath(self):
        """ The sequence of nodeNames from the root to this node. Separated by slashes."""
        return self._nodePath

    def _recursiveSetNodePath(self, nodePath):
        """ Sets the nodePath property and updates it for all children.
        """
        self._nodePath = nodePath
        for childItem in self.childItems:
            childItem._recursiveSetNodePath(nodePath + '/' + childItem.nodeName)

    @property
    def parentItem(self):
        """ The parent item """
        return self._parentItem
    
    @parentItem.setter
    def parentItem(self, value):
        """ The parent item """
        self._parentItem = value
        self._recursiveSetNodePath(self._constructNodePath())
    
    @property
    def childItems(self):
        """ List of child items """
        #logger.debug("childItems {!r}".format(self))
        return self._childItems

    def hasChildren(self):
        """ Returns True if the item has children 
        """
        return len(self.childItems) > 0

    def nChildren(self): # TODO: numChildren
        """ Returns the number of children 
        """
        return len(self.childItems)

    def child(self, row):
        """ Gets the child given its row number 
        """
        return self.childItems[row]


    def childByNodeName(self, nodeName):
        """ Gets first (direct) child that has the nodeName.
        """
        assert '/' not in nodeName, "nodeName can not contain slashes"
        for child in self.childItems:
            if child.nodeName == nodeName:
                return child

        raise IndexError("No child item found having nodeName: {}".format(nodeName))


    def findByNodePath(self, nodePath):
        """ Recursively searches for the child having the nodePath. Starts at self.
        """
        def _auxGetByPath(parts, item):
            "Aux function that does the actual recursive search"
            #logger.debug("_auxGetByPath item={}, parts={}".format(item, parts))
            
            if len(parts) == 0:
                return item
        
            head, tail = parts[0], parts[1:]
            if head == '':
                # Two consecutive slashes. Just go one level deeper.
                return _auxGetByPath(tail, item)
            else:
                childItem = item.childByNodeName(head)
                return _auxGetByPath(tail, childItem)        
                
        # The actual body of findByNodePath starts here
        
        check_is_a_string(nodePath)
        assert not nodePath.startswith('/'), "nodePath may not start with a slash"
        
        if not nodePath:
            raise IndexError("Item not found: {!r}".format(nodePath))
        
        return _auxGetByPath(nodePath.split('/'), self)
    
            

    def childNumber(self):
        """ Gets the index (nr) of this node in its parent's list of children
        """
        if self.parentItem != None:
            return self.parentItem.childItems.index(self)
        return 0


    def insertChild(self, childItem, position=None):
        """ Inserts a child item to the current item.
            The childItem may not yet have a parent (it will be set by this function).
            
            IMPORTANT: this does not let the model know that items have been added. 
            Use BaseTreeModel.insertItem instead.
            
            Returns childItem so that calls may be chained.
        """ 
        if position is None:
            position = self.nChildren()
            
        assert 0 <= position <= len(self.childItems), \
            "position should be 0 < {} <= {}".format(position, len(self.childItems))
            
        assert childItem.parentItem is None, "childItem already has a parent: {}".format(childItem)
            
        childItem.parentItem = self    
        self.childItems.insert(position, childItem)
        
        return childItem


    def removeChild(self, position):
        """ Removes the child at the position 'position'
            Calls the child item finalize to close its resources before removing it.
        """
        assert 0 <= position <= len(self.childItems), \
            "position should be 0 < {} <= {}".format(position, len(self.childItems))

        self.childItems[position].finalize()
        self.childItems.pop(position)


    def removeAllChildren(self):
        """ Removes the all children of this node.
            Calls the child items finalize to close their resources before removing them.
        """
        for childItem in self.childItems:
            childItem.finalize()
        self._childItems = []


    
class AbstractLazyLoadTreeItem(BaseTreeItem):
    """ Abstract base class for a tree item that can do lazy loading of children.
        Descendants should override the _fetchAllChildren
    """
    def __init__(self, nodeName=''):
        """ Constructor
        """
        super(AbstractLazyLoadTreeItem, self).__init__(nodeName=nodeName)
        self._childrenFetched = False
        
    def hasChildren(self):
        """ Returns True if the item has (fetched or unfetched) children 
        """
        return True
        #return not self._childrenFetched or len(self.childItems) > 0 TODO: use this? 
        
    def canFetchChildren(self):
        return not self._childrenFetched
        
    def fetchChildren(self):
        assert not self._childrenFetched, "canFetchChildren must be True"
        childItems = self._fetchAllChildren()
        self._childrenFetched = True
        return childItems
    
    def _fetchAllChildren(self):
        """ The function that actually fetches the children.
        
            The result must be a list of RepoTreeItems. Their parents must be None, 
            as that attribute will be set by BaseTreeitem.insertItem()
         
            :rtype: list of BaseRti objects
        """ 
        raise NotImplementedError
    
    def removeAllChildren(self):
        """ Removes all children """
        super(AbstractLazyLoadTreeItem, self).removeAllChildren()
        self._childrenFetched = False
