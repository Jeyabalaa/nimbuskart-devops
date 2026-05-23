# Walkthrough Video

## Video Link

> **TODO:** Replace this with your Loom / YouTube unlisted / Google Drive link before submitting.

Link: _[add your video URL here]_  
Length: ≤ 5 minutes

---

## Transcript / Outline

The walkthrough covers the following (≈ 5 min):

1. **[0:00 – 1:00] Start LocalStack & apply Terraform**
   - `docker run` LocalStack
   - `tflocal init && tflocal apply -auto-approve`
   - Show `terraform output` — VPC ID, subnet IDs, bucket name, orphan EBS volume ID

2. **[1:00 – 2:30] Run the Cost Janitor & walk through a finding**
   - `python janitor/janitor.py --dry-run`
   - Open `report.json`, point to the unattached EBS volume finding
   - Show `estimated_monthly_cost_usd`, `safe_to_auto_delete`, and `tags` fields

3. **[2:30 – 3:30] One design decision I'm proud of**
   - The provider plugin architecture in `DESIGN.md` — adding GCP requires only a new `providers/gcp.py` file, zero changes to the engine
   - Alternatively: the `Protected=true` guard in `delete_finding()` — a single tag prevents any auto-deletion, giving ops teams a simple escape hatch

4. **[3:30 – 4:30] One thing I would change**
   - Replace the static per-unit pricing in `constants.py` with a call to the AWS Price List API so cost estimates stay accurate as AWS adjusts pricing
   - Add multi-account support via AWS Organizations `describe_accounts` + cross-account role assumption

5. **[4:30 – 5:00] Show CI workflow green on a PR**
   - Navigate to GitHub Actions tab, show the `cost-janitor` job passing
   - Point to the uploaded artifacts and (if orphans found) the PR comment
