"""Issue-owned, explicitly injected Studio stages; no default live connection.

The inspector must perform a fresh read through the supported boundary, mapping
native occurrences from verified package paths and facts. Synthetic test
inspectors are labeled accordingly; they are not real Resolve evidence.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vera_timeline_agent.build_jobs import (
    StageContext,
    UncertainResult,
    publish_immutable_output,
)
from vera_timeline_agent.roundtrip_build import (
    PreparedBuild,
    ProofBuildError,
    _file_hash,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.studio_assembly import AdapterFactory, run_studio_assembly
from vera_timeline_agent.studio_spike import LocalFacts

JsonObject = dict[str, Any]
Inspector = Callable[[Path, JsonObject], JsonObject]
NATIVE_STAGES = {"building_resolve_timeline", "verifying_timeline"}


class NativeStages:
    """Real accepted assembly with explicit factory and independent fresh inspector.

    A native inspector implementation/WI bind remains required for real #145.
    This segment permits only the synthetic injected proof lane.
    """

    def __init__(
        self,
        build: PreparedBuild,
        *,
        adapter_factory: AdapterFactory,
        local_facts: LocalFacts,
        inspector: Inspector,
    ) -> None:
        if build.request["evidenceLevel"] != "synthetic_injected":
            raise ProofBuildError(
                "real #145 requires the guarded WI/native authorization seam"
            )
        self.build = build
        self.adapter_factory = adapter_factory
        self.local_facts = local_facts
        self.inspector = inspector
        self.result_path = build.run_root / "native-result.json"
        self.identity_path = build.run_root / "native-identity.json"

    def _manifest(self) -> JsonObject:
        self.build._assert_current()
        self.build._verify_media()
        self.build.verified_package()
        return load_operator_json(self.build.manifest_path)

    def _inspect(self, manifest: JsonObject) -> JsonObject:
        observed = self.inspector(self.build.package_root, manifest)
        if (
            set(observed)
            != {
                "schemaVersion",
                "projectUid",
                "timelineUid",
                "projectName",
                "timelineName",
                "timeline",
                "tracks",
                "items",
                "markers",
            }
            or observed["schemaVersion"] != "issue-144-native-readback/v1"
        ):
            raise ProofBuildError("native inspector returned incomplete readback")
        if any(
            not isinstance(observed[key], str) or not observed[key]
            for key in ("projectUid", "timelineUid")
        ):
            raise ProofBuildError("native identity is missing")
        if (
            observed["projectName"] != f"VERA Studio build {manifest['buildId']}"
            or observed["timelineName"] != f"VERA build {manifest['buildId']}"
            or observed["timeline"] != manifest["timeline"]
            or observed["tracks"] != manifest["tracks"]
            or observed["markers"] != manifest["markers"]
        ):
            raise ProofBuildError("native target settings/inventory changed")
        items = observed["items"]
        if not isinstance(items, list) or len(items) != len(manifest["events"]):
            raise ProofBuildError("native occurrence inventory changed")
        expected_events = {row["id"]: row for row in manifest["events"]}
        expected_sources = {row["id"]: row for row in manifest["sources"]}
        seen_events: set[str] = set()
        seen_items: set[str] = set()
        source_uids: dict[str, str] = {}
        occurrences: JsonObject = {}
        native_facts: JsonObject = {}
        for identity, event in expected_events.items():
            source = expected_sources[event["sourceId"]]
            relative = (
                source["path"]
                if source["kind"] != "placeholder"
                else f"Media/Placeholders/{source['id']}.png"
            )
            native_facts[identity] = {
                "sourcePath": str(self.build.package_root / relative),
                "sourceHash": _file_hash(self.build.package_root / relative),
                "trackKind": event["trackKind"],
                "trackIndex": next(
                    row["index"]
                    for row in manifest["tracks"]
                    if row["id"] == event["trackId"]
                ),
                "recordRange": event["recordRange"],
                "sourceRange": event.get("sourceRange"),
            }
        for item in items:
            if not isinstance(item, dict) or set(item) != {
                "itemUid",
                "mediaUid",
                "trackKind",
                "trackIndex",
                "recordRange",
                "sourceRange",
                "sourcePath",
                "sourceHash",
                "enabled",
                "speed",
            }:
                raise ProofBuildError("native occurrence lacks required facts")
            if (
                item["enabled"] is not True
                or isinstance(item["speed"], bool)
                or item["speed"] != 100
                or not isinstance(item["itemUid"], str)
                or not item["itemUid"]
                or not isinstance(item["mediaUid"], str)
                or not item["mediaUid"]
                or not isinstance(item["trackIndex"], int)
                or isinstance(item["trackIndex"], bool)
            ):
                raise ProofBuildError("native occurrence geometry/identity changed")
            for field in ("recordRange", "sourceRange"):
                value = item[field]
                if field == "sourceRange" and value is None:
                    continue
                if (
                    not isinstance(value, dict)
                    or set(value) != {"startFrame", "durationFrames"}
                    or any(
                        not isinstance(number, int)
                        or isinstance(number, bool)
                        or number < 0
                        or number > 2**53 - 1
                        for number in value.values()
                    )
                ):
                    raise ProofBuildError("native range is not complete integer frames")
            facts = {
                key: item[key]
                for key in (
                    "sourcePath",
                    "sourceHash",
                    "trackKind",
                    "trackIndex",
                    "recordRange",
                    "sourceRange",
                )
            }
            candidates = [
                identity
                for identity, expected in native_facts.items()
                if facts == expected
            ]
            if len(candidates) != 1:
                raise ProofBuildError(
                    "native occurrence mapping is changed or ambiguous"
                )
            identity = candidates[0]
            if identity in seen_events or item["itemUid"] in seen_items:
                raise ProofBuildError("native occurrence identity is duplicate")
            event = expected_events[identity]
            seen_events.add(identity)
            seen_items.add(item["itemUid"])
            source = expected_sources[event["sourceId"]]
            if source_uids.get(source["id"], item["mediaUid"]) != item["mediaUid"] or (
                item["mediaUid"] in source_uids.values()
                and source["id"] not in source_uids
            ):
                raise ProofBuildError("native source UID is ambiguous")
            source_uids[source["id"]] = item["mediaUid"]
            # Authoring identity is a sidecar binding to one unique pristine
            # package/path/geometry candidate, never a field read from a clip.
            occurrences[identity] = {
                "itemUid": item["itemUid"],
                "mediaUid": item["mediaUid"],
            }
        identity_record = {
            "projectUid": observed["projectUid"],
            "timelineUid": observed["timelineUid"],
            "occurrences": occurrences,
        }
        if (
            self.identity_path.exists()
            and load_operator_json(self.identity_path) != identity_record
        ):
            raise ProofBuildError(
                "native identity changed since first verified readback"
            )
        return identity_record

    def _result(self, context: StageContext, manifest: JsonObject) -> JsonObject:
        if not self.build.intent_path.exists() or not self.result_path.exists():
            raise UncertainResult(
                "native creation result is missing or uncertain; no retry"
            )
        intent = load_operator_json(self.build.intent_path)
        expected = self._intent(context, manifest)
        if intent != expected:
            raise ProofBuildError("native intent identity differs")
        result = load_operator_json(self.result_path)
        if (
            result.get("status") != "verified"
            or result.get("verified") is not True
            or (
                result.get("build_id") != manifest["buildId"]
                or result.get("package_root") != str(self.build.package_root)
                or result.get("project_name") != expected["projectName"]
                or result.get("timeline_name") != expected["timelineName"]
                or result.get("discrepancies") != []
            )
        ):
            raise UncertainResult(
                "native assembly is uncertain or unverified; preserve target"
            )
        return result

    def _intent(self, context: StageContext, manifest: JsonObject) -> JsonObject:
        return {
            "schemaVersion": "issue-144-native-intent/v1",
            "evidenceLevel": "synthetic_injected",
            "snapshotId": self.build.snapshot_id,
            "stageKey": hashlib.sha256(
                f"{context.project_id}\0{context.job_id}\0building_resolve_timeline".encode()
            ).hexdigest(),
            "manifestHash": _file_hash(self.build.manifest_path),
            "packageRoot": str(self.build.package_root),
            "projectName": f"VERA Studio build {manifest['buildId']}",
            "timelineName": f"VERA build {manifest['buildId']}",
        }

    def reconcile(self, context: StageContext) -> bool:
        if context.stage not in NATIVE_STAGES:
            return self.build.reconcile(context)
        manifest = self._manifest()
        if context.output_path.exists():
            self._result(context, manifest)
            receipt = load_operator_json(context.output_path)
            if receipt.get("stageKey") != context.stage_key or (
                receipt.get("snapshotId") != self.build.snapshot_id
                or receipt.get("stage") != context.stage
                or receipt.get("evidenceLevel") != "synthetic_injected"
                or receipt.get("resultHash") != _file_hash(self.result_path)
                or receipt.get("identityHash") != _file_hash(self.identity_path)
                or receipt.get("intentHash") != _file_hash(self.build.intent_path)
            ):
                raise ProofBuildError("native receipt/result identity changed")
            self._inspect(manifest)
            return True
        if self.build.intent_path.exists() and not self.result_path.exists():
            raise UncertainResult("native creation is uncertain; no automatic retry")
        return False

    def execute(self, context: StageContext) -> None:
        if context.stage not in NATIVE_STAGES:
            self.build.execute(context)
            return
        manifest = self._manifest()
        if (
            context.stage == "building_resolve_timeline"
            and not self.build.intent_path.exists()
        ):
            # No default factory: accepted assembly cannot silently connect live.
            # Publish once before entering it, including before factory invocation.
            self._reserve_intent(context, manifest)
            result = run_studio_assembly(
                self.build.package_root,
                action="build",
                adapter_factory=self.adapter_factory,
                local_facts=self.local_facts,
            )
            publish_immutable_output(self.result_path, result.to_json().encode("utf-8"))
        self._result(context, manifest)
        identity = self._inspect(manifest)
        publish_immutable_output(self.identity_path, _receipt_bytes(identity))
        self.build._assert_current()
        self.build.verified_package()
        publish_immutable_output(
            context.output_path,
            _receipt_bytes(
                {
                    "schemaVersion": "issue-144-native-stage/v1",
                    "evidenceLevel": "synthetic_injected",
                    "snapshotId": self.build.snapshot_id,
                    "stageKey": context.stage_key,
                    "stage": context.stage,
                    "resultHash": _file_hash(self.result_path),
                    "identityHash": _file_hash(self.identity_path),
                    "intentHash": _file_hash(self.build.intent_path),
                }
            ),
        )

    def _reserve_intent(self, context: StageContext, manifest: JsonObject) -> None:
        # Replayable output publication does not grant effect ownership. Use an
        # exclusive reservation so two workers cannot both proceed after absence.
        path = self.build.intent_path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
        except FileExistsError as error:
            raise UncertainResult(
                "native intent already reserved; no duplicate effect"
            ) from error
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_receipt_bytes(self._intent(context, manifest)))
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
