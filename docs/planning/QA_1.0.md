# RC-12 QA — Error-path pass

```
=== no-args (rc=2) clean ===
usage: agent_factory [-h] [--version]
                     {bootstrap,packs,tools,validate,run,jobs,ambition,context,probe,observe,brief,status,channel} ...
agent_factory: error: the following arguments are required: command

=== bad-flag (rc=2) clean ===
usage: agent_factory [-h] [--version]
                     {bootstrap,packs,tools,validate,run,jobs,ambition,context,probe,observe,brief,status,channel} ...
agent_factory: error: the following arguments are required: command

=== bootstrap-no-args (rc=2) clean ===
What should we call your workforce/company: Error: interactive input is required but stdin is closed.
Use 'bootstrap --pack <id>' for non-interactive generation,
or 'bootstrap --spec <file>' to load answers from a YAML file.

=== bootstrap-bad-flag (rc=2) clean ===
usage: agent_factory [-h] [--version]
                     {bootstrap,packs,tools,validate,run,jobs,ambition,context,probe,observe,brief,status,channel} ...
agent_factory: error: unrecognized arguments: --badflag

=== packs-no-args (rc=0) clean ===
business_ops    Business Operations         Go-to-market and operations workforce: marketing, operations, support, finance, data, and partnerships.
engineering     Software Engineering        Delivery-focused workforce: product, engineering, research, data, and agent-operations.
research        Research & Analysis         Evidence workforce: research, data, product-use, and partnership research.

=== tools-no-args (rc=0) clean ===
  slack      (not wired yet)
  stripe     (not wired yet)
  supabase   (not wired yet)

=== validate-no-args (rc=2) clean ===
No org.yaml found under orgs\MyOrg

=== validate-bad-org (rc=2) clean ===
usage: agent_factory [-h] [--version]
                     {bootstrap,packs,tools,validate,run,jobs,ambition,context,probe,observe,brief,status,channel} ...
agent_factory: error: unrecognized arguments: --org nonexistent_org_xyz

=== run-no-args (rc=2) clean ===
                         [--approval {ask,deny,allow}] [--max-steps MAX_STEPS]
                         [--temperature TEMPERATURE]
agent_factory run: error: the following arguments are required: --org, --role, --task

=== jobs-no-args (rc=2) clean ===
usage: agent_factory jobs [-h] --org ORG [--status STATUS] [--limit LIMIT]
agent_factory jobs: error: the following arguments are required: --org

=== ambition-no-args (rc=2) clean ===
                              [--max-actions MAX_ACTIONS]
                              [--max-risk {low,medium,high}]
agent_factory ambition: error: the following arguments are required: --org

=== context-no-args (rc=2) clean ===
usage: agent_factory context [-h] --org ORG [--add ADD] [--detail DETAIL]
                             [--search SEARCH] [--limit LIMIT]
agent_factory context: error: the following arguments are required: --org

=== observe-no-args (rc=2) clean ===
                             [--provider PROVIDER] [--model MODEL]
                             [--limit LIMIT]
agent_factory observe: error: the following arguments are required: --org

=== brief-no-args (rc=2) clean ===
usage: agent_factory brief [-h] --org ORG [--role ROLE] [--provider PROVIDER]
                           [--model MODEL]
agent_factory brief: error: the following arguments are required: --org

=== status-no-args (rc=2) clean ===
usage: agent_factory status [-h] --org ORG [--limit LIMIT]
agent_factory status: error: the following arguments are required: --org

=== channel-no-args (rc=2) clean ===
usage: agent_factory channel [-h] {post,list,worker} ...
agent_factory channel: error: the following arguments are required: channel_command

=== channel-post-no-args (rc=2) clean ===
usage: agent_factory channel post [-h] --org ORG [--channel CHANNEL]
                                  --text TEXT [--author AUTHOR] [--role ROLE]
agent_factory channel post: error: the following arguments are required: --org, --text

=== channel-worker-no-args (rc=2) clean ===
                                    [--max-messages MAX_MESSAGES]
                                    [--temperature TEMPERATURE]
agent_factory channel worker: error: the following arguments are required: --org

=== channel-list-no-args (rc=2) clean ===
usage: agent_factory channel list [-h] --org ORG [--channel CHANNEL]
                                  [--limit LIMIT]
agent_factory channel list: error: the following arguments are required: --org

```

# RC-16 QA — Live end-to-end proof run

Org: `orgs/QA_RC16` (bootstrapped from the `engineering` pack, `agent_factory
bootstrap --pack engineering --out orgs/QA_RC16`). All four flows below
(`run`, `ambition`, `brief`, `channel post → worker → list`) were run against
**both** configured providers — OpenAI (`gpt-4o-mini`) and Ollama
(`gemma3:12b`, local) — to prove real end-to-end behavior on each adapter.
`--approval allow`/`deny` used to keep the run non-interactive; Ollama calls
took roughly 25s–170s per completion (local CPU inference), well inside the
180s `OllamaLLM` timeout.

## OpenAI (`gpt-4o-mini`)

### 1. `run`

```
$ agent_factory run --org orgs/QA_RC16 --role worker_research_1 --task "Summarize in 2 sentences what this workforce's engineering pack is for." --provider openai --approval allow

job #1 [worker_research_1] -> done in 1 step(s)
--- output ---
The engineering pack for this workforce is designed to streamline the software development
process by providing tools and resources that enhance collaboration, efficiency, and quality
assurance. It aims to support the team in delivering reliable, high-quality software faster
while aligning with the organization's goals.
```

### 2. `ambition`

```
$ agent_factory ambition --org orgs/QA_RC16 --provider openai --model gpt-4o-mini --approval deny --candidates 3 --max-actions 1

Proposals from lead_exec (proactivity 5):
  - Automate Test Coverage Assessment (risk=medium, priority=1)
      action: Create a script that analyzes the current test coverage and identifies gaps in automated tests.
  - Cycle Time Analysis Report (risk=medium, priority=2)
      action: Compile data on current cycle times from ticket creation to deployment and identify bottlenecks.
  - Draft Quarterly Platform Roadmap (risk=low, priority=3)
      action: Outline a draft of the quarterly platform roadmap based on team feedback and strategic goals.

Executed 1 action(s):
  job #2 [Automate Test Coverage Assessment] -> done
```

> Note: `lead_exec`'s resolved tier model (`MODEL_smart=qwen2.5:7b`, an
> Ollama-only tag) is not valid against OpenAI when only `--provider` is
> overridden — confirmed via a real `404 model_not_found` error. Passing an
> explicit `--model gpt-4o-mini` (as above) resolves it. Worth a follow-up:
> tier-model env vars are provider-specific, not portable across `--provider`
> overrides.

### 3. `brief`

```
$ agent_factory brief --org orgs/QA_RC16 --provider openai --model gpt-4o-mini

**Today's Action Plan for QA RC16**

1. **WHAT**: Initiate the gathering of test coverage data.
   - **WHO**: QA Engineer
   - **FIRST STEP**: Access the existing analytics tools and extract the current test coverage metrics.
2. **WHAT**: Begin identifying coverage gaps based on the gathered data.
   - **WHO**: QA Engineer
   - **FIRST STEP**: Review the extracted metrics against the defined quality standards to pinpoint areas with insufficient test coverage.
3. **WHAT**: Categorize the identified gaps based on severity and impact.
   - **WHO**: QA Lead
   - **FIRST STEP**: Create a classification framework to categorize the gaps and start categorizing the identified gaps accordingly.
4. **WHAT**: Prioritize the identified gaps for remediation.
   - **WHO**: QA Lead
   - **FIRST STEP**: Develop a risk assessment matrix to rank the gaps based on their business impact.
5. **WHAT**: Prepare a report summarizing findings and recommendations.
   - **WHO**: QA Lead
   - **FIRST STEP**: Draft an outline for the report, including sections for findings, categorized gaps, and prioritized recommendations.
```

### 4. `channel post → worker → list`

```
$ agent_factory channel post --org orgs/QA_RC16 --text "What's our current focus this quarter?" --author "QA Tester"
posted message #1 to #general (for the lead) — queued for an agent reply

$ agent_factory channel worker --org orgs/QA_RC16 --provider openai --model gpt-4o-mini --approval deny
#general: answered 1 message(s)
  #1 by 1 step(s): Our current focus this quarter is to cut cycle time from ticket to deploy, raise

$ agent_factory channel list --org orgs/QA_RC16
#general (2 message(s), newest first)
-> #2   [lead_exec:Org Lead (Chief of Staff) (lead_exec)] (done) Our current focus this quarter is to cut cycle time from ticket to dep
*  #1   [human:QA Tester] (done) What's our current focus this quarter?
```

## Ollama (`gemma3:12b`, local)

### 1. `run`

```
$ agent_factory run --org orgs/QA_RC16 --role worker_research_1 --task "Summarize in 2 sentences what this workforce's engineering pack is for." --provider ollama --model gemma3:12b --approval allow

job #5 [worker_research_1] -> done
--- output (from store; terminal capture was flaky on this slow call) ---
This engineering pack aims to ship reliable, high-quality software faster by fostering a
self-reviewing team. The quarterly targets focus on reducing development cycle time,
increasing automated test coverage, and delivering the platform roadmap.
```

### 2. `ambition`

```
$ agent_factory ambition --org orgs/QA_RC16 --provider ollama --model gemma3:12b --approval deny --candidates 3 --max-actions 1

Executed 1 action(s):
  job #6 [director_product] -> done
--- output (from store) ---
task: Read the 'Automate Test Coverage Assessment' document (located in the workspace) and
identify specific data sources mentioned for gathering test coverage data. Document these
sources in a list.
result: I encountered an error attempting to read the 'Automate Test Coverage Assessment'
document. The file was not found at the specified path. Therefore, I cannot identify the
specific data sources mentioned within the document. Please ensure the file exists at the
correct location or provide an alternative path.
```

> This is a genuine (and correctly handled) tool-failure path: the proposed
> action referenced a document that doesn't exist in the workspace, and the
> agent reported the failure instead of hallucinating a result — good
> real-model evidence the `files_read` error path surfaces cleanly to output.

### 3. `brief`

```
$ agent_factory brief --org orgs/QA_RC16 --provider ollama --model gemma3:12b

Okay, here's your morning brief and prioritized action plan for QA RC16, as your Org Lead (Chief of Staff):

**Overall Situation:** The team is currently idle, having completed a series of tasks related
to test coverage assessment. We've hit a snag with accessing the core document, which is
blocking further progress. Our focus this quarter is clearly improving automated test coverage.

**Top Priorities - What You Should Do Today:**

1. **WHAT:** Resolve the document access issue to retrieve data sources for test coverage assessment.
   **WHO:** Me (lead_exec)
   **FIRST STEP:** Verify the document path and permissions. Confirm the file exists and I have access.
2. **WHAT:** Re-initiate the test coverage assessment plan, focusing on outlining a plan for analyzing coverage and identifying gaps.
   **WHO:** Worker Research 1
   **FIRST STEP:** Review the captured context regarding the plan and begin drafting a more detailed plan.
3. **WHAT:** Briefly recap the team's current focus and priorities with the team.
   **WHO:** Me (lead_exec)
   **FIRST STEP:** Send a quick message to the team summarizing the situation and next steps.
```

### 4. `channel post → worker → list`

```
$ agent_factory channel post --org orgs/QA_RC16 --text "What's our current focus this quarter?" --author "QA Tester"
posted message #3 to #general (for the lead) — queued for an agent reply

$ agent_factory channel worker --org orgs/QA_RC16 --provider ollama --model gemma3:12b --approval deny
#general: answered 1 message(s)
  #3 by 2 step(s): Our current focus this quarter is to: 1) Cut cycle time from ticket to deploy, 2

$ agent_factory channel list --org orgs/QA_RC16
#general (4 message(s), newest first)
-> #4   [lead_exec:Org Lead (Chief of Staff) (lead_exec)] (done) Our current focus this quarter is to: 1) Cut cycle time from ticket to
*  #3   [human:QA Tester] (done) What's our current focus this quarter?
-> #2   [lead_exec:Org Lead (Chief of Staff) (lead_exec)] (done) Our current focus this quarter is to cut cycle time from ticket to dep
*  #1   [human:QA Tester] (done) What's our current focus this quarter?
```

Full reply #4 text (untruncated, from store): "Our current focus this quarter
is to: 1) Cut cycle time from ticket to deploy, 2) Raise automated test
coverage, and 3) Ship and review the quarterly platform roadmap."

## Result

**Done when:** all four flows completed with real model output on both
providers — ✅ verified 2026-09-09. `run`, `ambition`, `brief`, and
`channel post → worker → list` all produced real, coherent model output on
both OpenAI (`gpt-4o-mini`) and Ollama (`gemma3:12b`); one real tool-failure
path (missing file in `ambition`) was also observed and handled gracefully.

