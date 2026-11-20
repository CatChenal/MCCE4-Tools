#!/usr/bin/env python3
"""
Module: __init__.py
"""
__doc__ = """
H-bonding Microstates Tool: ms_hbnets2: ms_hbnets with states sampling enabled.

Outputs H-bonds information from microstates using the 'hah' file', the output of the
detect_hbonds tool.

Notes:
 - Loading of H-bond data is either for 'pairs' or for 'states', reflected in the
   ms_hbnets2 tool subcommands.
   This split follows the msout loading routines that differ for computational efficiency.

H-bonding pairs (identical to previous implementation):
 The main output of the 'pairs' subcommand is the hb_pairs_pH*.csv file. 
 It lists the occupied pairs over the entire space.

H-bonding states:
 1. Sampling is performed with a sample-pct default of 25 when the hb states
    data from the msout file is loaded for the first time.
 2. The default names of the output files are: hb_states_pH*_s25.csv and 
    hb_states_pairs_pH*_s25.csv; Meaning 25% of the randomly selected hb states
    in the dictionary are saved in hb_states_pH*_s25.csv.
 3. Behavior with the -sample-pct and --reload options:
   - Option 'sample-pct': 
       The percentage of hb states to save in the hb_states_pH*_s{sample_pct}.csv file;
   - If that file does not exist, reload is reset to True internally so that 
     the msout data is loaded & sampled for the number of hb states:
      (len(hb_states)*pct/100)
   - If that file already exists, it is used by the correlator for any requested
     filtering option unless --reload is included, in which case, a NEW sample of
     that size will be generated (and the previous hb_states_pH*_s25.csv file over-
     written), then any requested filtering option is applied.
   - Option 'reload': Entail reloading the msout file into a dictionary.
 4. The correlation on an unfiltered hb-states file will take longer than with 
    ms_hbnets (more rows to process).
 5. The information about the state space is found in the commented first line
    in hb_states_pH*.csv and hb_pairs_pH*.csv, obtained with this command:
      head -n1 hb_states_pH*.csv
 6. Histograms of the hb states is produced when the msout file is loaded for the
    first time. The file name follows this pattern: hbms_<pheh>_<space size>.png.
    See example in mcce4/ms_hbnets2/hbms_pH7.00eH0.00_1500000.png.

Option sasa-group: Integer categorizing the pairs by their SASA% using 0,2 as threshold.
    1: Both residues are exposed residues
    2: One residue is exposed, the other buried
    3: Both residues are buried
    0: The pair includes at least one residue backbone

Examples:
ms_hbnets2 states -ph 5                     # get hb states at a non-default pH
ms_hbnets2 states -sample-pct 10            # return a sample of hb microstates of size 10% x n_hb_states
ms_hbnets2 states -sample-pct 10 --reload   # get a new sample of hb microstates of size 10% x n_hb_states
ms_hbnets2 states -figsize-data ,8          # change the data heatmap height, w=7, h=8
ms_hbnets2 states -figsize-data ,,cm        # change the unit of the data heatmap to cm
ms_hbnets2 states -data-cbar-min 0.3        # change the cbar lowest bound of the data heatmap
ms_hbnets2 states -data-map-color Greens    # change the color of the data heatmap
ms_hbnets2 states -res-of-interest DEHK+BK  # filter for these residues (keep BK)
ms_hbnets2 states -res-of-interest DEHK+    # same as above
ms_hbnets2 states -sasa-group 3             # Filter for pairs that are both buried
"""

import logging
import sys


def setup_logging(level: str = "INFO"):
    """Configure logger to screen & file."""
    log_format = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                   datefmt='%m-%d %H:%M')
    screen_handler = logging.StreamHandler(sys.stdout)
    screen_handler.setFormatter(log_format)
    file_handler = logging.FileHandler("ms_hbnets2.log", encoding="utf-8")
    file_handler.setFormatter(log_format)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[screen_handler, file_handler],
    )


setup_logging()