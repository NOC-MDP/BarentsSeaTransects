"""
This script enables the creation of model entries, that contain variable entries. Each variable entry is used in the creation
of a set of monthly transect plots for a specific longitude within a given extent. Optionally a monthly ice extent plot can
also be created.

The script can download CMEMS data (user needs to specify dataset id AND variable name) or use a local netcdf file.
It can handle ORCA grids by regridding them, and allows users to specify CMOCEAN colourmaps.

The example process shown below uses the Arctic Analysis and Forecast model availble from CMEMS and the NEMO MEDUSA SSP370
Class model run located on JASMIN.

NEMO-MEDUSA Model preprocessing steps:
1) subset using CDO on JASMIN, path used /gws/nopw/j04/class_vol1/CLASS-MEDUSA/OUT_eORCA12/C001/monthly/2023
    - cdo -select,name=siconc -sellonlatbox,29,31,69,80 eORCA12_MED_UKESM_y2023m01_icemod.nc /home/users/thopri/NEMO_MEDUSA_2023_01_ICE.nc
2) merge the 12 monthly files into one annual one
    -  cdo mergetime /home/users/thopri/NEMO_MEDUSA_2023_*ICE.nc /home/users/thopri/NEMO_MEDUSA_2023_ICE.nc
3) download to local PC:
    -  scp jas_phys_sci1:/home/users/thopri/NEMO_MEDUSA_2023_ICE.nc .

The code uses frozen classes for extent and variable entries reducing the risk of their parameters being altered after
creation/specification.

NOTE: the method __process_datasets in the model entry class currently hard codes the lat N and lat S and depth slices,
so these may need to be changed if the extent is changed.

"""
from core import Extent, ModelEntry, VariableEntry

def main():
    """
    creates transect plots, using the extent and Model Entries that are specified.
    :return:
    """
    html = False

    extent = Extent(year=2023,
                    north=85,
                    south=69,
                    east=31,
                    west=29
                    )
    # set the latitude start, end slices as well as depth slice. These may require tweaking
    latitude_n_slice = 85
    latitude_s_slice = 69.5
    depth_slice = 400

    # NEMO_MEDUSA_Phy = ModelEntry(dataset_id="NEMO_MEDUSA_Phy",
    #                              variable=[VariableEntry(name="thetao",
    #                                                      plot_name="temperature",
    #                                                      colourmap="thermal",
    #                                                      units="degreesC",
    #                              ),
    #                                         VariableEntry(name="so",
    #                                                      plot_name="salinity",
    #                                                      colourmap="haline",
    #                                                      units="PSU",
    #                                                      )
    #                                                    ],
    #                              extent=extent,
    #                              output_path="NEMO-MEDUSA/NEMO_MEDUSA_2023_T.nc",
    #                              ORCA=True
    #                              )
    #
    # NEMO_MEDUSA_BGC = ModelEntry(dataset_id="NEMO_MEDUSA_BGC",
    #                              variable=[VariableEntry(name="CHL",
    #                                                      plot_name="chlorophyll",
    #                                                      colourmap="algae",
    #                                                      units="mmolm-3",)],
    #                              extent=extent,
    #                              output_path="NEMO-MEDUSA/NEMO_MEDUSA_2023_CHL.nc",
    #                              ORCA=True)
    #
    # NEMO_MEDUSA_Phy.get_data()
    # NEMO_MEDUSA_BGC.get_data()
    #
    # NEMO_MEDUSA_BGC.plot_transects(longitude=30.0,html=html)
    # NEMO_MEDUSA_Phy.plot_transects(longitude=30.0,html=html)

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
    #                          file_format="zarr",
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
    #                         file_format="zarr",
    #                         extent=extent)
    #
    # Arctic_BGS.get_data()
    #
    # Arctic_BGS.plot_transects(longitude=30.0,html=html,lat_n_slice=latitude_n_slice,lat_s_slice=latitude_s_slice,depth_slice=depth_slice)
    # Arctic_Phys.plot_transects(longitude=30.0,html=html,lat_n_slice=latitude_n_slice,lat_s_slice=latitude_s_slice,depth_slice=depth_slice)

    Arctic_ICE = ModelEntry(dataset_id="cmems_mod_arc_phy_anfc_6km_detided_P1M-m",
                            variable=[VariableEntry(name="siconc",
                                                    plot_name="Sea Ice Extent",
                                                    units="% (0,1)",)],
                            extent=extent,
                            file_format="zarr",
                            )

    Arctic_ICE.get_data()
    Arctic_ICE.plot_map(html=html,lat_n_slice=latitude_n_slice,lat_s_slice=latitude_s_slice)
    #Arctic_ICE.plot_ice_extent(longitude=30.0,html=html,lat_s_slice=latitude_s_slice,lat_n_slice=latitude_n_slice)
    #
    # NEMO_MEDUSA_ICE = ModelEntry(dataset_id="NEMO_MEDUSA_ICE",
    #                         variable=[VariableEntry(name="siconc",
    #                                                 plot_name="sea ice",
    #                                                 units="km")],
    #                         extent=extent,
    #                         output_path="NEMO-MEDUSA/NEMO_MEDUSA_2023_ICE.nc",
    #                         ORCA=True)
    #
    # NEMO_MEDUSA_ICE.get_data()
    #
    # NEMO_MEDUSA_ICE.plot_ice_extent(longitude=30.0,html=html)

if __name__ == "__main__":
    main()