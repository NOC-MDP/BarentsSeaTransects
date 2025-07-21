from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import copernicusmarine
import xarray as xr
import holoviews as hv
from bokeh.io import show
import numpy as np
import hvplot.xarray
hv.extension('bokeh')

def main():
    dataset_id = "cmems_mod_arc_phy_my_topaz4_P1M"
    variables = ["thetao","so"]
    var_plot_names = ["temperature", "salinity"]
    colour_maps = ["plasma","viridis"]
    units = ["degreesC","PSU"]
    assert variables.__len__() == colour_maps.__len__() == units.__len__() == var_plot_names.__len__()

    month = ["January","February","March","April","May","June","July","August","September","October","November","December"]

    year = 2023

    min_lon = 29
    max_lon = 31
    min_lat = 69
    max_lat = 80

    start_dt = f"{year}-01-01"
    end_dt = f"{year}-12-31"
    concat_vars = "_".join(variables)
    output_file = f"{dataset_id}_{concat_vars}_{min_lat}_{max_lat}_{min_lon}_{max_lon}_{start_dt}_{end_dt}"
    output_dir = "copernicus_data"
    file_format = "zarr"
    skip_existing = True

    copernicusmarine.subset(dataset_id=dataset_id,
                            variables=variables,
                            minimum_latitude=min_lat,
                            maximum_latitude=max_lat,
                            minimum_longitude=min_lon,
                            maximum_longitude=max_lon,
                            start_datetime=start_dt,
                            end_datetime=end_dt,
                            output_filename=output_file,
                            output_directory=output_dir,
                            file_format=file_format,
                            skip_existing=skip_existing,)

    ds = xr.open_zarr(f"{output_dir}/{output_file}.zarr", consolidated=True)
    # Mask depth coordinates where parameter is valid (not NaN)
    valid_depths = ds['depth'].where(~np.isnan(ds[variables[0]]))
    # Find max valid depth
    max_valid_depth = valid_depths.max().values


    for i in range(month.__len__()):
        for j in range(variables.__len__()):
            month_dt = datetime.strptime(f"{month[i]} {year}", "%B %Y")
            ds_var = ds[variables[j]]
            # select based on valid values
            slice_ds = ds_var.sel(longitude=30,
                              depth=slice(0,max_valid_depth),
                              latitude=slice(71,80),
                              time=slice(month_dt,month_dt+relativedelta(months=+1))
                              )
            # Plot with HoloViews (heatmap with contours)
            heatmap = slice_ds.hvplot.quadmesh(
                x='latitude',
                y='depth',
                cmap=colour_maps[j],
                colorbar=True,
                flip_yaxis=True,
                title=f'Latitude–Depth Transect: {var_plot_names[j]} {month[i]} {year}',
                width=1600,
                height=600,
                bgcolor='gray',
                clabel=units[j]
            )
            contours = slice_ds.hvplot.contour(
                x='latitude', y='depth',
                levels=20,
                color='black',
                line_width=0.5,
                value_label=True,
            )
            png_out = f"docs/{year}_{month[i]}_{variables[j]}.html"
            # renderer = hv.renderer('bokeh')
            # bokeh_plot = renderer.get_plot(heatmap*contours).state
            # show(bokeh_plot)
            hvplot.save((heatmap*contours),filename=png_out,fmt="png")


if __name__ == "__main__":
    main()