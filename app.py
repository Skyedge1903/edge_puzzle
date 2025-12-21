from flask import Flask, render_template_string, send_from_directory, jsonify
import os
import re
import json

app = Flask(__name__)
IMG_FOLDER = "img"
LOG_FILE = "log.json"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Top Solutions Puzzle</title>
<style>
html, body {
    margin: 0;
    padding: 0;
    height: 100%;
    overflow: hidden;
}
body {
    font-family: "Fira Code", monospace;
    background-color: #1e1e1e;
    color: #c5c5c5;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    padding: 20px;
    min-height: 100vh;
}

/* Console window */
#log-window-container {
    width: calc(280px * 3 + 30px);
    margin-bottom: 10px;
}
#log-window {
    height: 264px; /* 12 lignes */
    background-color: #111;
    padding: 6px;
    overflow-y: auto;
    scrollbar-width: none;
    font-size: 14px;
    line-height: 1.2;
}
#log-window::-webkit-scrollbar { display: none; }
.log-entry {
    white-space: pre;
    margin: 0;
}
.key { color: #00ffcc; }
.value { color: #ffdd00; }

/* Fenêtres MacOS pour puzzles */
.gallery {
    display: flex;
    justify-content: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 10px;
}
.window {
    width: 280px;
    background-color: #111;
    border-radius: 10px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.8);
    overflow: hidden;
    margin-bottom: 10px;
    transition: transform 0.3s ease;
    cursor: pointer;
}
.title-bar {
    height: 25px;
    background-color: #222;
    display: flex;
    align-items: center;
    padding: 0 10px;
    font-size: 12px;
    color: #c5c5c5;
}
.window-buttons {
    display: flex;
    gap: 6px;
    margin-right: 8px;
}
.button {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}
.close { background-color: #ff605c; }
.minimize { background-color: #ffbd44; }
.maximize { background-color: #00ca56; }

.solution-card img {
    width: 260px;
    max-width: 100%;
    height: auto;
    border-radius: 5px;
    display: block;
    margin: 0 auto;
}

/* Zoom stable pour score */
.solution-card:hover {
    transform: scale(2);
    z-index: 9999;
}
.solution-card:hover img {
    width: auto;
    max-width: 100%;
    max-height: 80vh;
}
</style>
<script>
let currentFiles = {{ current_files | safe }};
let lastLogHash = "";

window.addEventListener('wheel', function(e) { e.preventDefault(); }, { passive: false });

function toggleMarks(id) {
    const img = document.getElementById(id);
    const withoutSrc = img.dataset.without;
    const withSrc = img.dataset.with;
    img.src = (img.src.endsWith(withoutSrc)) ? withSrc : withoutSrc;
}

function padRight(str, length) {
    str = str.toString();
    return str + " ".repeat(Math.max(0, length - str.length));
}

function formatStep(val) {
    return Math.floor(val / 1_000_000) + "M";
}
function formatStepSec(val) {
    return Math.floor(val / 1_000) + "K";
}

function renderLog(entries) {
    const container = document.getElementById("log-window");
    container.innerHTML = "";
    entries.slice(-12).forEach(entry => {
        const best_score = padRight(entry.best_score - 64, 3);
        const seed = padRight(entry.seed, 2);
        const elapsed_time = padRight(Math.floor(entry.elapsed_time), 8); // jusqu'à 100M
        const step = padRight(formatStep(entry.step), 6);
        const steps_per_sec = padRight(formatStepSec(entry.steps_per_sec), 6);

        const div = document.createElement("div");
        div.className = "log-entry";
        div.innerHTML = 
            `<span class="key">best_score</span>: <span class="value">${best_score}</span> | ` +
            `<span class="key">seed</span>: <span class="value">${seed}</span> | ` +
            `<span class="key">elapsed_time</span>: <span class="value">${elapsed_time}</span> | ` +
            `<span class="key">step</span>: <span class="value">${step}</span> | ` +
            `<span class="key">steps_per_sec</span>: <span class="value">${steps_per_sec}</span>`;
        container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
}

async function fetchUpdates() {
    try {
        const respImg = await fetch("/file_list");
        const dataImg = await respImg.json();
        const newFiles = dataImg.files;
        const added = newFiles.filter(f => !currentFiles.includes(f));
        if (added.length > 0 || newFiles.length !== currentFiles.length) {
            window.location.reload();
            return;
        }

        const respLog = await fetch("/log_data");
        const dataLog = await respLog.json();
        if (dataLog.hash !== lastLogHash) {
            renderLog(dataLog.entries);
            lastLogHash = dataLog.hash;
        }
    } catch(e) {
        console.error(e);
    }
}

setInterval(fetchUpdates, 1000);
</script>
</head>
<body>

<div id="log-window-container" class="window">
    <div class="title-bar">
        <div class="window-buttons">
            <div class="button close"></div>
            <div class="button minimize"></div>
            <div class="button maximize"></div>
        </div>
        Console
    </div>
    <div id="log-window"></div>
</div>

<div class="gallery">
    {% for sol in solutions %}
    <div class="window solution-card" onclick="toggleMarks('img{{ loop.index }}')">
        <div class="title-bar">
            <div class="window-buttons">
                <div class="button close"></div>
                <div class="button minimize"></div>
                <div class="button maximize"></div>
            </div>
            Score: {{ sol.score }}
        </div>
        <img id="img{{ loop.index }}"
             src="/img/{{ sol.without_marks }}"
             data-with="/img/{{ sol.with_marks }}"
             data-without="/img/{{ sol.without_marks }}">
    </div>
    {% endfor %}
</div>

<script>
renderLog({{ log_entries | safe }});
</script>

</body>
</html>
"""

@app.route("/img/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMG_FOLDER, filename)

def get_top_solutions(n=3):
    if not os.path.exists(IMG_FOLDER):
        return []
    files = os.listdir(IMG_FOLDER)
    files_with_marks = [f for f in files if "_with_marks" in f and f.endswith(".jpg")]
    solutions = []
    pattern = r"partial_solution_(\d+)_with_marks\.jpg$"
    for f in files_with_marks:
        match = re.search(pattern, f)
        if match:
            score = int(match.group(1))
            without_file = f.replace("_with_marks", "_without_marks")
            if without_file in files:
                solutions.append({
                    "score": score,
                    "with_marks": f,
                    "without_marks": without_file
                })
    solutions.sort(key=lambda x: x["score"], reverse=True)
    return solutions[:n]

def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
            simplified = []
            for entry in logs:
                simplified.append({
                    "best_score": entry.get("best_score"),
                    "seed": entry.get("seed"),
                    "elapsed_time": entry.get("elapsed_time",0),
                    "step": entry.get("step"),
                    "steps_per_sec": entry.get("steps_per_sec",0)
                })
            return simplified
    except json.JSONDecodeError:
        return []

def hash_log(entries):
    return str(hash(json.dumps(entries)))

@app.route("/")
def index():
    top_solutions = get_top_solutions()
    files = sorted([f for f in os.listdir(IMG_FOLDER) if f.endswith(".jpg")])
    log_entries = read_log()
    return render_template_string(HTML_TEMPLATE, solutions=top_solutions, current_files=files, log_entries=log_entries)

@app.route("/file_list")
def file_list():
    files = sorted([f for f in os.listdir(IMG_FOLDER) if f.endswith(".jpg")])
    return jsonify({"files": files})

@app.route("/log_data")
def log_data():
    entries = read_log()
    return jsonify({"entries": entries, "hash": hash_log(entries)})

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8050)))
