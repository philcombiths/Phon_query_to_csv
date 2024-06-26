# -*- coding: utf-8 -*-
# TODO Remove created temporary files.
# TODO Make ID of columns more of a generic function.
    # Else make robust to different filenames
# TODO Remove EML (doesn't seem to work)
# TODO make IPA feature adding robust to the segment regardless of diacritic.
    # Will need to refer to ipa_features.py

"""
Three functions used in sequence, to batch process Phon query
output csv files in a directory or subdirectories.

Note: participant, phase, language, analysis variables  in gen_csv() must be
    modified to specify or extract values from the current data structure. 
    These values are usually extracted from the filename str or containing 
    directory name str (see lines 143-167).

Generates:
- 'AllPart_AllLang_AllAnalyses_data.csv' : All data, extracted only from the Phon file input
- 'data_accuracy.csv' : All data from above, with Accuracy, Deletion, Substitution data
- 'combined_dataset.csv': All data from above, with phone characteristic data and data from 'phono_error_patterns.py'
    
###
# Example use case:
directory = r"D:/Data/Spanish Tx Singletons - Copy"
res = gen_csv(directory)
file_path = merge_csv()
result = column_match(file_path)
###

Created on Thu Jul 30 18:18:01 2020
@modified: 2024-06-09
@author: Philip Combiths

"""
import csv
import glob
import io
import logging
import os
import re
import shutil
import sys
from contextlib import contextmanager

import numpy as np
import pandas as pd
from ipa_features import ipa_map
from tqdm import tqdm

@contextmanager
def enter_dir(newdir):
    prevdir = os.getcwd()
    try:
        yield os.chdir(newdir)
    finally:
        os.chdir(prevdir)

@contextmanager
def change_dir(newdir):
    prevdir = os.getcwd()
    try:
        yield os.chdir(os.path.expanduser(newdir))
    finally:
        os.chdir(prevdir)

# Use log for debugging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(message)s - %(levelname)s - %(asctime)s")
formatter2 = logging.Formatter("%(message)s")

if log.hasHandlers(): # Prevent duplicate logs
    log.handlers.clear()

fh = logging.FileHandler("csv_compiler_errors.txt")
fh.setLevel(logging.CRITICAL)
fh.setFormatter(formatter2)
log.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
log.addHandler(ch)

def phon_query_to_csv(directory):
    """
    Wrapper for sequence of functions.
    """
    # Note: filepath variable required within functions
    filepath = gen_csv(directory) 
    filepath = merge_csv() # works with files created in previous step. No input needed.
    filepath = calculate_accuracy(filepath)
    result = phone_data_expander(filepath)
    print("***** All processes complete. *****")
    return result
    
# Step 1: Transforms to uniform structure csv files
def gen_csv(directory, query_type="listing"):
    """
    Formats a directory or subdirectories containing csv Phon query output files
    with unified column structure for input into merge_csv to generate a single
    master data file.

    Args:
        directory : directory path for original Phon query output files
        query_type : str in ['accuracy', 'PCC', 'listing'] specifying Phon query type.
            Default='listing' NOTE: different queries not yet implemented

    Note: participant, phase, language, analysis variables must be modified to
        specify or extract values from the current data structure. These values
        are usually extracted from the filename str or containing directory
        name str (see lines 143-167).

    Generates a new csv file in "Compiled/uniform_files" directory for each
        processed output file.

    Returns:
        tuple: (participant_list, phase_list, language_list, analysis_list, file_count)
    """

    participant_list = []
    phase_list = []
    language_list = []
    analysis_list = []
    probe_list = []
    probe_type_list = []
    file_count = 0
    try:
        assert "Compiled" not in os.listdir(directory), "Compiled directory already exists. Must be moved or remove before executing script."
    except AssertionError as e:
        print(e)
        response = input("Compiled directory already exists. Do you want to delete the 'Compiled' directory? (Y/N): ")
        if response.lower() == "y":
            shutil.rmtree(os.path.join(directory, 'Compiled'))
            print("Existing 'Compiled' directory has been deleted.")
        else:
            sys.exit("Exiting script.")
    with change_dir(os.path.normpath(directory)):
        for dirName, subdirList, fileList in os.walk(os.getcwd()):
            ## Check for Excel files in directory
            if any(fname.endswith(".xls") for fname in os.listdir(dirName)):
                log.warning("**Excel files located in this directory:")
                log.warning(dirName)
                log.critical(dirName)
            if any(fname.endswith(".xlsx") for fname in os.listdir(dirName)):
                log.warning("**Excel files located in this directory:")
                log.warning(dirName)
                log.critical(dirName)
            ## Check for CSV files in directory
            if not any(fname.endswith(".csv") for fname in os.listdir(dirName)):
                log.warning("**No .csv files located in this directory:")
                log.warning(dirName)
            log.info("extracting from %s" % dirName)
            try:
                os.makedirs(os.path.join(directory, "Compiled", "uniform_files"))
            except:  # Removed "WindowsError" for MacOS compatibility
                log.warning(sys.exc_info()[1])
                log.warning("Compiled Data directory already created.")
            for cur_csv in os.listdir(dirName):
                # Skip other files (listed below) if they occurr
                if cur_csv == "desktop.ini":
                    print(cur_csv, " skipped")
                    continue
                if cur_csv == "Report Template.txt":
                    print(cur_csv, " skipped")
                    continue
                if cur_csv == "Report.html":
                    print(cur_csv, " skipped")
                    continue
                if "Summary" in cur_csv:
                    print(cur_csv, " skipped")
                    continue
                # Include only CSV files
                if cur_csv.endswith(".csv"):
                    file_count += 1
                    with io.open(
                        os.path.join(dirName, cur_csv), mode="r", encoding="utf-8"
                    ) as current_csv:
                        # create pandas DataFrame df from csv file
                        df = pd.read_csv(current_csv, encoding="utf-8")
                        ###################################################
                        #### Extract keyword and column values
                        df.rename(columns={"Record #": "Record"}, inplace=True)
                        df.rename(columns={"Group #": "Group"}, inplace=True)
                        df['filename'] = cur_csv
                        df['Query Source'] = query
                        analysis = re.findall(
                            r"Consonants|Onset Clusters|Coda Clusters|Final Singletons|Initial Singletons|Medial Singletons|Singletons|Vowels|Initial Clusters|Final Clusters",
                            dirName,
                        )[0].replace(r"/", "")
                        analysis_list.append(analysis)
                        df["Analysis"] = analysis
                        phase = "unknown" # Default if no phase identified
                        phase = next((match for match in re.findall(
                            phase_regex,
                            cur_csv,
                        ) if match), "unknown")
                        phase_list.append(phase)
                        df["Phase"] = phase
                        # More complex language identification based on dictionary
                        lang_dict = {
                            "PEEP": "English",
                            "Peep": "English",
                            "peep": "English",
                            "En": "English",
                            "eng": "English",
                            "EFE": "Spanish",
                            "Efe": "Spanish",
                            "efe": "Spanish",
                            "Sp": "Spanish",
                            "spa": "Spanish",
                            "else": "Spanish" # When Tx is in Spanish, otherwise set to Tx language
                        }
                        language = "Spanish"  # Default language
                        for key, value in lang_dict.items():
                            if key in cur_csv and value == "English":
                                language = "English"
                                break
                        # language = cur_csv.split(".")[0] # Look in filename for language
                        language_list.append(language)
                        df["Language"] = language
                        try:
                            participant = re.findall(
                                participant_regex,
                                cur_csv,
                            )[0]
                        except IndexError as exc:
                            raise IndexError("No participant found in filename") from exc

                        participant_list.append(participant)
                        df["Participant"] = participant
                        # Add column of Speaker ID extracted from filename
                        df["Speaker"] = participant
                        ###################################################
                        print(
                            "***********************************************\n",
                            list(df),
                        )
                        probe = cur_csv.split("_")[1]
                        probe_list.append(probe)
                        df["Probe"] = probe
                        probe_type = phase
                        probe_type_list.append(probe_type)
                        df["Probe Type"] = probe_type

                        # Apply transformation to 'Result' series to generate new columns
                        derive_dict = {
                            "IPA Alignment": lambda x: x.split(";", 1)[0].strip(),
                            # "IPA Target": lambda x: x.split(";", 1)[0] # Redundant with IPA Target column
                            # .strip()
                            # .split("↔")[0]
                            # .strip(),
                            # "IPA Actual": lambda x: x.split(";", 1)[0] # Redundant with IPA Actual column
                            # .strip()
                            # .split("↔")[1]
                            # .strip(),
                            "Tiers": lambda x: x.split(";", 1)[1].strip(),
                            "Notes": lambda x: x.split(";", 1)[1].split("↔")[-1][3:],
                            "Orthography": lambda x: x.split(";", 1)[1]
                            .split(",")[0]
                            .strip(),
                            "IPA Target Words": lambda x: x.split(";", 1)[1]
                            .split(",")[1]
                            .strip(),
                            "IPA Actual Words": lambda x: x.split(";", 1)[1]
                            .split(",")[2]
                            .strip(),
                            "IPA Alignment Words": lambda x: re.search(r' (\S+↔\S+,)+', x) # updated to allow for no data (when transcription empty)
                            .group(0)
                            .strip()
                            [: -1] if re.search(r' (\S+↔\S+,)+', x) is not None else '',
                        }

                        for key in derive_dict.keys():
                            df[key] = df["Result"].apply(derive_dict[key])

                        df['IPA Target'] = df['IPA Target'].replace({'g': 'ɡ'}, regex=True)
                        df['IPA Actual'] = df['IPA Actual'].replace({'g': 'ɡ'}, regex=True)

                        # Save REV_csv, UTF-8
                        log.info("Current working directory" + os.getcwd())
                        try:
                            df.to_csv(
                                os.path.join(
                                    directory,
                                    "Compiled",
                                    "uniform_files",
                                    "%s_%s_%s_%s_%s_%s.csv"
                                    % (
                                        participant,
                                        language,
                                        phase,
                                        analysis,
                                        probe,
                                        probe_type,
                                    ),
                                ),
                                encoding="utf-8",
                                index=False,
                            )
                        except FileNotFoundError:
                            log.error(sys.exc_info()[1])
                            log.error("Compiled Data folder not yet created")
        return (
            set(participant_list),
            set(phase_list),
            set(language_list),
            set(analysis_list),
            set(probe_list),
            set(probe_type),
            file_count,
        )


# Step 2: Merges uniformly structured csv files
def merge_csv(
    participant_list=["AllPart"],
    language_list=["AllLang"],
    analysis_list=["AllAnalyses"],
    separate_participants=False,
    separate_languages=False,
    separate_analyses=False,
):
    """
    From a directory of uniformly structured csv files, merge into a single
    file or several files, as defined by fx argumments.

    Args:
        participant_list : list of participants to include, requires
            separate_participants=True. Default includes all.
        language_list : list of languages to include, requires
            separate_languages=True. Default includes all.
        analysis_list : list of analyses to include, requires
            separate_analyses=True. Default includes all.
        separate_participants : bool. Default=False
        separate_languages : bool. Default=False
        separate_analyses : bool. Default=False

    Returns str save_path

    Note: If a custom list is passed, corresponding "separate" variable must
        be set to True.
    """
    # Check for correct arguments
    if participant_list != ["AllPart"]:
        warning = (
            "If a custom participant_list is passed, separate_participants must = True"
        )
        assert separate_participants == True, warning
    if language_list != ["AllLang"]:
        warning = "If a custom language_list is passed, separate_languages must = True"
        assert separate_languages == True, warning
    if analysis_list != ["AllAnalyses"]:
        warning = "If a custom analysis_list is passed, separate_analyses must = True"
        assert separate_analyses == True, warning
    try:
        os.makedirs(os.path.join(directory, "Compiled", "merged_files"))
    # Was WindowsError for Windows operating system.
    except FileExistsError as e:
        log.warning(str(e))
        log.warning(sys.exc_info()[1])
        log.warning("Compiled Data directory already created.")
    for participant in participant_list:
        for language in language_list:
            for analysis in analysis_list:
                save_path = os.path.join(
                    directory,
                    "Compiled",
                    "merged_files",
                    f"{participant}_{language}_{analysis}_data.csv",
                )
                with io.open(save_path, "wb") as outfile:
                    log.info(outfile)
                    # participantdata = os.path.join(directory, 'Compiled Data', '%s*.csv' (participant))
                    if separate_participants:
                        if separate_languages:
                            if separate_analyses:
                                file_search_term = os.path.join(
                                    directory,
                                    "Compiled",
                                    "uniform_files",
                                    f"*{participant}*{language}*{analysis}*.csv",
                                )
                                # file_search_term = f"{directory}\\Compiled\\uniform_files\\*{participant}*{language}*{analysis}*.csv"
                            else:
                                file_search_term = os.path.join(
                                    directory,
                                    "Compiled",
                                    "uniform_files",
                                    f"*{participant}*{language}*.csv",
                                )
                        else:
                            if separate_analyses:
                                file_search_term = os.path.join(
                                    directory,
                                    "Compiled",
                                    "uniform_files",
                                    f"*{participant}*{analysis}*.csv",
                                )
                            else:
                                file_search_term = os.path.join(
                                    directory,
                                    "Compiled",
                                    "uniform_files",
                                    f"*{participant}*.csv",
                                )
                    else:
                        if separate_languages:
                            if separate_analyses:
                                file_search_term = os.path.join(
                                    directory,
                                    "Compiled",
                                    "uniform_files",
                                    f"*{language}*{analysis}*.csv",
                                )
                            else:
                                file_search_term = os.path.join(
                                    directory,
                                    "Compiled",
                                    "uniform_files",
                                    f"*{language}*.csv",
                                )
                        else:
                            if separate_analyses:
                                file_search_term = os.path.join(
                                    directory,
                                    "Compiled",
                                    "uniform_files",
                                    f"*{analysis}*.csv",
                                )
                            else:
                                file_search_term = os.path.join(
                                    directory, "Compiled", "uniform_files", "*.csv"
                                )
                    for i, fname in enumerate(glob.glob(file_search_term)):
                        with io.open(fname, "rb") as infile:
                            if i != 0:
                                infile.readline()  # Throw away header on all but first file
                            # Block copy rest of file from input to output without parsing
                            shutil.copyfileobj(infile, outfile)
                            log.info(fname + " has been imported.")
                    csv.writer(outfile)
                    log.info("Saved", outfile)

    return save_path


# Step 3: Create accuracy columns in dataframe
def calculate_accuracy(filepath):
    """
    Calculate accuracy metrics based on IPA Target and IPA Actual columns in a CSV file.

    Args:
        filepath (str): The path to the CSV file.

    Returns:
        DataFrame: The updated DataFrame with accuracy metrics.
    """
    output_filename = "data_accuracy.csv"
    # Read the CSV file into a DataFrame
    df = pd.read_csv(filepath, encoding="utf-8")

    # Create masks to derive accurate, substituted, and deleted phones
    accurate_mask = df["IPA Target"] == df["IPA Actual"]
    inaccurate_mask = df["IPA Target"] != df["IPA Actual"]
    deletion_mask = df["IPA Actual"].isin([pd.NaT, "", " ", "∅"]) | df["IPA Actual"].isnull()
    substitution_mask = ((df["IPA Target"] != df["IPA Actual"]) & (~deletion_mask))

    # Initialize columns with default values
    df["Accuracy"] = 0
    df["Deletion"] = 0
    df["Substitution"] = 0

    print("Processing Accuracy, Deletion, Substitution...")

    # Assign values to columns based on masks
    df.loc[accurate_mask, "Accuracy"] = 1
    df.loc[deletion_mask, "Deletion"] = 1
    df.loc[substitution_mask, "Substitution"] = 1

    # Save the updated DataFrame to a new CSV file
    print(f"Generating {output_filename}...")

    output_filepath = os.path.join(os.path.dirname(filepath), output_filename)
    df.to_csv(output_filepath, encoding="utf-8", index=False)

    print(f"Saved {output_filename}")

    return output_filepath

# Step 3: Organizes and renames columns according to column_alignment.csv
def column_match(
    table_to_modify,
    column_key="column_alignment.csv",
    table_to_match=None,
    output_filename="compatible_data",
):
    """
    Rearranges and renames columns in a DataFrame or CSV table to fit column
    structure specified in a column_key.

    Args:
        table_to_modify : file path, buffer object, or DataFrame
        column_key : file path. Default = 'column_alignment.csv'
        table_to_match : file path (optional). Default = None.
        output_filename : str. Default = "compatible_data"

    Generates output_filename csv file

    Returns:
        tuple: (new_table, actual_cols_omitted_renamed, actual_cols_added)
    """

    # Import table_to_modify as DataFrame
    try:
        if os.path.isfile(table_to_modify):
            table_directory = os.path.dirname(table_to_modify)
            print("'table_to_modify' input is a filepath.")
            table_to_modify = pd.read_csv(table_to_modify, encoding="utf-8")
    except:
        pass
    else:
        table_directory = None
        if isinstance(table_to_modify, pd.DataFrame):
            print("'table_to_modify' input is a DataFrame already.")
            warning = (
                "table_to_modify must be valid file path, buffer object, or DataFrame"
            )
        assert type(table_to_modify) == pd.core.frame.DataFrame, warning
    new_table = table_to_modify
    # os.path.join(table_directory,
    with open(column_key, mode="r") as key_file:
        key_reader = csv.reader(key_file)
        # Extract column information
        for i, row in enumerate(key_reader):
            if i == 2:
                target_cols = row
            if i == 3:
                actual_cols = row

        # Check actual columns
        actual_cols_omitted_renamed = []
        actual_cols_added = []
        for col in list(table_to_modify.columns):
            if col not in actual_cols:
                actual_cols_omitted_renamed.append(col)
        for col in actual_cols:
            if col not in list(table_to_modify.columns):
                actual_cols_added.append(col)
        # Rename actual columns
        for col_name_pair in zip(target_cols, actual_cols):
            if col_name_pair[1] == "":
                continue
            elif col_name_pair[0] != col_name_pair[1]:
                new_table = new_table.rename(
                    columns={col_name_pair[1]: col_name_pair[0]}
                )
        new_table = new_table.reindex(columns=target_cols)

        # Potential enhancement: Use optional table_to_match to import XLSX and test for compatibility.

        # Check new table
        valid_transformation = True
        if list(new_table.columns) == target_cols:
            pass
        elif len(list(new_table.columns)) < target_cols:
            print("WARNING: Target column(s) unaccounted for")
            valid_transformation = False
        for i, col_name_pair in enumerate(zip(list(new_table.columns), target_cols)):
            if col_name_pair[0] != col_name_pair[1]:
                if i < len(target_cols):
                    print("WARNING: Column mismatch")
                    valid_transformation = False
                else:
                    print(f"Column {col_name_pair[1]} appended.")
        if valid_transformation == True:
            print("*****************************")
            print("Valid transformation achieved.")
        else:
            print("*****************************")
            print(
                "WARNING: Valid transformation NOT achieved. Check file when complete."
            )
        print("Creating file...")

        output_filepath = os.path.join(
            directory, "Compiled", "merged_files", f"{output_filename}.csv"
        )
        new_table.to_csv(
            output_filepath,
            encoding="utf-8",
            index=False,
        )
        print("CSV file Generated:", os.path.abspath(output_filepath))
        print("Process complete.")
        return (new_table, actual_cols_omitted_renamed, actual_cols_added)
    
    
# phone_data_expander [in progress]
def phone_data_expander(file_location):
    output_filepath = os.path.join(
        directory, "Compiled", "merged_files", "full_annotated_dataset.csv"
    )
    
    if not isinstance(file_location, pd.DataFrame):
        # If not, assume it's a file location and load the data
        df = pd.read_csv(file_location)
    else:
        df = file_location
    # Generate ['ID-Target-Lang'] column
    df['ID-Target-Lang'] = df['Participant'] + df['IPA Target'] + df['Language']
    try: # Don't generate from Target columns if queries don't have Targets
        # Generate ['Target Type'] column
        df['Target Type'] = np.where(df['IPA Target'].str.len() == 1, 'C', np.where(df['IPA Target'].str.len() == 2, 'CC', 'CCC'))
        # Generate Target and Actual columns for each consonant in clusters
        df['T1'] = df['IPA Target'].str[0]  # Get C1
        df['T2'] = df['IPA Target'].str[1]  # Get C2
        df['T3'] = df['IPA Target'].str[2]  # Get C3
    except AttributeError:
        df['Target Type'] = ''
        df['T1'] = ''  # Get C1
        df['T2'] = ''  # Get C2
        df['T3'] = ''  # Get C3
    # Actual segments not accurate because diacritics are treated as segments.
    df['A1'] = df['IPA Actual'].str[0]  # Get C1
    df['A2'] = df['IPA Actual'].str[1]  # Get C2
    df['A3'] = df['IPA Actual'].str[2]  # Get C3
    df['A4'] = df['IPA Actual'].str[3]  # Get C4
    df['A5'] = df['IPA Actual'].str[4]  # Get C5
    # Fill NaN with empty string ''
    columns = ['T1', 'T2', 'T3', 'A1', 'A2', 'A3', 'A4', 'A5']
    df[columns] = df[columns].fillna('')
    
    properties = ['voice', 'place', 'manner', 'sonority']
    for col in tqdm(columns, desc='Processing by-segment feature columns'):
        for prop in properties:
            df[f'{col}_{prop}'] = df[col].apply(lambda x: getattr(ipa_map.ph_element(x), prop, '') if x else '')

    columns_more = ['IPA Target', 'IPA Actual']
    properties_more = ['voice', 'place', 'manner', 'sonority', 'EML']
    for col in tqdm(columns_more, desc='Processing features for IPA Target/Actualcolumns'):
        for prop in properties_more:
            df[f'{col}_{prop}'] = df[col].apply(lambda x: getattr(ipa_map.ph_element(x), prop, '') if x else '')
            # TODO Make this work for the main segment regardless of diacritics.

    output_filepath = os.path.join(
        directory, "Compiled", "merged_files", "full_annotated_dataset.csv"
    )
    df.to_csv(
        output_filepath,
        encoding="utf-8",
        index=False,
    )

    return df
    
    # For all the 'T1', 'T2', 'T3','A1', 'A2', 'A3', 'A4', 'A5' columns that contain IPA:
        # extract sonority, manner, voice, place as new columns in the df using ipa_map.py
    # When Type== "CC"
        # Sonority distance
        # For each component, 
    # For each component phoneme:
    #   Create df columns for each of the useful feature details:
    #   sonority, manner, voice, place, class
    #   Use the IPA table project already started
    # Draw on other required tables, including baseline phones to create additional cols
    

# Example use case:
if __name__ == "__main__":
    # parameters
    directory = os.path.normpath(input("Enter directory: "))
    query = "Queries_v5_phone_listings_phrase.xml"  # Write keyword here
    print("**********************************\n")
    print("Available flavors:\n")
    print("    - tx")
    print("    - typology")
    print("    - new typology\n")
    flavor = input("Specify flavor: ")

    if flavor == "tx":
        participant_regex = r"\w\d\d\d"
        phase_regex = r"BL-\d{1,2}|Post-\dmo|Pre|Post|Mid|Tx-\d{1,2}"

    elif flavor == "typology":
        participant_regex = r"\d\d\d"
        phase_regex = r"p[IVX]+"

    elif flavor == "new typology":
        participant_regex = r"\w{3,4}\d\d"
        phase_regex = r"no phases" # No phases in this dataset. Trigger null regex result

    result = phon_query_to_csv(directory)
    pass