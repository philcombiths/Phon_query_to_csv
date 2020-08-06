# -*- coding: utf-8 -*-
"""
Three functions, intended to be used in sequence, to batch process Phon query
output csv files in a directory or subdirectories.

Note: participant, phase, language, analysis variables must be modified to 
    specify or extract values from the current data structure. These values 
    are usually extracted from the filename str or containing directory 
    name str (see lines 131-159).


###
Example use case:
    
directory = "D:\Data\Spanish Singleton Analysis"
res = gen_csv(directory)
merge_csv()
result = column_match(os.path.join(directory,"Compiled", "merged_files", "AllPart_AllLang_AllAnalyses_data.csv"))
###

Created on Thu Jul 30 18:18:01 2020
@author: Philip
"""
# Preliminaries
import pandas as pd
import os
import io
import shutil
import glob
import csv
import sys
import logging
from contextlib import contextmanager
import regex as re

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

formatter = logging.Formatter('%(message)s - %(levelname)s - %(asctime)s')
formatter2 = logging.Formatter('%(message)s')
#Prevent duplicate logs
if (log.hasHandlers()):
    log.handlers.clear()

fh = logging.FileHandler('csv_compiler_errors.txt')
fh.setLevel(logging.CRITICAL)
fh.setFormatter(formatter2)
log.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
log.addHandler(ch)

def gen_csv(directory):
    """
    Formats a directory or subdirectories containing csv Phon query output files
    with unified column structure for input into merge_csv to generate a single
    master data file.
    
    Args:
        directory : directory path for original Phon query output files
           
    Note: participant, phase, language, analysis variables must be modified to 
        specify or extract values from the current data structure. These values 
        are usually extracted from the filename str or containing directory 
        name str (see lines 131-159).
        
    Generates a new csv file in "Compiled/uniform_files" directory for each 
        processed output file.
    
    Returns:
        tuple: (participant_list, phase_list, language_list, analysis_list, file_count)
    """
    
    participant_list = []
    phase_list = []
    language_list = []
    analysis_list = []
    file_count = 0
    assert 'Compiled' not in os.listdir(directory), "Compiled directory already exists. Move or remove before executing script,"
    with change_dir(os.path.normpath(directory)):
        for dirName, subdirList, fileList in os.walk(os.getcwd()):
            ## Check for Excel files in directory
            if any(fname.endswith('.xls') for fname in os.listdir(dirName)):
                log.warning('**Excel files located in this directory:')
                log.warning(dirName)
                log.critical(dirName)
            if any(fname.endswith('.xlsx') for fname in os.listdir(dirName)):
                log.warning('**Excel files located in this directory:')
                log.warning(dirName)
                log.critical(dirName)
            ## Check for CSV files in directory
            if not any(fname.endswith('.csv') for fname in os.listdir(dirName)):
                log.warning('**No .csv files located in this directory:')
                log.warning(dirName)
            log.info('extracting from %s' %dirName)
            try:
                os.makedirs(os.path.join(directory, 'Compiled', 'uniform_files'))
            except WindowsError:
                log.warning(sys.exc_info()[1])
                log.warning('Compiled Data directory already created.')     
            for cur_csv in os.listdir(dirName):
                # Skip other files (listed below) if they occurr
                if cur_csv == 'desktop.ini':
                    print (cur_csv, ' skipped')
                    continue
                if cur_csv == 'Report Template.txt':
                    print (cur_csv, ' skipped')
                    continue
                if cur_csv == 'Report.html':
                    print (cur_csv, ' skipped')
                    continue
                if 'Summary' in cur_csv:
                    print (cur_csv, ' skipped')
                    continue              
                # Include only CSV files
                if cur_csv.endswith('.csv'):
                    # Only works with "Accurate", "Deleted", and "Substitutions" files
                    substring_list = ['Accurate', 'Deleted', 'Deletions', 'Substitutions']
                    if any(substring in cur_csv for substring in substring_list):                
                        # open CSV file in read mode with UTF-8 encoding
                        file_count += 1
                        with io.open(os.path.join(dirName, cur_csv), mode='r', encoding='utf-8') as current_csv:
                            # create pandas DataFrame df from csv file
                            df = pd.read_csv(current_csv, encoding='utf-8')                            
                            ###################################################
                            #### Extract keyword and column values
                            keyword = 'Consonant Accuracy Phon 2.2b21 wDiacritics' # Write keyword here
                            label = 'Query' # Write column label for keyword here
                            df[label] = keyword        
                            analysis = "Singleton Accuracy"
                            analysis_list.append(analysis)
                            df['Analysis'] = analysis
                            #if re.match("BL\d|\d-MoPost|Pre|Post|Mid", cur_csv).group(0)
                            phase = re.findall(r"BL\d|\d-MoPost|Pre|Post|Mid", cur_csv)[0]
                            phase_list.append(phase)
                            df['Phase'] = phase  
                            language = 'Spanish'
                            language_list.append(language)
                            df['Language'] = language
                            participant = cur_csv.split('_')[1]
                            participant_list.append(participant)
                            df['Participant'] = participant
                            # Add column of Speaker ID extracted from filename
                            df['Speaker'] = participant                            
                            # Add column of source csv query type, extracted from filename
                            accuracy = cur_csv.split('_')[0].split('.')[0]
                            if accuracy == 'Deletions':
                                accuracy = 'Deleted'
                            df['Accuracy'] = accuracy
                            ###################################################
                            print ('***********************************************\n', list(df))
                            
                            # Save REV_csv 
                            # With UTF-8 BOM encoding for Excel readability
                            log.info('Current working directory'+os.getcwd())
                            try:
                                df.to_csv(os.path.join(directory,'Compiled', 'uniform_files', '%s_%s_%s_%s_%s.csv' % (participant, language, phase, analysis, accuracy)), encoding = 'utf-8-sig', index=False)
                            except FileNotFoundError:
                                log.error(sys.exc_info()[1])
                                log.error('Compiled Data folder not yet created')
        return (set(participant_list), set(phase_list), set(language_list), set(analysis_list), file_count)

def merge_csv(participant_list=['AllPart'], language_list=['AllLang'], 
              analysis_list=['AllAnalyses'], separate_participants=False, 
              separate_languages=False, separate_analyses=False):
    """
    
    """
    
    try:
        os.makedirs(os.path.join(directory, 'Compiled', 'merged_files'))
    except WindowsError:
        log.warning(sys.exc_info()[1])
        log.warning('Compiled Data directory already created.')        
    for participant in participant_list:
        for language in language_list:
            for analysis in analysis_list:
                with io.open(os.path.join(directory, 'Compiled','merged_files', 
                                          f'{participant}_{language}_{analysis}_data.csv'), 'wb') as outfile:
                    log.info(outfile)
                    # participantdata = os.path.join(directory, 'Compiled Data', '%s*.csv' (participant))            
                    if separate_participants:
                        if separate_languages:
                            if separate_analyses:
                                file_search_term = f"{directory}\\Compiled\\uniform_files\\*{participant}*{language}*{analysis}*.csv"
                            else:
                                file_search_term = f"{directory}\\Compiled\\uniform_files\\*{participant}*{language}*.csv"
                        else:
                            if separate_analyses:
                                file_search_term = f"{directory}\\Compiled\\uniform_files\\*{participant}*{analysis}*.csv"
                            else:
                                file_search_term = f"{directory}\\Compiled\\uniform_files\\*{participant}*.csv"                       
                    else:
                        if separate_languages:
                            if separate_analyses:
                                file_search_term = f"{directory}\\Compiled\\uniform_files\\*{language}*{analysis}*.csv"
                            else:
                                file_search_term = f"{directory}\\Compiled\\uniform_files\\*{language}*.csv"
                        else:
                            if separate_analyses:
                                file_search_term = f"{directory}\\Compiled\\uniform_files\\*{analysis}*.csv"
                            else:
                                file_search_term = f"{directory}\\Compiled\\uniform_files\\*.csv"
                    for i, fname in enumerate(glob.glob(file_search_term)):      
                        with io.open(fname, 'rb') as infile:
                            if i != 0:
                                infile.readline()  # Throw away header on all but first file
                            # Block copy rest of file from input to output without parsing
                            shutil.copyfileobj(infile, outfile)
                            log.info(fname + " has been imported.")                            
                    csv.writer(outfile)
                    log.info('Saved', outfile)
    return
                    
                    
def column_match(table_to_modify, column_key="column_alignment.csv", 
                 table_to_match=None, output_filename = "compatible_data"):
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
        table_to_modify = pd.read_csv(table_to_modify, encoding='utf-8')
    except ValueError:
        warning = "table_to_modify must be valid file path, buffer object, or DataFrame"
        assert type(table_to_modify) == pd.core.frame.DataFrame, warning
    finally:
        new_table = table_to_modify
    
    with open(column_key, mode = 'r') as key_file:
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
            if col_name_pair[1] == '':
                continue
            elif col_name_pair[0] != col_name_pair[1]:
                new_table = new_table.rename(columns={col_name_pair[1]:col_name_pair[0]})                       
        new_table = new_table.reindex(columns=target_cols)
           
        # Potential enhancement: Use optional table_to_match to import XLSX and test for compatibility.
        
        # Check new table
        valid_transformation = True
        if list(new_table.columns) == target_cols:
            pass
        elif len(list(new_table.columns)) < target_cols:
                print("WARNING: Target column(s) unaccounted for")
                valid_transformation = False
        for i, col_name_pair in enumerate(zip(list(new_table.columns), 
                                              target_cols)):
            if col_name_pair[0] != col_name_pair[1]:
                if i < len(target_cols):
                    print("WARNING: Column mismatch")
                    valid_transformation = False
                else:
                    print(f"Column {col_name_pair[1]} appended.")
        if valid_transformation == True:
            print("*****************************")
            print('Valid transformation achieved.')
        new_table.to_csv(os.path.join(directory, "Compiled", "merged_files", 
                                      f"{output_filename}.csv"), 
                                      encoding='utf-8', index=False)
        return (new_table, actual_cols_omitted_renamed, actual_cols_added)
    

###
# Example use case:
    
directory = r"G:\My Drive\Phonological Typologies Lab\Projects\Spanish SSD Tx\Participant Analyses\Spanish Singleton Analysis\S102 1-MoPost"
res = gen_csv(directory)
merge_csv()
result = column_match(os.path.join(directory,"Compiled", "merged_files", "AllPart_AllLang_AllAnalyses_data.csv"))
###
            