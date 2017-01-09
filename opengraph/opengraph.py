# encoding: utf-8

import re
import requests

# Inject pyopenssl into urllib3 to prevent warnings
try:
    import urllib3.contrib.pyopenssl
    urllib3.contrib.pyopenssl.inject_into_urllib3()
except Exception as e:
    pass

# BeautifulSoup processing
try:
    from bs4 import BeautifulSoup
except ImportError:
    from BeautifulSoup import BeautifulSoup

# Import JSON
global import_json
try:
    import json
    import_json = True
except ImportError:
    import_json = False



class OpenGraph(dict):
    """
    """
    
    user_agent        = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:43.0) Gecko/20100101 Firefox/43.0"
    user_agent_header = 'User-Agent'
    required_attrs    = ['title', 'type', 'image', 'url', 'description']

    def __init__(self, url=None, html=None, scrape=False, headers=None, **kwargs):
        # If scrape == True, then will try to fetch missing attribtues
        # from the page's body

        self.scraped = False
        self.scrape = scrape
        self._url = url

        self.doc = None
        self.response_headers = None

        for k in kwargs.keys():
            self[k] = kwargs[k]
        
        dict.__init__(self)

        # Handle custom http headers
        if headers:
            self.headers = headers
            
            # Add in the user agent header if not provided
            if self.user_agent_header not in self.headers:
                self.headers[self.user_agent_header] = self.user_agent
        else:
            # Always have user agent header at a minimum
            self.headers = {self.user_agent_header: self.user_agent}

        if url is not None:
            self.fetch(url, self.headers)
            
        if html is not None:
            self.parser(html)

    def __setattr__(self, name, val):
        self[name] = val

    def __getattr__(self, name):
        return self[name]

    def fetch(self, url, headers=None):
        """
        """
        request_obj = requests.get(url, headers=headers, timeout=(3, 5))
        html = request_obj.content
        self.response_headers = request_obj.headers

    # Since there might be a redirect, get the final url from request object
        self._url = request_obj.url

        return self.parser(html)
        
    def parser(self, html):
        """
        """
        if not isinstance(html, BeautifulSoup):
            doc = BeautifulSoup(html, "lxml")
        else:
            doc = html

        self.doc = doc

        # Some sites only have og tags in the header, some in the body
        # ogs = doc.html.head.findAll(property=re.compile(r'^og'))
        ogs = doc.html.findAll(property=re.compile(r'^og'))
        
        # Look at every og tag
        for og in ogs:
            if og.has_attr(u'content'):
                # Store property name minus the "og:"
                prop_name = og[u'property'][3:]

                # If this is a video property, create a list since many sites offer alternative formats
                if 'video' in prop_name:
                    # If first time, init the list with property content
                    if prop_name not in self:
                        self[prop_name] = [ og[u'content'] ]
                    # else append to the list with property content
                    else:
                        self[prop_name].append(og[u'content'])
                # For non-video properties, just copy the content
                # NOTE: this means that for duplicate properties, only the last one survives
                else:
                    self[prop_name] = og[u'content']
        
        # Couldn't fetch all required attrs from og tags, try scraping body
        if not self.is_valid() and self.scrape:
            for attr in self.required_attrs:
                if not self.valid_attr(attr):
                    try:
                        self[attr] = getattr(self, 'scrape_%s' % attr)(doc)
                    except AttributeError:
                        pass
            self.scraped = True

    def valid_attr(self, attr):
        return hasattr(self, attr) and len(self[attr]) > 0

    def is_valid(self):
        try:
            return all([self.valid_attr(attr) for attr in self.required_attrs])
        except KeyError:
            return False
        
    def to_html(self):
        if not self.is_valid():
            return u"<meta property=\"og:error\" content=\"og metadata is not valid\" />"
            
        meta = u""
        for key,value in self.iteritems():
            meta += u"\n<meta property=\"og:%s\" content=\"%s\" />" %(key, value)
        meta += u"\n"
        
        return meta
        
    def to_json(self):
        # TODO: force unicode
        global import_json
        if not import_json:
            return "{'error':'there isn't json module'}"

        if not self.is_valid():
            return json.dumps({'error':'og metadata is not valid'})
            
        return json.dumps(self)
        
    def to_xml(self):
        pass

    def scrape_image(self, doc):
        images = [dict(img.attrs).get('src', '') for img in doc.html.body.findAll('img') if dict(img.attrs).get('src', '')]

        if images:
            return images[0]

        return u''

    def scrape_title(self, doc):
        return doc.html.head.title.text

    def scrape_type(self, doc):
        return 'other'

    def scrape_url(self, doc):
        return self._url

    def scrape_description(self, doc):
        tag = doc.html.head.findAll('meta', attrs={"name":re.compile("description$", re.I)})
        result = "".join([t['content'] for t in tag])
        return result

    def run_extractor(self, func):
        return func(self.doc, self._url)
