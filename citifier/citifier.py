#!/usr/bin/env python
"""
Moby Dick by Herman Melville and 346 Others

An entry for NaNoGemMo ("write code that writes a novel") 2019.

https://github.com/hugovk/NaNogenMo/2019
https://github.com/NaNoGenMo/2019/issues/34

Go through a book, eg. Moby Dick, check each word in turn, find another work using that
word, and add that work as a citation for that single word. "Moby Dick, as written by
[list of cited authors]".

Prep:
Download Project Gutenberg's August 2003 CD archive ("contains 600 of our best Ebooks")
    https://www.gutenberg.org/wiki/Gutenberg:The_CD_and_DVD_Project

Extract into PG2003-08, so that:
    PG2003-08/master_list.csv contains the metadata (use the fixed version in this repo)
    PG2003-08/etext00/ these contain txt files
    PG2003-08/etext01/ "
    PG2003-08/etextXX/ "

Move the main work into the root:
    mv PG2003-08/etext01/moby11.txt .

And manually delete the PG boilerplate from beginning and end of moby11.txt
(use the one in this repo)

Run with just three input books:
    python citifier.py --number 3

Run with all found books and cache the processed co-author books
(On my machine: ~60 mins first run, ~20 mins subsequent runs):
    python citifier.py --cache

Create a PDF:
    brew cask install wkhtmltopdf
    wkhtmltopdf output.html output.pdf
"""
import argparse
import codecs
import csv
import os
import pickle
import random
import re
from pprint import pprint

from textblob import TextBlob  # pip install textblob
from tqdm import tqdm  # pip install tqdm

BOOKS_CACHE = "/tmp/citifier.pkl"


def recursive_find(inspec):
    import fnmatch

    matches = []
    head, tail = os.path.split(inspec)
    if len(head) == 0:
        head = "."

    for root, dirnames, filenames in os.walk(head):
        for filename in fnmatch.filter(filenames, tail):
            matches.append(os.path.join(root, filename))

    return matches


def load_cache(filename):
    data = None
    if os.path.isfile(filename):
        print("Open cache...")
        with open(filename, "rb") as fp:
            data = pickle.load(fp)
    return data


def save_cache(filename, data):
    with open(filename, "wb") as fp:
        pickle.dump(data, fp, -1)


class Book:
    def __init__(self, filename):
        self.fullpath = filename
        _, self.filename = os.path.split(filename)

        try:
            text = self.text()
        except UnicodeDecodeError:
            # TODO fix for etext03/vbgle11a.txt and etext04/clprm10u.txt
            text = ""

        blob = TextBlob(text)
        self.set = set(blob.words.lower())

    def text(self):
        with codecs.open(self.fullpath, encoding="cp1252") as f:
            return f.read()


def make_cites(cite_filenames, metadata):
    out = []
    # print(cite_filenames)
    for i, id in enumerate(cite_filenames):
        try:
            author = metadata[id]["Author-LN"].strip()
            if metadata[id]["Author-FN"]:
                author += ", " + metadata[id]["Author-FN"].strip()
        except KeyError:
            author = "[Unknown author]"
            pprint(id)
        try:
            title = metadata[id]["Title"]
            if metadata[id]["Subtitle"]:
                title += ": " + metadata[id]["Subtitle"].strip()
        except KeyError:
            title = f"[{id}]"
            pprint(id)
        out.append(f"<r>{i+1}</r> {author}, <i>{title}</i>")
    return out


def get_coauthors(cite_filenames, metadata):
    out = set()
    for i, id in enumerate(cite_filenames):
        try:
            author = ""
            if metadata[id]["Author-FN"]:
                author += metadata[id]["Author-FN"].strip() + " "
            author += metadata[id]["Author-LN"].strip()
        except KeyError:
            author = "[Unknown author]"
        out.add(author)
    return list(out)


def load_metadata():
    with open("PG2003-08/master_list.csv") as f:
        # Skip first 4 lines of preamble
        next(f)
        next(f)
        next(f)
        next(f)
        reader = csv.DictReader(f)

        result = {}
        for row in reader:
            # print(row)
            key = row.pop("Text")
            # Only keep those with text files, ignore HTMLs
            if key == "":
                continue
            # if key in result:
            # implement your duplicate row handling here
            # pass
            result[key] = row

        # pprint(result)
        # pprint(result["zenda10.txt"])
        # pprint(result["zenda10.txt"]["Title"])
        return result


def main(infile1, inspec, total_books, use_cache):
    print("open")

    metadata = load_metadata()

    book1 = Book(infile1)
    print(book1.filename)
    print("set1 words:", len(book1.set))

    books = load_cache(BOOKS_CACHE) if use_cache else None
    if not books:
        files = recursive_find(inspec)
        if total_books > 0:
            files = random.sample(files, min(total_books, len(files)))

        print("read books")
        books = [Book(file) for file in tqdm(files, unit="book")]
        if use_cache:
            save_cache(BOOKS_CACHE, books)

    print("citify")
    book1_text = book1.text()
    done = set()
    # List of cited works
    cite_filenames = []
    for word in tqdm(list(book1.set), unit="word"):
        # for word in tqdm(list(book1.set)[:1000], unit="word"):
        if word.lower() in done:
            continue

        # Skip some words that mess up the regex, like "START**THE", "ETEXTS**START"
        if "*" in word:
            continue

        # print(word)
        done.add(word.lower())

        random.shuffle(books)
        # print(books)

        for book2 in books:
            # print(book2.filename)

            if word.lower() in book2.set:

                if book2.filename not in cite_filenames:
                    cite_filenames.append(book2.filename)

                # Replace them all with the word and a cite number
                book1_text = re.sub(
                    rf"\b({word})\b",
                    rf"\1REF{cite_filenames.index(book2.filename)+1}REF",
                    book1_text,
                    flags=re.IGNORECASE,
                )
                break

    print("done:", len(done))

    # print("missing:")
    # pprint(book1.set - done)

    # Now all the big text replacements are done, replace REFxREF with some HTML
    book1_text = re.sub(rf"REF(\d+)REF", rf"<r>\1</r>", book1_text)

    title = metadata[book1.filename]["Title"]
    first_author = (
        f'{metadata[book1.filename]["Author-FN"].strip()} '
        f'{metadata[book1.filename]["Author-LN"].strip()}'
    )

    coauthors = get_coauthors(cite_filenames, metadata)
    cites = make_cites(cite_filenames, metadata)
    cite_list = "\n".join(cites)

    with open("output.html", "w") as f:
        f.write(
            f"""
<title>{title} by {first_author} and {len(coauthors)} Others</title>
<link rel="stylesheet" href="style.css">
<center id="top">
<h1><i>{title}</i></h1>
<h3>by</h3>
<h2>{first_author}</h2>
<h3>and</h3>
<p>{", ".join(coauthors[:-1])} and {coauthors[-1]}
<p>Jump to <a href="#references">references</a>
</center>
<pre>
"""
        )
        f.write(book1_text)
        f.write(
            f"""

<h1 id="references">References</h1>
{cite_list}
</pre>
<p><a href="#top">Back to top</a>
"""
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Always cite your sources",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-i1", "--infile", default="moby11.txt", help="Input filename")
    parser.add_argument(
        "-i2",
        "--inspec",
        default="PG2003-08/*.txt",
        help="Input file spec of texts by co-authors",
    )
    parser.add_argument(
        "-n",
        "--number",
        default=0,
        type=int,
        help="Total number of co-author books to read. 0=all",
    )
    parser.add_argument(
        "-c",
        "--cache",
        action="store_true",
        help="Cache the processed co-author books. "
        "If the cache exists, ignores --inspec and --number, and saves ~40 minutes. ",
    )
    args = parser.parse_args()

    main(args.infile, args.inspec, args.number, args.cache)


# End of file
