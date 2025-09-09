from qgis.core import (
    QgsProject, QgsLayoutExporter, QgsRasterLayer, QgsLayoutItemPicture
)
from qgis.utils import iface
import os
import csv

# 1. Load your QGIS project
project = QgsProject.instance()
project.read('/Users/thopri/BarentsSeaTransects/Ice_Extent_Map.qgz')

# 2. Get the layout manager and layout
layout_manager = project.layoutManager()
layout = layout_manager.layoutByName("Layout 1")

# 3. Get the raster layer
raster_layer = QgsProject.instance().mapLayersByName('/siconc')[0]

# === 4. Load coordinates & rotation from CSV ===
csv_path = "/disco/example_disco_trajectory.csv"
# Expect CSV columns: step,x,y,rotation
trajectory = []
with open(csv_path, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        trajectory.append({
            "x": float(row["x"]),
            "y": float(row["y"]),
            "rotation": float(row["rotation"])
        })

# 4. Loop through raster bands
for step, row in enumerate(trajectory, start=1):
    # Update the raster symbology to use a different band
    if step <= raster_layer.bandCount():
        renderer = raster_layer.renderer().clone()
        renderer.setBand(step)
        raster_layer.setRenderer(renderer)
        raster_layer.triggerRepaint()

    # Get your point layer by name
    layer = QgsProject.instance().mapLayersByName('disco_loc')[0]
    
    # Start editing the layer
    layer.startEditing()

    # Get the only feature (or use a specific ID if needed)
    feature = next(layer.getFeatures())
    
        # === Update rotation attribute ===
    layer.startEditing()
    rotation_idx = layer.fields().indexOf('rotation')
    if rotation_idx != -1:
        layer.changeAttributeValue(feature.id(), rotation_idx, row["rotation"])
    layer.commitChanges()
    
    # === Update geometry (position) ===
    layer.startEditing()
    new_geom = QgsGeometry.fromPointXY(QgsPointXY(row["x"], row["y"]))
    layer.changeGeometry(feature.id(), new_geom)
    layer.commitChanges()
    layer.triggerRepaint()

    # 5. Export layout
    exporter = QgsLayoutExporter(layout)
    output_path = f"/Users/thopri/BarentsSeaTransects/Arctic_Ice_Extent_2023/ice_extent_day_{step}.png"
    exporter.exportToImage(output_path, QgsLayoutExporter.ImageExportSettings())