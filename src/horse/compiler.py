from typing import Any, Callable, Dict, Generic, Sequence, TypeVar

import argparse
import dataclasses
import functools
import re
import struct
import sys

from horse.types import Word
import horse.blen


@dataclasses.dataclass
class ParserState:
    lines: Sequence[str]
    line: int
    char: int

    @property
    def remaining(self) -> str:
        return self.lines[self.line][self.char :]


T = TypeVar("T", covariant=True)


@dataclasses.dataclass
class ParseResult(Generic[T]):
    result: T
    new_state: ParserState


class ParseError(ValueError):
    def __init__(self, state: ParserState, message):
        max_line = len(str(len(state.lines) + 1))
        max_char = len(str(max(len(line) for line in state.lines) + 1))
        msg = "\n".join(
            [
                state.lines[state.line].strip(),
                " " * state.char + "^",
                f"line {state.line + 1:0{max_line}d}, char {state.char + 1:0{max_char}d}: {message}",
            ]
        )
        super().__init__(msg)


REGISTER_RE = re.compile(r"(R\d+|ZERO_REGISTER|PROGRAM_COUNTER)")
WHITESPACE_RE = re.compile(r"\s+")
INTEGER_RE = re.compile(r"-?\d+")


def parse_whitespace(current_state: ParserState) -> ParseResult[str]:
    match = WHITESPACE_RE.match(current_state.remaining)
    if match is not None:
        parsed = match.group(0)
        new_state = dataclasses.replace(
            current_state, char=current_state.char + len(parsed)
        )
        return ParseResult(parsed, new_state)
    else:
        raise ParseError(current_state, "expected whitespace")


def maybe_parse_whitespace(current_state: ParserState) -> ParseResult[str]:
    try:
        return parse_whitespace(current_state)
    except ParseError:
        return ParseResult("", current_state)


def parse_keyword(keyword: str, current_state: ParserState) -> ParseResult[str]:
    if current_state.remaining.startswith(keyword):
        parsed = keyword
        new_state = dataclasses.replace(
            current_state, char=current_state.char + len(parsed)
        )
        return ParseResult(parsed, new_state)
    else:
        raise ParseError(current_state, f"expected keyword {keyword}")


def parse_integer(current_state: ParserState) -> ParseResult[int]:
    match = INTEGER_RE.match(current_state.remaining)
    if match is not None:
        parsed = match.group(0)
        new_state = dataclasses.replace(
            current_state, char=current_state.char + len(parsed)
        )
        return ParseResult(int(parsed), new_state)
    else:
        raise ParseError(current_state, "expected integer")


def parse_register(current_state: ParserState) -> ParseResult[horse.blen.Register]:
    match = REGISTER_RE.match(current_state.remaining)
    if match is not None:
        parsed = match.group(0)
        result = horse.blen.horse.blen.Register[parsed]
        new_state = dataclasses.replace(
            current_state, char=current_state.char + len(parsed)
        )
        return ParseResult(result, new_state)
    else:
        raise ParseError(current_state, "expected register")


def parse_comment(current_state: ParserState) -> ParseResult[str]:
    remaining_line = current_state.lines[current_state.line][current_state.char :]
    if remaining_line.startswith(";"):
        parsed = remaining_line
        new_state = dataclasses.replace(
            current_state, char=current_state.char + len(parsed)
        )
        return ParseResult(parsed, new_state)
    else:
        raise ParseError(current_state, "expected comment")


def maybe_parse_comment(current_state: ParserState) -> ParseResult[str]:
    try:
        return parse_comment(current_state)
    except ParseError:
        return ParseResult("", current_state)


def parse_noop_args(current_state: ParserState) -> ParseResult[horse.blen.NoOp]:
    return ParseResult(horse.blen.NoOp(), current_state)


def parse_halt_args(current_state: ParserState) -> ParseResult[horse.blen.Halt]:
    return ParseResult(horse.blen.Halt(), current_state)


def parse_load_args(current_state: ParserState) -> ParseResult[horse.blen.Load]:
    _result: ParseResult[Any]

    _result = parse_whitespace(current_state)

    _result = parse_register(_result.new_state)
    address: horse.blen.Register = _result.result

    _result = parse_whitespace(_result.new_state)

    _result = parse_register(_result.new_state)
    target: horse.blen.Register = _result.result

    return ParseResult(horse.blen.Load(address, target), _result.new_state)


def parse_store_args(current_state: ParserState) -> ParseResult[horse.blen.Store]:
    _result: ParseResult[Any]

    _result = parse_whitespace(current_state)

    _result = parse_register(_result.new_state)
    address: horse.blen.Register = _result.result

    _result = parse_whitespace(_result.new_state)

    _result = parse_register(_result.new_state)
    source: horse.blen.Register = _result.result

    return ParseResult(horse.blen.Store(address, source), _result.new_state)


def parse_copy_if_args(current_state: ParserState) -> ParseResult[horse.blen.CopyIf]:
    _result: ParseResult[Any]

    _result = parse_whitespace(current_state)

    _result = parse_register(_result.new_state)
    register_to_test: horse.blen.Register = _result.result

    _result = parse_whitespace(_result.new_state)

    _result = parse_register(_result.new_state)
    source: horse.blen.Register = _result.result

    _result = parse_whitespace(_result.new_state)

    _result = parse_register(_result.new_state)
    target: horse.blen.Register = _result.result

    return ParseResult(
        horse.blen.CopyIf(register_to_test, source, target), _result.new_state
    )


def parse_binary_operation_args(
    current_state: ParserState, opcode: horse.blen.BinaryOpCode
) -> ParseResult[horse.blen.BinaryOperation]:
    _result: ParseResult[Any]

    _result = parse_whitespace(current_state)

    _result = parse_register(_result.new_state)
    operand0: horse.blen.Register = _result.result

    _result = parse_whitespace(_result.new_state)

    _result = parse_register(_result.new_state)
    operand1: horse.blen.Register = _result.result

    _result = parse_whitespace(_result.new_state)

    _result = parse_register(_result.new_state)
    result: horse.blen.Register = _result.result

    return ParseResult(
        horse.blen.BinaryOperation(opcode, operand0, operand1, result),
        _result.new_state,
    )


def parse_unary_operation_args(
    current_state: ParserState, opcode: horse.blen.NonBinaryOpCode
) -> ParseResult[horse.blen.UnaryOperation]:
    _result: ParseResult[Any]

    _result = parse_whitespace(current_state)

    _result = parse_register(_result.new_state)
    operand: horse.blen.Register = _result.result

    _result = parse_whitespace(_result.new_state)

    _result = parse_register(_result.new_state)
    result: horse.blen.Register = _result.result

    return ParseResult(
        horse.blen.UnaryOperation(opcode, operand, result), _result.new_state,
    )


INSTRUCTIONS: Dict[
    str, Callable[[ParserState], ParseResult[horse.blen.Instruction]]
] = {
    "copy_if": parse_copy_if_args,
    "test_equal": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.TEST_EQUAL
    ),
    "test_greater_than": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.TEST_GREATER_THAN
    ),
    "bitwise_and": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.BITWISE_AND
    ),
    "bitwise_or": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.BITWISE_OR
    ),
    "bitwise_xor": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.BITWISE_XOR
    ),
    "add": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.ADD
    ),
    "subtract": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.SUBTRACT
    ),
    "multiply": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.MULTIPLY
    ),
    "floor_divide": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.FLOOR_DIVIDE
    ),
    "modulus": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.MODULUS
    ),
    "left_shift": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.LEFT_SHIFT
    ),
    "right_shift": functools.partial(
        parse_binary_operation_args, opcode=horse.blen.BinaryOpCode.RIGHT_SHIFT
    ),
    "no_op": parse_noop_args,
    "halt": parse_halt_args,
    "load": parse_load_args,
    "store": parse_store_args,
    "increment": functools.partial(
        parse_unary_operation_args, opcode=horse.blen.NonBinaryOpCode.INCREMENT,
    ),
    "decrement": functools.partial(
        parse_unary_operation_args, opcode=horse.blen.NonBinaryOpCode.DECREMENT,
    ),
    "convert_to_bool": functools.partial(
        parse_unary_operation_args, opcode=horse.blen.NonBinaryOpCode.CONVERT_TO_BOOL,
    ),
    "bitwise_not": functools.partial(
        parse_unary_operation_args, opcode=horse.blen.NonBinaryOpCode.BITWISE_NOT,
    ),
    "negate": functools.partial(
        parse_unary_operation_args, opcode=horse.blen.NonBinaryOpCode.NEGATE,
    ),
    "posit": functools.partial(
        parse_unary_operation_args, opcode=horse.blen.NonBinaryOpCode.POSIT,
    ),
}


def parse_instruction(
    current_state: ParserState,
) -> ParseResult[horse.blen.Instruction]:
    _result: ParseResult[Any]

    for keyword in INSTRUCTIONS:
        try:
            _result = parse_keyword(keyword, current_state)
        except ParseError:
            continue
        else:
            break
    else:
        raise ParseError(current_state, "expected keyword")

    return INSTRUCTIONS[keyword](_result.new_state)


def compile(lines: Sequence[str]) -> Sequence[Word]:
    state = ParserState(lines, 0, 0)
    compiled = []

    _result: ParseResult[Any]

    while state.line < len(state.lines):
        try:
            instruction_result = parse_instruction(state)
            compiled_line = instruction_result.result.to_word()
        except ParseError as e:
            try:
                _result = parse_keyword("constant", state)
                _result = parse_whitespace(_result.new_state)
                constant_result = parse_integer(_result.new_state)
                compiled_line = Word(constant_result.result)
            except ParseError:
                try:
                    _result = maybe_parse_whitespace(state)
                    _result = maybe_parse_comment(_result.new_state)
                    if _result.new_state.remaining:
                        raise ParseError(
                            state, "expected instruction or comment or blank line"
                        )
                    state = dataclasses.replace(state, line=state.line + 1, char=0)
                    continue
                except ParseError:
                    raise e

        _result = maybe_parse_whitespace(instruction_result.new_state)
        _result = maybe_parse_comment(_result.new_state)
        if _result.new_state.remaining.strip():
            raise ParseError(
                instruction_result.new_state, "expected comment or end of line"
            )

        compiled.append(compiled_line)
        state = dataclasses.replace(state, line=state.line + 1, char=0)

    return compiled


def main(arguments=None):
    parser = argparse.ArgumentParser(description="Compiler for the blen language.")
    parser.add_argument("-i", "--input", metavar="FILE", help="Input file.")
    parser.add_argument("-o", "--output", metavar="FILE", help="Ouptut file.")

    args = parser.parse_args(arguments)

    with open(args.input, "r") as f:
        lines = f.readlines()

    try:
        compiled = compile(lines)
    except ParseError as e:
        print(str(e))
        return 1

    with open(args.output, "wb") as f:
        f.write(struct.pack(">{}H".format(len(compiled)), *compiled))

    return 0


if __name__ == "__main__":
    sys.exit(main())
