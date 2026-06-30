"""DXDCNet controller-specific constants shared by adapter services."""

from server import models


CURRENT_LIMIT_PARAM_TO_MODE = {
  models.N_CURRENT_PARAM: models.TRACK_MODE_N,
  models.HO_CURRENT_PARAM: models.TRACK_MODE_HO,
  models.G_CURRENT_PARAM: models.TRACK_MODE_G,
  models.DC_CURRENT_PARAM: models.TRACK_MODE_DC,
}

PARAM_RAILCOM = 0x03
PARAM_SCREEN_BRIGHTNESS = 0x7E
PARAM_SCREEN_DIRECTION = 0x80
