from dplexapi.dcut import CutterInterface
from dplexapi.dplex import PlexInterface
import tomllib
from io import BytesIO
from jinja2 import Template
import os, time, subprocess
import pytz
from redis import Redis
from rq import Connection, Queue, Worker
from rq.job import Job
import requests


xspf_template = """<?xml version="1.0" encoding="UTF-8"?>
<playlist xmlns="http://xspf.org/ns/0/" xmlns:vlc="http://www.videolan.org/vlc/playlist/ns/0/" version="1">
	<title>Wiedergabeliste</title>
	<trackList>{% for item in data %}
		<track>
            <title>{{ item['title'] }}</title>
			<location>{{ item['url'] }}</location>
			<duration>{{ item['dur'] }}</duration>
			<extension application="http://www.videolan.org/vlc/playlist/0">
				<vlc:id>{{ item['i'] }}</vlc:id>
			</extension>
		</track>{% endfor %}
	</trackList>
	<extension application="http://www.videolan.org/vlc/playlist/0">
		<vlc:item tid="0"/>
	</extension>
</playlist>"""

class Plexdata:
    def __init__(self, basedir) -> None:
        self.basedir = basedir
        self.initialize()

    def initialize(self):
        config_path = os.getenv('PLEXDATA_CONFIG', 'config.toml')
        with open(config_path, mode="rb") as fp:
            self.cfg = tomllib.load(fp)
        env_overrides = {
            'fileserver': os.getenv('VUECUTTER_FILESERVER'),
            'fileservermac': os.getenv('VUECUTTER_FILESERVER_MAC'),
            'plexurl': os.getenv('VUECUTTER_PLEX_URL'),
            'plextoken': os.getenv('VUECUTTER_PLEX_TOKEN'),
            'redispw': os.getenv('VUECUTTER_REDIS_PASSWORD'),
            'wolurl': os.getenv('VUECUTTER_WOL_URL'),
        }
        for key, value in env_overrides.items():
            if value:
                self.cfg[key] = value
        if self.hostalive():
            try:
                self.plex = PlexInterface(self.cfg["plexurl"],self.cfg["plextoken"])
                self.cutter = CutterInterface(self.cfg["fileserver"])
                self.initial_section = self.plex.sections[0]
                self.initial_movie_key = 0
                self.initial_movie = self.initial_section.recentlyAdded()[self.initial_movie_key]
                self._selection = { 
                    'section_type': self.initial_section.type,
                    'sections' : [s for s in self.plex.sections if ((s.type == 'movie') or (s.type == 'show'))],
                    'section' : self.initial_section,
                    'seasons' : None,
                    'season' : None,
                    'series' : None,
                    'serie' : None,
                    'movies' : self.initial_section.recentlyAdded(),
                    'movie' : self.initial_movie,
                    'pos_time' : '00:00:00'
                    }
                
                redis_host = os.getenv('REDIS_HOST', 'redis' if os.getenv('IN_DOCKER') == 'true' else 'localhost')
                redis_port = int(os.getenv('REDIS_PORT', '6379'))
                redis_password = os.getenv('REDIS_PASSWORD', self.cfg.get('redispw', ''))
                redis_kwargs = {
                    'host': redis_host,
                    'port': redis_port,
                    'db': 0,
                }
                if redis_password:
                    redis_kwargs['password'] = redis_password
                print(f"Redis connection target: {redis_host}:{redis_port}")
                self.redis_connection = Redis(**redis_kwargs)
                self.q = Queue('VueCutter', connection=self.redis_connection, default_timeout=600)
                # initialization.
                self.initial_series_key = 0
                self.initial_season_key = 0
            except ConnectionError as e:
                self.initial_movie = ''
                self._selection = {} 
                self.initial_section = ''
                print(f"ConnectionError: {e}")
                raise e

        else:
            self.plex = None
            self.cutter = None
            self.initial_movie = ''
            self._selection = { }
            self.initial_section = ''

    def hostalive(self) -> bool:
        try:
            conn = requests.head(self.cfg['plexurl'], timeout=2)
            if str(conn) == '<Response [401]>':
                conn.close()
                return True
            else:
                return False
        except requests.exceptions.RequestException as e:
            print(str(e))
            return False
        
    def wolserver(self):
        try:
            wolurl = self.cfg['wolurl']
            r = requests.get(wolurl, timeout=30),
            #r.raise_for_status()
            return r
        except requests.exceptions.HTTPError as err:
            raise SystemExit(err)
        
    @property
    def section_title(self):
        if self.plex is not None:
            return self._selection['section'].title
        else:
            return ''

    async def streamsectionall(self):
        if self.plex is not None:
            sec = self._selection['section']
            mov = sec.all()
            data = []
            for i,m in enumerate(mov):
                data.append({'i':i, 'title':m.title.replace('&','&amp;'), 'url': m.getStreamURL().replace('&','&amp;'), 'dur': m.duration})
            j2_template = Template(xspf_template)
            w = j2_template.render(data=data)    
            b = BytesIO(w.encode('utf-8','xmlcharrefreplace'))
            b.seek(0)
            return b
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')

    async def streamsection(self):
        if self.plex is not None:
            movies = self._selection['movies']
            data = []
            for i,m in enumerate(movies):
                data.append({'i':i, 'title':m.title.replace('&','&amp;'), 'url': m.getStreamURL().replace('&','&amp;'), 'dur': m.duration})
            j2_template = Template(xspf_template)
            w = j2_template.render(data=data)    
            b = BytesIO(w.encode('utf-8','xmlcharrefreplace'))
            b.seek(0)
            return b
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
    
    async def streamurl(self):
        if self.plex is not None:
            m = self._selection['movie']
            data = [{'i':0, 'title':m.title.replace('&','&amp;'), 'url': m.getStreamURL().replace('&','&amp;'), 'dur': m.duration}]
            j2_template = Template(xspf_template)
            w = j2_template.render(data=data)    
            b = BytesIO(w.encode('utf-8','xmlcharrefreplace'))
            b.seek(0)
            return b
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
    
    def get_selection(self):
        if self.plex is not None:
            ret = {
                    'sections': [s.title for s in self._selection['sections']], 
                    'section': self._selection['section'].title,
                }
            if self._selection['section'].type == "movie": #movie sections
                ret.update({ 
                    'section_type': 'movie',
                    'movies': [m.title for m in self._selection['movies']], 
                    'movie': self._selection['movie'].title,
                    'pos_time' : self._selection['pos_time']    
                })
            elif self._selection['section'].type == "show": #series section
                ret.update({
                    'section_type': 'show',
                    'series':[s.title for s in self._selection['series']],
                    'serie': self._selection['serie'].title,
                    'seasons': [season.title for season in self._selection['serie'].seasons()] if self._selection['section'].type == 'show' else [],
                    'season': self._selection['season'].title,
                    'movies': [e.title for e in self._selection['season']], 
                    'movie': self._selection['movie'].title,
                    'pos_time' : self._selection['pos_time']   
                })
            else:
                raise ValueError('Unknown section type')
            return ret
        else:
            self.initialize()
            return {
                    'sections': [s.title for s in self._selection['sections']], 
                    'section': self._selection['section'].title,
                }
    
    async def _update_section(self, section_name, force=False):
        if self.plex is not None:
            if ((self._selection['section'].title != section_name) or force):
                if force:
                    self.initialize()
                section = self.plex.server.library.section(section_name)
                if section.type == 'movie':
                    movies = section.recentlyAdded()
                    default_movie = movies[self.initial_movie_key]
                    self._selection.update({ 
                        'section_type': 'movie',
                        'section' : section,
                        'series' : None,
                        'serie' : None, 
                        'seasons' : None,
                        'season' : None,
                        'movies' : movies, 
                        'movie' : default_movie 
                    })
                elif section.type == 'show':
                    series = section.all()
                    serie = series[self.initial_series_key]
                    seasons = serie.seasons()
                    season = seasons[self.initial_season_key]
                    movies = season.episodes()
                    default_movie = movies[self.initial_movie_key]
                    self._selection.update({ 
                        'section_type': 'show',
                        'section' : section,
                        'series' : series,
                        'serie' : serie, 
                        'seasons' : seasons,
                        'season' : season,
                        'movies' : movies, 
                        'movie' : default_movie 
                    })
                else:
                    raise ValueError('Unknown Plex section type.')           
            else:
                pass # no change in section
            return self._selection['section']  
        else:
            self.initialize()
    
    async def _update_serie(self, serie_name, force=False):
        if self.plex is not None:
            if ((self._selection['serie'].title != serie_name) or force): 
                print('*********** new',serie_name)
                section = self._selection['section']
                serie = [s for s in section.all() if s.title == serie_name][0]
                seasons = serie.seasons()
                season = seasons[self.initial_season_key]
                movies = season.episodes()
                default_movie = movies[self.initial_movie_key]
                self._selection.update({ 
                    'serie': serie, 
                    'seasons' : seasons,
                    'season': season, 
                    'movies' : movies, 
                    'movie' : default_movie 
                })
            else:
                pass
            return self._selection['serie']
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
    
    async def _update_season(self, season_name, force=False):
        if self.plex is not None:
            if ((self._selection['season'].title != season_name) or force): 
                print('*********** new',season_name)
                serie = self._selection['serie']
                season = serie.season(season_name)
                movies = season.episodes()
                default_movie = movies[self.initial_movie_key]
                self._selection.update({ 'season' : season, 'movies' : movies, 'movie' : default_movie })
            else:
                pass
            return self._selection['season']
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
    
    async def _update_movie(self, movie_name):
        if self.plex is not None:
            sel_movie = self._selection['movies'][self.initial_movie_key]
            if movie_name != '':
                lmovie = [m for m in self._selection['movies'] if m.title == movie_name]
                if lmovie:
                    sel_movie = lmovie[0]
            self._selection['movie'] = sel_movie
            return self._selection['movie']
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
    
    async def _timeline(self, req):
        t0 = time.time()
        #------------------------------
        basename = str(req['basename']); 
        pos = int(req['pos']); 
        l = int(req['l']); 
        r = int(req['r']); 
        step = int(req['step']); 
        size = req['size']
        m = self._selection['movie']
        self.cutter.ensure_media(m)
        target = self.basedir + "/dist/static/"+ basename
        tl = self.cutter.gen_timeline(m.duration // 1000, pos, l, r, step)
        r = self.cutter.timeline(m, target , size, tl)
        #------------------------------
        t1 = time.time()
        print(f"total:{(t1-t0):5.2f}")
        #------------------------------
        return r
    
    async def _movie_info(self, req):
        if self.plex is not None:
            if req is not None:
                section_name = req['section']
                movie_name = req['movie']
                if movie_name != '':
                    s = await self._update_section(section_name)
                    m = await self._update_movie(movie_name)
                    m_info = { 'movie_info': self.plex.movie_rec(m) }
                else:
                    if section_name == '':
                        s = await self._update_section('Plex Recordings')
                    m = await self._update_movie('')
                    m_info = { 'movie_info': self.plex.movie_rec(m) }
            else:
                m_info = { 'movie_info': { 'duration': 0 } }
            return m_info
        else:
            return { 'movie_info': { 'duration': 0 } }
    
    async def _movie_cut_info(self):
        if self.plex is not None:
            m = self._selection['movie']
            self.cutter.ensure_media(m)
            dmin = m.duration / 60000
            apsc = self.cutter._apsc(m)
            cutfile = self.cutter._cutfile(m)
            eta_apsc = int((0.5 if not apsc else 0) * dmin)
            eta_cut =  int(0.9 * dmin)
            eta = eta_apsc + eta_cut
            self._selection['eta'] = eta
            return { 'movie': m.title, 'eta': eta, 'eta_cut': eta_cut, 'eta_apsc': eta_apsc, 'cutfile': cutfile, 'apsc' : apsc }
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
    
    async def _frame(self, req):
        if not self.hostalive():
            self.initialize()
        if self.plex is not None:
            if req is not None:
                movie_name = req['movie_name']
                pos_time = req['pos_time']
                try:
                    m = await self._update_movie(movie_name)
                    self.cutter.ensure_media(m)
                    pic_name = await self.cutter.aframe(m ,pos_time ,self.basedir + "/dist/static/")
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(f"\nframe throws error:\n{str(e)}\n")             
                    raise e
            else:
                raise ValueError('Missing frame request data')
            return pic_name
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
    
    async def _cut2(self, req):
        if self.plex is not None:
            section_name = req['section']
            movie_name = req['movie_name']
            cutlist = req['cutlist']
            inplace = req['inplace']
            s = await self._update_section(section_name)
            m = await self._update_movie(movie_name)
            self.cutter.ensure_media(m)
            res = f"Queue Cut From section '{s}', cut '{m.title}', cutlist{cutlist}, inplace={inplace}, engine=ffmpeg"
            try:
                mm = self.plex.MovieData(m)
                print("will cut now:\n",res)
                job = self.q.enqueue_call(self.cutter.cut, args=(mm,cutlist,inplace))
                res = {
                    'Section': s.title,
                    'Duration Raw': mm.duration // 60000,
                    'Duration Cut': sum([self.cutter.cutlength(cut['t0'],cut['t1']) for cut in cutlist]),
                    'Cutlist': cutlist,
                    'Inplace': inplace,
                    'Engine': 'ffmpeg',
                    '.ap .sc Files': self.cutter._apsc(m),
                    'cut File': self.cutter._cutfile(m)
                }
                return { 'result': res}
            except subprocess.CalledProcessError as e:
                print(str(e))
                return { 'result': str(e) }
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
        
    async def _doProgress(self):
        if self.plex is not None:
            mstatus = {
                'title': '-',
                'cut_progress': 0,
                'apsc_progress': 0,
                'started': 0,
                'status': 'idle'
            } 
            workers = Worker.all(connection=self.redis_connection)
            worker = workers[0] if len(workers) > 0 else None
            if worker:
                lhb = pytz.utc.localize(worker.last_heartbeat)
                lhbtz = lhb.astimezone(pytz.timezone("Europe/Vienna"))
                w = {
                    'name': worker.name,
                    'state': worker.state,
                    'last_heartbeat': lhbtz.strftime("%H:%M:%S"),
                    'current_job_id': worker.get_current_job_id(),
                    'failed': worker.failed_job_count
                } 
            else:
                w = {
                    'status':'no worker detected'
                }
            qd = {
                'started':self.q.started_job_registry.count,
                'finished':self.q.finished_job_registry.count,
                'failed':self.q.failed_job_registry.count,
            }
            if self.q.started_job_registry.count > 0:
                qd['started_jobs'] = []
                for job_id in self.q.started_job_registry.get_job_ids():
                    job = Job.fetch(job_id, connection=self.redis_connection)
                    m = self.plex.MovieData(job.args[0])
                    prog = self.cutter._movie_stats(*job.args)
                    apsc_prog = self.cutter._apsc_stats(*job.args)
                    #apsc_size = plexdata.cutter._apsc_size(m)
                    d = {
                        'title': m.title,
                        'ss':job.args[1],
                        'to':job.args[2],
                        'name': job_id,
                        'status':job.get_status(refresh=True),
                        'cut_progress':prog,
                        'apsc_progress':apsc_prog
                    }
                    qd['started_jobs'].append(d)
                    mstatus.update({
                        'title': m.title,
                        #'apsc_size': apsc_size,
                        'cut_progress': prog,
                        'apsc_progress':apsc_prog,
                        'started': self.q.started_job_registry.count,
                        'status': d['status']           
                    })

            if self.q.finished_job_registry.count > 0:
                qd['finished_jobs'] = []
                for job_id in self.q.finished_job_registry.get_job_ids():
                    job = Job.fetch(job_id, connection=self.redis_connection)
                    d = {
                        'name': job_id,
                        'result': job.result
                    }
                    qd['finished_jobs'].append(d) 

            return mstatus
        else:
            raise ValueError(f'Plex Server {self.cfg["fileserver"]} not available')
