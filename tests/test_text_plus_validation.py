from __future__ import annotations

from typing import Any

import pytest
from vera_timeline_agent.studio_spike import (
    BLACKMAGIC_BUNDLE_ID,
    ConnectedFacts,
    LocalFacts,
)
from vera_timeline_agent.text_plus_template import (
    DEFAULT_TEXT_PLUS_TEMPLATE_METADATA,
    TextPlusTemplate,
    validate_text_plus_template,
)
from vera_timeline_agent.text_plus_validation import (
    DurationObservation,
    FusionFingerprint,
    TextPlusValidationEvidence,
    append_template_item,
    fingerprint_fusion_item,
    import_template_generator,
    run_text_plus_validation,
)


@pytest.fixture
def standard_local() -> LocalFacts:
    return LocalFacts(
        os_name="macOS",
        os_version="15.1",
        architecture="x86_64",
        app_path="/Applications/DaVinci Resolve/DaVinci Resolve.app",
        app_installed=True,
        install_source="blackmagic_package_receipt",
        bundle_name="DaVinci Resolve",
        bundle_identifier=BLACKMAGIC_BUNDLE_ID,
        bundle_version="21.0.4",
        bundle_build="21.0.40005",
        mas_receipt=False,
        package_receipt_id="com.blackmagic-design.ManifestLite",
        package_receipt_version="21.0.4",
        scripting_module_path="/sdk/DaVinciResolveScript.py",
        scripting_module_installed=True,
        scripting_docs_path="/sdk/README.txt",
        scripting_docs_installed=True,
    )


def _evidence(template: TextPlusTemplate) -> TextPlusValidationEvidence:
    fingerprint = FusionFingerprint(1, ("MediaOut", "TextPlus"), 1)
    return TextPlusValidationEvidence(
        asset_sha256=template.sha256,
        authoring_resolve_version=template.authoring_resolve_version,
        stock_fingerprint=fingerprint,
        template_fingerprint=fingerprint,
        duration_observations=(
            DurationObservation(24, 23, 23),
            DurationObservation(24, 24, 24),
            DurationObservation(24, 25, 25),
            DurationObservation(72, 72, 72),
        ),
        append_end_frame_delta=0,
        canonical_timeline_name="VERA Text+ canonical V4",
        canonical_track_index=4,
        canonical_record_frame=0,
        canonical_duration_frames=72,
    )


class RecordingValidationAdapter:
    def __init__(self, *, fail_after_create: bool = False) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.fail_after_create = fail_after_create

    def connected_facts(self) -> ConnectedFacts:
        self.calls.append(("connected_facts", None))
        return ConnectedFacts("DaVinci Resolve Studio", "studio", "21.0.4", "5", True)

    def probe(self, template: TextPlusTemplate) -> tuple[str, ...]:
        self.calls.append(("probe", template.sha256))
        return ()

    def check_project_name_available(self, name: str) -> None:
        self.calls.append(("check_project_name_available", name))

    def create_project(self, name: str) -> None:
        self.calls.append(("create_project", name))

    def validate(self, template: TextPlusTemplate) -> TextPlusValidationEvidence:
        self.calls.append(("validate", template.sha256))
        if self.fail_after_create:
            raise RuntimeError("injected validation failure")
        return _evidence(template)

    def save_close_reopen(self, project_name: str) -> None:
        self.calls.append(("save_close_reopen", project_name))

    def verify_reopened(
        self, template: TextPlusTemplate, evidence: TextPlusValidationEvidence
    ) -> tuple[str, ...]:
        self.calls.append(("verify_reopened", evidence.append_end_frame_delta))
        return ()


def test_validation_preflight_is_nonmutating_and_checks_name(
    standard_local: LocalFacts,
) -> None:
    adapter = RecordingValidationAdapter()
    result = run_text_plus_validation(
        action="preflight",
        project_name="Unique validation project",
        local_facts=standard_local,
        adapter_factory=lambda _: adapter,
    )

    assert result.status == "preflight_passed"
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]
    assert result.asset_sha256.startswith("4a984512")


def test_validation_build_retains_exact_mutation_order(
    standard_local: LocalFacts,
) -> None:
    adapter = RecordingValidationAdapter()
    result = run_text_plus_validation(
        action="build",
        project_name="Unique validation project",
        local_facts=standard_local,
        adapter_factory=lambda _: adapter,
    )

    assert result.status == "verified"
    assert result.verified
    assert result.evidence is not None
    assert result.evidence.append_end_frame_delta == 0
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
        "create_project",
        "validate",
        "save_close_reopen",
        "verify_reopened",
    ]


def test_validation_failure_after_creation_reports_retained_project(
    standard_local: LocalFacts,
) -> None:
    adapter = RecordingValidationAdapter(fail_after_create=True)
    result = run_text_plus_validation(
        action="build",
        project_name="Retained partial validation project",
        local_facts=standard_local,
        adapter_factory=lambda _: adapter,
    )

    assert result.status == "mutation_failed"
    assert "retained" in result.message
    assert result.project_name == "Retained partial validation project"


def test_fingerprint_requires_one_text_plus_and_sorted_registration_ids() -> None:
    class Tool:
        def __init__(self, registration_id: str) -> None:
            self.registration_id = registration_id

        def GetAttrs(self, key: str) -> str:
            assert key == "TOOLS_RegID"
            return self.registration_id

    class Composition:
        def GetToolList(self, selected: bool = False) -> dict[str, Tool]:
            assert not selected
            return {"Text1": Tool("TextPlus"), "MediaOut1": Tool("MediaOut")}

    class Item:
        def GetFusionCompCount(self) -> int:
            return 1

        def GetFusionCompByIndex(self, index: int) -> Composition:
            assert index == 1
            return Composition()

    template = validate_text_plus_template(DEFAULT_TEXT_PLUS_TEMPLATE_METADATA)
    assert fingerprint_fusion_item(Item(), template) == FusionFingerprint(
        1, ("MediaOut", "TextPlus"), 1
    )


def test_template_import_restores_folder_and_requires_one_direct_clip() -> None:
    template = validate_text_plus_template(DEFAULT_TEXT_PLUS_TEMPLATE_METADATA)

    class Clip:
        def GetName(self) -> str:
            return "Text+"

    class Folder:
        def __init__(self, name: str, clips: list[Clip] | None = None) -> None:
            self.name = name
            self.clips = clips or []
            self.children: list[Folder] = []

        def GetName(self) -> str:
            return self.name

        def GetClipList(self) -> list[Clip]:
            return self.clips

        def GetSubFolderList(self) -> list[Folder]:
            return self.children

    root = Folder("Master")
    prior = Folder("Prior")

    class Pool:
        def __init__(self) -> None:
            self.selected: list[Folder] = []

        def GetRootFolder(self) -> Folder:
            return root

        def GetCurrentFolder(self) -> Folder:
            return prior

        def SetCurrentFolder(self, folder: Folder) -> bool:
            self.selected.append(folder)
            return True

        def ImportFolderFromFile(self, path: str, source: str) -> bool:
            assert path == str(template.asset_path)
            assert source == ""
            root.children.append(Folder("VERA Text+ Template", [Clip()]))
            return True

    pool = Pool()
    clip = import_template_generator(pool, template)

    assert clip.GetName() == "Text+"
    assert pool.selected == [root, prior]


def test_append_template_item_uses_exact_documented_clip_info() -> None:
    class Item:
        def GetStart(self, _: bool) -> int:
            return 100

    item = Item()

    class State:
        appended = False

    state = State()

    class Timeline:
        def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
            assert (kind, index) == ("video", 4)
            return [item] if state.appended else []

    class Pool:
        def __init__(self) -> None:
            self.values: list[dict[str, Any]] | None = None

        def AppendToTimeline(self, values: list[dict[str, Any]]) -> list[Item]:
            self.values = values
            state.appended = True
            return [item]

    pool = Pool()
    generator = object()
    result = append_template_item(
        pool,
        generator,
        Timeline(),
        start_frame=0,
        end_frame=72,
        record_frame=100,
        track_index=4,
    )

    assert result is item
    assert pool.values == [
        {
            "mediaPoolItem": generator,
            "startFrame": 0,
            "endFrame": 72,
            "recordFrame": 100,
            "trackIndex": 4,
            "mediaType": 1,
        }
    ]
