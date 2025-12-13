import unittest
import os
import pymupdf
from tempfile import TemporaryDirectory
from fetcharoo.pdf_utils import merge_pdfs, save_pdf_to_file

class TestPdfUtils(unittest.TestCase):
    def create_sample_pdf(self, num_pages=1):
        """Create a sample PDF document with the specified number of pages."""
        pdf_doc = pymupdf.open()
        for _ in range(num_pages):
            pdf_doc.new_page()
        pdf_content = pdf_doc.write()
        pdf_doc.close()
        return pdf_content

    def test_merge_pdfs(self):
        # Create two sample PDFs with 1 and 2 pages respectively
        pdf1_content = self.create_sample_pdf(num_pages=1)
        pdf2_content = self.create_sample_pdf(num_pages=2)

        # Merge the PDFs
        merged_pdf = merge_pdfs([pdf1_content, pdf2_content])

        # Check that the merged PDF has 3 pages
        self.assertEqual(merged_pdf.page_count, 3)

        # Close the merged PDF document
        merged_pdf.close()

    def test_save_pdf_to_file_append_mode(self):
        # Create a sample PDF with 2 pages
        pdf_content = self.create_sample_pdf(num_pages=2)
        pdf_document = pymupdf.Document(stream=pdf_content, filetype="pdf")

        # Use a temporary directory for testing
        with TemporaryDirectory() as temp_dir:
            # Define the output file path
            output_file_path = os.path.join(temp_dir, 'output.pdf')

            # Save the PDF to the output file
            save_pdf_to_file(pdf_document, output_file_path, mode='append')

            # Check that the output file exists
            self.assertTrue(os.path.exists(output_file_path))

            # Open the output file and check the page count
            saved_pdf = pymupdf.Document(output_file_path)
            self.assertEqual(saved_pdf.page_count, 2)

            # Close the saved PDF document
            saved_pdf.close()

    def test_save_pdf_to_file_overwrite_mode(self):
        # Create a sample PDF with 2 pages
        pdf_content = self.create_sample_pdf(num_pages=2)
        pdf_document = pymupdf.Document(stream=pdf_content, filetype="pdf")

        # Use a temporary directory for testing
        with TemporaryDirectory() as temp_dir:
            # Define the output file path
            output_file_path = os.path.join(temp_dir, 'output.pdf')

            # Save the PDF to the output file
            save_pdf_to_file(pdf_document, output_file_path, mode='overwrite')

            # Check that the output file exists
            self.assertTrue(os.path.exists(output_file_path))

            # Open the output file and check the page count
            saved_pdf = pymupdf.Document(output_file_path)
            self.assertEqual(saved_pdf.page_count, 2)

            # Close the saved PDF document
            saved_pdf.close()

            # Save a new PDF with 1 page to the same output file
            new_pdf_content = self.create_sample_pdf(num_pages=1)
            new_pdf_document = pymupdf.Document(stream=new_pdf_content, filetype="pdf")
            save_pdf_to_file(new_pdf_document, output_file_path, mode='overwrite')

            # Open the output file and check the page count
            saved_pdf = pymupdf.Document(output_file_path)
            self.assertEqual(saved_pdf.page_count, 1)

            # Close the saved PDF document
            saved_pdf.close()

    def test_save_pdf_to_file_unique_mode(self):
        # Create a sample PDF with 2 pages
        pdf_content = self.create_sample_pdf(num_pages=2)
        pdf_document = pymupdf.Document(stream=pdf_content, filetype="pdf")
        # Use a temporary directory for testing
        with TemporaryDirectory() as temp_dir:
            # Define the output file path
            output_file_path = os.path.join(temp_dir, 'output.pdf')

            # Save the PDF to the output file
            save_pdf_to_file(pdf_document, output_file_path, mode='unique')

            # Check that the output file exists
            self.assertTrue(os.path.exists(output_file_path))

            # Open the output file and check the page count
            saved_pdf = pymupdf.Document(output_file_path)
            self.assertEqual(saved_pdf.page_count, 2)

            # Close the saved PDF document
            saved_pdf.close()

            # Save a new PDF with 1 page to the same output file
            new_pdf_content = self.create_sample_pdf(num_pages=1)
            new_pdf_document = pymupdf.Document(stream=new_pdf_content, filetype="pdf")
            save_pdf_to_file(new_pdf_document, output_file_path, mode='unique')

            # Check that a new PDF file with a unique name exists
            unique_output_file_path = os.path.join(temp_dir, 'output_1.pdf')
            self.assertTrue(os.path.exists(unique_output_file_path))

            # Open the unique output file and check the page count
            unique_saved_pdf = pymupdf.Document(unique_output_file_path)
            self.assertEqual(unique_saved_pdf.page_count, 1)

            # Close the unique saved PDF document
            unique_saved_pdf.close()

if __name__ == '__main__':
    unittest.main()