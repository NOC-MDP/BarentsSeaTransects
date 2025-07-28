import os
from datetime import datetime
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta
import copernicusmarine
import xarray as xr
import xesmf as xe
import holoviews as hv
import hvplot.xarray
import hvplot.pandas
from bokeh.io import show
from attrs import frozen, define
import cmocean.cm as cmo
import cftime
hv.extension('bokeh')

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
    file_format: str = "netcdf"
    ORCA: bool = False
    horizontal_resolution: float = (1/12)
    month: list[str] = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October","November", "December"]

    def get_data(self) -> ():
        """
        if no output path specified then data will be downloaded from CMEMS using the dataset id
        in the model entry and the varible entry names. If an output path is specified then the
        script will try and use the file specified. Supported data formats are zarr or netcdf.
        :return:
        """
        if self.output_path is None:
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
            # TODO need to add a check here to ensure local data source has extent and variables etc required
            pass

    def plot_transects(self,longitude:float,html:bool=False):
        """
        Creates monthly transect plots for every variable entry in the model entry
        :param longitude:
        :param html:
        :return:
        """
        # check longitude is within model entry extent
        assert self.extent.west <= longitude <= self.extent.east
        # get dataset, and depth and latitude/longitude slices
        ds,max_valid_depth,latitude_start_slice,latitude_end_slice = self.__process_datasets()
        # for each variable
        for j in range(self.variable.__len__()):
            # get the variable from the dataset
            ds_var = ds[self.variable[j].name]
            # if its an ORCA grid regrid to a regular grid
            if self.ORCA:
                ds_var = self.__regrid_ORCA(ds_var,var_name=self.variable[j].name)
            # for each month
            for i in range(self.month.__len__()):
                month_dt,next_month_dt = self.__create_month_dt(month=self.month[i])
                max_valid_vals,min_valid_vals = self.__colourmap_limits(ds_var,var_name=self.variable[j].name)
                # select slices by getting closest longitude
                lon_slice = ds_var.longitude.sel(longitude=longitude, method='nearest').item()
                # slicing dataset four ways!
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
                # export to html or png
                self.__export(heatmap*contours,html=html,var_name=self.variable[j].name,month=self.month[i])

    def plot_ice_extent(self,longitude:float,html:bool=False,threshold:float=0.05):
        """
        creates an annual ice extent plot for the longitude transect for every variable entry in the model entry
        :param longitude:
        :param html:
        :param threshold:
        :return:
        """
        # check longitude is within extent
        assert self.extent.west <= longitude <= self.extent.east
        # get dataset and depth, and lat/lon slices
        ds,max_valid_depth,latitude_start_slice,latitude_end_slice = self.__process_datasets()
        # for each variable
        for j in range(self.variable.__len__()):
            # get variable dataset
            ds_var = ds[self.variable[j].name]
            # regrid to regular grid if model is an ORCA grid
            if self.ORCA:
                ds_var = self.__regrid_ORCA(ds_var,var_name=self.variable[j].name)
            # create empty list to hold monthly ice extent and month datetimes
            ice_extents = []
            month_dts = []
            # for every month
            for i in range(self.month.__len__()):
                month_dt,next_month_dt = self.__create_month_dt(month=self.month[i])
                month_dts.append(month_dt)
                # select longitude slice based on nearest value
                lon_slice = ds_var.longitude.sel(longitude=longitude, method='nearest').item()
                # slice three ways!
                slice_ds = ds_var.sel(longitude=lon_slice,
                                      latitude=slice(latitude_start_slice, latitude_end_slice),
                                      time=slice(month_dt, next_month_dt)
                                      )
                try:
                    ice = slice_ds[self.variable[j].name].values
                except KeyError:
                    # if its a data array rather than a dataset then you get a key error so retry without var name
                    ice = slice_ds.values
                lat = slice_ds['latitude'].values
                extent_km = 0.0
                # calculate extent for every grid cell along transect
                for k in range(len(ice[0]) - 1):
                    # if ice conc is above threshold
                    if ice[0][k] > threshold:
                        # calculate distance between current and next point
                        d = self.haversine(longitude, lat[k], longitude, lat[k + 1])
                        # added to current monthly extent
                        extent_km += d
                ice_extents.append(extent_km)
            # create dataframe from list of monthly extents and list of month datetimes
            df = pd.DataFrame({'extent': ice_extents},index=month_dts)
            extents = df.hvplot.line(
                                x='index',
                                y='extent',
                                title=f'Monthly Extent along Transect: {self.variable[j].plot_name} {self.extent.year}',
                                xlabel='Month',
                                ylabel='Extent (km)',
                                line_width=4,
                                width=1600,
                                height=600,
                            )
            # export plots
            self.__export(extents,html=html,var_name=self.variable[j].name,month="Annual")


    def __export(self,hvplots,html:bool,month:str,var_name:str) -> ():
        """
        exports the plots as either an interactive html page or png image.
        :param hvplots: hvplot object being exported
        :param html: bool true export as html, false export as png
        :param month: month name as a string (or if not monthly a suitable folder name to store under year folder)
        :param var_name: variable name as a string
        """
        if html:
            renderer = hv.renderer('bokeh')
            bokeh_plot = renderer.get_plot(hvplots).state
            show(bokeh_plot)
        else:
            os.makedirs(f"docs/{self.dataset_id}/{self.extent.year}/{month}", exist_ok=True)
            png_out = f"docs/{self.dataset_id}/{self.extent.year}/{month}/{var_name}.png"
            hvplot.save(hvplots, filename=png_out, fmt="png")

    @staticmethod
    def haversine(lon1, lat1, lon2, lat2):
        """
        Haversine formula returns distance between two points in km
        :param lon1:
        :param lat1:
        :param lon2:
        :param lat2:
        :return:
        """
        R = 6371.0  # Earth radius in km
        lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(a))
        return R * c

    def __process_datasets(self) -> (xr.Dataset,int,float,float):
        """
        Opens input datasets as a xarray dataset, and not much else!
        :return:
        """
        # open dataset
        if self.file_format == "zarr":
            ds = xr.open_zarr(f"{self.output_path}.zarr", consolidated=True)
        elif self.file_format == "netcdf":
            ds = xr.open_dataset(f"{self.output_path}")
        else:
            raise Exception("unsupported file format")

        # TODO do a better job here than a hardcoded depths and lat slices
        # if not self.ORCA:
        #     depth_key = "depth"
        # else:
        #     depth_key = "deptht"
        # # Mask depth coordinates where parameter is valid (not NaN)
        # valid_depths = ds[depth_key].where(~np.isnan(ds[self.variable[0].name]))
        # Find max valid depth
        max_valid_depth = 400  # valid_depths.max().values
        latitude_start_slice = 69.5
        latitude_end_slice = 80

        return ds,max_valid_depth,latitude_start_slice,latitude_end_slice

    def __regrid_ORCA(self,ds_var:xr.DataArray,var_name:str) -> xr.Dataset:
        """
        Regrid the NEMO ORCA grid to a regular spaced one.
        :param ds_var:
        :param var_name:
        :return:
        """
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
        """
        Determining colourmap limits for plotting purposes, any values outside of 5th and 95th percentiles are discarded.
        :param ds_var:
        :param var_name:
        :return:
        """
        try:
            max_valid_vals = np.nanpercentile(ds_var[var_name].values, 95)
            min_valid_vals = np.nanpercentile(ds_var[var_name].values, 5)
        except KeyError:
            max_valid_vals = np.nanpercentile(ds_var.values, 95)
            min_valid_vals = np.nanpercentile(ds_var.values, 5)
        return max_valid_vals, min_valid_vals

    def __create_month_dt(self,month:str):
        """
        Create the current and next month datetime objects.
        :param month:
        :return:
        """
        # create start of month datetime object
        month_dt = datetime.strptime(f"{month} {self.extent.year}", "%B %Y")
        next_month_dt = month_dt + relativedelta(months=+1)
        if self.ORCA:
            # convert datetime objects to cftime ones
            month_dt = cftime.Datetime360Day(month_dt.year, month_dt.month, month_dt.day, 0, 0, 0, 0)
            next_month_dt = cftime.Datetime360Day(next_month_dt.year, next_month_dt.month, next_month_dt.day, 0,
                                                  0, 0, 0)
        return month_dt, next_month_dt