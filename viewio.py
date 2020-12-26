from io import IOBase, TextIOBase
from sublime import Region


class HexViewIO(IOBase):
    def __init__(self, view):
        if view.encoding() != "Hexadecimal":
            raise ValueError("view should have hexadecimal encoding")
        self._view = view
        self._pos = 0

    def _size(self):
        """Size of view buffer after being converted from hex to bytes."""
        self._checkSeekable()
        return self._pos_hex_to_bytes(self._view.size())

    @staticmethod
    def _pos_hex_to_bytes(pos):
        whole_lines, partial_line = divmod(pos, 40)
        whole_groups, partial_group = divmod(partial_line, 5)
        whole_bytes, partial_byte = divmod(partial_group, 2)
        return whole_lines * 16 + whole_groups * 2 + whole_bytes

    @staticmethod
    def _pos_bytes_to_hex(pos):
        whole_lines, partial_line = divmod(pos, 16)
        whole_groups, whole_bytes = divmod(partial_line, 2)
        return whole_lines * 40 + whole_groups * 5 + whole_bytes * 2

    """ Positioning """

    def seek(self, pos, whence=0):
        """Change stream position.

        Change the stream position to byte offset pos. Argument pos is
        interpreted relative to the position indicated by whence.  Values
        for whence are ints:

        * 0 -- start of stream (the default); offset should be zero or positive
        * 1 -- current stream position; offset may be negative
        * 2 -- end of stream; offset is usually negative
        Some operating systems / file systems could provide additional values.

        Return an int indicating the new absolute position.
        """
        self._checkSeekable()
        if whence == 0:
            if pos < 0:
                raise ValueError("negative seek position %r" % (pos,))
            self._pos = pos
        elif whence == 1:
            self._pos = max(0, self._pos + pos)
        elif whence == 2:
            self._pos = max(0, self._size() + pos)
        else:
            raise ValueError("unsupported whence value")
        return self._pos

    """ Inquiries """

    def seekable(self):
        """Return a bool indicating whether object supports random access.

        If False, seek(), tell() and truncate() will raise OSError.
        This method may need to do a test seek().
        """
        return self.fileno() > 0

    def readable(self):
        """Return a bool indicating whether object was opened for reading.

        If False, read() will raise OSError.
        """
        return self.fileno() > 0

    """ Lower-level APIs """

    def fileno(self):
        """Returns underlying file descriptor (an int) if one exists.

        An OSError is raised if the IO object does not use a file descriptor.
        """
        return self._view.buffer_id()

    def read(self, size=-1):
        self._checkReadable()
        if size is None:
            size = -1
        begin = self._pos_bytes_to_hex(self._pos)
        if size < 0:
            self._pos = self._size()
        else:
            self._pos = min(self._pos + size, self._size())
        end = self._pos_bytes_to_hex(self._pos)
        return bytes.fromhex(self._view.substr(Region(begin, end)).replace("\n", " "))

    def write(self, *args, **kwargs):
        self._unsupported("write")
