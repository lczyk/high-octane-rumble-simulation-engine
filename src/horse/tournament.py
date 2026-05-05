import argparse
import array
import dataclasses
import logging
import multiprocessing
import os.path as op
import random
import struct
import sys
from collections.abc import Iterator, Mapping, MutableMapping, Sequence

import horse.blen
import horse.types
from horse.blen import Address
from horse.types import Word


_MEMORY_SIZE = 1 << horse.types.WORD_N_BITS


@dataclasses.dataclass
class VirtualMemory(MutableMapping[Address, Word]):
    offset: int
    real_memory: array.array  # 'H' (uint16), length _MEMORY_SIZE

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(offset={self.offset}, real_memory=...)"

    def real_address(self, virtual_address: Address) -> Address:
        return Address(Word((virtual_address + self.offset) % (1 << horse.types.WORD_N_BITS)))

    def __getitem__(self, virtual_address: Address) -> Word:
        return Word(self.real_memory[self.real_address(virtual_address)])

    def __setitem__(self, virtual_address: Address, value: Word) -> None:
        self.real_memory[self.real_address(virtual_address)] = value

    def __delitem__(self, virtual_address: Address) -> None:
        self.real_memory[self.real_address(virtual_address)] = 0

    def __len__(self) -> int:
        return _MEMORY_SIZE

    def __iter__(self) -> Iterator[Address]:
        return (Address(Word(i)) for i in range(_MEMORY_SIZE))


def tournament(
    programs: Mapping[str, Sequence[Word]],
    seed: int,
    max_steps: int,
    *,
    log: bool = True,
    quiet: bool = False,
) -> list[str]:
    """Runs a tournament and returns the winner names (empty = no winner, >1 = draw)."""
    memory: array.array = array.array("H", bytes(2 * _MEMORY_SIZE))

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
    winner_names = [m.name for m in winners]

    if not quiet:
        if not winners:
            print("no one won")
        elif len(winners) == 1:
            print(winners[0].name, "won!")
        else:
            print(
                "It was a draw between the following:",
                ", ".join(machine.name for machine in machines),
            )

    return winner_names


def read_program(filename: str) -> Sequence[Word]:
    with open(filename, "rb") as f:
        contents = f.read()

    return [Word(i) for (i,) in struct.iter_unpack(">H", contents)]


def _run_one(args: tuple[dict[str, Sequence[Word]], int, int]) -> list[str]:
    programs, seed, max_steps = args
    return tournament(programs, seed=seed, max_steps=max_steps, log=False, quiet=True)


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
    parser.add_argument(
        "--n-seeds",
        type=int,
        metavar="INT",
        default=1,
        help="Run this many seeds (starting from --seed) and print aggregate W/D/L stats.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        metavar="INT",
        default=None,
        help="Worker processes for --n-seeds runs (default: cpu count).",
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

    if args.n_seeds == 1:
        tournament(programs, seed=args.seed, max_steps=args.max_steps, log=not args.no_logs)
        return 0

    tasks = [(programs, args.seed + i, args.max_steps) for i in range(args.n_seeds)]
    with multiprocessing.Pool(args.workers) as pool:
        results = pool.map(_run_one, tasks)

    wins: dict[str, int] = {name: 0 for name in programs}
    draws = 0
    no_winner = 0
    for winner_names in results:
        if len(winner_names) == 1:
            wins[winner_names[0]] += 1
        elif len(winner_names) == 0:
            no_winner += 1
        else:
            draws += 1

    n = args.n_seeds
    for name, count in wins.items():
        print(f"{name} wins: {count}/{n} ({count / n * 100:.1f}%)")
    print(f"draws:     {draws}/{n} ({draws / n * 100:.1f}%)")
    if no_winner:
        print(f"no winner: {no_winner}/{n} ({no_winner / n * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
