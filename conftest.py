# -*- coding: utf-8 -*-
"""pytest icin proje kokunu sys.path'e ekler (core/ ve moduller/ import edilsin)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
