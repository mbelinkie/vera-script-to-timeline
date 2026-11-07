import { describe, expect, it } from "vitest";

import { parseQaConfig, QaConfigError } from "../src/qa-config.js";

const sha = "a".repeat(40);
const root = "/work/vera-repo";
const good: NodeJS.ProcessEnv = {
  VERA_STT_MODE: "development-qa",
  VERA_STT_QA_HOST: "127.0.0.1",
  VERA_STT_QA_PORT: "38429",
  VERA_STT_QA_DATABASE_URL: "postgresql://vera_stt_qa_app:private@127.0.0.1:5432/vera_stt_qa_159_test",
  VERA_STT_SOURCE_SHA: sha,
  VERA_STT_QA_IDENTITY_FILE: "/tmp/vera-private/identity.json",
};

describe("explicit development QA configuration", () => {
  it("accepts a dedicated loopback PostgreSQL target and independently pinned source", () => {
    expect(parseQaConfig(good, sha, root)).toEqual({
      deploymentMode: "development-qa",
      bindHost: "127.0.0.1",
      port: 38429,
      sourceSha: sha,
      databaseUrl: good.VERA_STT_QA_DATABASE_URL,
      databaseName: "vera_stt_qa_159_test",
      databaseUser: "vera_stt_qa_app",
      identityFile: "/tmp/vera-private/identity.json",
    });
  });

  it.each([
    ["no mode", { VERA_STT_MODE: undefined }],
    ["release mode", { VERA_STT_MODE: "hosted-release" }],
    ["wildcard listener", { VERA_STT_QA_HOST: "0.0.0.0" }],
    ["proxy listener", { VERA_STT_QA_HOST: "localhost" }],
    ["privileged port", { VERA_STT_QA_PORT: "80" }],
    ["zero port", { VERA_STT_QA_PORT: "0" }],
    ["bad port", { VERA_STT_QA_PORT: "65536" }],
    ["no source pin", { VERA_STT_SOURCE_SHA: undefined }],
    ["forged source", { VERA_STT_SOURCE_SHA: "b".repeat(40) }],
    ["relative secrets file", { VERA_STT_QA_IDENTITY_FILE: "private/identity.json" }],
    ["repo secrets file", { VERA_STT_QA_IDENTITY_FILE: "/work/vera-repo/config/secrets.json" }],
    ["default database", { VERA_STT_QA_DATABASE_URL: "postgresql://app:password@127.0.0.1/postgres" }],
    ["research DB", { VERA_STT_QA_DATABASE_URL: "postgresql://app:password@127.0.0.1/vera_research" }],
    ["public database host", { VERA_STT_QA_DATABASE_URL: "postgresql://app:password@10.0.0.6/vera_stt_qa_sandbox" }],
    ["no database username", { VERA_STT_QA_DATABASE_URL: "postgresql://:password@127.0.0.1/vera_stt_qa_sandbox" }],
    ["superuser username", { VERA_STT_QA_DATABASE_URL: "postgresql://postgres:password@127.0.0.1/vera_stt_qa_sandbox" }],
    ["no password", { VERA_STT_QA_DATABASE_URL: "postgresql://app@127.0.0.1/vera_stt_qa_sandbox" }],
    ["libpq options", { VERA_STT_QA_DATABASE_URL: "postgresql://app:password@127.0.0.1/vera_stt_qa_sandbox?options=-csearch_path%3Dother" }],
    ["URL fragment", { VERA_STT_QA_DATABASE_URL: "postgresql://app:password@127.0.0.1/vera_stt_qa_sandbox#fragment" }],
    ["overlong database", { VERA_STT_QA_DATABASE_URL: `postgresql://app:password@127.0.0.1/vera_stt_qa_${"a".repeat(52)}` }],
  ])("refuses %s without reflecting secret values", (_name, override) => {
    expect(() => parseQaConfig({ ...good, ...override }, sha, root))
      .toThrowError(new QaConfigError());
  });

  it("rejects untrusted or malformed checked-out SHA", () => {
    expect(() => parseQaConfig(good, "b".repeat(40), root)).toThrow(QaConfigError);
    expect(() => parseQaConfig(good, "not-a-sha", root)).toThrow(QaConfigError);
  });
});
