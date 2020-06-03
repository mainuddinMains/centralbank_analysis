from datetime import date
import threading
import sys
import os
import pickle
import re

import requests
from bs4 import BeautifulSoup

import numpy as np
import pandas as pd

# User TIKA for pdf parsing
os.environ['TIKA_SERVER_JAR'] = 'https://repo1.maven.org/maven2/org/apache/tika/tika-server/1.19/tika-server-1.19.jar'
import tika
from tika import parser

# Import parent class
from .FomcBase import FomcBase

class FomcMeetingScript(FomcBase):
    '''
    A convenient class for extracting meeting scripts from the FOMC website.

    Example Usage:  
        fomc = FomcMeetingScript()
        df = fomc.get_contents()
    '''
    def __init__(self, verbose = True, max_threads = 10, base_dir = '../data/FOMC/'):
        super().__init__('meeting_script', verbose, max_threads, base_dir)

    def _get_links(self, from_year):
        '''
        Override private function that sets all the links for the contents to download on FOMC website
         from from_year (=min(2015, from_year)) to the current most recent year
        '''
        self.links = []
        self.title = []
        self.speaker = []

        r = requests.get(self.calendar_url)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Meeting Script can be found only in the archive as it is publised after five years
        # Archived before 2015
        if from_year <= 2014:
            for year in range(from_year, 2015):
                yearly_contents = []
                fomc_yearly_url = self.base_url + '/monetarypolicy/fomchistorical' + str(year) + '.htm'
                r_year = requests.get(fomc_yearly_url)
                soup_yearly = BeautifulSoup(r_year.text, 'html.parser')
                meeting_scripts = soup_yearly.find_all('a', href=re.compile('^/monetarypolicy/files/FOMC\d{8}meeting.pdf'))
                for meeting_script in meeting_scripts:
                    self.links.append(meeting_script.attrs['href'])
                    self.speaker.append(self._speaker_from_date(self._date_from_link(meeting_script.attrs['href'])))
                    self.title.append('Meeting Transcript')
                if self.verbose: print("YEAR: {} - {} meeting scripts found.".format(year, len(meeting_scripts)))
            print("There are total ", len(self.links), ' links for ', self.content_type)

    def _add_article(self, link, index=None):
        '''
        Override a private function that adds a related article for 1 link into the instance variable
        The index is the index in the article to add to. 
        Due to concurrent processing, we need to make sure the articles are stored in the right order
        '''
        if self.verbose:
            sys.stdout.write(".")
            sys.stdout.flush()

        link_url = self.base_url + link
        article_date = self._date_from_link(link)

        #print(link_url)

        # date of the article content
        self.dates.append(article_date)

        # Scripts are provided only in pdf. Save the pdf and pass the content
        res = requests.get(link_url)
        pdf_filepath = self.base_dir + 'script_pdf/FOMC_MeetingScript_' + article_date + '.pdf'
        with open(pdf_filepath, 'wb') as f:
            f.write(res.content)
        pdf_file_parsed = parser.from_file(pdf_filepath)
        paragraphs = re.sub('(\n)(\n)+', '\n', pdf_file_parsed['content'].strip())
        paragraphs = paragraphs.split('\n')

        section = -1
        paragraph_sections = []
        for paragraph in paragraphs:
            if not re.search('^(page|january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', paragraph.lower()):
                if len(re.findall(r'[A-Z]', paragraph[:10])) > 5 and not re.search('(present|frb/us|abs cdo|libor|rp–ioer|lsaps|cusip|nairu|s cpi|clos, r)', paragraph[:10].lower()):
                    section += 1
                    paragraph_sections.append("")
                if section >= 0:
                    paragraph_sections[section] += paragraph
        self.articles[index] = "\n\n[SECTION]\n\n".join([paragraph for paragraph in paragraph_sections])