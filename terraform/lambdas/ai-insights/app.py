import os
import json
import boto3
import datetime
from botocore.response import StreamingBody

ENV = os.environ.get("ENV", "staging")
REPORT_BUCKET = os.environ["REPORT_BUCKET"]
DDB_TABLE = os.environ["DDB_TABLE"]
MODEL_ID = os.environ.get("MODEL_ID", "")
SUMMARY_TOP_N = int(os.environ.get("SUMMARY_TOP_N", "5"))
SNS_TOPIC_ARN = os.environ.get("AI_SNS_TOPIC_ARN")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

s3 = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DDB_TABLE)
sns = boto3.client("sns", region_name=AWS_REGION)

# Bedrock runtime client
try:
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
except Exception:
    bedrock = None

def iso_ts():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def list_recent_runs(limit=10):
    items = []
    try:
        resp = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('pk').eq(f"ENV#{ENV}"),
            Limit=limit,
            ScanIndexForward=False
        )
        items = resp.get("Items", [])
    except Exception:
        items = []
    return items

def build_prompt(env, runs):
    # Build the top resources string
    top_resources = []
    for r in runs:
        if "top_offenders" in r:
            for o in r["top_offenders"]:
                top_resources.append(f"{o.get('resource_id')} | {o.get('action_taken', 'skipped')}")

    top_resources = "\n".join(f"- {t}" for t in top_resources[:SUMMARY_TOP_N]) or "No recent offenders found."
    # load template
    try:
        with open("templates/summary_prompt.txt", "r") as f:
            tmpl = f.read()
    except Exception:
        tmpl = """You are a cloud cost optimization assistant.
Company priority: cost savings first; safety always.
Environment: {env}
Top resources:
{top_resources}
Write a 150-250 word, bullet-first executive summary with:
- 3 prioritized action items
- One safety note about what not to do
Tone: concise, actionable.
"""
    return tmpl.replace("{{env}}", env).replace("{{top_resources}}", top_resources)

def call_bedrock(prompt):
    if not bedrock:
        return "Bedrock client not available in this environment."
    if not MODEL_ID:
        return "MODEL_ID not configured."
    try:
        payload = {"inputText": prompt}
        resp = bedrock.invoke_model(modelId=MODEL_ID, contentType="application/json", accept="application/json", body=json.dumps(payload))
        # resp['body'] is a streaming body; read it
        body: StreamingBody = resp.get("body")
        if body:
            text = body.read().decode("utf-8")
            # Many Bedrock models return text directly or JSON with content; return raw for now
            return text
        return json.dumps(resp)
    except Exception as e:
        return f"Bedrock invocation error: {str(e)}"

def lambda_handler(event, context):
    runs = list_recent_runs(10)
    prompt = build_prompt(ENV, runs)
    ai_text = call_bedrock(prompt)
    ts = iso_ts()
    key = f"{ENV}/ai_summaries/summary-{ts}.txt"
    try:
        s3.put_object(Bucket=REPORT_BUCKET, Key=key, Body=ai_text)
    except Exception:
        pass
    # publish to SNS
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=f"Cost Summary - {ENV}", Message=ai_text)
    except Exception:
        pass
    # save compact record to dynamo
    try:
        table.put_item(Item={"pk": f"ENV#{ENV}", "sk": f"AI#{ts}", "summary_key": key, "created": ts})
    except Exception:
        pass
    return {"status": "ok", "summary_key": key}
