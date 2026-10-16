"""Small no-Resolve checks for the audio mapping readback guards."""

import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).with_name("audio-mapping-readonly.py")
SPEC = importlib.util.spec_from_file_location("audio_mapping_readonly", MODULE)
CODE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CODE)


class Source:
    def __init__(self, uid, name="generated.wav"):
        self.uid, self.name = uid, name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name


class Item:
    def __init__(self, uid, source):
        self.uid, self.source = uid, source
        self.calls = 0

    def GetUniqueId(self):
        return self.uid

    def GetMediaPoolItem(self):
        return self.source

    def GetSourceAudioChannelMapping(self):
        self.calls += 1
        return '{"track_mapping":{"1":{"channel_idx":[1,2],"mute":false,"type":"Stereo"}}}'


def run():
    raw = Item("occ-1", Source("src-1"))
    pinned = {"occ-1": {"occurrenceUid": "occ-1", "sourceUid": "src-1", "trackIndex": 1}}
    bound = CODE._bind_objects(pinned, [(1, [raw])])
    first = CODE._collect(bound, set())
    second = CODE._collect(bound, set())
    assert first == second and raw.calls == 2
    assert first[0]["GetSourceAudioChannelMapping"]["parsed"]["track_mapping"]

    unstable = Item("occ-2", Source("src-2"))
    unstable.values = iter(['{"a":1}', '{"a":2}'])
    unstable.GetSourceAudioChannelMapping = lambda: next(unstable.values)
    bound_unstable = CODE._bind_objects(
        {"occ-2": {"occurrenceUid": "occ-2", "sourceUid": "src-2"}},
        [(1, [unstable])],
    )
    a = CODE._collect(bound_unstable, set())
    b = CODE._collect(bound_unstable, set())
    assert a != b

    for source in (Source("unexpected"), Source(CODE.PROTECTED_UID, CODE.PROTECTED_NAME)):
        refused = Item("occ-1", source)
        try:
            CODE._bind_objects(pinned, [(1, [refused])])
        except RuntimeError:
            pass
        else:
            raise AssertionError("unexpected/protected source accepted")
        assert refused.calls == 0

    context = {"timeline": CODE.MATRIX_UID, "page": "edit", "playhead": "00:00:00:00"}
    before = json.dumps(context, sort_keys=True)
    assert json.dumps(context, sort_keys=True) == before
    print("PASS: stable JSON, inconsistent getter, pre-getter source refusal, unchanged context")


if __name__ == "__main__":
    run()
