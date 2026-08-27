"""Fix NO-side sign-convention bugs in momentum strategies.

For YES tokens: price velocity / pressure should have the same sign as delta.
For NO tokens: price velocity / pressure should have the OPPOSITE sign of delta
(because the NO token rises when spot falls).

The buggy pattern was:
    if np.sign(X) != np.sign(d): continue
which is correct for YES but rejects valid NO entries.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
FILES = [
    "strategies/s31_aligned_mode.py",
    "strategies/s32_momentum_mode.py",
    "strategies/s39_cross_window_momentum.py",
    "strategies/s52_liquidity_momentum.py",
    "strategies/s55_rapid_probability_change_chase.py",
    "strategies/s66_seven_trigger_exit_stack.py",
    "strategies/s69_complementary_exit_discipline.py",
]


def expected_sign_expr(side_var: str = "side") -> str:
    return f"(np.sign(d) if {side_var} == 'YES' else -np.sign(d))"


def fix_file(path: Path):
    text = path.read_text()
    original = text
    # Replace standalone sign checks:  if np.sign(X) != np.sign(d):
    # with:                            if np.sign(X) != (np.sign(d) if side == "YES" else -np.sign(d)):
    pattern = re.compile(
        r"if\s+np\.sign\(([^)]+)\)\s*!=\s*np\.sign\(d\)\s*:\s*\n\s*continue"
    )

    def repl(m):
        var = m.group(1)
        return f'if np.sign({var}) != {expected_sign_expr()}:\n                continue'

    text = pattern.sub(repl, text)

    # Replace combined sign check in s32:  or np.sign(vel) != np.sign(d)
    text = re.sub(
        r"np\.sign\(vel\)\s*!=\s*np\.sign\(d\)",
        f"np.sign(vel) != {expected_sign_expr()}",
        text,
    )

    # Replace combined sign check in s39:  if np.sign(short_vel) != np.sign(d):
    text = re.sub(
        r"if\s+np\.sign\(short_vel\)\s*!=\s*np\.sign\(d\)\s*:",
        f"if np.sign(short_vel) != {expected_sign_expr()}:",
        text,
    )

    if text != original:
        path.write_text(text)
        print(f"fixed {path}")
    else:
        print(f"no change {path}")


if __name__ == "__main__":
    for rel in FILES:
        fix_file(REPO / rel)
