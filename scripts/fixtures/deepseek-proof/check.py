"""Frozen acceptance check; run only for the synthetic transport proof."""

from target import proof_value

if __name__ == "__main__":
    assert proof_value() == "after", "Synthetic replacement has not been applied"
