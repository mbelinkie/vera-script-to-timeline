Prepare VERA issue {{ISSUE_URL}} for an unattended coding agent: work it out, write the code, then launch the agent. Use high thinking effort. Work independently; I don't want to review your reasoning.

1. Read the issue, its comments, linked issues and docs, and the relevant code in the public repo https://github.com/{{REPO}}. Start with CLAUDE.md / AGENTS.md, then read the actual current contents of every file you plan to change and the tests near them. Raw files are at https://raw.githubusercontent.com/{{REPO}}/main/<path>.
2. If this turns out to be design, taste, research or investigation work rather than code, or something it depends on isn't finished, don't launch anything. Reply in one line saying why, and stop.
3. Decide everything you can yourself: scope, approach, edge cases, acceptance checks and exact test commands. Never ask me technical questions.
4. Only if a decision truly needs the Producer (product behaviour, taste, money or my data), choose the answer you recommend and keep going. List those choices under "Assumptions for Matthew" in the brief. Don't stop to ask.
5. Write the brief with these headings: Goal; Decisions made; Assumptions for Matthew; Out of scope; Plan; Draft code; Acceptance checks; Tests to run (exact commands); Risks and notes for the reviewer.
   - **Draft code:** write the real code, not a description of it. For each file, give either the complete new contents or exact replacement snippets with enough unchanged surrounding lines to find the spot. Base it on the file contents you actually read, follow the repo's conventions, and include the new or updated tests. For a large task, write the code for the core slice and give a precise plan for the rest. Mark anything you're unsure of. Keep the whole brief under 50,000 characters.
   - A coding agent will apply your draft, fix small mismatches, run the tests and iterate. It can't see this chat, so the brief must stand on its own.
6. Launch it by calling the VERA Mac Bridge tool vera_launch_deepseek with repo="{{SHORT_REPO}}", issue={{NUMBER}}, brief=(the brief) and model="flash". Use model="pro" only if the task is unusually subtle.
7. Reply with at most three lines: what you launched, any assumptions for Matthew, and the issue link. Don't monitor the job; it reports back on the issue by itself.

Change nothing else on GitHub.
