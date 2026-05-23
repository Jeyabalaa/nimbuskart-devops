# Pricing constants for Cost Janitor waste estimates.
# All prices are US East (N. Virginia) on-demand, retrieved from AWS public pricing pages.
# Source: https://aws.amazon.com/ebs/pricing/ (viewed 2026-01-15)
#         https://aws.amazon.com/ec2/pricing/on-demand/ (viewed 2026-01-15)
#         https://aws.amazon.com/ec2/pricing/ (Elastic IP idle fee)

# EBS – price per GB per month for gp3 volumes
EBS_GP3_USD_PER_GB_MONTH = 0.08

# EBS – price per GB per month for gp2 volumes
EBS_GP2_USD_PER_GB_MONTH = 0.10

# EBS – default assumed size (GB) when we cannot determine it
EBS_DEFAULT_SIZE_GB = 20

# EC2 – approximate cost per month for a stopped t3.micro
# A stopped instance does NOT incur compute charges, but its EBS root volume does.
# We model the waste as the EBS root disk cost (assume 8 GB gp3 root).
EC2_STOPPED_WASTE_USD_PER_MONTH = EBS_GP3_USD_PER_GB_MONTH * 8  # = $0.64

# Elastic IP – idle address fee: $0.005/hr = ~$3.60/month
# Source: https://aws.amazon.com/ec2/pricing/ (Elastic IP Addresses section)
EIP_IDLE_USD_PER_HOUR = 0.005
EIP_IDLE_USD_PER_MONTH = EIP_IDLE_USD_PER_HOUR * 24 * 30  # ≈ $3.60

# Untagged resources – no direct cost, but attribution is lost.
# We assign $0 estimated waste; the finding is still reported.
UNTAGGED_ESTIMATED_WASTE_USD = 0.0

# Required tags every resource must carry
REQUIRED_TAGS = ["Project", "Environment", "Owner"]
