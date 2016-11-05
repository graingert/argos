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

""" PyQtGraph 2D image plot
"""
from __future__ import division, print_function

import logging, math
import numpy as np
import pyqtgraph as pg

from functools import partial
from collections import OrderedDict
from libargos.info import DEBUGGING
from libargos.config.boolcti import BoolCti, BoolGroupCti
from libargos.config.choicecti import ChoiceCti
from libargos.config.groupcti import MainGroupCti
from libargos.inspector.abstract import AbstractInspector, InvalidDataError
from libargos.inspector.pgplugins.pgctis import (X_AXIS, Y_AXIS, BOTH_AXES,
                                                 defaultAutoRangeMethods, PgAxisLabelCti,
                                                 PgAxisCti, PgAxisFlipCti, PgAspectRatioCti,
                                                 PgAxisRangeCti, PgHistLutColorRangeCti, PgGridCti,
                                                 PgGradientEditorItemCti, setXYAxesAutoRangeOn,
                                                 PgPlotDataItemCti)
from libargos.inspector.pgplugins.pgplotitem import ArgosPgPlotItem
from libargos.inspector.pgplugins.pghistlutitem import HistogramLUTItem
from libargos.qt import Qt, QtCore, QtGui, QtSlot
from libargos.utils.cls import array_has_real_numbers, check_class
from libargos.utils.masks import replaceMaskedValue

logger = logging.getLogger(__name__)

ROW_TITLE,    COL_TITLE    = 0, 0  # colspan = 3
ROW_COLOR,    COL_COLOR    = 1, 0  # rowspan = 2
ROW_HOR_LINE, COL_HOR_LINE = 1, 1
ROW_IMAGE,    COL_IMAGE    = 2, 1
ROW_VER_LINE, COL_VER_LINE = 2, 2
ROW_PROBE,    COL_PROBE    = 3, 0  # colspan = 2



def calcPgImagePlot2dDataRange(pgImagePlot2d, percentage, crossPlot):
    """ Calculates the range from the inspectors' sliced array. Discards percentage of the minimum
        and percentage of the maximum values of the inspector.slicedArray

        :param pgImagePlot2d: the range methods will work on (the sliced array) of this inspector.
        :param percentage: percentage that will be discarded.
        :param crossPlot: if None, the range will be calculated from the entire sliced array,
            if "horizontal" or "vertical" the range will be calculated from the data under the
            horizontal or vertical cross hairs.
            If the cursor is outside the image, there is no valid data under the cross-hair and
            the range will be determined from the sliced array as a fall back.
    """

    if crossPlot is None:
        array = pgImagePlot2d.slicedArray.data

    elif crossPlot == 'horizontal':
        if pgImagePlot2d.crossPlotRow is not None:
            array = pgImagePlot2d.slicedArray.data[pgImagePlot2d.crossPlotRow, :]
        else:
            array = pgImagePlot2d.slicedArray.data # fall back on complete sliced array

    elif crossPlot == 'vertical':
        if pgImagePlot2d.crossPlotCol is not None:
            array = pgImagePlot2d.slicedArray.data[:, pgImagePlot2d.crossPlotCol]
        else:
            array = pgImagePlot2d.slicedArray.data # fall back on complete sliced array
    else:
        raise ValueError("crossPlot must be: None, 'horizontal' or 'vertical', got: {}"
                         .format(crossPlot))

    return np.nanpercentile(array, (percentage, 100-percentage) )


def crossPlotAutoRangeMethods(pgImagePlot2d, crossPlot, intialItems=None):
    """ Creates an ordered dict with autorange methods for an PgImagePlot2d inspector.

        :param pgImagePlot2d: the range methods will work on (the sliced array) of this inspector.
        :param crossPlot: if None, the range will be calculated from the entire sliced array,
            if "horizontal" or "vertical" the range will be calculated from the data under the
            horizontal or vertical cross hairs
        :param intialItems: will be passed on to the  OrderedDict constructor.
    """
    rangeFunctions = OrderedDict({} if intialItems is None else intialItems)

    # If crossPlot is "horizontal" or "vertical" make functions that determine the range from the
    # data at the cross hair.
    if crossPlot:
        rangeFunctions['cross all data'] = partial(calcPgImagePlot2dDataRange, pgImagePlot2d,
                                                   0.0, crossPlot)
        for percentage in [0.1, 0.2, 0.5, 1, 2, 5, 10, 20]:
            label = "cross discard {}%".format(percentage)
            rangeFunctions[label] = partial(calcPgImagePlot2dDataRange, pgImagePlot2d,
                                            percentage, crossPlot)

    # Always add functions that determine the data from the intire sliced array.
    for percentage in [0.1, 0.2, 0.5, 1, 2, 5, 10, 20]:
        rangeFunctions['image all data'] = partial(calcPgImagePlot2dDataRange, pgImagePlot2d,
                                                   0.0, None)

        label = "image discard {}%".format(percentage)
        rangeFunctions[label] = partial(calcPgImagePlot2dDataRange, pgImagePlot2d,
                                        percentage, None)
    return rangeFunctions



class PgImagePlot2dCti(MainGroupCti):
    """ Configuration tree item for a PgImagePlot2dCti inspector
    """
    def __init__(self, pgImagePlot2d, nodeName):
        """ Constructor

            Maintains a link to the target pgImagePlot2d inspector, so that changes in the
            configuration can be applied to the target by simply calling the apply method.
            Vice versa, it can connect signals to the target.
        """
        super(PgImagePlot2dCti, self).__init__(nodeName)
        check_class(pgImagePlot2d, PgImagePlot2d)
        self.pgImagePlot2d = pgImagePlot2d
        imagePlotItem = self.pgImagePlot2d.imagePlotItem
        viewBox = imagePlotItem.getViewBox()

        self.insertChild(ChoiceCti('title', 0, editable=True,
                                   configValues=["{base-name} -- {name} {slices}",
                                                 "{name} {slices}", "{path} {slices}"]))
        #### Axes ####
        self.aspectLockedCti = self.insertChild(PgAspectRatioCti(viewBox))

        self.xAxisCti = self.insertChild(PgAxisCti('x-axis'))
        #xAxisCti.insertChild(PgAxisShowCti(imagePlotItem, 'bottom')) # disabled, seems broken
        self.xAxisCti.insertChild(PgAxisLabelCti(imagePlotItem, 'bottom', self.pgImagePlot2d.collector,
            defaultData=1, configValues=[PgAxisLabelCti.NO_LABEL, "idx of {x-dim}"]))
        self.xFlippedCti = self.xAxisCti.insertChild(PgAxisFlipCti(viewBox, X_AXIS))
        self.xAxisRangeCti = self.xAxisCti.insertChild(PgAxisRangeCti(viewBox, X_AXIS))

        self.yAxisCti = self.insertChild(PgAxisCti('y-axis'))
        #yAxisCti.insertChild(PgAxisShowCti(imagePlotItem, 'left'))  # disabled, seems broken
        self.yAxisCti.insertChild(PgAxisLabelCti(imagePlotItem, 'left', self.pgImagePlot2d.collector,
            defaultData=1, configValues=[PgAxisLabelCti.NO_LABEL, "idx of {y-dim}"]))
        self.yFlippedCti = self.yAxisCti.insertChild(PgAxisFlipCti(viewBox, Y_AXIS))
        self.yAxisRangeCti = self.yAxisCti.insertChild(PgAxisRangeCti(viewBox, Y_AXIS))

        #### Color scale ####
        colorAutoRangeFunctions = defaultAutoRangeMethods(self.pgImagePlot2d)
        self.insertChild(PgHistLutColorRangeCti(pgImagePlot2d.histLutItem, colorAutoRangeFunctions,
                                                nodeName="color range"))

        histViewBox = pgImagePlot2d.histLutItem.vb
        histViewBox.enableAutoRange(Y_AXIS, False)
        self.histRangeCti = self.insertChild(PgAxisRangeCti(histViewBox, Y_AXIS,
                                                            nodeName='histogram range'))

        self.insertChild(PgGradientEditorItemCti(self.pgImagePlot2d.histLutItem.gradient))

        # Probe and cross-hair plots
        self.probeCti = self.insertChild(BoolCti('show probe', True))

        self.crossPlotGroupCti = self.insertChild(BoolGroupCti('cross-hair',  expanded=False))

        self.crossPenCti = self.crossPlotGroupCti.insertChild(PgPlotDataItemCti(expanded=False))
        #self.crossLinesCti = self.crossPlotGroupCti.insertChild(PgPlotDataItemCti('cross pen',
        #                                                                          expanded=False))

        self.horCrossPlotCti = self.crossPlotGroupCti.insertChild(BoolCti('horizontal', False,
                                                                          expanded=False))
        self.horCrossPlotCti.insertChild(PgGridCti(pgImagePlot2d.horCrossPlotItem))
        self.horCrossPlotRangeCti = self.horCrossPlotCti.insertChild(PgAxisRangeCti(
            self.pgImagePlot2d.horCrossPlotItem.getViewBox(), Y_AXIS, nodeName="data range",
            autoRangeFunctions = crossPlotAutoRangeMethods(self.pgImagePlot2d, "horizontal")))

        self.verCrossPlotCti = self.crossPlotGroupCti.insertChild(BoolCti('vertical', False,
                                                                          expanded=False))
        self.verCrossPlotCti.insertChild(PgGridCti(pgImagePlot2d.verCrossPlotItem))
        self.verCrossPlotRangeCti = self.verCrossPlotCti.insertChild(PgAxisRangeCti(
            self.pgImagePlot2d.verCrossPlotItem.getViewBox(), X_AXIS, nodeName="data range",
            autoRangeFunctions = crossPlotAutoRangeMethods(self.pgImagePlot2d, "vertical")))

        # Connect signals
        self._imageAutoRangeFn = partial(setXYAxesAutoRangeOn, self,
                                         self.xAxisRangeCti, self.yAxisRangeCti)
        self.pgImagePlot2d.imagePlotItem.sigAxisReset.connect(self._imageAutoRangeFn)

        self._horCrossPlotAutoRangeFn = partial(setXYAxesAutoRangeOn, self,
                                                self.xAxisRangeCti, self.horCrossPlotRangeCti)
        self.pgImagePlot2d.horCrossPlotItem.sigAxisReset.connect(self._horCrossPlotAutoRangeFn)

        self._verCrossPlotAutoRangeFn = partial(setXYAxesAutoRangeOn, self,
                                                self.verCrossPlotRangeCti, self.yAxisRangeCti)
        self.pgImagePlot2d.verCrossPlotItem.sigAxisReset.connect(self._verCrossPlotAutoRangeFn)

        # Also update axis auto range tree items when linked axes are resized
        horCrossViewBox = self.pgImagePlot2d.horCrossPlotItem.getViewBox()
        horCrossViewBox.sigRangeChangedManually.connect(self.xAxisRangeCti.setAutoRangeOff)
        verCrossViewBox = self.pgImagePlot2d.verCrossPlotItem.getViewBox()
        verCrossViewBox.sigRangeChangedManually.connect(self.yAxisRangeCti.setAutoRangeOff)


    def _closeResources(self):
        """ Disconnects signals.
            Is called by self.finalize when the cti is deleted.
        """
        verCrossViewBox = self.pgImagePlot2d.verCrossPlotItem.getViewBox()
        verCrossViewBox.sigRangeChangedManually.disconnect(self.yAxisRangeCti.setAutoRangeOff)
        horCrossViewBox = self.pgImagePlot2d.horCrossPlotItem.getViewBox()
        horCrossViewBox.sigRangeChangedManually.disconnect(self.xAxisRangeCti.setAutoRangeOff)

        self.pgImagePlot2d.verCrossPlotItem.sigAxisReset.disconnect(self._verCrossPlotAutoRangeFn)
        self.pgImagePlot2d.horCrossPlotItem.sigAxisReset.disconnect(self._horCrossPlotAutoRangeFn)
        self.pgImagePlot2d.imagePlotItem.sigAxisReset.disconnect(self._imageAutoRangeFn)




class PgImagePlot2d(AbstractInspector):
    """ Inspector that contains a PyQtGraph 2-dimensional image plot
    """

    def __init__(self, collector, parent=None):
        """ Constructor. See AbstractInspector constructor for parameters.
        """
        super(PgImagePlot2d, self).__init__(collector, parent=parent)

        # The sliced array is kept in memory. This may be different per inspector, e.g. 3D
        # inspectors may decide that this uses to much memory. The slice is therefor not stored
        # in the collector.
        self.slicedArray = None

        self.titleLabel = pg.LabelItem('title goes here...')

        # The image item
        self.imagePlotItem = ArgosPgPlotItem()
        self.viewBox = self.imagePlotItem.getViewBox()
        self.viewBox.disableAutoRange(BOTH_AXES)

        self.imageItem = pg.ImageItem()
        self.imagePlotItem.addItem(self.imageItem)

        self.histLutItem = HistogramLUTItem() # what about GradientLegend?
        self.histLutItem.setImageItem(self.imageItem)
        self.histLutItem.vb.setMenuEnabled(False)
        self.histLutItem.setHistogramRange(0, 100) # Disables autoscaling

        # Probe and cross hair plots
        self.crossPlotRow = None # the row coordinate of the cross hair. None if no cross hair.
        self.crossPlotCol = None # the col coordinate of the cross hair. None if no cross hair.
        self.horCrossPlotItem = ArgosPgPlotItem()
        self.verCrossPlotItem = ArgosPgPlotItem()
        self.horCrossPlotItem.setXLink(self.imagePlotItem)
        self.verCrossPlotItem.setYLink(self.imagePlotItem)
        self.horCrossPlotItem.setLabel('left', ' ')
        self.verCrossPlotItem.setLabel('bottom', ' ')
        self.horCrossPlotItem.showAxis('top', True)
        self.horCrossPlotItem.showAxis('bottom', False)
        self.verCrossPlotItem.showAxis('right', True)
        self.verCrossPlotItem.showAxis('left', False)

        self.crossPen = pg.mkPen("#BFBFBF")
        self.crossShadowPen = pg.mkPen([0, 0, 0, 100], width=3)
        self.crossLineHorShadow = pg.InfiniteLine(angle=0, movable=False, pen=self.crossShadowPen)
        self.crossLineVerShadow = pg.InfiniteLine(angle=90, movable=False, pen=self.crossShadowPen)
        self.crossLineHorizontal = pg.InfiniteLine(angle=0, movable=False, pen=self.crossPen)
        self.crossLineVertical = pg.InfiniteLine(angle=90, movable=False, pen=self.crossPen)
        self.probeLabel = pg.LabelItem('', justify='left')

        # Layout

        # Hiding the horCrossPlotItem and horCrossPlotItem will still leave some space in the
        # grid layout. We therefore remove them from the layout instead. We need to know if they
        # are already added.
        self.horPlotAdded = False
        self.verPlotAdded = False

        self.graphicsLayoutWidget = pg.GraphicsLayoutWidget()
        self.contentsLayout.addWidget(self.graphicsLayoutWidget)

        self.graphicsLayoutWidget.addItem(self.titleLabel, ROW_TITLE, COL_TITLE, colspan=3)
        self.graphicsLayoutWidget.addItem(self.histLutItem, ROW_COLOR, COL_COLOR, rowspan=2)
        self.graphicsLayoutWidget.addItem(self.imagePlotItem, ROW_IMAGE, COL_IMAGE)
        self.graphicsLayoutWidget.addItem(self.probeLabel, ROW_PROBE, COL_PROBE, colspan=3)

        gridLayout = self.graphicsLayoutWidget.ci.layout # A QGraphicsGridLayout
        gridLayout.setHorizontalSpacing(10)
        gridLayout.setVerticalSpacing(10)
        #gridLayout.setRowSpacing(ROW_PROBE, 40)

        gridLayout.setRowStretchFactor(ROW_HOR_LINE, 1)
        gridLayout.setRowStretchFactor(ROW_IMAGE, 2)
        gridLayout.setColumnStretchFactor(COL_IMAGE, 2)
        gridLayout.setColumnStretchFactor(COL_VER_LINE, 1)

        # Configuration tree
        self._config = PgImagePlot2dCti(pgImagePlot2d=self, nodeName='inspector')

        # Connect signals
        # Based mouseMoved on crosshair.py from the PyQtGraph examples directory.
        # I did not use the SignalProxy because I did not see any difference.
        self.imagePlotItem.scene().sigMouseMoved.connect(self.mouseMoved)


    def finalize(self):
        """ Is called before destruction. Can be used to clean-up resources.
        """
        logger.debug("Finalizing: {}".format(self))
        self.imagePlotItem.scene().sigMouseMoved.connect(self.mouseMoved)
        self.imagePlotItem.close()
        self.graphicsLayoutWidget.close()


    @classmethod
    def axesNames(cls):
        """ The names of the axes that this inspector visualizes.
            See the parent class documentation for a more detailed explanation.
        """
        return tuple(['Y', 'X'])


    def _hasValidData(self):
        """ Returns True if the inspector has data that can be plotted.
        """
        return self.slicedArray is not None and array_has_real_numbers(self.slicedArray.data)


    def _clearContents(self):
        """ Clears the contents when no valid data is available
        """
        logger.debug("Clearing inspector contents")
        self.titleLabel.setText('')

        # Don't clear the imagePlotItem, the imageItem is only added in the constructor.
        self.imageItem.clear()
        self.imagePlotItem.setLabel('left', '')
        self.imagePlotItem.setLabel('bottom', '')


    def _drawContents(self, reason=None, initiator=None):
        """ Draws the plot contents from the sliced array of the collected repo tree item.

            The reason and initiator parameters are ignored.
            See AbstractInspector.updateContents for their description.
        """
        self.crossPlotRow = None # reset because the sliced array shape may change
        self.crossPlotCol = None # idem dito

        gridLayout = self.graphicsLayoutWidget.ci.layout # A QGraphicsGridLayout

        if self.config.horCrossPlotCti.configValue:
            gridLayout.setRowStretchFactor(ROW_HOR_LINE, 1)
            if not self.horPlotAdded:
                self.graphicsLayoutWidget.addItem(self.horCrossPlotItem, ROW_HOR_LINE, COL_HOR_LINE)
                self.horPlotAdded = True
                gridLayout.activate()
        else:
            gridLayout.setRowStretchFactor(ROW_HOR_LINE, 0)
            if self.horPlotAdded:
                self.graphicsLayoutWidget.removeItem(self.horCrossPlotItem)
                self.horPlotAdded = False
                gridLayout.activate()

        if self.config.verCrossPlotCti.configValue:
            gridLayout.setColumnStretchFactor(COL_VER_LINE, 1)
            if not self.verPlotAdded:
                self.graphicsLayoutWidget.addItem(self.verCrossPlotItem, ROW_VER_LINE, COL_VER_LINE)
                self.verPlotAdded = True
                gridLayout.activate()
        else:
            gridLayout.setColumnStretchFactor(COL_VER_LINE, 0)
            if self.verPlotAdded:
                self.graphicsLayoutWidget.removeItem(self.verCrossPlotItem)
                self.verPlotAdded = False
                gridLayout.activate()

        # The sliced array can be a masked array or a (regular) numpy array. PyQtGraph doesn't
        # handle masked array so we convert the masked values to Nans. Missing data values are
        # replaced by NaNs. The PyQtGraph image plot shows this as the color at the lowest end
        # of the color scale. Unfortunately we cannot choose a missing-value color, but at least
        # the Nans do not influence for the histogram and color range.
        #missingDataValue = self.collector.rti.missingDataValue if self.collector.rti else None # TODO nicer solution
        #self.slicedArray = replace_missing_values(self.collector.getSlicedArray(),
        #                                          missingDataValue, np.nan)

        self.slicedArray = self.collector.getSlicedArray()

        if not self._hasValidData():
            self._clearContents()
            raise InvalidDataError("No data available or it does not contain real numbers")

        # Valid plot data from here on
        self.slicedArray.replaceMaskedValueWithNan()  # will convert data to float if int

        self.titleLabel.setText(self.configValue('title').format(**self.collector.rtiInfo))

        # PyQtGraph uses the following dimension order: T, X, Y, Color.
        # We need to transpose the slicedArray ourselves because axes = {'x':1, 'y':0}
        # doesn't seem to do anything.
        self.slicedArray = self.slicedArray.transpose()
        self.imageItem.setImage(self.slicedArray.data, autoLevels=False)

        self.horCrossPlotItem.invertX(self.config.xFlippedCti.configValue)
        self.verCrossPlotItem.invertY(self.config.yFlippedCti.configValue)

        if self.config.probeCti.configValue:
            self.probeLabel.setVisible(True)
            self.imagePlotItem.addItem(self.crossLineVerShadow, ignoreBounds=True)
            self.imagePlotItem.addItem(self.crossLineHorShadow, ignoreBounds=True)
            self.imagePlotItem.addItem(self.crossLineVertical, ignoreBounds=True)
            self.imagePlotItem.addItem(self.crossLineHorizontal, ignoreBounds=True)
        else:
            self.probeLabel.setVisible(False)

        # Update the config tree from the (possibly) new state of the PgImagePlot2d inspector,
        # e.g. the axis range or color range may have changed while drawing.
        self.config.updateTarget()


    @QtSlot(QtCore.QPointF)
    def mouseMoved(self, viewPos):
        """ Updates the probe text with the values under the cursor.
            Draws a vertical line and a symbol at the position of the probe.
        """
        try:
            show_data_point = False # shows the data point as a circle in the cross hair plots
            self.crossPlotRow, self.crossPlotCol = None, None

            self.probeLabel.setText("<span style='color: #808080'>no data at cursor</span>")
            self.crossLineHorizontal.setVisible(False)
            self.crossLineVertical.setVisible(False)
            self.crossLineHorShadow.setVisible(False)
            self.crossLineVerShadow.setVisible(False)

            self.horCrossPlotItem.clear()
            self.verCrossPlotItem.clear()

            if (self._hasValidData() and self.slicedArray is not None
                and self.viewBox.sceneBoundingRect().contains(viewPos)):

                # Calculate the row and column at the cursor. I just math.floor because the pixel
                # corners of the image lie at integer values (and not the centers of the pixels).
                scenePos = self.viewBox.mapSceneToView(viewPos)
                row, col = math.floor(scenePos.y()), math.floor(scenePos.x())
                row, col = int(row), int(col) # Needed in Python 2
                nRows, nCols = self.slicedArray.shape

                if (0 <= row < nRows) and (0 <= col < nCols):
                    self.viewBox.setCursor(Qt.CrossCursor)
                    self.crossPlotRow, self.crossPlotCol = row, col
                    value = self.slicedArray[row, col]
                    txt = "pos = ({:d}, {:d}), value = {!r}".format(row, col, value)
                    self.probeLabel.setText(txt)

                    # Show cross section at the cursor pos in the line plots
                    if self.config.horCrossPlotCti.configValue:
                        self.crossLineHorShadow.setVisible(True)
                        self.crossLineHorizontal.setVisible(True)
                        self.crossLineHorShadow.setPos(row)
                        self.crossLineHorizontal.setPos(row)
                        horPlotDataItem = self.config.crossPenCti.createPlotDataItem()
                        horPlotDataItem.setData(self.slicedArray[row, :], connect="finite")
                        self.horCrossPlotItem.addItem(horPlotDataItem)

                        # Vertical line in hor-cross plot
                        crossLineShadow90 = pg.InfiniteLine(angle=90, movable=False,
                                                            pen=self.crossShadowPen)
                        crossLineShadow90.setPos(col)
                        self.horCrossPlotItem.addItem(crossLineShadow90, ignoreBounds=True)
                        crossLine90 = pg.InfiniteLine(angle=90, movable=False, pen=self.crossPen)
                        crossLine90.setPos(col)
                        self.horCrossPlotItem.addItem(crossLine90, ignoreBounds=True)

                        if show_data_point:
                            crossPoint90 = pg.PlotDataItem(symbolPen=self.crossPen)
                            crossPoint90.setSymbolBrush(QtGui.QBrush(self.config.crossPenCti.penColor))
                            crossPoint90.setSymbolSize(10)
                            crossPoint90.setData((col,), (self.slicedArray[row, col],))
                            self.horCrossPlotItem.addItem(crossPoint90, ignoreBounds=True)

                        self.config.horCrossPlotRangeCti.updateTarget() # update auto range

                    if self.config.verCrossPlotCti.configValue:
                        self.crossLineVerShadow.setVisible(True)
                        self.crossLineVertical.setVisible(True)
                        self.crossLineVerShadow.setPos(col)
                        self.crossLineVertical.setPos(col)
                        verPlotDataItem = self.config.crossPenCti.createPlotDataItem()
                        verPlotDataItem.setData(self.slicedArray[:, col], np.arange(nRows),
                                                connect="finite")
                        self.verCrossPlotItem.addItem(verPlotDataItem)

                        # Horizontal line in ver-cross plot
                        crossLineShadow0 = pg.InfiniteLine(angle=0, movable=False,
                                                           pen=self.crossShadowPen)
                        crossLineShadow0.setPos(row)
                        self.verCrossPlotItem.addItem(crossLineShadow0, ignoreBounds=True)
                        crossLine0 = pg.InfiniteLine(angle=0, movable=False, pen=self.crossPen)
                        crossLine0.setPos(row)
                        self.verCrossPlotItem.addItem(crossLine0, ignoreBounds=True)

                        if show_data_point:
                            crossPoint0 = pg.PlotDataItem(symbolPen=self.crossPen)
                            crossPoint0.setSymbolBrush(QtGui.QBrush(self.config.crossPenCti.penColor))
                            crossPoint0.setSymbolSize(10)
                            crossPoint0.setData((self.slicedArray[row, col],), (row,))
                            self.verCrossPlotItem.addItem(crossPoint0, ignoreBounds=True)

                        self.config.verCrossPlotRangeCti.updateTarget() # update auto range

        except Exception as ex:
            # In contrast to _drawContents, this function is a slot and thus must not throw
            # exceptions. The exception is logged. Perhaps we should clear the cross plots, but
            # this could, in turn, raise exceptions.
            if DEBUGGING:
                raise
            else:
                logger.exception(ex)

