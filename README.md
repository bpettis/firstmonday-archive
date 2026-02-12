# firstmonday-archive

https://firstmonday.org/ojs/index.php/fm/announcement/view/99

After 30 years of publication, the open access peer reviewed journal _First Monday_ will be ceasing publication. The community of internet researchers is quite saddened by this news, and there has already been a great deal of interest in finding ways to continue the journal's operations. While much remains to be seen about what will happen next, it seems prudent to ensure that this invaluable piece of internet history is adequately preserved.

I am working on a simple project to mirror all publications from _First Monday_ to ensure that this rich collection of scholarship is not lost.

For questions or more info, contact me at [ben.pettis@richmond.edu](ben.pettis@richmond.edu)

## Basic Usage

1. Install required packages

```
pip3 install -r requirements.txt
```

2. Run the `scraper.py` script

```
python3 scraper.py
```

This will create two files, `articles.csv` and `issues.csv` which contains metadata for all articles and issues.
A separate folder `pdfs` will be created which contains the PDF for each article. 

## Known Issues

- Downloads PDFs, but for articles that only include HTML (Which is a _lot_ of stuff pre-2018ish), the article is not yet downloaded at this point (information is still saved to the CSV so we can go back and get them later)

## Future Steps

- Upload PDF files (along with metadata) to Internet Archive for wider access
- Recreate search funcationality on a new website (or possibly integrate with Internet Archive?)


## Other Notes

Work published in _First Monday_ is published under a permissive Creative Commons License (Attribution-NonCommercial-ShareAlike 4.0 International License)
Authors retain copyright to their work published in _First Monday_. Please see the footer of each article for details.

