<div align="center">

<img src="https://raw.githubusercontent.com/vdutts7/squircle/main/webp/aws.webp" alt="bedrock" width="80" height="80" />
<img src="https://raw.githubusercontent.com/vdutts7/squircle/main/webp/aws-bedrock.webp" alt="opensearch" width="80" height="80" />
<img src="https://raw.githubusercontent.com/vdutts7/squircle/main/webp/aws-aurora.webp" alt="aurora" width="80" height="80" />
<img src="https://raw.githubusercontent.com/vdutts7/squircle/main/webp/claude.webp" alt="python" width="80" height="80" />

<h1 align="center">bedrock-tax</h1>
<p align="center"><i>Replacing OpenSearch Serverless with Aurora x pgvector to cut Bedrock Knowledge Base costs from $700/mo → $50/mo</i></p>

[![Github][github]][github-url]

</div>

<br/>

## Table of Contents

<ol>
    <a href="#problem">Problem</a><br/>
    <a href="#approach">Approach</a><br/>
</ol>

<br/>

## Problem

Our AI agent (used for speeding up oncall triage work) was querying a **AWS Bedrock Knowledge Base** (backed by **AWS OpenSearch Serverless**):
- OpenSearch Serverless requires min **2 OCU** (OpenSearch Compute Units) [quote](https://aws.amazon.com/opensearch-service/pricing/)
- billed at **$350/OCU/month** [quote](https://aws.amazon.com/opensearch-service/pricing/)
- result → a flat **$700/month floor** *regardless of actual query volume*

The KB served **~8,800 documents** across three domains:
- documentation:  **~7,700** chunks
- compliance rules: **~1,100** rules
- code repo metadata: **~5,600** chunks

Realizing the issue:
- AI agent's underlying Bedrock model was Claude 3.5 Haiku (`claude-3-5-haiku-20241022`), which accessed the Knowledge Base thru the `Bedrock Retrieve API` at **$0.00035 per query** [quote](https://aws.amazon.com/bedrock/pricing/)
- at human query volumes this per-query cost was negligible- the $700 floor dominated the bill

But agent traffic is **NOT** human traffic:
- a human triaging a ticket may search the KB **~5 times/hr** → skim results → move on
- the agent doing the same triage blasts the KB **20+ times/5 sec**- every tool call, often further fanning out into parallel crosswalk lookups across docs, security rules, commit history
- a busy oncall week with just **1,000 agent sessions** = **100,000 queries** = **$35/day** in Retrieve fees alone- *on top of the $700 floor(!)*

## Hidden constraint

Bedrock Knowledge Base presents as a single managed service: 
> ingest docs → call `RetrieveCommand` → results

But under the hood, it decomposes into two meters that are actually **decoupled**:

| | Meter | What | Cost ($) | | Alternative |
|---|---|---|---|---|---|
| <img src="https://raw.githubusercontent.com/vdutts7/squircle/main/webp/aws-opensearch.webp" width="40" height="40" alt="OpenSearch" /> | Vector store (backend) | OpenSearch Serverless| $700/mo floor | → | Swap backend (Aurora pgvector), keep interface (`Bedrock Retrieve API`) |
| <img src="https://raw.githubusercontent.com/vdutts7/squircle/main/webp/aws-bedrock.webp" width="40" height="40" alt="Bedrock" /> | Retrieval interface | `Bedrock Retrieve API` | $0.00035 x query [quote](https://aws.amazon.com/bedrock/pricing/) | → | Query backend (vector store) directly via raw SQL |

**Core insight**: cost floor was attached to the backend (vector store), *not to the retrieval interface*

<!-- BADGES -->
[github]: https://img.shields.io/badge/bedrock--tax-000000?style=for-the-badge&logo=github&logoColor=white
[github-url]: https://github.com/vdutts7/bedrock-tax

