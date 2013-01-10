#!/usr/bin/env python
import datetime
import os
import functools
import hashlib
import re
import urllib
import urlparse

from lxml import etree
from lxml.cssselect import CSSSelector, SelectorSyntaxError, ExpressionError

from flask import Flask, abort, make_response
app = Flask(__name__)


import sys, os
sys.path.insert(0, os.path.normpath('../'))
from mincss.processor import Processor


CACHE_DIR = os.path.join(
    os.path.dirname(__file__),
    '.cache'
)

@app.route("/cache/<path:path>")
def cache(path):
    source = os.path.join(CACHE_DIR, path)
    with open(source) as f:
        response = make_response(f.read())
        response.headers["Content-type"] = "text/css"
        return response
        #return


@app.route("/<path:path>")
def proxy(path):
    if path == 'favicon.ico':
        abort(404)
    url = path
    if not path.startswith('http://'):
        url = 'http://' + url
    html = urllib.urlopen(url).read()
    p = Processor(debug=False)
    p.process(url)


    css_url_regex = re.compile('url\(([^\)]+)\)')

    def css_url_replacer(match, href=None):
        filename = match.groups()[0]
        bail = match.group()

        if ((filename.startswith('"') and filename.endswith('"')) or
            (filename.startswith("'") and filename.endswith("'"))):
            filename = filename[1:-1]
        if 'data:image' in filename or '://' in filename:
            return bail
        if filename == '.':
            # this is a known IE hack in CSS
            return bail

        if not filename.startswith('/'):
            filename = os.path.normpath(
                os.path.join(
                    os.path.dirname(href),
                    filename
                )
            )

        new_filename = urlparse.urljoin(url, filename)
        return 'url("%s")' % new_filename

    for each in p.inlines:
        # this should be using CSSSelector instead
        new_inline = each.after
        new_inline = css_url_regex.sub(css_url_replacer, new_inline)
        html = html.replace(each.before, new_inline)

    parser = etree.HTMLParser()
    stripped = html.strip()
    tree = etree.fromstring(stripped, parser).getroottree()
    page = tree.getroot()

    # lxml inserts a doctype if none exists, so only include it in
    # the root if it was in the original html.
    was_doctype = tree.docinfo.doctype
    root = tree if stripped.startswith(tree.docinfo.doctype) else page

    links = dict((x.href, x) for x in p.links)
    all_lines = html.splitlines()
    for link in CSSSelector('link')(page):
        if (
            link.attrib.get('rel', '') == 'stylesheet' or
            link.attrib['href'].lower().endswith('.css')
        ):
            print "URL", repr(url)
            print "HREF", repr(link.attrib['href'])
            hash_ = hashlib.md5(url + link.attrib['href']).hexdigest()[:7]
            now = datetime.date.today()
            destination_dir = os.path.join(
                CACHE_DIR,
                `now.year`,
                `now.month`,
                `now.day`,
            )
            mkdir(destination_dir)

            new_css = links[link.attrib['href']].after
            new_css = css_url_regex.sub(
                functools.partial(css_url_replacer, href=link.attrib['href']),
                new_css
            )
            destination = os.path.join(destination_dir, hash_ + '.css')
            with open(destination, 'w') as f:
                f.write(new_css)

            link.attrib['href'] = '/cache%s' % destination.replace(CACHE_DIR, '')

    for img in CSSSelector('img, script')(page):
        orig_src = urlparse.urljoin(url, img.attrib['src'])
        img.attrib['src'] = orig_src

    return (was_doctype and was_doctype or '') + '\n' + etree.tostring(page)


def mkdir(newdir):
    """works the way a good mkdir should :)
        - already exists, silently complete
        - regular file in the way, raise an exception
        - parent directory(ies) does not exist, make them as well
    """
    if os.path.isdir(newdir):
        return
    if os.path.isfile(newdir):
        raise OSError("a file with the same name as the desired "
                      "dir, '%s', already exists." % newdir)
    head, tail = os.path.split(newdir)
    if head and not os.path.isdir(head):
        mkdir(head)
    if tail:
        os.mkdir(newdir)

#class InlineElement(etree.Comment):
#    pass

_link_regex = re.compile('<link .*?>')
_href_regex = re.compile('href=[\'"]([^\'"]+)[\'"]')
def _find_link(line, href):
    for each in _link_regex.findall(line):
        for each_href in _href_regex.findall(each):
            if each_href == href:
                return each


if __name__ == "__main__":
    app.run(debug=True)