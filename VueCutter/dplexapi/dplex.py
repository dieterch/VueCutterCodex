import concurrent.futures
import subprocess
import itertools
import json
import os
import time

#import plexapi
from plexapi.client import PlexClient, ClientTimeline, DEFAULT_MTYPE
from plexapi.server import PlexServer
from plexapi import (BASE_HEADERS, CONFIG, TIMEOUT, X_PLEX_CONTAINER_SIZE, log, logfilter, utils)
from requests.status_codes import _codes as codes
from plexapi.exceptions import BadRequest, NotFound, Unauthorized, Unsupported
from xml.etree import ElementTree


class MyPlexClient(PlexClient):

    def query(self, path, method=None, headers=None, timeout=None, **kwargs):
        """ Main method used to handle HTTPS requests to the Plex client. This method helps
            by encoding the response to utf-8 and parsing the returned XML into and
            ElementTree object. Returns None if no data exists in the response.
        """
        url = self.url(path)
        method = method or self._session.get
        timeout = timeout or TIMEOUT
        log.debug('%s %s', method.__name__.upper(), url)
        headers = self._headers(**headers or {})
        response = method(url, headers=headers, timeout=timeout, **kwargs)
        if response.status_code not in (200, 201, 204):
            codename = codes.get(response.status_code)[0]
            errtext = response.text.replace('\n', ' ')
            message = '(%s) %s; %s %s' % (response.status_code, codename, response.url, errtext)
            if response.status_code == 401:
                raise Unauthorized(message)
            elif response.status_code == 404:
                raise NotFound(message)
            else:
                raise BadRequest(message)
        data = response.text.encode('utf8')
        return ElementTree.fromstring(data) if data.strip() else None

    def sendCommand(self, command, proxy=None, timeout=None, **params):
        """ Convenience wrapper around :func:`~plexapi.client.PlexClient.query` to more easily
            send simple commands to the client. Returns an ElementTree object containing
            the response.

            Parameters:
                command (str): Command to be sent in for format '<controller>/<command>'.
                proxy (bool): Set True to proxy this command through the PlexServer.
                **params (dict): Additional GET parameters to include with the command.

            Raises:
                :exc:`~plexapi.exceptions.Unsupported`: When we detect the client doesn't support this capability.
        """
        command = command.strip('/')
        controller = command.split('/')[0]
        headers = {'X-Plex-Target-Client-Identifier': self.machineIdentifier}
        if controller not in self.protocolCapabilities:
            log.debug('Client %s doesnt support %s controller.'
                      'What your trying might not work' % (self.title, controller))

        # proxy = self._proxyThroughServer if proxy is None else proxy
        # query = self._server.query if proxy else self.query

        # Workaround for ptp. See https://github.com/pkkid/python-plexapi/issues/244
        t = time.time()
        if command == 'timeline/poll':
            self._last_call = t
        elif t - self._last_call >= 80 and self.product in ('ptp', 'Plex Media Player'):
            self._last_call = t
            self.sendCommand(ClientTimeline.key, wait=0)

        params['commandID'] = self._nextCommandId()
        key = '/player/%s%s' % (command, utils.joinArgs(params))

        try:
            return self.query(key, headers=headers, timeout=timeout)
        except ElementTree.ParseError:
            # Workaround for players which don't return , valid XML on successful commands
            #   - Plexamp, Plex for Android: `b'OK'`
            #   - Plex for Samsung: `b'<?xml version="1.0"?><Response code="200" status="OK">'`
            if self.product in (
                'Plexamp',
                'Plex for Android (TV)',
                'Plex for Android (Mobile)',
                'Plex for Samsung',
            ):
                return
            raise

    def seekTo(self, offset, mtype=DEFAULT_MTYPE, timeout=None):
        """ Seek to the specified offset (ms) during playback.

            Parameters:
                offset (int): Position to seek to (milliseconds).
                mtype (str): Media type to take action against (music, photo, video).
        """
        self.sendCommand('playback/seekTo', offset=offset, type=mtype, timeout=timeout)

class MyPlexServer(PlexServer):

    def clients(self):
        """ Returns list of all :class:`~plexapi.client.PlexClient` objects connected to server. """
        items = []
        ports = None
        for elem in self.query('/clients'):
            port = elem.attrib.get('port')
            if not port:
                log.warning('%s did not advertise a port, checking plex.tv.', elem.attrib.get('name'))
                ports = self._myPlexClientPorts() if ports is None else ports
                port = ports.get(elem.attrib.get('machineIdentifier'))
            baseurl = 'http://%s:%s' % (elem.attrib['host'], port)
            items.append(MyPlexClient(baseurl=baseurl, server=self,
                                    token=self._token, data=elem, connect=False))

        return items

class PlexInterface:

    class MovieData():
        def __init__(self, movie):
            self.title = movie.title
            self.locations = movie.locations 
            self.duration = movie.duration
            self.summary = movie.summary

        def __iter__(self):
            yield from {
                "title": self.title,
                "locations": self.locations,
                "duration": self.duration,
                "summary": self.summary
            }.items()

        def __str__(self):
            return json.dumps(dict(self), ensure_ascii=False)

        def __repr__(self):
            return self.__str__()
            
        def to_json(self):
            return json.dumps(self.__dict__)

    def __init__(self, url, token):
        self._url = url
        self._token = token
        self._plex = MyPlexServer(self._url, self._token)
        self._sectioncache = {}

    @property
    def clients(self):
        return self._plex.clients()

    @property
    def server(self):
        return self._plex

    def client(self,clientname):
        return self._plex.client(clientname)

    def min_to_ms(self, min):
        return min * 60000

    def ms_to_min(self, ms):
        return ms // 60000

    @property
    def sections(self):
        return self._plex.library.sections()

    def loadsections(self, secs):
        for sec in secs:
            self.content(sec.title)

    def loadallsections(self):
        self.loadsections(self.sections)

    def content(self, section, cache=False):
        #t0 = time.time()
        if section in self._sectioncache and cache:
            pass
        else:
            self._sectioncache[section] = {
                'title' : section,
                'data'  : [v for v in self._plex.library.section(section).all()]
            }
        #t1 = time.time()
        #print(f"delta t={t1-t0}")
        return self._sectioncache[section]['data']

    def set_key(self, key=None, reverse=None):
        if (key != None and reverse != None):
            self._key = key
            self._reverse = reverse

    def sorted_content(self, section):
        content = self.content(section)
        if (self._key != None and self._reverse != None):
            content = sorted(content, key=lambda x: getattr(x,self._key) , reverse=self._reverse)
        return content

    @classmethod
    def movie_rec(cls, movie):
        return {
            'title': movie.title, 
            'locations': movie.locations, 
            'summary':movie.summary, 
            'addedAt': movie.addedAt, 
            'duration_ms': movie.duration,
            'duration':movie.duration // 60000,
            'duration_sec_rest': (movie.duration % 60000) // 1000, 
            'year':movie.year,
            'guid':movie.guid.split('/')[-1],
            'streamURL':movie.getStreamURL()
        }

    def double_movies(self):

        def _doubles(mvs, k):
            doubles = []
            #print(f"\ncomparing '{k[0]}' and '{k[1]}' :")
            for m in mvs[k[0]]['data'][:]:
                for n in mvs[k[1]]['data'][:]:
                    if (n.title.strip().lower() == m.title.strip().lower()):
                        #print(f"{k[0]:<20}: {n.title.strip() +' | '+str(n.year)+' | '+str(n.duration // 60000)+' min':<50} \n" + 
                        #      f"{k[1]:<20}: {m.title.strip() +' | '+str(m.year)+' | '+str(n.duration // 60000)+' min':<50} \n")
                        rec = {n.title.strip().lower():k}
                        doubles.append(rec)
            return doubles

        mov_secs = [s for s in self.sections 
            if (s.type == 'movie' and s.title != 'Andere Videos')]
        self.loadsections(mov_secs)
        
        #filtere Filme, die als nicht doppelrt gekennzeichnet wurden 
        with open(os.path.dirname(__file__) + '/data/keep.json') as file:
            keep = json.load(file)['keep']
        mvs = self._sectioncache    
        for sec in mvs:
            mvs[sec]['data'] = [v for v in mvs[sec]['data'] if v.title not in keep] 
        
        t = mvs.keys()
        combinations = list(itertools.combinations(t, 2))

        doubles = []
        for k in combinations:
            doubles += _doubles(mvs,k)
        return doubles

    def print_doubles(self):
        t0 = time.time()
        erg = self.double_movies()
        for i, rec in enumerate(erg):
            for k in rec:
                s1, s2 = rec[k]
                print(f"{(i+1):3d}  {k:<50}{s1:>15}, {s2:<15}")
        t1 = time.time()
        print("---")
        print(f"{t1-t0:0.1f} sec")
