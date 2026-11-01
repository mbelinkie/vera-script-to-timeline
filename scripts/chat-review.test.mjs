import assert from 'node:assert/strict';
import test from 'node:test';
import {
  CHAT_APPROVAL_LABEL, approvalComment, assertChatReviewApproved,
  chatReviewQuery, chatStateForItem, evaluateChatReview, issueRevision,
  parseApprovalComment, parseChatReviewGraphql, parseIssueUrl,
  reviewChatUrl, reviewPrompt, fetchChatReviewSnapshot,
} from './chat-review-lib.mjs';
import { buildProgressModel, parseProjectItems, renderDashboard } from './project-progress-lib.mjs';

const url = 'https://github.com/mbelinkie/vera-script-to-timeline/issues/125';
const researchUrl = 'https://github.com/mbelinkie/vera-research-video-clips/issues/125';
const title = 'Build the authoring editor';
const body = '## Acceptance criteria\n- [ ] A user can save a script';
const summary = 'Producer reviewed scope, acceptance, failure states, and dependencies.';
function approvedIssue(replacements={}) {
  return {
    number: 125, title, body, labels: [{ name: CHAT_APPROVAL_LABEL }],
    comments: [{body: approvalComment({title,body,producer:'mbelinkie',summary,reviewedAt:'2026-10-31T12:00:00Z'}),
      url: url+'#issuecomment-123',author:{login:'mbelinkie'}}],
    ...replacements,
  };
}

test('standardized Chat prompt is human-guided, and launch is non-approving', () => {
  assert.equal(parseIssueUrl(url+'#a').number,125);
  assert.equal(parseIssueUrl(researchUrl).repo,'vera-research-video-clips');
  for (const bad of ['https://evil.test/', 'javascript:alert(1)', 'https://github.com/evil/vera-script-to-timeline/issues/125', 'https://github.com/mbelinkie/vera-script-to-timeline/pull/125']) {
    assert.throws(()=>parseIssueUrl(bad));
  }
  const prompt = reviewPrompt(url);
  assert.match(prompt, /Work iteratively/);
  assert.match(prompt, /NEVER declare the review complete/);
  assert.match(prompt, /I approve this Chat review for vera-script-to-timeline#125/);
  assert.match(new URL(reviewChatUrl(url)).searchParams.get('prompt'), /Producer/);
  assert.equal(new URL(reviewChatUrl(url)).host, 'chatgpt.com');
});

test('the approval record has an exact issue revision and the actual Producer must have authored it', () => {
  const digest = issueRevision(title,body);
  assert.equal(digest.length, 64);
  assert.notEqual(digest, issueRevision(title,body+'\nNew requirement'));
  assert.equal(evaluateChatReview(approvedIssue()).status,'approved');
  assert.equal(assertChatReviewApproved(approvedIssue()).approved,true);
  assert.equal(evaluateChatReview(approvedIssue({title:title+' (changed)'})).status,'outdated');
  assert.equal(evaluateChatReview(approvedIssue({body:body+' ' })).status,'outdated');
  assert.equal(evaluateChatReview(approvedIssue({labels:[]})).status,'not-reviewed');
  assert.equal(evaluateChatReview(approvedIssue({labels:[{name:'chat-review-pending'}]})).status,'in-review');
  assert.equal(evaluateChatReview(approvedIssue({comments:[]})).status,'unverified');
  assert.equal(evaluateChatReview(approvedIssue({comments:[{body:approvedIssue().comments[0].body, author:{login:'other'}}]})).status,'unverified');
  assert.throws(()=>assertChatReviewApproved(approvedIssue({body:'unexpected edit'})), /Codex claim blocked/);
});

test('a simple label is never proof of Producer approval; other comments do not stale an approved revision', () => {
  const issue = approvedIssue();
  issue.comments.push({body:'An ordinary conversation or CI comment',author:{login:'mbelinkie'}});
  assert.equal(evaluateChatReview(issue).approved,true);
  const forged = {...issue, comments:[{body:issue.comments[0].body.replace('"producer":"mbelinkie"','"producer":"other"'),author:{login:'mbelinkie'}}]};
  assert.equal(evaluateChatReview(forged).approved,false);
  assert.equal(parseApprovalComment({body:issue.comments[0].body,author:{login:'another'}}),null);
  assert.throws(()=>approvalComment({title,body,producer:'mbelinkie',summary:''}),/summary/);
});

test('GraphQL batch audit does not mix equal-number issues across repos', () => {
  const a = approvedIssue();
  const b = approvedIssue({title:'Research task',body:'Research body',comments:[]});
  const q = chatReviewQuery([{url}, {url:researchUrl}]);
  assert.match(q, /vera-script-to-timeline/);
  assert.match(q, /vera-research-video-clips/);
  const response={data:{ r0:{i0:{title:a.title,body:a.body,labels:{nodes:a.labels},comments:{nodes:a.comments}}},
                         r1:{i0:{title:b.title,body:b.body,labels:{nodes:b.labels},comments:{nodes:b.comments}}}}};
  const statuses=parseChatReviewGraphql([{url},{url:researchUrl}],response);
  assert.equal(statuses[url.toLowerCase()].status,'approved');
  assert.equal(statuses[researchUrl.toLowerCase()].status,'unverified');
});

test('a failed live GraphQL audit cannot silently turn a label into approval', async () => {
  const item = {url, chatReviewLabels:['chat-reviewed']};
  const models=[{goals:[],workItems:[item]}];
  const r=await fetchChatReviewSnapshot('.',models,{execFileAsync:async()=>{throw new Error('No GitHub permission')}});
  assert.equal(r.errors.length,1);
  assert.equal(r.states[url.toLowerCase()],undefined);
  assert.equal(chatStateForItem(item,r.states).status,'unverified');
});

test('dashboard shows review status and launches a review for unapproved issues', () => {
  const data={totalCount:1,items:[{status:'Ready',labels:['type:implementation','model:terra','effort:high','chat-reviewed'],
    'Queue Order':10,'Program Milestone':'R2',blockedBy:[],
    content:{type:'Issue',number:125,title,url}}]};
  const model={...buildProgressModel(parseProjectItems(data)),projectTitle:'STT',projectNumber:2};
  const approved = renderDashboard(model,{chatReviewSnapshot:{states:{[url]:{status:'approved',approved:true,url:url+'#issuecomment-123'}},errors:[]}});
  assert.match(approved,/Chat approved/);
  assert.match(approved,/View signed review/);
  assert.doesNotMatch(approved,/Review in ChatGPT/);
  assert.match(approved,/id="queue-chat"/);
  assert.match(approved,/data-queue-chat="approved"/);
  const stale = renderDashboard(model,{chatReviewSnapshot:{states:{[url]:{status:'outdated',approved:false}},errors:[]}});
  assert.match(stale,/Chat review outdated/);
  assert.match(stale,/Review in ChatGPT/);
  assert.match(stale,/Copy prompt/);
  assert.match(stale,/data-queue-chat="outdated"/);
  const unknown=renderDashboard(model);
  assert.match(unknown,/Review unverified/);
  assert.doesNotMatch(unknown,/Chat approved/);
});
