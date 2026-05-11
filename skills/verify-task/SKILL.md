---
name: verify-task
description: Skeptically verify a task before implementation. Use when manually invoked for AI-generated, audit-generated, or solution-heavy tasks from Jira, Linear, GitHub, or similar trackers that may be invalid, overstated, or include a weak proposed solution.
disable-model-invocation: true
---

# Verify Task

Use this skill as an extra first step before implementation. Verify whether the task should be done and whether its proposed solution is actually the best approach.

## Workflow

1. Extract the task's core problem, requested outcome, proposed solution, evidence, and affected files or systems.
2. Verify the problem against current reality: code, tests, product behavior, logs, docs, or tracker context as available.
3. Decide whether the task is valid.
   - Valid: the problem is real, current, worth addressing, and within scope.
   - Invalid: the claim is false, already solved, speculative, too low-value, or would create churn without a meaningful outcome.
4. If valid, choose the implementation from first principles.
   - Treat the task's proposed solution as a suggestion, not an instruction.
   - Compare it with simpler, safer, more local, or more idiomatic alternatives.
   - Implement the best solution using normal codebase judgment.
5. If invalid, do not edit the codebase. Cancel or close the task when tooling and permissions are available; otherwise report that it should be canceled.

## Cancellation Comment

When canceling or recommending cancellation, write a short comment using `/message-writing` style: direct, precise, no filler. State the concrete evidence and why no code change is needed.

Template:

```text
I verified this against the current code and the task does not apply: [specific reason]. Canceling to avoid unnecessary churn.
```

Adapt the wording to the tracker and evidence. Keep it to one or two sentences.
