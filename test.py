import xarray as xr
import numpy as np
import xesmf as xe
import pyproj

# --- Step 1: Load original Zarr dataset (lat/lon grid)
ds = xr.open_zarr("/Users/thopri/BarentsSeaTransects/copernicus_data/cmems_mod_arc_phy_anfc_6km_detided_P1M-m_siconc_85_69_31_29_2023-01-01_2023-12-31.zarr")  # Replace with your actual path
data_var = ds["siconc"]        # Replace with your variable name
lat = ds["latitude"]
lon = ds["longitude"]

# --- Step 2: Define source grid
ds_src = xr.Dataset({
    "latitude": (["latitude"], lat.data),
    "longitude": (["longitude"], lon.data),
})

# --- Step 3: Define target grid in EPSG:3571

# Create Arctic Stereographic projection
proj_3571 = pyproj.CRS("EPSG:3571")
proj_4326 = pyproj.CRS("EPSG:4326")
transformer = pyproj.Transformer.from_crs(proj_3571, proj_4326, always_xy=True)

# Define x/y grid in meters (EPSG:3571)
x = np.linspace(-2000000, 2000000, 500)
y = np.linspace(-2000000, 2000000, 500)
xx, yy = np.meshgrid(x, y)

# Transform grid centers to lat/lon
lon_out, lat_out = transformer.transform(xx, yy)

# Create target grid dataset
ds_tgt = xr.Dataset({
    "latitude": (["y", "x"], lat_out.data),
    "longitude": (["y", "x"], lon_out.data)
})

# --- Step 4: Create regridder and regrid
regridder = xe.Regridder(ds_src, ds_tgt, method="bilinear", periodic=False)
data_regridded = regridder(data_var.data)
print(data_regridded)
# --- Step 5: Build output dataset in EPSG:3571
ds_out = xr.Dataset(
    {"data_var": (["y", "x"], data_regridded)},
    coords={
        "x": ("x", x[0:len(data_regridded.x)]),
        "y": ("y", y[0:len(data_regridded.y)])
    },
    attrs={"crs": "EPSG:3571"}
)

# --- Step 6: Save to new Zarr
ds_out.to_zarr("output_3571.zarr", mode="w")
