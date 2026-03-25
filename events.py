# SPDX-License-Identifier: LicenseRef-ImageWriter-NC
# Copyright (c) 2026 Giorgio Ferrara

# ImageWriter Stream Decoder
# Copyright (c) 2026 Giorgio Ferrara
#
# This software is licensed for non-commercial use only.
# Commercial use requires a separate license agreement.
#
# See LICENSE and COMMERCIAL_LICENSE.md for details.


from dataclasses import dataclass

@dataclass
class NewPrintJob:
    pass

@dataclass
class NewPage:
    pass

@dataclass
class SetLeftMargin:
    left_margin: int

@dataclass
class SetXRelativeToMargin:
    x: int

@dataclass
class GraphicBand:
    size: int
    band: bytes

@dataclass
class SetVerticalUnit:
    vertical_unit: int

@dataclass
class LineFeed:
    pass

Event = NewPrintJob | NewPage | SetLeftMargin | SetXRelativeToMargin | GraphicBand | SetVerticalUnit | LineFeed