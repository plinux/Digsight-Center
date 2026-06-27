class _FakeUdpExchangeBase:
  def __init__(self):
    self.requests = []

  def _record_request(self, host, port, payload, local_port, max_packets, stop_when):
    self.requests.append({
      "host": host,
      "port": port,
      "payload": payload,
      "local_port": local_port,
      "max_packets": max_packets,
      "stop_when": bool(stop_when),
    })

  def _bounded_responses(self, batch, max_packets, stop_when):
    responses = []
    for response in batch[:max_packets]:
      responses.append(response)
      if stop_when and stop_when(response):
        break
    return responses


class FakeRequestMappedUdpTransport(_FakeUdpExchangeBase):
  def __init__(self, responses_by_request):
    super().__init__()
    self.responses_by_request = responses_by_request

  def exchange(self, host, port, payload, local_port=0, max_packets=32, stop_when=None):
    self._record_request(host, port, payload, local_port, max_packets, stop_when)
    return self._bounded_responses(self.responses_by_request.get(payload, []), max_packets, stop_when)


class FakeUdpTransport(_FakeUdpExchangeBase):
  def __init__(self, responses):
    super().__init__()
    self.responses = responses

  def exchange(self, host, port, payload, local_port=0, max_packets=32, stop_when=None):
    self._record_request(host, port, payload, local_port, max_packets, stop_when)
    return self._bounded_responses(self.responses, max_packets, stop_when)


class SequencedUdpTransport(_FakeUdpExchangeBase):
  def __init__(self, response_batches):
    super().__init__()
    self.response_batches = list(response_batches)

  def exchange(self, host, port, payload, local_port=0, max_packets=32, stop_when=None):
    self._record_request(host, port, payload, local_port, max_packets, stop_when)
    batch = self.response_batches.pop(0) if self.response_batches else []
    return self._bounded_responses(batch, max_packets, stop_when)
