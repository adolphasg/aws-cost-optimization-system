import os
import json
import boto3
import datetime
from decimal import Decimal

ENV = os.environ.get("ENV", "staging")
REPORT_BUCKET = os.environ["REPORT_BUCKET"]
DDB_TABLE = os.environ["DDB_TABLE"]
CPU_THRESHOLD = float(os.environ.get("CPU_THRESHOLD", "5.0"))
CPU_WINDOW_DAYS = int(os.environ.get("CPU_WINDOW_DAYS", "7"))
S3_EMPTY_DAYS = int(os.environ.get("S3_EMPTY_DAYS", "30"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

ec2 = boto3.client("ec2", region_name=AWS_REGION)
cw = boto3.client("cloudwatch", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DDB_TABLE)
cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)

def iso_ts():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def get_cpu_avg(instance_id, days):
    end = datetime.datetime.utcnow()
    start = end - datetime.timedelta(days=days)
    try:
        resp = cw.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start,
            EndTime=end,
            Period=3600,
            Statistics=["Average"]
        )
        dps = resp.get("Datapoints", [])
        if not dps:
            return 0.0
        avg = sum(dp["Average"] for dp in dps) / len(dps)
        return round(avg, 3)
    except Exception:
        return 0.0

PRICING = {
    "t2.micro": 0.0116,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    # extend as needed
}

def estimate_monthly(instance_type):
    hourly = PRICING.get(instance_type, 0.05)
    return round(hourly * 24 * 30, 2)

def put_metric_idle_count(count):
    try:
        cloudwatch.put_metric_data(
            Namespace="CostOptimizer",
            MetricData=[{
                "MetricName": "IdleResources.Count",
                "Dimensions": [{"Name": "Env", "Value": ENV}, {"Name": "ResourceType", "Value": "ec2"}],
                "Value": count,
                "Unit": "Count"
            }]
        )
    except Exception:
        pass

def put_metric_savings(amount):
    try:
        cloudwatch.put_metric_data(
            Namespace="CostOptimizer",
            MetricData=[{
                "MetricName": "EstimatedSavings.MonthlyUSD",
                "Dimensions": [{"Name": "Env", "Value": ENV}],
                "Value": amount,
                "Unit": "None"
            }]
        )
    except Exception:
        pass

def save_to_dynamo(item):
    try:
        table.put_item(Item=item)
    except Exception:
        pass

def lambda_handler(event, context):
    run_ts = iso_ts()
    findings = []
    estimated_total = 0.0

    # EC2: list instances filtered by tag Env=ENV
    try:
        resp = ec2.describe_instances(Filters=[
            {"Name": "tag:Env", "Values": [ENV]},
            {"Name": "instance-state-name", "Values": ["running", "stopped", "stopping"]}
        ])
    except Exception:
        resp = {"Reservations": []}

    for r in resp.get("Reservations", []):
        for inst in r.get("Instances", []):
            iid = inst["InstanceId"]
            itype = inst.get("InstanceType", "unknown")
            cpu_avg = get_cpu_avg(iid, CPU_WINDOW_DAYS)
            idle = cpu_avg < CPU_THRESHOLD
            savings = estimate_monthly(itype) if idle else 0.0
            if idle:
                estimated_total += savings
            item = {
                "pk": f"ENV#{ENV}",
                "sk": f"RESOURCE#{iid}#{run_ts}",
                "resource_id": iid,
                "resource_type": "ec2",
                "env": ENV,
                "last_seen": run_ts,
                "idle_reason": f"cpu_avg={cpu_avg}",
                "metrics_snapshot": {"cpu_avg": Decimal(str(cpu_avg))},
                "estimated_monthly_cost_savings": Decimal(str(round(savings, 2))),
                "risk_flags": []
            }
            findings.append(item)
            save_to_dynamo(item)

    # S3: check buckets (limited permission)
    try:
        buckets = s3.list_buckets().get("Buckets", [])
    except Exception:
        buckets = []

    for b in buckets:
        name = b["Name"]
        # We only consider buckets that include project name to avoid scanning account-wide buckets you can't access
        if not name.startswith(os.environ.get("PROJECT_PREFIX", "")) and not name.startswith(f"{os.environ.get('PROJECT_PREFIX', '')}-{ENV}"):
            # Skip buckets not obviously related to project
            continue
        try:
            obj = s3.list_objects_v2(Bucket=name, MaxKeys=1)
            empty = obj.get("KeyCount", 0) == 0
            if empty:
                item = {
                    "pk": f"ENV#{ENV}",
                    "sk": f"RESOURCE#s3:{name}#{run_ts}",
                    "resource_id": name,
                    "resource_type": "s3",
                    "env": ENV,
                    "last_seen": run_ts,
                    "idle_reason": "bucket_empty",
                    "metrics_snapshot": {},
                    "estimated_monthly_cost_savings": Decimal("0.10"),
                    "risk_flags": []
                }
                findings.append(item)
                save_to_dynamo(item)
        except Exception:
            continue

    # Write report to S3
    report = {
        "run_id": f"run-{run_ts}",
        "env": ENV,
        "timestamp": run_ts,
        "findings": findings
    }
    try:
        s3.put_object(Bucket=REPORT_BUCKET, Key=f"{ENV}/reports/run-{run_ts}.json", Body=json.dumps(report, default=str))
    except Exception:
        pass

    # Publish metrics
    put_metric_idle_count(sum(1 for f in findings if f["resource_type"] == "ec2"))
    put_metric_savings(estimated_total)

    return {"status": "ok", "findings": len(findings)}
