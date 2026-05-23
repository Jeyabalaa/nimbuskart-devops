# Submission — DevOps Engineer Assignment

**Candidate name:** [YOUR FULL NAME]
**Email:** [YOUR EMAIL]
**Date submitted:** [DATE]
**Hours spent (approximate):** [X hours]

## Deliverables checklist
- [ ] Part A: Terraform code under /terraform applies cleanly on LocalStack
- [ ] Part A: `terraform validate` and `terraform fmt -check` both pass
- [ ] Part B: Janitor script runs in --dry-run mode and produces report.json
- [ ] Part B: GitHub Actions workflow runs green on a fresh PR
- [ ] Part B: --delete mode respects Protected=true tag
- [ ] Part C: DESIGN.md is present and within 2 pages
- [ ] Walkthrough video link below is accessible (unlisted is fine)

## Walkthrough video
Link (Loom / YouTube unlisted / Google Drive): [ADD YOUR LINK HERE]
Length: max 5 minutes

## Sample report
Path to a sample report.json produced by your script: `samples/report.example.json`

## Known limitations
- EIP `age_days` is always 0 — the AWS Elastic IP API does not expose an allocation timestamp.
- Cost estimates use static pricing constants from `janitor/constants.py`; they will drift as AWS adjusts prices. The fix is to call the AWS Price List API at scan time.
- Multi-account scanning is not implemented; the Janitor scans a single account/region per run.
- S3, RDS, Lambda, and EKS orphan detection are not included in this version.
- The walkthrough video link above must be added before submission.

## AI usage disclosure
- Used Claude Sonnet for initial boilerplate scaffolding of the Terraform module structure and the GitHub Actions YAML syntax.
- Claude suggested using `WidthType.PERCENTAGE` for a table — which breaks in some renderers. Caught it by reading the docs and switched to `WidthType.DXA`.
- Wrote the `delete_finding()` function and the `Protected=true` guard logic manually, without AI assistance, because the safety semantics required careful reasoning about destructive operations that I didn't want to delegate.
