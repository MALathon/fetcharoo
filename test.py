from pdf_scraper.pdf_scraper import download_pdfs_from_webpage as dfw
import logging

def main():
    dfw(url='https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K223435', recursion_depth=0, mode='merge', write_dir='D:/output')

if __name__ == "__main__":
    # set logging level and specify log file
    logging.basicConfig(
        level=logging.INFO,
        filename='logfile.log',  # Specify the log file name
        format='%(asctime)s - %(levelname)s - %(message)s'  # Optional: specify log message format
    )
    main()