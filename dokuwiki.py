import requests
import sys
import xml.etree.ElementTree as ET
import getpass
import argparse

class DokuWikiError(RuntimeError):
    def __init__(self, string, xml, response):
        if not string:
            string = ''
        if not xml:
            xml = ''
        if not response:
            response = ''

        self._error_string = (
            "DokuWiki error: {}. \nXML:\n{}\nHTTP Response {}:\n{}"
            .format(
                string,
                xml,
                response.status_code,
                response.text.encode('utf-8', errors='ignore')))

    def __str__(self):
        return self._error_string

class DokuWiki:
    '''
    A class representing a DokuWiki, using the XML RPC
    to communicate with it and do simple manipulations.
    https://en.wikipedia.org/wiki/XML-RPC
    https://www.dokuwiki.org/devel:xmlrpc
    '''
    XML_RPC=(u'''
    <?xml encoding="utf8" version="1.0"?>
    <methodCall>
      <methodName>{method_name}</methodName>
      <params>
        {parameters}
      </params>
    </methodCall>''')

    RPC_PATH="/lib/exe/xmlrpc.php"

    def __get_parsed_response(self, method, params, retrieve_path):
        params_str = ''
        # technically, there are other types of parameters defined in the
        # XML-RPC. I don't use any so I don't check.

        for param in params:
            # CDATA tag means 'character data' and is very much necessary
            # for the frequent case of embedded HTML markup.
            params_str += "<param><string><![CDATA[{}]]></string></param>".format(param)

        data_str = DokuWiki.XML_RPC.format(method_name=method,
                                           parameters=params_str)

        response = requests.put(self.url + DokuWiki.RPC_PATH,
                                data=data_str.encode('utf8', errors='ignore'),
                                cookies=self.cookies)

        if not (response.status_code >= 200 and
                response.status_code <= 299):
            raise DokuWikiError("response code was not OK.",
                                data_str,
                                response)

        return_val = None

        try:
            # XML should be able to use UTF-8. However,
            # the dokuwiki doesn't send an 'encoding' parameter in it's
            # xml header or whatever it is. ElemTree is confused
            # by utf8 chars and throws an error.
            parsed_response = ET.fromstring(
                    response.text.encode('utf-8', errors='ignore'))
            return_val = parsed_response.findall(retrieve_path)[0].text
        except Exception as e:
            raise DokuWikiError(
                "caught {}".format(e),
                data_str,
                response)

        return return_val, response

    def __init__(self, url):
        self.url=url
        self.version = None
        self.cookies = requests.cookies.RequestsCookieJar()
        self.version = self.__get_parsed_response(
                            'dokuwiki.getVersion',
                            [],
                            './params/param/value/string')

    def get_page(self, pagename):
        return self.__get_parsed_response(
                'wiki.getPage',
                [pagename],
                './params/param/value/string')[0]

    def put_page(self, pagename, pagetext):
        return bool(int(self.__get_parsed_response(
                        'wiki.putPage',
                        [pagename, pagetext],
                        './params/param/value/boolean')[0]))

    def login(self, username, password):
        value, response = self.__get_parsed_response(
                            'dokuwiki.login',
                            [username, password],
                            './params/param/value/boolean')
        self.cookies.update(response.cookies)
        return bool(int(value))

'''
Demo program for fetching dokuwiki stuff using XML RPC
'''

def main(url, 
        page,
        action, 
        nologin, 
        input_file, 
        output_file):

    wiki = DokuWiki(url)
    

    if not nologin:
        username = raw_input('username > ')
        password = getpass.getpass('password > ')
        if not wiki.login(username, password):
            print("could not log in")
            raise SystemExit(1)
        else:
            print("logged in OK.")

    #print(wiki.version)

    if action == 'get':
        output_file.write(wiki.get_page(page))
    elif action == 'put':
        wikitext=''
        for line in iter(input_file.readline, ''):
            wikitext += line
        wiki.put_page(page, wikitext)
    else:
        print('undefined action')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process dokuwiki arguments")
    parser.add_argument('--nologin',
                        dest='nologin',
                        action='store_true',
                        default=False)
    parser.add_argument('url', nargs=1)
    parser.add_argument('page', nargs=1)
    parser.add_argument('action', nargs=1)
    parser.add_argument('output_file', nargs='?', default='')
    parser.add_argument('input_file', nargs='?', default='')
    params = parser.parse_args(sys.argv[1:])

    i = None
    if params.input_file == '':
        i = sys.stdin
    else:
        i = open(params.input_file, 'r')

    o = None
    if params.output_file == '':
        o = sys.stdout
    else:
        o = open(params.output_file, 'w')

    with o as out, i as inp:
        main(url=params.url[0],
             page=params.page[0],
             action=params.action[0],
             nologin=params.nologin,
             input_file=inp,
             output_file=out)

