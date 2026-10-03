// node --test src/lib/library.test.js   (from frontend/)
import assert from "node:assert/strict";
import test from "node:test";
import { matches, related, sortJobs } from "./library.js";

const label = s => ({ finance: "Finance", tech: "Tech & AI" })[s] || s;
const done = (id, o) => ({ id, status: "done", community: "tech", language: "en", duration: 30, created: id, topic: `t${id}`, ...o });
const jobs = [
  done(1, { topic: "SIP vs FD", community: "finance", language: "hinglish", result: { duration: 41, hook: "Stop saving wrong", caption: "", hashtags: ["#upi"] } }),
  done(2, { topic: "AI tools", style: "anime", result: { duration: 14, hook: "", caption: "", hashtags: [] } }),
  { id: 3, status: "running", community: "tech", language: "en", duration: 60, created: 3, topic: "zzz" },
  { id: 4, status: "queued", community: "tech", language: "en", duration: 15, created: 0, topic: "aaa" },
];
const ids = list => list.map(j => j.id);
const none = {};

test("search reaches hashtags, hook and community name", () => {
  assert.deepEqual(ids(jobs.filter(j => matches(j, "#upi", none, label))), [1]);
  assert.deepEqual(ids(jobs.filter(j => matches(j, "saving", none, label))), [1]);
  assert.deepEqual(ids(jobs.filter(j => matches(j, "tech & ai", none, label))), [2, 3, 4]);
});

test("filters: any within a group, all across groups, missing style is photo", () => {
  const picks = { community: new Set(["tech", "finance"]), style: new Set(["photo"]) };
  assert.deepEqual(ids(jobs.filter(j => matches(j, "", picks, label))), [1, 3, 4]);
  assert.deepEqual(ids(jobs.filter(j => matches(j, "", { duration: new Set([15]) }, label))), [4]);
});

test("sorting keeps videos being made first and in their order", () => {
  const making = [jobs[2], jobs[3]];
  assert.deepEqual(ids(sortJobs([...making, jobs[0], jobs[1]], "latest")), [3, 4, 2, 1]);
  assert.deepEqual(ids(sortJobs([...making, jobs[0], jobs[1]], "shortest")), [3, 4, 2, 1]);
  assert.deepEqual(ids(sortJobs([...making, jobs[0], jobs[1]], "longest")), [3, 4, 1, 2]);
  assert.deepEqual(ids(sortJobs([...making, jobs[1], jobs[0]], "az")), [3, 4, 2, 1]);
});

test("related ranks community and language, skips itself and unfinished videos", () => {
  const me = done(9, { result: {} });
  const list = [me, ...jobs,
    done(5, { community: "finance", language: "en", result: {} }),
    done(6, { result: {} }),
    done(7, { language: "hi", result: {} })];
  assert.deepEqual(ids(related(list, me)), [6, 2, 7, 5, 1]);
  assert.deepEqual(ids(related(list, me, 2)), [6, 2]);
});
