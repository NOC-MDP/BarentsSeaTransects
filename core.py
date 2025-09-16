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
import cartopy.crs as ccrs
import multiprocessing as mp

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
    bathy_path: str = "GEBCO_2025_sub_ice.nc"
    traj_path: str = None
    export_path: str = None

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

    def plot_map(self, lat_n_slice: float, lat_s_slice: float, lon_e_slice: float, lon_w_slice: float,
                 html: bool = False, data_slice_n=90, further_south=10, plot_days=False):
        """ Creates monthly transect plots for every variable entry in the model entry
        :param plot_days:
        :param further_south: this slices data further south than requested plot extent, required for arctic plots due to extreme latitude curve
         :param data_slice_n: this slices data further north than the requested plotting extent, required for arctic plots.
         :param lon_w_slice:
         :param lon_e_slice:
         :param lat_s_slice:
         :param lat_n_slice:
         :param html:
         :return: """
        # check longitude is within model entry extent # get dataset, and depth and latitude/longitude slices
        ds = self.__process_datasets()
        for j in range(self.variable.__len__()):
            ds_var = ds[self.variable[j].name]
            if plot_days:
                plot_steps = 365
            else: plot_steps = 12
            for i in range(plot_steps):
                print(f"Plotting step {i+1}")
                max_valid_vals, min_valid_vals = self.__colourmap_limits(ds_var, var_name=self.variable[j].name)
                if plot_days:
                    first_dt, next_dt = self.__create_day_dt(day_of_year=i+1)
                else:
                    first_dt, next_dt = self.__create_month_dt(month=self.month[i])
                # run plotting code in subprocess so that memory is constrained
                p = mp.Process(target=self._plot_one, args=(i,j,html,ds_var,first_dt,next_dt,max_valid_vals,min_valid_vals,
                                                             lat_s_slice,lat_n_slice,lon_e_slice,lon_w_slice,further_south,
                                                             data_slice_n,plot_days))
                p.start()
                p.join()
                if p.exitcode !=0:
                    raise RuntimeError(f"Process exited with code {p.exitcode}")
    # plotting function to plot a single map (wrapped in subprocess to ensure memory is constrained)
    def _plot_one(self,i,j,html,ds_var,first_dt,next_dt,max_valid_vals,min_valid_vals,
                   lat_s_slice,lat_n_slice,lon_e_slice,lon_w_slice,further_south,
                   data_slice_n,plot_days):
        # ds_var = ds_var.where(ds_var != 0, np.nan)
        # ds_var_renamed = ds_var.rename( # {"time_counter": "time", "lat": "latitude", "lon": "longitude"})
        # slicing dataset four ways!
        slice_ds = ds_var.sel( latitude=slice(lat_s_slice-further_south, data_slice_n), time=slice(first_dt, next_dt) )
        # create colourmap
        if self.variable[j].colourmap is None:
            colourmap = cmo.thermal
        elif self.variable[j].colourmap == "haline":
            colourmap = cmo.haline
        elif self.variable[j].colourmap == "algae":
            colourmap = cmo.algae
        elif self.variable[j].colourmap == "thermal":
            colourmap = cmo.thermal
        elif self.variable[j].colourmap == "ice":
            colourmap = cmo.ice
        else: raise Exception(f"Unknown colourmap: {self.variable[j].colourmap}")
        #tiles = gv.tile_sources.EsriOceanBase()
        # hvplots = gv.util.get_tile_rgb(tiles, bbox=(-40, 60, 100, 85),
        # zoom_level=5).opts(width=1000, # height=800, # #projection=ccrs.NorthPolarStereo() # )
        # Plot with HoloViews (heatmap with contours)
        if plot_days:
            plot_title = f'{self.variable[j].plot_name} Map: Day {i+1} {self.extent.year}'
        else:
            plot_title = f'{self.variable[j].plot_name} Map: {self.month[i]} {self.extent.year}'

        heatmap = slice_ds.hvplot.quadmesh( y='latitude',
                                            x='longitude',
                                            cmap=colourmap,
                                            colorbar=True,
                                            title=plot_title,
                                            width=1000, height=800,
                                            clabel=self.variable[j].units,
                                            clim=(min_valid_vals, max_valid_vals),
                                            crs=ccrs.PlateCarree(),
                                            projection=ccrs.NorthPolarStereo(),
                                            project=True,
                                            rasterize=True,
                                            features={"coastline":'50m','borders':'50m','ocean':'50m','land':'50m'},
                                            ylim=(lat_s_slice, lat_n_slice), xlim=(lon_w_slice, lon_e_slice), )
        if plot_days:
            id_str = f"{self.variable[j].name}_day_{i+1}_{lat_n_slice}_{lat_s_slice}_{lon_e_slice}_{lon_w_slice}"
        else:
            id_str = f"{self.variable[j].name}_{self.month[i]}_{lat_n_slice}_{lat_s_slice}_{lon_e_slice}_{lon_w_slice}"

        self.__export(heatmap, html=html, id_str=id_str)

    def plot_transects(self,longitude:float,lat_n_slice:float,lat_s_slice:float,depth_slice:float,html:bool=False,add_trajectory:bool=False):
        """
        Creates monthly transect plots for every variable entry in the model entry
        :param depth_slice:
        :param lat_s_slice:
        :param lat_n_slice:
        :param longitude:
        :param html:
        :return:
        """
        # check longitude is within model entry extent
        assert self.extent.west <= longitude <= self.extent.east
        assert lat_s_slice <= lat_n_slice
        assert self.extent.south <= lat_s_slice <= self.extent.north
        assert self.extent.south <= lat_n_slice <= self.extent.north
        # get dataset, and depth and latitude/longitude slices
        ds = self.__process_datasets()
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
                # open and slice bathy
                bathy_ds = xr.open_dataset(self.bathy_path)
                bathy_var = bathy_ds["elevation"]
                bathy_lon_slice = bathy_ds.lon.sel(lon=longitude, method='nearest').item()
                bathy_slice = bathy_var.sel(lon=bathy_lon_slice,lat=slice(lat_s_slice, lat_n_slice))
                bathy_slice = bathy_slice * -1

                # construct polygon coordinates
                x_vals = bathy_slice["lat"].values
                bathy_vals = bathy_slice.values

                # polygon that goes from bathy down to max depth
                x_poly = np.concatenate([x_vals, x_vals[::-1]])
                y_poly = np.concatenate([bathy_vals, np.full_like(x_vals, depth_slice)])

                bathy_polygon = hv.Polygons([{"x": x_poly, "y": y_poly}]).opts(
                    fill_color="gray",  # or background colour
                    line_color="black"
                )
                # slicing dataset four ways!
                slice_ds = ds_var.sel(longitude=lon_slice,
                                      depth=slice(0, depth_slice),
                                      latitude=slice(lat_s_slice, lat_n_slice),
                                      time=slice(month_dt, next_month_dt)
                                      )
                # interpolate to fill gaps at bottom due to coarse grid and fine bathy
                slice_ds_interp = slice_ds.interpolate_na(dim="latitude")
                slice_ds_interp = slice_ds_interp.ffill(dim="depth")

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
                # clip dataset to match colourmap
                slice_ds_clipped = slice_ds_interp.clip(min_valid_vals, max_valid_vals)
                # Plot with HoloViews (heatmap with contours)
                heatmap = slice_ds_clipped.hvplot.contourf(
                    x='latitude',
                    y='depth',
                    cmap=colourmap,
                    colorbar=True,
                    flip_yaxis=True,
                    title=f'Latitude–Depth Transect: {self.variable[j].plot_name} {self.month[i]} {self.extent.year}',
                    width=1600,
                    height=600,
                    clabel=self.variable[j].units,
                    clim=(min_valid_vals, max_valid_vals),
                    xlim=(lat_s_slice,lat_n_slice),
                    ylim=(0,depth_slice),
                    levels=50,
                )
                if self.traj_path is not None and add_trajectory:
                    waypoints = pd.read_csv(self.traj_path)
                    trajectory = waypoints.hvplot.line(
                        x="latitude",
                        y="depth",
                        color="black",
                        line_width=2,
                        legend=False
                    )
                    id_str = f"{self.variable[j].name}_{self.month[i]}_{longitude}_{lat_n_slice}_{lat_s_slice}_{depth_slice}_trajectory"
                    self.__export(heatmap * bathy_polygon * trajectory, html=html, id_str=id_str)
                elif self.traj_path is None and add_trajectory:
                    raise Exception("No trajectory available please set trajectory path in model entry")
                else:
                    id_str = f"{self.variable[j].name}_{self.month[i]}_{longitude}_{lat_n_slice}_{lat_s_slice}_{depth_slice}"
                    # export to html or png
                    self.__export(heatmap*bathy_polygon,html=html,id_str=id_str)
        ds.close()

    def plot_ice_extent(self,longitude:float,lat_n_slice:float,lat_s_slice:float,html:bool=False,threshold:float=0.05):
        """
        creates an annual ice extent plot for the longitude transect for every variable entry in the model entry
        :param lat_s_slice:
        :param lat_n_slice:
        :param longitude:
        :param html:
        :param threshold:
        :return:
        """
        # check longitude is within extent
        assert self.extent.west <= longitude <= self.extent.east
        assert lat_s_slice <= lat_n_slice
        assert self.extent.south <= lat_s_slice <= self.extent.north
        assert self.extent.south <= lat_n_slice <= self.extent.north
        # get dataset and depth, and lat/lon slices
        ds = self.__process_datasets()
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
                                      latitude=slice(lat_s_slice, lat_n_slice),
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
            id_str = f"{self.variable[j].name}_Monthy_Ice_Extent"
            self.__export(extents,html=html,id_str=id_str)
        ds.close()



    def __export(self,hvplots,html:bool,id_str:str) -> ():
        """
        exports the plots as either an interactive html page or png image.
        :param hvplots: hvplot object being exported
        :param html: bool true export as html, false export as png
        """
        if html:
            renderer = hv.renderer('bokeh')
            bokeh_plot = renderer.get_plot(hvplots).state
            show(bokeh_plot)
        else:
            if self.export_path is not None:
                os.makedirs(self.export_path,exist_ok=True)
                png_out = f"{self.export_path}/{id_str}.png"
            else:
                os.makedirs(f"docs/{self.dataset_id}/{self.extent.year}/", exist_ok=True)
                png_out = f"docs/{self.dataset_id}/{self.extent.year}/{id_str}.png"
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

    def __process_datasets(self) -> xr.Dataset:
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

        return ds

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
                {"deptht": "depth", "time_counter": "time", "lat": "latitude", "lon": "longitude"})
        except ValueError:
            # maybe different lat/lon names?
            try:
                ds_var = ds_var.rename(
                    {"deptht": "depth", "time_counter": "time", "nav_lat": "latitude", "nav_lon": "longitude"})
            # assume dataset is 2D
            except ValueError:
                ds_var = ds_var.rename(
                    {"time_counter": "time", "lat": "latitude", "lon": "longitude"})
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

    @staticmethod
    def __colourmap_limits(ds_var, var_name:str) -> (float, float):
        """
        Determining colourmap limits for plotting purposes, any values outside of 5th and 95th percentiles are discarded.
        :param ds_var:
        :param var_name:
        :return:
        """
        try:
            max_valid_vals = np.nanpercentile(ds_var[var_name].values,98)
            min_valid_vals = np.nanpercentile(ds_var[var_name].values,2)
        except KeyError:
            max_valid_vals = np.nanpercentile(ds_var.values,98)
            min_valid_vals = np.nanpercentile(ds_var.values,2)
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

    def __create_day_dt(self,day_of_year:int):
        """
        Create the current and next month datetime objects.
        :param month:
        :return:
        """
        # create start of month datetime object
        month_dt = datetime.strptime(f"{day_of_year:03} {self.extent.year}", "%j %Y")
        next_month_dt = month_dt + relativedelta(months=+1)
        if self.ORCA:
            # convert datetime objects to cftime ones
            month_dt = cftime.Datetime360Day(month_dt.year, month_dt.month, month_dt.day, 0, 0, 0, 0)
            next_month_dt = cftime.Datetime360Day(next_month_dt.year, next_month_dt.month, next_month_dt.day, 0,
                                                  0, 0, 0)
        return month_dt, next_month_dt

    def _plot_one_map(args):
        """Worker function run in a separate process."""
        (self_obj, var_idx, step_idx, plot_days,
         lat_n_slice, lat_s_slice, lon_e_slice, lon_w_slice,
         html, data_slice_n, further_south) = args

        # re-open dataset inside the child (important!)
        ds = xr.open_zarr(
            f"{self_obj.output_path}.zarr",
            consolidated=True,
            chunks={"time": 1, "latitude": 256, "longitude": 256}
        )

        try:
            var = self_obj.variable[var_idx]
            if plot_days:
                first_dt, next_dt = self_obj.__create_day_dt(day_of_year=step_idx + 1)
                plot_title = f"{var.plot_name} Map: Day {step_idx + 1} {self_obj.extent.year}"
                id_str = f"{var.name}_day_{step_idx + 1}_{lat_n_slice}_{lat_s_slice}_{lon_e_slice}_{lon_w_slice}"
            else:
                first_dt, next_dt = self_obj.__create_month_dt(month=self_obj.month[step_idx])
                plot_title = f"{var.plot_name} Map: {self_obj.month[step_idx]} {self_obj.extent.year}"
                id_str = f"{var.name}_{self_obj.month[step_idx]}_{lat_n_slice}_{lat_s_slice}_{lon_e_slice}_{lon_w_slice}"

            # limits and colourmap
            max_valid_vals, min_valid_vals = self_obj.__colourmap_limits(ds, var_name=var.name)
            cmap_lookup = {"haline": cmo.haline, "algae": cmo.algae,
                           "thermal": cmo.thermal, "ice": cmo.ice}
            colourmap = cmap_lookup.get(var.colourmap, cmo.thermal)

            # select only needed data
            da = ds[var.name].sel(
                latitude=slice(lat_s_slice - further_south, data_slice_n),
                longitude=slice(lon_w_slice, lon_e_slice),
                time=slice(first_dt, next_dt)
            )
            field2d = da.mean(dim="time").load()

            heatmap = field2d.hvplot.quadmesh(
                y="latitude", x="longitude", cmap=colourmap,
                clim=(min_valid_vals, max_valid_vals),
                title=plot_title, clabel=var.units,
                width=1000, height=800,
                crs=ccrs.PlateCarree(), projection=ccrs.NorthPolarStereo(),
                project=True, rasterize=False,
                features={"coastline": "50m", "borders": "50m", "ocean": "50m", "land": "50m"},
                ylim=(lat_s_slice, lat_n_slice), xlim=(lon_w_slice, lon_e_slice),
            )

            self_obj.__export(heatmap, html=html, id_str=id_str)

        finally:
            ds.close()