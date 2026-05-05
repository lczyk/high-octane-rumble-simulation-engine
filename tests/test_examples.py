from pathlib import Path

import pytest

import horse.compiler

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLES = sorted(EXAMPLES_DIR.glob("*.bln"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_compiles(path):
    lines = path.read_text().splitlines(keepends=True)
    compiled = horse.compiler.compile(lines)
    assert len(compiled) > 0
