# It saves the parsed data into the csv format 

import os 
import csv

#STEP 1: Create Output Dictionary

def create_output_directory():
    # creates the output folder if it dosen't exists 
    os.makedirs("data/csv", exist_ok = True)

# STEP 2: Prepare 1 CSV row 
def prepare_row(metadata):

    """ Converts the metadata into a CSV - friendly format .
    Lists like judges and citations are converted into strings because CSV Files cannot store Python lists. """

    row = metadata.copy() # making a copy 

    # convert ths list of judges into 1 string 
    row["judges"] = " | ".join(row["judges"])

    #convert list of citations into 1 string 
    row["citations"] = " | ".join(row["citations"])

    return row

#STEP 3: Write metadata to CSV
def write_csv(metadata_list):

    """
    Write all the metadata dictionaries into a CSV file"""
    
    # create output folder 
    create_output_directory()

    # Output CSV path 
    csv_path = "data/csv/judgements.csv"

    # If there is no data, stop
    if len(metadata_list) == 0:
        print("No metadata available to save.")
        return 
    
    #Get all column names from first dictionary 
    fieldnames = metadata_list[0].keys()

    #Open CSV file 
    with  open(csv_path, mode = "w", newline = "", encoding = "utf-8") as csv_file :

        #Create CSV writer 
        writer = csv.DictWriter(csv_file, fieldnames = fieldnames)

        #write coulmn names
        writer.writeheader()

        # write each metadata dictionary 
        for metadata in metadata_list:
            row = prepare_row(metadata)
            writer.writerow(row)

    print(f"\nCSV successfully saved at : {csv_path}")

# STEP 4 : Testing
# ---------------------------------------------------------

if __name__ == "__main__":

    from scraper.search import search_judgements
    from scraper.downloader import download_all_pdfs
    from scraper.parser import parse_all_judgements

    # Search judgments
    results = search_judgements(
        search_query="criminal appeal",
        category="Criminal"
    )

    # Download PDFs
    results = download_all_pdfs(results[:2])

    # Parse metadata
    results = parse_all_judgements(results)

    # Save CSV
    write_csv(results)