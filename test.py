import cartopy.crs as ccrs
import geoviews as gv
from bokeh.io import show
gv.extension('bokeh')

tiles = gv.tile_sources.EsriImagery()

hvplots = gv.util.get_tile_rgb(tiles, bbox=(-180, -70, 180, 70), zoom_level=1).opts(width=500, height=500, projection=ccrs.NorthPolarStereo())

renderer = gv.renderer('bokeh')
bokeh_plot = renderer.get_plot(hvplots).state
show(bokeh_plot)