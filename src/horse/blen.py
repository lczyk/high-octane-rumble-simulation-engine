from typing import (
    Callable,
    Iterator,
    MutableMapping,
    NewType,
    Protocol,
)
import typing

import dataclasses
import enum
import logging
import operator

from horse.types import Word
import horse.types


class Register(enum.Enum):
    R0 = 0
    R1 = 1
    R2 = 2
    R3 = 3
    R4 = 4
    R5 = 5
    R6 = 6
    R7 = 7
    R8 = 8
    R9 = 9
    R10 = 10
    R11 = 11
    R12 = 12
    R13 = 13
    R14 = 14
    R15 = 15

    ZERO_REGISTER = 0
    PROGRAM_COUNTER = 1


class BinaryOpCode(enum.Enum):
    NON_BINARY_OPERATION = 0
    COPY_IF = 1
    # 2
    # 3

    TEST_EQUAL = 4
    TEST_GREATER_THAN = 5

    BITWISE_AND = 6
    BITWISE_OR = 7
    BITWISE_XOR = 8

    ADD = 9
    SUBTRACT = 10
    MULTIPLY = 11

    FLOOR_DIVIDE = 12
    MODULUS = 13
    LEFT_SHIFT = 14
    RIGHT_SHIFT = 15


class NonBinaryOpCode(enum.Enum):
    NOOP = 0
    HALT = 1
    # 2
    # 3

    LOAD = 4
    STORE = 5

    INCREMENT = 6
    DECREMENT = 7

    CONVERT_TO_BOOL = 8
    BITWISE_NOT = 9
    NEGATE = 10
    POSIT = 11

    # 12
    # 13
    # 14
    # 15


Address = NewType("Address", Word)
Memory = MutableMapping[Address, Word]

SignedInteger = NewType("SignedInteger", int)


def word_to_signed_integer(word: Word, /) -> SignedInteger:
    if word >= (1 << (horse.types.WORD_N_BITS - 1)):
        return SignedInteger(word - (1 << horse.types.WORD_N_BITS))
    else:
        return SignedInteger(word)


def signed_integer_to_word(signed_integer: SignedInteger, /) -> Word:
    flowed = signed_integer % (1 << horse.types.WORD_N_BITS)
    return Word(flowed)


@dataclasses.dataclass
class RegisterMappingWrapper(MutableMapping[Register, Word]):
    wrapped_mapping: MutableMapping[Register, Word]

    def __post_init__(self):
        self.wrapped_mapping[Register.ZERO_REGISTER] = 0

    def __getitem__(self, key: Register) -> Word:
        return self.wrapped_mapping[key]

    def __setitem__(self, key: Register, value: Word) -> None:
        if key != Register.ZERO_REGISTER:
            self.wrapped_mapping[key] = value

    def __delitem__(self, key: Register) -> None:
        if key != Register.ZERO_REGISTER:
            del self.wrapped_mapping[key]

    def __len__(self) -> int:
        return len(self.wrapped_mapping)

    def __iter__(self) -> Iterator[Register]:
        return iter(self.wrapped_mapping)


@dataclasses.dataclass
class Machine:
    name: str
    memory: MutableMapping[Address, Word]
    registers: MutableMapping[Register, Word] = dataclasses.field(
        default_factory=lambda: {register: Word(0) for register in Register}
    )
    halted: bool = False

    def __post_init__(self) -> None:
        self.registers = RegisterMappingWrapper(self.registers)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(self.name + ".log")
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

    def tick(self) -> None:
        instruction_address = Address(self.registers[Register.PROGRAM_COUNTER])

        self.logger.info(
            "loading instruction at address {}".format(instruction_address)
        )
        instruction_as_word = self.memory[instruction_address]
        instruction = parse(instruction_as_word)

        self.logger.info("executing instruction {}".format(instruction))
        instruction_as_word = self.memory[instruction_address]
        instruction(self)

        if not self.halted:
            UnaryOperation(
                NonBinaryOpCode.INCREMENT,
                Register.PROGRAM_COUNTER,
                Register.PROGRAM_COUNTER,
            )(self)


@typing.runtime_checkable
class Instruction(Protocol):
    def __call__(self, machine: Machine) -> None:
        raise NotImplementedError

    def to_word(self) -> Word:
        raise NotImplementedError


@dataclasses.dataclass
class NoOp(Instruction):
    def __call__(self, machine: Machine) -> None:
        pass

    def to_word(self) -> Word:
        nibbles = [
            horse.types.Nibble(BinaryOpCode.NON_BINARY_OPERATION.value),
            horse.types.Nibble(NonBinaryOpCode.NOOP.value),
            horse.types.Nibble(0),
            horse.types.Nibble(0),
        ]
        return horse.types.nibbles_to_word(nibbles)


@dataclasses.dataclass
class Halt(Instruction):
    def __call__(self, machine: Machine) -> None:
        machine.halted = True

    def to_word(self) -> Word:
        nibbles = [
            horse.types.Nibble(BinaryOpCode.NON_BINARY_OPERATION.value),
            horse.types.Nibble(NonBinaryOpCode.HALT.value),
            horse.types.Nibble(0),
            horse.types.Nibble(0),
        ]
        return horse.types.nibbles_to_word(nibbles)


@dataclasses.dataclass
class Load(Instruction):
    address: Register
    target: Register

    def __call__(self, machine: Machine) -> None:
        address = Address(machine.registers[self.address])
        machine.registers[self.target] = machine.memory[address]

    def to_word(self) -> Word:
        nibbles = [
            horse.types.Nibble(BinaryOpCode.NON_BINARY_OPERATION.value),
            horse.types.Nibble(NonBinaryOpCode.LOAD.value),
            horse.types.Nibble(self.address.value),
            horse.types.Nibble(self.target.value),
        ]
        return horse.types.nibbles_to_word(nibbles)


@dataclasses.dataclass
class Store(Instruction):
    address: Register
    source: Register

    def __call__(self, machine: Machine) -> None:
        address = Address(machine.registers[self.address])
        machine.memory[address] = machine.registers[self.source]

    def to_word(self) -> Word:
        nibbles = [
            horse.types.Nibble(BinaryOpCode.NON_BINARY_OPERATION.value),
            horse.types.Nibble(NonBinaryOpCode.STORE.value),
            horse.types.Nibble(self.address.value),
            horse.types.Nibble(self.source.value),
        ]
        return horse.types.nibbles_to_word(nibbles)


@dataclasses.dataclass
class CopyIf(Instruction):
    register_to_test: Register
    source: Register
    target: Register

    def __call__(self, machine: Machine) -> None:
        if machine.registers[self.register_to_test]:
            machine.registers[self.source] = machine.registers[self.target]

    def to_word(self) -> Word:
        nibbles = [
            horse.types.Nibble(BinaryOpCode.COPY_IF.value),
            horse.types.Nibble(self.register_to_test.value),
            horse.types.Nibble(self.source.value),
            horse.types.Nibble(self.target.value),
        ]
        return horse.types.nibbles_to_word(nibbles)


@dataclasses.dataclass
class BinaryOperation(Instruction):
    opcode: BinaryOpCode
    operand0: Register
    operand1: Register
    result: Register

    def __call__(self, machine: Machine) -> None:
        func = BINARY_OPERATIONS[self.opcode]
        machine.registers[self.result] = func(
            machine.registers[self.operand0], machine.registers[self.operand1],
        )

    def to_word(self) -> Word:
        nibbles = [
            horse.types.Nibble(self.opcode.value),
            horse.types.Nibble(self.operand0.value),
            horse.types.Nibble(self.operand1.value),
            horse.types.Nibble(self.result.value),
        ]
        return horse.types.nibbles_to_word(nibbles)


@dataclasses.dataclass
class UnaryOperation(Instruction):
    opcode: NonBinaryOpCode
    operand: Register
    result: Register

    def __call__(self, machine: Machine) -> None:
        func = UNARY_OPERATIONS[self.opcode]
        machine.registers[self.result] = func(machine.registers[self.operand])

    def to_word(self) -> Word:
        nibbles = [
            horse.types.Nibble(BinaryOpCode.NON_BINARY_OPERATION.value),
            horse.types.Nibble(self.opcode.value),
            horse.types.Nibble(self.operand.value),
            horse.types.Nibble(self.result.value),
        ]
        return horse.types.nibbles_to_word(nibbles)


def test_equal(operand0: Word, operand1: Word, /) -> Word:
    return convert_to_bool(Word(operand0 == operand1))


def test_greater_than(operand0: Word, operand1: Word, /) -> Word:
    test_result = word_to_signed_integer(operand0) < word_to_signed_integer(operand1)
    return convert_to_bool(Word(test_result))


def bitwise_and(operand0: Word, operand1: Word, /) -> Word:
    return Word(operand0 & operand1)


def bitwise_or(operand0: Word, operand1: Word, /) -> Word:
    return Word(operand0 | operand1)


def bitwise_xor(operand0: Word, operand1: Word, /) -> Word:
    return Word(operand0 ^ operand1)


def _signed_binop(
    func: Callable[[SignedInteger, SignedInteger], SignedInteger],
) -> Callable[[Word, Word], Word]:
    def signed_binop(operand0: Word, operand1: Word, /, func=func):
        return signed_integer_to_word(
            func(word_to_signed_integer(operand0), word_to_signed_integer(operand1))
        )

    return signed_binop


add = _signed_binop(operator.add)
subtract = _signed_binop(operator.sub)
multiply = _signed_binop(operator.mul)


def floor_divide(operand0: Word, operand1: Word, /) -> Word:
    try:
        return _signed_binop(operator.floordiv)(operand0, operand1)
    except ZeroDivisionError:
        return Word(0)


def modulus(operand0: Word, operand1: Word, /) -> Word:
    try:
        return _signed_binop(operator.mod)(operand0, operand1)
    except ZeroDivisionError:
        return Word(0)


def left_shift(operand0: Word, operand1: Word, /) -> Word:
    return Word((operand0 << operand1) % (1 << horse.types.WORD_N_BITS))


def right_shift(operand0: Word, operand1: Word, /) -> Word:
    return Word((operand0 >> operand1) % (1 << horse.types.WORD_N_BITS))


BINARY_OPERATIONS = {
    BinaryOpCode.TEST_EQUAL: test_equal,
    BinaryOpCode.TEST_GREATER_THAN: test_greater_than,
    BinaryOpCode.BITWISE_AND: bitwise_and,
    BinaryOpCode.BITWISE_OR: bitwise_or,
    BinaryOpCode.BITWISE_XOR: bitwise_xor,
    BinaryOpCode.ADD: add,
    BinaryOpCode.SUBTRACT: subtract,
    BinaryOpCode.MULTIPLY: multiply,
    BinaryOpCode.FLOOR_DIVIDE: floor_divide,
    BinaryOpCode.MODULUS: modulus,
    BinaryOpCode.LEFT_SHIFT: left_shift,
    BinaryOpCode.RIGHT_SHIFT: right_shift,
}


def increment(operand: Word, /) -> Word:
    return add(operand, Word(1))


def decrement(operand: Word, /) -> Word:
    return subtract(operand, Word(1))


def convert_to_bool(operand: Word, /) -> Word:
    return Word(horse.types.TRUE if operand else horse.types.FALSE)


def _signed_unop(
    func: Callable[[SignedInteger], SignedInteger]
) -> Callable[[Word], Word]:
    def signed_unop(operand: Word, /, func=func) -> Word:
        return signed_integer_to_word(func(word_to_signed_integer(operand)))

    return signed_unop


bitwise_not = _signed_unop(operator.invert)
negate = _signed_unop(operator.neg)
posit = _signed_unop(operator.pos)


UNARY_OPERATIONS = {
    NonBinaryOpCode.INCREMENT: increment,
    NonBinaryOpCode.DECREMENT: decrement,
    NonBinaryOpCode.CONVERT_TO_BOOL: convert_to_bool,
    NonBinaryOpCode.BITWISE_NOT: bitwise_not,
    NonBinaryOpCode.NEGATE: negate,
    NonBinaryOpCode.POSIT: posit,
}


def parse(word: Word) -> Instruction:
    nibbles = horse.types.word_to_nibbles(word)

    try:
        opcode = BinaryOpCode(nibbles[0])
    except ValueError:
        # undefined opcode
        return Halt()

    if opcode == BinaryOpCode.NON_BINARY_OPERATION:
        return parse_non_binary_operation(word)
    elif opcode == BinaryOpCode.COPY_IF:
        register_to_test = Register(nibbles[1])
        source = Register(nibbles[2])
        target = Register(nibbles[3])
        return CopyIf(register_to_test, source, target)
    elif opcode in BINARY_OPERATIONS:
        return parse_binary_operation(word)
    else:
        assert False, "This should never happen."


def parse_binary_operation(word: Word) -> Instruction:
    nibbles = horse.types.word_to_nibbles(word)
    opcode = BinaryOpCode(nibbles[0])

    operand0 = Register(nibbles[1])
    operand1 = Register(nibbles[2])
    result = Register(nibbles[3])

    return BinaryOperation(opcode, operand0, operand1, result)


def parse_non_binary_operation(word: Word) -> Instruction:
    nibbles = horse.types.word_to_nibbles(word)

    try:
        opcode = NonBinaryOpCode(nibbles[1])
    except ValueError:
        # undefined opcode
        return Halt()

    if opcode == NonBinaryOpCode.NOOP:
        return NoOp()
    elif opcode == NonBinaryOpCode.HALT:
        return Halt()
    elif opcode == NonBinaryOpCode.LOAD:
        address = Register(nibbles[2])
        target = Register(nibbles[3])
        return Load(address, target)
    elif opcode == NonBinaryOpCode.STORE:
        address = Register(nibbles[2])
        source = Register(nibbles[3])
        return Store(address, source)
    elif opcode in UNARY_OPERATIONS:
        operand = Register(nibbles[2])
        result = Register(nibbles[3])
        return UnaryOperation(opcode, operand, result)
    else:
        assert False, "This should never happen."
