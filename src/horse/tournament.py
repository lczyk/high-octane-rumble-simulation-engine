import argparse
import dataclasses
import logging
import os.path as op
import random
import struct
import sys
from collections.abc import Iterator, Mapping, MutableMapping, Sequence

import horse.blen
import horse.types
from horse.blen import Address
from horse.types import Word


@dataclasses.dataclass
class VirtualMemory(MutableMapping[Address, Word]):
    offset: int
    real_memory: MutableMapping[Address, Word]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(offset={self.offset}, real_memory=...)"

    def real_address(self, virtual_address: Address) -> Address:
        return Address(Word((virtual_address + self.offset) % (1 << horse.types.WORD_N_BITS)))

    def __getitem__(self, virtual_address: Address) -> Word:
        return self.real_memory[self.real_address(virtual_address)]

    def __setitem__(self, virtual_address: Address, value: Word) -> None:
        self.real_memory[self.real_address(virtual_address)] = value

    def __delitem__(self, virtual_address: Address) -> None:
        del self.real_memory[self.real_address(virtual_address)]

    def __len__(self) -> int:
        return len(self.real_memory)

    def __iter__(self) -> Iterator[Address]:
        return iter(self.real_memory)


def tournament(
    programs: Mapping[str, Sequence[Word]],
    seed: int,
    max_steps: int,
    *,
    log: bool = True,
) -> None:
    """Runs a tournament and determines the winner."""
    memory = {Address(Word(i)): Word(0) for i in range(1 << horse.types.WORD_N_BITS)}

    random.seed(seed)

    # copy programs into memory
    offsets: dict[str, int] = {}

    for program in programs:
        for _ in range(100000):
            offset = random.randrange(0, 1 << horse.types.WORD_N_BITS)

            if not any(offset <= other < offset + len(programs[program]) for other in offsets.values()):
                break
        else:
            raise RuntimeError("couldn't fit programs in memory")

        offsets[program] = offset

    for program in programs:
        for i, instruction in enumerate(programs[program]):
            memory[Address(Word(offsets[program] + i))] = instruction

    if not log:
        logging.getLogger("horse").setLevel(logging.CRITICAL)

    machines = [horse.blen.Machine(program, memory=VirtualMemory(offsets[program], memory)) for program in programs]

    # go!
    for _ in range(max_steps):
        if sum(not machine.halted for machine in machines) <= 1:
            break

        for machine in machines:
            machine.tick()

    winners = [machine for machine in machines if not machine.halted]

    if not winners:
        print("no one won")
    elif len(winners) == 1:
        print(winners[0].name, "won!")
    else:
        print(
            "It was a draw between the following:",
            ", ".join(machine.name for machine in machines),
        )


def read_program(filename: str) -> Sequence[Word]:
    with open(filename, "rb") as f:
        contents = f.read()

    return [Word(i) for (i,) in struct.iter_unpack(">H", contents)]


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a tournament")
    parser.add_argument("programs", metavar="FILE", nargs="+", help="The combatants.")
    parser.add_argument("--seed", type=int, metavar="INT", default=0, help="Random seed.")
    parser.add_argument(
        "--max-steps",
        type=int,
        metavar="INT",
        default=10_000,
        help="Maximum number of steps.",
    )
    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Disable logging of machine state.",
    )

    args = parser.parse_args(arguments)

    programs: dict[str, Sequence[Word]] = {}

    for filename in args.programs:
        if not op.isfile(filename):
            print(f"File {filename} does not exist.")
            return 1

        program_name, extension = op.splitext(op.basename(filename))

        if extension != ".blc":
            print(f"File {filename} is not a compiled blen program (.blc file).")
            return 1

        if program_name in programs:
            print(
                f"Program '{program_name}' already exists! "
                "Program names must be unique, since they are used to identify the winner."
            )
            return 1

        programs[program_name] = read_program(filename)

    tournament(programs, seed=args.seed, max_steps=args.max_steps, log=not args.no_logs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
