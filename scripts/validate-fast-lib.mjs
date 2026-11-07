// Preserve the original validate:fast package.json && chain verbatim and in order.
export const FAST_PHASES = Object.freeze([
  Object.freeze(["contracts", "check:contracts-generated"]),
  Object.freeze(["ts-lint", "lint:typescript"]),
  Object.freeze(["ts-types", "typecheck:typescript"]),
  Object.freeze(["ts-tests", "test:typescript:fast"]),
  Object.freeze(["py-lint", "lint:python"]),
  Object.freeze(["py-types", "typecheck:python"]),
  Object.freeze(["py-tests", "test:python:fast"]),
]);

// Injectable synchronous runner and monotonic clock keep the timer testable.
export function runFastPhases({ run, now, write }) {
  const started = now();
  const phases = [];
  let exitCode = 0;

  for (const [name, script] of FAST_PHASES) {
    const began = now();
    let status;
    try {
      status = run(script);
    } catch (error) {
      write(`[validate:fast] ${name} could not run: ${String(error)}`);
      status = 1;
    }

    const seconds = (now() - began) / 1000;
    const phaseExitCode = Number.isInteger(status) && status >= 0 ? status : 1;
    phases.push({ name, script, seconds, exitCode: phaseExitCode });
    write(`[validate:fast] ${name}: ${seconds.toFixed(3)}s ${phaseExitCode === 0 ? "PASS" : `FAIL (exit=${phaseExitCode})`}`);

    if (phaseExitCode !== 0) {
      exitCode = phaseExitCode;
      break;
    }
  }

  const totalSeconds = (now() - started) / 1000;
  write(`[validate:fast] total: ${totalSeconds.toFixed(3)}s; exit=${exitCode}`);
  return { phases, totalSeconds, exitCode };
}
