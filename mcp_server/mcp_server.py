from __future__ import annotations
import json
import os
import boto3

from mcp.server.fastmcp import FastMCP

SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

mcp = FastMCP("MissionControl")

@mcp.tool()
def publish_recommendation(payload: str) -> str:
  data = json.loads(payload)
  msg = json.dumps({"type": "fuel_recommendation", "data": data})
  boto3.client("sns").publish(TopicArn=SNS_TOPIC_ARN, Message=msg, Subject="FuelOptimization")

  return "OK"

if __name__ == "__main__":
  mcp.run(transport="streamable-http")
