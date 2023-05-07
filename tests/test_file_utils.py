import os
import unittest
from tempfile import TemporaryDirectory
from fetcharoo.file_utils import check_file_exists, check_pdf_exists

class TestFileUtils(unittest.TestCase):
    def test_check_file_exists(self):
        # Create a temporary directory for testing
        with TemporaryDirectory() as temp_dir:
            # Create a temporary file within the temporary directory
            temp_file_path = os.path.join(temp_dir, 'test_file.txt')
            with open(temp_file_path, 'w') as temp_file:
                temp_file.write('Test content')

            # Test that check_file_exists returns True for an existing file
            self.assertTrue(check_file_exists(temp_file_path))

            # Test that check_file_exists returns False for a non-existent file
            non_existent_file_path = os.path.join(temp_dir, 'non_existent.txt')
            self.assertFalse(check_file_exists(non_existent_file_path))

    def test_check_pdf_exists(self):
        # Create a temporary directory for testing
        with TemporaryDirectory() as temp_dir:
            # Create a temporary PDF file within the temporary directory
            temp_pdf_path = os.path.join(temp_dir, 'test_file.pdf')
            with open(temp_pdf_path, 'w') as temp_file:
                temp_file.write('Test content')

            # Test that check_pdf_exists returns True for an existing PDF file
            self.assertTrue(check_pdf_exists('test_file.pdf', temp_dir))

            # Test that check_pdf_exists returns False for a non-existent PDF file
            self.assertFalse(check_pdf_exists('non_existent.pdf', temp_dir))

            # Test that check_pdf_exists returns False for an empty name
            self.assertFalse(check_pdf_exists('', temp_dir))

if __name__ == '__main__':
    unittest.main()
