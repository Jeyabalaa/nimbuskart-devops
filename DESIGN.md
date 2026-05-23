# DESIGN.md — Cost Janitor: Hardening, Scale & Multi-Cloud

## Multi-Cloud Reality

To support GCP next quarter (and Azure later) without rewriting the core, the Janitor adopts a **provider plugin pattern**:

```
janitor/
├── core/
│   ├── engine.py        # orchestrates scans, builds report, handles --dry-run/--delete
│   ├── report.py        # schema validation + serialisation
│   └── models.py        # Finding dataclass (cloud-agnostic)
└── providers/
    ├── base.py          # Abstract class: scan_unattached_volumes(), scan_idle_ips(), etc.
    ├── aws.py           # Implements base.py using boto3
    ├── gcp.py           # Implements base.py using google-cloud-compute
    └── azure.py         # Implements base.py using azure-mgmt-compute
```

`engine.py` calls only the abstract interface. Adding GCP means writing `gcp.py` with the same method signatures — zero changes to the engine or report schema. The CLI gains a `--provider aws|gcp|azure` flag, and CI can fan out one job per provider.

---

## Permissions

### Dry-run mode (read-only)

The Janitor needs only Describe/List actions. Minimal IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CostJanitorReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVolumes",
        "ec2:DescribeInstances",
        "ec2:DescribeAddresses",
        "ec2:DescribeTags",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

### Delete mode (additional actions required)

Add only what is needed for each resource type:

```
ec2:DeleteVolume       — for unattached EBS
ec2:TerminateInstances — for stopped EC2 (scope to tagged resources via Condition)
ec2:ReleaseAddress     — for idle EIPs
```

The delete role should be a **separate IAM role** assumed only when `--delete` is passed, with a short session duration (1 hour) and CloudTrail logging mandatory.

---

## Safety Net — Two Failure Modes

**1. Root EBS volume mistaken for an orphan**

If an EC2 instance is stopped and its root volume is detached (e.g. for offline forensics), the Janitor sees an unattached `available` volume and flags it for deletion. Auto-deleting it would destroy the instance's OS disk, causing data loss and requiring re-provisioning.

*Guardrails:* (a) Tag root volumes `Protected=true` via a Terraform default. (b) Cross-reference volume attachment history via CloudTrail before marking `safe_to_auto_delete=true`. (c) Add a `--min-age-days` flag (default 30) so volumes younger than 30 days are never auto-deleted.

**2. Elastic IP used by an external DNS record**

An EIP may be unassociated in AWS (e.g. instance replaced) yet still pointed to by a customer-facing DNS A-record. Releasing it means another AWS customer can claim that IP, causing traffic to be misdirected.

*Guardrails:* (a) Never auto-release EIPs — always set `safe_to_auto_delete=false` for EIPs and require a human approval step (e.g. a GitHub Actions manual approval gate or a Slack approval bot). (b) Check Route53 / external DNS before flagging an EIP as safe to release.

---

## Observability

Publish to **CloudWatch Custom Metrics** (namespace `CostJanitor`) and forward to the FinOps Grafana dashboard via a CloudWatch data source.

| Metric | Source | Alert Threshold |
|---|---|---|
| `OrphansFound` (count) | Janitor report summary | Alert if > 0 for 3 consecutive days (persistent waste) |
| `EstimatedMonthlyWasteUSD` (gauge) | Janitor report summary | Alert if > $100 (absolute waste cap) |
| `JanitorRunDurationSeconds` (timer) | Janitor process timing | Alert if > 300s (scan is timing out or API is slow) |
| `JanitorExitCode` (gauge) | CI/CD step outcome | Alert if ≠ 0 and ≠ 1 (unexpected crash, not just orphans found) |
| `DeletedResourcesCount` (count, delete mode only) | Post-run tally | Alert if > 10 in a single run (unexpectedly large cleanup batch) |

---

## What I Did Not Build

I scoped this implementation to the brief's explicit requirements and left out the following: multi-account scanning (AWS Organizations `describe_accounts` + cross-account role assumption), S3 bucket cost analysis (ListObjectsV2 + Storage Lens), RDS idle instance detection, a Slack/PagerDuty alerting integration for the Janitor output, Terraform state drift detection, and a web UI for FinOps team self-service. These are meaningful production features but would each add a day of work and were not required to prove the core pattern. The provider-plugin architecture above is designed so they can be added incrementally.
