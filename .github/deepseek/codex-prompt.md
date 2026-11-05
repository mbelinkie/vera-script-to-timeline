Prepare VERA issue {{ISSUE_URL}} so Codex can implement it quickly, then post your brief to the issue. Codex will do the work itself on Matthew's Mac (this ticket isn't suitable for DeepSeek), so your job is to save Codex exploration. Use high thinking effort. Work independently; I don't want to review your reasoning.

1. Read the issue, its comments, linked issues and docs, and the relevant code in the public repo https://github.com/{{REPO}}. Start with AGENTS.md, then trace the real code paths this work touches: read the actual current files, the functions involved and the tests around them. Raw files are at https://raw.githubusercontent.com/{{REPO}}/main/<path>.
2. Treat the issue's own "Dependencies" section as authoritative and never invent blockers. If part of the work needs something unfinished, scope around it and list it under "Out of scope". Stop without posting only if this is design, taste, research or investigation work; then reply in one line saying why.
3. Decide everything you can yourself and never ask me technical questions. If a decision truly needs the Producer (product behaviour, taste, money or my data), pick the answer you recommend, list it under "Assumptions for Matthew", and keep going.
4. Write the brief with these headings:
   - **Goal**: the outcome in two or three sentences.
   - **Code map**: the most valuable part. For each relevant piece, give its exact path, the function or class name and approximate line numbers, what it does today, and how the pieces connect (call order, data that flows between them, existing protocols or guards that must be reused). Note the existing tests and fixtures to build on. Only state what you actually read; mark anything inferred.
   - **Decisions made** and **Assumptions for Matthew**.
   - **Out of scope**.
   - **Plan**: ordered, concrete steps, each naming the files it changes.
   - **Draft code**: only for parts that can be written and unit-tested without real hardware or apps (pure logic, schemas, adapters behind interfaces, tests with fakes). Write real code, based on the files you read. Skip anything that must be tuned against the real app.
   - **Verification on the Mac**: exact commands for the focused tests, plus a step-by-step real-app check if one is needed, with what "pass" looks like.
   - **Risks and notes**: the traps, edge cases and existing behaviour that must not break.
   Keep the whole brief under 50,000 characters. Codex can't see this chat, so the brief must stand on its own.
5. Post it by calling the VERA Mac Bridge tool vera_post_brief with repo="{{SHORT_REPO}}", issue={{NUMBER}} and brief=(the brief). Don't call vera_launch_deepseek.
6. Reply with at most three lines: that the brief is posted, any assumptions for Matthew, and the issue link.

Change nothing else on GitHub.
