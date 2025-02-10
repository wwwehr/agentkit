
from pdb import set_trace as bp
import argparse
import os
import json

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage
# from langchain_openai import ChatOpenAI
from langchain_community.llms import VLLMOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

# Import CDP Agentkit Langchain Extension.
from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper


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


# Configure a file to persist the agent's CDP MPC Wallet Data.
wallet_data_file = "wallet_data.txt"

load_dotenv()

"""
[
  {
    "id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    "name": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    "version": "1.0",
    "description": "",
    "author": "",
    "license": "Apache 2.0",
    "source": "https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    "supported_features": [
      "chat_completion"
    ],
    "tool_support": false
  },
  {
    "id": "meta-llama/Llama-3.1-8B-Instruct",
    "name": "meta-llama/Llama-3.1-8B-Instruct",
    "version": "1.0",
    "description": "",
    "author": "",
    "license": "Apache 2.0",
    "source": "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct",
    "supported_features": [
      "chat_completion"
    ],
    "tool_support": true
  },
  {
    "id": "meta-llama/Llama-3.2-3B-Instruct",
    "name": "meta-llama/Llama-3.2-3B-Instruct",
    "version": "1.0",
    "description": "",
    "author": "",
    "license": "Apache 2.0",
    "source": "https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct",
    "supported_features": [
      "chat_completion"
    ],
    "tool_support": true
  }
]
"""


def initialize_agent():
    """Initialize the agent with CDP Agentkit."""
    # Initialize LLM.
    """
    llm = ChatOpenAI(model="gpt-4o-mini")
    """

    llm = VLLMOpenAI(
        openai_api_base=os.environ["NILLION_NILAI_HOST"],
        openai_api_key=os.environ["NILLION_NILAI_KEY"],
        model_name="meta-llama/Llama-3.1-8B-Instruct",
        model_kwargs={"stop": ["."]},
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
        create_react_agent(
            llm,
            tools=tools,
            checkpointer=memory,
            state_modifier=(
                "You are a helpful agent that can interact onchain using the Coinbase Developer Platform AgentKit. "
                "You are empowered to interact onchain using your tools. If you ever need funds, you can request "
                "them from the faucet if you are on network ID 'base-sepolia'. If not, you can provide your wallet "
                "details and request funds from the user. Before executing your first action, get the wallet details "
                "to see what network you're on. If there is a 5XX (internal) HTTP error code, ask the user to try "
                "again later. If someone asks you to do something you can't do with your currently available tools, "
                "you must say so, and encourage them to implement it themselves using the CDP SDK + Agentkit, "
                "recommend they go to docs.cdp.coinbase.com for more information. Be concise and helpful with your "
                "responses. Refrain from restating your tools' descriptions unless it is explicitly requested."
            ),
        ),
        config,
    )


# Autonomous Mode
def run_autonomous_mode(agent_executor, config, task: str):
    """Run the agent autonomously."""
    print("Starting autonomous mode...")

    # Run agent in autonomous mode
    print(task)
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=task)]}, config
    ):
        if "agent" in chunk:
            print(chunk["agent"]["messages"][0].content)
        elif "tools" in chunk:
            print(chunk["tools"]["messages"][0].content)
        else:
            bp()
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

    TASK = f"""
    Your name is Doctor Feelgood. You're the one that makes you feel, alright.
    You are a helpful human physician with an expertise in Internal Medicine.
    You have been asked to help diagnose a patient. Here are all the case
    details.

    INTAKE:
    {json.dumps(data['INTAKE'])}

    CHART:
    {json.dumps(data['CHART'])}

    Form an opinion and suggest a diagnosis. Describe your reasoning in detail. Then
    save your opinion into existing schema that is in the SecretVault. You should
    transform your findings to match the available fields in the schema. If you do
    not find an existing schema, do not create one, just stop.
    """

    agent_executor, config = initialize_agent()
    print("Agent is informed of task.")
    run_autonomous_mode(agent_executor=agent_executor, config=config, task=TASK)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze input file and write case report to Nillion SecretVault"
    )
    parser.add_argument("case_file_path", type=str, help="Path to case file")
    args = parser.parse_args()
    print(f"The doctor is IN [{args.case_file_path}]...")
    main(args.case_file_path)
