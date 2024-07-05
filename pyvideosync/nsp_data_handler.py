import os


class NspDataHandler:
    """This class does the following to the NSP data
    1. verify integrity
    2. get basic statistics
    3.
    """

    def __init__(self, nsp_dir: str) -> None:
        self.nsp_dir = nsp_dir
        self.files = os.listdir(nsp_dir)

    def _count_files(self, prefix: str, suffix: str) -> int:
        """Helper method to count files with a specific prefix and suffix."""
        return sum(
            1
            for file in self.files
            if file.startswith(prefix) and file.endswith(suffix)
        )

    def get_num_nsp1_nev(self):
        return self._count_files("NSP1", ".nev")

    def get_num_nsp2_nev(self):
        return self._count_files("NSP2", ".nev")

    def get_num_nsp1_ns5(self):
        return self._count_files("NSP1", ".ns5")

    def get_num_nsp2_ns5(self):
        return self._count_files("NSP2", ".ns5")

    def get_num_nsp1_ns3(self):
        return self._count_files("NSP1", ".ns3")

    def get_num_nsp2_ns3(self):
        return self._count_files("NSP2", ".ns3")

    def verify_integrity(self):
        """Verify integrity of NSP data in terms of
        1.
        """
        pass
