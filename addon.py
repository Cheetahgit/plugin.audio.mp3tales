# coding=utf-8
##########################################################################
#
#  Copyright 2014 Lee Smith
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##########################################################################

import sys
import re
import urlparse
import itertools

from xbmcswift2 import Plugin
from bs4 import BeautifulSoup
import requests2 as requests

BASE_URL = "http://mp3tales.info"

ID_RE = re.compile("id=(\d+)$")
YEAR_RE = re.compile("(\d{4})")
COPY_YEAR_RE = re.compile(u"© +" + YEAR_RE.pattern)
MP3_RE = re.compile('file: "(.+\.mp3)"')

plugin = Plugin()

def get_soup(param, value):
    url = BASE_URL + "/tales/?{}={}".format(param, value)
    soup = BeautifulSoup(requests.get(url).text)
    return soup

def not_in_series(tag):
    if tag.find_parent('li', 'series'):
        return False
    else:
        return True

def get_page_numbers(soup):
    return (int(page.string.strip(u'\xa0')) for page in
            reversed(soup.find('legend').next_sibling(['a', 'b'])))

def get_mp3s(soup):
    for li in soup('li', 'item', not_in_series):
        title = li.a.string
        year = YEAR_RE.search(li.text)
        if year:
            year = int(year.group(1))

        item = {'label': title,
                'path': plugin.url_for('play',
                                       mp3_id=ID_RE.search(li.a['href']).group(1)),
                'is_playable': True,
                'info': {'year': year}
                }
        yield item
    
def get_series(soup, param, value):
    for i, series in enumerate(soup('li', 'series')):
        item = {'label': u"Серия: " + series.b.string,
                'path': plugin.url_for('series',
                                       param=param,
                                       value=value,
                                       series=i),
                'is_playable': False
                }
        yield item

def get_series_mp3s(soup, series):
    i = int(series)
    li = soup('li', 'series', limit=i + 1)[i]
    for item in get_mp3s(li):
        yield item

def get_page_links(soup, page=1):
    npages = get_page_numbers(soup).next()
    
    if page < npages:
        next_page = str(page + 1)
        item = {'label': u"{} ({}) >>".format(plugin.get_string(30004), next_page),
                'path': plugin.url_for('select_item', page=next_page)
                }
        yield item

    if page > 1:
        previous_page = str(page - 1)
        item = {'label': u"<< {} ({})".format(plugin.get_string(30005), previous_page),
                'path': plugin.url_for('select_item', page=previous_page)
                }
        yield item
        
    yield {'label': plugin.get_string(30003),
           'path': plugin.url_for('pages')}

def get_pages(soup):
    for page in get_page_numbers(soup):
        item = {'label': str(page),
                'path': plugin.url_for('select_item', page=str(page))    
                }
        yield item

def get_index():
    yield {'label': plugin.get_string(30001),
           'path': plugin.url_for('search')}

    yield {'label': plugin.get_string(30002),
           'path': plugin.url_for('select_item', page='1')}

    yield {'label': plugin.get_string(30003),
           'path': plugin.url_for('pages')}


@plugin.route('/')
def index():
    return get_index()

@plugin.route('/search')
def search():
    query = plugin.keyboard(heading=plugin.get_string(30001))
    if query:
        query = query.decode('utf-8').encode('cp1251')
        url = plugin.url_for('search_result', query=query)
        plugin.redirect(url)

@plugin.route('/search/<query>')
def search_result(query):
    param = 's'
    soup = get_soup(param, query)
    return itertools.chain(get_mp3s(soup),
                           get_series(soup, param, query))

@plugin.route('/pages')
def pages():
    soup = get_soup('p', 1)
    return get_pages(soup)

@plugin.route('/page/<page>')
def select_item(page):
    param = 'p'
    page = int(page)
    soup = get_soup(param, page)
    items = itertools.chain(get_page_links(soup, page),
                            get_mp3s(soup),
                            get_series(soup, param, page))
	
    if page > 1:
        update_listing = True
    else:
        update_listing = False

    return plugin.finish(items,
                         update_listing=update_listing,
                         sort_methods=['playlist_order', 'video_year'])

@plugin.route('/param/<param>/value/<value>/series/<series>')
def series(param, value, series):
    soup = get_soup(param, value)
    return get_series_mp3s(soup, series)

@plugin.route('/play/<mp3_id>')
def play(mp3_id):
    soup = get_soup('id', mp3_id)

    mp3_file = MP3_RE.search(soup.find(text=MP3_RE).string).group(1)
    url = urlparse.urljoin(BASE_URL, mp3_file)
    
    title = soup.find('h1').string
    icon = BASE_URL + soup.find('img', alt=title)['src']
    
    copy = soup.find(text=COPY_YEAR_RE)
    year = COPY_YEAR_RE.search(copy).group(1)

    item = {'path': url,
            'is_playable': True,
            'info': {'title': title,
                     'year': year,
                     'album': BASE_URL
                     },
            'icon': icon,
            'thumbnail': icon,
            'properties': {'mimetype': 'audio/mpeg'},
            'stream_info': {'audio': {'codec': 'mp3'}}
            }

    return plugin.set_resolved_url(item)

if __name__ == '__main__':
    plugin.run()

