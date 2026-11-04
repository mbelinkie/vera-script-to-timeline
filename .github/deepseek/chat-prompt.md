Groom VERA issue {{ISSUE_URL}} so a DeepSeek coding agent can attempt it unattended, then launch it. Use high thinking effort.

1. Read the issue, its comments, linked issues and docs, and the relevant code in the public repo https://github.com/{{REPO}} (start with CLAUDE.md / AGENTS.md, then the files and tests the task touches).
2. Resolve as much as you can yourself: scope, approach, likely files, edge cases, acceptance checks and exact test commands. Make reasonable technical decisions and state them.
3. Ask me only questions that truly need the Producer: product behaviour, taste, money or my data. Put them in one short numbered list, each with your recommended answer. Ask nothing technical. If there are no such questions, don't ask any.
4. Write a self-contained brief with these headings: Goal; Decisions made; Out of scope; Likely files; Plan; Acceptance checks; Tests to run (exact commands); Risks and notes for the reviewer.
5. Launch it by calling the VERA Mac Bridge tool vera_launch_deepseek with repo="{{SHORT_REPO}}", issue={{NUMBER}}, brief=(the brief) and model="flash". Use model="pro" only if the task is large or subtle. If I haven't answered a question yet, launch anyway using your recommended answers and list them as assumptions in the brief. Only wait for me if a wrong guess would make the whole attempt useless.
6. Reply with at most three lines: what you launched, which assumptions you made, and the issue link. Don't monitor the job; it reports back on the issue by itself.

Change nothing else on GitHub.
