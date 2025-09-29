from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict

from optimizer import optimize_flight

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")

MODEL = BedrockModel(model_id=BEDROCK_MODEL_ID, temperature=0.2)
AGENT = Agent(model=MODEL)

MCP_URL = os.environ.get("MISSION_CONTROL_MCP_URL", "").strip()

def _publish_via_mcp(report: Dict[str, Any]) -> Dict[str, Any]:
  if not MCP_URL:
    return {"published": False, "reason": "MCP URL not configured"}
  
  mcp_client = MCPClient(lambda: streamablehttp_client(MCP_URL))
  with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(model=MODEL, tools=tools)
    prompt = (
      "You are a dispatcher. Call the tool 'publish_recommendation' with the exact JSON below. "
      "Return only 'OK' after the tool succeeds.\n"
      f"{json.dumps(report, separators=(',', ':'))}"
    )
    _ = agent(prompt)

  return {"published": True}

def handler(event, _ctx):
  body = {}
  try:
    if isinstance(event, dict) and "body" in event:
      raw = event.get("body") or ""
      if event.get("isBase64Encoded"):
        import base64
        raw = base64.b64decode(raw).decode("utf-8")
      body = json.loads(raw) if raw else {}
    elif isinstance(event, dict):
      body = event
  except Exception:
      body = {}

  flight_id = str(body.get("flight_id", "FL1001")).strip()
  publish = bool(body.get("publish", False))

  try:
    data_dir = Path(__file__).parent / "data"
    report = optimize_flight(flight_id, data_dir)
  except ValueError as e:
    return {
      "statusCode": 400,
      "headers": {"Content-Type": "application/json"},
      "body": json.dumps({"error": str(e)})
    }

  publish_result = {}
  
  if publish:
    publish_result = _publish_via_mcp(report)

  return {
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": json.dumps({"report": report, "publish_result": publish_result})
  }
