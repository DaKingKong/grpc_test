# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings

from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2
import ringcx_streaming_pb2 as ringcx__streaming__pb2

GRPC_GENERATED_VERSION = '1.71.0'
GRPC_VERSION = grpc.__version__
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    raise RuntimeError(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + f' but the generated code in ringcx_streaming_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class StreamingStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Stream = channel.stream_unary(
                '/ringcentral.ringcx.streaming.v1beta2.Streaming/Stream',
                request_serializer=ringcx__streaming__pb2.StreamEvent.SerializeToString,
                response_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                _registered_method=True)


class StreamingServicer(object):
    """Missing associated documentation comment in .proto file."""

    def Stream(self, request_iterator, context):
        """For each Dialog, gRPC client makes single 'Stream' call toward server and all 'StreamEvent' messages are sent over the established stream
        Server does not return any response/stream back
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_StreamingServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Stream': grpc.stream_unary_rpc_method_handler(
                    servicer.Stream,
                    request_deserializer=ringcx__streaming__pb2.StreamEvent.FromString,
                    response_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'ringcentral.ringcx.streaming.v1beta2.Streaming', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('ringcentral.ringcx.streaming.v1beta2.Streaming', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class Streaming(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def Stream(request_iterator,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.stream_unary(
            request_iterator,
            target,
            '/ringcentral.ringcx.streaming.v1beta2.Streaming/Stream',
            ringcx__streaming__pb2.StreamEvent.SerializeToString,
            google_dot_protobuf_dot_empty__pb2.Empty.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
