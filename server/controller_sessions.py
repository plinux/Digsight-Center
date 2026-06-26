"""Controller session factories used by HTTP-facing code."""

from digsight_dxdcnet.session import DXDCNetSessionManager


def default_controller_session(udp_transport=None) -> DXDCNetSessionManager:
  return DXDCNetSessionManager(udp_transport)
