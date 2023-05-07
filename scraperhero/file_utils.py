import os

def check_file_exists(file_path) -> bool:
    """Check if the file already exists."""
    return os.path.exists(file_path)

def check_pdf_exists(name, write_dir) -> bool:
    """Check if the PDF file already exists."""
    if not name:
        return False

    # Determine the output file name
    file_name = os.path.basename(name)
    output_file_path = os.path.join(write_dir, file_name)

    # Check if the PDF file already exists
    return os.path.exists(output_file_path)
