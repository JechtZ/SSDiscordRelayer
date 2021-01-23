import os

dev = os.environ.get('DEV', False)

from .main import *
if dev:
  try:
    from .dev import *
  except ModuleNotFoundError:
    pass
else:
  try:
    from .live import *
  except ModuleNotFoundError:
    pass
