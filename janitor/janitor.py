#!/usr/bin/env python3
"""
Cost Janitor — NimbusKart orphan-resource detector.

Usage:
  python janitor.py [--dry-run] [--delete] [--region REGION]
                    [--endpoint-url URL] [--stopped-days N]
                    [--output-dir DIR]

Defaults:
  --dry-run is active unless --delete is explicitly passed.
  --stopped-days 14
  --region us-east-1
  --output-dir .
"""

import argparse
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from constants import (
    EBS_GP3_USD_PER_GB_MONTH,
    EBS_GP2_USD_PER_GB_MONTH,
    EBS_DEFAULT_SIZE_GB,
    EC2_STOPPED_WASTE_USD_PER_MONTH,
    EIP_IDLE_USD_PER_MONTH,
    UNTAGGED_ESTIMATED_WASTE_USD,
    REQUIRED_TAGS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def tags_to_dict(tag_list: list | None) -> dict:
    """Convert AWS [{Key, Value}] tag list to a plain dict."""
    if not tag_list:
        return {}
    return {t["Key"]: t["Value"] for t in tag_list}


def missing_tags(tag_dict: dict) -> list[str]:
    """Return required tags that are absent or empty."""
    return [t for t in REQUIRED_TAGS if not tag_dict.get(t)]


def age_days(dt: datetime) -> int:
    """Return how many whole days ago a UTC datetime was."""
    now = datetime.now(timezone.utc)
    return (now - dt).days


def is_protected(tag_dict: dict) -> bool:
    """Return True if the resource has Protected=true tag."""
    return tag_dict.get("Protected", "").lower() == "true"


def ebs_monthly_cost(volume: dict) -> float:
    """Estimate monthly cost for an EBS volume based on type and size."""
    size = volume.get("Size", EBS_DEFAULT_SIZE_GB)
    vol_type = volume.get("VolumeType", "gp3")
    rate = EBS_GP2_USD_PER_GB_MONTH if vol_type == "gp2" else EBS_GP3_USD_PER_GB_MONTH
    return round(rate * size, 2)


# ── Scanners ──────────────────────────────────────────────────────────────────

def scan_unattached_ebs(ec2_client) -> list[dict]:
    """Find EBS volumes in 'available' state (not attached to any instance)."""
    findings = []
    paginator = ec2_client.get_paginator("describe_volumes")
    for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
        for vol in page["Volumes"]:
            tag_dict = tags_to_dict(vol.get("Tags"))
            create_time = vol.get("CreateTime", datetime.now(timezone.utc))
            findings.append({
                "resource_id": vol["VolumeId"],
                "resource_type": "ebs_volume",
                "reason": "unattached",
                "age_days": age_days(create_time),
                "estimated_monthly_cost_usd": ebs_monthly_cost(vol),
                "tags": {t: tag_dict.get(t) for t in REQUIRED_TAGS},
                "suggested_action": "delete",
                "safe_to_auto_delete": is_protected(tag_dict) is False and not missing_tags(tag_dict) == REQUIRED_TAGS,
                "_raw_resource": vol,
                "_tag_dict": tag_dict,
            })
    return findings


def scan_stopped_ec2(ec2_client, stopped_days: int) -> list[dict]:
    """Find EC2 instances stopped for more than stopped_days days."""
    findings = []
    paginator = ec2_client.get_paginator("describe_instances")
    for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]):
        for reservation in page["Reservations"]:
            for inst in reservation["Instances"]:
                tag_dict = tags_to_dict(inst.get("Tags"))
                # StateTransitionReason contains e.g. "User initiated (2026-01-01 10:00:00 GMT)"
                # Fall back to LaunchTime if we cannot parse it.
                raw_reason = inst.get("StateTransitionReason", "")
                stopped_at = None
                if "(" in raw_reason and ")" in raw_reason:
                    try:
                        date_str = raw_reason.split("(")[1].split(")")[0].replace(" GMT", "+00:00")
                        stopped_at = datetime.fromisoformat(date_str)
                    except (ValueError, IndexError):
                        pass
                if stopped_at is None:
                    stopped_at = inst.get("LaunchTime", datetime.now(timezone.utc))

                days_stopped = age_days(stopped_at)
                if days_stopped >= stopped_days:
                    findings.append({
                        "resource_id": inst["InstanceId"],
                        "resource_type": "ec2_instance",
                        "reason": f"stopped_for_{days_stopped}_days",
                        "age_days": days_stopped,
                        "estimated_monthly_cost_usd": EC2_STOPPED_WASTE_USD_PER_MONTH,
                        "tags": {t: tag_dict.get(t) for t in REQUIRED_TAGS},
                        "suggested_action": "terminate",
                        "safe_to_auto_delete": False,  # EC2 termination is always high-risk
                        "_raw_resource": inst,
                        "_tag_dict": tag_dict,
                    })
    return findings


def scan_idle_eips(ec2_client) -> list[dict]:
    """Find Elastic IPs not associated with any instance or network interface."""
    findings = []
    response = ec2_client.describe_addresses()
    for addr in response.get("Addresses", []):
        # Unassociated EIPs have no AssociationId
        if addr.get("AssociationId"):
            continue
        tag_dict = tags_to_dict(addr.get("Tags"))
        findings.append({
            "resource_id": addr.get("AllocationId", addr.get("PublicIp", "unknown")),
            "resource_type": "elastic_ip",
            "reason": "unassociated",
            "age_days": 0,  # EIPs have no creation timestamp in the API
            "estimated_monthly_cost_usd": EIP_IDLE_USD_PER_MONTH,
            "tags": {t: tag_dict.get(t) for t in REQUIRED_TAGS},
            "suggested_action": "release",
            "safe_to_auto_delete": not is_protected(tag_dict),
            "_raw_resource": addr,
            "_tag_dict": tag_dict,
        })
    return findings


def scan_untagged_resources(ec2_client) -> list[dict]:
    """
    Find EC2 instances and EBS volumes missing one or more required tags.
    Stopped/unattached resources already reported above are excluded to avoid duplicates.
    """
    findings = []

    # Check running instances
    paginator = ec2_client.get_paginator("describe_instances")
    for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["running", "pending"]}]):
        for reservation in page["Reservations"]:
            for inst in reservation["Instances"]:
                tag_dict = tags_to_dict(inst.get("Tags"))
                absent = missing_tags(tag_dict)
                if absent:
                    findings.append({
                        "resource_id": inst["InstanceId"],
                        "resource_type": "ec2_instance",
                        "reason": f"missing_tags:{','.join(absent)}",
                        "age_days": age_days(inst.get("LaunchTime", datetime.now(timezone.utc))),
                        "estimated_monthly_cost_usd": UNTAGGED_ESTIMATED_WASTE_USD,
                        "tags": {t: tag_dict.get(t) for t in REQUIRED_TAGS},
                        "suggested_action": "tag",
                        "safe_to_auto_delete": False,
                        "_raw_resource": inst,
                        "_tag_dict": tag_dict,
                    })

    # Check attached volumes for missing tags
    paginator = ec2_client.get_paginator("describe_volumes")
    for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["in-use"]}]):
        for vol in page["Volumes"]:
            tag_dict = tags_to_dict(vol.get("Tags"))
            absent = missing_tags(tag_dict)
            if absent:
                findings.append({
                    "resource_id": vol["VolumeId"],
                    "resource_type": "ebs_volume",
                    "reason": f"missing_tags:{','.join(absent)}",
                    "age_days": age_days(vol.get("CreateTime", datetime.now(timezone.utc))),
                    "estimated_monthly_cost_usd": UNTAGGED_ESTIMATED_WASTE_USD,
                    "tags": {t: tag_dict.get(t) for t in REQUIRED_TAGS},
                    "suggested_action": "tag",
                    "safe_to_auto_delete": False,
                    "_raw_resource": vol,
                    "_tag_dict": tag_dict,
                })

    return findings


# ── Deletion actions ──────────────────────────────────────────────────────────

def delete_finding(ec2_client, finding: dict) -> str:
    """Attempt to delete/release the resource. Returns a status string."""
    rid = finding["resource_id"]
    rtype = finding["resource_type"]

    if is_protected(finding.get("_tag_dict", {})):
        return f"SKIPPED (Protected=true): {rid}"

    try:
        if rtype == "ebs_volume" and finding["reason"] == "unattached":
            ec2_client.delete_volume(VolumeId=rid)
            return f"DELETED volume {rid}"

        elif rtype == "ec2_instance" and finding["reason"].startswith("stopped_for_"):
            ec2_client.terminate_instances(InstanceIds=[rid])
            return f"TERMINATED instance {rid}"

        elif rtype == "elastic_ip":
            ec2_client.release_address(AllocationId=rid)
            return f"RELEASED EIP {rid}"

        else:
            return f"NO-OP (action '{finding['suggested_action']}' requires manual intervention): {rid}"

    except ClientError as exc:
        return f"ERROR deleting {rid}: {exc}"


# ── Report builders ───────────────────────────────────────────────────────────

def build_report(findings: list[dict], account_id: str, region: str) -> dict:
    """Build the report.json structure (strips internal _raw_resource keys)."""
    clean_findings = []
    for f in findings:
        clean = {k: v for k, v in f.items() if not k.startswith("_")}
        clean_findings.append(clean)

    total_waste = sum(f["estimated_monthly_cost_usd"] for f in clean_findings)

    return {
        "scan_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "account_id": account_id,
        "region": region,
        "summary": {
            "total_orphans": len(clean_findings),
            "estimated_monthly_waste_usd": round(total_waste, 2),
        },
        "findings": clean_findings,
    }


def build_markdown(report: dict) -> str:
    """Build a human-readable Markdown summary from a report dict."""
    ts = report["scan_timestamp"]
    total = report["summary"]["total_orphans"]
    waste = report["summary"]["estimated_monthly_waste_usd"]

    lines = [
        "# 🧹 Cost Janitor Report",
        "",
        f"**Scan time:** {ts}  ",
        f"**Region:** {report['region']}  ",
        f"**Account:** {report['account_id']}  ",
        "",
        f"## Summary",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total orphans found | {total} |",
        f"| Estimated monthly waste | ${waste:.2f} |",
        "",
    ]

    if total == 0:
        lines.append("✅ **No orphans detected. All clear!**")
        return "\n".join(lines)

    lines.append("## Findings")
    lines.append("")

    by_type: dict[str, list] = {}
    for f in report["findings"]:
        by_type.setdefault(f["resource_type"], []).append(f)

    for rtype, items in by_type.items():
        lines.append(f"### {rtype.replace('_', ' ').title()} ({len(items)})")
        lines.append("")
        lines.append("| Resource ID | Reason | Age (days) | Est. Monthly Cost | Safe to Auto-Delete |")
        lines.append("|-------------|--------|-----------|-------------------|---------------------|")
        for item in items:
            safe = "✅" if item["safe_to_auto_delete"] else "❌"
            lines.append(
                f"| `{item['resource_id']}` "
                f"| {item['reason']} "
                f"| {item['age_days']} "
                f"| ${item['estimated_monthly_cost_usd']:.2f} "
                f"| {safe} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("*Generated by Cost Janitor. Run with `--delete` to remediate (Protected=true resources are always skipped).*")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NimbusKart Cost Janitor")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="Report findings without deleting anything (default)")
    mode.add_argument("--delete", action="store_true", default=False,
                      help="Delete/release detected orphans (skips Protected=true)")
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    parser.add_argument("--endpoint-url", default=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
                        help="Override the AWS endpoint URL (for LocalStack)")
    parser.add_argument("--stopped-days", type=int, default=14,
                        help="Minimum days an EC2 instance must be stopped to be flagged (default: 14)")
    parser.add_argument("--output-dir", default=".", help="Directory to write report.json and report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    delete_mode = args.delete
    dry_run = not delete_mode

    print(f"[janitor] mode={'DELETE' if delete_mode else 'DRY-RUN'}  region={args.region}  endpoint={args.endpoint_url}")

    ec2 = boto3.client(
        "ec2",
        region_name=args.region,
        endpoint_url=args.endpoint_url,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )

    # Resolve account ID (LocalStack always returns 000000000000)
    try:
        sts = boto3.client(
            "sts",
            region_name=args.region,
            endpoint_url=args.endpoint_url,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        )
        account_id = sts.get_caller_identity()["Account"]
    except Exception:
        account_id = "000000000000"

    print("[janitor] Scanning for orphaned resources...")
    findings: list[dict] = []
    findings += scan_unattached_ebs(ec2)
    findings += scan_stopped_ec2(ec2, args.stopped_days)
    findings += scan_idle_eips(ec2)
    findings += scan_untagged_resources(ec2)

    print(f"[janitor] Found {len(findings)} orphan(s).")

    if delete_mode:
        for finding in findings:
            result = delete_finding(ec2, finding)
            print(f"  {result}")

    report = build_report(findings, account_id, args.region)
    markdown = build_markdown(report)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "report.json"
    md_path = out_dir / "report.md"

    report_path.write_text(json.dumps(report, indent=2, default=str))
    md_path.write_text(markdown)

    print(f"[janitor] Report written to {report_path} and {md_path}")

    # Exit non-zero in dry-run mode when orphans exist (so CI fails the check)
    if dry_run and findings:
        print(f"[janitor] Exiting with code 1 — {len(findings)} orphan(s) found in dry-run mode.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
