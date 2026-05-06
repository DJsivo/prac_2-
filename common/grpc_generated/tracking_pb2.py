"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    27,
    2,
    '',
    'tracking.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0etracking.proto\x12\x08tracking\"\'\n\x13InitTrackingRequest\x12\x10\n\x08order_id\x18\x01 \x01(\x05\"E\n\x11InitTrackingReply\x12\n\n\x02ok\x18\x01 \x01(\x08\x12\x13\n\x0btracking_id\x18\x02 \x01(\x05\x12\x0f\n\x07message\x18\x03 \x01(\t2e\n\x0fTrackingService\x12R\n\x14InitTrackingForOrder\x12\x1d.tracking.InitTrackingRequest\x1a\x1b.tracking.InitTrackingReplyb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'tracking_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_INITTRACKINGREQUEST']._serialized_start=28
  _globals['_INITTRACKINGREQUEST']._serialized_end=67
  _globals['_INITTRACKINGREPLY']._serialized_start=69
  _globals['_INITTRACKINGREPLY']._serialized_end=138
  _globals['_TRACKINGSERVICE']._serialized_start=140
  _globals['_TRACKINGSERVICE']._serialized_end=241
# @@protoc_insertion_point(module_scope)
