"""
Script to download CMEMS data, and produce transect plots of the data.
Different variables and model entries can be specified. NOTE: the lat slice is manually set
so will probably need tweaking (was unable to robustly ID the valid data edge.)
"""


import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
import copernicusmarine
import xarray as xr
import holoviews as hv
from bokeh.io import show
import numpy as np
import hvplot.xarray
hv.extension('bokeh')
from attrs import frozen, define
import cmocean.cm as cmo

def main():
    """
    creates transect plots, using the extent and Model Entries that are specified.
    :return:
    """
    extent = Extent(year=2023,
                    north=80,
                    south=69,
                    east=31,
                    west=29
                    )

    NEMO_MEDUSA_Phy = ModelEntry(dataset_id="NEMO_MEDUSA_Phy",
                                 variable=[VariableEntry(name="thetao",
                                                         plot_name="temperature",
                                                         colourmap="thermal",
                                                         units="degreesC",
                                 )],
                                 extent=extent,
                                 file_format="netcdf",
                                 output_path="NEMO-MEDUSA/NEMO_MEDUSA_2023_T.nc",
                                 local_source=True,
                                 regular_grid=False
                                 )

    NEMO_MEDUSA_Phy.get_data()

    NEMO_MEDUSA_Phy.plot_transects(longitude=30.0,html=True)

    # Arctic_Phys = ModelEntry(dataset_id="cmems_mod_arc_phy_anfc_6km_detided_P1M-m",
    #                          variable=[VariableEntry(name="thetao",
    #                                                    plot_name="temperature",
    #                                                    colourmap="thermal",
    #                                                    units="degreesC",
    #                                                    ),
    #                                      VariableEntry(name="so",
    #                                                    plot_name="salinity",
    #                                                    colourmap="haline",
    #                                                    units="PSU"
    #                                                    )
    #                                      ],
    #                          extent=extent,)
    #
    # Arctic_Phys.get_data()
    #
    # Arctic_BGS = ModelEntry(dataset_id="cmems_mod_arc_bgc_anfc_ecosmo_P1M-m",
    #                         variable=[VariableEntry(name="chl",
    #                                                 plot_name="chlorophyll",
    #                                                 colourmap="algae",
    #                                                 units="mmolm-3")
    #                                   ],
    #                         extent=extent)
    #
    # Arctic_BGS.get_data()
    #
    # Arctic_BGS.plot_transects(longitude=30.0)
    # Arctic_Phys.plot_transects(longitude=30.0)


@frozen
class Extent:
    north: float
    south: float
    east: float
    west: float
    year: int

@frozen
class VariableEntry:
    name: str
    plot_name:str
    colourmap:str
    units: str

@define
class ModelEntry:
    dataset_id: str
    variable: list[VariableEntry]
    extent: Extent
    output_path: str = None
    local_source: bool = False
    file_format: str = "zarr"
    regular_grid: bool = True

    def get_data(self) -> ():
        if self.local_source and self.output_path is None:
            raise Exception("output_path must be specified for local sources")
        elif self.local_source is False and self.output_path is None:
            output_dir = "copernicus_data"
            skip_existing = True
            start_dt = f"{self.extent.year}-01-01"
            end_dt = f"{self.extent.year}-12-31"
            var_list = []
            for var in self.variable:
                var_list.append(var.name)
            concat_vars = "_".join(var_list)
            output_file = f"{self.dataset_id}_{concat_vars}_{self.extent.north}_{self.extent.south}_{self.extent.east}_{self.extent.west}_{start_dt}_{end_dt}"
            self.output_path = f"{output_dir}/{output_file}"

            copernicusmarine.subset(dataset_id=self.dataset_id,
                                    variables=var_list,
                                    minimum_latitude=self.extent.south,
                                    maximum_latitude=self.extent.north,
                                    minimum_longitude=self.extent.west,
                                    maximum_longitude=self.extent.east,
                                    start_datetime=start_dt,
                                    end_datetime=end_dt,
                                    output_filename=output_file,
                                    output_directory=output_dir,
                                    file_format=self.file_format,
                                    skip_existing=skip_existing,
                                    )
        else:
            pass

    def plot_transects(self,longitude:float,html:bool=False):
        # TODO need to figure out how to dynamically set these the start slice in particular
        latitude_start_slice = 69.5
        latitude_end_slice = 80

        assert longitude >= self.extent.west and longitude <= self.extent.east

        month = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                 "November", "December"]
        # open dataset
        if self.file_format == "zarr":
            ds = xr.open_zarr(f"{self.output_path}.zarr", consolidated=True)
        elif self.file_format == "netcdf":
            ds = xr.open_dataset(f"{self.output_path}")
        else:
            raise Exception("unsupported file format")
        if self.regular_grid:
            depth_key = "depth"
        else:
            depth_key = "deptht"
        # Mask depth coordinates where parameter is valid (not NaN)
        valid_depths = ds[depth_key].where(~np.isnan(ds[self.variable[0].name]))
        # Find max valid depth
        max_valid_depth = valid_depths.max().values

        for j in range(self.variable.__len__()):
            # get max and min values of variable to set colour map range
            ds_var = ds[self.variable[j].name]
            max_valid_vals = np.nanmax(ds_var.values)
            min_valid_vals = np.nanmin(ds_var.values)
            for i in range(month.__len__()):
                # create start of month datetime object
                month_dt = datetime.strptime(f"{month[i]} {self.extent.year}", "%B %Y")
                if not self.regular_grid:
                    tolerance = 0.05  # degrees

                    # nav_lon has shape (y, x)
                    mask = np.abs(ds['nav_lon'].values - longitude) < tolerance
                    iy_ix_pairs = np.argwhere(mask)
                    transect_profiles = []
                    latitudes = []

                    for iy, ix in iy_ix_pairs:
                        profile = ds[self.variable[0].name].isel(y=iy, x=ix)
                        # get the correct time slice
                        profile = profile.isel(time_counter=i)
                        # Store profile and corresponding latitude
                        transect_profiles.append(profile.values)
                        latitudes.append(ds['nav_lat'].values[iy, ix])

                    data = np.vstack(transect_profiles)  # shape: (n_points, depth)
                    latitudes = np.array(latitudes)
                    depths = ds['deptht'].values

                    # Sort by latitude for plotting
                    sorted_idx = np.argsort(latitudes)
                    data = data[sorted_idx]
                    latitudes = latitudes[sorted_idx]
                    # Build a temporary DataArray for plotting
                    slice_ds = xr.DataArray(
                        data,
                        coords={'latitude': latitudes, 'depth': depths},
                        dims=('latitude', 'depth'),
                        name='thetao'
                    )
                else:
                    # select based on valid values
                    lon_slice = ds.longitude.sel(longitude=longitude, method='nearest').item()
                    slice_ds = ds_var.sel(longitude=lon_slice,
                                          depth=slice(0, max_valid_depth),
                                          latitude=slice(latitude_start_slice, latitude_end_slice),
                                          time=slice(month_dt, month_dt + relativedelta(months=+1))
                                          )
                # create colourmap
                if self.variable[j].colourmap == "haline":
                    colourmap = cmo.haline
                elif self.variable[j].colourmap == "algae":
                    colourmap = cmo.algae
                elif self.variable[j].colourmap == "thermal":
                    colourmap = cmo.thermal
                else:
                    raise Exception(f"Unknown colourmap: {self.variable[j].colourmap}")
                # Plot with HoloViews (heatmap with contours)
                heatmap = slice_ds.hvplot.quadmesh(
                    x='latitude',
                    y='depth',
                    cmap=colourmap,
                    colorbar=True,
                    flip_yaxis=True,
                    title=f'Latitude–Depth Transect: {self.variable[j].plot_name} {month[i]} {self.extent.year}',
                    width=1600,
                    height=600,
                    bgcolor='gray',
                    clabel=self.variable[j].units,
                    clim=(min_valid_vals, max_valid_vals),
                )
                contours = slice_ds.hvplot.contour(
                    x='latitude', y='depth',
                    levels=20,
                    color='black',
                    line_width=0.5,
                    value_label=True,
                )

                if html:
                    renderer = hv.renderer('bokeh')
                    bokeh_plot = renderer.get_plot(heatmap*contours).state
                    show(bokeh_plot)
                else:
                    os.makedirs(f"docs/{self.dataset_id}/{self.extent.year}/{month[i]}", exist_ok=True)
                    png_out = f"docs/{self.dataset_id}/{self.extent.year}/{month[i]}/{self.variable[j].name}.png"
                    hvplot.save((heatmap * contours), filename=png_out, fmt="png")







if __name__ == "__main__":
    main()