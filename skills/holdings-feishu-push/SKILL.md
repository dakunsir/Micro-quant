---
name: holdings-feishu-push
description: Create or update a Feishu document for the current holdings recommendation and send a concise link and summary to an explicitly identified Feishu recipient.
metadata:
  short-description: Publish holdings recommendations to Feishu
---

# Holdings Feishu Push

Use this skill when the user asks to publish current holdings, planned trades, or a rebalance recommendation to Feishu. It coordinates one structured document and one concise message. It does not execute trades or claim that a recommendation is a filled order.

## Authorization And Inputs

Require explicit authorization immediately before both external writes: creating/updating the document and sending the message.

Require:

- the holdings or recommendation source;
- a recipient ID and its exact type: `open_id`, `union_id`, `user_id`, `email`, or `chat_id`;
- the message content or permission to summarize the current recommendation.

Never infer a recipient type from an ID prefix. `ou_...` and `oc_...` are clues only, not validation.

Use the running portfolio endpoint first when it is available:

```text
http://127.0.0.1:8767/api/live-portfolio
```

Otherwise use the explicitly named current data product or generated output. Do not fill missing prices, quantities, execution dates, or holdings with defaults.

## Document Workflow

1. Read the current recommendation and record its signal date, planned execution date, status, data boundary, candidate count, target count, per-stock amount, and execution rules.
2. Distinguish confirmed positions from planned buys and deferred candidates. An empty paper-state file means confirmed holdings are unknown or zero only when the source explicitly says so; do not convert a missing broker position into a real holding.
3. With the configured `feishu-mcp` document tools, call `get_feishu_root_folder_info` when no target is supplied. Create the document with `create_feishu_document` using a `folderToken` or `wikiContext`; never invent a destination.
4. Fill the document with headings and tables using `batch_create_feishu_blocks` and `create_feishu_table`. Include:
   - current confirmed holdings, or an explicit no-confirmed-holdings statement;
   - planned buys with name, industry, research rank, target amount, and Monday action;
   - deferred candidates and the order in which they may replace blocked buys;
   - planned industry distribution and actual industry distribution only when actual positions exist;
   - data boundary, backtest summary, and pre-open checks.
5. Verify the returned document ID/revision and read the document blocks or metadata before sending its link.

The document is a research and execution-planning record. It is not a broker statement or a transaction confirmation.

## Message Workflow

Send only after the document has been verified. The message should contain:

- the document link;
- signal date and planned execution date;
- current confirmed holdings status;
- planned buy count, target amount, and defer/limit-up rule;
- a compact list of planned buys;
- a clear statement that the content is pending execution when no fills are recorded.

Use the bundled `scripts/send_message.py` with the official `lark-oapi` SDK for IM messages. The current `feishu-mcp@0.3.2` exposes document, folder, task, and member tools, but no IM message-send tool; do not claim that MCP sent a message.

```powershell
python skills/holdings-feishu-push/scripts/send_message.py `
  --receive-id "<recipient-id>" `
  --receive-id-type open_id `
  --text "<verified document link and concise summary>"
```

The helper reads `FEISHU_APP_ID` and `FEISHU_APP_SECRET` only from the process environment. Never write credentials, access tokens, or secrets to this repository, a generated document, or logs.

## Feishu Configuration

The MCP must use stdio when registered with Codex:

```toml
[mcp_servers.feishu]
command = "npx"
args = ["-y", "feishu-mcp@0.3.2", "--stdio"]
```

The application needs document permissions, a published version, bot availability for the recipient, and message permissions for IM delivery. Tenant/app credentials do not require a manually refreshed `user_access_token`. User authentication is only needed for MCP features that explicitly require user identity, such as user-scoped tasks, calendar, or member operations.

If the MCP's local scope validator reports stale or unused-module requirements, do not treat a local bypass as authorization. A temporary `FEISHU_SCOPE_VALIDATION=false` diagnostic may be used only to test the real API; stop on the API's permission error and report the missing scopes.

## Completion And Failure Rules

Report completion only when:

- document creation/update returned a document ID and a revision or equivalent success result;
- document metadata or blocks were read back successfully;
- message delivery returned `code=0` and a `message_id`.

On failure, report the Feishu code, message, and log ID without exposing credentials. Do not blindly retry invalid recipient, permission, bot-availability, or content errors. A document success with message failure is a partial result and must be reported as such.
