"""KDPBuilder: generate and assemble children's coloring books for Amazon KDP.

Pipeline stages follow the project workflow:
  1. prompts.py    build line-art prompts
  3-4. imageprep.py clean raw images to pure black-and-white, thicken lines
  5-6. assemble.py  scale to DPI and build a single-sided interior PDF
  gate. the kdp-compliance skill validates the finished PDF

Print specs are read from the shared kdp_specs.json via specs.py. Do not
duplicate the numbers anywhere else.
"""

from . import assemble, cover, generate, imageprep, prompts, scan, specs

__all__ = ["assemble", "cover", "generate", "imageprep", "prompts", "scan", "specs"]
__version__ = "0.1.0"
