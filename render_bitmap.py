# SPDX-License-Identifier: LicenseRef-ImageWriter-NC
# Copyright (c) 2026 Giorgio Ferrara

# ImageWriter Stream Decoder
# Copyright (c) 2026 Giorgio Ferrara
#
# This software is licensed for non-commercial use only.
# Commercial use requires a separate license agreement.
#
# See LICENSE and COMMERCIAL_LICENSE.md for details.


import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from PIL import Image

from parser import parse_stream, set_verbose
from events import *


@dataclass(frozen=True)
class Paper:
    width_mm:    int
    height_mm:   int
    dots_width:  int
    dots_height: int

A4 = Paper(
    width_mm    = 210,
    height_mm   = 297,
    dots_width  = 576,
    dots_height = 841
)

US_LETTER = Paper(
    width_mm    = 216,
    height_mm   = 279,
    dots_width  = 612,
    dots_height = 792
)

PAPER_FORMATS = {
    "A4":       A4,
    "USLetter": US_LETTER
}


Band = Tuple[int, int, bytes]        # offset_y, offset_x, graphic band


def get_print_job_pages_bands(stream: bytes, consider_all_jobs: bool = False) -> List[List[Band]]:
    class PageContext:
        def __init__(self):        
            self.current_x         = 0
            self.offset_y          = 0
            self.left_margin       = 0
            self.vertical_unit     = 0
            self.bands             = []

    page         = 0
    page_context = PageContext()
    out          = []              
    
    for ev in parse_stream(stream):
        if (isinstance(ev, NewPrintJob)):
            if page > 0 and  not consider_all_jobs :
                # Forget previous saved data: just keep last print job
                page         = 0
                out          = []
                page_context = PageContext()

        elif (isinstance(ev, NewPage)):
            if page > 0 :
                # Before processing a new page, store data of the previous one
                out.append(page_context.bands)

            page         = page + 1
            page_context = PageContext()

        elif isinstance(ev, SetLeftMargin):
            page_context.left_margin = ev.left_margin

        elif isinstance(ev, SetXRelativeToMargin):
            page_context.current_x = page_context.left_margin + ev.x
        
        elif isinstance(ev, GraphicBand):
            page_context.bands.append ((page_context.offset_y, page_context.current_x, ev.band))
            page_context.offset_y = 0
        
        elif isinstance(ev, SetVerticalUnit):
            page_context.vertical_unit = ev.vertical_unit

        elif isinstance(ev, LineFeed):
            dots_per_lf = (page_context.vertical_unit + 1) // 2
            page_context.offset_y += dots_per_lf

    if page_context.bands:
        # Store data of the last processed page
        out.append(page_context.bands)

    return out

def render_pages_bands(pages_bands: List[List[Band]], output: str, paper: Paper = A4,  page_sep: str = "_"
                       , center_horizontally: bool = False, center_vertically: bool = False
                       , margin_left: int = 0, margin_top: int = 0):
    
    def split_filename_and_extension():
        base, ext = os.path.splitext(output)

        if ext and 3 <= len(ext) <= 4:
            return base, ext
        return output, ''
    
    def output_page_info():
        parts = []

        if width > paper.dots_width:
            parts.append(f"Adapted width: {width} exceedes by: {width - paper.dots_width} dots page width")
        if height > paper.dots_height:
            parts.append(f"Adapted height: {height} exceedes by: {height - paper.dots_height} dots page height")
        if shift_x:
            parts.append(f"Margin left: {uniformed_margin_x if center_horizontally else margin_left} dots")
        if shift_y:
            parts.append(f"Margin top: {uniformed_margin_y if center_vertically else margin_top} dots")

        if parts :
            print(f"{image_name}...")
            print("\t" + "\n\t".join(parts))
            print("saved")
        else:
            print (f"{image_name} saved")
    
    name, ext   = split_filename_and_extension() 
    page        = 0

    for bands in pages_bands:
        # Compute max x and y as well as min x and y
        Mx     = max((current_x + len(band) for _, current_x, band in bands), default = 0)
        My     = sum(offset_y for offset_y, _, _ in bands) + 8 # default is 0
        mx     = min((current_x for _, current_x, _ in bands), default = 0)
        my     = bands[0][0] if bands else 0
        
        # Image width and heigth are those of choiced paper, adapted to printed image if not contained
        width  = paper.dots_width if margin_left + Mx <= paper.dots_width else margin_left + Mx
        height = paper.dots_height if margin_top + My <= paper.dots_height else margin_top + My

        # Compute margin x and y in case print has to be centered either horizontally or vertically
        uniformed_margin_x = (width - (Mx - mx)) // 2
        uniformed_margin_y = (height - (My - my)) // 2
        # Compute how many pixels to shift if print has to be centered
        shift_x = uniformed_margin_x - mx if center_horizontally else margin_left - mx if margin_left else 0
        shift_y = uniformed_margin_y - my if center_vertically else margin_top - my if margin_top else 0

        page       = page + 1   
        image_name = f"{name}{page_sep}{page:03d}{'.png' if ext == '' else ext}"  # default one

        img = Image.new("1", (width, height), 1)
        px = img.load()

        y = 0
        for offset_y, current_x, band in bands:
            y += offset_y
            for x, byte in enumerate(band):
                for bit in range(8):
                    if (byte >> bit) & 1:
                        pixel_x = shift_x + current_x + x
                        pixel_y = shift_y + y + bit
                        px[pixel_x, pixel_y] = 0    
        # Ignore possible blanks after the last band
        
        img.save(image_name)
        output_page_info()

def parse_args():

    def bounded_int_0_100(value: str) -> int:
        ivalue = int(value)
        if not (0 <= ivalue <= 100):
            raise argparse.ArgumentTypeError(
                "Value must be between 0 and 100"
            )
        return ivalue
    
    parser = argparse.ArgumentParser(
        description="ImageWriter stream decoder and renderer"
    )
    parser.add_argument(
        "input",
        help="ImageWriter input stream file"
    )
    parser.add_argument(
        "output",
        help="Output base name (optionally with extension).\n"
             "A page number is appended automatically.\n"
             "Example: /home/user/output.png → /home/user/output_001.png, /home/user/output_002.png"
    )
    parser.add_argument(
        "--page-sep",
        default="_",
        help="Separator between output name and page number (default: '_'). Use '' for no separator."
    )
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable logging output"
    )
    parser.add_argument(
        "--paper-format",
        choices=["A4", "USLetter"],
        default="A4",
        help="Paper format (default: A4)"
    )
    parser.add_argument(
        "--center-horizontally",
        action="store_true",
        help="Center the print horizontally on the page"
    )
    parser.add_argument(
        "--center-vertically",
        action="store_true",
        help="Center the print vertically on the page"
    )
    parser.add_argument(
        "--margin-left",
        type=bounded_int_0_100,
        default=0,
        help="Left margin (0–100, default: 0)"
    )
    parser.add_argument(
        "--margin-top",
        type=bounded_int_0_100,
        default=0,
        help="Top margin (0–100, default: 0)"
    )
    parser.add_argument(
        "--all-jobs",
        action="store_true",
        help="Consider all print jobs"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    set_verbose (args.verbose)
    
    with open(args.input, "rb") as f:
        stream = f.read() 
    
    page_bands = get_print_job_pages_bands(stream, args.all_jobs)
    render_pages_bands(page_bands, args.output, PAPER_FORMATS[args.paper_format]
                       , args.page_sep, args.center_horizontally, args.center_vertically
                       , args.margin_left, args.margin_top)
    
if __name__ == "__main__":
    main()