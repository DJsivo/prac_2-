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
    'auth.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\nauth.proto\x12\x04\x61uth\"!\n\x0eGetUserRequest\x12\x0f\n\x07user_id\x18\x01 \x01(\x05\"J\n\x0cGetUserReply\x12\r\n\x05\x66ound\x18\x01 \x01(\x08\x12\n\n\x02id\x18\x02 \x01(\x05\x12\x10\n\x08username\x18\x03 \x01(\t\x12\r\n\x05\x65mail\x18\x04 \x01(\t2B\n\x0b\x41uthService\x12\x33\n\x07GetUser\x12\x14.auth.GetUserRequest\x1a\x12.auth.GetUserReplyb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'auth_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_GETUSERREQUEST']._serialized_start=20
  _globals['_GETUSERREQUEST']._serialized_end=53
  _globals['_GETUSERREPLY']._serialized_start=55
  _globals['_GETUSERREPLY']._serialized_end=129
  _globals['_AUTHSERVICE']._serialized_start=131
  _globals['_AUTHSERVICE']._serialized_end=197
# @@protoc_insertion_point(module_scope)
