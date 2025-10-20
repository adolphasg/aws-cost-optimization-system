import os
import json
import boto3
import datetime

ENV = os.environ.get("ENV", "staging")
REPORT_BUCKET = os.environ["REPORT_BUCKET"]
DDB_TABLE = os.environ["DDB_TABLE"]
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

s3 = boto3.client("s3", region_name=AWS_REGION)
ec2 = boto3.client("ec2", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DDB_TABLE)

def iso_ts():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def load_latest_report():
    prefix = f"{ENV}/reports/"
    try:
        objs = s3.list_objects_v2(Bucket=REPORT_BUCKET, Prefix=prefix).get("Contents", [])
        if not objs:
            return None, None
        latest = sorted(objs, key=lambda x: x["LastModified"])[-1]
        key = latest["Key"]
        body = s3.get_object(Bucket=REPORT_BUCKET, Key=key)["Body"].read()
        return json.loads(body), key
    except Exception:
        return None, None

def lambda_handler(event, context):
    report, key = load_latest_report()
    if not report:
        return {"status": "no_report_found"}

    run_ts = iso_ts()
    actions = []
    for f in report.get("findings", []):
        rid = f["resource_id"]
        rtype = f["resource_type"]
        if rtype == "ec2":
            try:
                tags_resp = ec2.describe_tags(Filters=[{"Name":"resource-id","Values":[rid]}])
                tagdict = {}
                for t in tags_resp.get("Tags", []):
                    tagdict[t["Key"]] = t["Value"]
            except Exception:
                tagdict = {}
            # Safety checks
            if tagdict.get("Env") != ENV:
                actions.append({"resource_id": rid, "skipped_with_reason": "Env tag missing or mismatched"})
                continue
            if tagdict.get("Critical", "false").lower() == "true":
                actions.append({"resource_id": rid, "skipped_with_reason": "marked_critical"})
                continue
            # Stop instance
            if not DRY_RUN:
                try:
                    ec2.stop_instances(InstanceIds=[rid])
                    ec2.create_tags(Resources=[rid], Tags=[{"Key":"CostManaged","Value":"stopped"},{"Key":"CostActionAt","Value":run_ts}])
                    actions.append({"resource_id": rid, "action_taken": "stopped"})
                except Exception as e:
                    actions.append({"resource_id": rid, "skipped_with_reason": f"error_stopping:{str(e)}"})
            else:
                actions.append({"resource_id": rid, "action_taken": "simulated_stop"})
        elif rtype == "s3":
            # Tag bucket
            if not DRY_RUN:
                try:
                    s3.put_bucket_tagging(Bucket=rid, Tagging={"TagSet":[{"Key":"CostManaged","Value":"true"},{"Key":"CostActionAt","Value":run_ts}]})
                    actions.append({"resource_id": rid, "action_taken": "tagged_bucket"})
                except Exception as e:
                    actions.append({"resource_id": rid, "skipped_with_reason": f"error_tagging:{str(e)}"})
            else:
                actions.append({"resource_id": rid, "action_taken": "simulated_tag_bucket"})
        else:
            actions.append({"resource_id": rid, "skipped_with_reason": "unsupported_resource_type"})

    # Save run summary to DynamoDB
    summary = {
        "pk": f"ENV#{ENV}",
        "sk": f"RUN#{run_ts}",
        "run_id": f"run-{run_ts}",
        "env": ENV,
        "totals": {"actions": len(actions)},
        "top_offenders": [a for a in actions[:10]],
        "timestamp": run_ts
    }
    try:
        table.put_item(Item=summary)
    except Exception:
        pass

    # write report with actions appended
    report["actions_taken"] = actions
    new_key = f"{ENV}/reports/run-{run_ts}-actions.json"
    try:
        s3.put_object(Bucket=REPORT_BUCKET, Key=new_key, Body=json.dumps(report))
    except Exception:
        pass

    return {"status": "ok", "actions": len(actions)}
