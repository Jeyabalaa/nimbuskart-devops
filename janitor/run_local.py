import json, sys, os
from moto import mock_aws
import boto3

os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = ""

@mock_aws
def run():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    s3  = boto3.client("s3",  region_name="us-east-1")

    print("[setup] Creating fake AWS resources...")

    vpc = ec2.create_vpc(CidrBlock="10.20.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]

    subnet1 = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.20.1.0/24", AvailabilityZone="us-east-1a")
    subnet1_id = subnet1["Subnet"]["SubnetId"]

    sg = ec2.create_security_group(GroupName="web-sg", Description="Web SG", VpcId=vpc_id)

    for i in range(1, 3):
        ec2.run_instances(
            ImageId="ami-12345678", MinCount=1, MaxCount=1,
            InstanceType="t3.micro", SubnetId=subnet1_id,
            TagSpecifications=[{"ResourceType": "instance", "Tags": [
                {"Key": "Name", "Value": f"web-{i}"},
                {"Key": "Project", "Value": "nimbuskart"},
                {"Key": "Environment", "Value": "staging"},
                {"Key": "Owner", "Value": "devops-team"},
                {"Key": "ManagedBy", "Value": "terraform"},
            ]}]
        )

    s3.create_bucket(Bucket="nimbuskart-staging-app-logs")

    orphan = ec2.create_volume(
        AvailabilityZone="us-east-1a", Size=10, VolumeType="gp3",
        TagSpecifications=[{"ResourceType": "volume", "Tags": [
            {"Key": "Project", "Value": "nimbuskart"},
            {"Key": "Environment", "Value": "staging"},
            {"Key": "Owner", "Value": "devops-team"},
            {"Key": "ManagedBy", "Value": "terraform"},
        ]}]
    )
    print(f"[setup] Orphan EBS created: {orphan['VolumeId']}")

    stopped = ec2.run_instances(
        ImageId="ami-12345678", MinCount=1, MaxCount=1,
        InstanceType="t3.micro", SubnetId=subnet1_id,
        TagSpecifications=[{"ResourceType": "instance", "Tags": [
            {"Key": "Project", "Value": "nimbuskart"},
            {"Key": "Environment", "Value": "staging"},
            {"Key": "Owner", "Value": "devops-team"},
            {"Key": "ManagedBy", "Value": "terraform"},
        ]}]
    )
    stopped_id = stopped["Instances"][0]["InstanceId"]
    ec2.stop_instances(InstanceIds=[stopped_id])
    print(f"[setup] Stopped EC2 created: {stopped_id}")

    untagged = ec2.run_instances(
        ImageId="ami-12345678", MinCount=1, MaxCount=1,
        InstanceType="t3.micro", SubnetId=subnet1_id
    )
    print(f"[setup] Untagged instance created: {untagged['Instances'][0]['InstanceId']}")

    print("\n[setup] Done. Running janitor...\n" + "="*60)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from janitor import scan_unattached_ebs, scan_stopped_ec2, scan_untagged_resources, build_report, build_markdown
    from pathlib import Path

    findings = []
    findings += scan_unattached_ebs(ec2)
    findings += scan_stopped_ec2(ec2, stopped_days=14)
    findings += scan_untagged_resources(ec2)

    print(f"\n[janitor] Found {len(findings)} orphan(s).")

    report = build_report(findings, "000000000000", "us-east-1")
    markdown = build_markdown(report)

    out = Path("output")
    out.mkdir(exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(markdown, encoding="utf-8")

    print("[janitor] Report saved to output/report.json and output/report.md")
    print("\n" + "="*60)
    print(markdown.encode("ascii", errors="replace").decode())
    return len(findings)

if __name__ == "__main__":
    sys.exit(1 if run() > 0 else 0)
