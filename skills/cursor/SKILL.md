---
name: cursor
description: Guide for choosing the right Cursor feature (rules, skills, subagents, hooks, modes, MCP, context providing) for any task or workflow problem. Use when the user asks which Cursor feature to use, when planning how to approach a complex task, when discussing workflow improvements, or when the user includes this skill explicitly.
---

# Cursor Feature Guide

Help the user choose the optimal Cursor feature for their current task or workflow problem.

**Read [cursor-features.md](cursor-features.md) thoroughly** before making any recommendation. It contains the agent's complete operational knowledge of every Cursor feature.

## When This Skill Helps

- User is starting a complex task and isn't sure how to approach it
- User asks "should this be a rule or a skill?" or similar feature-selection questions
- User wants to improve their workflow or automate something
- Agent recognizes a situation where a specific Cursor feature would help
- User is building new Cursor configuration (rules, skills, subagents, hooks)

## Process

1. **Understand the situation** — What is the user trying to accomplish? What's the pain point?
2. **Consult the reference** — Read `cursor-features.md` and use the Decision Matrices (both prospective and retrospective)
3. **Recommend the lightest mechanism** — Rule < Skill < Subagent. Don't over-engineer.
4. **Explain the trade-offs** — Why this feature over alternatives? What are the costs?

## Quick Reference

Use the **Prospective Decision Matrix** in `cursor-features.md` when helping the user choose a feature for a current task. Use the **Retrospective Decision Matrix** when reviewing what could have been done better.

## Related Skills

- Use `create-rule` skill to implement new rules
- Use `create-skill` skill to implement new skills
- Use `sync-cursor-features` skill to update the feature knowledge base
