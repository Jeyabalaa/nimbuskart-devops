# NimbusKart Cost Hygiene — DevOps Assignment

## Overview

This repository is a self-contained FinOps automation solution for NimbusKart, an e-commerce startup whose AWS bill grew from ~$400 to ~$2,100/month due to orphaned and untagged cloud resources. It contains three deliverables: a modular Terraform stack that provisions NimbusKart's staging environment on LocalStack (no real AWS account required), a Python "Cost Janitor" script that detects orphaned EBS volumes, stopped EC2 instances, idle Elastic IPs, and untagged resources, and a GitHub Actions workflow that runs the Janitor on every pull request and posts a cost-waste summary as a PR comment.

---

## How to run locally

### Prerequisites
- Docker (running)
- Python 3.10+
- Terraform 1.5+

### 1. Clone and set up

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
pip install terraform-local boto3
```

### 2. Start LocalStack

```bash
docker run --rm -d \
  -p 4566:4566 \
  -e SERVICES=ec2,s3,iam,sts \
  --name localstack \
  localstack/localstack
```

Wait ~15 seconds for LocalStack to be ready:

```bash
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool
# Look for: "ec2": "available"
```

### 3. Apply Terraform

```bash
cd terraform
tflocal init
tflocal validate
tflocal apply -auto-approve
tflocal output
cd ..
```

### 4. Run the Cost Janitor

```bash
cd janitor
pip install -r requirements.txt

# Dry-run (default) — reports orphans, exits 1 if any found
python janitor.py --dry-run --endpoint-url http://localhost:4566

# View the report
cat report.json
cat report.md

# Delete mode — actually removes orphans (skips Protected=true)
python janitor.py --delete --endpoint-url http://localhost:4566
```

### 5. Run unit tests

```bash
pip install pytest
pytest janitor/tests/ -v
```

### 6. Tear down

```bash
docker stop localstack
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Actions CI                         │
│  ┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │ LocalStack   │   │ Terraform apply │   │ Cost Janitor     │  │
│  │ (service     │──▶│ (provisions VPC,│──▶│ --dry-run        │  │
│  │  container)  │   │  EC2, S3, EBS)  │   │                  │  │
│  └──────────────┘   └─────────────────┘   └────────┬─────────┘  │
│                                                     │            │
│                                           ┌─────────▼─────────┐  │
│                                           │ report.json       │  │
│                                           │ report.md         │  │
│                                           │ (artifacts)       │  │
│                                           └─────────┬─────────┘  │
│                                                     │            │
│                                           ┌─────────▼─────────┐  │
│                                           │ PR Comment        │  │
│                                           │ (if orphans ≥ 1)  │  │
│                                           └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Terraform module layout:
  terraform/
  ├── main.tf              (EC2, SG, S3, orphan EBS)
  ├── variables.tf
  ├── outputs.tf
  └── modules/network/     (VPC, subnets, IGW, route tables)

Cost Janitor scan order:
  1. scan_unattached_ebs()    → EBS volumes in "available" state
  2. scan_stopped_ec2()       → instances stopped > N days
  3. scan_idle_eips()         → EIPs with no AssociationId
  4. scan_untagged_resources()→ running instances/volumes missing tags
```

---

## Decisions & deviations

- **SSH CIDR changed from `0.0.0.0/0` to `10.0.0.0/8` (default)** — opening port 22 to the entire internet is a critical security risk; `var.ssh_allowed_cidr` lets callers override it, but the default is a private range.
- **No single `main.tf` with everything inline** — the spec is explicit that a flat file is a fail; networking is extracted into `modules/network/`.
- **`--dry-run` is the default mode** — the spec says "default", but to make the CLI safe-by-default, `--delete` must be explicitly passed; you cannot accidentally delete resources.
- **`safe_to_auto_delete` is always `false` for EC2 instances** — terminating an instance is irreversible and high-risk; this field is a hint to humans, not a green-light for automation.
- **EIP `age_days` is always 0** — the AWS EC2 `describe_addresses` API does not return an allocation timestamp; this is a known API limitation, documented in `constants.py`.
- **AMI ID is a variable with a plausible default** — LocalStack accepts any string for AMI IDs, so the default `ami-0c02fb55956c7d316` (Amazon Linux 2 in us-east-1) is illustrative but not validated against LocalStack.
- **S3 bucket name must be globally unique** — `var.log_bucket_name` should be overridden per deployment; the default may collide if multiple reviewers run this simultaneously.

---

## Trade-offs

With one more week I would: (1) replace static pricing constants with live calls to the AWS Price List API so cost estimates stay accurate; (2) add multi-account scanning via AWS Organizations and cross-account IAM role assumption; (3) extend the Janitor to cover RDS idle instances, unused Lambda layers, and orphaned Load Balancers; (4) implement the GCP provider in `janitor/providers/gcp.py` as a working proof of the plugin architecture described in `DESIGN.md`; (5) add a Slack webhook integration so the FinOps team gets a daily digest without checking GitHub.

---

## AI usage disclosure

- Used Claude Sonnet to generate the initial Terraform module skeleton and the GitHub Actions YAML boilerplate.
- Claude suggested using `WidthType.PERCENTAGE` for a table rendering issue — caught this by reading the docx-js docs and switched to `WidthType.DXA`.
- Wrote the `delete_finding()` function and the `Protected=true` skip logic manually without AI assistance, because the safety semantics of destructive operations required careful, explicit reasoning that I didn't want to delegate to an LLM.
