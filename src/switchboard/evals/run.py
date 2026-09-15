"""Run the eval suite against is_low_quality and print a report.

Run: python -m switchboard.evals.run
"""

from switchboard.evals.dataset import CASES
from switchboard.evals.runner import run_eval
from switchboard.routing.quality import is_low_quality


def main() -> None:
    result = run_eval(CASES, is_low_quality)

    print(f"Eval cases: {result.total}")
    print(f"Accuracy: {result.correct}/{result.total} = {result.accuracy:.1%}")
    print()
    print(f"False positive rate (needlessly escalated): {result.false_positive_rate:.1%}")
    for name in result.false_positives:
        print(f"  - {name}")
    print()
    print(f"False negative rate (bad answer passed as fine): {result.false_negative_rate:.1%}")
    for name in result.false_negatives:
        print(f"  - {name}")


if __name__ == "__main__":
    main()