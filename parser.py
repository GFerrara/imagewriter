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
from typing import Iterator

from events import *


CHR_CODES = {           
                     0x21:'!', 0x22:'"', 0x23:'#', 0x24:'$', 0x25:'%', 0x26:'&', 0x27:'\'', 0x28: '(', 0x29:')', 0x2A: '*', 0x2B: '+', 0x2C: ',',  0x2D: '-', 0x2E: '.', 0x2F: '/'
        , 0x30:'0',  0x31:'1', 0x32:'2', 0x33:'3', 0x34:'4', 0x35:'5', 0x36:'6', 0x37:'7',  0x38: '8', 0x39:'9', 0x3A: ':', 0x3B: ';', 0x3C: '<',  0x3D: '=', 0x3E: '>', 0x3F: '?'
        , 0x40:'©',  0x41:'A', 0x42:'B', 0x43:'C', 0x44:'D', 0x45:'E', 0x46:'F', 0x47:'G',  0x48: 'H', 0x49:'I', 0x4A: 'J', 0x4B: 'K', 0x4C: 'L',  0x4D: 'M', 0x4E: 'N', 0x4F: 'O'
        , 0x50:'P',  0x51:'Q', 0x52:'R', 0x53:'S', 0x54:'T', 0x55:'U', 0x56:'V', 0x57:'W',  0x58: 'X', 0x59:'Y', 0x5A: 'Z', 0x5B: '[', 0x5C: '\\', 0x5D: ']', 0x5E: '^', 0x5F: '_'
        , 0x60:'\'', 0x61:'a', 0x62:'b', 0x63:'c', 0x64:'d', 0x65:'e', 0x66:'f', 0x67:'g',  0x68: 'h', 0x69:'i', 0x6A: 'j', 0x6B: 'k', 0x6C: 'l',  0x6D: 'm', 0x6E: 'n', 0x6F: 'o'
        , 0x70:'p',  0x71:'q', 0x72:'r', 0x73:'s', 0x74:'t', 0x75:'u', 0x76:'v', 0x77:'w',  0x78: 'x', 0x79:'y', 0x7A: 'z'
    }
CHARS     = {v: k for k, v in CHR_CODES.items()}

LF        = 0x0A
CR        = 0x0D
ESC       = 0x1B

verbose   = True


def bytes_to_int(bb: bytes):
    return int(bb.decode("ascii"))

def byte_to_hex(b: int):
    return f"{b:02X}"

def set_verbose(v: bool):
    global verbose
    verbose = v

def log(s: str):
    if not verbose: return
    print (s)

def inline_log(s: str):
    if not verbose: return
    print (s, end = " ")

def compact_log(s: str):
    if not verbose: return
    print (s, end = "")

def hex_dump_log(bb: bytes):
    if not verbose: return
    for b in bb:
        compact_log(f"{b:02X}")
    compact_log(" ")

def can_read_from(pos: int, length: int, size: int):
    # pos is zero-based, so its maximum accepted value is: size - 1. 
    # In other words pos must always satisfy this rule: 0 <= i < size 
    return pos + length < size

def parse_stream(stream: bytes) -> Iterator[Event]:
    F    = CHARS.get('F')
    G    = CHARS.get('G')
    L    = CHARS.get('L')
    S    = CHARS.get('S')
    T    = CHARS.get('T')
    c    = CHARS.get('c')
    r    = CHARS.get('r')

    class PageContext:
        def __init__(self):        
            self.current_x         = 0
            self.offset_y          = 0
            self.left_margin       = 0
            self.vertical_unit     = 0

    i                 = 0
    stream_size       = len(stream)
    page              = 0
    page_context      = PageContext()

    while i < stream_size:
        if (stream[i] == ESC):
            inline_log ("ESC")
            
            if not can_read_from(i, 1, stream_size):
                break

            if (stream[i + 1] == CHARS.get('?')):
                inline_log ("?")

                yield (NewPrintJob())

                i += 2
                continue

            elif (stream[i + 1] == r):
                inline_log ("r")

                page         = page + 1
                page_context = PageContext()
                inline_log (f"[page: {page:02d}]")

                yield (NewPage())

                i += 2
                continue

            elif (stream[i + 1] == c):
                inline_log ("c")

                # ESC c can be seen as an alternative to the combination of ESC ? and ESC r

                yield (NewPrintJob())

                page         = page + 1
                page_context = PageContext()
                inline_log (f"[page: {page:02d}]")

                yield (NewPage())

                i += 2
                continue

            elif (stream[i + 1] == F):
                inline_log ("F")
                i += 1

                # i now points to F. Let's check this pattern Fdddd
                if not can_read_from(i, 4, stream_size):
                    break

                offset_x = bytes_to_int(stream[i + 1:i + 5])
                inline_log (f"{offset_x:04d}")
                page_context.current_x = page_context.left_margin + offset_x
                
                yield (SetXRelativeToMargin(offset_x))
                
                i += 5
                continue

            elif (stream[i + 1] == G or stream[i + 1] == S):
                inline_log (str(CHR_CODES.get(stream[i + 1])))
                i += 1

                # i now points to G (or S). Let's check this pattern Gdddd (or Sdddd)
                if not can_read_from(i, 4, stream_size):
                    break

                nnnn = bytes_to_int(stream[i + 1:i + 5])
                inline_log (f"{nnnn:04d} [dx: {page_context.current_x:04d} - dy: {page_context.offset_y:04d} - Mx: {(page_context.current_x + nnnn):04d} - size: {nnnn:04d}]")
                i += 4

                if not can_read_from(i, nnnn, stream_size):
                    nnnn = stream_size - (i + 1)
                    if nnnn == 0:
                        break

                i += 1
                # i now points to the first band element
                band = stream[i:i + nnnn]
                hex_dump_log (band)
                
                yield (GraphicBand(nnnn, band))

                offset_y = 0
                i += nnnn
                continue

            elif (stream[i + 1] == L):
                inline_log ("L")
                i += 1
                
                # i now points to L. Let's check this pattern Lddd
                if not can_read_from(i, 3, stream_size):
                    break

                page_context.left_margin = bytes_to_int(stream[i + 1:i + 4])
                inline_log (f"{page_context.left_margin:03d}")
                
                yield (SetLeftMargin(page_context.left_margin))

                i += 4
                continue
            
            elif (stream[i + 1] == T):
                inline_log ("T")
                i += 1
                
                # i now points to T. Let's check this pattern Tdd
                if not can_read_from(i, 2, stream_size):
                    break

                page_context.vertical_unit = bytes_to_int(stream[i + 1:i + 3])
                inline_log (f"{page_context.vertical_unit:02d}")
                
                yield (SetVerticalUnit(page_context.vertical_unit))

                i += 3
                continue

            elif (stream[i + 1] in CHR_CODES):
                inline_log (str(CHR_CODES.get(stream[i + 1])))
                i += 2
                continue
            
        elif (stream[i] == CR):
            log ("[CR]")
            i += 1
            continue

        elif (stream[i] == LF):
            log ("[LF]")
            dots_per_lf = (page_context.vertical_unit + 1) // 2
            page_context.offset_y += dots_per_lf

            yield (LineFeed())

            i += 1
            continue

        inline_log (byte_to_hex(stream[i]))    
        i += 1
    
    log("\n")

def parse_args():
    parser = argparse.ArgumentParser(
        description="ImageWriter stream decoder"
    )
    parser.add_argument(
        "input",
        help="ImageWriter input stream file"
    )
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable logging output"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    set_verbose (args.verbose)
    
    with open(args.input, "rb") as f:
        stream = f.read()
    
    for ev in parse_stream(stream):
        pass

if __name__ == "__main__":
    main()