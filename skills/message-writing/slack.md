# Slack

Slack delivery uses the Slack MCP server when available. The workflow is always draft first, then send only after explicit user confirmation.

## Draft Format

Draft Slack messages in standard Markdown. This is the readable preview shown to the user and the source sent through MCP with `content_type: "text/markdown"`.

Use:


| Element       | Markdown source syntax                |
| ------------- | ------------------------------------- |
| Bold          | `**text**`                            |
| Italic        | `*text*`                              |
| Inline code   | `text`                                |
| Code block    | Triple backticks                      |
| Link          | `[display text](https://example.com)` |
| Bullet list   | `- item`                              |
| Numbered list | `1. item`                             |
| Blockquote    | `> text`                              |


Use `\n\n` between paragraphs, headings, blockquotes, and list groups. A single newline is only for consecutive list items in the same list.

Return the draft in a fenced `text` block so the user can review the exact message. If the message contains backtick fences or long backtick runs, use an outer fence that is strictly longer than the longest backtick run inside the message.

## Team References

Before resolving org-specific people, channels, or user groups, look for:

```text
.cursor/references/team-directory.md
```

This project-local file is the single source of truth for Slack usernames, Slack IDs, channel IDs, Linear names, product ownership, and similar team-specific facts. Do not bake organization-specific names or channel IDs into this shared skill.

If the team directory is missing or does not contain the person/channel:

1. Use the Slack MCP directory resources or lookup tools when available.
2. Ask one focused question if the result is ambiguous.
3. Never invent Slack usernames, IDs, or channel IDs.

## Mentions

For MCP sends using `content_type: "text/markdown"`, prefer `@username` from the team directory. The Slack MCP markdown converter resolves usernames to clickable mentions.

Do not write raw `<@USER_ID>` mentions in `text/markdown` sends unless the specific MCP server requires Slack mrkdwn instead. Some markdown converters consume angle brackets and break the mention.

## Sending

Use the enabled Slack MCP server for Slack delivery. Before calling an MCP tool, read that tool's descriptor/schema.

When the user asks you to send a Slack message:

1. Draft or revise the message with the root message-writing rules and this Slack reference.
2. Resolve the target channel, DM, thread, and mentions from `.cursor/references/team-directory.md` or Slack MCP lookup.
3. Show the exact draft in a fenced `text` block and state the destination.
4. Ask for confirmation unless the user has already approved this exact draft and destination.
5. After confirmation, call the Slack MCP `conversations_add_message` tool with `content_type: "text/markdown"`, `channel_id`, `text`, and `thread_ts` when replying in a thread.

`content_type: "text/markdown"` accepts standard Markdown and converts it to Slack formatting, including bullets, bold, links, code, and blockquotes.

If the user asks for a Slack draft but does not ask you to send it, only show the draft. Do not discuss manual rich-paste workarounds unless the user asks.

## Reading Messages And Attachments

When the user shares a Slack permalink, fetch the message and attachments through the Slack MCP server. Never use `WebFetch` on a Slack permalink; it usually returns a login wall or times out.

### Permalink To MCP Arguments

A permalink has the shape:

```text
https://<workspace>.slack.com/archives/<CHANNEL_ID>/p<TS_NO_DOT>
```

- `channel_id` is the `C...` segment.
- `thread_ts` / `ts` is the `p...` number with a `.` inserted before the last 6 digits. Example: `p1776768770467469` becomes `1776768770.467469`.

### Fetch The Message

Two useful entry points:

- Shortcut: call `conversations_search_messages` with the full Slack URL as `search_query`.
- Thread reader: call `conversations_replies` with `channel_id`, `thread_ts`, and an appropriate `limit`.

The CSV response may include `FileCount`, `AttachmentIDs`, and `HasMedia`. If `FileCount > 0` or `HasMedia = true`, download the attachments before answering.

### Download Attachments

For each ID in `AttachmentIDs`, call `attachment_get_data`.

Images and binary files return base64. Decode them into a temporary or ignored proof directory, then read the saved file with the image-capable read tool before acting on it. Text files return decoded content directly.

The Slack MCP attachment size limit is usually 5MB. If a file is too large, surface the filename and size and ask the user to paste the attachment into chat.

## Testing New Formatting

When trying a new Slack formatting pattern, test by sending to a DM with the user's approval before using it in public channels.