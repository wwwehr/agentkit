from pdb import set_trace as bp
import argparse
import os
import json
import requests

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

# Import CDP Agentkit Langchain Extension.
from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper


"""

import logging
import http.client


# Enable HTTP debug logging
http.client.HTTPConnection.debuglevel = 1

# Configure logging to show everything
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True
"""


# Configure a file to persist the agent's CDP MPC Wallet Data.
wallet_data_file = "wallet_data.txt"

load_dotenv()

def _probe_model_name(llm_host: str) -> str:
    res = requests.get(f"{llm_host}/models")
    res.raise_for_status()
    try:
        return res.json()["data"][0]["id"]
    except Exception:
        print("failed to fetch model name from nilai endpoint")
        raise

def initialize_agent():
    """Initialize the agent with CDP Agentkit."""


    llm_reasoning = ChatOpenAI(
        openai_api_base=os.environ["NILLION_NILAI_REASONING_HOST"],
        openai_api_key=os.environ["NILLION_NILAI_KEY"],
        model_name=_probe_model_name(os.environ["NILLION_NILAI_REASONING_HOST"])
    )

    llm_tools = ChatOpenAI(
        openai_api_base=os.environ["NILLION_NILAI_TOOLS_HOST"],
        openai_api_key=os.environ["NILLION_NILAI_KEY"],
        model_name=_probe_model_name(os.environ["NILLION_NILAI_TOOLS_HOST"])
    )

    wallet_data = None

    if os.path.exists(wallet_data_file):
        with open(wallet_data_file) as f:
            wallet_data = f.read()

    # Configure CDP Agentkit Langchain Extension.
    values = {}
    if wallet_data is not None:
        # If there is a persisted agentic wallet, load it and pass to the CDP Agentkit Wrapper.
        values = {"cdp_wallet_data": wallet_data}

    agentkit = CdpAgentkitWrapper(**values)

    # persist the agent's CDP MPC Wallet Data.
    wallet_data = agentkit.export_wallet()
    with open(wallet_data_file, "w") as f:
        f.write(wallet_data)

    # Initialize CDP Agentkit Toolkit and get tools.
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    tools = [x for x in cdp_toolkit.get_tools() if x.name.startswith("nillion")]

    # Store buffered conversation history in memory.
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP Agentkit Chatbot Example!"}}

    # Create ReAct Agent using the LLM and CDP Agentkit tools.
    return (
        create_react_agent(llm_tools, tools=tools, checkpointer=memory, debug=True),
        llm_reasoning,
        config,
    )


# Autonomous Mode
def run_autonomous_mode(agent_executor, config, task: str):
    """Run the agent autonomously."""
    print("Starting autonomous mode...")

    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=task)]}, config
    ):
        if "agent" in chunk:
            print("AGENT RESPONSE")
            print(chunk["agent"]["messages"][0].content)
        elif "tools" in chunk:
            print("TOOLS RESPONSE")
            print(chunk["tools"]["messages"][0].content)
        else:
            print("OTHER RESPONSE")
            print(chunk)
        print("-------------------")


def main(case_file_path: str) -> bool:
    """Start the chatbot agent."""
    try:
        with open(case_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File {case_file_path} not found")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file: {e}")

    REASONING_TASK = f"""
    Your name is Doctor Feelgood. You're the one that makes you feel, alright.
    You are a helpful human physician with an expertise in Internal Medicine.
    You have been asked to help diagnose a patient. Here are all the case
    details.

    INTAKE:
    {json.dumps(data['INTAKE'])}

    CHART:
    {json.dumps(data['CHART'])}

    Form an opinion and suggest a diagnosis. Describe your reasoning in detail.
    """

    agent_executor, llm_reasoning, config = initialize_agent()
    res = llm_reasoning.invoke(REASONING_TASK)

    TOOLS_TASK = f"""
    You are a doctor and you have formed an opinion and suggested a diagnosis. 
    This is your reasoning report. Your report is found below.

    You must save your opinion into existing schema that is in the SecretVault. 
    First, you should lookup the schema to use, and then transform your findings 
    to match the available fields in the schema. If you do not find an existing 
    schema, do not create one, just stop. Tell me your thoughts afterwards.

    YOUR DIAGNOSIS IS:
    {res.content}
    """
    print("Agent is informed of task.")
    run_autonomous_mode(agent_executor=agent_executor, config=config, task=TOOLS_TASK)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze input file and write case report to Nillion SecretVault"
    )
    parser.add_argument("case_file_path", type=str, help="Path to case file")
    args = parser.parse_args()
    print(f"The doctor is IN [{args.case_file_path}]...")
    main(args.case_file_path)
