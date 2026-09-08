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
