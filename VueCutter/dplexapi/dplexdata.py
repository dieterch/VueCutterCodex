from dplexapi.dcut import CutterInterface
from dplexapi.dplex import PlexInterface
import tomllib
from io import BytesIO
from jinja2 import Template
import os
import time
import subprocess
import pytz
from rq import Queue, Worker
from rq.job import Job
from redis import Redis
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
        self.initial_movie_key = 0
        self.initial_series_key = 0
        self.initial_season_key = 0
        self._processed_finished_cut_jobs = set()
        self._post_cut_refresh = {}
        self._active_server_id = None
        self._servers = {}
        self.initialize()

    def initialize(self):
        config_path = os.getenv('PLEXDATA_CONFIG', 'config.toml')
        with open(config_path, mode='rb') as fp:
            self.cfg = tomllib.load(fp)

        redis_host = os.getenv('REDIS_HOST', 'redis' if os.getenv('IN_DOCKER') == 'true' else 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_password = os.getenv('REDIS_PASSWORD', os.getenv('VUECUTTER_REDIS_PASSWORD', self.cfg.get('redispw', '')))
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
        self.analysis_timeout = int(os.getenv('VUECUTTER_ANALYSIS_TIMEOUT', '7200'))

        previous_servers = self._servers
        previous_active = self._active_server_id
        self._servers = {}
        for server_cfg in self._load_server_configs():
            previous = previous_servers.get(server_cfg['id'], {})
            prev_cutter = previous.get('cutter')
            if prev_cutter and previous.get('config', {}).get('media_root') == server_cfg.get('media_root'):
                cutter = prev_cutter
            else:
                cutter = CutterInterface(server_cfg['fileserver'], server_cfg.get('media_root', ''))
            self._servers[server_cfg['id']] = {
                'config': server_cfg,
                'plex': previous.get('plex'),
                'cutter': cutter,
                'selection': previous.get('selection'),
                'status': previous.get('status', 'offline'),
                'reason': previous.get('reason', ''),
            }

        self.refresh_server_statuses(eager=False)
        self._active_server_id = self._pick_active_server(previous_active)

    def _load_server_configs(self):
        configs = []
        primary = self._build_server_config('')
        if primary:
            configs.append(primary)
        secondary = self._build_server_config('_2')
        if secondary:
            configs.append(secondary)
        if not configs:
            raise ValueError('No Plex server configured.')
        return configs

    def _build_server_config(self, suffix):
        if suffix == '':
            server_id = 'plex1'
            default_name = 'Plex 1'
            fallback = {
                'url': self.cfg.get('plexurl', ''),
                'token': self.cfg.get('plextoken', ''),
                'fileserver': self.cfg.get('fileserver', ''),
                'fileservermac': self.cfg.get('fileservermac', ''),
                'wolurl': self.cfg.get('wolurl', ''),
            }
        else:
            server_id = 'plex2'
            default_name = 'Plex 2'
            fallback = {
                'url': '',
                'token': '',
                'fileserver': '',
                'fileservermac': '',
                'wolurl': '',
            }

        url = (os.getenv(f'VUECUTTER_PLEX_URL{suffix}', fallback['url']) or '').strip()
        token = (os.getenv(f'VUECUTTER_PLEX_TOKEN{suffix}', fallback['token']) or '').strip()
        fileserver = (os.getenv(f'VUECUTTER_FILESERVER{suffix}', fallback['fileserver']) or '').strip()
        media_root = (os.getenv(f'VUECUTTER_MEDIA_ROOT{suffix}', '') or '').strip()
        if not (url and token and fileserver):
            return None

        return {
            'id': server_id,
            'name': (os.getenv(f'VUECUTTER_PLEX_NAME{suffix}', '') or '').strip() or default_name,
            'url': url,
            'token': token,
            'fileserver': fileserver,
            'fileservermac': (os.getenv(f'VUECUTTER_FILESERVER_MAC{suffix}', fallback['fileservermac']) or '').strip(),
            'wolurl': (os.getenv(f'VUECUTTER_WOL_URL{suffix}', fallback['wolurl']) or '').strip(),
            'media_root': media_root,
        }

    def _pick_active_server(self, preferred_server_id=None):
        if preferred_server_id in self._servers:
            return preferred_server_id
        for server_id, ctx in self._servers.items():
            if ctx['status'] == 'online':
                return server_id
        return next(iter(self._servers.keys()), None)

    def _probe_server(self, server_id):
        ctx = self._servers[server_id]
        headers = {
            'X-Plex-Token': ctx['config']['token'],
        }
        attempts = (
            ('HEAD', ctx['config']['url']),
            ('GET', ctx['config']['url']),
            ('GET', f"{ctx['config']['url'].rstrip('/')}/identity"),
        )
        last_reason = ''
        for method, url in attempts:
            try:
                response = requests.request(method, url, headers=headers, timeout=3, allow_redirects=True)
                status_code = getattr(response, 'status_code', None)
                response.close()
                if status_code is not None and status_code < 500:
                    return 'online', ''
                last_reason = f'{method} {url} -> HTTP {status_code}'
            except requests.exceptions.RequestException as exc:
                last_reason = str(exc) or f'{method} {url} failed'
        return 'offline', last_reason or 'connection failed'

    def _initialize_server_selection(self, server_id, force=False):
        ctx = self._servers[server_id]
        if ctx['status'] != 'online':
            raise RuntimeError(self._server_unavailable_message(server_id))
        if not force and ctx['plex'] is not None and ctx['selection'] is not None:
            return ctx
        try:
            plex = PlexInterface(ctx['config']['url'], ctx['config']['token'])
            sections = [section for section in plex.sections if section.type in ('movie', 'show')]
            if not sections:
                raise ValueError(f"No supported Plex sections found on '{ctx['config']['name']}'.")
            initial_section = sections[0]
            selection = self._build_selection_from_section(initial_section)
            ctx['plex'] = plex
            ctx['selection'] = selection
            ctx['reason'] = ''
            return ctx
        except Exception as exc:
            ctx['plex'] = None
            ctx['selection'] = None
            ctx['status'] = 'offline'
            ctx['reason'] = str(exc)
            raise RuntimeError(self._server_unavailable_message(server_id))

    def refresh_server_statuses(self, eager=False):
        for server_id, ctx in self._servers.items():
            status, reason = self._probe_server(server_id)
            ctx['status'] = status
            ctx['reason'] = reason
            if status == 'online':
                if eager and (ctx['plex'] is None or ctx['selection'] is None):
                    try:
                        self._initialize_server_selection(server_id, force=ctx['selection'] is None)
                    except RuntimeError:
                        pass
            else:
                ctx['plex'] = None
                ctx['selection'] = None

    def server_statuses(self):
        self.refresh_server_statuses(eager=False)
        return [self._server_summary(server_id) for server_id in self._servers]

    def hostalive(self) -> bool:
        self.refresh_server_statuses(eager=False)
        return any(ctx['status'] == 'online' for ctx in self._servers.values())

    def _server_summary(self, server_id):
        ctx = self._servers[server_id]
        reason = ctx['reason'].strip() if ctx['reason'] else ''
        mount_method = 'host' if ctx['config'].get('media_root') else 'smb'
        return {
            'id': server_id,
            'name': ctx['config']['name'],
            'url': ctx['config']['url'],
            'status': ctx['status'],
            'reason': reason,
            'selectable': ctx['status'] == 'online',
            'mount_method': mount_method,
            'media_root': ctx['config'].get('media_root', ''),
        }

    def _server_unavailable_message(self, server_id):
        ctx = self._servers.get(server_id)
        if ctx is None:
            return 'Plex server unavailable: unknown server.'
        reason = ctx['reason'].strip() if ctx['reason'] else 'server is offline or sleeping'
        return f"Plex server unavailable: {ctx['config']['name']} ({ctx['config']['url']}) - {reason}."

    def _blank_selection_payload(self):
        return {
            'sections': [],
            'section': '',
            'section_type': '',
            'series': [],
            'serie': '',
            'seasons': [],
            'season': '',
            'movies': [],
            'movie': '',
            'pos_time': '00:00:00',
        }

    def _build_selection_from_section(self, section):
        selection = {
            'section_type': section.type,
            'sections': [s for s in section._server.library.sections() if s.type in ('movie', 'show')],
            'section': section,
            'seasons': None,
            'season': None,
            'series': None,
            'serie': None,
            'movies': [],
            'movie': None,
            'pos_time': '00:00:00',
        }
        if section.type == 'movie':
            movies = section.recentlyAdded()
            selection['movies'] = movies
            selection['movie'] = movies[self.initial_movie_key] if movies else None
        elif section.type == 'show':
            series = section.all()
            selection['series'] = series
            if series:
                serie = series[self.initial_series_key]
                seasons = serie.seasons()
                season = seasons[self.initial_season_key] if seasons else None
                movies = season.episodes() if season is not None else []
                selection.update({
                    'serie': serie,
                    'seasons': seasons,
                    'season': season,
                    'movies': movies,
                    'movie': movies[self.initial_movie_key] if movies else None,
                })
            else:
                selection.update({
                    'series': [],
                    'seasons': [],
                    'movies': [],
                })
        else:
            raise ValueError('Unknown Plex section type.')
        return selection

    def _selection_payload(self, server_id):
        base = {
            'server': server_id,
            'servers': [self._server_summary(key) for key in self._servers],
        }
        ctx = self._servers.get(server_id)
        if ctx is None or ctx['status'] != 'online' or ctx['selection'] is None:
            return {
                **base,
                **self._blank_selection_payload(),
            }

        selection = ctx['selection']
        ret = {
            **base,
            'sections': [section.title for section in selection['sections']],
            'section': selection['section'].title,
            'pos_time': selection['pos_time'],
        }
        if selection['section'].type == 'movie':
            ret.update({
                'section_type': 'movie',
                'movies': [movie.title for movie in selection['movies']],
                'movie': selection['movie'].title if selection['movie'] is not None else '',
            })
        elif selection['section'].type == 'show':
            ret.update({
                'section_type': 'show',
                'series': [serie.title for serie in selection['series'] or []],
                'serie': selection['serie'].title if selection['serie'] is not None else '',
                'seasons': [season.title for season in selection['seasons'] or []],
                'season': selection['season'].title if selection['season'] is not None else '',
                'movies': [episode.title for episode in selection['movies']],
                'movie': selection['movie'].title if selection['movie'] is not None else '',
            })
        else:
            raise ValueError('Unknown section type')
        return ret

    def _ensure_active_server(self, require_online=False, force_reload=False):
        if self._active_server_id is None:
            self._active_server_id = self._pick_active_server()
        if self._active_server_id is None:
            raise RuntimeError('Plex server unavailable: no Plex server configured.')
        self.refresh_server_statuses(eager=False)
        ctx = self._servers[self._active_server_id]
        if ctx['status'] == 'online':
            self._initialize_server_selection(self._active_server_id, force=force_reload)
            return self._active_server_id, self._servers[self._active_server_id]
        if require_online:
            raise RuntimeError(self._server_unavailable_message(self._active_server_id))
        return self._active_server_id, ctx

    def _active_selection(self, require_online=False, force_reload=False):
        _, ctx = self._ensure_active_server(require_online=require_online, force_reload=force_reload)
        return ctx['selection']

    def _active_plex(self):
        _, ctx = self._ensure_active_server(require_online=True)
        return ctx['plex']

    def _active_cutter(self):
        _, ctx = self._ensure_active_server(require_online=True)
        return ctx['cutter']

    def _active_server_name(self):
        if self._active_server_id and self._active_server_id in self._servers:
            return self._servers[self._active_server_id]['config']['name']
        return 'Plex server'

    def select_server(self, server_id):
        if server_id not in self._servers:
            raise ValueError(f"Unknown Plex server '{server_id}'.")
        self.refresh_server_statuses(eager=False)
        if self._servers[server_id]['status'] != 'online':
            raise RuntimeError(self._server_unavailable_message(server_id))
        self._active_server_id = server_id
        self._initialize_server_selection(server_id, force=False)
        return self.get_selection()

    def wolserver(self):
        _, ctx = self._ensure_active_server(require_online=False)
        wolurl = ctx['config'].get('wolurl') or self.cfg.get('wolurl')
        if not wolurl:
            raise ValueError('No WOL server configured.')
        try:
            return requests.get(wolurl, timeout=30)
        except requests.exceptions.HTTPError as err:
            raise SystemExit(err)

    @property
    def section_title(self):
        selection = self._active_selection(require_online=False)
        if selection and selection.get('section') is not None:
            return selection['section'].title
        return ''

    async def streamsectionall(self):
        selection = self._active_selection(require_online=True)
        sec = selection['section']
        mov = sec.all()
        data = []
        for i, movie in enumerate(mov):
            data.append({'i': i, 'title': movie.title.replace('&', '&amp;'), 'url': movie.getStreamURL().replace('&', '&amp;'), 'dur': movie.duration})
        j2_template = Template(xspf_template)
        rendered = j2_template.render(data=data)
        buffer = BytesIO(rendered.encode('utf-8', 'xmlcharrefreplace'))
        buffer.seek(0)
        return buffer

    async def streamsection(self):
        selection = self._active_selection(require_online=True)
        movies = selection['movies']
        data = []
        for i, movie in enumerate(movies):
            data.append({'i': i, 'title': movie.title.replace('&', '&amp;'), 'url': movie.getStreamURL().replace('&', '&amp;'), 'dur': movie.duration})
        j2_template = Template(xspf_template)
        rendered = j2_template.render(data=data)
        buffer = BytesIO(rendered.encode('utf-8', 'xmlcharrefreplace'))
        buffer.seek(0)
        return buffer

    async def streamurl(self):
        selection = self._active_selection(require_online=True)
        movie = selection['movie']
        data = [{'i': 0, 'title': movie.title.replace('&', '&amp;'), 'url': movie.getStreamURL().replace('&', '&amp;'), 'dur': movie.duration}]
        j2_template = Template(xspf_template)
        rendered = j2_template.render(data=data)
        buffer = BytesIO(rendered.encode('utf-8', 'xmlcharrefreplace'))
        buffer.seek(0)
        return buffer

    def get_selection(self):
        server_id, ctx = self._ensure_active_server(require_online=False)
        if ctx['status'] == 'online':
            self._initialize_server_selection(server_id, force=False)
        return self._selection_payload(server_id)

    async def _update_section(self, section_name, force=False):
        server_id, ctx = self._ensure_active_server(require_online=True, force_reload=force)
        selection = ctx['selection']
        if selection is None:
            raise RuntimeError(self._server_unavailable_message(server_id))
        if force or selection['section'].title != section_name:
            section = ctx['plex'].server.library.section(section_name)
            ctx['selection'] = self._build_selection_from_section(section)
        return ctx['selection']['section']

    async def _update_serie(self, serie_name, force=False):
        _, ctx = self._ensure_active_server(require_online=True)
        selection = ctx['selection']
        if selection is None or selection['section_type'] != 'show':
            raise ValueError('Current section is not a show section.')
        current = selection['serie']
        if current is None or current.title != serie_name or force:
            section = selection['section']
            serie = [entry for entry in section.all() if entry.title == serie_name][0]
            seasons = serie.seasons()
            season = seasons[self.initial_season_key] if seasons else None
            movies = season.episodes() if season is not None else []
            selection.update({
                'serie': serie,
                'seasons': seasons,
                'season': season,
                'movies': movies,
                'movie': movies[self.initial_movie_key] if movies else None,
            })
        return selection['serie']

    async def _update_season(self, season_name, force=False):
        _, ctx = self._ensure_active_server(require_online=True)
        selection = ctx['selection']
        if selection is None or selection['season'] is None:
            raise ValueError('Current selection has no season.')
        if selection['season'].title != season_name or force:
            season = selection['serie'].season(season_name)
            movies = season.episodes()
            selection.update({
                'season': season,
                'movies': movies,
                'movie': movies[self.initial_movie_key] if movies else None,
            })
        return selection['season']

    async def _update_movie(self, movie_name):
        _, ctx = self._ensure_active_server(require_online=True)
        selection = ctx['selection']
        if selection is None:
            raise RuntimeError(self._server_unavailable_message(self._active_server_id))
        movies = selection['movies']
        if not movies:
            selection['movie'] = None
            return None
        sel_movie = movies[self.initial_movie_key]
        if movie_name != '':
            matching = [movie for movie in movies if movie.title == movie_name]
            if matching:
                sel_movie = matching[0]
        selection['movie'] = sel_movie
        return selection['movie']

    async def _timeline(self, req):
        selection = self._active_selection(require_online=True)
        cutter = self._active_cutter()
        basename = str(req['basename'])
        pos = int(req['pos'])
        left = int(req['l'])
        right = int(req['r'])
        step = int(req['step'])
        size = req['size']
        movie = selection['movie']
        cutter.ensure_media(movie)
        target = self.basedir + '/dist/static/' + basename
        timeline = cutter.gen_timeline(movie.duration // 1000, pos, left, right, step)
        t0 = time.time()
        result = cutter.timeline(movie, target, size, timeline)
        t1 = time.time()
        print(f"total:{(t1 - t0):5.2f}")
        return result

    async def _movie_info(self, req):
        try:
            self._ensure_active_server(require_online=True)
        except RuntimeError:
            return {'movie_info': {'duration': 0, 'duration_ms': 0}}
        plex = self._active_plex()
        selection = self._active_selection(require_online=True)
        if req is not None:
            section_name = req.get('section', selection['section'].title if selection and selection.get('section') is not None else '')
            movie_name = req.get('movie', '')
            if section_name:
                await self._update_section(section_name)
            movie = await self._update_movie(movie_name)
            if movie is None:
                return {'movie_info': {'duration': 0, 'duration_ms': 0}}
            return {'movie_info': plex.movie_rec(movie)}
        return {'movie_info': {'duration': 0, 'duration_ms': 0}}

    async def _movie_cut_info(self):
        selection = self._active_selection(require_online=True)
        cutter = self._active_cutter()
        movie = selection['movie']
        cutter.ensure_media(movie)
        duration_minutes = movie.duration / 60000
        apsc = cutter._apsc(movie)
        cutfile = cutter._cutfile(movie)
        eta_apsc = int((0.5 if not apsc else 0) * duration_minutes)
        eta_cut = int(0.9 * duration_minutes)
        eta = eta_apsc + eta_cut
        selection['eta'] = eta
        return {'movie': movie.title, 'eta': eta, 'eta_cut': eta_cut, 'eta_apsc': eta_apsc, 'cutfile': cutfile, 'apsc': apsc}

    async def _analyze_movie(self, req=None):
        self._ensure_active_server(require_online=True)
        selection = self._active_selection(require_online=True)
        section_name = req.get('section') if req else selection['section'].title
        serie_name = req.get('serie') if req else None
        season_name = req.get('season') if req else None
        movie_name = req.get('movie') if req else selection['movie'].title
        await self._update_section(section_name)
        if serie_name:
            await self._update_serie(serie_name)
        if season_name:
            await self._update_season(season_name)
        movie = await self._update_movie(movie_name)
        movie.analyze()
        return {
            'status': 'started',
            'movie': movie.title,
            'message': f"Plex analyze started for '{movie.title}'.",
        }

    async def _frame(self, req):
        selection = self._active_selection(require_online=True)
        cutter = self._active_cutter()
        if req is None:
            raise ValueError('Missing frame request data')
        movie_name = req['movie_name']
        pos_time = req['pos_time']
        try:
            movie = await self._update_movie(movie_name)
            cutter.ensure_media(movie)
            return await cutter.aframe(movie, pos_time, self.basedir + '/dist/static/')
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"\nframe throws error:\n{str(exc)}\n")
            raise exc

    async def _cut2(self, req):
        server_id, ctx = self._ensure_active_server(require_online=True)
        section_name = req['section']
        movie_name = req['movie_name']
        cutlist = req['cutlist']
        inplace = req['inplace']
        section = await self._update_section(section_name)
        movie = await self._update_movie(movie_name)
        ctx['cutter'].ensure_media(movie)
        try:
            movie_data = ctx['plex'].MovieData(movie)
            print("will cut now:\n", f"Queue Cut From server '{server_id}', section '{section}', cut '{movie.title}', cutlist{cutlist}, inplace={inplace}, engine=ffmpeg")
            job = self.q.enqueue_call(ctx['cutter'].cut, args=(movie_data, cutlist, inplace))
            job.meta['server_id'] = server_id
            job.meta['job_kind'] = 'cut'
            job.save_meta()
            result = {
                'Section': section.title,
                'Duration Raw': movie_data.duration // 60000,
                'Duration Cut': sum([ctx['cutter'].cutlength(cut['t0'], cut['t1']) for cut in cutlist]),
                'Cutlist': cutlist,
                'Inplace': inplace,
                'Engine': 'ffmpeg',
                '.ap .sc Files': ctx['cutter']._apsc(movie),
                'cut File': ctx['cutter']._cutfile(movie),
                'server': server_id,
            }
            return {'result': result}
        except subprocess.CalledProcessError as exc:
            print(str(exc))
            return {'result': str(exc)}

    def _target_cut_duration_ms(self, cutlist, server_id=None):
        cutter = self._servers[server_id]['cutter'] if server_id in self._servers else self._active_cutter()
        seconds = sum([
            max(cutter.str2pos(cut['t1']) - cutter.str2pos(cut['t0']), 0)
            for cut in cutlist
        ])
        return seconds * 1000

    def _fetch_movie_by_rating_key(self, server_id, rating_key):
        if not rating_key or server_id not in self._servers:
            return None
        ctx = self._servers[server_id]
        if ctx['status'] != 'online':
            return None
        self._initialize_server_selection(server_id, force=False)
        try:
            return ctx['plex'].server.fetchItem(int(rating_key))
        except Exception:
            try:
                return ctx['plex'].server.fetchItem(rating_key)
            except Exception:
                return None

    def _current_selection_matches_rating_key(self, server_id, rating_key):
        ctx = self._servers.get(server_id)
        if ctx is None or ctx['selection'] is None:
            return False
        current = ctx['selection'].get('movie')
        return current is not None and str(getattr(current, 'ratingKey', '')) == str(rating_key)

    def _start_post_cut_refresh(self, job):
        inplace = bool(job.args[2]) if len(job.args) > 2 else False
        if not inplace:
            self._processed_finished_cut_jobs.add(job.id)
            return None
        server_id = job.meta.get('server_id', self._active_server_id)
        movie_data = job.args[0]
        rating_key = getattr(movie_data, 'ratingKey', None)
        expected_duration_ms = self._target_cut_duration_ms(job.args[1], server_id=server_id)
        self._post_cut_refresh[server_id] = {
            'job_id': job.id,
            'server_id': server_id,
            'rating_key': str(rating_key),
            'title': getattr(movie_data, 'title', ''),
            'expected_duration_ms': expected_duration_ms,
            'started_at': time.time(),
        }
        movie = self._fetch_movie_by_rating_key(server_id, rating_key)
        if movie is not None:
            movie.analyze()
        return self._post_cut_refresh[server_id]

    def _poll_post_cut_refresh(self, server_id):
        refresh_state = self._post_cut_refresh.get(server_id)
        if not refresh_state:
            return None
        ctx = self._servers.get(server_id)
        if ctx is None or ctx['status'] != 'online':
            return {
                'title': refresh_state['title'],
                'cut_progress': 100,
                'cut_phase': 'waiting for plex',
                'apsc_progress': 0,
                'started': 1,
                'status': 'started',
            }
        movie = self._fetch_movie_by_rating_key(server_id, refresh_state['rating_key'])
        if movie is None:
            return {
                'title': refresh_state['title'],
                'cut_progress': 100,
                'cut_phase': 'plex refresh pending',
                'apsc_progress': 0,
                'started': 1,
                'status': 'started',
            }
        try:
            movie.reload(checkFiles=True)
        except Exception:
            pass
        current_duration_ms = getattr(movie, 'duration', 0) or 0
        expected_duration_ms = refresh_state['expected_duration_ms']
        if current_duration_ms > 0 and abs(current_duration_ms - expected_duration_ms) <= 5000:
            if self._current_selection_matches_rating_key(server_id, refresh_state['rating_key']):
                ctx['selection']['movie'] = movie
            self._processed_finished_cut_jobs.add(refresh_state['job_id'])
            self._post_cut_refresh.pop(server_id, None)
            return {
                'title': movie.title,
                'cut_progress': 100,
                'cut_phase': 'plex analyze finished',
                'apsc_progress': 0,
                'started': 0,
                'status': 'idle',
            }
        return {
            'title': movie.title,
            'cut_progress': 100,
            'cut_phase': f'plex analyze ({current_duration_ms // 1000}s / {(expected_duration_ms or 0) // 1000}s)',
            'apsc_progress': 0,
            'started': 1,
            'status': 'started',
        }

    async def _analyze_recording(self, req):
        server_id, ctx = self._ensure_active_server(require_online=True)
        mode = req.get('mode', 'start_end')
        if mode not in ('start_end', 'full'):
            mode = 'start_end'
        selection = ctx['selection']
        section_name = req.get('section', selection['section'].title)
        serie_name = req.get('serie')
        season_name = req.get('season')
        movie_name = req.get('movie_name') or req.get('movie') or selection['movie'].title
        await self._update_section(section_name)
        if serie_name:
            await self._update_serie(serie_name)
        if season_name:
            await self._update_season(season_name)
        movie = await self._update_movie(movie_name)
        ctx['cutter'].ensure_media(movie)
        movie_data = ctx['plex'].MovieData(movie)
        cached_result = ctx['cutter']._cached_analysis(movie_data, mode)
        if cached_result is not None:
            return {
                'job_id': f'cached:{mode}:{cached_result.get("movie", movie.title)}',
                'status': 'finished',
                'movie': movie.title,
                'mode': mode,
                'server': server_id,
                'progress': {
                    'phase': 'cached',
                    'percent': 100,
                    'movie': movie.title,
                    'cancellable': False,
                    'mode': mode,
                },
                'result': cached_result,
            }
        job = self.q.enqueue_call(
            ctx['cutter'].analyze_recording,
            args=(movie_data, mode),
            timeout=self.analysis_timeout,
        )
        job.meta['server_id'] = server_id
        job.meta['job_kind'] = 'analysis'
        job.save_meta()
        return {
            'job_id': job.id,
            'status': job.get_status(refresh=True),
            'movie': movie.title,
            'mode': mode,
            'server': server_id,
        }

    async def _analysis_status(self, job_id):
        job = Job.fetch(job_id, connection=self.redis_connection)
        status = job.get_status(refresh=True)
        payload = {
            'job_id': job.id,
            'status': status,
            'server': job.meta.get('server_id', self._active_server_id),
        }
        analysis_meta = job.meta.get('analysis', {}) if hasattr(job, 'meta') else {}
        if analysis_meta:
            payload['progress'] = analysis_meta
        if status == 'failed':
            payload['error'] = job.exc_info.splitlines()[-1] if job.exc_info else 'Analysis failed.'
            return payload
        if status == 'finished':
            if isinstance(job.result, dict) and job.result.get('cancelled'):
                payload['status'] = 'cancelled'
            payload['result'] = job.result
            return payload
        if status == 'canceled':
            payload['status'] = 'cancelled'
            return payload
        payload['movie'] = job.args[0].title if job.args else ''
        if len(job.args) > 1:
            payload['mode'] = job.args[1]
        return payload

    async def _cancel_analysis(self, job_id):
        job = Job.fetch(job_id, connection=self.redis_connection)
        status = job.get_status(refresh=True)
        analysis_meta = job.meta.get('analysis', {}) if hasattr(job, 'meta') else {}
        movie_title = analysis_meta.get('movie') or (job.args[0].title if job.args else '')
        if status in ('finished', 'failed', 'canceled'):
            return {
                'job_id': job.id,
                'status': 'cancelled' if status == 'canceled' else status,
                'movie': movie_title,
                'server': job.meta.get('server_id', self._active_server_id),
            }
        if status == 'queued':
            job.cancel()
            return {
                'job_id': job.id,
                'status': 'cancelled',
                'movie': movie_title,
                'server': job.meta.get('server_id', self._active_server_id),
            }
        job.meta['analysis'] = {
            **analysis_meta,
            'phase': 'cancelling',
            'percent': analysis_meta.get('percent', 0),
            'movie': movie_title,
            'cancellable': False,
            'cancel_requested': True,
        }
        job.save_meta()
        return {
            'job_id': job.id,
            'status': 'cancelling',
            'movie': movie_title,
            'server': job.meta.get('server_id', self._active_server_id),
            'progress': job.meta['analysis'],
        }

    def _job_server_id(self, job):
        return job.meta.get('server_id', self._active_server_id)

    def _job_matches_active_server(self, job):
        return self._job_server_id(job) == self._active_server_id

    async def _doProgress(self):
        self._ensure_active_server(require_online=False)
        mstatus = {
            'title': '-',
            'cut_progress': 0,
            'cut_phase': '',
            'apsc_progress': 0,
            'started': 0,
            'status': 'idle'
        }
        workers = Worker.all(connection=self.redis_connection)
        worker = workers[0] if len(workers) > 0 else None
        if worker and worker.last_heartbeat:
            lhb = pytz.utc.localize(worker.last_heartbeat)
            lhbtz = lhb.astimezone(pytz.timezone('Europe/Vienna'))
            _worker_status = {
                'name': worker.name,
                'state': worker.state,
                'last_heartbeat': lhbtz.strftime('%H:%M:%S'),
                'current_job_id': worker.get_current_job_id(),
                'failed': worker.failed_job_count
            }
        else:
            _worker_status = {
                'status': 'no worker detected'
            }

        started_jobs = []
        for job_id in self.q.started_job_registry.get_job_ids():
            job = Job.fetch(job_id, connection=self.redis_connection)
            if not self._job_matches_active_server(job):
                continue
            started_jobs.append(job)

        if started_jobs:
            for job in started_jobs:
                cutter = self._servers.get(self._job_server_id(job), {}).get('cutter', self._active_cutter())
                movie = job.args[0]
                cut_meta = job.meta.get('cut', {})
                progress = cut_meta.get('percent')
                if progress is None:
                    progress = cutter._movie_stats(*job.args)
                apsc_progress = cutter._apsc_stats(*job.args)
                mstatus.update({
                    'title': movie.title,
                    'cut_progress': progress,
                    'cut_phase': cut_meta.get('phase', ''),
                    'apsc_progress': apsc_progress,
                    'started': len(started_jobs),
                    'status': job.get_status(refresh=True),
                })
        else:
            refresh_status = self._poll_post_cut_refresh(self._active_server_id)
            if refresh_status is not None:
                return refresh_status

            finished_cut_job = None
            for job_id in reversed(self.q.finished_job_registry.get_job_ids()):
                if job_id in self._processed_finished_cut_jobs:
                    continue
                job = Job.fetch(job_id, connection=self.redis_connection)
                if not self._job_matches_active_server(job):
                    continue
                if getattr(job, 'func_name', '').endswith('.cut'):
                    ended_at = getattr(job, 'ended_at', None)
                    if ended_at is not None and (time.time() - ended_at.timestamp()) > 300:
                        self._processed_finished_cut_jobs.add(job_id)
                        continue
                    finished_cut_job = job
                    break
            if finished_cut_job is not None:
                refresh_state = self._start_post_cut_refresh(finished_cut_job)
                if refresh_state is not None:
                    return {
                        'title': refresh_state['title'],
                        'cut_progress': 100,
                        'cut_phase': 'plex analyze',
                        'apsc_progress': 0,
                        'started': 1,
                        'status': 'started',
                    }

        return mstatus
