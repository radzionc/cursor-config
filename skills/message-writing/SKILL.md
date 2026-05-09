---
name: message-writing
description: Drafts, rewrites, polishes, and reviews user-sendable chat messages for Discord, Slack, Telegram, Teams, Signal, WhatsApp, comments, DMs, short updates, and async replies. Use when the user asks for a message, reply, announcement, team update, or text meant to be pasted into a messaging app.
---

# Message Writing

Write messages like a careful person who knows the context: clear, short, useful. "Human" must never mean lower quality, fake slang, random abbreviations, weak grammar, or reduced precision.

## When to Use

Use this skill for text the user will send in a messaging surface: Discord, Slack, Telegram, Teams, Signal, WhatsApp, comments, DMs, short updates, async replies, and announcements.

Do not use it for code comments, documentation, PR descriptions, commit messages, assistant status updates, or long-form writing unless the user explicitly wants that text written as a chat message.

## Platform References

Before drafting, identify the target platform if it is stated or obvious.

Read a platform reference file only when one exists for that target:

- **Slack:** [slack.md](slack.md). Required for MCP delivery, mentions, `.cursor/references/team-directory.md`, and Slack permalink handling.

For **Discord**, **Telegram**, **Teams**, **Signal**, **WhatsApp**, and similar surfaces that have no file here, follow this skill only. Ordinary markdown-style formatting (bold, lists, links, inline code) is appropriate; nothing platform-specific is required for Discord beyond normal good judgment on links and tone. Optional **Discord** detail: wrap a URL in angle brackets (`<https://example.com>`) to post a clickable link without the large embed preview.

If the platform is unknown, draft with plain messaging-app formatting and do not read a platform file. Platform reference files may override the output or delivery workflow when a platform needs special handling.

## Process

1. Identify the recipient, purpose, required facts, target platform, and desired next action.
2. If critical context is missing, ask one focused question. If the user clearly wants a draft now, write only what can be said accurately.
3. Draft one strong final version by default, not multiple options.
4. Remove filler, throat-clearing, performative polish, and anything that sounds assistant-written.
5. Show the exact message before any delivery. Use a readable format the user can review quickly.

Never copy message drafts to the clipboard.

## Delivery

Delivery is platform-specific:

- If the platform has no available delivery mechanism, return a copyable fenced `text` block.
- If the platform has a delivery mechanism, first show the exact draft and wait for the user's explicit confirmation before sending.
- If the user asks to send before seeing the exact draft, show the draft and ask for confirmation instead of sending immediately.
- If the user has already approved the exact draft and destination, use the platform reference's delivery workflow.

Do not send, post, or run a delivery command until the user has confirmed the exact message and destination.

## Style Rules

- Preserve exact names, technical terms, URLs, numbers, and nuance.
- Keep it short, but not under-explained. Include only details that change what the recipient understands or does next.
- Use normal capitalization. Start messages and sentences with capital letters unless quoting text that intentionally differs.
- Do not fake casualness. No random abbreviations, misspellings, slang, or shortened words to "sound human."
- Avoid em dashes and dash-heavy sentence structure. Prefer a sentence break, comma, colon, or a clear connective word.
- Avoid double dashes (`--`) and subject-style prefixes like `re:` or `re`  unless quoting existing text.
- Prefer plain paragraphs for 1-2 points. Use bullets only when they make the message easier to scan.
- Use formatting lightly: code for exact technical names and bold only when it clarifies the point.
- Avoid AI boilerplate: "Here is a polished version", "I hope this message finds you well", "I wanted to reach out", "Let me know if you need anything else", unless the user explicitly wants that tone.
- Keep the tone direct, warm, and low-drama. Light contractions are fine. Do not over-apologize, over-thank, or over-soften.
- Mention specific people only when the message needs their attention or action.
- Use emojis only when the user asks or the surrounding conversation already clearly uses them.

## Output

Return the final text only, inside a fenced code block by default. Add explanations, variants, or commentary only when the user asks for them or when a platform delivery workflow requires it.

Use a plain text fence by default:

```text
Message goes here.
```

If the message itself contains backtick fences or long backtick runs, use an outer fence that is strictly longer than the longest backtick run inside the message, so the copied message remains exact.