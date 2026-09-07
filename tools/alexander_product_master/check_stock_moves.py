# ruff: noqa
import json
from datetime import datetime, timedelta

Move = env["stock.move"].sudo() if "stock.move" in env else None
if Move is None:
    print(json.dumps({"stock_move_model": False}))
else:
    recent = Move.search([("create_date", ">=", "2026-09-07 22:00:00")], limit=20)
    today_count = Move.search_count([("create_date", ">=", "2026-09-07 22:00:00")])
    print(
        json.dumps(
            {
                "recent_count_since_22utc": today_count,
                "sample": [
                    {
                        "id": m.id,
                        "product": m.product_id.display_name,
                        "date": str(m.create_date),
                        "uid": m.create_uid.id,
                        "origin": m.origin,
                        "state": m.state,
                    }
                    for m in recent
                ],
                "total_moves": Move.search_count([]),
            },
            default=str,
        )
    )
