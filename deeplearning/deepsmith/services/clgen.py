import grpc
import math
import time
import typing
from absl import app
from absl import flags
from absl import logging
from concurrent import futures

from deeplearning.clgen import sample
from deeplearning.clgen.proto import model_pb2
from deeplearning.deepsmith.proto import deepsmith_pb2
from deeplearning.deepsmith.proto import generator_pb2
from deeplearning.deepsmith.proto import generator_pb2_grpc
from deeplearning.deepsmith.services import generator
from deeplearning.deepsmith.services import services


FLAGS = flags.FLAGS


def ClgenInstanceToGenerator(
    instance: sample.Instance) -> deepsmith_pb2.Generator:
  """Convert a CLgen instance to a DeepSmith generator proto."""
  g = deepsmith_pb2.Generator()
  g.name = f'clgen'
  g.opts['model'] = instance.model.path
  g.opts['sampler'] = instance.sampler.hash
  return g


class ClgenGenerator(generator.GeneratorBase,
                     generator_pb2_grpc.GeneratorServiceServicer):

  def __init__(self, config: generator_pb2.ClgenGenerator):
    super(ClgenGenerator, self).__init__(config)
    self.instance = sample.Instance(self.config.instance)
    self.generator = ClgenInstanceToGenerator(self.instance)
    with self.instance.Session():
      self.instance.model.Train()

  def GetGeneratorCapabilities(
      self, request: generator_pb2.GetGeneratorCapabilitiesRequest,
      context) -> generator_pb2.GetGeneratorCapabilitiesResponse:
    del context
    response = services.BuildDefaultResponse(
        generator_pb2.GetGeneratorCapabilitiesRequest)
    response.toolchain = self.config.model.corpus.language
    response.generator = self.generator
    return response

  def GenerateTestcases(self, request: generator_pb2.GenerateTestcasesRequest,
                        context) -> generator_pb2.GenerateTestcasesResponse:
    del context
    response = services.BuildDefaultResponse(
        generator_pb2.GenerateTestcasesResponse)
    with self.instance.Session():
      num_programs = math.ceil(
          request.num_testcases / len(self.config.testcase_skeleton))
      samples = self.instance.model.Sample(self.instance.sampler, num_programs)
      for sample in samples:
        response.testcases.extend(self.SampleToTestcases(sample))
    return response

  def SampleToTestcases(self, sample: model_pb2.Sample) -> typing.List[
    deepsmith_pb2.Testcase]:
    """Convert a CLgen sample to a list of DeepSmith testcase protos."""
    testcases = []
    for skeleton in self.config.testcase_skeleton:
      t = deepsmith_pb2.Testcase()
      t.CopyFrom(skeleton)
      p = t.profiling_events.add()
      p.type = 'generation'
      p.duration_ms = sample.sample_time_ms
      p.event_start_epoch_ms = sample.sample_start_epoch_ms_utc
      t.inputs['src'] = sample.text
      testcases.append(t)
    return testcases


def main(argv):
  if len(argv) > 1:
    raise app.UsageError('Unrecognized arguments')
  generator_config = services.ServiceConfigFromFlag(
      'generator_config', generator_pb2.ClgenGenerator())
  server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
  services.AssertLocalServiceHostname(generator_config.service)
  service = ClgenGenerator(generator_config)
  generator_pb2_grpc.add_GeneratorServiceServicer_to_server(service, server)
  server.add_insecure_port(f'[::]:{generator_config.service.port}')
  logging.info('%s listening on %s:%s', type(service).__name__,
               generator_config.service.hostname, generator_config.service.port)
  server.start()
  try:
    while True:
      time.sleep(3600 * 24)
  except KeyboardInterrupt:
    server.stop(0)


if __name__ == '__main__':
  app.run(main)
