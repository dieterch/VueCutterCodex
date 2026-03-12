import asyncio
import os
import time
import concurrent.futures
import subprocess
import shlex
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
