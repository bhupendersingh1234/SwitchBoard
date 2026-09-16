"""Query accumulated cascade_decisions and write them as OpenAI fine-tuning
JSONL, ready to upload via the fine-tuning API or dashboard.

Run: python -m switchboard.routing.export_cli --output training_data.jsonl
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from switchboard.db.models import CascadeDecision
from switchboard.db.session import build_sessionmaker
from switchboard.routing.finetune_export import CascadeRecord, export_training_examples


async def export_to_file(engine: AsyncEngine, output_path: str) -> tuple[int, int]:
    sessionmaker = build_sessionmaker(engine)

    async with sessionmaker() as session:
        result = await session.execute(select(CascadeDecision))
        rows = result.scalars().all()

    records = [
        CascadeRecord(
            messages=row.messages,
            response_content=row.response_content,
            was_low_quality=row.was_low_quality,
        )
        for row in rows
    ]
    lines = export_training_examples(records)

    def _write() -> None:
        with open(output_path, "w") as f:
            for line in lines:
                f.write(line + "\n")

    await asyncio.to_thread(_write)

    return len(rows), len(lines)


async def main() -> None:
    from switchboard.core.config import get_settings
    from switchboard.db.session import build_engine

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="cascade_training_data.jsonl")
    args = parser.parse_args()

    settings = get_settings()
    engine = build_engine(settings.database_url)
    try:
        total_decisions, exported = await export_to_file(engine, args.output)
        print(f"Recorded decisions: {total_decisions}")
        print(f"Training examples exported (low-quality filtered out): {exported}")
        print(f"Written to: {args.output}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())