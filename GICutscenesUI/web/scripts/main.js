window.onload = async _=>{
	let tab_now = window.location.hash.split("#").at(-1)
	if (tab_now){
		openTab(tab_now)
	}
	let version = await eel.get_version()();
	document.getElementById("version").innerHTML = version;

	let folder = await eel.get_script_file()();
	update_path(folder, document.getElementById("script_path"))
	load_settings()
	getTranslation()
	get_output_folder()
}

function openTab(tab){
	window.location.hash = tab
	document.querySelector(".tabcontent.showed").classList.remove("showed")
	document.getElementById(tab).classList.add("showed")
	document.querySelector(".tab > button.active").classList.remove("active")
	document.querySelector(`.tab > button[data=${tab}]`).classList.add("active")
}


async function change_script_folder(){
	var folder = await eel.ask_script_file()();
	update_path(folder, document.getElementById("script_path"))
}
function update_path(path, input){
	if (path){
		input.value = path
		input.style.width = input.value.length + "ch";
		input.style.borderColor = ""
	}
	else{
		input.style.borderColor = "red"
	}
}


async function selectFiles(){
	var files = await eel.ask_files()();
	if (files && files.length > 0){
		updatePreview(files)
	}
}
function updatePreview(files){
	let preview = document.getElementById("preview_zone")
	preview.innerHTML = '<summary></summary>'
	files.forEach(e=>{
		preview.innerHTML += `<div path='${e}'>${e.replace(/^.*[\\\/]/, '')}</div>`
	})
}


var BLOCK_START = false;
async function start(){
	if (!BLOCK_START){
		var files = []
		Array.from(document.getElementById("preview_zone").getElementsByTagName("div")).forEach(e=>{
			files.push(e.getAttribute("path"))
		})

		if (files.length > 0){
			if (document.getElementById("script_path").value){
				// MAIN CALL
				let settings = parseSettings()
				document.getElementById("progress").style.display = "block"
				await eel.start_work(files, settings)();
			}
			else{
				openTab('settings')
				setTimeout(()=>{
					alert(LANG("select_script_file"))
				},10)
			}
		}
		else{
			alert(LANG("no_files"))
		}
	}
}