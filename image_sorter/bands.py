"""Band definitions for MicaSense RedEdge-MX Dual Camera System.

Filename suffix (the trailing _N in IMG_NNNN_N.tif) maps to a specific band.
The dual system spans suffixes 1-10: 1-5 from the RED camera, 6-10 from the BLUE.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    suffix: int
    name: str
    folder: str
    center_nm: float
    bandwidth_nm: float
    camera: str  # "RED" or "BLUE"


BANDS: dict[int, Band] = {
    1:  Band(1,  "Blue",         "01_Blue_475",         475.0, 32.0, "RED"),
    2:  Band(2,  "Green",        "02_Green_560",        560.0, 27.0, "RED"),
    3:  Band(3,  "Red",          "03_Red_668",          668.0, 14.0, "RED"),
    4:  Band(4,  "NIR",          "04_NIR_842",          842.0, 57.0, "RED"),
    5:  Band(5,  "RedEdge_717",  "05_RedEdge_717",      717.0, 12.0, "RED"),
    6:  Band(6,  "CoastalBlue",  "06_CoastalBlue_444",  444.0, 28.0, "BLUE"),
    7:  Band(7,  "Green_531",    "07_Green_531",        531.0, 14.0, "BLUE"),
    8:  Band(8,  "Red_650",      "08_Red_650",          650.0, 16.0, "BLUE"),
    9:  Band(9,  "RedEdge_705",  "09_RedEdge_705",      705.0, 10.0, "BLUE"),
    10: Band(10, "RedEdge_740",  "10_RedEdge_740",      740.0, 18.0, "BLUE"),
}
