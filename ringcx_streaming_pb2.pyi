from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Codec(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CODEC_UNSPECIFIED: _ClassVar[Codec]
    OPUS: _ClassVar[Codec]
    PCMA: _ClassVar[Codec]
    PCMU: _ClassVar[Codec]
    L16: _ClassVar[Codec]
    FLAC: _ClassVar[Codec]

class ProductType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRODUCT_TYPE_UNSPECIFIED: _ClassVar[ProductType]
    QUEUE: _ClassVar[ProductType]
    CAMPAIGN: _ClassVar[ProductType]
    IVR: _ClassVar[ProductType]

class DialogType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DIALOG_TYPE_UNSPECIFIED: _ClassVar[DialogType]
    INBOUND: _ClassVar[DialogType]
    OUTBOUND: _ClassVar[DialogType]

class ParticipantType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PARTICIPANT_TYPE_UNSPECIFIED: _ClassVar[ParticipantType]
    CONTACT: _ClassVar[ParticipantType]
    AGENT: _ClassVar[ParticipantType]
    BOT: _ClassVar[ParticipantType]
CODEC_UNSPECIFIED: Codec
OPUS: Codec
PCMA: Codec
PCMU: Codec
L16: Codec
FLAC: Codec
PRODUCT_TYPE_UNSPECIFIED: ProductType
QUEUE: ProductType
CAMPAIGN: ProductType
IVR: ProductType
DIALOG_TYPE_UNSPECIFIED: DialogType
INBOUND: DialogType
OUTBOUND: DialogType
PARTICIPANT_TYPE_UNSPECIFIED: ParticipantType
CONTACT: ParticipantType
AGENT: ParticipantType
BOT: ParticipantType

class Account(_message.Message):
    __slots__ = ("id", "sub_account_id", "rc_account_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    SUB_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    RC_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    sub_account_id: str
    rc_account_id: str
    def __init__(self, id: _Optional[str] = ..., sub_account_id: _Optional[str] = ..., rc_account_id: _Optional[str] = ...) -> None: ...

class Product(_message.Message):
    __slots__ = ("id", "type")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: ProductType
    def __init__(self, id: _Optional[str] = ..., type: _Optional[_Union[ProductType, str]] = ...) -> None: ...

class Dialog(_message.Message):
    __slots__ = ("id", "type", "ani", "dnis", "language", "attributes")
    class AttributesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ANI_FIELD_NUMBER: _ClassVar[int]
    DNIS_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: DialogType
    ani: str
    dnis: str
    language: str
    attributes: _containers.ScalarMap[str, str]
    def __init__(self, id: _Optional[str] = ..., type: _Optional[_Union[DialogType, str]] = ..., ani: _Optional[str] = ..., dnis: _Optional[str] = ..., language: _Optional[str] = ..., attributes: _Optional[_Mapping[str, str]] = ...) -> None: ...

class Participant(_message.Message):
    __slots__ = ("id", "type", "name")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: ParticipantType
    name: str
    def __init__(self, id: _Optional[str] = ..., type: _Optional[_Union[ParticipantType, str]] = ..., name: _Optional[str] = ...) -> None: ...

class AudioFormat(_message.Message):
    __slots__ = ("codec", "rate", "ptime")
    CODEC_FIELD_NUMBER: _ClassVar[int]
    RATE_FIELD_NUMBER: _ClassVar[int]
    PTIME_FIELD_NUMBER: _ClassVar[int]
    codec: Codec
    rate: int
    ptime: int
    def __init__(self, codec: _Optional[_Union[Codec, str]] = ..., rate: _Optional[int] = ..., ptime: _Optional[int] = ...) -> None: ...

class AudioContent(_message.Message):
    __slots__ = ("payload", "seq", "duration")
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    SEQ_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    payload: bytes
    seq: int
    duration: int
    def __init__(self, payload: _Optional[bytes] = ..., seq: _Optional[int] = ..., duration: _Optional[int] = ...) -> None: ...

class StreamEvent(_message.Message):
    __slots__ = ("session_id", "dialog_init", "segment_start", "segment_media", "segment_info", "segment_stop")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    DIALOG_INIT_FIELD_NUMBER: _ClassVar[int]
    SEGMENT_START_FIELD_NUMBER: _ClassVar[int]
    SEGMENT_MEDIA_FIELD_NUMBER: _ClassVar[int]
    SEGMENT_INFO_FIELD_NUMBER: _ClassVar[int]
    SEGMENT_STOP_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    dialog_init: DialogInitEvent
    segment_start: SegmentStartEvent
    segment_media: SegmentMediaEvent
    segment_info: SegmentInfoEvent
    segment_stop: SegmentStopEvent
    def __init__(self, session_id: _Optional[str] = ..., dialog_init: _Optional[_Union[DialogInitEvent, _Mapping]] = ..., segment_start: _Optional[_Union[SegmentStartEvent, _Mapping]] = ..., segment_media: _Optional[_Union[SegmentMediaEvent, _Mapping]] = ..., segment_info: _Optional[_Union[SegmentInfoEvent, _Mapping]] = ..., segment_stop: _Optional[_Union[SegmentStopEvent, _Mapping]] = ...) -> None: ...

class DialogInitEvent(_message.Message):
    __slots__ = ("account", "dialog")
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    DIALOG_FIELD_NUMBER: _ClassVar[int]
    account: Account
    dialog: Dialog
    def __init__(self, account: _Optional[_Union[Account, _Mapping]] = ..., dialog: _Optional[_Union[Dialog, _Mapping]] = ...) -> None: ...

class SegmentStartEvent(_message.Message):
    __slots__ = ("segment_id", "product", "participant", "audio_format")
    SEGMENT_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    PARTICIPANT_FIELD_NUMBER: _ClassVar[int]
    AUDIO_FORMAT_FIELD_NUMBER: _ClassVar[int]
    segment_id: str
    product: Product
    participant: Participant
    audio_format: AudioFormat
    def __init__(self, segment_id: _Optional[str] = ..., product: _Optional[_Union[Product, _Mapping]] = ..., participant: _Optional[_Union[Participant, _Mapping]] = ..., audio_format: _Optional[_Union[AudioFormat, _Mapping]] = ...) -> None: ...

class SegmentMediaEvent(_message.Message):
    __slots__ = ("segment_id", "audio_content")
    SEGMENT_ID_FIELD_NUMBER: _ClassVar[int]
    AUDIO_CONTENT_FIELD_NUMBER: _ClassVar[int]
    segment_id: str
    audio_content: AudioContent
    def __init__(self, segment_id: _Optional[str] = ..., audio_content: _Optional[_Union[AudioContent, _Mapping]] = ...) -> None: ...

class SegmentInfoEvent(_message.Message):
    __slots__ = ("segment_id", "event", "data")
    SEGMENT_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    segment_id: str
    event: str
    data: str
    def __init__(self, segment_id: _Optional[str] = ..., event: _Optional[str] = ..., data: _Optional[str] = ...) -> None: ...

class SegmentStopEvent(_message.Message):
    __slots__ = ("segment_id",)
    SEGMENT_ID_FIELD_NUMBER: _ClassVar[int]
    segment_id: str
    def __init__(self, segment_id: _Optional[str] = ...) -> None: ...
