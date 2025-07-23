import xarray as xr

# Open datasets
data_ds = xr.open_dataset("NEMO-MEDUSA/NEMO_MEDUSA_2023_T.nc")
mask_ds = xr.open_dataset("NEMO-MEDUSA/tmesh_mask.nc")

# Choose the variables
data = data_ds["thetao"]
mask = mask_ds["tmask"]

# Align mask to data (this will broadcast or match dimensions where possible)
mask, data = xr.align(mask, data)

# Option 1: if 0 = valid, 1 = invalid
masked_data = data.where(mask == 0)

# Option 2: if 1 = valid, 0 = invalid (just flip the logic)
# masked_data = data.where(mask == 1)

# Save to new file
masked_data.to_netcdf("masked_data.nc")