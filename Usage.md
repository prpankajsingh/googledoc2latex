# Introduction #

Google Docs are a great collaborative tool. This script helps convert a google doc to a latex file so you can just edit the whole thing on google doc with collaborators.

# Details #

Firstly you need to publish you google doc - this allows the script to be able to fetch it without needing to log into a google account. This can be done by selecting "Share/Publish as Web page". Its also useful to allow the document to be republished each time its changed.

Google docs have a complex hard to remember URL so its always good to use tinyurl to make it easier to remember.

There is already a test page you can try, and we will use it with out example:

```
python googledoc2latex.py -o test http://tinyurl.com/googledoc2latex-testpage
```

This will create test.tex and test.bib. Now we can compile them:
```
$ pdflatex test
$ bibtex test
$ pdflatex test
$ pdflatex test
```
And we should have a pdf document ready to go.