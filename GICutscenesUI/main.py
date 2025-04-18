from tkinter import Tk, font
from tkinter.filedialog import askdirectory, askopenfilename, askopenfilenames
import eel
import sys, os
import shutil
import subprocess
import json
from json_minify import json_minify
import re
import base64
import requests
from subtitles import *

CONSOLE_DEBUG_MODE = False
__version__ = '0.9.1'

# ---- Required Functions ----

def resource_path(relative_path=""):
	""" Get absolute path to resource, works for dev and for PyInstaller """
	base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(base_path, relative_path)

@eel.expose
def get_version():
	return __version__

# ---- Locales ----

remove_coma_regex = r'''(?<=[}\]"']),(?!\s*[{["'])'''

@eel.expose
def get_translation(code):
	tr_file = os.path.join(resource_path("web"), "locales", code + ".json")
	if os.path.exists(tr_file):
		with open(tr_file, 'r', encoding="utf-8-sig") as file:
			string = json_minify(file.read()) # remove comments
			string = re.sub(remove_coma_regex, "", string, 0) # remove coma at the end
			output = json.loads(string)
			return output

def load_subs_preview_text():
	file = os.path.join(resource_path("web"), "locales", "subtitles_preview.json")
	with open(file, 'r', encoding="utf-8-sig") as f:
		string = re.sub(remove_coma_regex, "", f.read(), 0)
		data = json.loads(string)
	def wraper(lang): return data.get(lang, data.get('en'))
	return wraper

SUBTITLES_PREVIEW_TEXT = load_subs_preview_text()


# ---- EXE Functions ----

def find_script(script_name):
	def find_in(folder):
		files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
		if script_name in files:
			return os.path.join(folder, script_name)
	
	result = find_in(os.getcwd())
	if result: return result

	result = find_in(resource_path())
	if result: return result

def file_in_temp(file):
	return os.path.dirname(file) == os.path.dirname(resource_path(os.path.basename(file)))


# ---- Settings Functions ----

def load_settings_inline():
	global SCRIPT_FILE, OUTPUT_F, FFMPEG, SUBTITLES_F
	set_file = os.path.join(os.getcwd(), "UI-settings.json")
	settings = {}
	if os.path.exists(set_file):
		with open(set_file, 'r', encoding='utf-8') as file:
			settings = json.loads(file.read())
			if "script_file" in settings.keys():
				SCRIPT_FILE = settings["script_file"]
			if "output_folder" in settings.keys():
				OUTPUT_F = settings["output_folder"]
			if "FFMPEG" in settings.keys():
				FFMPEG = settings["FFMPEG"]
			if "subtitles_folder" in settings.keys():
				SUBTITLES_F = settings["subtitles_folder"]

	SCRIPT_FILE = settings.get("script_file") or find_script("GICutscenes.exe")
	OUTPUT_F = settings.get("output_folder") or os.path.join(os.getcwd(), "output")
	FFMPEG = settings.get("FFMPEG") or find_script("ffmpeg.exe") or "ffmpeg"
	SUBTITLES_F = settings.get("subtitles_folder") or ""

	if os.path.exists(os.path.join(os.getcwd(), "versions.json")) and file_in_temp(SCRIPT_FILE):
		local_ver_file = os.path.join(os.getcwd(), "versions.json")
		temp_ver_file = os.path.join(os.path.dirname(SCRIPT_FILE), "versions.json")
		with open(local_ver_file, 'r') as orig_file:
			data = orig_file.read()
		with open(temp_ver_file, 'w') as temp_file:
			temp_file.write(data)

load_settings_inline()

@eel.expose
def load_settings():
	set_file = os.path.join(os.getcwd(), "UI-settings.json")
	if os.path.exists(set_file):
		with open(set_file, 'r', encoding='utf-8') as file:
			settings = json.loads(file.read())
			return settings
	return {}

@eel.expose
def save_settings(settings):
	settings['output_folder'] = OUTPUT_F
	settings['subtitles_folder'] = SUBTITLES_F
	if not file_in_temp(SCRIPT_FILE):
		settings['script_file'] = SCRIPT_FILE
	if not file_in_temp(FFMPEG):
		settings['FFMPEG'] = FFMPEG

	with open(os.path.join(os.getcwd(), "UI-settings.json"), 'w', encoding='utf-8') as file:
		file.write(json.dumps(settings, indent=4, ensure_ascii=False))
	return True

@eel.expose
def delete_settings():
	global SCRIPT_FILE, OUTPUT_F, FFMPEG, SUBTITLES_F
	SCRIPT_FILE = find_script("GICutscenes.exe")
	OUTPUT_F = os.path.join(os.getcwd(), "output")
	FFMPEG = find_script("ffmpeg.exe") or "ffmpeg"
	SUBTITLES_F = ""
	
	set_file = os.path.join(os.getcwd(), "UI-settings.json")
	if os.path.exists(set_file):
		os.remove(set_file)
		return True
	return False



# ---- About Tab Functions ----

@eel.expose
def get_GICutscenes_ver():
	if SCRIPT_FILE:
		process = subprocess.Popen([SCRIPT_FILE, "--version"], stdout=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
		answer = process.communicate()[0]
		try:
			text = answer.decode('utf-8')
		except UnicodeDecodeError:
			text = answer.decode(os.device_encoding(0))
		return text.strip()

def get_ffmpeg_output(cmd):
	process = subprocess.Popen([
		FFMPEG, "-hide_banner"] + cmd,
		stdout=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW
	)
	answer = process.communicate()[0]
	try:
		text = answer.decode('utf-8')
	except UnicodeDecodeError:
		text = answer.decode(os.device_encoding(0))
	return text

@eel.expose
def get_ffmpeg_ver():
	def find_ver(text):
		return text.splitlines()[0].split("ffmpeg version")[-1].strip().split()[0]
	def find_year(text):
		match = re.findall(r'\b([1-3][0-9]{3})\b', text)
		if match is not None:
			return match
	try:
		text = get_ffmpeg_output(['-version'])
		final = {'ver': find_ver(text.strip()), 'year': find_year(text.strip())}
		return final
	except: return {}


def parse_releases(relative_path):
	r = requests.get(f'https://api.github.com/repos/{relative_path}/tags')
	if r.status_code == 200:
		answer = r.json()
		latest = answer[0]["name"]
		return latest
	else:
		r = requests.get(f'https://github.com/{relative_path}/tags')
		links = []
		for line in r.text.split("\n"):
			match = re.search(r"href=\"(.+)\">", line)
			if match:
				links.append(match.group(1))

		pat = re.compile(r'releases\/tag')
		content = [ s for s in links if pat.findall(s) ]
		latest = sorted(content)[-1].split("/")[-1]
		return latest

@eel.expose
def get_latest_ui_version():
	return parse_releases('SuperZombi/GICutscenesUI')

@eel.expose
def get_latest_script_version():
	return parse_releases('ToaHartor/GI-cutscenes')

@eel.expose
def compare_version_files():
	if SCRIPT_FILE:
		local_ver_file = os.path.join(
			os.path.dirname(SCRIPT_FILE),
			"versions.json"
		)
		if os.path.exists(local_ver_file):
			with open(local_ver_file, 'r') as file:
				LOCAL = file.read()

			try:
				r = requests.get("https://raw.githubusercontent.com/ToaHartor/GI-cutscenes/main/versions.json")
				GLOBAL = r.text

				if json.loads(LOCAL) == json.loads(GLOBAL):
					return {"success": True, "status": True}
				else:
					return {"success": True, "status": False}
			except: None
	return {"success": False}

@eel.expose
def download_latest_version_file():
	r = requests.get("https://raw.githubusercontent.com/ToaHartor/GI-cutscenes/main/versions.json")
	local_ver_file = os.path.join(os.path.dirname(SCRIPT_FILE), "versions.json")
	with open(local_ver_file, 'w') as file:
		file.write(r.text)

	if file_in_temp(SCRIPT_FILE):
		local_ver_file = os.path.join(os.getcwd(), "versions.json")
		with open(local_ver_file, 'w') as file:
			file.write(r.text)


# ---- Logger Functions ----

def send_message_to_ui_output(type_, message):
	eel.putMessageInOutput(type_, message)()

def log_subprocess_output(pipe, process=None):
	for line in pipe:
		if process:
			if STOPED_BY_USER:
				process.kill()
		send_message_to_ui_output("console", line.strip())


# ---- Explorer Functions ----

def get_disks():
	import win32api
	return [d for d in win32api.GetLogicalDriveStrings()[0]]

@eel.expose
def get_all_fonts():
	root = Tk()
	root.withdraw()
	return sorted(set(font.families()))

@eel.expose
def ask_files():
	root = Tk()
	root.withdraw()
	root.wm_attributes('-topmost', 1)
	files = askopenfilenames(initialdir=GENSHIN_FOLDER, parent=root,
		filetypes=[("Genshin Impact Cutscene", "*.usm"), ("All files", "*.*")]
	)
	return files

def ask_folder():
	root = Tk()
	root.withdraw()
	root.wm_attributes('-topmost', 1)
	return askdirectory(parent=root)

@eel.expose
def get_output_folder():
	return OUTPUT_F

@eel.expose
def get_subtitles_folder():
	return SUBTITLES_F

@eel.expose
def ask_output_folder():
	global OUTPUT_F
	folder = ask_folder()
	if folder: OUTPUT_F = folder
	return OUTPUT_F

@eel.expose
def ask_subtitles_folder():
	global SUBTITLES_F
	folder = ask_folder()
	if folder: SUBTITLES_F = folder
	return SUBTITLES_F

@eel.expose
def open_output_folder():
	if os.name == "nt":
		subprocess.run(['explorer', OUTPUT_F], creationflags=subprocess.CREATE_NO_WINDOW)
	elif os.name == "posix":
		subprocess.run(['xdg-open', OUTPUT_F], creationflags=subprocess.CREATE_NO_WINDOW)

def find_genshin_folder():
	if os.name == "nt":
		templates = (
			('Games', 'Genshin Impact'),
			('Program Files', 'Genshin Impact'),
			('Program Files', 'HoYoPlay', 'games')
		)
		for _disk in get_disks():
			disk = f'{_disk}:'+os.sep
			for template in templates:
				path = os.path.join(disk, *template)
				if os.path.exists(path):
					assets = os.path.join(path, "Genshin Impact game", "GenshinImpact_Data", "StreamingAssets", "VideoAssets", "StandaloneWindows64")
					if os.path.exists(assets): return assets
					print("[WARN] Assets not found!")
GENSHIN_FOLDER = find_genshin_folder()


# ---- Subtitles Functions ----
@eel.expose
def make_subs_preview(args):
	params = {
		"tempfile": "temp.ass",
		"width": 1920, "height": 1080,
		**args
	}
	width, height, tempfile = params.pop("width"), params.pop("height"), params.pop("tempfile")
	make_subs_template(text=SUBTITLES_PREVIEW_TEXT(params.pop("lang")), file=tempfile, **params)
	cmd = [
		FFMPEG, '-f', 'lavfi', '-i', 
		f'color=color=black@0.0:size={width}x{height},format=rgba,subtitles={tempfile}:alpha=1', 
		'-vframes', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'
	]
	process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
	output, error = process.communicate()
	os.remove(tempfile)
	if process.returncode == 0:
		img_base64 = base64.b64encode(output).decode('utf-8')
		data_url = f"data:image/png;base64,{img_base64}"
		return data_url


# ---- GPU Functions ----
GPU_args = {
	"nvidia": {
		"decode": 'cuda',
		"encode": 'h264_nvenc'
	},
	"intel": {
		"decode": 'qsv',
		"encode": 'h264_qsv'
	},
	"amd": {
		"encode": "h264_amf"
	}
}
def test_encoder(encoder, decoder=None):
	try:
		cmd = [
			FFMPEG, '-f', 'lavfi', '-i', 
			'color=black:size=360x360', 
			'-vframes', '1', '-f', "null",
			'-vcodec', encoder, '-'
		]
		process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
		returncode = process.wait()
		if returncode == 0: return True
	except: None

@eel.expose
def get_ffmpeg_supports():
	suported = []
	for gpu, args in GPU_args.items():
		if test_encoder(args.get("encode")):
			suported.append(gpu)
	return suported


# ---- MAIN Functions ----
STOPED_BY_USER = None
@eel.expose
def stop_work():
	global STOPED_BY_USER
	STOPED_BY_USER = True

@eel.expose
def start_work(files, args):
	global STOPED_BY_USER
	STOPED_BY_USER = False
	send_message_to_ui_output("event", "start")
	file_lenth = len(files)
	send_message_to_ui_output("file_count", [0, file_lenth])
	# Make folders
	temp_folder = resource_path("Temp")
	if not os.path.exists(temp_folder):
		os.mkdir(temp_folder)
	if not os.path.exists(OUTPUT_F):
		os.mkdir(OUTPUT_F)

	OLD_DIR = os.getcwd()
	os.chdir(os.path.dirname(SCRIPT_FILE))

	for i, file in enumerate(files):
		if STOPED_BY_USER: break
		else:
			send_message_to_ui_output("file_count", [i, file_lenth])
			send_message_to_ui_output("event", "copy_files")
			send_message_to_ui_output("work_file", file)
			send_message_to_ui_output("console", f"----- {os.path.basename(file)} -----")
			send_message_to_ui_output("event", "run_demux")
			# MAIN CALL
			p_status = 0
			if CONSOLE_DEBUG_MODE:
				subprocess.call([SCRIPT_FILE, 'demuxUsm', file, '--output', OUTPUT_F])
			else:
				process = subprocess.Popen([SCRIPT_FILE, 'demuxUsm', file, '--output', OUTPUT_F], encoding=os.device_encoding(0), universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
				with process.stdout:
					log_subprocess_output(process.stdout)
				p_status = process.wait()

			if p_status != 0:
				send_message_to_ui_output("event", "error")
				send_message_to_ui_output("sub_work", {"name": "keys", "status": False})
			else:
				send_message_to_ui_output("event", "rename_files")

				# Rename to m2v
				old_file_name = os.path.splitext(os.path.basename(file))[0]
				file_name = str(old_file_name) + ".ivf"
				new_file_name = str(old_file_name) + ".m2v"
				file_name = os.path.join(OUTPUT_F, file_name)
				new_file_name = os.path.join(OUTPUT_F, new_file_name)
				if os.path.exists(file_name):
					if os.path.exists(new_file_name): os.remove(new_file_name)
					os.rename(file_name, new_file_name)
				else:
					send_message_to_ui_output("console", "\n")
					send_message_to_ui_output("event", "error")
					send_message_to_ui_output("sub_work", {"name": "keys", "status": False})
					continue

				# Delete hca encoded Audio (cuz wav files decoded)
				for index in [0, 1, 2, 3]:
					f = str(old_file_name) + "_" + str(index) + ".hca"
					f = os.path.join(OUTPUT_F, f)
					if os.path.exists(f):
						os.remove(f)

				# Merge Video and Audio
				if args['merge']:
					if STOPED_BY_USER: break
					else:
						audio_index = int(args['audio_index'])
						audio_file = os.path.join(OUTPUT_F , str(old_file_name) + "_" + str(audio_index) + ".wav")
						output_file = os.path.join(OUTPUT_F, str(old_file_name) + ".mp4")

						# Subtitles
						subtitles_file = None
						if args['subtitles']:
							send_message_to_ui_output("console", "\nSearching for subtitles")

							if args.get('subtitles_provider') == "local":
								if args.get('subtitles_folder'):
									subtitles = find_subtitles(
										old_file_name,
										provider=args.get('subtitles_folder'),
										lang=args.get('subtitles_lang')
									)
							elif args.get('subtitles_provider') == "url":
								if args.get('subtitles_url'):
									subtitles = find_subtitles(
										old_file_name,
										provider=args.get('subtitles_url'),
										lang=args.get('subtitles_lang')
									)
							else:
								subtitles = find_subtitles(
									old_file_name,
									provider=args.get('subtitles_provider'),
									lang=args.get('subtitles_lang')
								)

							if not subtitles:
								send_message_to_ui_output("console", "Subtitles not found!")
								send_message_to_ui_output("sub_work", {"name": "subtitles", "status": False})
							else:
								send_message_to_ui_output("console", "Converting subtitles")
								send_message_to_ui_output("sub_work", {"name": "subtitles", "status": True})
								subtitles_file = os.path.join(OUTPUT_F, str(old_file_name) + ".ass")
								srt_to_ass(
									subtitles,
									subtitles_file,
									font_name=args.get('subtitles_font'),
									font_size=args.get('subtitles_fontsize'),
									text_color=args.get('subtitles_text_color'),
									outline_color=args.get('subtitles_outline_color'),
									outline_width=args.get('subtitles_outline_width'),
									letter_spacing=args.get('subtitles_letter_spacing'),
									bold=args.get('subtitles_bold'),
									italic=args.get('subtitles_italic')
								)

						# Merging
						send_message_to_ui_output("event", "run_merge")
						send_message_to_ui_output("console", "\nStarting ffmpeg")
						if os.path.exists(output_file):
							send_message_to_ui_output("console", f'File {output_file} already exists.')
							os.remove(output_file)

						send_message_to_ui_output("console", "Working ffmpeg...")
						p_status = 0
						bitrate = int(args['video_quality']) * 1000
						gp_args = GPU_args[args.get('gpu')] if args.get('gpu') and args.get('gpu') in GPU_args else {}
						command = [FFMPEG, '-hide_banner']
						if "decode" in gp_args:
							if gp_args['decode'] == "qsv" and subtitles_file: pass
							else:
								command += ['-hwaccel', gp_args['decode']]
						command += [
							'-i', new_file_name,
							'-i', audio_file
						]
						if subtitles_file:
							subs_file = subtitles_file.replace("\\", "/").replace(":", "\\\\\\:")
							command += ["-vf", f'subtitles={subs_file}']
						if "encode" in gp_args:
							command += ['-c:v', gp_args['encode']]
						command += [
							'-b:v', str(bitrate),
							'-b:a', '192K',
							output_file
						]

						if CONSOLE_DEBUG_MODE:
							subprocess.call(command)
						else:
							process = subprocess.Popen(command, encoding='utf-8', universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
							with process.stderr:
								log_subprocess_output(process.stderr, process)
							p_status = process.wait()

						if p_status != 0:
							if os.path.exists(output_file): os.remove(output_file)
							send_message_to_ui_output("event", "error")
							continue
						else:
							send_message_to_ui_output("console", "Merging complete!")
							if args['delete_after_merge']:
								send_message_to_ui_output("console", "Removing trash...")
								if subtitles_file: os.remove(subtitles_file)
								files_to_remove = [
									old_file_name + ".m2v",
									*[f"{old_file_name}_{i}.wav" for i in [0, 1, 2, 3]]
								]
								files_to_remove = list(map(lambda x: os.path.join(OUTPUT_F, x),files_to_remove))
								for f in files_to_remove:
									os.remove(f)
								send_message_to_ui_output("console", "OK")

				if i != file_lenth - 1:
					send_message_to_ui_output("console", "\n")

				send_message_to_ui_output("event", "ok")

	send_message_to_ui_output("event", "finish")
	if STOPED_BY_USER:
		send_message_to_ui_output("console", "\nStoped by user")
		send_message_to_ui_output("event", "stoped")
	else:
		send_message_to_ui_output("file_count", [file_lenth, file_lenth])
	shutil.rmtree(temp_folder)
	os.chdir(OLD_DIR)


eel.init(resource_path("web"))

browsers = ['chrome', 'default']
for browser in browsers:
	try:
		eel.start("main.html", size=(600, 800), mode=browser, port=0)
		break
	except Exception:
		print(f"Failed to launch the app using {browser.title()} browser")
