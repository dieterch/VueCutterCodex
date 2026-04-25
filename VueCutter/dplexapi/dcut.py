import asyncio
import os
import time
import concurrent.futures
import subprocess
import shlex
import re
import selectors
import signal
import hashlib
from pprint import pformat as pf
from rq import get_current_job

class MediaUnavailableError(FileNotFoundError):
	def __init__(self, path):
		super().__init__(f"Media source unavailable: '{path}' is missing. Ensure the NAS is online and the host media path is mounted.")
		self.path = path

class AnalysisCancelledError(RuntimeError):
	pass

class CutterInterface:
	def __init__(self, server, media_root=None):
		self._server = server
		self._ffmpeg_binary = '/usr/bin/ffmpeg'
		self._media_root = (media_root or os.getenv('VUECUTTER_MEDIA_ROOT', '')).rstrip('/')
		self._media_keep_share = os.getenv('VUECUTTER_MEDIA_KEEP_SHARE', 'true').lower() != 'false'
		self._analysis_cache = {}
		self.last_movie = ""
		self.target = ""

	def _long_runtask(self, delay):
		time.sleep(delay)

	def _path_plit(self, movie):
		hlp = movie.locations[0].split('/')
		share = "/".join(hlp[2:3])
		folder = "/".join(hlp[3:-1])
		file = hlp[-1]
		return (share, folder, file)

	def _call(self, exc_lst):
		try:
			res = subprocess.check_output(exc_lst)
			return res
		except subprocess.CalledProcessError as err:
			raise err		

	def _filename(self,movie):
		"""
		the movie filename
		"""
		if len(movie.locations) > 1:
			raise ValueError('cannot handle multiple Files in movie folder')
		else:
			_,_,file = self._path_plit(movie)
			return file

	def _foldername(self,movie):
		"""
		path to the mounted movie folder
		"""
		if len(movie.locations) > 1:
			raise ValueError('cannot handle multiple Files in movie folder')
		else:
			share,path,_ = self._path_plit(movie)
			if self._media_root:
				parts = [self._media_root]
				if self._media_keep_share and share:
					parts.append(share)
				if path:
					parts.append(path)
				return os.path.join(*parts) + "/"
			return os.path.dirname(__file__) + "/mnt/" + path + ("/" if path else "")	

	def _pathname(self,movie):
		"""
		path to the mounted movie file
		"""
		return self._foldername(movie) + self._filename(movie)		

	def ensure_media(self, movie):
		self.mount(movie)
		path = self._pathname(movie)
		if not os.path.exists(path):
			raise MediaUnavailableError(path)
		return path

	def _cutfilename(self,movie):
		"""
		the movie cut filename
		"""
		if len(movie.locations) > 1:
			raise ValueError('cannot handle multiple Files in movie folder')
		else:
			return os.path.splitext(self._filename(movie))[0] + ' cut.ts'

	def _cutname(self,movie):
		"""
		path to the mounted movie cut file (inplace = False)
		"""
		return self._foldername(movie) + self._cutfilename(movie)	

	def _tempfilename(self,movie):
		"""
		the movie temp filename @ inplace cutting
		"""
		if len(movie.locations) > 1:
			raise ValueError('cannot handle multiple Files in movie folder')
		else:
			return os.path.splitext(self._filename(movie))[0] + '_.ts'

	def _tempname(self,movie):
		"""
		path to the temporary movie cut file (inplace = true)
		"""
		return self._foldername(movie) + self._tempfilename(movie)

	def _movie_stats(self, movie, cutlist, inplace=False):
		"""
		return TS Progress in percent 
		"""
		if inplace:
			targetname =  f"{self._pathname(movie)}"
		else:
			targetname =  f"{self._cutname(movie)}"  
		self.ensure_media(movie)
		cl = sum([self.cutlength(cut['t0'],cut['t1']) for cut in cutlist])
		ml = (movie.duration / 60000)
		faktor = cl/ml
		try:
			moviesize = os.path.getsize(self._pathname(movie))
			targetsize = faktor * moviesize
			#targetfile = self._cutname(movie) if not inplace else self._tempname(movie)
			# first calculate the size of all parts
			actualsize = sum([os.path.getsize(f"{self._foldername(movie)}part{i}.ts") for i in range(len(cutlist))])
			if len(cutlist) > 1:
				# add the size of the target file to actualsize
				if os.path.exists(targetname):
					actualsize += os.path.getsize(targetname)
				targetsize = 2 * targetsize # parts and target file
			elif os.path.exists(targetname):
				actualsize = os.path.getsize(targetname)
		except FileNotFoundError as e:
			print(str(e))
			actualsize = 0
		print(f"**** actualsize: {actualsize:.0f} targetsize: {targetsize:.0f}")
		progress = actualsize/targetsize
		progress = int(progress * 100) if progress < 1.0 else 100
		return progress

	def _apsc_stats(self, movie, cutlist, inplace=False):
		"""
		return AP Progress in percent 
		"""
		return 100

	def mount(self, movie):
		if self._media_root:
			return None
		if len(movie.locations) > 1:
			raise ValueError('cannot cut multiple Files in movie folder')
		else:
			share, path, file = self._path_plit(movie)
			source = f"//{self._server}/{share}"
			target = os.path.dirname(__file__) + "/mnt/"
			mount_lst = ["mount","-t","cifs", "-o", "credentials=/etc/smbcredentials", f"{source}", f"{target}"]
		try:
			if not os.path.exists(self._pathname(movie)):
				# beim ersten mount oder wenn die section sich ändert ...
				print('******remounting necessary')				
				try:
					self.umount()
				except subprocess.CalledProcessError as e:
					print(f'***** neglecting error by intention ****')

				res = subprocess.check_output(mount_lst)
				print(f"{source} mounted.")
				return res
			else:
				pass
				#print('******no mounting needed')
		except subprocess.CalledProcessError as e:
			print(str(e))
			raise e

	def umount(self):
		if self._media_root:
			return None
		target = os.path.dirname(__file__) + "/mnt/"
		umount_lst = ["umount","-l",f"{target}"]		
		try:
			res = subprocess.check_output(umount_lst)
			print(f"{target} unmounted.")
			return res
		except subprocess.CalledProcessError as e:
			print(str(e))
			raise e

	def pos2str(self,pos):
		return f"{(pos // 3600):02d}:{((pos % 3600) // 60):02d}:{(pos % 60):02d}"

	def str2pos(self,ps):
		return int(ps[:2])*3600 + int(ps[3:5])*60 + int(ps[-2:])

	def cutlength(self,ss,to):
		return (self.str2pos(to) - self.str2pos(ss)) // 60

	def dstr(self, pos, max, ds):
		val = pos + ds
		val = val if val >=0 else 0
		val = val if val < max else max
		return self.pos2str(val)

	def gen_timeline(self, max, pos, l, r ,step):
		return [self.dstr(pos,max,delta) for delta in range(l*step,(r+1)*step,step)]

	def fname2file(self, ftime):
		if self.target != "":
			return self.target[:-4] + '_' + ftime + self.target[-4:]
		else:
			return ""

	def filter_timelist(self, timelist):
		if self.target == "":
			return timelist
		else: 
			return [ftime for ftime in timelist if not os.path.exists(self.fname2file(ftime))]

	def delete_target_files(self):
		if self.target != "":
			for file in os.listdir(os.path.dirname(self.target)):
				if file.startswith(os.path.basename(self.target)[:-4] + '_'):
					os.remove(os.path.dirname(self.target) + '/' + file)	
		
	def timeline(self, movie, target, size, timelist):
		self.target = target
		if movie.title != self.last_movie: 
			self.delete_target_files()
		#print('Timelist vor dem filtern:')
		#print(pf(timelist))
		timelist = self.filter_timelist(timelist)
		#print('Timelist nach dem filtern:')
		#print(pf(timelist))		
		with concurrent.futures.ThreadPoolExecutor() as executor:
			futures = []
			for ftime in timelist:
				futures.append(executor.submit(self.frame, ftime, size, movie, self.fname2file(ftime)))
			result = []
			for future in concurrent.futures.as_completed(futures):
				result.append(future.result())
		self.last_movie = movie.title
		return 'ok'

	def frame(self, ftime, scale, movie, ftarget):
		t0 = time.time()
		self.ensure_media(movie)
		ffstr2 = f"""ffmpeg -ss {ftime} -i "{self._pathname(movie)}" -vframes 1 -q:v 15 \
-vf "scale={scale}:-1, drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf: \
x=(w-text_w)/2: y=(h-text_h)*0.98: fontsize=18: fontcolor=yellow: \
text='{(ftime[:2]+chr(92)+':'+ftime[3:5]+chr(92)+':'+ftime[-2:]).replace('0','O')}':" '{ftarget}' \
-hide_banner -loglevel fatal -max_error_rate 1 -y"""
		exc_lst = shlex.split(ffstr2)
		try:
			subprocess.check_output(exc_lst)
		except subprocess.CalledProcessError as err:
			print(str(err))
			raise(err)
		finally:
			t1 = time.time()
			return f"{(t1-t0):5.2f}"


	def oframe(self,movie, ftime, ftarget = None):
		t0 = time.time()
		#frame_name = 'guid' + PlexInterface.movie_rec(movie)['guid'] + '_' + str(ftime).replace(':','-') + '.jpg'
		frame_name = 'frame.jpg'
		if ftarget == None:
			ftarget = os.path.dirname(__file__) + "/data/"
		ftarget += frame_name
		exc_lst = [self._ffmpeg_binary,"-ss", ftime, "-i", f"{self._pathname(movie)}", 
			"-vframes", "1", "-q:v", "15", "-vf" ,"scale=1024:-1",f"{ftarget}", "-hide_banner", "-loglevel", "fatal", 
			"-max_error_rate","1","-y" ]
		self.ensure_media(movie)
		try:
			res = subprocess.check_output(exc_lst)
			res = res.decode('utf-8')
			print(res)
		except subprocess.CalledProcessError as err:
			print(str(err))
		finally:
			#self.umount()
			t1 = time.time()
			print(f"In frame:{(t1-t0):5.2f} sec.")
			return frame_name

	async def aframe(self,movie, ftime, ftarget = None):
		t0 = time.time()
		#frame_name = 'guid' + PlexInterface.movie_rec(movie)['guid'] + '_' + str(ftime).replace(':','-') + '.jpg'
		frame_name = 'frame.jpg'
		if ftarget == None:
			ftarget = os.path.dirname(__file__) + "/data/"
		ftarget += frame_name
		exc_lst = [self._ffmpeg_binary,"-ss", ftime, "-i", f"{self._pathname(movie)}", 
			"-vframes", "1", "-q:v", "15", "-vf" ,"scale=1024:-1",f"{ftarget}", "-hide_banner", "-loglevel", "fatal", 
			"-max_error_rate","1","-y" ]
		self.ensure_media(movie)
		try:
			res = subprocess.check_output(exc_lst)
			res = res.decode('utf-8')
			print(res)
		except subprocess.CalledProcessError as err:
			print(str(err))
		finally:
			#self.umount()
			t1 = time.time()
			print(f"\nIn aframe:{(t1-t0):5.2f} sec.")
			return frame_name

	def _set_analysis_progress(self, phase, percent, movie_title="", cancellable=False, mode="start_end"):
		job = get_current_job()
		if job is None:
			return
		current = job.meta.get('analysis', {})
		job.meta['analysis'] = {
			'phase': phase,
			'percent': max(0, min(int(percent), 100)),
			'movie': movie_title,
			'cancellable': cancellable,
			'cancel_requested': current.get('cancel_requested', False),
			'mode': mode,
		}
		job.save_meta()

	def _set_cut_progress(self, phase, percent, movie_title=""):
		job = get_current_job()
		if job is None:
			return
		job.meta['cut'] = {
			'phase': phase,
			'percent': max(0, min(int(percent), 100)),
			'movie': movie_title,
		}
		job.save_meta()

	def _request_analysis_cancel(self, phase='cancelling', percent=None, movie_title="", mode="start_end"):
		job = get_current_job()
		if job is None:
			return
		current = job.meta.get('analysis', {})
		job.meta['analysis'] = {
			'phase': phase,
			'percent': current.get('percent', 0) if percent is None else max(0, min(int(percent), 100)),
			'movie': movie_title or current.get('movie', ''),
			'cancellable': False,
			'cancel_requested': True,
			'mode': mode or current.get('mode', 'start_end'),
		}
		job.save_meta()

	def _cancel_requested(self, last_check, minimum_interval=1.0):
		job = get_current_job()
		now = time.time()
		if job is None:
			return False, now
		if now - last_check < minimum_interval:
			return False, last_check
		job.refresh()
		requested = bool(job.meta.get('analysis', {}).get('cancel_requested'))
		return requested, now

	def _terminate_process(self, process):
		try:
			os.killpg(process.pid, signal.SIGTERM)
		except ProcessLookupError:
			return
		except Exception:
			process.terminate()
		try:
			process.wait(timeout=5)
		except subprocess.TimeoutExpired:
			try:
				os.killpg(process.pid, signal.SIGKILL)
			except Exception:
				process.kill()
			process.wait(timeout=5)

	def _progress_seconds_from_line(self, line):
		if line.startswith('out_time_ms='):
			try:
				return int(line.split('=', 1)[1]) / 1_000_000
			except ValueError:
				return None
		if line.startswith('out_time='):
			try:
				return self.str2pos(line.split('=', 1)[1].strip())
			except Exception:
				return None
		return None

	def _run_ffmpeg_detection(self, movie, exc_lst, phase, phase_start_percent, phase_end_percent, duration_seconds, mode="start_end"):
		self.ensure_media(movie)
		process = subprocess.Popen(
			exc_lst,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
			bufsize=1,
			start_new_session=True,
		)
		selector = selectors.DefaultSelector()
		if process.stdout:
			selector.register(process.stdout, selectors.EVENT_READ, data='stdout')
		if process.stderr:
			selector.register(process.stderr, selectors.EVENT_READ, data='stderr')
		stdout_chunks = []
		stderr_chunks = []
		last_percent = phase_start_percent
		last_cancel_check = 0.0
		self._set_analysis_progress(phase, phase_start_percent, movie.title, cancellable=True, mode=mode)
		while selector.get_map():
			cancel_requested, last_cancel_check = self._cancel_requested(last_cancel_check)
			if cancel_requested:
				self._request_analysis_cancel(movie_title=movie.title, mode=mode)
				self._terminate_process(process)
				selector.close()
				raise AnalysisCancelledError(f'Analysis cancelled for {movie.title}.')
			for key, _ in selector.select(timeout=0.5):
				line = key.fileobj.readline()
				if not line:
					selector.unregister(key.fileobj)
					continue
				if key.data == 'stdout':
					stdout_chunks.append(line)
					seconds = self._progress_seconds_from_line(line.strip())
					if seconds is None or duration_seconds <= 0:
						continue
					phase_progress = max(0.0, min(seconds / duration_seconds, 1.0))
					percent = int(phase_start_percent + (phase_end_percent - phase_start_percent) * phase_progress)
					if percent > last_percent:
						last_percent = percent
						self._set_analysis_progress(phase, percent, movie.title, cancellable=True, mode=mode)
				else:
					stderr_chunks.append(line)
		returncode = process.wait()
		selector.close()
		self._set_analysis_progress(phase, phase_end_percent, movie.title, cancellable=True, mode=mode)
		if returncode != 0:
			raise subprocess.CalledProcessError(
				returncode,
				exc_lst,
				output=''.join(stdout_chunks),
				stderr=''.join(stderr_chunks)
			)
		return ''.join(stdout_chunks) + '\n' + ''.join(stderr_chunks)

	def _run_ffmpeg_cut_process(self, exc_lst, movie, phase, phase_start_percent, phase_end_percent, duration_seconds):
		process = subprocess.Popen(
			exc_lst,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
			bufsize=1,
		)
		selector = selectors.DefaultSelector()
		if process.stdout:
			selector.register(process.stdout, selectors.EVENT_READ, data='stdout')
		if process.stderr:
			selector.register(process.stderr, selectors.EVENT_READ, data='stderr')
		stdout_chunks = []
		stderr_chunks = []
		last_percent = phase_start_percent
		self._set_cut_progress(phase, phase_start_percent, movie.title)
		while selector.get_map():
			for key, _ in selector.select(timeout=0.5):
				line = key.fileobj.readline()
				if not line:
					selector.unregister(key.fileobj)
					continue
				if key.data == 'stdout':
					stdout_chunks.append(line)
					seconds = self._progress_seconds_from_line(line.strip())
					if seconds is None or duration_seconds <= 0:
						continue
					phase_progress = max(0.0, min(seconds / duration_seconds, 1.0))
					percent = int(phase_start_percent + (phase_end_percent - phase_start_percent) * phase_progress)
					if percent > last_percent:
						last_percent = percent
						self._set_cut_progress(phase, percent, movie.title)
				else:
					stderr_chunks.append(line)
		returncode = process.wait()
		selector.close()
		self._set_cut_progress(phase, phase_end_percent, movie.title)
		if returncode != 0:
			raise subprocess.CalledProcessError(
				returncode,
				exc_lst,
				output=''.join(stdout_chunks),
				stderr=''.join(stderr_chunks)
			)
		return ''.join(stdout_chunks) + '\n' + ''.join(stderr_chunks)

	def _parse_black_events(self, log_text):
		pattern = re.compile(r"black_start:(?P<start>\d+(?:\.\d+)?)\s+black_end:(?P<end>\d+(?:\.\d+)?)\s+black_duration:(?P<duration>\d+(?:\.\d+)?)")
		events = []
		for match in pattern.finditer(log_text):
			events.append({
				'type': 'black',
				'start': float(match.group('start')),
				'end': float(match.group('end')),
				'duration': float(match.group('duration')),
			})
		return events

	def _parse_silence_events(self, log_text):
		start_pattern = re.compile(r"silence_start:\s*(?P<start>\d+(?:\.\d+)?)")
		end_pattern = re.compile(r"silence_end:\s*(?P<end>\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(?P<duration>\d+(?:\.\d+)?)")
		events = []
		current_start = None
		for line in log_text.splitlines():
			start_match = start_pattern.search(line)
			if start_match:
				current_start = float(start_match.group('start'))
				continue
			end_match = end_pattern.search(line)
			if end_match and current_start is not None:
				events.append({
					'type': 'silence',
					'start': current_start,
					'end': float(end_match.group('end')),
					'duration': float(end_match.group('duration')),
				})
				current_start = None
		return events

	def _analysis_cache_key(self, movie, mode):
		path = movie.locations[0] if movie.locations else movie.title
		try:
			stat = os.stat(self._pathname(movie))
			payload = f"{mode}|{path}|{stat.st_size}|{int(stat.st_mtime)}"
		except Exception:
			payload = f"{mode}|{path}|{getattr(movie, 'duration', 0)}"
		return hashlib.sha1(payload.encode('utf-8')).hexdigest()

	def _cached_analysis(self, movie, mode):
		key = self._analysis_cache_key(movie, mode)
		result = self._analysis_cache.get(key)
		if result is None:
			return None
		return {**result, 'cached': True}

	def _store_analysis_cache(self, movie, mode, result):
		key = self._analysis_cache_key(movie, mode)
		self._analysis_cache[key] = {**result, 'mode': mode}

	def _offset_events(self, events, offset_seconds):
		return [
			{
				**event,
				'start': event['start'] + offset_seconds,
				'end': event['end'] + offset_seconds,
			}
			for event in events
		]

	def _window_bounds(self, duration_seconds, kind):
		window_size = min(max(25 * 60, duration_seconds // 5 if duration_seconds else 0), 30 * 60)
		window_size = max(min(window_size, duration_seconds if duration_seconds > 0 else window_size), 1)
		if kind == 'start':
			return 0, window_size
		return max(duration_seconds - window_size, 0), min(window_size, duration_seconds)

	def _run_window_detection(self, movie, kind, phase_prefix, phase_start_percent, phase_end_percent, mode="start_end", include_silence=False):
		duration_seconds = max(int(movie.duration // 1000), 0)
		offset_seconds, window_seconds = self._window_bounds(duration_seconds, kind)
		path = self._pathname(movie)
		black_log = self._run_ffmpeg_detection(movie, [
			self._ffmpeg_binary,
			'-hide_banner',
			'-loglevel', 'info',
			'-nostats',
			'-progress', 'pipe:1',
			'-ss', self.pos2str(int(offset_seconds)),
			'-t', self.pos2str(int(window_seconds)),
			'-i', path,
			'-vf', 'blackdetect=d=0.2:pic_th=0.97',
			'-an',
			'-f', 'null',
			'-'
		], f'{phase_prefix} {kind} window', phase_start_percent, phase_end_percent, max(window_seconds, 1), mode=mode)
		black_events = self._offset_events(self._parse_black_events(black_log), offset_seconds)
		silence_events = []
		if include_silence:
			try:
				silence_log = self._run_ffmpeg_detection(movie, [
					self._ffmpeg_binary,
					'-hide_banner',
					'-loglevel', 'info',
					'-nostats',
					'-progress', 'pipe:1',
					'-ss', self.pos2str(int(offset_seconds)),
					'-t', self.pos2str(int(window_seconds)),
					'-i', path,
					'-af', 'silencedetect=n=-35dB:d=0.35',
					'-vn',
					'-f', 'null',
					'-'
				], f'{phase_prefix} {kind} refine', phase_end_percent, phase_end_percent, max(window_seconds, 1), mode=mode)
				silence_events = self._offset_events(self._parse_silence_events(silence_log), offset_seconds)
			except subprocess.CalledProcessError:
				silence_events = []
		return black_events, silence_events

	def _candidate_score(self, candidate_time, target_time, preferred_start, preferred_end, base_score):
		score = base_score
		if preferred_start <= candidate_time <= preferred_end:
			score += 2.5
		distance = abs(candidate_time - target_time)
		score += max(0.0, 2.0 - (distance / 180.0))
		return round(score, 3)

	def _select_edge_candidate(self, black_events, silence_events, kind, duration_seconds):
		target_time = min(15 * 60, duration_seconds / 2 if duration_seconds else 15 * 60) if kind == 'start' else max(duration_seconds - 15 * 60, 0)
		if kind == 'start':
			preferred_start = min(5 * 60, max(duration_seconds - 1, 0))
			preferred_end = min(20 * 60, duration_seconds)
		else:
			preferred_start = max(duration_seconds - 20 * 60, 0)
			preferred_end = max(duration_seconds - 5 * 60, 0)
		candidates = []
		for event in black_events:
			moment = event['end'] if kind == 'start' else event['start']
			base = 3.0 + min(event['duration'], 2.0)
			candidates.append({
				'time': moment,
				'score': self._candidate_score(moment, target_time, preferred_start, preferred_end, base),
				'source': 'black',
			})
		for event in silence_events:
			moment = event['end'] if kind == 'start' else event['start']
			base = 1.0 + min(event['duration'], 1.0)
			candidates.append({
				'time': moment,
				'score': self._candidate_score(moment, target_time, preferred_start, preferred_end, base),
				'source': 'silence',
			})
		if not candidates:
			return None
		return max(candidates, key=lambda candidate: (candidate['score'], -abs(candidate['time'] - target_time)))

	def _detect_start_end_boundaries(self, movie, mode="start_end"):
		duration_seconds = max(int(movie.duration // 1000), 0)
		warnings = []
		start_black, start_silence = self._run_window_detection(movie, 'start', 'scan', 0, 35, mode=mode, include_silence=True)
		start_candidate = self._select_edge_candidate(start_black, start_silence, 'start', duration_seconds)
		end_black, end_silence = self._run_window_detection(movie, 'end', 'scan', 50, 85, mode=mode, include_silence=True)
		end_candidate = self._select_edge_candidate(end_black, end_silence, 'end', duration_seconds)
		boundaries = []
		if start_candidate is None:
			warnings.append('No confident content start detected; defaulting to recording start.')
			boundaries.append({'id': 'content-start', 'kind': 'content_start', 'time': self.pos2str(0), 'confidence': 0.1})
		else:
			boundaries.append({
				'id': 'content-start',
				'kind': 'content_start',
				'time': self.pos2str(int(start_candidate['time'])),
				'confidence': round(min(start_candidate['score'] / 5.0, 1.0), 2),
			})
		if end_candidate is None:
			warnings.append('No confident content end detected; defaulting to recording end.')
			boundaries.append({'id': 'content-end', 'kind': 'content_end', 'time': self.pos2str(duration_seconds), 'confidence': 0.1})
		else:
			boundaries.append({
				'id': 'content-end',
				'kind': 'content_end',
				'time': self.pos2str(int(end_candidate['time'])),
				'confidence': round(min(end_candidate['score'] / 5.0, 1.0), 2),
			})
		return sorted(boundaries, key=lambda boundary: self.str2pos(boundary['time'])), warnings

	def _scan_ad_breaks(self, movie, content_start_seconds, content_end_seconds, mode="full"):
		if content_end_seconds - content_start_seconds < 180:
			return [], ['Recording is too short for reliable ad-break detection.']
		path = self._pathname(movie)
		chunk_size = 20 * 60
		current = content_start_seconds
		all_black_events = []
		chunk_index = 0
		total_seconds = max(content_end_seconds - content_start_seconds, 1)
		while current < content_end_seconds:
			window_seconds = min(chunk_size, content_end_seconds - current)
			phase_start = 60 + int(35 * ((current - content_start_seconds) / total_seconds))
			phase_end = 60 + int(35 * (((current - content_start_seconds) + window_seconds) / total_seconds))
			log_text = self._run_ffmpeg_detection(movie, [
				self._ffmpeg_binary,
				'-hide_banner',
				'-loglevel', 'info',
				'-nostats',
				'-progress', 'pipe:1',
				'-ss', self.pos2str(int(current)),
				'-t', self.pos2str(int(window_seconds)),
				'-i', path,
				'-vf', 'blackdetect=d=0.25:pic_th=0.97',
				'-an',
				'-f', 'null',
				'-'
			], f'scan ads {chunk_index + 1}', phase_start, phase_end, max(window_seconds, 1), mode=mode)
			all_black_events.extend(self._offset_events(self._parse_black_events(log_text), current))
			current += window_seconds
			chunk_index += 1
		clusters = self._cluster_points_from_events(all_black_events, [])
		pairs = self._pair_ad_clusters(clusters, content_start_seconds, content_end_seconds)
		boundaries = []
		for pair_index, (ad_start, ad_end) in enumerate(pairs):
			boundaries.append({
				'id': f'ad-start-{pair_index}',
				'kind': 'ad_start',
				'time': self.pos2str(int(ad_start['time'])),
				'confidence': round(min(ad_start['score'] / 3.0, 1.0), 2),
			})
			boundaries.append({
				'id': f'ad-end-{pair_index}',
				'kind': 'ad_end',
				'time': self.pos2str(int(ad_end['time'])),
				'confidence': round(min(ad_end['score'] / 3.0, 1.0), 2),
			})
		if not boundaries:
			return [], ['No confident ad breaks detected inside the content window.']
		return sorted(boundaries, key=lambda boundary: self.str2pos(boundary['time'])), []

	def _cluster_boundary_points(self, points, merge_window=6):
		if not points:
			return []
		points = sorted(points, key=lambda point: point['time'])
		clusters = []
		current = None
		for point in points:
			if current is None or point['time'] - current['last_time'] > merge_window:
				current = {
					'weighted_time': point['time'] * point['weight'],
					'total_weight': point['weight'],
					'start_weight': point['weight'] if point['direction'] == 'start' else 0.0,
					'end_weight': point['weight'] if point['direction'] == 'end' else 0.0,
					'black_weight': point['weight'] if point['source'] == 'black' else 0.0,
					'silence_weight': point['weight'] if point['source'] == 'silence' else 0.0,
					'last_time': point['time'],
				}
				clusters.append(current)
				continue
			current['weighted_time'] += point['time'] * point['weight']
			current['total_weight'] += point['weight']
			current['last_time'] = point['time']
			if point['direction'] == 'start':
				current['start_weight'] += point['weight']
			else:
				current['end_weight'] += point['weight']
			if point['source'] == 'black':
				current['black_weight'] += point['weight']
			else:
				current['silence_weight'] += point['weight']
		for index, cluster in enumerate(clusters):
			cluster['time'] = cluster['weighted_time'] / cluster['total_weight']
			cluster['score'] = round(cluster['total_weight'], 2)
			cluster['id'] = f"cluster-{index}"
		return clusters

	def _cluster_points_from_events(self, black_events, silence_events):
		points = []
		for event in black_events:
			weight = 1.3 if event['duration'] >= 0.4 else 1.0
			points.append({'time': event['start'], 'direction': 'start', 'weight': weight, 'source': 'black'})
			points.append({'time': event['end'], 'direction': 'end', 'weight': weight, 'source': 'black'})
		for event in silence_events:
			weight = 0.7 if event['duration'] >= 0.5 else 0.5
			points.append({'time': event['start'], 'direction': 'start', 'weight': weight, 'source': 'silence'})
			points.append({'time': event['end'], 'direction': 'end', 'weight': weight, 'source': 'silence'})
		return self._cluster_boundary_points(points)

	def _choose_content_start(self, clusters, duration_seconds):
		window_end = min(max(duration_seconds * 0.45, 300), 1800)
		candidates = [cluster for cluster in clusters if 15 <= cluster['time'] <= window_end and cluster['end_weight'] >= cluster['start_weight']]
		if not candidates:
			return None
		return max(candidates, key=lambda cluster: (cluster['score'], -cluster['time']))

	def _choose_content_end(self, clusters, duration_seconds):
		window_start = max(duration_seconds * 0.55, duration_seconds - 1800, 0)
		candidates = [cluster for cluster in clusters if window_start <= cluster['time'] <= max(duration_seconds - 15, 0) and cluster['start_weight'] >= cluster['end_weight']]
		if not candidates:
			return None
		return max(candidates, key=lambda cluster: (cluster['score'], cluster['time']))

	def _pair_ad_clusters(self, clusters, content_start, content_end):
		internal = [
			cluster for cluster in clusters
			if content_start + 30 < cluster['time'] < content_end - 30 and cluster['score'] >= 1.0
		]
		pairs = []
		index = 0
		while index < len(internal):
			start_cluster = internal[index]
			if start_cluster['start_weight'] <= start_cluster['end_weight']:
				index += 1
				continue
			match = None
			for candidate_index in range(index + 1, len(internal)):
				end_cluster = internal[candidate_index]
				gap = end_cluster['time'] - start_cluster['time']
				if gap < 30:
					continue
				if gap > 1200:
					break
				if end_cluster['end_weight'] >= end_cluster['start_weight']:
					match = (candidate_index, end_cluster)
					break
			if match is None:
				index += 1
				continue
			candidate_index, end_cluster = match
			pairs.append((start_cluster, end_cluster))
			index = candidate_index + 1
		return pairs

	def _derive_keep_intervals(self, boundaries):
		warnings = []
		start_boundary = next((boundary for boundary in boundaries if boundary['kind'] == 'content_start'), None)
		end_boundary = next((boundary for boundary in boundaries if boundary['kind'] == 'content_end'), None)
		if not start_boundary or not end_boundary:
			return [], ['Unable to derive keep intervals because start/end detection is incomplete.']
		start_seconds = self.str2pos(start_boundary['time'])
		end_seconds = self.str2pos(end_boundary['time'])
		if end_seconds <= start_seconds:
			return [], ['Detected end is not after detected start.']
		intervals = []
		cursor_seconds = start_seconds
		cursor_id = start_boundary['id']
		ad_starts = sorted((boundary for boundary in boundaries if boundary['kind'] == 'ad_start'), key=lambda boundary: boundary['time'])
		ad_ends = sorted((boundary for boundary in boundaries if boundary['kind'] == 'ad_end'), key=lambda boundary: boundary['time'])
		pending_end_index = 0
		for ad_start in ad_starts:
			ad_start_seconds = self.str2pos(ad_start['time'])
			if ad_start_seconds <= cursor_seconds or ad_start_seconds >= end_seconds:
				continue
			while pending_end_index < len(ad_ends) and self.str2pos(ad_ends[pending_end_index]['time']) <= ad_start_seconds:
				pending_end_index += 1
			if pending_end_index >= len(ad_ends):
				warnings.append(f"Ad start at {ad_start['time']} has no matching ad end.")
				break
			ad_end = ad_ends[pending_end_index]
			ad_end_seconds = self.str2pos(ad_end['time'])
			if ad_end_seconds <= ad_start_seconds:
				warnings.append(f"Ad end at {ad_end['time']} is not after ad start {ad_start['time']}.")
				pending_end_index += 1
				continue
			if ad_start_seconds > cursor_seconds:
				intervals.append({
					't0': self.pos2str(cursor_seconds),
					't1': ad_start['time'],
					'start_id': cursor_id,
					'end_id': ad_start['id'],
				})
			cursor_seconds = ad_end_seconds
			cursor_id = ad_end['id']
			pending_end_index += 1
		if cursor_seconds < end_seconds:
			intervals.append({
				't0': self.pos2str(cursor_seconds),
				't1': end_boundary['time'],
				'start_id': cursor_id,
				'end_id': end_boundary['id'],
			})
		intervals = [interval for interval in intervals if self.str2pos(interval['t1']) > self.str2pos(interval['t0'])]
		if not intervals:
			warnings.append('No remaining keep intervals could be derived from the detected boundaries.')
		return intervals, warnings

	def analyze_recording(self, movie, mode='start_end'):
		t0 = time.time()
		self.ensure_media(movie)
		duration_seconds = max(int(movie.duration // 1000), 0)
		cached = self._cached_analysis(movie, mode)
		if cached is not None:
			self._set_analysis_progress('cached', 100, movie.title, cancellable=False, mode=mode)
			return cached
		warnings = []
		self._set_analysis_progress('starting', 0, movie.title, cancellable=True, mode=mode)
		try:
			start_end_cached = self._cached_analysis(movie, 'start_end') if mode == 'full' else None
			if start_end_cached is not None:
				boundaries = list(start_end_cached.get('boundaries', []))
				boundary_warnings = list(start_end_cached.get('warnings', []))
				self._set_analysis_progress('reusing cached start/end', 55, movie.title, cancellable=True, mode=mode)
			else:
				boundaries, boundary_warnings = self._detect_start_end_boundaries(movie, mode=mode)
			warnings.extend(boundary_warnings)
			content_start_seconds = self.str2pos(next(boundary['time'] for boundary in boundaries if boundary['kind'] == 'content_start'))
			content_end_seconds = self.str2pos(next(boundary['time'] for boundary in boundaries if boundary['kind'] == 'content_end'))
			if mode == 'full' and content_end_seconds > content_start_seconds:
				ad_boundaries, ad_warnings = self._scan_ad_breaks(movie, content_start_seconds, content_end_seconds, mode=mode)
				boundaries.extend(ad_boundaries)
				warnings.extend(ad_warnings)
			else:
				self._set_analysis_progress('finished start/end', 100, movie.title, cancellable=False, mode=mode)
			boundaries = sorted(boundaries, key=lambda boundary: self.str2pos(boundary['time']))
			keep_intervals, interval_warnings = self._derive_keep_intervals(boundaries)
			warnings.extend(interval_warnings)
		except AnalysisCancelledError:
			self._request_analysis_cancel(phase='cancelled', percent=0, movie_title=movie.title, mode=mode)
			return {
				'movie': movie.title,
				'duration': self.pos2str(duration_seconds),
				'boundaries': [],
				'keep_intervals': [],
				'warnings': ['Analysis cancelled.'],
				'analysis_seconds': round(time.time() - t0, 2),
				'cancelled': True,
				'mode': mode,
			}
		result = {
			'movie': movie.title,
			'duration': self.pos2str(duration_seconds),
			'boundaries': boundaries,
			'keep_intervals': keep_intervals,
			'warnings': warnings,
			'analysis_seconds': round(time.time() - t0, 2),
			'mode': mode,
		}
		self._store_analysis_cache(movie, mode, result)
		self._set_analysis_progress('finished', 100, movie.title, cancellable=False, mode=mode)
		return result

	def _apsc(self,movie):
		#check ob .ap und Datei existiert.
		try:
			self.ensure_media(movie)
			return os.path.exists(self._pathname(movie)+'.ap')
		except FileNotFoundError as e:
			print(str(e))
		finally:
			pass
			#self.umount()

	def _apsc_size(self,movie):
		if os.path.exists(self._pathname(movie)+'.ap'):
			return os.path.getsize(self._pathname(movie)+'.ap')
		else:
			return 0

	def _cutfile(self,movie):
		#check ob *_cut.ts Datei existiert.
		try:
			self.ensure_media(movie)
			return os.path.exists(self._cutname(movie))
		except FileNotFoundError as e:
			print(str(e))
		finally:
			pass
			#self.umount()

	def _ffmpegjoin(self, movie, cutlist, inplace = False):
        # if there is only one part, just rename it to the target file otherwise join the parts
		if inplace:
			targetname =  f"{self._pathname(movie)}"
		else:
			targetname =  f"{self._cutname(movie)}"
		if len(cutlist) > 1:
			print()
			print(f"'{self._filename(movie)}' wird mit ffmpeg zusammengefügt. -]+{cutlist}+[- ")
			total_cut_seconds = max(sum([max(self.str2pos(cut['t1']) - self.str2pos(cut['t0']), 0) for cut in cutlist]), 1)
			exc_lst = [self._ffmpeg_binary,"-y","-hide_banner","-loglevel","error","-nostats","-progress","pipe:1","-i"]
			file_lst = [f"{self._foldername(movie)}part{i}.ts" for i in range(len(cutlist))]
			exc_lst += [f"concat:" + '|'.join(file_lst),"-c","copy",f"{targetname}"]
			try:
				print("---------------------------------")
				print(f"exc_lst: {exc_lst}")
				print("---------------------------------")
				res = self._run_ffmpeg_cut_process(exc_lst, movie, 'join', 85, 100, total_cut_seconds)
				print(f"'{self._filename(movie)}' wurde mit ffmeg zusammengefügt.")
				# delete part*.ts files
				for i in range(len(cutlist)):
					os.remove(f"{self._foldername(movie)}part{i}.ts")
				return res
			except subprocess.CalledProcessError as e:
				raise e
		else:
			try:
				if os.path.exists(targetname):
					os.remove(targetname)
				os.rename(f"{self._foldername(movie)}part0.ts",targetname)
	
 				# remove .ap and .sc files, if they exist
				# print(f"targetname: {targetname}, {targetname+'.ap'}, {targetname+'.sc'}")	
				if os.path.exists(targetname+'.ap'):
					os.remove(targetname+'.ap')
				if os.path.exists(targetname+'.sc'):
					os.remove(targetname+'.sc')

				return f"{self._foldername(movie)}part0.ts wurde in {targetname} umbenannt."
			except FileNotFoundError as e:
				raise e

	def _ffmpegsplit(self, movie, cutlist, inplace = False):
		print()
		print(f"'{self._filename(movie)}' wird mit ffmpeg geschnitten. -]+{cutlist}+[- ")
		total_cut_seconds = max(sum([max(self.str2pos(cut['t1']) - self.str2pos(cut['t0']), 0) for cut in cutlist]), 1)
		processed_seconds = 0
		results = []
		for i, cut in enumerate(cutlist):
			cut_seconds = max(self.str2pos(cut['t1']) - self.str2pos(cut['t0']), 1)
			phase_start = int((processed_seconds / total_cut_seconds) * 85)
			processed_seconds += cut_seconds
			phase_end = int((processed_seconds / total_cut_seconds) * 85)
			exc_lst = [
				self._ffmpeg_binary, "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1",
				"-ss", f"{cut['t0']}", "-to", f"{cut['t1']}", "-i", f"{self._pathname(movie)}",
				"-map", "0:v", "-map", "0:a", "-map", "0:s?", "-c", "copy", f"{self._foldername(movie)}part{i}.ts"
			]
			try:
				print("---------------------------------")
				print(f"exc_lst: {exc_lst}")
				print("---------------------------------")
				results.append(self._run_ffmpeg_cut_process(exc_lst, movie, f'split {i+1}/{len(cutlist)}', phase_start, phase_end, cut_seconds))
			except subprocess.CalledProcessError as e:
				raise e
		print(f"'{self._filename(movie)}' wurde mit ffmeg nach {self._foldername(movie)}part0.ts geschnitten.")
		return "\n".join(results)

	def cut(self, movie, cutlist, inplace=False):
		t0 = time.time()
		t1 = time.time() #initialize t1, in case no first run applies (e.g.) .ap files already exist ...
		restxt = 'cut started ... \n'
		resdict = {
			'name': movie.title,
			'inplace': inplace,
			'engine': 'ffmpeg'
		}
		self._set_cut_progress('preparing', 0, movie.title)
		self.ensure_media(movie)
		#check ob .ap und .sc Dateien existieren, wenn nicht, erzeugen
		restxt += f"{self._filename(movie)} exists ? {os.path.exists(self._pathname(movie))}\n"
		restxt += f"{self._filename(movie)+'.ap'} exists ? {os.path.exists(self._pathname(movie)+'.ap')}\n"
		restxt += f"{self._filename(movie)+'.sc'} exists ? {os.path.exists(self._pathname(movie)+'.sc')}\n\n"

		if ((inplace == False) and (os.path.exists(self._cutname(movie)))):
			try:
				os.remove(self._cutname(movie))
				if os.path.exists(self._cutname(movie)+'.ap'):
					os.remove(self._cutname(movie)+'.ap')
				if os.path.exists(self._cutname(movie)+'.cuts'):
					os.remove(self._cutname(movie)+'.cuts')
				if os.path.exists(self._cutname(movie)+'.sc'):
					os.remove(self._cutname(movie)+'.sc')
				restxt += f"*_cut.ts file existed, deleted ... \n\n"
			except FileNotFoundError as e:
				print(str(e))


		try:
			t1=time.time()
			res = self._ffmpegsplit(movie,cutlist,inplace)
			print("---------------------------------")
			print("FFMPEG split Result: ", res)
			print("---------------------------------")
			restxt += f"Result FFMpeg Spit: {res}\n"
			restxt += f"Split Time: {(t1 - t0):7.0f} sec.\n\n"
			resdict.update({
					'FFSplitTime': (t1-t0)
			})
			res2 = self._ffmpegjoin(movie,cutlist,inplace)
			print("---------------------------------")
			print("FFMPEG join Result: ", res2)
			print("---------------------------------")
			t2 = time.time()
			restxt += f"Ergebnis FFMPEG Join: {res2}\n"
		except subprocess.CalledProcessError as e:
			raise e

		if ((inplace == True) and (os.path.exists(self._cutname(movie)))):
			try:
				os.remove(self._cutname(movie))
				if os.path.exists(self._cutname(movie)+'.ap'):
					os.remove(self._cutname(movie)+'.ap')
				if os.path.exists(self._cutname(movie)+'.cuts'):
					os.remove(self._cutname(movie)+'.cuts')
				if os.path.exists(self._cutname(movie)+'.sc'):
					os.remove(self._cutname(movie)+'.sc')
				restxt += f"cut successful, *_cut.ts file deleted.\n"
			except FileNotFoundError as e:
				print(str(e))

		restxt += f"Cut Time    : {(t2 - t1):7.0f} sec.\n"
		restxt += f"Total Time  : {(t2 - t0):7.0f} sec.\n\n"
		resdict.update({
			'CutTime': (t2 - t1),
			'TotalTime': (t2 - t0),
		})
		self._set_cut_progress('finished', 100, movie.title)
		print(f"elapsed time: {(t2 - t0):7.0f} sec.")
		if self.target != "":
			self.delete_target_files()
			self.target = ""
		return resdict
		#self.umount()
