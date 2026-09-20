# Antigravity CLI usage and quota behavior

Publication note: local usernames, workspace paths, and user-specific identifiers have been anonymized.\n\nStatus: empirical usage and quota notes  
Tested version: Antigravity CLI 1.2.7  
Plan observed: Google AI Plus  
Primary platform: Windows, PowerShell  
Test workspace: `<WORKSPACE>\agy-smoke-test`

This document records observed Antigravity CLI usage reporting, weekly quota buckets, model cost calibration, quota inspection commands, capacity errors, and practical guidance for quota-aware routing.

Internal prompt construction, protobuf decoding, model-facing tools, plugins, and structured-output internals are documented separately in `antigravity_internal.md`.

## 1. Scope

This document answers four practical questions:

1. How do we read current Antigravity quota from the CLI?
2. Which models share which quota bucket?
3. How much weekly quota did controlled model calls consume?
4. How should a future orchestrator use this information?

All quota-cost measurements below are empirical measurements from one Google AI Plus account on Antigravity CLI 1.2.7.

They are not official fixed token limits.

Google/Antigravity may change:

- bucket sizes;
- model weighting;
- token pricing weights;
- refresh policy;
- model availability;
- model aliases;
- quota calculations;
- plan behavior.

Treat the measured values as calibration data, not contractual limits.

## 2. The best machine-readable quota command

The most useful command discovered is:

```powershell
& "$env:LOCALAPPDATA\agy\bin\agy.exe" -p "/usage" --output-format json
```

This is handled by the CLI itself.

In the observed run it returned:

```text
duration_seconds = 0
num_turns = 0
input_tokens = 0
output_tokens = 0
thinking_tokens = 0
total_tokens = 0
```

Therefore `/usage` is suitable for polling quota without making a model inference call.

It is preferable to scraping the interactive TUI.

## 3. `/usage` JSON structure

Observed outer structure:

```json
{
  "conversation_id": "",
  "status": "SUCCESS",
  "response": "...",
  "duration_seconds": 0,
  "num_turns": 0,
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "thinking_tokens": 0,
    "cache_read_tokens": 0,
    "total_tokens": 0
  },
  "command": {
    "name": "usage",
    "data": {
      "description": "...",
      "groups": [
        {
          "name": "Gemini Models",
          "description": "Models within this group: Gemini Flash, Gemini Pro",
          "buckets": [
            {
              "id": "gemini-weekly",
              "name": "Weekly Limit Remaining",
              "description": "...",
              "window": "weekly",
              "remaining_fraction": 0.8791952133178711,
              "reset_time": "2026-09-26T22:16:37Z"
            }
          ]
        },
        {
          "name": "Claude and GPT models",
          "description": "Models within this group: Claude Opus, Claude Sonnet, GPT-OSS",
          "buckets": [
            {
              "id": "3p-weekly",
              "name": "Weekly Limit Remaining",
              "description": "...",
              "window": "weekly",
              "remaining_fraction": 0.7084000110626221,
              "reset_time": "2026-09-26T22:25:09Z"
            }
          ]
        }
      ]
    }
  }
}
```

The important machine fields are:

```text
command.data.groups[].buckets[].id
command.data.groups[].buckets[].remaining_fraction
command.data.groups[].buckets[].reset_time
```

## 4. Observed weekly buckets

Two independent weekly buckets were observed.

### 4.1 Gemini bucket

Bucket ID:

```text
gemini-weekly
```

Models described by the CLI as sharing this bucket:

```text
Gemini Flash
Gemini Pro
```

### 4.2 Third-party bucket

Bucket ID:

```text
3p-weekly
```

Models described by the CLI as sharing this bucket:

```text
Claude Opus
Claude Sonnet
GPT-OSS
```

The tests confirmed that use of a Gemini model changed only `gemini-weekly`.

Use of Claude changed only `3p-weekly`.

A failed GPT-OSS capacity request changed neither observed token usage nor the model-call usage counters.

## 5. Interactive `/usage`

Inside the interactive Antigravity CLI, the command:

```text
/usage
```

displayed approximately:

```text
Gemini Models          Weekly Limit Remaining  88%
Claude and GPT models  Weekly Limit Remaining  71%
```

The TUI display rounds the remaining value.

It is useful for humans but not suitable for measuring small quota deltas.

For experiments and automation, use:

```text
-p "/usage" --output-format json
```

because it exposes the precise floating-point `remaining_fraction`.

## 6. PowerShell quota display

A convenient PowerShell command:

```powershell
(& "$env:LOCALAPPDATA\agy\bin\agy.exe" -p "/usage" --output-format json |
    ConvertFrom-Json
).command.data.groups |
ForEach-Object {
    $group = $_

    $_.buckets | ForEach-Object {
        [PSCustomObject]@{
            Group             = $group.name
            Bucket            = $_.id
            RemainingFraction = $_.remaining_fraction
            RemainingPct      = $_.remaining_fraction * 100
            Reset             = $_.reset_time
        }
    }
} | Format-Table -AutoSize
```

Note that PowerShell may render decimal separators according to the local Windows locale.

For example:

```text
0,851047217845917
```

is the same numeric value as:

```text
0.851047217845917
```

in JSON.

Do not parse formatted PowerShell table text when the original JSON is available.

## 7. Raw machine-oriented PowerShell extraction

For scripts, avoid `Format-Table` and keep objects or JSON.

Example:

```powershell
$usage = & "$env:LOCALAPPDATA\agy\bin\agy.exe" `
    -p "/usage" `
    --output-format json |
    ConvertFrom-Json

$buckets = @{}

foreach ($group in $usage.command.data.groups) {
    foreach ($bucket in $group.buckets) {
        $buckets[$bucket.id] = $bucket
    }
}

$buckets["gemini-weekly"].remaining_fraction
$buckets["3p-weekly"].remaining_fraction
```

For an orchestrator, the bucket IDs should be treated as keys rather than relying on localized or human-readable group names.

## 8. Statusline as an alternative telemetry source

Antigravity also exposes machine-readable state to a custom statusline command.

A captured statusline payload included:

```json
{
  "model": {
    "id": "Gemini 3.8 Flash (High)",
    "display_name": "Gemini 3.8 Flash (High)",
    "effort": "high"
  },
  "version": "1.2.7",
  "context_window": {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "context_window_size": 1048576,
    "used_percentage": 0,
    "remaining_percentage": 100,
    "current_usage": null
  },
  "quota": {
    "3p-weekly": {
      "remaining_fraction": 0.7084,
      "reset_time": "2026-09-26T22:25:09Z",
      "reset_in_seconds": 601038
    },
    "gemini-weekly": {
      "remaining_fraction": 0.8827704,
      "reset_time": "2026-09-26T22:16:37Z",
      "reset_in_seconds": 600526
    }
  },
  "agent_state": "idle",
  "sandbox": {
    "enabled": false
  },
  "plan_tier": "Google AI Plus"
}
```

The statusline feed is useful when an already-running interactive session must expose:

- active model;
- effort;
- current context-window telemetry;
- agent state;
- plan tier;
- quota;
- reset countdown.

For a standalone orchestrator that only needs quota, `/usage --output-format json` is simpler.

## 9. Statusline capture example

A simple PowerShell statusline sink:

```powershell
$payload = [Console]::In.ReadToEnd()

$payload | Set-Content `
    -LiteralPath '<WORKSPACE>\agy-smoke-test\agy-status-payload.json' `
    -Encoding utf8

try {
    $state = $payload | ConvertFrom-Json
    Write-Output "AGY state captured | $($state.model.display_name)"
}
catch {
    Write-Output "AGY state captured"
}
```

It was configured interactively with:

```text
/statusline pwsh -NoProfile -File <WORKSPACE>\agy-smoke-test\agy-status-dump.ps1
```

A quoted path was initially passed through incorrectly in this specific invocation, so an unquoted path was used because the path contained no spaces.

## 10. Plan tier observed

The statusline payload reported:

```text
plan_tier = Google AI Plus
```

All calibration numbers in this document therefore apply specifically to the observed Google AI Plus setup.

Do not assume the same bucket behavior for other plans.

## 11. Weekly reset timestamps observed

During the experiment:

```text
gemini-weekly reset:
2026-09-26T22:16:37Z

3p-weekly reset:
2026-09-26T22:25:09Z
```

The two buckets had independent reset timestamps approximately eight and a half minutes apart.

Therefore a future orchestrator should not assume that all weekly buckets reset simultaneously.

Use each bucket's own:

```text
reset_time
```

## 12. Token accounting fields

Normal model calls returned:

```json
"usage": {
  "input_tokens": ...,
  "output_tokens": ...,
  "thinking_tokens": ...,
  "cache_read_tokens": ...,
  "total_tokens": ...
}
```

In all observed examples:

```text
total_tokens = input_tokens + output_tokens
```

`thinking_tokens` was not added again on top of `output_tokens`.

Example:

```text
input_tokens    = 11973
output_tokens   = 255
thinking_tokens = 205
total_tokens    = 12228
```

because:

```text
11973 + 255 = 12228
```

Therefore, for observed CLI 1.2.7 output:

```text
Do not calculate:
input + output + thinking
```

That would double-count thinking.

The safest rule is to trust the reported:

```text
total_tokens
```

and treat `thinking_tokens` as a breakout metric.

## 13. Claude thinking telemetry caveat

Claude Sonnet and Claude Opus calls repeatedly reported:

```text
thinking_tokens = 0
```

including the model named:

```text
claude-opus-4-6-thinking
```

This must not be interpreted as proof that the model performed no internal reasoning.

The Antigravity transcript and request behavior showed that Claude was still participating in the same agent runtime.

Practical rule:

```text
Do not use thinking_tokens as a cross-provider measure of reasoning effort.
```

It is provider/backend dependent.

## 14. Controlled quota-probe methodology

The model-cost calibration used deliberately similar prompts.

Example:

```powershell
& "$env:LOCALAPPDATA\agy\bin\agy.exe" `
  -p "Respond with exactly: QUOTA_PROBE_OK. Do not use any tools." `
  --model gemini-3.8-flash-high `
  --output-format json
```

Procedure:

1. Read precise bucket `remaining_fraction`.
2. Run exactly one model probe.
3. Do not run any other model request.
4. Read `/usage --output-format json` again.
5. Compute:
   ```text
   quota_delta = before - after
   ```
6. Record model-reported token usage.
7. Compare probes only when prompt/context shape is similar.

This prevents unrelated calls from contaminating the measurement.

## 15. Important limitation of the calibration

Antigravity states in `/usage` that:

```text
Quota is consumed proportionally to the cost of the tokens.
```

Therefore the weekly bucket is not safely modeled as a simple raw-token counter.

The cost may depend on:

- model family;
- model tier;
- input versus output;
- reasoning/output behavior;
- potentially other backend weighting.

Consequently, the `effective capacity` calculations in this document are:

```text
token-equivalent estimates for this specific probe shape
```

not official token limits.

## 16. Gemini 3.8 Flash High probe

Prompt:

```text
Respond with exactly: QUOTA_PROBE_OK. Do not use any tools.
```

Usage:

```text
input_tokens    = 11694
output_tokens   = 45
thinking_tokens = 38
total_tokens    = 11739
```

Quota:

```text
before = 0.8827704000000000
after  = 0.8791952133178711
delta  = 0.0035751866821289
```

Weekly percentage points consumed:

```text
0.35751866821289%
```

Effective full-bucket capacity for this exact workload shape:

```text
11739 / 0.0035751866821289
= approximately 3,283,465 token-equivalents
```

Equivalent full-bucket probe count:

```text
1 / 0.0035751866821289
= approximately 279.71 probes
```

## 17. Gemini 3.8 Flash Medium probe

Prompt:

```text
Respond with exactly: QUOTA_PROBE_MEDIUM_OK. Do not use any tools.
```

Usage:

```text
input_tokens    = 11694
output_tokens   = 43
thinking_tokens = 34
total_tokens    = 11737
```

Quota:

```text
before = 0.875674426555634
after  = 0.872102379798889
delta  = 0.003572046756745
```

Weekly percentage points consumed:

```text
0.3572046756745%
```

Effective full-bucket capacity:

```text
approximately 3,285,791 token-equivalents
```

Equivalent full-bucket probe count:

```text
approximately 279.95 probes
```

## 18. Gemini 3.8 Flash Low probe

Prompt:

```text
Respond with exactly: QUOTA_PROBE_LOW_OK. Do not use any tools.
```

Usage:

```text
input_tokens    = 11692
output_tokens   = 9
thinking_tokens = 0
total_tokens    = 11701
```

Quota:

```text
before = 0.8791952133178711
after  = 0.875674426555634
delta  = 0.0035207867622371
```

Weekly percentage points consumed:

```text
0.35207867622371%
```

Effective full-bucket capacity:

```text
approximately 3,323,405 token-equivalents
```

Equivalent full-bucket probe count:

```text
approximately 284.03 probes
```

## 19. Gemini Flash effort-level comparison

Controlled measurements:

| Model | Input | Output | Thinking | Total | Weekly bucket consumed |
|---|---:|---:|---:|---:|---:|
| Gemini 3.8 Flash High | 11,694 | 45 | 38 | 11,739 | 0.357519% |
| Gemini 3.8 Flash Medium | 11,694 | 43 | 34 | 11,737 | 0.357205% |
| Gemini 3.8 Flash Low | 11,692 | 9 | 0 | 11,701 | 0.352079% |

Relative quota consumption:

```text
Medium / High = approximately 0.9991x
Low / High    = approximately 0.9848x
```

Observed conclusion:

For this short, input-heavy workload, High and Medium were effectively the same cost.

Low was only about 1.5% cheaper than High.

Therefore:

```text
Choosing Flash Low instead of Flash High solely to save weekly quota
provided very little benefit in this test.
```

The more important quota-saving factors are likely:

- reducing repeated agent turns;
- reducing unnecessary context;
- avoiding validation/retry loops;
- avoiding unnecessary model calls;
- choosing Flash instead of Pro where appropriate.

## 20. Gemini 3.1 Pro High probe

Prompt:

```text
Respond with exactly: QUOTA_PROBE_PRO_HIGH_OK. Do not use any tools.
```

Usage:

```text
input_tokens    = 11964
output_tokens   = 247
thinking_tokens = 236
total_tokens    = 12211
```

Quota:

```text
before = 0.872102379798889
after  = 0.861345589160919
delta  = 0.010756790637970
```

Weekly percentage points consumed:

```text
1.075679063797%
```

Effective full-bucket capacity for this workload:

```text
approximately 1,135,190 token-equivalents
```

Equivalent full-bucket probe count:

```text
approximately 92.96 probes
```

## 21. Gemini 3.1 Pro Low probe

Prompt:

```text
Respond with exactly: QUOTA_PROBE_PRO_LOW_OK. Do not use any tools.
```

Usage:

```text
input_tokens    = 11961
output_tokens   = 152
thinking_tokens = 141
total_tokens    = 12113
```

Quota:

```text
before = 0.861345589160919
after  = 0.851047217845917
delta  = 0.010298371315002
```

Weekly percentage points consumed:

```text
1.0298371315002%
```

Effective full-bucket capacity:

```text
approximately 1,176,205 token-equivalents
```

Equivalent full-bucket probe count:

```text
approximately 97.10 probes
```

## 22. Gemini Pro effort-level comparison

Observed models exposed only:

```text
Gemini 3.1 Pro High
Gemini 3.1 Pro Low
```

An attempt to invoke:

```text
gemini-3.1-pro-medium
```

failed immediately with:

```text
model gemini-3.1-pro-medium is not recognized
```

and reported:

```text
duration_seconds = 0
input_tokens = 0
output_tokens = 0
total_tokens = 0
```

So there was no observed quota-consuming inference for that invalid model selection.

Measured Pro comparison:

| Model | Input | Output | Thinking | Total | Weekly bucket consumed |
|---|---:|---:|---:|---:|---:|
| Gemini 3.1 Pro High | 11,964 | 247 | 236 | 12,211 | 1.075679% |
| Gemini 3.1 Pro Low | 11,961 | 152 | 141 | 12,113 | 1.029837% |

Relative quota consumption:

```text
Pro Low / Pro High = approximately 0.9574x
```

So Pro Low was about 4.3% cheaper than Pro High in this test.

## 23. Flash versus Pro

Using the controlled High probes:

```text
Pro High quota delta   = 0.010756790637970
Flash High quota delta = 0.0035751866821289
```

Ratio:

```text
Pro High / Flash High
= approximately 3.0087x
```

Using Pro Low against Flash High:

```text
Pro Low / Flash High
= approximately 2.8805x
```

This is one of the most useful routing observations.

For this input-heavy probe:

```text
Gemini Pro consumed about 3x the fraction of the shared Gemini weekly bucket
compared with Gemini Flash.
```

Unlike Flash Low versus High, the Flash-versus-Pro choice has a large quota impact.

## 24. Claude Sonnet 4.6 probe

CLI model:

```text
claude-sonnet-4-6
```

Displayed model:

```text
Claude Sonnet 4.6 (Thinking)
```

Prompt:

```text
Respond with exactly: QUOTA_PROBE_SONNET_OK. Do not use any tools.
```

Usage:

```text
input_tokens    = 13497
output_tokens   = 33
thinking_tokens = 0
total_tokens    = 13530
```

Quota:

```text
before = 0.708400011062622
after  = 0.683027982711792
delta  = 0.025372028350830
```

Weekly percentage points consumed:

```text
2.537202835083%
```

Effective full-bucket capacity for this specific Sonnet workload:

```text
approximately 533,264 token-equivalents
```

Equivalent full-bucket probe count:

```text
approximately 39.41 probes
```

## 25. Claude Opus 4.6 probe

CLI model:

```text
claude-opus-4-6-thinking
```

Prompt:

```text
Respond with exactly: QUOTA_PROBE_OPUS_OK. Do not use any tools.
```

Usage:

```text
input_tokens    = 13500
output_tokens   = 47
thinking_tokens = 0
total_tokens    = 13547
```

Quota:

```text
before = 0.683027982711792
after  = 0.640555977821350
delta  = 0.042472004890442
```

Weekly percentage points consumed:

```text
4.2472004890442%
```

Effective full-bucket capacity for this workload:

```text
approximately 318,963 token-equivalents
```

Equivalent full-bucket probe count:

```text
approximately 23.54 probes
```

## 26. Sonnet versus Opus

Because Sonnet and Opus share the same `3p-weekly` bucket, their quota deltas can be directly compared much more cleanly than cross-bucket Gemini-versus-Claude percentages.

Measured ratio:

```text
Opus quota delta   = 0.042472004890442
Sonnet quota delta = 0.025372028350830

Opus / Sonnet
= approximately 1.6740x
```

For this probe:

```text
Opus consumed about 67.4% more of the shared third-party weekly quota
than Sonnet.
```

Their raw total token counts were nearly identical:

```text
Sonnet = 13,530
Opus   = 13,547
```

This strongly indicates model-specific quota weighting inside the shared third-party bucket.

## 27. Cross-bucket comparisons require caution

It is tempting to say:

```text
Sonnet is 7.1x more expensive than Flash
```

because:

```text
2.5372 / 0.3575 ~= 7.1
```

But this is not a valid direct token-price conclusion because:

```textSonnet uses 3p-weekly
Flash uses gemini-weekly
```

The absolute sizes of these two weekly buckets are not published by the CLI.

Therefore cross-bucket comparisons should be worded as:

```text
A Sonnet probe consumed X% of its own weekly bucket.
A Flash probe consumed Y% of its own weekly bucket.
```

Do not treat `X / Y` as a universal monetary or per-token cost ratio.

Within a shared bucket, comparisons such as:

```text
Pro versus Flash
Opus versus Sonnet
```

are much more meaningful.

## 28. Summary calibration table

| Model | Bucket | Input | Output | Thinking | Total | Bucket fraction | Weekly percentage |
|---|---|---:|---:|---:|---:|---:|---:|
| Gemini 3.8 Flash High | gemini-weekly | 11,694 | 45 | 38 | 11,739 | 0.003575187 | 0.357519% |
| Gemini 3.8 Flash Medium | gemini-weekly | 11,694 | 43 | 34 | 11,737 | 0.003572047 | 0.357205% |
| Gemini 3.8 Flash Low | gemini-weekly | 11,692 | 9 | 0 | 11,701 | 0.003520787 | 0.352079% |
| Gemini 3.1 Pro High | gemini-weekly | 11,964 | 247 | 236 | 12,211 | 0.010756791 | 1.075679% |
| Gemini 3.1 Pro Low | gemini-weekly | 11,961 | 152 | 141 | 12,113 | 0.010298371 | 1.029837% |
| Claude Sonnet 4.6 | 3p-weekly | 13,497 | 33 | 0 | 13,530 | 0.025372028 | 2.537203% |
| Claude Opus 4.6 | 3p-weekly | 13,500 | 47 | 0 | 13,547 | 0.042472005 | 4.247200% |

## 29. Effective full-bucket probe capacities

These are not official limits.

They are extrapolations from one probe shape.

| Model | Approx. token-equivalent capacity | Approx. identical probes per full bucket |
|---|---:|---:|
| Gemini 3.8 Flash High | 3.283M | 279.71 |
| Gemini 3.8 Flash Medium | 3.286M | 279.95 |
| Gemini 3.8 Flash Low | 3.323M | 284.03 |
| Gemini 3.1 Pro High | 1.135M | 92.96 |
| Gemini 3.1 Pro Low | 1.176M | 97.10 |
| Claude Sonnet 4.6 | 0.533M | 39.41 |
| Claude Opus 4.6 | 0.319M | 23.54 |

These values should be labeled:

```text
effective token-equivalents for this controlled input-heavy probe
```

not:

```text
official weekly token limits
```

## 30. Current measured snapshot after the calibration sequence

After the measured Gemini and Claude probes, and after the failed GPT-OSS test, the observed precise remaining fractions were:

```text
gemini-weekly = 0.851047217845917
3p-weekly     = 0.640555977821350
```

Equivalent percentages:

```text
Gemini remaining = 85.1047217845917%
3P remaining     = 64.0555977821350%
```

At those remaining levels, if all future requests were identical to the controlled probes, the rough remaining number of calls would be:

| Model workload | Rough identical calls remaining |
|---|---:|
| Flash High | 238.0 |
| Flash Medium | 238.3 |
| Flash Low | 241.7 |
| Pro High | 79.1 |
| Pro Low | 82.6 |
| Sonnet | 25.2 |
| Opus | 15.1 |

These are scenario estimates, not guarantees.

Real agent tasks can vary dramatically in cost.

## 31. Why real tasks can cost much more than probes

The controlled probes were intentionally simple.

Real Antigravity tasks can create additional model turns because of:

- tool execution;
- failed permissions;
- schema validation;
- retries;
- runtime-generated continuation turns;
- subagents;
- browser use;
- large file reads;
- larger conversation history;
- longer reasoning;
- long outputs.

A particularly important test involved deliberately conflicting instructions and a JSON schema.

That run reported:

```text
input_tokens    = 49,845
output_tokens   = 13,134
thinking_tokens = 12,966
total_tokens    = 62,979
num_turns       = 2
```

The transcript showed multiple internal model/tool steps:

```text
plain response
-> runtime continuation
-> invalid finish tool call
-> schema validation error
-> corrected finish call
-> completion
```

Therefore an orchestrator should optimize for:

```text
avoiding unnecessary retries and extra turns
```

rather than focusing only on Low versus High effort modes.

## 32. Plugin overhead also affects usage

Earlier tests with global Gemini plugins enabled had much larger model input contexts.

After disabling unrelated global plugins, simple Gemini input fell substantially.

The exact plugin/context reverse engineering is documented in:

```text
antigravity_internal.md
```

Operational implication:

```text
Unused skills and plugins can consume quota on every request.
```

For dedicated headless workers, a minimal plugin profile can be materially more efficient than a desktop/global profile containing many unrelated skills.

## 33. GPT-OSS 120B capacity behavior

Model:

```text
gpt-oss-120b-medium
```

was listed as available by the CLI.

However, at least two attempts returned:

```text
HTTP 503
status = UNAVAILABLE
retryable = true
No capacity available for model gpt-oss-120b-medium on the server
```

Observed outer result:

```json
{
  "status": "ERROR",
  "response": "",
  "duration_seconds": 0,
  "num_turns": 1,
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "thinking_tokens": 0,
    "cache_read_tokens": 0,
    "total_tokens": 0
  }
}
```

The error also exposed:

```text
error_code = 503
retryable = true
```

No successful GPT-OSS quota calibration was obtained.

Do not assume the 503 was caused specifically by US daytime traffic. The available evidence only proves that the serving backend reported no capacity at those times.

## 34. GPT-OSS fallback rule

A future orchestrator should classify:

```text
503 + retryable=true
```

as a transient provider/model availability failure.

Recommended behavior:

```text
first failure
-> short bounded backoff
-> retry only if latency budget allows
-> otherwise fall back to another configured model
```

Do not repeatedly hammer the unavailable model.

Also do not count a zero-token 503 as a completed agent task.

## 35. Model list observed during testing

The CLI reported the following available models:

```text
Gemini 3.8 Flash (High)
Gemini 3.8 Flash (Medium)
Gemini 3.8 Flash (Low)

Gemini 3.7 Flash (High)
Gemini 3.7 Flash (Medium)
Gemini 3.7 Flash (Low)

Gemini 3.6 Flash (High)
Gemini 3.6 Flash (Medium)
Gemini 3.6 Flash (Low)

Gemini 3.1 Pro (High)
Gemini 3.1 Pro (Low)

Claude Sonnet 4.6 (Thinking)
Claude Opus 4.6 (Thinking)

GPT-OSS 120B (Medium)
```

Only the specifically measured models in the calibration table should be assigned measured cost coefficients.

Do not automatically transfer Gemini 3.8 Flash measurements to 3.7 or 3.6 without testing.

## 36. Initial routing implications

The measurements suggest a practical first-pass policy.

### Gemini Flash

Use for:

```text
routine coding work
simple analysis
high-volume worker tasks
basic file inspection
cheap parallel agents
```

Observed High/Medium/Low quota difference was very small for a short input-heavy probe.

Choose the effort level primarily for task quality/reasoning needs rather than expected quota savings.

### Gemini Pro

Reserve for:

```text
harder analysis
planning
complex review
escalation from Flash
difficult debugging
```

A Pro probe consumed about three times the Gemini weekly bucket fraction of a comparable Flash probe.

### Claude Sonnet

Use selectively for tasks where Sonnet's behavior or quality is specifically valuable.

It is materially cheaper than Opus inside the same third-party bucket.

### Claude Opus

Treat as an expensive escalation/reviewer model.

A comparable Opus probe consumed about 1.67 times Sonnet's third-party weekly quota.

### GPT-OSS

Treat as opportunistic until capacity proves reliable.

Always provide fallback behavior.

## 37. Suggested quota thresholds for an orchestrator

These are policy suggestions, not Antigravity requirements.

A reasonable starting policy could be:

```text
remaining >= 50%
    normal routing

remaining 25% to 50%
    avoid expensive models for routine work

remaining 10% to 25%
    reserve Pro/Sonnet/Opus for escalation and review

remaining 5% to 10%
    prefer cheapest acceptable model
    reduce speculative parallelism

remaining < 5%
    require explicit override for non-essential work
```

Use separate decisions for:

```text
gemini-weekly
3p-weekly
```

because one bucket can be healthy while the other is nearly exhausted.

## 38. Better routing than fixed thresholds

A more useful orchestrator can estimate the expected quota fraction before choosing a model.

Maintain an empirical cost table:

```text
model
workload_class
observed_input_tokens
observed_output_tokens
quota_delta
timestamp
CLI_version
```

Then estimate:

```text
expected_bucket_cost(model, task_class)
```

and route based on:

```text
required quality
remaining quota
expected cost
retry history
availability
latency budget
```

This is better than assuming a universal cost-per-token number.

## 39. Suggested telemetry record

For every model invocation, store:

```json
{
  "timestamp": "...",
  "conversation_id": "...",
  "model": "...",
  "bucket": "...",
  "quota_before": 0.0,
  "quota_after": 0.0,
  "quota_delta": 0.0,
  "input_tokens": 0,
  "output_tokens": 0,
  "thinking_tokens": 0,
  "cache_read_tokens": 0,
  "total_tokens": 0,
  "duration_seconds": 0.0,
  "status": "...",
  "retryable": false,
  "denied_actions": [],
  "task_class": "..."
}
```

This would allow the orchestrator to learn its own empirical cost model over time.

## 40. Avoid polling quota after every tiny action

Although `/usage` itself was observed as a zero-token CLI command, there is no need to query it excessively.

A future orchestrator can:

```text
read quota before a batch
track estimated local deltas
refresh after expensive calls
refresh after provider errors
refresh periodically
refresh before crossing a policy threshold
```

This reduces unnecessary backend/API traffic even when token usage is zero.

## 41. Quota update precision

The JSON response exposes `remaining_fraction` with substantially more precision than the TUI.

Examples:

```text
0.8791952133178711
0.875674426555634
0.851047217845917
0.64055597782135
```

This was sufficient to measure a single short model call.

Use the numeric JSON value directly.

Do not round before calculating deltas.

## 42. Calibration formula

For one controlled call:

```text
delta = remaining_before - remaining_after
```

Weekly percentage consumed:

```text
weekly_pct = delta * 100
```

Effective full-bucket token-equivalent capacity:

```text
effective_capacity = total_tokens / delta
```

Equivalent number of identical probes in a full bucket:

```text
full_bucket_calls = 1 / delta
```

Approximate identical calls remaining:

```text
remaining_calls = current_remaining_fraction / delta
```

Again, these formulas describe a specific measured workload.

They do not turn the quota bucket into an official raw-token limit.

## 43. Recommended calibration script design

A future calibration utility should:

1. Read `/usage` JSON.
2. Save bucket state.
3. Run exactly one controlled prompt.
4. Capture outer result JSON.
5. Read `/usage` again.
6. Verify the unrelated bucket did not change unexpectedly.
7. Calculate delta.
8. Save all raw data and derived values.
9. Refuse to calculate cost if:
   - another model ran during the measurement;
   - the call retried unexpectedly;
   - the result was a capacity error;
   - the model performed tools;
   - quota could not be refreshed.

This would make future comparisons reproducible.

## 44. Separate model availability from quota

The GPT-OSS result demonstrates that:

```text
model listed in catalog
```

does not imply:

```text
model currently has serving capacity
```

A router should track at least:

```text
catalog_available
recently_servable
quota_available
permission_available
```

as separate dimensions.

For example:

```text
GPT-OSS:
catalog_available = true
recently_servable = false
quota_bucket = 3p-weekly
```

after repeated capacity failures.

## 45. Errors that should not be interpreted as quota exhaustion

Observed examples include:

### Invalid model selection

```text
model ... is not recognized
usage = 0
duration = 0
```

### Provider capacity error

```text
503 UNAVAILABLE
retryable = true
usage = 0
```

### Permission denial

A permission denial may occur after model inference has already consumed tokens.

Therefore it is very different from a zero-token model-selection or capacity failure.

Always inspect:

```text
status
error code
retryable
usage
denied_actions
```

before classifying a failure.

## 46. Current practical conclusions

The most useful findings from the calibration are:

1. `/usage --output-format json` is a precise, zero-model-token quota probe.
2. Gemini and third-party models use separate weekly buckets.
3. Flash High/Medium/Low had almost identical quota cost for the controlled short request.
4. Gemini Pro consumed roughly 3x the Gemini bucket fraction of Flash for a comparable request.
5. Opus consumed about 1.67x the third-party bucket fraction of Sonnet.
6. GPT-OSS was catalog-visible but repeatedly unavailable due to server capacity.
7. Raw token count alone is not enough to predict quota usage across model families.
8. Agent retries and validation loops can dominate usage.
9. Unnecessary plugin context can increase recurring request cost.
10. A future router should query exact bucket state and maintain empirical per-model cost data.

## 47. Open questions

Still worth measuring:

- Gemini 3.7 Flash cost versus 3.8 Flash.
- Gemini 3.6 Flash cost versus 3.8 Flash.
- Input token versus output token weighting.
- Thinking/reasoning token weighting.
- Cache-read behavior and quota cost.
- Long-context cost scaling.
- Tool-heavy task cost.
- Multi-turn conversation cost.
- Subagent cost accounting.
- Whether parallel agents debit quota independently and immediately.
- Whether quota deltas are strictly linear.
- Whether bucket weighting changes near exhaustion.
- Whether reset behavior is a hard reset or rolling accounting internally.
- Whether successful GPT-OSS calls have a distinct weight from Claude.
- How model-cost weighting changes across Antigravity releases and subscription tiers.

## 48. Recommended next measurements

To learn more without wasting excessive quota:

```text
1. Measure one controlled long-output Flash call.
2. Compare with a similar-token input-heavy Flash call.
3. Measure one 3.7 Flash probe.
4. Measure one 3.6 Flash probe.
5. Re-test GPT-OSS only occasionally when useful.
6. Start logging real task quota deltas rather than synthetic probes.
```

Real-task telemetry will eventually be more useful than additional synthetic microbenchmarks.

## 49. Reproduction checklist

```text
[ ] Record CLI version
[ ] Record plan tier
[ ] Read exact /usage JSON
[ ] Save bucket remaining_fraction
[ ] Run exactly one controlled model call
[ ] Save full result JSON
[ ] Record input/output/thinking/total
[ ] Read exact /usage JSON again
[ ] Calculate before - after
[ ] Verify unrelated bucket
[ ] Record reset_time
[ ] Record capacity or permission failures
[ ] Label extrapolations as token-equivalents, not official limits
```

## 50. Bottom line

Antigravity quota should be treated as a model-cost-weighted resource, not a plain raw-token counter.

The CLI exposes enough machine-readable information to build quota-aware orchestration without scraping the UI:

```text
agy -p "/usage" --output-format json
```

The observed Google AI Plus setup had two independently tracked weekly buckets:

```text
gemini-weekly
3p-weekly
```

Controlled probes showed that model selection matters much more than effort level:

```text
Flash High ~= Flash Medium ~= Flash Low
Pro ~= 3x Flash within the Gemini bucket
Opus ~= 1.67x Sonnet within the third-party bucket
```

Those ratios are empirical for the tested workload and version, not permanent product guarantees.

A robust future orchestrator should therefore combine:

```text
precise live quota
+ model availability
+ empirical model cost
+ task difficulty
+ retry history
+ expected context/output size
```

rather than routing solely by raw token count or model name.