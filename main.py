"""
Script to download CMEMS data, and produce transect plots of the data.
Different variables and model entries can be specified. NOTE: the lat slice is manually set
so will probably need tweaking (was unable to robustly ID the valid data edge.)
"""


import os
from datetime import datetime

import pandas as pd
from dateutil.relativedelta import relativedelta
import copernicusmarine
import xarray as xr
import xesmf as xe
import holoviews as hv
from bokeh.io import show
import numpy as np
import hvplot.xarray
import hvplot.pandas
hv.extension('bokeh')
from attrs import frozen, define
import cmocean.cm as cmo
import cftime

def main():
    """
    creates transect plots, using the extent and Model Entries that are specified.
    :return:
    """
    html = False
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
                                 ),
                                            VariableEntry(name="so",
                                                         plot_name="salinity",
                                                         colourmap="haline",
                                                         units="PSU",
                                                         )
                                                       ],
                                 extent=extent,
                                 file_format="netcdf",
                                 output_path="NEMO-MEDUSA/NEMO_MEDUSA_2023_T.nc",
                                 local_source=True,
                                 ORCA=True
                                 )

    NEMO_MEDUSA_BGC = ModelEntry(dataset_id="NEMO_MEDUSA_BGC",
                                 variable=[VariableEntry(name="CHL",
                                                         plot_name="chlorophyll",
                                                         colourmap="algae",
                                                         units="mmolm-3",)],
                                 extent=extent,
                                 file_format="netcdf",
                                 output_path="NEMO-MEDUSA/NEMO_MEDUSA_2023_CHL.nc",
                                 local_source=True,
                                 ORCA=True)

    NEMO_MEDUSA_Phy.get_data()
    NEMO_MEDUSA_BGC.get_data()

    NEMO_MEDUSA_BGC.plot_transects(longitude=30.0,html=html)
    NEMO_MEDUSA_Phy.plot_transects(longitude=30.0,html=html)

    Arctic_Phys = ModelEntry(dataset_id="cmems_mod_arc_phy_anfc_6km_detided_P1M-m",
                             variable=[VariableEntry(name="thetao",
                                                       plot_name="temperature",
                                                       colourmap="thermal",
                                                       units="degreesC",
                                                       ),
                                         VariableEntry(name="so",
                                                       plot_name="salinity",
                                                       colourmap="haline",
                                                       units="PSU"
                                                       )
                                         ],
                             extent=extent,)

    Arctic_Phys.get_data()

    Arctic_BGS = ModelEntry(dataset_id="cmems_mod_arc_bgc_anfc_ecosmo_P1M-m",
                            variable=[VariableEntry(name="chl",
                                                    plot_name="chlorophyll",
                                                    colourmap="algae",
                                                    units="mmolm-3")
                                      ],
                            extent=extent)

    Arctic_BGS.get_data()

    Arctic_BGS.plot_transects(longitude=30.0,html=html)
    Arctic_Phys.plot_transects(longitude=30.0,html=html)

    Arctic_ICE = ModelEntry(dataset_id="cmems_mod_arc_phy_anfc_6km_detided_P1M-m",
                            variable=[VariableEntry(name="siconc",
                                                    plot_name="sea ice",
                                                    units="km",)],
                            extent=extent)

    Arctic_ICE.get_data()
    Arctic_ICE.plot_ice_extent(longitude=30.0,html=html)

    NEMO_MEDUSA_ICE = ModelEntry(dataset_id="NEMO_MEDUSA_ICE",
                            variable=[VariableEntry(name="siconc",
                                                    plot_name="sea ice",
                                                    units="km")],
                            extent=extent,
                            file_format="netcdf",
                            output_path="NEMO-MEDUSA/NEMO_MEDUSA_2023_ICE.nc",
                            local_source=True,
                            ORCA=True)

    NEMO_MEDUSA_ICE.get_data()

    NEMO_MEDUSA_ICE.plot_ice_extent(longitude=30.0,html=html)


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
    units: str
    colourmap:str = None

@define
class ModelEntry:
    dataset_id: str
    variable: list[VariableEntry]
    extent: Extent
    output_path: str = None
    local_source: bool = False
    file_format: str = "zarr"
    ORCA: bool = False
    horizontal_resolution: float = (1/12)
    month: list[str] = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October","November", "December"]

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
            # TODO need to add a check here to ensure local data source has extent required
            pass

    def plot_transects(self,longitude:float,html:bool=False):
        # TODO need to figure out how to dynamically set these the start slice in particular
        latitude_start_slice = 69.5
        latitude_end_slice = 80
        assert self.extent.west <= longitude <= self.extent.east

        ds,max_valid_depth = self.__process_datasets()

        for j in range(self.variable.__len__()):
            # get max and min values of variable to set colour map range
            ds_var = ds[self.variable[j].name]
            # rename time and depth dimensions to be consistent
            if self.ORCA:
                ds_var = self.__regrid_ORCA(ds_var,var_name=self.variable[j].name)
            for i in range(self.month.__len__()):
                month_dt,next_month_dt = self.__create_month_dt(month=self.month[i])
                max_valid_vals,min_valid_vals = self.__colourmap_limits(ds_var,var_name=self.variable[j].name)
                # select based on valid values
                lon_slice = ds_var.longitude.sel(longitude=longitude, method='nearest').item()

                slice_ds = ds_var.sel(longitude=lon_slice,
                                      depth=slice(0, max_valid_depth),
                                      latitude=slice(latitude_start_slice, latitude_end_slice),
                                      time=slice(month_dt, next_month_dt)
                                      )
                # create colourmap
                if self.variable[j].colourmap is None:
                    colourmap = cmo.thermal
                elif self.variable[j].colourmap == "haline":
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
                    title=f'Latitude–Depth Transect: {self.variable[j].plot_name} {self.month[i]} {self.extent.year}',
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
                    os.makedirs(f"docs/{self.dataset_id}/{self.extent.year}/{self.month[i]}", exist_ok=True)
                    png_out = f"docs/{self.dataset_id}/{self.extent.year}/{self.month[i]}/{self.variable[j].name}.png"
                    hvplot.save((heatmap * contours), filename=png_out, fmt="png")

    def plot_ice_extent(self,longitude:float,html:bool=False):
        # TODO need to figure out how to dynamically set these the start slice in particular
        latitude_start_slice = 69.5
        latitude_end_slice = 80

        assert self.extent.west <= longitude <= self.extent.east
        ds,max_valid_depth = self.__process_datasets()

        for j in range(self.variable.__len__()):
            # get max and min values of variable to set colour map range
            ds_var = ds[self.variable[j].name]
            # rename time and depth dimensions to be consistent
            if self.ORCA:
                ds_var = self.__regrid_ORCA(ds_var,var_name=self.variable[j].name)
            ice_extents = []
            month_dts = []
            for i in range(self.month.__len__()):
                month_dt,next_month_dt = self.__create_month_dt(month=self.month[i])
                month_dts.append(month_dt)
                # select based on valid values
                lon_slice = ds_var.longitude.sel(longitude=longitude, method='nearest').item()
                slice_ds = ds_var.sel(longitude=lon_slice,
                                      latitude=slice(latitude_start_slice, latitude_end_slice),
                                      time=slice(month_dt, next_month_dt)
                                      )

                threshold = 0.05
                try:
                    ice = slice_ds[self.variable[j].name].values
                except KeyError:
                    # if its a dataarray rather than dataset then you get a key error
                    ice = slice_ds.values
                lat = slice_ds['latitude'].values
                extent_km = 0.0
                for k in range(len(ice[0]) - 1):
                    if ice[0][k] > threshold:
                        d = self.haversine(longitude, lat[k], longitude, lat[k + 1])
                        extent_km += d
                ice_extents.append(extent_km)
            df = pd.DataFrame({'extent': ice_extents},index=month_dts)
            extents = df.hvplot.line(
                                x='index',
                                y='extent',
                                title=f'Monthly Extent along Transect: {self.variable[j].plot_name} {self.month[i]} {self.extent.year}',
                                xlabel='Month',
                                ylabel='Extent (km)',
                                line_width=4,
                                width=1600,
                                height=600,
                            )
        if html:
            renderer = hv.renderer('bokeh')
            bokeh_plot = renderer.get_plot(extents).state
            show(bokeh_plot)
        else:
            os.makedirs(f"docs/{self.dataset_id}/{self.extent.year}/{self.month[i]}", exist_ok=True)
            png_out = f"docs/{self.dataset_id}/{self.extent.year}/{self.variable[j].name}.png"
            hvplot.save((extents), filename=png_out, fmt="png")



    # Haversine formula (returns distance in km)
    @staticmethod
    def haversine(lon1, lat1, lon2, lat2):
        R = 6371.0  # Earth radius in km
        lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(a))
        return R * c


    def __process_datasets(self) -> (xr.Dataset,int):

        # open dataset
        if self.file_format == "zarr":
            ds = xr.open_zarr(f"{self.output_path}.zarr", consolidated=True)
        elif self.file_format == "netcdf":
            ds = xr.open_dataset(f"{self.output_path}")
        else:
            raise Exception("unsupported file format")

        # if not self.ORCA:
        #     depth_key = "depth"
        # else:
        #     depth_key = "deptht"
        # # Mask depth coordinates where parameter is valid (not NaN)
        # valid_depths = ds[depth_key].where(~np.isnan(ds[self.variable[0].name]))
        # Find max valid depth
        max_valid_depth = 400  # valid_depths.max().values

        return ds,max_valid_depth

    def __regrid_ORCA(self,ds_var:xr.DataArray,var_name:str) -> xr.Dataset:
        # regrid ORCA grid to a regular one, rename variables and create valid cftime Datetime
        try:
            ds_var = ds_var.rename(
                {"deptht": "depth", "time_counter": "time", "nav_lat": "latitude", "nav_lon": "longitude"})
        except ValueError:
            # assume dataset is 2D
            ds_var = ds_var.rename(
                {"time_counter": "time", "nav_lat": "latitude", "nav_lon": "longitude"})
        ds_var = ds_var.where(ds_var != 0)
        lat = ds_var['latitude']
        lon = ds_var['longitude']
        lat_number = int((lat.max() - lat.min()) / self.horizontal_resolution)
        lon_number = int((lon.max() - lon.min()) / self.horizontal_resolution)
        # Define a regular grid with 1D lat/lon arrays
        target_lat = np.linspace(lat.min(), lat.max(), lat_number)
        target_lon = np.linspace(lon.min(), lon.max(), lon_number)
        # Create a target grid dataset
        target_grid = xr.Dataset({
            'latitude': (['latitude'], target_lat),
            'longitude': (['longitude'], target_lon)
        })
        # Create a regridder object to go from curvilinear to regular grid
        regridder = xe.Regridder(ds_var, target_grid, method='bilinear', ignore_degenerate=True)
        # Regrid the entire dataset
        ds_regridded = regridder(ds_var)
        # Add units to latitude and longitude coordinates
        ds_regridded['latitude'].attrs['units'] = 'degrees_north'
        ds_regridded['longitude'].attrs['units'] = 'degrees_east'
        # Convert all float32 variables in the dataset to float64
        ds_regridded = ds_regridded.astype('float64')
        # try and convert to dataset as it maybe an dataarray which is not compatible with contour plotting
        try:
            ds_var = ds_regridded.to_dataset(name=var_name)
        except AttributeError:
            pass
        ds_var = ds_var.where(ds_var != 0)
        return ds_var

    def __colourmap_limits(self,ds_var,var_name:str) -> (float,float):
        try:
            max_valid_vals = np.nanpercentile(ds_var[var_name].values, 95)
            min_valid_vals = np.nanpercentile(ds_var[var_name].values, 5)
        except KeyError:
            max_valid_vals = np.nanpercentile(ds_var.values, 95)
            min_valid_vals = np.nanpercentile(ds_var.values, 5)
        return max_valid_vals, min_valid_vals

    def __create_month_dt(self,month:str):
        # create start of month datetime object
        month_dt = datetime.strptime(f"{month} {self.extent.year}", "%B %Y")
        next_month_dt = month_dt + relativedelta(months=+1)
        if self.ORCA:
            # convert datetime objects to cftime ones
            month_dt = cftime.Datetime360Day(month_dt.year, month_dt.month, month_dt.day, 0, 0, 0, 0)
            next_month_dt = cftime.Datetime360Day(next_month_dt.year, next_month_dt.month, next_month_dt.day, 0,
                                                  0, 0, 0)
        return month_dt, next_month_dt






if __name__ == "__main__":
    main()