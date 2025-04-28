# -*- coding: utf-8 -*-
"""
Created on Sun Feg 01 18:26:58 2025

@author: Bobby Azad
"""

import sys
import geopandas as gpd
import pandas as pd

import matplotlib
matplotlib.use("Qt5Agg")  # ensure Qt5
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# Import contextily to add a basemap layer
import contextily as ctx

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QFileDialog, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QPushButton, QMessageBox, QDialog, QDialogButtonBox,
    QCheckBox, QRadioButton, QGroupBox, QLabel, QLineEdit, QHBoxLayout, QComboBox,
    QInputDialog, QSlider, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt


##############################################################################
# MapDialog: Overlays the shapefile on a real-world basemap.
# Includes a horizontal zoom slider and a grid of four arrow buttons for navigation,
# positioned on the left side. When navigating, the "base view" is updated so that
# subsequent zooming is relative to the current view.
##############################################################################
class MapDialog(QDialog):
    def __init__(self, gdf, parent=None):
        super().__init__(parent)
        # Close stray figures so no extra "Figure 1" window appears.
        plt.close('all')
        self.setWindowTitle("Shapefile Map Viewer. A demo version by Bobby Azad")
        self.resize(900, 600)
        self.gdf = gdf
        self.current_alpha = 1.0  # Current transparency for the shapefile overlay.

        main_layout = QVBoxLayout(self)

        # --- Top Controls for Coloring ---
        control_layout = QHBoxLayout()
        self.column_combo = QComboBox()
        self.column_combo.addItem("<No color column>")
        for col_name in self.gdf.columns:
            if col_name != "geometry":
                self.column_combo.addItem(col_name)
        control_layout.addWidget(QLabel("Color by:"))
        control_layout.addWidget(self.column_combo)
        # Default to 'zone' if present.
        idx = self.column_combo.findText("zone")
        if idx >= 0:
            self.column_combo.setCurrentIndex(idx)
        self.cmap_combo = QComboBox()
        colormaps = ["viridis", "plasma", "coolwarm", "Reds", "Blues", "Greens", "Set1"]
        for cm in colormaps:
            self.cmap_combo.addItem(cm)
        control_layout.addWidget(QLabel("Colormap:"))
        control_layout.addWidget(self.cmap_combo)
        self.update_btn = QPushButton("Update Map")
        self.update_btn.clicked.connect(self.update_map)
        control_layout.addWidget(self.update_btn)
        self.reset_btn = QPushButton("Reset View")
        self.reset_btn.clicked.connect(self.reset_view)
        control_layout.addWidget(self.reset_btn)
        main_layout.addLayout(control_layout)

        # --- Map and Controls Layout ---
        # Create a horizontal layout: left side contains the navigation buttons;
        # next, the canvas and zoom slider; then the vertical transparency slider.
        map_layout = QHBoxLayout()

        # Navigation buttons widget.
        nav_widget = QWidget()
        nav_grid = QGridLayout()
        nav_grid.setSpacing(0)
        nav_grid.setContentsMargins(0, 0, 0, 0)
        nav_grid.setSizeConstraint(QGridLayout.SetFixedSize)
        
        self.btn_up = QPushButton("↑")
        self.btn_down = QPushButton("↓")
        self.btn_left = QPushButton("←")
        self.btn_right = QPushButton("→")
        
        for btn in (self.btn_up, self.btn_down, self.btn_left, self.btn_right):
            btn.setFixedSize(40, 40)
        
        # Connect each button to pan 20% of the current view.
        self.btn_up.clicked.connect(lambda: self.move_map(0, 0.2))
        self.btn_down.clicked.connect(lambda: self.move_map(0, -0.2))
        self.btn_left.clicked.connect(lambda: self.move_map(-0.2, 0))
        self.btn_right.clicked.connect(lambda: self.move_map(0.2, 0))
        
        # Arrange the buttons in a "+" shape
        nav_grid.addWidget(self.btn_up, 0, 1)  # Up button in the center
        nav_grid.addWidget(self.btn_left, 1, 0)  # Left button
        nav_grid.addWidget(self.btn_right, 1, 2)  # Right button
        nav_grid.addWidget(self.btn_down, 2, 1)  # Down button in the center
        nav_widget.setLayout(nav_grid)
        nav_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        map_layout.addWidget(nav_widget)

        # Canvas and its related controls.
        canvas_layout = QVBoxLayout()
        self.fig = Figure(figsize=(6, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        canvas_layout.addWidget(self.toolbar)
        canvas_layout.addWidget(self.canvas)
        # Horizontal zoom slider.
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(10)    # 10% of base view.
        self.zoom_slider.setMaximum(300)   # 300% means zoomed in.
        self.zoom_slider.setValue(100)     # 100% is the base view.
        self.zoom_slider.setTickInterval(10)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.valueChanged.connect(self.on_slider_zoom)
        canvas_layout.addWidget(self.zoom_slider)
        map_layout.addLayout(canvas_layout)

        # Vertical transparency slider.
        self.transparency_slider = QSlider(Qt.Vertical)
        self.transparency_slider.setMinimum(0)
        self.transparency_slider.setMaximum(100)
        self.transparency_slider.setValue(100)  # Fully opaque.
        self.transparency_slider.setTickInterval(10)
        self.transparency_slider.setTickPosition(QSlider.TicksRight)
        self.transparency_slider.valueChanged.connect(self.on_slider_transparency)
        map_layout.addWidget(self.transparency_slider)

        main_layout.addLayout(map_layout)

        self.plot_initial()


    def plot_initial(self):
        self.ax.clear()
        current_col = self.column_combo.currentText()
        cmap = self.cmap_combo.currentText()
    
        if self.gdf.crs is not None:
            try:
                if self.gdf.crs.to_epsg() != 3857:
                    display_gdf = self.gdf.to_crs(epsg=3857)
                else:
                    display_gdf = self.gdf
            except Exception as e:
                print("Error in reprojection:", e)
                display_gdf = self.gdf
    
            if current_col == "<No color column>":
                display_gdf.plot(ax=self.ax, zorder=2, alpha=self.current_alpha)
            else:
                display_gdf.plot(column=current_col, cmap=cmap, legend=True,
                                 ax=self.ax, zorder=2, alpha=self.current_alpha)
    
            try:
                self.basemap_im = ctx.add_basemap(self.ax,
                                                  source=ctx.providers.Esri.WorldImagery,
                                                  zorder=1, attribution='', reset_extent=False)
            except Exception as e:
                print("Basemap could not be added:", e)
                self.basemap_im = None
        else:
            self.gdf.plot(ax=self.ax, zorder=2, alpha=self.current_alpha)
            self.basemap_im = None
    
        self.ax.set_title("Shapefile Geometry")
    
        # REMOVE AXES LABELS
        self.ax.set_xticks([])  # Remove x-axis ticks
        self.ax.set_yticks([])  # Remove y-axis ticks
    
        self.fig.tight_layout()
        self.canvas.draw()
    
        self.original_xlim = self.ax.get_xlim()
        self.original_ylim = self.ax.get_ylim()
        
        

    def update_map(self):
        self.ax.clear()
        col = self.column_combo.currentText()
        cmap = self.cmap_combo.currentText()
    
        if self.gdf.crs is not None:
            try:
                if self.gdf.crs.to_epsg() != 3857:
                    display_gdf = self.gdf.to_crs(epsg=3857)
                else:
                    display_gdf = self.gdf
            except Exception as e:
                print("Error in reprojection:", e)
                display_gdf = self.gdf
    
            if col == "<No color column>":
                display_gdf.plot(ax=self.ax, zorder=2, alpha=self.current_alpha)
            else:
                display_gdf.plot(column=col, cmap=cmap, legend=True,
                                 ax=self.ax, zorder=2, alpha=self.current_alpha)
    
            try:
                self.basemap_im = ctx.add_basemap(self.ax,
                                                  source=ctx.providers.Esri.WorldImagery,
                                                  zorder=1, attribution='', reset_extent=False)
            except Exception as e:
                print("Basemap could not be added:", e)
                self.basemap_im = None
        else:
            self.gdf.plot(ax=self.ax, zorder=2, alpha=self.current_alpha)
            self.basemap_im = None
    
        self.ax.set_title("Shapefile Geometry")
    
        # REMOVE AXES LABELS
        self.ax.set_xticks([])  # Remove x-axis ticks
        self.ax.set_yticks([])  # Remove y-axis ticks
    
        self.fig.tight_layout()
        self.canvas.draw()
    
        self.zoom_slider.setValue(100)
        self.original_xlim = self.ax.get_xlim()
        self.original_ylim = self.ax.get_ylim()
        
        

    def reset_view(self):
        """Reset the view to the original base view and remove axis labels."""
        self.ax.set_xlim(self.original_xlim)
        self.ax.set_ylim(self.original_ylim)
        self.zoom_slider.setValue(100)
    
        if self.basemap_im is not None:
            self.basemap_im.set_extent((self.original_xlim[0], self.original_xlim[1],
                                        self.original_ylim[0], self.original_ylim[1]))
        else:
            try:
                self.basemap_im = ctx.add_basemap(self.ax,
                                                  source=ctx.providers.Esri.WorldImagery,
                                                  zorder=1, attribution='', reset_extent=False)
            except Exception as e:
                print("Basemap re-add failed:", e)
    
        # REMOVE AXES LABELS PERMANENTLY
        self.ax.set_xticks([])  # Remove x-axis ticks
        self.ax.set_yticks([])  # Remove y-axis ticks
    
        self.canvas.draw_idle()


    def on_slider_zoom(self, value):
        """
        Adjust the view limits based on the zoom slider value.
        The slider value (as a percentage) defines a scale factor relative to the current base view.
        """
        scale = value / 100.0  # 1.0 = current base; >1.0 = zoom in; <1.0 = zoom out.
        x_center = (self.original_xlim[0] + self.original_xlim[1]) / 2
        y_center = (self.original_ylim[0] + self.original_ylim[1]) / 2
        half_width = (self.original_xlim[1] - self.original_xlim[0]) / 2
        half_height = (self.original_ylim[1] - self.original_ylim[0]) / 2
    
        new_xlim = [x_center - half_width / scale, x_center + half_width / scale]
        new_ylim = [y_center - half_height / scale, y_center + half_height / scale]
    
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
    
        if self.basemap_im is not None:
            self.basemap_im.set_extent((new_xlim[0], new_xlim[1], new_ylim[0], new_ylim[1]))
        else:
            try:
                self.basemap_im = ctx.add_basemap(self.ax,
                                                  source=ctx.providers.Esri.WorldImagery,
                                                  zorder=1, attribution='', reset_extent=False)
            except Exception as e:
                print("Basemap update failed:", e)
    
        # REMOVE AXES LABELS PERMANENTLY
        self.ax.set_xticks([])  # Remove x-axis ticks
        self.ax.set_yticks([])  # Remove y-axis ticks
    
        self.canvas.draw_idle()


    def on_slider_transparency(self, value):
        """
        Update the transparency of the shapefile overlay.
        A value of 100 means fully opaque.
        """
        new_alpha = value / 100.0
        self.current_alpha = new_alpha
        for coll in self.ax.collections:
            if coll.get_zorder() == 2:
                coll.set_alpha(new_alpha)
        self.canvas.draw_idle()

    # --- Navigation Buttons Handler ---
    def move_map(self, dx_frac, dy_frac):
        """
        Pan the view by a fraction of the current view's width/height.
        dx_frac and dy_frac are fractions; for example, 0.2 moves 20% of the current width.
        After panning, update the base view used for zooming.
        """
        # Get the current view limits
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        
        # Calculate the width and height of the current view
        width = cur_xlim[1] - cur_xlim[0]
        height = cur_ylim[1] - cur_ylim[0]
        
        # Calculate the new view limits based on the panning fractions
        dx = dx_frac * width
        dy = dy_frac * height
        new_xlim = (cur_xlim[0] + dx, cur_xlim[1] + dx)
        new_ylim = (cur_ylim[0] + dy, cur_ylim[1] + dy)
        
        # Set the new view limits
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        
        # Update the basemap's extent to match the new view limits
        if self.basemap_im is not None:
            self.basemap_im.set_extent((new_xlim[0], new_xlim[1], new_ylim[0], new_ylim[1]))
        
        # Redraw the canvas to reflect the changes
        self.canvas.draw_idle()
        
        # Update the base view so that the zoom slider works relative to the new view
        self.original_xlim = self.ax.get_xlim()
        self.original_ylim = self.ax.get_ylim()



##############################################################################
# MassUpdateDialog: Unchanged functionality for mass updating table columns.
##############################################################################
class MassUpdateDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mass Update Columns")
        self.selectedColumns = []
        self.operation = None
        self.value = 0

        main_layout = QVBoxLayout(self)

        columns_groupbox = QGroupBox("Select Columns to Update:")
        columns_layout = QVBoxLayout()
        self.checkboxes = []
        for col in columns:
            cb = QCheckBox(col)
            columns_layout.addWidget(cb)
            self.checkboxes.append(cb)
        columns_groupbox.setLayout(columns_layout)
        main_layout.addWidget(columns_groupbox)

        operations_groupbox = QGroupBox("Operation:")
        operations_layout = QVBoxLayout()
        self.radio_add = QRadioButton("Add")
        self.radio_sub = QRadioButton("Subtract")
        self.radio_mul = QRadioButton("Multiply")
        self.radio_div = QRadioButton("Divide")
        self.radio_add.setChecked(True)
        operations_layout.addWidget(self.radio_add)
        operations_layout.addWidget(self.radio_sub)
        operations_layout.addWidget(self.radio_mul)
        operations_layout.addWidget(self.radio_div)
        operations_groupbox.setLayout(operations_layout)
        main_layout.addWidget(operations_groupbox)

        value_layout = QHBoxLayout()
        value_layout.addWidget(QLabel("Value:"))
        self.value_edit = QLineEdit()
        self.value_edit.setText("0")
        value_layout.addWidget(self.value_edit)
        main_layout.addLayout(value_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def accept(self):
        self.selectedColumns = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        if self.radio_add.isChecked():
            self.operation = "add"
        elif self.radio_sub.isChecked():
            self.operation = "subtract"
        elif self.radio_mul.isChecked():
            self.operation = "multiply"
        elif self.radio_div.isChecked():
            self.operation = "divide"
        try:
            self.value = float(self.value_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Please enter a valid numeric value.")
            return
        super().accept()

    def getSelectedColumns(self):
        return self.selectedColumns

    def getOperation(self):
        return self.operation

    def getValue(self):
        return self.value


##############################################################################
# MainWindow: Enhanced UI for editing/viewing shapefiles.
##############################################################################
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shapefile (DBF) Editor - Demo version by: Bobby Azad")
        self.resize(900, 600)

        # Menu Bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open Shapefile", self)
        open_action.triggered.connect(self.open_shapefile)
        file_menu.addAction(open_action)
        save_action = QAction("Save Shapefile As...", self)
        save_action.triggered.connect(self.save_shapefile)
        file_menu.addAction(save_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools Menu for additional features (e.g., Statistics)
        tools_menu = menubar.addMenu("Tools")
        stats_action = QAction("Show Statistics", self)
        stats_action.triggered.connect(self.show_statistics)
        tools_menu.addAction(stats_action)

        # Help Menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # Main widget layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        # --- Filter Section ---
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter column:"))
        self.filterColumnCombo = QComboBox()
        filter_layout.addWidget(self.filterColumnCombo, 1)
        filter_layout.addWidget(QLabel("Filter text:"))
        self.filterLineEdit = QLineEdit()
        filter_layout.addWidget(self.filterLineEdit, 3)
        apply_filter_btn = QPushButton("Apply Filter")
        apply_filter_btn.clicked.connect(self.apply_filter)
        filter_layout.addWidget(apply_filter_btn)
        clear_filter_btn = QPushButton("Clear Filter")
        clear_filter_btn.clicked.connect(self.clear_filter)
        filter_layout.addWidget(clear_filter_btn)
        self.main_layout.addLayout(filter_layout)
        # --- End Filter Section ---

        # Table widget
        self.tableWidget = QTableWidget()
        self.main_layout.addWidget(self.tableWidget)

        # First row of buttons
        buttons_layout = QHBoxLayout()
        self.massUpdateButton = QPushButton("Mass Update")
        self.massUpdateButton.clicked.connect(self.mass_update)
        buttons_layout.addWidget(self.massUpdateButton)
        self.viewMapButton = QPushButton("View Map")
        self.viewMapButton.clicked.connect(self.view_map)
        buttons_layout.addWidget(self.viewMapButton)
        self.main_layout.addLayout(buttons_layout)

        # Second row of buttons for adding/deleting columns/rows
        crud_layout = QHBoxLayout()
        self.addColumnButton = QPushButton("Add Column")
        self.addColumnButton.clicked.connect(self.add_column)
        crud_layout.addWidget(self.addColumnButton)
        self.delColumnButton = QPushButton("Delete Selected Column")
        self.delColumnButton.clicked.connect(self.delete_column)
        crud_layout.addWidget(self.delColumnButton)
        self.addRowButton = QPushButton("Add Row")
        self.addRowButton.clicked.connect(self.add_row)
        crud_layout.addWidget(self.addRowButton)
        self.delRowButton = QPushButton("Delete Selected Row")
        self.delRowButton.clicked.connect(self.delete_row)
        crud_layout.addWidget(self.delRowButton)
        self.main_layout.addLayout(crud_layout)

        # Status Bar
        self.statusBar().showMessage("Ready")

        # Internal references.
        self.shapefile_path = None
        self.gdf = None
        self.attr_columns = []

    def apply_table_theme(self):
        self.tableWidget.setAlternatingRowColors(True)
        self.tableWidget.verticalHeader().setDefaultSectionSize(30)
        self.tableWidget.horizontalHeader().setDefaultSectionSize(150)
        self.tableWidget.setStyleSheet(
            """
            QTableWidget {
                alternate-background-color: #f9f9f9;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                font-weight: bold;
                font-size: 12pt;
                border-bottom: 2px solid #888;
            }
            """
        )

    def apply_filter(self):
        col_text = self.filterColumnCombo.currentText()
        if col_text in ["--", ""]:
            QMessageBox.warning(self, "Filter Error", "Please select a valid column to filter.")
            return
        filter_text = self.filterLineEdit.text().lower()
        col_index = self.filterColumnCombo.currentIndex()
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, col_index)
            if item is not None:
                cell_text = item.text().lower()
                self.tableWidget.setRowHidden(row, filter_text not in cell_text)

    def clear_filter(self):
        self.filterLineEdit.clear()
        for row in range(self.tableWidget.rowCount()):
            self.tableWidget.setRowHidden(row, False)

    def open_shapefile(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Open Shapefile", "", "Shapefiles (*.shp)")
        if file_path:
            self.load_shapefile(file_path)

    def load_shapefile(self, shp_path):
        try:
            gdf = gpd.read_file(shp_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Shapefile:\n{str(e)}")
            return
        self.shapefile_path = shp_path
        self.gdf = gdf
        self.attr_columns = [c for c in self.gdf.columns if c != "geometry"]
        self.populate_table()

    def populate_table(self):
        if self.gdf is None or len(self.attr_columns) == 0:
            self.tableWidget.setRowCount(0)
            self.tableWidget.setColumnCount(0)
            return
        df_attrs = self.gdf[self.attr_columns].copy()
        num_rows = len(df_attrs)
        num_cols = len(df_attrs.columns)
        self.tableWidget.clear()
        self.tableWidget.setRowCount(num_rows)
        self.tableWidget.setColumnCount(num_cols)
        self.tableWidget.setHorizontalHeaderLabels(df_attrs.columns.tolist())
        for row_idx in range(num_rows):
            for col_idx in range(num_cols):
                val = df_attrs.iat[row_idx, col_idx]
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.tableWidget.setItem(row_idx, col_idx, item)
        self.apply_table_theme()
        self.filterColumnCombo.clear()
        self.filterColumnCombo.addItems(self.attr_columns)

    def add_column(self):
        col_name, ok = QInputDialog.getText(self, "New Column", "Enter column name:")
        if not ok or not col_name:
            return
        default_value, ok2 = QInputDialog.getText(self, "Default Value", "Enter default value for new column:")
        if not ok2:
            return
        col_index = self.tableWidget.columnCount()
        self.tableWidget.insertColumn(col_index)
        self.tableWidget.setHorizontalHeaderItem(col_index, QTableWidgetItem(col_name))
        row_count = self.tableWidget.rowCount()
        for row in range(row_count):
            item = QTableWidgetItem(default_value)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.tableWidget.setItem(row, col_index, item)
        self.attr_columns.append(col_name)
        self.apply_table_theme()
        self.filterColumnCombo.clear()
        self.filterColumnCombo.addItems(self.attr_columns)

    def delete_column(self):
        col_index = self.tableWidget.currentColumn()
        if col_index < 0:
            QMessageBox.warning(self, "Delete Column", "No column selected.")
            return
        self.tableWidget.removeColumn(col_index)
        if col_index < len(self.attr_columns):
            self.attr_columns.pop(col_index)
        self.apply_table_theme()
        self.filterColumnCombo.clear()
        self.filterColumnCombo.addItems(self.attr_columns)

    def add_row(self):
        row_count = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row_count)
        self.apply_table_theme()

    def delete_row(self):
        row_index = self.tableWidget.currentRow()
        if row_index < 0:
            QMessageBox.warning(self, "Delete Row", "No row selected.")
            return
        self.tableWidget.removeRow(row_index)
        self.apply_table_theme()

    def mass_update(self):
        if self.gdf is None or not len(self.attr_columns):
            QMessageBox.warning(self, "No Data", "No shapefile data loaded.")
            return
        dialog = MassUpdateDialog(self.attr_columns, self)
        if dialog.exec_() == QDialog.Accepted:
            selected_columns = dialog.getSelectedColumns()
            operation = dialog.getOperation()
            value = dialog.getValue()
            for col_idx, col_name in enumerate(self.attr_columns):
                if col_name in selected_columns:
                    for row in range(self.tableWidget.rowCount()):
                        item = self.tableWidget.item(row, col_idx)
                        if item is not None:
                            try:
                                old_val = float(item.text())
                                if operation == "add":
                                    new_val = old_val + value
                                elif operation == "subtract":
                                    new_val = old_val - value
                                elif operation == "multiply":
                                    new_val = old_val * value
                                elif operation == "divide":
                                    if value == 0:
                                        QMessageBox.warning(self, "Error", "Cannot divide by zero.")
                                        return
                                    new_val = old_val / value
                                else:
                                    new_val = old_val
                                item.setText(str(new_val))
                            except ValueError:
                                pass
            QMessageBox.information(self, "Success", "Mass update operation applied.")

    def save_shapefile(self):
        if self.gdf is None:
            QMessageBox.warning(self, "No Shapefile Loaded", "Please open a shapefile first.")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Shapefile As", self.shapefile_path, "Shapefiles (*.shp)"
        )
        if not save_path:
            return
        records = []
        for row_idx in range(self.tableWidget.rowCount()):
            row_data = {}
            for col_idx, col_name in enumerate(self.attr_columns):
                item = self.tableWidget.item(row_idx, col_idx)
                val_str = item.text() if item else ""
                if col_name in self.gdf.columns and pd.api.types.is_numeric_dtype(self.gdf[col_name]):
                    try:
                        val = float(val_str)
                    except ValueError:
                        val = None
                else:
                    val = val_str
                row_data[col_name] = val
            records.append(row_data)
        updated_df = pd.DataFrame(records, columns=self.attr_columns)
        if "geometry" in self.gdf.columns:
            geom = self.gdf["geometry"]
        else:
            QMessageBox.critical(self, "Error", "No geometry found in the GeoDataFrame.")
            return
        new_gdf = gpd.GeoDataFrame(updated_df, geometry=geom, crs=self.gdf.crs)
        try:
            new_gdf.to_file(save_path, driver="ESRI Shapefile")
            QMessageBox.information(self, "Success", f"Shapefile saved successfully:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save shapefile:\n{str(e)}")
        self.gdf = new_gdf

    def view_map(self):
        if self.gdf is None:
            QMessageBox.warning(self, "No Shapefile Loaded", "Please open a shapefile first.")
            return
        try:
            dlg = MapDialog(self.gdf, parent=self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot shapefile:\n{str(e)}")

    def show_statistics(self):
        if self.gdf is None:
            QMessageBox.information(self, "Statistics", "No shapefile loaded.")
            return
        num_features = len(self.gdf)
        bounds = self.gdf.total_bounds
        stats = [
            f"Number of features: {num_features}",
            "Bounds:",
            f"  MinX: {bounds[0]:.2f}, MinY: {bounds[1]:.2f}",
            f"  MaxX: {bounds[2]:.2f}, MaxY: {bounds[3]:.2f}",
            f"Coordinate Reference System: {self.gdf.crs if self.gdf.crs else 'None'}",
            f"Geometry types: {', '.join(self.gdf.geom_type.unique())}",
            f"Number of attribute columns: {len(self.attr_columns)}"
        ]
        if self.gdf.crs and self.gdf.crs.is_projected:
            total_area = self.gdf.area.sum()
            avg_area = self.gdf.area.mean()
            stats.append(f"Total area: {total_area:.2f} square units")
            stats.append(f"Average area per feature: {avg_area:.2f} square units")
        else:
            stats.append(
                "Note: The shapefile is not in a projected coordinate system. "
                "Coordinates are likely in degrees, so area calculations may not be accurate."
            )
        QMessageBox.information(self, "Shapefile Statistics", "\n".join(stats))

    def show_about(self):
        about_text = (
            "Shapefile (DBF) Editor - Demo version\n"
            "Developed for agronomists\n\n"
            "Features:\n"
            " - View and edit shapefile attributes\n"
            " - Mass update attribute values\n"
            " - Interactive map viewer with slider-based zoom/pan, a real-world basemap, "
            "transparency control, and navigation arrows\n"
            " - Filter table rows\n\n"
            "Version 1.0"
        )
        QMessageBox.information(self, "About", about_text)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


