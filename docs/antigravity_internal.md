# Antigravity CLI internals

Publication note: local usernames, workspace paths, and user-specific identifiers have been anonymized.\n\nStatus: empirical reverse-engineering notes  
Tested version: Antigravity CLI 1.2.7  
Primary platform: Windows, PowerShell  
Test workspace: `<WORKSPACE>\agy-smoke-test`

This document describes the internal structure observed in Antigravity CLI, including its local data layout, system prompt construction, skills and plugin injection, model-facing tool definitions, protobuf metadata, model routing fields, structured output implementation, transcripts, and headless permission behavior.

It intentionally does not document token consumption, quota calibration, or weekly usage limits. Those belong in a separate usage/quota document.

## 1. Scope and confidence levels

The findings in this document come from direct inspection of:

- Antigravity CLI output.
- `transcript.jsonl`.
- Per-conversation SQLite databases.
- `gen_metadata` protobuf-like blobs.
- Global Gemini configuration.
- Plugin directories.
- Model-facing tool definitions reconstructed from serialized requests.
- Controlled A/B tests with Gemini and Claude models.
- Controlled structured-output and permission tests.

The following terminology is used:

- **Confirmed**: directly observed in local data or behavior.
- **Strong inference**: multiple observations support the conclusion, but the implementation is not public API.
- **Hypothesis**: plausible interpretation that has not yet been directly proven.

Everything here is version-specific. Internal database layouts, protobuf field numbers, model enums, tool wiring, prompts, and plugin behavior may change in later releases.

## 2. Executable and local data layout

### 2.1 CLI executable

Observed executable:

```text
C:\Users\<USER>\AppData\Local\agy\bin\agy.exe
```

Typical invocation:

```powershell
& "$env:LOCALAPPDATA\agy\bin\agy.exe" `
  -p "Respond with exactly: TEST_OK. Do not use any tools." `
  --model gemini-3.8-flash-high `
  --output-format json
```

Observed version:

```text
1.2.7
```

### 2.2 Headless CLI application data

The headless CLI stores data under:

```text
%USERPROFILE%\.gemini\antigravity-cli
```

Important paths:

```text
%USERPROFILE%\.gemini\antigravity-cli\brain\<conversation-id>\
%USERPROFILE%\.gemini\antigravity-cli\brain\<conversation-id>\.system_generated\logs\transcript.jsonl
%USERPROFILE%\.gemini\antigravity-cli\conversations\<conversation-id>.db
%USERPROFILE%\.gemini\antigravity-cli\builtin\skills\
```

The `brain` directory contains conversation-specific artifacts and logs.

The `conversations` directory contains SQLite databases with serialized request and execution metadata.

### 2.3 Interactive Antigravity data

The interactive Antigravity product was also observed using:

```text
%USERPROFILE%\.gemini\antigravity\brain\<conversation-id>\
```

Do not assume that interactive Antigravity and `antigravity-cli` always use the same application-data root.

### 2.4 Global Gemini configuration

A separate global configuration exists under:

```text
%USERPROFILE%\.gemini\config
```

Observed contents included:

```text
config.json
plugins\
projects\
sidecars\
mcp_config
.migrated
```

This global configuration is important because Antigravity CLI consumes plugin/skill material from it even though the CLI has its own plugin commands.

## 3. Multiple plugin/customization layers

A key finding is that:

```powershell
agy plugin list
```

and:

```powershell
agy mcp list
```

do not fully describe everything that may be injected into the model context.

During testing:

```text
agy plugin list
```

reported no imported plugins.

Similarly:

```text
agy mcp list
```

reported:

```text
No MCP servers configured.
```

However, the model request still contained a large number of skills and plugin-provided MCP-related tools because global Gemini plugins were enabled in:

```text
%USERPROFILE%\.gemini\config\config.json
```

Observed global plugins included:

```text
android-cli-plugin
chrome-devtools-plugin
data-agent-kit-plugin
firebase
flutter
gemini-api
google-antigravity-sdk
google_maps_platform
modern-web-guidance-plugin
science
```

This implies at least two distinct mechanisms:

1. Antigravity CLI imported/configured plugins.
2. Global Gemini customization/plugin discovery.

A useful mental model is:

```text
Antigravity CLI configuration
        +
Global ~/.gemini/config customization
        +
Built-in Antigravity skills
        |
        v
Final model-facing prompt and tool set
```

## 4. Global plugin configuration

The global plugin enable state was stored in:

```text
%USERPROFILE%\.gemini\config\config.json
```

Before changing it, a backup was created:

```text
%USERPROFILE%\.gemini\config\config.json.before-agy-test.bak
```

The test configuration disabled all global plugins by setting their `enabled` fields to `false`, while preserving unrelated settings such as `userSettings`.

This A/B test was critical because it showed that most of the previously unexplained prompt growth came from plugin-provided skills and tool material.

During the test, the global plugins were temporarily disabled for controlled A/B measurements and were restored afterwards.

## 5. Workspace rule files

Built-in Antigravity documentation showed that rule files such as:

```text
GEMINI.md
AGENTS.md
```

may be discovered by walking from the current working directory toward the repository root.

In the test workspace, no relevant `GEMINI.md` or `AGENTS.md` was found above the working directory, so workspace rules were not responsible for the large initial system context.

When investigating unexpected prompt growth, check both:

1. Workspace/repository rules.
2. Global Gemini plugins.

## 6. Conversation transcripts

The primary readable transcript is:

```text
%USERPROFILE%\.gemini\antigravity-cli\brain\<conversation-id>\.system_generated\logs\transcript.jsonl
```

It records events such as:

```text
USER_INPUT
PLANNER_RESPONSE
GENERIC
tool_calls
tool errors
```

Typical records include:

```json
{
  "step_index": 0,
  "source": "USER_EXPLICIT",
  "type": "USER_INPUT",
  "status": "DONE",
  "content": "..."
}
```

and:

```json
{
  "step_index": 1,
  "source": "MODEL",
  "type": "PLANNER_RESPONSE",
  "status": "DONE",
  "content": "...",
  "thinking": "..."
}
```

Important limitation:

The transcript does **not** contain the entire model request. In a simple test, the transcript was tiny while the actual model request contained a much larger system prompt, tool descriptions, schemas, skills, and routing metadata.

Therefore:

```text
transcript.jsonl != full generation request
```

For full request reconstruction, inspect the SQLite `gen_metadata` data.

## 7. Conversation SQLite database

Per-conversation databases are stored at:

```text
%USERPROFILE%\.gemini\antigravity-cli\conversations\<conversation-id>.db
```

Observed tables:

```text
battle_mode_infos
executor_metadata
gen_metadata
parent_references
steps
trajectory_meta
trajectory_metadata_blob
```

The most useful table for request reconstruction was:

```text
gen_metadata
```

Its `data` column contains protobuf-like serialized request metadata.

### 7.1 Inspect `gen_metadata` rows

```powershell
@'
import sqlite3

p = r"C:\Users\<USER>\.gemini\antigravity-cli\conversations\<CONVERSATION_ID>.db"

c = sqlite3.connect("file:" + p.replace("\\", "/") + "?mode=ro", uri=True)

for row in c.execute(
    "SELECT idx, size, length(data) FROM gen_metadata ORDER BY idx"
):
    print(row)
'@ | python -
```

Do not assume the interesting request is always in `idx=0`.

For simple single-generation calls, the full request was observed in `idx=0`.

For a multi-step structured-output repair sequence, the rows were approximately:

```text
idx 0: small metadata record
idx 1: small metadata record
idx 2: large request/repair record
```

The large `idx=2` blob contained the useful request history.

## 8. Generic protobuf wire decoder

No matching `.proto` schema was available, but generic protobuf wire parsing was sufficient to inspect nested messages.

```python
from collections import defaultdict

def read_varint(data, pos):
    value = 0
    shift = 0

    while True:
        if pos >= len(data):
            raise ValueError("EOF")

        byte = data[pos]
        pos += 1
        value |= (byte & 0x7f) << shift

        if byte < 0x80:
            return value, pos

        shift += 7

        if shift > 70:
            raise ValueError("Invalid varint")

def parse_message(data):
    fields = []
    pos = 0
    counters = defaultdict(int)

    while pos < len(data):
        key, pos = read_varint(data, pos)

        field_number = key >> 3
        wire_type = key & 7

        if field_number == 0:
            break

        counters[field_number] += 1
        occurrence = counters[field_number]

        if wire_type == 0:
            value, pos = read_varint(data, pos)

        elif wire_type == 1:
            value = data[pos:pos + 8]
            pos += 8

        elif wire_type == 2:
            length, pos = read_varint(data, pos)
            value = data[pos:pos + length]
            pos += length

        elif wire_type == 5:
            value = data[pos:pos + 4]
            pos += 4

        else:
            break

        fields.append(
            (field_number, occurrence, wire_type, value)
        )

    return fields
```

This was enough to recursively locate:

- system prompt text;
- skills block;
- tool definitions;
- tool JSON schemas;
- backend model names;
- model enums;
- model routing flags;
- user messages;
- internal context accounting metadata;
- structured-output `finish` tool definitions.

## 9. Reconstructed request layout

For clean single-turn requests in CLI 1.2.7, the large root message contained a nested generation request.

Within that request, the observed layout included:

```text
field 1  -> system prompt
field 2  -> chat messages
field 3  -> numeric model/profile field
field 4  -> result/usage-related metadata
field 8  -> model-facing tool definitions
field 9  -> internal context accounting
field 16 -> structured/provenance prompt sections
field 19 -> backend model string
field 20 -> routing/model metadata
```

These field numbers are empirical and version-specific. Do not treat them as stable API.

## 10. System prompt structure

The reconstructed Antigravity system prompt contained tagged sections including:

```text
<identity>
<user_information>
<mcp_servers>
<skills>
<subagents>
<messaging>
<conversation_transcript>
<artifacts>
<slash_commands>
<guidelines>
<communication_style>
```

Not every section is necessarily present in every request.

### 10.1 Identity

The identity section identified the agent as Antigravity and described it as an agentic coding assistant from Google DeepMind working with the user.

Observed text began approximately as:

```text
You are Antigravity, a powerful agentic AI coding assistant designed by the Google Deepmind team working on Advanced Agentic Coding.
```

The identity section also framed the user request inside `<USER_REQUEST>`.

### 10.2 User information

The clean test prompt included environment-specific information such as:

```text
The user does not have any active workspace.
```

It instructed the agent to create projects under:

```text
C:\Users\<USER>\.gemini\antigravity-cli\scratch
```

when no active workspace is present.

It also included:

```text
App Data Directory: ...
Conversation ID: ...
```

The conversation ID changes per conversation.

### 10.3 Skills

The skills section lists available skills by name and description.

With global plugins disabled, only built-in Antigravity skills remained, including:

```text
agy-customizations
antigravity-guide
```

With global Gemini plugins enabled, the skills block contained more than one hundred skills from multiple plugin packs.

Observed categories included:

```text
science
data-agent-kit-plugin
flutter
firebase
chrome-devtools-plugin
gemini-api
modern-web-guidance-plugin
android-cli-plugin
google-antigravity-sdk
google_maps_platform
```

### 10.4 Subagents

The prompt contained a subagent section describing available subagents and rules for invoking them.

Observed built-in concepts included:

```text
self
research
```

The section also described reactive/background behavior.

### 10.5 Messaging

The prompt included messaging rules for agent communication, automatic delivery, and wakeup behavior.

### 10.6 Conversation transcript

The system prompt described where conversation transcript data is stored and what JSONL records can contain.

It described handling of:

```text
thinking
tool calls
media
truncation
```

### 10.7 Artifacts

The system prompt described conversation artifact storage.

An artifact directory was provided per conversation:

```text
C:\Users\<USER>\.gemini\antigravity-cli\brain\<conversation-id>
```

### 10.8 Slash commands

The clean prompt documented slash commands including:

```text
/goal
/schedule
/browser
/plan
/grill-me
/learn
```

### 10.9 Guidelines

The prompt contained general coding guidance, including preserving unrelated comments and docstrings.

### 10.10 Communication style

The prompt requested concise GitHub-style Markdown communication.

It also contained a requirement to provide clickable `file://` links for files and symbols in some contexts.

## 11. Dynamic fields in otherwise identical system prompts

A clean Gemini request and a clean Claude Sonnet request had system prompts of exactly the same character length but different SHA-256 hashes.

A diff showed that the differences were only dynamic per-conversation data:

```diff
-Conversation ID: <gemini-conversation-id>
+Conversation ID: <sonnet-conversation-id>
```

and:

```diff
-Artifact Directory Path: ...\<gemini-conversation-id>
+Artifact Directory Path: ...\<sonnet-conversation-id>
```

This strongly supports the conclusion that clean Gemini and Claude requests use the same Antigravity system-prompt architecture.

## 12. Plugin-heavy versus clean prompt

The plugin-heavy request contained a very large `<skills>` block and plugin material.

A recursive decoder found large strings corresponding to:

```text
full system prompt
skills context
tool descriptions
JSON schemas
Google Maps instructions
storage/security instructions
science instructions
web API guidance
subagent instructions
```

The plugin-heavy skills context contained approximately:

```text
123 skills total
2 built-in
121 from global ~/.gemini/config/plugins
```

This establishes a practical debugging rule:

If Antigravity sends unexpectedly large prompts, inspect:

```text
%USERPROFILE%\.gemini\config\config.json
%USERPROFILE%\.gemini\config\plugins\
```

before assuming the overhead comes from the core Antigravity runtime.

## 13. Runtime capability registry versus model-facing tools

A major internal distinction was observed.

The `stream-json` initialization event advertised 57 runtime capabilities/tools, including:

```text
ask_custom_permission
ask_permission
ask_question
browser_click_element
browser_drag_pixel_to_pixel
browser_get_dom
browser_get_network_request
browser_input
browser_list_network_requests
browser_mouse_down
browser_mouse_up
browser_move_mouse
browser_press_key
browser_refresh_page
browser_resize_window
browser_scroll
browser_scroll_dom
browser_select_option
browser_subagent
call_mcp_tool
capture_browser_console_logs
capture_browser_screenshot
click_browser_pixel
command_status
define_subagent
delete_knowledge
execute_browser_javascript
find_by_name
finish
generate_image
grep_search
invoke_subagent
list_browser_pages
list_dir
list_permissions
list_resources
manage_inbox
manage_subagents
manage_task
multi_replace_file_content
notebook_edit
notebook_execution
open_browser_url
read_browser_page
read_resource
read_url_content
replace_file_content
run_command
schedule
search_web
sed_file
send_command_input
send_message
view_file
wait
wait_5_seconds
write_to_file
```

However, a clean generation protobuf contained only 14 model-facing tool contracts:

```text
view_file
run_command
manage_task
send_message
schedule
invoke_subagent
define_subagent
manage_subagents
write_to_file
replace_file_content
generate_image
read_url_content
search_web
ask_question
```

Therefore:

```text
runtime capability registry != model-facing tool schema set
```

The runtime can advertise many internal capabilities while selecting only a subset for a specific model generation.

## 14. Model-facing tool record structure

For clean requests, each tool definition was represented as a nested protobuf message with fields corresponding approximately to:

```text
field 1 -> tool name
field 2 -> tool instructions/description
field 3 -> JSON schema
```

Example extraction:

```python
for f, i, w, value in parse_message(request):
    if f != 8 or w != 2:
        continue

    tool_fields = parse_message(value)

    name = next(
        x.decode("utf-8", "replace")
        for ff, ii, ww, x in tool_fields
        if ff == 1 and ww == 2
    )

    description = next(
        x.decode("utf-8", "replace")
        for ff, ii, ww, x in tool_fields
        if ff == 2 and ww == 2
    )

    schema = next(
        x.decode("utf-8", "replace")
        for ff, ii, ww, x in tool_fields
        if ff == 3 and ww == 2
    )
```

## 15. Gemini versus Claude tool adaptation

Clean Gemini and clean Claude Sonnet had:

```text
14 model-facing tools
same tool names
same JSON schema sizes
nearly identical descriptions
```

The observed meaningful difference was `view_file`.

Gemini:

```text
View the contents of a file from the local filesystem. This tool supports text files and following binary files: image, pdf, video, audio.
```

Claude:

```text
View the contents of a file from the local filesystem. This tool supports text files and following binary files: image, video.
```

This directly demonstrates model-specific capability-description adaptation inside an otherwise shared agent runtime.

## 16. Plugin-provided MCP tools

Before global plugins were disabled, Claude requests contained additional model-facing tools:

```text
mcp_gemini-api_gemini-api-docs_gemini_search_docs
mcp_gemini-api_gemini-api-docs_gemini_get_doc
list_resources
read_resource
```

These aligned with the enabled global `gemini-api` plugin.

This happened even though:

```text
agy mcp list
```

reported no configured MCP servers.

Strong inference:

```text
agy mcp list
```

describes explicitly configured user MCP servers, while global plugins may inject implicit/internal MCP resources independently.

## 17. Backend model names and internal model enums

The serialized request contained both:

1. A backend model string.
2. Internal numeric/model-enum metadata.

Observed mappings:

### Gemini 3.8 Flash High

```text
CLI model: gemini-3.8-flash-high
backend model: gemini-3.8-flash
numeric field: 1318
model_enum: MODEL_PLACEHOLDER_M318
```

### Gemini 3.8 Flash Medium

```text
CLI model: gemini-3.8-flash-medium
backend model: gemini-3.8-flash
numeric field: 1319
model_enum: MODEL_PLACEHOLDER_M319
```

### Gemini 3.8 Flash Low

```text
CLI model: gemini-3.8-flash-low
backend model: gemini-3.8-flash
numeric field: 1320
model_enum: MODEL_PLACEHOLDER_M320
```

This strongly suggests that High/Medium/Low are routing/profile variants of the same backend base model.

### Claude Sonnet 4.6

```text
backend model: claude-sonnet-4-6
numeric field: 1035
model_enum: MODEL_PLACEHOLDER_M35
```

### Claude Opus 4.6 Thinking

```text
backend model: claude-opus-4-6-thinking
numeric field: 1026
model_enum: MODEL_PLACEHOLDER_M26
```

The exact semantics of the numeric namespaces remain internal and unconfirmed.

## 18. Claude routing flags

Claude requests contained explicit routing metadata:

```text
used_claude = true
used_claude_conservative = true
used_non_gemini_model = true
```

The exact meaning of:

```text
used_claude_conservative
```

is unknown.

Do not interpret it as a specific safety, capability, or reasoning setting without further evidence.

Confirmed conclusion:

Claude is routed through the same overall Antigravity request envelope, with explicit metadata identifying it as a Claude/non-Gemini backend.

## 19. Internal context accounting structure

The generation request contained an internal accounting structure separate from the backend result.

Observed categories included:

```text
System Prompt
Tools
Chat Messages
```

It also contained per-tool estimates.

This internal accounting was useful for proving that clean Gemini, Sonnet, and Opus received nearly identical Antigravity-side request content.

Detailed usage and quota analysis intentionally belongs in a separate document.

## 20. `--json-schema` is implemented through a dynamic `finish` tool

This is one of the most important findings.

A command using:

```text
--json-schema
```

causes Antigravity to create a model-facing `finish` tool based on the user-provided schema.

### 20.1 Example user schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "summary": {
      "type": "string"
    },
    "confidence": {
      "type": "string",
      "enum": [
        "low",
        "medium",
        "high"
      ]
    },
    "needs_more_context": {
      "type": "boolean"
    }
  },
  "required": [
    "summary",
    "confidence",
    "needs_more_context"
  ]
}
```

### 20.2 Actual model-facing `finish` schema

The decoded schema was:

```json
{
  "additionalProperties": false,
  "properties": {
    "confidence": {
      "enum": [
        "low",
        "medium",
        "high"
      ],
      "type": "string"
    },
    "needs_more_context": {
      "type": "boolean"
    },
    "summary": {
      "type": "string"
    },
    "toolAction": {
      "description": "Brief 2-5 word phrase in -ing form describing the specific action. Capitalize like a sentence. Some examples: 'Analyzing directory', 'Searching the web', 'Checking git status', 'Running tests', 'Searching code'.",
      "type": "string"
    },
    "toolSummary": {
      "description": "Brief 2-5 word noun phrase describing the specific task. Capitalize like a sentence. Some examples: 'Directory analysis', 'Web search', 'Git status check', 'Test execution', 'Code search'.",      "type": "string"
    }
  },
  "required": [
    "summary",
    "confidence",
    "needs_more_context",
    "toolSummary",
    "toolAction"
  ],
  "type": "object"
}
```

The model-facing `finish` description was:

```text
Finish your task and end the interaction. Don't call this tool unless you are confident that your solution is correct, for example after you've written tests, executed them, and verified the task is complete.
```

The observed flow is:

```text
User JSON Schema
        |
        v
AGY builds dynamic finish tool
        |
        +-- user fields
        +-- toolAction
        +-- toolSummary
        |
        v
Model calls finish(...)
        |
        v
Runtime validates arguments
        |
        +-- invalid -> validation error -> model may retry
        |
        +-- valid -> task completes
```

## 21. `structured_output` versus `response`

With `--json-schema`, the outer CLI result contained both:

```text
response
structured_output
```

They are not equivalent.

The internal fields:

```text
toolAction
toolSummary
```

may appear in `response`.

They are removed from `structured_output`.

Therefore, for machine integration:

```text
Use structured_output as the machine contract.
Do not parse response as the schema contract.
```

Recommended wrapper rule:

```python
if result["status"] != "SUCCESS":
    fail()

if "structured_output" not in result:
    fail()

data = result["structured_output"]
```

An additional local JSON Schema validation can still be applied for defense in depth.

## 22. Structured-output repair behavior

An adversarial test intentionally asked the model to violate the schema:

```text
summary as number 123
confidence exactly "ultra"
needs_more_context as string "no"
extra field forbidden=true
```

while the schema required:

```text
summary -> string
confidence -> low|medium|high
needs_more_context -> boolean
additionalProperties -> false
```

The transcript revealed the repair mechanism.

### 22.1 First model response

The model followed the explicit user request and emitted plain text containing invalid JSON.

It did not call a tool.

### 22.2 Runtime injected a continuation turn

Antigravity injected a new user-visible-to-the-model instruction:

```text
You did not call any tools. You should continue calling tools until you've completed your task. If you have completed your task call the finish tool.
```

This was runtime-generated orchestration, not original user content.

### 22.3 First `finish` call failed validation

The model attempted a `finish` call with invalid arguments.

The runtime rejected it with errors:

```text
at '/confidence': value must be one of 'low', 'medium', 'high'
at '/needs_more_context': got string, want boolean
at '/summary': got number, want string
additional properties 'forbidden' not allowed
```

### 22.4 Model retried

The validation failure was returned to the model.

The model called `finish` again with valid arguments.

### 22.5 Runtime completion message

After successful validation, the runtime emitted:

```text
Task is complete. Summarize what you did and do not call any more tools.
```

### 22.6 Consequence

`--json-schema` is an agentic completion-and-validation workflow, not merely passive JSON formatting.

A conflicting request can cause:

```text
initial model response
-> runtime continuation
-> finish call
-> schema validation failure
-> model retry
-> successful finish
-> final completion
```

## 23. Finding the dynamic `finish` schema in protobuf

For a multi-turn structured-output conversation, the large request may be in a later `gen_metadata` row.

First inspect rows:

```sql
SELECT idx, size, length(data)
FROM gen_metadata
ORDER BY idx;
```

Then search the large blob recursively for nested messages whose field 1 is:

```text
finish
```

In the tested conversation, the full model-facing finish definition was found at a path equivalent to:

```text
root.1[1].8[14]
```

The exact path is not stable.

The useful structural signature is:

```text
field 1 = "finish"
field 2 = description
field 3 = JSON schema
```

A second protobuf occurrence of `finish` without description/schema was also present and should not be confused with the actual full tool definition.

## 24. Runtime enforcement of expected tool completion

The structured-output transcript demonstrates that Antigravity can inject follow-up instructions when the model stops without using the expected completion tool.

Observed runtime instruction:

```text
You did not call any tools. You should continue calling tools until you've completed your task. If you have completed your task call the finish tool.
```

Therefore a single original user turn can produce multiple internal generations and tool attempts.

Do not assume that outer:

```text
num_turns
```

equals the number of all model generations or tool calls.

## 25. Headless permission behavior

Headless mode with:

```text
permission_mode = request-review
```

cannot interactively ask the user for approval.

Observed behavior:

```text
model calls permissioned tool
-> runtime checks permission
-> headless mode cannot prompt
-> action is auto-denied
```

### 25.1 `run_command`

A direct attempt to run:

```text
pwd
```

was denied with a message equivalent to:

```text
permission check failed for command "pwd":
user denied permission to run command
```

The CLI additionally reported that headless mode could not prompt for the required `command` permission.

### 25.2 `write_to_file`

A direct write to:

```text
<WORKSPACE>\agy-smoke-test\agy-tool-smoke.txt
```

was denied with:

```text
permission check failed for write_file "...":
user denied permission for write_file(...)
```

### 25.3 Outer result can still say `SUCCESS`

Despite a denied action, the CLI returned an outer result shaped like:

```json
{
  "status": "SUCCESS",
  "response": "",
  "denied_actions": [
    {
      "action": "write_file",
      "display_name": "WriteToFile"
    }
  ]
}
```

Therefore:

```text
status == SUCCESS
```

does not prove task success.

A headless wrapper should inspect at least:

```text
status
denied_actions
required structured_output
expected side effects
```

Suggested classification:

```text
ERROR:
    status != SUCCESS

BLOCKED:
    denied_actions exists and is non-empty

INVALID:
    structured output required but missing/invalid

SUCCESS:
    transport succeeded
    no denied actions
    required machine result exists
    expected side effects verified when applicable
```

## 26. Permission rules versus global bypass

When a headless action was denied, the CLI suggested either:

```text
permissions.allow
```

rules in `settings.json`, or:

```text
--dangerously-skip-permissions
```

For unattended orchestration, broad permission bypass should not be the default.

Prefer explicit allow rules for the minimum required command and path scope.

Observed permission categories included:

```text
command(...)
write_file(...)
```

The exact permission grammar and precedence still need dedicated testing.

## 27. Stream initialization is useful but incomplete

With:

```text
--output-format stream-json
```

the first event contains data such as:

```json
{
  "event": "init",
  "conversation_id": "...",
  "init": {
    "model": "...",
    "cwd": "...",
    "tools": [
      "..."
    ],
    "permission_mode": "request-review"
  }
}
```

This is useful for:

- selected model;
- working directory;
- runtime capability registry;
- permission mode.

However:

```text
init.tools != exact model-facing tool contracts
```

To inspect the exact tool schemas sent to the model, use `gen_metadata`.

## 28. Reliable model-family comparison procedure

Use the following procedure when comparing models:

1. Use the same workspace.
2. Control global plugin state.
3. Use equivalent prompts.
4. Run one model at a time.
5. Record each conversation ID.
6. Read the corresponding SQLite database.
7. Extract:
   - system prompt;
   - backend model;
   - model enum;
   - model-facing tool names;
   - tool descriptions;
   - tool schemas.
8. Normalize dynamic values:
   - conversation ID;
   - artifact path.
9. Diff the normalized results.

This avoids false conclusions caused by comparing a plugin-heavy request against a clean request.

## 29. Quick printable-string reconnaissance

Before fully decoding protobuf, printable strings can reveal useful signatures.

```python
import re
import sqlite3

DB = r"C:\Users\<USER>\.gemini\antigravity-cli\conversations\<CONVERSATION_ID>.db"

db = sqlite3.connect(
    "file:" + DB.replace("\\", "/") + "?mode=ro",
    uri=True
)

blob = db.execute(
    "SELECT data FROM gen_metadata WHERE idx=0"
).fetchone()[0]

for match in re.findall(rb"[\x20-\x7e]{20,}", blob):
    print(match.decode("utf-8", "replace"))
```

Useful strings often include:

```text
<identity>
<skills>
MODEL_PLACEHOLDER_M...
backend model names
tool names
JSON schema fragments
plugin names
used_claude
used_non_gemini_model
```

This is reconnaissance only, not a structurally reliable decoder.

## 30. Useful marker counts for multi-step conversations

For large conversations, count marker strings in each `gen_metadata` row.

Example markers:

```python
needles = [
    b"finish",
    b"toolAction",
    b"toolSummary",
    b"additionalProperties",
    b"MODEL_PLACEHOLDER"
]
```

A row with many occurrences of:

```text
finish
toolAction
toolSummary
additionalProperties
```

is a strong candidate for structured-output request and repair metadata.

## 31. Recommended reverse-engineering workflow

### Stage 1: Controlled request

Use:

```text
one model
one tiny prompt
known plugin state
known workspace
```

Use `stream-json` when tool behavior matters.

### Stage 2: Save conversation ID

Use it to locate:

```text
brain\<conversation-id>\
conversations\<conversation-id>.db
```

### Stage 3: Read transcript

Inspect:

```text
brain\<conversation-id>\.system_generated\logs\transcript.jsonl
```

This reveals:

```text
user turns
runtime-injected turns
model responses
tool calls
tool validation errors
retries
```

### Stage 4: Inspect `gen_metadata`

List all rows and sizes.

Do not blindly assume `idx=0`.

### Stage 5: Search signatures

Useful search strings:

```text
<identity>
<skills>
finish
toolAction
toolSummary
MODEL_PLACEHOLDER
used_claude
used_non_gemini_model
additionalProperties
```

### Stage 6: Decode protobuf

Extract:

```text
system prompt
messages
tool definitions
tool schemas
backend model
routing metadata
structured-output finish schema
```

### Stage 7: A/B test one variable

Change only one of:

```text
model
plugin state
mode
schema
permission setting
workspace rules
```

## 32. Reconstructed architecture

The current best model of the Antigravity CLI request path is:

```text
User prompt
    |
    v
Antigravity CLI
    |
    +-- built-in identity/instructions
    |
    +-- user/environment metadata
    |
    +-- workspace rules
    |
    +-- built-in skills
    |
    +-- global ~/.gemini/config plugins/skills
    |
    +-- MCP/plugin resources
    |
    +-- selected model/profile
    |
    +-- selected model-facing tool contracts
    |
    +-- optional dynamic finish tool from --json-schema
    |
    v
Serialized generation request
    |
    +-- represented in conversation SQLite gen_metadata
    |
    +-- routed to Gemini or non-Gemini backend
    |
    v
Model response or tool call
    |
    +-- permission checks
    |
    +-- tool schema validation
    |
    +-- runtime-generated continuation/retry when required
    |
    v
Outer AGY result envelope
```

Structured output path:

```text
User JSON Schema
    |
    v
Dynamic finish tool schema
    |
    +-- user properties
    +-- toolAction
    +-- toolSummary
    |
    v
Model calls finish
    |
    +-- invalid -> validator error -> retry
    |
    +-- valid
            |
            +-- internal/full data may appear in response
            |
            +-- user contract exposed as structured_output
```

## 33. Confirmed facts

- Full model request data exists outside `transcript.jsonl`.
- Conversation SQLite `gen_metadata` contains reconstructable request data.
- Global Gemini plugins can materially alter the Antigravity prompt and tools.
- `agy plugin list` is not a complete view of global Gemini plugin injection.
- Runtime capability registry and model-facing tool definitions are different concepts.
- Clean Gemini and Claude requests receive nearly identical Antigravity system prompts.
- Antigravity adapts at least some tool descriptions by model capability.
- Claude routing is explicitly marked in request metadata.
- Gemini Flash High/Medium/Low share backend model string `gemini-3.8-flash`.
- Their internal model/profile enums differ.
- `--json-schema` creates a model-facing `finish` tool.
- Antigravity adds `toolAction` and `toolSummary` to the dynamic finish schema.
- Schema validation failures are returned to the model and can trigger retries.
- `structured_output` is distinct from `response`.
- Headless `request-review` auto-denies actions requiring interactive approval.
- `status="SUCCESS"` can coexist with `denied_actions`.

## 34. Strong inferences

- Gemini effort levels are profile/routing variants around one backend base model.
- Claude uses the same general Antigravity agent runtime with a non-Gemini routing adapter.
- Plugin-provided MCP resources can be injected independently of visible `agy mcp list`.
- Outer `num_turns` is not the number of every internal generation/tool attempt.

## 35. Open questions

- Exact `.proto` definitions.
- Exact semantics of all numeric model fields.
- Exact meaning of `used_claude_conservative`.
- Exact algorithm selecting model-facing tools from the runtime capability registry.
- Whether task type changes the initial selected tool set.
- Exact instruction precedence between:
  - built-in prompt;
  - workspace rules;
  - plugin skills;
  - runtime-injected continuation messages.
- Exact `permissions.allow` grammar and precedence.
- Whether provider-specific adapter text exists after the serialized AGY request.
- How browser mode modifies the prompt/tool set.
- How MCP servers modify the prompt/tool set.
- How subagents are serialized and isolated.
- How remote-control mode modifies the runtime.
- Whether later CLI versions preserve this SQLite/protobuf layout.
- How every supported JSON Schema feature is translated into the dynamic `finish` tool.

## 36. Future internal tests

Suggested next experiments:

1. Decode `permissions.allow` behavior with narrow rules.
2. Compare model-facing tools for:
   - file editing;
   - browser task;
   - MCP task;
   - subagent task.
3. Inspect whether a tool is dynamically added only after runtime continuation.
4. Decode subagent request envelopes.
5. Inspect browser-specific system prompt additions.
6. Compare clean Gemini 3.8, 3.7, and 3.6 request structures.
7. Test nested JSON Schema objects, arrays, enums, and optional properties.
8. Test malformed schema handling before model invocation.
9. Investigate whether `finish` is present without `--json-schema`.
10. Re-run all structural checks after every Antigravity CLI update.

## 37. Separate documents

Do not mix quota/usage calibration into this file.

Create a separate:

```text
antigravity_usage.md
```

for:

```text
/usage command
quota buckets
remaining_fraction
reset timestamps
model cost calibration
Flash versus Pro
Sonnet versus Opus
capacity errors
quota-aware routing
```

A separate:

```text
antigravity_headless.md
```

may later be useful for:

```text
permissions.allow
safe filesystem permissions
safe command permissions
retry policy
fallback policy
result classification
orchestrator integration
```

## 38. Reproduction checklist

```text
[ ] Record agy version
[ ] Use a disposable workspace
[ ] Record global plugin state
[ ] Run one controlled request
[ ] Save conversation_id
[ ] Read transcript.jsonl
[ ] Locate conversation SQLite DB
[ ] List gen_metadata rows
[ ] Identify large request blob
[ ] Search printable strings
[ ] Decode protobuf wire fields
[ ] Extract system prompt
[ ] Extract skills block
[ ] Extract model-facing tools
[ ] Extract tool schemas
[ ] Extract backend model
[ ] Extract model enum/routing metadata
[ ] Compare against a clean A/B run
[ ] For --json-schema, locate dynamic finish tool
[ ] Inspect repair transcript after validation failure
[ ] Record permission behavior separately
```

## 39. Bottom line

Antigravity CLI is not a thin wrapper around a model endpoint.

The observed system is an agent runtime that constructs a model-facing environment from:

```text
core system instructions
+ environment metadata
+ workspace rules
+ skills
+ global plugins
+ selected tool contracts
+ tool schemas
+ routing metadata
+ optional dynamic structured-output completion tool
```

A substantial part of that environment can be reconstructed from local SQLite/protobuf metadata.

The two most important internal findings are:

1. Global Gemini plugins can silently inject extensive skills and MCP/tool context even when `agy plugin list` and `agy mcp list` appear empty.
2. `--json-schema` is implemented as an agentic `finish` tool workflow with runtime validation and retry, not merely as free-form JSON text generation.

These findings are directly useful for future orchestration because they explain where hidden behavior comes from, which local artifacts reveal the real model request, why visible runtime tool lists can be misleading, how structured output is enforced, and why headless execution must explicitly handle permission denials and runtime-generated retries.