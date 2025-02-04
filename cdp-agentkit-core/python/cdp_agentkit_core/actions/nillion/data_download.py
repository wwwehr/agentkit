from cdp import Wallet
from cdp_agentkit_core.actions import CdpAction
from pydantic import BaseModel, Field

from collections.abc import Callable

from collections import defaultdict

import requests

import nilql
from cdp_agentkit_core.actions.nillion.constants import CONFIG
from cdp_agentkit_core.actions.nillion.utils import init


NILLION_DATA_DOWNLOAD_PROMPT = """
This tool can download data from your privacy preserving database based on a schema UUID4. Do not use this tool for other purposes.

Inputs:
- a UUID4 that identifies the schema to be read from
"""


class NillionDataDownloadInput(BaseModel):
    """Input argument schema for data download action."""

    schema_uuid: str = Field(
        description="the UUID4 obtained from the nildb_schema_lookup_tool"
    )


def nillion_data_download(wallet: Wallet, schema_id: str) -> dict:
    """Download all records in the specified node and schema."""
    print(f"fn:data_download [{schema_id}]")
    try:
        init()
        shares = defaultdict(list)
        for node in CONFIG["nodes"]:
            headers = {
                "Authorization": f'Bearer {node["bearer"]}',
                "Content-Type": "application/json",
            }

            body = {
                "schema": schema_id,
                "filter": {},
            }

            response = requests.post(
                f"{node['url']}/api/v1/data/read",
                headers=headers,
                json=body,
            )
            assert (
                response.status_code == 200
            ), "upload failed: " + response.content.decode("utf8")
            data = response.json().get("data")
            for d in data:
                shares[d["_id"]].append(d)
        decrypted = []
        for k in shares:
            decrypted.append(nilql.unify(CONFIG["cluster_key"], shares[k]))
        return decrypted
    except Exception as e:
        print(f"Error retrieving records in node: {e!r}")
        return {}


class NillionDataDownloadAction(CdpAction):
    """Nillion Data Download Action."""

    name: str = "nillion_data_download"
    description: str = NILLION_DATA_DOWNLOAD_PROMPT
    args_schema: type[BaseModel] = NillionDataDownloadInput
    func: Callable[..., str] = nillion_data_download
