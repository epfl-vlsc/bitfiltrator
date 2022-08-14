# Bitfiltrator

## Introduction

Bitfiltrator is an automated *bitstream parameter extraction* tool for Xilinx UltraScale and UltraScale+ FPGAs.

Bitstream parameters are a series of device- and architecture-specific constants that are needed to locate the position of certain configuration bits in a bitstream. These parameters are the basis for implementing bitstream manipulation tools or open-source FPGA toolchains for modern US/US+ devices.

All extracted parameters are stored in human/machine-readable files. Pre-generated versions of these files are available in the [resources](./resources) directory.

### Demo (locating configuration bits for named BELs)

The [demo.py](src/demo.py) file contains a short program that prints out the SLR name, frame addresses, and frame offsets of any LUT, Flip-Flop, and 18K BRAM given as argument.

```python
╰─❯ python3 demo.py -h
usage: demo.py [-h] [--luts [LUTS ...]] [--ffs [FFS ...]] [--brams [BRAMS ...]] bitstream

Demo application that locates a resource and prints its SLR name, frame addresses, and frame offsets.

positional arguments:
  bitstream            Input bitstream (with header). Must be a full bitstream, not a partial one.

options:
  -h, --help           show this help message and exit
  --luts [LUTS ...]    Name of LUTs to locate in the form of SLICE_X(\d+)Y(\d+)/[A-H]6LUT
  --ffs [FFS ...]      Name of Flip-Flops to locate in the form of SLICE_X(\d+)Y(\d+)/[A-H]FF2?
  --brams [BRAMS ...]  Name of 18K BRAMs to locate in the form of RAMB18_X(\d+)Y(\d+)

╰─❯ python3 demo.py <xcu200.bit> --luts SLICE_X0Y13/B6LUT --ffs SLICE_X0Y13/GFF2 --brams RAMB18_X2Y12
SLICE_X0Y13/B6LUT
INIT[ 0] -> SLR0, frame address: 0x00000307 (BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR =   0, COL_ADDR =   3, MINOR_ADDR =   7), frame offset:  639
INIT[ 1] -> SLR0, frame address: 0x00000306 (BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR =   0, COL_ADDR =   3, MINOR_ADDR =   6), frame offset:  639
INIT[ 2] -> SLR0, frame address: 0x00000305 (BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR =   0, COL_ADDR =   3, MINOR_ADDR =   5), frame offset:  639
INIT[ 3] -> SLR0, frame address: 0x00000304 (BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR =   0, COL_ADDR =   3, MINOR_ADDR =   4), frame offset:  639
...
INIT[62] -> SLR0, frame address: 0x00000305 (BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR =   0, COL_ADDR =   3, MINOR_ADDR =   5), frame offset:  624
INIT[63] -> SLR0, frame address: 0x00000304 (BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR =   0, COL_ADDR =   3, MINOR_ADDR =   4), frame offset:  624

SLICE_X0Y13/GFF2
INIT -> SLR0, frame address: 0x0000030c (BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR =   0, COL_ADDR =   3, MINOR_ADDR =  12), frame offset:  668

RAMB18_X2Y12
INIT[    0] -> SLR0, frame address: 0x01000200 (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR =   0), frame offset: 1536
INIT[    1] -> SLR0, frame address: 0x01000200 (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR =   0), frame offset: 1548
INIT[    2] -> SLR0, frame address: 0x01000200 (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR =   0), frame offset: 1560
INIT[    3] -> SLR0, frame address: 0x01000200 (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR =   0), frame offset: 1572
...
INIT[16382] -> SLR0, frame address: 0x010002ff (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR = 255), frame offset: 1631
INIT[16383] -> SLR0, frame address: 0x010002ff (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR = 255), frame offset: 1643
INIT_P[    0] -> SLR0, frame address: 0x01000200 (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR =   0), frame offset: 1584
INIT_P[    1] -> SLR0, frame address: 0x01000200 (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR =   0), frame offset: 1590
INIT_P[    2] -> SLR0, frame address: 0x01000200 (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR =   0), frame offset: 1587
INIT_P[    3] -> SLR0, frame address: 0x01000200 (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR =   0), frame offset: 1593
...
INIT_P[ 2046] -> SLR0, frame address: 0x010002ff (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR = 255), frame offset: 1589
INIT_P[ 2047] -> SLR0, frame address: 0x010002ff (BLOCK_TYPE = BRAM_CONTENT, ROW_ADDR =   0, COL_ADDR =   2, MINOR_ADDR = 255), frame offset: 1595
```

## Installation

Bitfiltrator is implemented entirely in Python (3.10) and Tcl. The easiest way to use Bitfiltrator is to set up its dependencies using a virtual environment. The instructions below use [conda](https://docs.conda.io/projects/conda/en/latest/) as the virtual environment management system, but you can easily perform a similar setup with other environment managers ([venv](https://docs.python.org/3/tutorial/venv.html), etc.) if you prefer.

Bitfiltrator was developed and tested on *Ubuntu 20.04* and *Vivado 2021.1*. It should run without issues on any machine that has Vivado and Python installed (using `conda` below).

```bash
# Download and install conda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/Downloads/Miniconda3-latest-Linux-x86_64.sh
cd ~/Downloads
./Miniconda3-latest-Linux-x86_64.sh

# Set up python 3.10 virtual environment called "bitfiltrator" and install dependencies
conda create -n bitfiltrator python=3.10
conda activate bitfiltrator
pip install joblib more_itertools numpy pandas
```

You must ensure the virtual environment is active and Vivado is available in your `PATH` before calling Bitfiltrator. This can generally be performed by executing the following commands:

```bash
conda activate bitfiltrator
source <xilinx-install-dir>/Vivado/<vivado-version>/settings64.sh
```

## Usage

### FPGA part files

Bitfiltrator reverse-engineers device/architecture parameters by creating carefully-crafted designs, generating bitstreams for them, and analyzing their binary structure. Since bitstreams are generated, Bitfiltrator needs to supply an FPGA part number to Vivado in each experiment. A pre-generated list of part numbers exists in [parts_all.json](./resources/parts_all.json) and [parts_webpack.json](./resources/parts_webpack.json). Bitfiltrator queries these lists internally.

However, these pre-generated lists may contain more devices than your *local* Vivado install supports. Running Bitfiltrator with these pre-generated lists may therefore cause Vivado to crash if it is asked to generate a bitstream for an unknown part number.

Deleting the pre-generated part files and generating them from your *local* Vivado installation solves the problem.

```bash
╰─❯ rm -f ./resources/parts_all.json
╰─❯ rm -f ./resources/parts_webpack.json
╰─❯ python3 src/generate_fpga_part_files.py
```

### Extracting device parameters (i.e., a device summary)

Use [create_device_summary.py](./src/create_device_summary.py) to extract device parameters for a given FPGA part number.

For example, the following command creates a device summary for the `xcu200` FPGA and places it in the default [resources/devices](./resources/devices/) directory. A copy of the device summary is also written to the user-requested file (`xcu200_summary.json` below).

```bash
╰─❯ python3 src/create_device_summary.py xcu200-fsgd2104-2-e <working-dir> <xcu200_summary.json>
```

__Please consider creating a pull request with your device parameter file if it is not part of the pre-generated list. In particular, we welcome PRs for non-WebPack devices :)__

### Extracting architecture parameters (i.e., an architecture summary)

Use [create_arch_summary.py](./src/create_arch_summary.py) to extract architecture parameters for a given FPGA part number.

Note that all US FPGAs have the same architecture summary, and that all US+ FPGAs have the same architecture summary (which is different from US FPGAs). It is therefore recommended to use the smallest FPGA that has the given target architecture when calling this program to reduce the size of bitstreams that are generated and analyzed. This significantly speeds up the processes of extracting architecture parameters.

For example, the following command creates an architecture summary for the `xazu2eg-sbva484-1-i` FPGA and places it in the default [resources/archs](./resources/archs/) directory. A copy of the architecture summary is also written to the user-requested file (`usplus_summary.json` below).

```bash
╰─❯ python3 src/create_arch_summary.py xazu2eg-sbva484-1-i <working-dir> <usplus_summary.json>
```

### Running all steps above automatically

The [run_all.py](./src/run_all.py) program creates device and architecture summaries for *all* WebPack-enabled US/US+ FPGAs available in your local Vivado installation. Note that this requires several GBs of disk space and takes several hours to complete depending on the speed and parallelism of your machine.

```bash
╰─❯ rm -f ./resources/parts_all.json
╰─❯ rm -f ./resources/parts_webpack.json
╰─❯ rm -f ./resources/archs/
╰─❯ rm -f ./resources/devices/
╰─❯ python3 src/run_all.py --verify <working-dir>
```

For reference, the end-to-end runtime for reverse-engineering 34 WebPack-enabled US/US+ FPGAs available in Vivado 2021.1 is ~3h on a Xeon E5-2680 v3 CPU (using `--process_cnt 24`). Disk space use for this process was ~16 GB.

# License

All code in this repository is available under the MIT license. Please refer to the [full license](./LICENSE) for details.

# About

This project was created by Sahand Kashani, Mahyar Emami, and James Larus at [EPFL](https://www.epfl.ch/en/).

A top-down explanation of how Bitfiltrator reverse-engineers the configuration bits of various cells can be found in the following [paper](./fpl22-bitfiltrator-paper.pdf) and [presentation](./fpl22-bitfiltrator-slides.pdf).

```
Sahand Kashani, Mahyar Emami, and James R. Larus. Bitfiltrator: A general approach for reverse-engineering Xilinx bitstream formats. In Proceedings of the 32nd International Conference on Field‐Programmable Logic and Applications, Belfast, August 2022.
```

If you'd like to cite this software, please use the following Bibtex entry:

```
@software{bitfiltrator,
  author = {Kashani, Sahand and Emami, Mahyar and R. Larus, James},
  license = {MIT},
  month = {8},
  title = {{Bitfiltrator: A general approach for reverse-engineering Xilinx bitstream formats}},
  url = {https://github.com/epfl-vlsc/bitfiltrator},
  version = {1.0},
  year = {2022}
}
```