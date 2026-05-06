"""x402 payment gate wiring for the FastAPI app.

Builds the middleware that protects POST /verify with a per-request USDC
charge on Base (Sepolia for testnet, mainnet by env override). Verification
and settlement are delegated to the public Coinbase facilitator at
https://x402.org/facilitator — no API keys required for testnet.
"""
from __future__ import annotations

from x402 import x402ResourceServer
from x402.http import HTTPFacilitatorClient
from x402.http.facilitator_client import FacilitatorConfig
from x402.http.middleware.fastapi import payment_middleware
from x402.http.types import PaymentOption, RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from config.settings import (
    get_x402_facilitator_url,
    get_x402_network,
    get_x402_pay_to,
    get_x402_price,
)


def build_payment_middleware():
    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=get_x402_facilitator_url()))
    server = x402ResourceServer(facilitator)
    network = get_x402_network()
    server.register(network, ExactEvmServerScheme())

    routes = {
        "POST /verify": RouteConfig(
            accepts=PaymentOption(
                scheme="exact",
                pay_to=get_x402_pay_to(),
                price=get_x402_price(),
                network=network,
            ),
            description="TRAC3R dataset verification",
        ),
    }
    return payment_middleware(routes, server)
