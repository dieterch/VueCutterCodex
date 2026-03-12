import asyncio
import os
import time
import concurrent.futures
import subprocess
import shlex
import re
from pprint import pformat as pf

class MediaUnavailableError(FileNotFoundError):
	def __init__(self, path):
		super().__init__(f"Media source unavailable: '{path}' is missing. Ensure the NAS is online and the host media path is mounted.")
		self.path = path

class CutterInterface:
	def __init__(self, server):
		self._server = server
		self._ffmpeg_binary = '/usr/bin/ffmpeg'
		self._media_root = os.getenv('VUECUTTER_MEDIA_ROOT', '').rstrip('/')
		self._media_keep_share = os.getenv('VUECUTTER_MEDIA_KEEP_SHARE', 'true').lower() != 'false'
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
			res = await subprocess.check_output(exc_lst)
			res = res.decode('utf-8')
			print(res)
		except subprocess.CalledProcessError as err:
			print(str(err))
		finally:
			#self.umount()
			t1 = time.time()
			print(f"\nIn aframe:{(t1-t0):5.2f} sec.")
			return frame_name

	def _run_ffmpeg_detection(self, movie, exc_lst):
		self.ensure_media(movie)
		completed = subprocess.run(
			exc_lst,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
			check=False
		)
		if completed.returncode != 0:
			raise subprocess.CalledProcessError(
				completed.returncode,
				exc_lst,
				output=completed.stdout,
				stderr=completed.stderr
			)
		return f"{completed.stdout}\n{completed.stderr}"

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

	def analyze_recording(self, movie):
		t0 = time.time()
		self.ensure_media(movie)
		path = self._pathname(movie)
		duration_seconds = max(int(movie.duration // 1000), 0)
		warnings = []
		black_log = self._run_ffmpeg_detection(movie, [
			self._ffmpeg_binary,
			'-hide_banner',
			'-loglevel', 'info',
			'-i', path,
			'-vf', 'blackdetect=d=0.4:pic_th=0.98',
			'-an',
			'-f', 'null',
			'-'
		])
		black_events = self._parse_black_events(black_log)
		try:
			silence_log = self._run_ffmpeg_detection(movie, [
				self._ffmpeg_binary,
				'-hide_banner',
				'-loglevel', 'info',
				'-i', path,
				'-af', 'silencedetect=n=-35dB:d=0.5',
				'-vn',
				'-f', 'null',
				'-'
			])
			silence_events = self._parse_silence_events(silence_log)
		except subprocess.CalledProcessError:
			silence_events = []
			warnings.append('Audio silence detection was unavailable; using video-only boundary hints.')
		clusters = self._cluster_points_from_events(black_events, silence_events)
		start_cluster = self._choose_content_start(clusters, duration_seconds)
		end_cluster = self._choose_content_end(clusters, duration_seconds)
		boundaries = []
		if start_cluster is None:
			warnings.append('No confident content start detected; defaulting to recording start.')
			boundaries.append({'id': 'content-start', 'kind': 'content_start', 'time': self.pos2str(0), 'confidence': 0.1})
		else:
			boundaries.append({
				'id': 'content-start',
				'kind': 'content_start',
				'time': self.pos2str(int(start_cluster['time'])),
				'confidence': round(min(start_cluster['score'] / 3.0, 1.0), 2),
			})
		if end_cluster is None:
			warnings.append('No confident content end detected; defaulting to recording end.')
			boundaries.append({'id': 'content-end', 'kind': 'content_end', 'time': self.pos2str(duration_seconds), 'confidence': 0.1})
		else:
			boundaries.append({
				'id': 'content-end',
				'kind': 'content_end',
				'time': self.pos2str(int(end_cluster['time'])),
				'confidence': round(min(end_cluster['score'] / 3.0, 1.0), 2),
			})
		content_start_seconds = self.str2pos(next(boundary['time'] for boundary in boundaries if boundary['kind'] == 'content_start'))
		content_end_seconds = self.str2pos(next(boundary['time'] for boundary in boundaries if boundary['kind'] == 'content_end'))
		for pair_index, (ad_start, ad_end) in enumerate(self._pair_ad_clusters(clusters, content_start_seconds, content_end_seconds)):
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
		boundaries = sorted(boundaries, key=lambda boundary: self.str2pos(boundary['time']))
		keep_intervals, interval_warnings = self._derive_keep_intervals(boundaries)
		warnings.extend(interval_warnings)
		return {
			'movie': movie.title,
			'duration': self.pos2str(duration_seconds),
			'boundaries': boundaries,
			'keep_intervals': keep_intervals,
			'warnings': warnings,
			'analysis_seconds': round(time.time() - t0, 2),
		}

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
			exc_lst = [self._ffmpeg_binary,"-y","-hide_banner","-loglevel","fatal", "-i"]
			file_lst = [f"{self._foldername(movie)}part{i}.ts" for i in range(len(cutlist))]
			exc_lst += [f"concat:" + '|'.join(file_lst),"-c","copy",f"{targetname}"]
			try:
				print("---------------------------------")
				print(f"exc_lst: {exc_lst}")
				print("---------------------------------")
				res = subprocess.check_output(exc_lst)
				res = res.decode('utf-8')
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
		exc_lst = [self._ffmpeg_binary,"-y","-hide_banner","-loglevel","fatal"]
		map_lst = []
		for i, cut  in enumerate(cutlist):
			exc_lst += ["-ss",f"{cut['t0']}","-to",f"{cut['t1']}","-i",f"{self._pathname(movie)}"]
			map_lst += [f"-map",f"{i}:v","-map",f"{i}:a","-map",f"{i}:s?", "-c", "copy", f"{self._foldername(movie)}part{i}.ts"]
		exc_lst += map_lst
		try:
			print("---------------------------------")
			print(f"exc_lst: {exc_lst}")
			print("---------------------------------")
			res = subprocess.check_output(exc_lst)
			res = res.decode('utf-8')
			print(f"'{self._filename(movie)}' wurde mit ffmeg nach {self._foldername(movie)}part0.ts geschnitten.")
			return res
		except subprocess.CalledProcessError as e:
			raise e

	def cut(self, movie, cutlist, inplace=False):
		t0 = time.time()
		t1 = time.time() #initialize t1, in case no first run applies (e.g.) .ap files already exist ...
		restxt = 'cut started ... \n'
		resdict = {
			'name': movie.title,
			'inplace': inplace,
			'engine': 'ffmpeg'
		}
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
		print(f"elapsed time: {(t2 - t0):7.0f} sec.")
		if self.target != "":
			self.delete_target_files()
			self.target = ""
		return resdict
		#self.umount()
