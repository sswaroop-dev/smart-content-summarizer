# -*- coding: utf-8 -*-
"""Untitled2.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1_FDLgbM3sX9_pudYDBe8WJpzadRBMt5l
"""

!pip install SpeechRecognition
!pip install rake_nltk

import math
import pandas as pd
import speech_recognition as sr
from nltk import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import nltk
from googlesearch import search
from operator import itemgetter
import time

# Download NLTK data (punkt and stopwords)
nltk.download('punkt')  # Ensure punkt is downloaded
nltk.download('stopwords')
nltk.download('punkt_tab')
nltk.download('averaged_perceptron_tagger_eng')
nltk.download('maxent_ne_chunker_tab')
nltk.download('words')

"""
# CUSTOMIZABLE PARAMETERS
"""

# Adjust these values to customize your results

# Summary length factor: Increase for longer summaries, decrease for shorter ones
# Default is 1.1 - Increase (e.g., 1.3) for longer summaries, decrease (e.g., 0.9) for shorter ones
SUMMARY_LENGTH_FACTOR = 1.1

# Search parameters
DEFAULT_NUM_LINKS = 3      # Number of links to return per keyword

"""# TEXT PROCESSING FUNCTIONS"""

def create_frequency_table(text_string) -> dict:
    """
    Creates initial frequency table from input text.
    This table is used for both summarization and keyword extraction.

    Customization:
    - Modify stopWords list to include/exclude specific words
    - Adjust word stemming by modifying or removing the PorterStemmer
    """
    stopWords = set(stopwords.words("english"))
    # Add custom stopwords here if needed
    # stopWords.update(['custom', 'words'])

    words = word_tokenize(text_string)
    ps = PorterStemmer()
    freqTable = {}

    for word in words:
        word = ps.stem(word.lower())
        if word in stopWords:
            continue
        freqTable[word] = freqTable.get(word, 0) + 1

    return freqTable

def create_frequency_matrix(sentences):
    """
    Creates a frequency matrix for each sentence.
    This is the first step in calculating sentence importance.
    """
    frequency_matrix = {}
    stopWords = set(stopwords.words("english"))
    ps = PorterStemmer()

    for sent in sentences:
        freq_table = {}
        words = word_tokenize(sent)
        for word in words:
            word = ps.stem(word.lower())
            if word in stopWords:
                continue
            freq_table[word] = freq_table.get(word, 0) + 1
        # Using first 15 chars as key - adjust this length if needed
        frequency_matrix[sent[:15]] = freq_table

    return frequency_matrix

"""# TF-IDF CALCULATION FUNCTIONS"""

def create_tf_matrix(freq_matrix):
    """Calculates Term Frequency for each word in each sentence"""
    tf_matrix = {}
    for sent, f_table in freq_matrix.items():
        tf_table = {}
        count_words_in_sentence = len(f_table)
        for word, count in f_table.items():
            tf_table[word] = count / count_words_in_sentence
        tf_matrix[sent] = tf_table
    return tf_matrix

def create_documents_per_words(freq_matrix):
    """Counts how many sentences contain each word"""
    word_per_doc_table = {}
    for sent, f_table in freq_matrix.items():
        for word in f_table.keys():
            word_per_doc_table[word] = word_per_doc_table.get(word, 0) + 1
    return word_per_doc_table

def create_idf_matrix(freq_matrix, count_doc_per_words, total_documents):
    """Calculates Inverse Document Frequency for each word"""
    idf_matrix = {}
    for sent, f_table in freq_matrix.items():
        idf_table = {}
        for word in f_table.keys():
            idf_table[word] = math.log10(total_documents / float(count_doc_per_words[word]))
        idf_matrix[sent] = idf_table
    return idf_matrix

def create_tf_idf_matrix(tf_matrix, idf_matrix):
    """Combines TF and IDF matrices to create final TF-IDF scores"""
    tf_idf_matrix = {}
    for (sent1, f_table1), (sent2, f_table2) in zip(tf_matrix.items(), idf_matrix.items()):
        tf_idf_table = {}
        for (word1, value1), (word2, value2) in zip(f_table1.items(), f_table2.items()):
            tf_idf_table[word1] = float(value1 * value2)
        tf_idf_matrix[sent1] = tf_idf_table
    return tf_idf_matrix

"""# SCORING AND SUMMARY GENERATION FUNCTIONS"""

def score_sentences(tf_idf_matrix):
    """
    Calculates importance score for each sentence.

    Customization:
    - Modify the scoring formula to weigh sentences differently
    - Currently uses average TF-IDF score of words in sentence
    """
    sentenceValue = {}
    for sent, f_table in tf_idf_matrix.items():
        total_score_per_sentence = sum(f_table.values())
        count_words_in_sentence = len(f_table)
        sentenceValue[sent] = total_score_per_sentence / count_words_in_sentence
    return sentenceValue

def find_average_score(sentenceValue) -> int:
    """Calculates threshold for sentence inclusion in summary"""
    sumValues = sum(sentenceValue.values())
    average = sumValues / len(sentenceValue)
    return average

def generate_summary(sentences, sentenceValue, threshold):
    """
    Generates final summary by selecting high-scoring sentences.

    Customization:
    - Adjust threshold multiplication factor (currently SUMMARY_LENGTH_FACTOR)
    - Modify sentence selection criteria
    - Change summary format
    """
    summary = ''
    for sentence in sentences:
        if sentence[:15] in sentenceValue and sentenceValue[sentence[:15]] >= threshold:
            summary += " " + sentence
    return summary

"""# GOOGLE SEARCH FUNCTIONS"""

from rake_nltk import Rake
from sklearn.feature_extraction.text import TfidfVectorizer
import time
from googlesearch import search

def get_top_relevant_links_from_summary(summary_text, num_links=DEFAULT_NUM_LINKS):
    """
    Extracts a single broad search query from the summary using a hybrid method:
      1. RAKE is used to extract candidate phrases.
      2. TF-IDF (with 2- and 3-grams) is used to get statistically important phrases.
      3. The function then selects the first candidate that appears in both lists.
    This increases the chance of picking a query that is central to the text's topic.
    """
    # --- Step 1: RAKE Extraction ---
    r = Rake()
    r.extract_keywords_from_text(summary_text)
    rake_candidates = r.get_ranked_phrases()  # List of candidate phrases ranked by RAKE

    # --- Step 2: TF-IDF Extraction ---
    # We focus on bi-grams and tri-grams for a more specific phrase.
    vectorizer = TfidfVectorizer(ngram_range=(2, 3), stop_words="english")
    tfidf_matrix = vectorizer.fit_transform([summary_text])
    tfidf_scores = tfidf_matrix.toarray().flatten()
    feature_names = vectorizer.get_feature_names_out()

    # Sort candidate n-grams by their TF-IDF score (highest first)
    sorted_indices = tfidf_scores.argsort()[::-1]
    tfidf_candidates = [feature_names[i] for i in sorted_indices if tfidf_scores[i] > 0]

    # --- Step 3: Choose a query that appears in both candidate lists ---
    query = None
    for phrase in tfidf_candidates:
        for candidate in rake_candidates:
            # If one phrase is contained in the other, consider it a match.
            if phrase in candidate or candidate in phrase:
                query = phrase
                break
        if query:
            break

    # Fallback: if no overlap is found, try using the top TF-IDF candidate,
    # or, if that fails, the top RAKE candidate.
    if not query:
        if tfidf_candidates:
            query = tfidf_candidates[0]
        elif rake_candidates:
            query = rake_candidates[0]
        else:
            query = summary_text

    print(f"\nUsing search query: \"{query}\"")

    search_results = []
    try:
        # Using quotes for an exact match search.
        for url in search(f'"{query}"', num=num_links, stop=num_links, pause=2):
            search_results.append(url)
            # Removed: print(f"Found: {url}")
    except Exception as e:
        print(f"Error during search: {str(e)}")

    return query, search_results

"""# MAIN PROCESSING FUNCTIONS"""

def run_summarization(text):
    """
    Main function that runs the entire summarization process.
    Returns both the summary and frequency matrix for further use.
    """
    sentences = sent_tokenize(text)
    total_documents = len(sentences)

    freq_matrix = create_frequency_matrix(sentences)
    tf_matrix = create_tf_matrix(freq_matrix)
    count_doc_per_words = create_documents_per_words(freq_matrix)
    idf_matrix = create_idf_matrix(freq_matrix, count_doc_per_words, total_documents)
    tf_idf_matrix = create_tf_idf_matrix(tf_matrix, idf_matrix)
    sentence_scores = score_sentences(tf_idf_matrix)
    threshold = find_average_score(sentence_scores)

    # Adjust SUMMARY_LENGTH_FACTOR at top of file to modify summary length
    summary = generate_summary(sentences, sentence_scores, SUMMARY_LENGTH_FACTOR * threshold)

    return summary, freq_matrix

# Main execution
if __name__ == "__main__":
    # Let user choose input method
    print("\nChoose input method:")
    print("1. Speech input")
    print("2. Manual text input")

    while True:
        choice = input("\nEnter your choice (1 or 2): ").strip()

        if choice == "1":
            # Speech input
            r = sr.Recognizer()
            try:
                with sr.Microphone() as source:
                    print("\nSpeak your text clearly:")
                    print("Listening...")
                    audio = r.listen(source)
                    print("Processing speech...")
                    text = r.recognize_google(audio)
                    print("\nTranscribed text:")
                    print("-" * 50)
                    print(text)
                    print("-" * 50)

                    # Confirm the transcription
                    confirm = input("\nIs this transcription correct? (yes/no): ").lower()
                    if confirm not in ['y', 'yes']:
                        print("Please try again or choose manual input.")
                        continue
                break

            except sr.UnknownValueError:
                print("Sorry, could not understand the audio. Please try again.")
                continue
            except sr.RequestError as e:
                print(f"Could not process the speech: {str(e)}")
                print("Please try manual input instead.")
                continue

        elif choice == "2":
            # Manual text input
            print("\nEnter or paste your text below (press Enter twice when done):")
            print("-" * 50)

            # Collect lines until user enters a blank line
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)

            text = '\n'.join(lines)

            if not text.strip():
                print("No text entered. Please try again.")
                continue
            break

        else:
            print("Invalid choice. Please enter 1 or 2.")

    # After generating the summary:
summary, freq_matrix = run_summarization(text)

# Print summary
print("\nSummary:")
summary_sentences = sent_tokenize(summary)
for i, sentence in enumerate(summary_sentences, 1):
    print(f"• {sentence.strip()}")

# Get relevant links based on summary
query, relevant_links = get_top_relevant_links_from_summary(summary)
#print(f"\nSearch query used: \"{query}\"")
print("\nRelevant Links Found:")
for idx, link in enumerate(relevant_links, start=1):
    print(f"{idx}. {link}")