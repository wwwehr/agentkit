from cdp_agentkit_core.actions.nillion.constants import (
    CONFIG,
)
from ecdsa import SigningKey, SECP256k1
import jwt
import nilql
import requests
import time


def init() -> bool:
    """Initialize config with JWTs signed with ES256K for multiple node_ids; Add cluster key."""
    response = requests.post(
        "https://sv-sda-registration.replit.app/api/config",
        headers={
            "Content-Type": "application/json",
        },
        json={"org_did": CONFIG["org_did"]},
    )
    nodes = response.json()["nodes"]

    # Convert the secret key from hex to bytes
    private_key = bytes.fromhex(CONFIG["secret_key"])
    signer = SigningKey.from_string(private_key, curve=SECP256k1)

    for node in nodes:
        # Create payload for each node_id
        payload = {
            "iss": CONFIG["org_did"],
            "aud": node["did"],
            "exp": int(time.time()) + 3600,
        }

        # Create and sign the JWT
        node["bearer"] = jwt.encode(payload, signer.to_pem(), algorithm="ES256K")

    CONFIG["nodes"] = nodes
    CONFIG["cluster_key"] = nilql.ClusterKey.generate(
        {"nodes": [{}] * len(nodes)}, {"store": True}
    )

    return True
