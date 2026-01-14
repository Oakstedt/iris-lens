# hcp_client.py
import sys
import os

# Ensure we can import from the bundled 'src' folder
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    # Adjust this import based on the actual NGPIris structure in /src
    from hcp import HCPHandler 
except ImportError:
    HCPHandler = None

class HCPClient:
    """ Encapsulates all interactions with the NGP-Iris Backend. """
    def __init__(self):
        self.connected = False
        # Future: Initialize HCPHandler here using credentials

    def list_buckets(self):
        """ Returns a list of bucket names. """
        # Mock logic - Replace with real HCPHandler call later
        return ["research-cohort-2025", "clinical-data-archive", "temp-storage"]

    def fetch_files(self, bucket_name):
        """ Returns a list of file tuples: (name, size, type, date) """
        # Mock logic - Replace with real HCPHandler call later
        return [
            ("patient_data_001.csv", "1.2 MB", "CSV", "2025-01-10"),
            ("scan_results_MRI.dicom", "450 MB", "DICOM", "2025-01-12"),
            ("summary_report.pdf", "0.5 MB", "PDF", "2025-01-14"),
            ("notes_v2.txt", "0.1 KB", "Text", "2025-01-14"),
        ]