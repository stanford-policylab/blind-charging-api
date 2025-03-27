import base64
import struct
from typing import Generator


class EmbeddingCodec:
    """A codec for working with Embeddings.

    This class is focused on IO encoding/decoding operations for embeddings.

    This class does *not* deal with analytical operations on embeddings, such as
    computing similarity metrics.

    The binary vector format is intended to be simple enough to port easily to other
    languages: a sequence of double-precision (64-bit) floats in big-endian format.

    For example to load the vector in R, the following will work:

    ```R
    library(base64enc)

    eb64 <- "..." // base64-encoded binary data

    // Decode eb64 from base64 to get the binary data
    bin <- base64decode(eb64)
    // Decode `ebin` binary data. It is a big-endian vector of 64-bit doubles.
    vec <- readBin(bin, "double", n = length(ebin) / 8, endian = "big")
    ```
    """

    _VECTOR_TYPE = "d"
    """Storage format for the embedding.

    Default is storing `n` double-precision floats (64-bit).
    """

    _HEADER_FMT = ">"
    """Header for the struct format.

    This encodes the endianness. The default is big-endian.
    (The choice of endianness is arbitrary, but should be explicit and consistent.)
    """

    _PACK_STRUCT = _HEADER_FMT + "{n}" + _VECTOR_TYPE
    """Format string for packing and unpacking the embedding.

    This combines the header, dimensionality, and vector type.
    """

    @classmethod
    def calc_binary_size(cls, n: int) -> int:
        """Calculate the size of the binary embedding."""
        return struct.calcsize(cls._PACK_STRUCT.format(n=n))

    @classmethod
    def from_binary(cls, value: bytes | bytearray | str) -> "EmbeddingCodec":
        """Convert a binary embedding to a list of floats.

        If the input is passed as a string, it is assumed to be base64-encoded.

        Args:
            value (bytes | bytearray | str): The binary embedding.

        Returns:
            EmbeddingCodec: The embedding object.
        """
        if isinstance(value, str):
            value = base64.b64decode(value)

        return cls(list(cls.unpack(value)))

    @classmethod
    def pack(cls, value: list[float] | tuple[float, ...]) -> bytearray:
        """Pack the embedding into bytes.

        Args:
            value (list[float] | tuple[float]): The embedding to pack.

        Returns:
            bytearray: The packed embedding.

        Raises:
            ValueError: If the embedding exceeds the maximum size.
        """
        v_len = len(value)

        fmt = cls._pack_format(v_len)

        v_bin = bytearray(struct.calcsize(fmt))
        struct.pack_into(fmt, v_bin, 0, *value)
        return v_bin

    @classmethod
    def unpack(cls, value: bytes | bytearray) -> Generator[float, None, None]:
        """Unpack the embedding from bytes.

        Args:
            value (bytes): The packed embedding.

        Yields:
            Generator[float, None, None]: Unpacked floats from the embedding.
        """
        # Decode the embedding point-by-point until it's complete.
        # Re-use the pack format with `n=1` to get each point, including
        # the endianness header.
        point_fmt = cls._pack_format(1)
        for p in struct.iter_unpack(point_fmt, value):
            yield p[0]

    @classmethod
    def _pack_format(cls, n: int) -> str:
        """Return the format string for packing the vector.

        Args:
            n (int): The dimensionality of the vector.

        Returns:
            str: The format string for `struct` operations.
        """
        return cls._PACK_STRUCT.format(n=n)

    @property
    def dimensions(self) -> int:
        """Return the number of dimensions in the embedding."""
        return len(self.vector)

    def __init__(self, vector: list[float] | tuple[float]) -> None:
        """Initialize the embedding with a vector."""
        self.vector: tuple[float, ...] = tuple(vector)

    def to_binary(self) -> bytes:
        """Convert the embedding to binary."""
        return bytes(self.pack(self.vector))

    def to_base64(self) -> str:
        """Convert the embedding to a base64-encoded string."""
        return base64.b64encode(self.to_binary()).decode()

    def to_list(self) -> list[float]:
        """Convert the embedding to a list."""
        return list(self.vector)
