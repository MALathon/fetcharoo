import pymupdf
import logging
import os

def merge_pdfs(pdf_contents) -> pymupdf.Document:
    """Merge multiple PDFs into a single document and return the merged document."""
    # Create a new empty PDF document
    pymupdf.TOOLS.mupdf_warnings()  # empty the problem message container
    merged_pdf = pymupdf.Document()

    for pdf_content in pdf_contents:
        # Check if the PDF content is valid
        if not pdf_content or len(pdf_content) < 10:
            logging.error('Invalid or empty PDF content.')
            continue
        try:
            # Load the PDF content into a PyMuPDF document
            pdf_document = pymupdf.Document(stream=pdf_content, filetype="pdf")
            # Append the pages of the current PDF document to the merged PDF
            merged_pdf.insert_pdf(pdf_document)
            # Close the current PDF document
            pdf_document.close()
        except Exception as e:
            logging.error(f'Failed to read PDF content: {e}')
            continue

    return merged_pdf

def save_pdf_to_file(pdf_document, output_file_path, mode='append') -> None:
    """Save a PDF document to the specified file."""
    # If mode is 'append' and the output file already exists and is not empty, insert its pages into the new PDF
    if mode == 'append' and os.path.exists(output_file_path) and os.path.getsize(output_file_path) > 0:
        existing_pdf = pymupdf.Document(output_file_path)
        pdf_document.insert_pdf(existing_pdf)
        existing_pdf.close()

    # If mode is 'unique', check if the file already exists, and if it does, append a unique identifier to the file name
    elif mode == 'unique':
        unique_id = 1
        file_name, file_ext = os.path.splitext(output_file_path)
        while os.path.exists(output_file_path):
            output_file_path = f"{file_name}_{unique_id}{file_ext}"
            unique_id += 1

    # Check if the PDF document has at least one page
    if pdf_document.page_count > 0:
        # Write the PDF to the output file
        try:
            # Save the PDF to the output file
            pdf_document.save(output_file_path)
        except IOError as e:
            logging.error(f'Failed to save PDF file to the local filesystem: {e}')
    else:
        logging.warning('Cannot save PDF with zero pages.')

    # Close the PDF document
    pdf_document.close()
