"""Clean and tampered demo datasets for TRAC3R.

Mirrors demo-data/clean_dataset.csv and demo-data/tampered_dataset.csv as
Python lists of dicts shaped to backend/models/request.py (timestamp, source,
value). Imported by agent_demo.py and the Postman collection generator.
"""
from __future__ import annotations


clean_dataset: list[dict] = [
    {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
    {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1215},
    {"timestamp": "2026-04-29T19:02:00Z", "source": "node1", "value": 1198},
    {"timestamp": "2026-04-29T19:03:00Z", "source": "node2", "value": 1207},
    {"timestamp": "2026-04-29T19:04:00Z", "source": "node1", "value": 1221},
    {"timestamp": "2026-04-29T19:05:00Z", "source": "node2", "value": 1212},
    {"timestamp": "2026-04-29T19:06:00Z", "source": "node1", "value": 1195},
    {"timestamp": "2026-04-29T19:07:00Z", "source": "node2", "value": 1209},
    {"timestamp": "2026-04-29T19:08:00Z", "source": "node1", "value": 1228},
    {"timestamp": "2026-04-29T19:09:00Z", "source": "node2", "value": 1219},
    {"timestamp": "2026-04-29T19:10:00Z", "source": "node1", "value": 1204},
    {"timestamp": "2026-04-29T19:11:00Z", "source": "node2", "value": 1216},
    {"timestamp": "2026-04-29T19:12:00Z", "source": "node1", "value": 1230},
    {"timestamp": "2026-04-29T19:13:00Z", "source": "node2", "value": 1224},
    {"timestamp": "2026-04-29T19:14:00Z", "source": "node1", "value": 1210},
    {"timestamp": "2026-04-29T19:15:00Z", "source": "node2", "value": 1199},
    {"timestamp": "2026-04-29T19:16:00Z", "source": "node1", "value": 1208},
    {"timestamp": "2026-04-29T19:17:00Z", "source": "node2", "value": 1220},
    {"timestamp": "2026-04-29T19:18:00Z", "source": "node1", "value": 1232},
    {"timestamp": "2026-04-29T19:19:00Z", "source": "node2", "value": 1217},
    {"timestamp": "2026-04-29T19:20:00Z", "source": "node1", "value": 1206},
    {"timestamp": "2026-04-29T19:21:00Z", "source": "node2", "value": 1197},
    {"timestamp": "2026-04-29T19:22:00Z", "source": "node1", "value": 1213},
    {"timestamp": "2026-04-29T19:23:00Z", "source": "node2", "value": 1226},
    {"timestamp": "2026-04-29T19:24:00Z", "source": "node1", "value": 1201},
]


tampered_dataset: list[dict] = [
    {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
    {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1215},
    {"timestamp": "2026-04-29T19:02:00Z", "source": "node1", "value": 1198},
    {"timestamp": "2026-04-29T19:03:00Z", "source": "node2", "value": 1207},
    {"timestamp": "2026-04-29T19:04:00Z", "source": "node1", "value": 1221},
    {"timestamp": "2026-04-29T19:05:00Z", "source": "node2", "value": 1212},
    {"timestamp": "2026-04-29T19:06:00Z", "source": "node1", "value": 1195},
    {"timestamp": "2026-04-29T19:06:00Z", "source": "node2", "value": 1209},
    {"timestamp": "2026-04-29T19:08:00Z", "source": "node1", "value": 1228},
    {"timestamp": "2026-04-29T19:09:00Z", "source": "node2", "value": 1219},
    {"timestamp": "2026-04-29T19:10:00Z", "source": "node1", "value": 1204},
    {"timestamp": "2026-04-29T19:11:00Z", "source": "node2", "value": 1216},
    {"timestamp": "2026-04-29T19:12:00Z", "source": "node1", "value": 1230},
    {"timestamp": "2026-04-29T19:13:00Z", "source": "node2", "value": 7200},
    {"timestamp": "2026-04-29T19:14:00Z", "source": "node1", "value": 1210},
    {"timestamp": "2026-04-29T19:15:00Z", "source": "node2", "value": 1199},
    {"timestamp": "2026-04-29T19:16:00Z", "source": "node1", "value": 1208},
    {"timestamp": "2026-04-29T19:17:00Z", "source": "node2", "value": 1220},
    {"timestamp": "2026-04-29T19:19:00Z", "source": "node2", "value": 1217},
    {"timestamp": "2026-04-29T19:20:00Z", "source": "node1", "value": 1206},
    {"timestamp": "2026-04-29T19:21:00Z", "source": "node2", "value": 1197},
    {"timestamp": "2026-04-29T19:04:00Z", "source": "node1", "value": 1221},
    {"timestamp": "2026-04-29T19:22:00Z", "source": "node1", "value": 1213},
    {"timestamp": "2026-04-29T19:23:00Z", "source": "node2", "value": 1226},
    {"timestamp": "2026-04-29T19:24:00Z", "source": "node1", "value": 1201},
]
