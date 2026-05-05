from typing import NewType, Sequence

WORD_N_BITS = 16
MAX_WORD = (1 << WORD_N_BITS) - 1

BYTE_N_BITS = 8
MAX_BYTE = (1 << BYTE_N_BITS) - 1

NIBBLE_N_BITS = 4
MAX_NIBBLE = (1 << NIBBLE_N_BITS) - 1

Word = NewType("Word", int)
Byte = NewType("Byte", int)
Nibble = NewType("Nibble", int)

TRUE = Word(MAX_WORD)
FALSE = Word(0)


def word_to_nibbles(word: Word, /) -> Sequence[Nibble]:
    return tuple(
        Nibble(word >> d & ((1 << NIBBLE_N_BITS) - 1))
        for d in range(WORD_N_BITS - NIBBLE_N_BITS, 0 - NIBBLE_N_BITS, -NIBBLE_N_BITS)
    )


def nibbles_to_word(nibbles: Sequence[Nibble], /) -> Word:
    return Word(
        sum(
            nibble << d
            for nibble, d in zip(
                nibbles,
                range(WORD_N_BITS - NIBBLE_N_BITS, 0 - NIBBLE_N_BITS, -NIBBLE_N_BITS),
            )
        )
    )
